"""Ingest Ookla Speedtest Open Data for fixed and mobile broadband speed measures.

Downloads quarterly speed test tiles from Ookla's S3 bucket for both fixed
and mobile service types, spatially joins them to Census 2020 block group
boundaries, and computes device-weighted speed aggregates. Block group values
are rolled up to Census tracts and counties using simple means.

Fixed measures (all with _geo20 suffix):
  - avg_down_speed_geo20: device-weighted mean download speed (Mb/s)
  - avg_up_speed_geo20: device-weighted mean upload speed (Mb/s)
  - perc_above_25_3_geo20: % of devices with >=25 Mb/s down + >=3 Mb/s up
  - perc_above_100_20_geo20: % of devices with >=100 Mb/s down + >=20 Mb/s up

Mobile measures (all with _geo20 suffix):
  - mobile_avg_down_speed_geo20
  - mobile_avg_up_speed_geo20
  - mobile_perc_above_25_3_geo20
  - mobile_perc_above_100_20_geo20

Data source: https://www.ookla.com/ookla-for-good/open-data
Tile S3 bucket: ookla-open-data.s3-us-west-2.amazonaws.com
"""

from __future__ import annotations

import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.profiles import resolve_profile, resolve_states
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data" / "distribution"
CACHE_DIR = TOPIC_DIR / "data" / "working" / "bg_cache"
GEO_BASE = TOPIC_DIR.parent.parent / "geographies"

log = get_logger("ookla.ingest")

# Ookla S3 URL pattern — tiles are global shapefiles, one per quarter
TILE_URL = (
    "https://ookla-open-data.s3-us-west-2.amazonaws.com/shapefiles/performance"
    "/type={service_type}/year={year}/quarter={quarter}"
    "/{year}-{month:02d}-01_performance_{service_type}_tiles.zip"
)

QUARTER_TO_MONTH = {1: 1, 2: 4, 3: 7, 4: 10}

# Measure name prefix per service type
MEASURE_PREFIX = {"fixed": "", "mobile": "mobile_"}

BASE_MEASURES = ["avg_down_speed", "avg_up_speed", "perc_above_25_3", "perc_above_100_20"]


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def get_tile_url(year: int, quarter: int, service_type: str) -> str:
    """Build the S3 URL for an Ookla quarterly tile shapefile."""
    return TILE_URL.format(
        service_type=service_type,
        year=year,
        quarter=quarter,
        month=QUARTER_TO_MONTH[quarter],
    )


def load_bg_boundaries(profile_name: str) -> gpd.GeoDataFrame:
    """Load Census 2020 block group boundaries for a profile's states.

    Reads from geographies/{profile}/Census Geographies/Block Group/2020/
    and filters to profile counties if applicable (e.g., NCR county subset).
    """
    profile = resolve_profile(profile_name)
    state_fips = {
        "VA": "51", "MD": "24", "DC": "11",
    }

    parts = []
    for state in profile.states:
        # Try profile-specific path first, then state path
        geojson_dir = (
            GEO_BASE / profile_name / "Census Geographies"
            / "Block Group" / "2020" / "data" / "distribution"
        )
        if not geojson_dir.exists():
            geojson_dir = (
                GEO_BASE / state / "Census Geographies"
                / "Block Group" / "2020" / "data" / "distribution"
            )

        geojson_files = list(geojson_dir.glob("*.geojson"))
        if not geojson_files:
            log.warning("No BG GeoJSON found in %s", geojson_dir)
            continue

        gdf = gpd.read_file(geojson_files[0])
        fips = state_fips.get(state, "")

        # Filter to profile counties if specified
        if profile.counties.get(state):
            county_fips = {fips + c for c in profile.counties[state]}
            gdf = gdf[gdf["geoid"].str[:5].isin(county_fips)]

        parts.append(gdf)
        log.info("Loaded %d BGs for %s from %s", len(gdf), state, geojson_files[0].name)

    if not parts:
        raise FileNotFoundError(f"No BG boundaries found for profile {profile_name}")

    bgs = pd.concat(parts, ignore_index=True)
    bgs = bgs.to_crs(epsg=4326)
    return bgs


