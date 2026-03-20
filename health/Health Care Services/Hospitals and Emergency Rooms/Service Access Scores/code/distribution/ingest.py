"""Ingest hospital accessibility scores for VA and NCR using CMS Hospital Compare data.

Uses CMS Hospital Compare data (2015-2025), geocoded via HIFLD + Census fallback,
ACS total population at block group level, and pre-computed BG-to-BG travel times
to compute 2SFCA, E2SFCA, and 3SFCA access scores.  Each hospital counts as a
single facility (capacity=1), consistent with the original R pipeline.
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sdc_core.census import CensusClient
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

HCS_DIR = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HCS_DIR / "code"))
from compute_service_access import (
    _haversine_km,
    aggregate_bg_to_levels,
    load_travel_times,
    run_fca_variants,
)

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = Path(__file__).resolve().parents[6]
DIST_DIR = TOPIC_DIR / "data" / "distribution"
WORKING_DIR = TOPIC_DIR / "data" / "working"
CENTROIDS_PATH = REPO_DIR / "geographies" / "osrm" / "bg_centroids_2020.csv"

log = get_logger("hospitals.ingest")

NCR_COUNTIES = {
    "51059", "51600", "51610", "51107", "51013", "51510",
    "51683", "51685", "51153",
    "24021", "24031", "24033", "24017",
    "11001",
}

MEASURE_PREFIX = "hosp"
DATA_SOURCE = "cms"

# ACS 5-year latest available year
ACS_MAX_YEAR = 2023


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def load_geocoded_hospitals(config: dict) -> pd.DataFrame:
    """Load the geocoded hospital lookup from the working directory."""
    geo_path = TOPIC_DIR / config["sources"]["cms"]["geocoded_file"]
    if not geo_path.exists():
        # Fall back to old geocoded files
        for alt in [
            WORKING_DIR / "vadcmd_cms_2015_2025_hospitals_geo.csv",
            WORKING_DIR / "ncr_cms_2015_2022_hospitals.csv",
        ]:
            if alt.exists():
                log.warning("Geocoded file not at %s, using %s", geo_path.name, alt.name)
                geo_path = alt
                break
        else:
            raise FileNotFoundError(f"No geocoded hospital file found at {geo_path}")

    geo = pd.read_csv(geo_path, dtype={"facility_id": str, "zip_code": str})
    geo["lat"] = pd.to_numeric(geo["lat"], errors="coerce")
    geo["long"] = pd.to_numeric(geo["long"], errors="coerce")
    geo = geo.dropna(subset=["lat", "long"])
    log.info("Loaded geocoded hospitals: %d records", len(geo))
    return geo


def load_centroids() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load BG centroids, return (geoids, lats, lons) arrays."""
    centroids = pd.read_csv(CENTROIDS_PATH, dtype={"geoid": str})
    return centroids["geoid"].values, centroids["lat"].values, centroids["lon"].values


def snap_to_block_groups(
    hosp_locs: pd.DataFrame,
    bg_geoids: np.ndarray,
    bg_lats: np.ndarray,
    bg_lons: np.ndarray,
) -> pd.DataFrame:
    """Snap hospital locations to nearest block group centroid."""
    bg_assignments = []
    for _, row in hosp_locs.iterrows():
        dists = _haversine_km(bg_lats, bg_lons, row["lat"], row["long"])
        bg_assignments.append(bg_geoids[np.argmin(dists)])

    return pd.DataFrame({
        "lid": range(len(hosp_locs)),
        "bg_geoid": bg_assignments,
        "capacity": 1,  # Each hospital = 1 facility
        "lat": hosp_locs["lat"].values,
        "lon": hosp_locs["long"].values,
    })


def load_combined_hospitals(config: dict) -> pd.DataFrame:
    """Load the combined VA/DC/MD hospital file from working directory."""
    combined_path = TOPIC_DIR / "data" / "working" / "vadcmd_cms_2015_2025_hospitals.csv"
    if not combined_path.exists():
        raise FileNotFoundError(f"Combined hospital file not found: {combined_path}")
    df = pd.read_csv(combined_path, dtype={"facility_id": str, "zip_code": str, "year": str})
    df["year"] = df["year"].astype(int)
    log.info("Loaded combined hospitals: %d rows, years %s", len(df), sorted(df["year"].unique()))
    return df


def load_hospitals_for_year(
    year: int,
    all_hospitals: pd.DataFrame,
    geo_hosp: pd.DataFrame,
    bg_geoids: np.ndarray,
    bg_lats: np.ndarray,
    bg_lons: np.ndarray,
) -> pd.DataFrame | None:
    """Extract hospitals for one year, join geocodes, snap to BGs.

    Returns provider DataFrame or None if year data is missing.
    """
    cms = all_hospitals[all_hospitals["year"] == year].copy()
    if cms.empty:
        log.warning("No hospitals for year %d in combined file", year)
        return None

    log.info("CMS %d: %d hospitals", year, len(cms))

    # Join with geocoded addresses on (facility_id, address, state)
    merged = cms.merge(
        geo_hosp[["facility_id", "address", "state", "lat", "long"]].drop_duplicates(
            subset=["facility_id", "address", "state"]
        ),
        on=["facility_id", "address", "state"],
        how="left",
    )

    # For unmatched, try matching on just facility_id + state
    unmatched = merged["lat"].isna()
    if unmatched.any():
        fallback_geo = (
            geo_hosp[["facility_id", "state", "lat", "long"]]
            .drop_duplicates(subset=["facility_id", "state"])
        )
        for idx in merged[unmatched].index:
            fid = merged.at[idx, "facility_id"]
            st = merged.at[idx, "state"]
            match = fallback_geo[
                (fallback_geo["facility_id"] == fid) & (fallback_geo["state"] == st)
            ]
            if not match.empty:
                merged.at[idx, "lat"] = match.iloc[0]["lat"]
                merged.at[idx, "long"] = match.iloc[0]["long"]

    missing = merged["lat"].isna().sum()
    if missing > 0:
        log.warning("Year %d: dropping %d hospitals with missing geocodes", year, missing)
        merged = merged.dropna(subset=["lat"])

    if merged.empty:
        log.warning("Year %d: no geocoded hospitals — skipping", year)
        return None

    # Each hospital is a unique location with capacity=1
    hosp_locs = (
        merged[["facility_id", "lat", "long"]]
        .drop_duplicates(subset=["facility_id"])
        .reset_index(drop=True)
    )

    log.info("Year %d: %d unique hospital locations", year, len(hosp_locs))

    providers = snap_to_block_groups(hosp_locs, bg_geoids, bg_lats, bg_lons)
    log.info("Year %d: snapped %d hospitals to block groups", year, len(providers))
    return providers


