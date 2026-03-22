"""Ingest urgent care center accessibility scores for VA and NCR.

Uses NPPES NPI Registry data (taxonomy 261QU0200X) for urgent care facility
locations, ACS total population at block group level, and pre-computed
BG-to-BG travel times to compute 2SFCA, E2SFCA, and 3SFCA access scores.
Each center has capacity=1 (facility-level, not individual providers).
Loops over years (2020-2025), filtering facilities by enumeration date
so that each year includes only facilities that had been NPI-registered
by December 31 of that year.
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
CENTROIDS_PATH = REPO_DIR / "geographies" / "osrm" / "bg_centroids_2020.csv"

log = get_logger("urgent.ingest")

NCR_COUNTIES = {
    "51059", "51600", "51610", "51107", "51013", "51510",
    "51683", "51685", "51153",
    "24021", "24031", "24033", "24017",
    "11001",
}

MEASURE_PREFIX = "urgent"
DATA_SOURCE = "nppes"

# ACS 5-year latest available year
ACS_MAX_YEAR = 2023


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def load_centroids() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load BG centroids, return (geoids, lats, lons) arrays."""
    centroids = pd.read_csv(CENTROIDS_PATH, dtype={"geoid": str})
    return centroids["geoid"].values, centroids["lat"].values, centroids["lon"].values


def load_facilities(config: dict) -> pd.DataFrame:
    """Load geocoded NPPES urgent care facilities.

    Returns DataFrame with lat, long, state, enum_year columns.
    """
    geo_path = TOPIC_DIR / config["sources"]["nppes"]["geocoded_file"]
    if not geo_path.exists():
        raise FileNotFoundError(f"Geocoded facility file not found: {geo_path}")

    geo = pd.read_csv(geo_path, dtype={"postalcode": str})
    # Drop rows without valid coordinates
    geo = geo.dropna(subset=["lat", "long"])
    # Parse dates to year for per-year filtering
    geo["enum_year"] = pd.to_datetime(geo["enumeration_date"], errors="coerce").dt.year
    geo["cert_year"] = pd.to_datetime(geo["certification_date"], errors="coerce").dt.year
    log.info("Loaded %d geocoded urgent care facilities (enum years %d-%d, cert years %d-%d)",
             len(geo), int(geo["enum_year"].min()), int(geo["enum_year"].max()),
             int(geo["cert_year"].min()), int(geo["cert_year"].max()))
    return geo


def snap_facilities_to_block_groups(
    facilities: pd.DataFrame,
    bg_geoids: np.ndarray,
    bg_lats: np.ndarray,
    bg_lons: np.ndarray,
) -> pd.DataFrame:
    """Snap each facility to its nearest block group centroid.

    Each facility gets capacity=1 (urgent care centers, not individual providers).
    """
    bg_assignments = []
    for _, row in facilities.iterrows():
        dists = _haversine_km(bg_lats, bg_lons, row["lat"], row["long"])
        bg_assignments.append(bg_geoids[np.argmin(dists)])

    return pd.DataFrame({
        "lid": range(len(facilities)),
        "bg_geoid": bg_assignments,
        "capacity": 1,
        "lat": facilities["lat"].values,
        "lon": facilities["long"].values,
        "provider_state": facilities["state"].values,
    })


def run() -> list[RunResult]:
    t0 = time.time()
    results = []

    try:
        config = load_config()
        years = config["output"]["years"]

        # Load all facilities; per-year filtering by enumeration date happens in loop
        all_facilities = load_facilities(config)
        bg_geoids, bg_lats, bg_lons = load_centroids()

        travel_times = load_travel_times()
        census = CensusClient()

        DIST_DIR.mkdir(parents=True, exist_ok=True)

        va_year_frames = []
        ncr_year_frames = []

        for year in years:
            yt0 = time.time()
            log.info("=== Processing year %d ===", year)

            # Filter to facilities that were active in this year:
            # - enumerated on or before Dec 31 of this year (facility existed)
            # - last certified in this year or the prior year (still operating)
            #   A 1-year grace period accounts for the annual certification cycle.
            enumerated = all_facilities["enum_year"] <= year
            certified = all_facilities["cert_year"] >= (year - 1)
            year_facilities = all_facilities[enumerated & certified]
            log.info("Year %d: %d facilities (enumerated by Dec 31, certified within 1 year)", year, len(year_facilities))

            if year_facilities.empty:
                log.warning("Year %d: no facilities — skipping", year)
                continue

            providers = snap_facilities_to_block_groups(
                year_facilities, bg_geoids, bg_lats, bg_lons,
            )

            # ACS population year: use year - 1, capped at ACS_MAX_YEAR
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