def download_and_join_tiles(
    year: int,
    quarter: int,
    bgs: gpd.GeoDataFrame,
    service_type: str,
) -> pd.DataFrame | None:
    """Download one quarter of Ookla tiles and spatially join to BGs.

    Returns a DataFrame with columns:
        geoid, avg_d_kbps, avg_u_kbps, devices, tests
    or None if the download fails (e.g., quarter not yet available).
    """
    url = get_tile_url(year, quarter, service_type)
    log.info("Downloading %s tiles: %d-Q%d", service_type, year, quarter)

    try:
        tiles = gpd.read_file(url)
    except Exception as e:
        log.warning("Failed to download %s %d-Q%d: %s", service_type, year, quarter, e)
        return None

    log.info("  %d tiles downloaded", len(tiles))

    # Ensure same CRS
    if tiles.crs != bgs.crs:
        tiles = tiles.to_crs(bgs.crs)

    # Spatial join — inner join keeps only tiles that intersect a BG
    joined = gpd.sjoin(tiles, bgs[["geoid", "geometry"]], how="inner", predicate="intersects")
    log.info("  %d tile-BG intersections", len(joined))

    if joined.empty:
        return None

    return joined[["geoid", "avg_d_kbps", "avg_u_kbps", "devices", "tests"]].copy()


def aggregate_to_bg(joined: pd.DataFrame) -> pd.DataFrame:
    """Aggregate tile-level data to block group level.

    Computes device-weighted average speeds and threshold percentages.
    """

    def _bg_agg(group: pd.DataFrame) -> pd.Series:
        devices = group["devices"].values
        total_devices = devices.sum()

        if total_devices == 0:
            return pd.Series({
                "avg_down_speed": np.nan,
                "avg_up_speed": np.nan,
                "perc_above_25_3": np.nan,
                "perc_above_100_20": np.nan,
            })

        # Device-weighted average speeds (convert kbps → Mbps)
        avg_down = np.average(group["avg_d_kbps"].values, weights=devices) / 1000
        avg_up = np.average(group["avg_u_kbps"].values, weights=devices) / 1000

        # Threshold percentages: % of devices in tiles above threshold
        above_25_3 = (
            (group["avg_d_kbps"] >= 25_000) & (group["avg_u_kbps"] >= 3_000)
        )
        above_100_20 = (
            (group["avg_d_kbps"] >= 100_000) & (group["avg_u_kbps"] >= 20_000)
        )
        perc_25_3 = (devices[above_25_3.values].sum() / total_devices) * 100
        perc_100_20 = (devices[above_100_20.values].sum() / total_devices) * 100

        return pd.Series({
            "avg_down_speed": round(avg_down, 2),
            "avg_up_speed": round(avg_up, 2),
            "perc_above_25_3": round(perc_25_3, 1),
            "perc_above_100_20": round(perc_100_20, 1),
        })

    result = joined.groupby("geoid").apply(_bg_agg).reset_index()
    return result