def run() -> list[RunResult]:
    t0 = time.time()
    results = []

    try:
        config = load_config()
        years = config["output"]["years"]

        geo_hosp = load_geocoded_hospitals(config)
        all_hospitals = load_combined_hospitals(config)
        bg_geoids, bg_lats, bg_lons = load_centroids()
        travel_times = load_travel_times()
        census = CensusClient()

        DIST_DIR.mkdir(parents=True, exist_ok=True)

        va_year_frames = []
        ncr_year_frames = []

        for year in years:
            yt0 = time.time()
            log.info("=== Processing year %d ===", year)

            providers = load_hospitals_for_year(
                year, all_hospitals, geo_hosp, bg_geoids, bg_lats, bg_lons,
            )
            if providers is None:
                continue

            # ACS population year: use cms_year - 1, capped at ACS_MAX_YEAR
            acs_year = min(year - 1, ACS_MAX_YEAR)
            log.info("Year %d: using ACS year %d for population", year, acs_year)

            pop_data = census.get_acs_multi(
                variables={"total_pop": "B01001_001"},
                years=[acs_year],
                geographies=["block_group"],
                states=["51", "24", "11"],
            )

            consumer_geoids = pop_data["geoid"].values
            consumer_pop = pop_data["total_pop"].values.astype(float)

            # --- VA ---
            va_mask = np.array([g.startswith("51") for g in consumer_geoids])
            va_providers = providers[providers["bg_geoid"].str.startswith("51")]
            if len(va_providers) > 0:
                va_bg = run_fca_variants(
                    consumer_geoids[va_mask], consumer_pop[va_mask],
                    va_providers, travel_times, MEASURE_PREFIX,
                )
                va_long = aggregate_bg_to_levels(
                    va_bg, MEASURE_PREFIX, year, consumer_pop=consumer_pop[va_mask],
                )
                va_year_frames.append(va_long)
                log.info("Year %d VA: %d rows", year, len(va_long))

            # --- NCR ---
            ncr_mask = np.array([g[:5] in NCR_COUNTIES for g in consumer_geoids])
            if ncr_mask.any():
                ncr_providers = providers[providers["bg_geoid"].str[:5].isin(NCR_COUNTIES)]
                if len(ncr_providers) > 0:
                    ncr_bg = run_fca_variants(
                        consumer_geoids[ncr_mask], consumer_pop[ncr_mask],
                        ncr_providers, travel_times, MEASURE_PREFIX,
                    )
                    ncr_long = aggregate_bg_to_levels(
                        ncr_bg, MEASURE_PREFIX, year, consumer_pop=consumer_pop[ncr_mask],
                    )
                    ncr_year_frames.append(ncr_long)
                    log.info("Year %d NCR: %d rows", year, len(ncr_long))

            log.info("Year %d done in %.1fs", year, time.time() - yt0)

        # Combine all years and write output
        if va_year_frames:
            va_all = pd.concat(va_year_frames, ignore_index=True)
            va_name = build_file_name(
                coverage_area="va",
                data_source=DATA_SOURCE,
                years=years,
                title=f"access_scores_{MEASURE_PREFIX}",
                geographies=["county", "tract", "block_group"],
            )
            va_path = write_data(va_all, DIST_DIR / f"{va_name}.csv.xz")
            log.info("Wrote VA: %s (%d rows)", va_path.name, len(va_all))
            results.append(RunResult(
                success=True, rows=len(va_all),
                output_path=str(va_path), duration_sec=time.time() - t0,
            ))

        if ncr_year_frames:
            ncr_all = pd.concat(ncr_year_frames, ignore_index=True)
            ncr_name = build_file_name(
                coverage_area="ncr",
                data_source=DATA_SOURCE,
                years=years,
                title=f"access_scores_{MEASURE_PREFIX}",
                geographies=["county", "tract", "block_group"],
            )
            ncr_path = write_data(ncr_all, DIST_DIR / f"{ncr_name}.csv.xz")
            log.info("Wrote NCR: %s (%d rows)", ncr_path.name, len(ncr_all))
            results.append(RunResult(
                success=True, rows=len(ncr_all),
                output_path=str(ncr_path), duration_sec=time.time() - t0,
            ))

    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        results.append(RunResult(success=False, error=str(e), duration_sec=time.time() - t0))

    return results


if __name__ == "__main__":
    results = run()
    for r in results:
        if r.success:
            log.info("OK: %d rows -> %s", r.rows, r.output_path)
        else:
            log.error("FAIL: %s", r.error)
    if any(not r.success for r in results):
        raise SystemExit(1)