def annual_average(quarterly_dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """Average quarterly BG values within a year (simple mean across quarters)."""
    if not quarterly_dfs:
        return pd.DataFrame()

    combined = pd.concat(quarterly_dfs, ignore_index=True)
    annual = combined.groupby("geoid")[BASE_MEASURES].mean().reset_index()

    annual["avg_down_speed"] = annual["avg_down_speed"].round(2)
    annual["avg_up_speed"] = annual["avg_up_speed"].round(2)
    annual["perc_above_25_3"] = annual["perc_above_25_3"].round(1)
    annual["perc_above_100_20"] = annual["perc_above_100_20"].round(1)

    return annual


def rollup_geographies(bg_df: pd.DataFrame) -> pd.DataFrame:
    """Roll up BG data to tract and county levels using simple means."""
    # Block group level — already have it
    bg = bg_df.copy()
    bg["region_type"] = "block_group"

    # Tract level — truncate 12-digit BG GEOID to 11-digit tract
    tract = bg_df.copy()
    tract["geoid"] = tract["geoid"].str[:11]
    tract = tract.groupby("geoid")[BASE_MEASURES].mean().reset_index()
    tract["region_type"] = "tract"

    # County level — truncate to 5-digit county
    county = bg_df.copy()
    county["geoid"] = county["geoid"].str[:5]
    county = county.groupby("geoid")[BASE_MEASURES].mean().reset_index()
    county["region_type"] = "county"

    # Round after aggregation
    for level in [tract, county]:
        level["avg_down_speed"] = level["avg_down_speed"].round(2)
        level["avg_up_speed"] = level["avg_up_speed"].round(2)
        level["perc_above_25_3"] = level["perc_above_25_3"].round(1)
        level["perc_above_100_20"] = level["perc_above_100_20"].round(1)

    return pd.concat([bg, tract, county], ignore_index=True)


def to_long_format(wide_df: pd.DataFrame, year: int, service_type: str) -> pd.DataFrame:
    """Convert wide measure columns to standard long format."""
    id_cols = ["geoid", "region_type"]
    prefix = MEASURE_PREFIX[service_type]

    long = wide_df[id_cols + BASE_MEASURES].melt(
        id_vars=id_cols,
        var_name="measure",
        value_name="value",
    )
    long["year"] = year
    long["moe"] = pd.NA

    # Add prefix (mobile_ or nothing) and _geo20 suffix
    long["measure"] = prefix + long["measure"] + "_geo20"

    return long[["geoid", "year", "measure", "value", "moe", "region_type"]]


def _cache_path(profile: str, service_type: str, year: int, quarter: int) -> Path:
    """Path for cached BG-level aggregates."""
    return CACHE_DIR / f"{profile}_{service_type}_{year}_Q{quarter}.csv"


def process_service_type(
    service_type: str,
    years: list[int],
    quarters: list[int],
    bgs: gpd.GeoDataFrame,
    profile_name: str,
) -> list[pd.DataFrame]:
    """Process all years for one service type. Returns list of long DataFrames.

    Caches BG-level aggregates per quarter to data/working/bg_cache/ so
    re-runs skip the expensive download+join+aggregate step.
    """
    prefix = MEASURE_PREFIX[service_type]
    log.info("--- Processing service type: %s (prefix=%r) ---", service_type, prefix)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    all_years_long = []

    for year in years:
        log.info("  Year %d (%s)", year, service_type)
        quarterly_results = []

        for q in quarters:
            cache_file = _cache_path(profile_name, service_type, year, q)

            if cache_file.exists():
                bg_agg = pd.read_csv(cache_file, dtype={"geoid": str})
                log.info("    Q%d: %d BGs (cached)", q, len(bg_agg))
                quarterly_results.append(bg_agg)
                continue

            joined = download_and_join_tiles(year, q, bgs, service_type)
            if joined is not None and not joined.empty:
                bg_agg = aggregate_to_bg(joined)
                bg_agg.to_csv(cache_file, index=False)
                quarterly_results.append(bg_agg)
                log.info("    Q%d: %d BGs with data (saved to cache)", q, len(bg_agg))

        if not quarterly_results:
            log.warning("    No data for %s %d, skipping", service_type, year)
            continue

        annual = annual_average(quarterly_results)
        log.info("    Annual average: %d BGs", len(annual))

        multi_geo = rollup_geographies(annual)
        long = to_long_format(multi_geo, year, service_type)
        all_years_long.append(long)
        log.info("    %d long-format rows", len(long))

    return all_years_long


def run_source(name: str, src: dict, out_dir: Path) -> RunResult:
    """Process one coverage area (NCR or VA) for all service types."""
    t0 = time.time()
    try:
        profile_name = src["profile"]
        years = src["years"]
        quarters = src["quarters"]
        service_types = src.get("service_types", ["fixed"])

        log.info("=== Ingesting source '%s' (profile=%s) ===", name, profile_name)

        # Load BG boundaries once for this profile
        bgs = load_bg_boundaries(profile_name)
        log.info("Loaded %d block groups for %s", len(bgs), profile_name)

        all_long = []
        for stype in service_types:
            long_parts = process_service_type(stype, years, quarters, bgs, profile_name)
            all_long.extend(long_parts)

        if not all_long:
            return RunResult(
                success=False,
                error=f"No data for any year/service_type in source '{name}'",
                duration_sec=time.time() - t0,
            )

        result = pd.concat(all_long, ignore_index=True)

        # Build filename and write
        states = resolve_states(src)
        auto_name = build_file_name(
            df=result,
            states=states,
            years=years,
            source_type=src.get("type", "ookla"),
            title="broadband_speed",
        )
        out_path = write_data(result, out_dir / f"{auto_name}.csv.xz")
        log.info("Wrote %d rows to %s", len(result), out_path)

        return RunResult(
            success=True,
            rows=len(result),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Ingest failed for '%s': %s", name, e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


def run() -> list[RunResult]:
    """Main entry point: process all sources from pipeline.yaml."""
    config = load_config()
    out_dir = DIST_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for name, src in config["sources"].items():
        results.append(run_source(name, src, out_dir))
    return results


if __name__ == "__main__":
    results = run()
    for r in results:
        status = "OK" if r.success else "FAILED"
        log.info("%s — %d rows in %.1fs", status, r.rows, r.duration_sec)
        if r.error:
            log.error("  Error: %s", r.error)
    if any(not r.success for r in results):
        raise SystemExit(1)
