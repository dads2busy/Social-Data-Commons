"""Ingest EMS service accessibility scores for VA and NCR.

Uses HIFLD EMS station locations (CSV with lat/lon), ACS total population at
block group level, and pre-computed BG-to-BG travel times to compute 2SFCA,
E2SFCA, and 3SFCA access scores. Each EMS station is treated as a single unit
(capacity=1) since no capacity column is available.

Data source: HIFLD Emergency Medical Service Stations (2021 snapshot).
No download step needed — data already exists as CSV in data/original/.
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
ORIG_DIR = TOPIC_DIR / "data" / "original"
CENTROIDS_PATH = REPO_DIR / "geographies" / "osrm" / "bg_centroids_2020.csv"

log = get_logger("ems.ingest")

NCR_COUNTIES = {
    "51059", "51600", "51610", "51107", "51013", "51510",
    "51683", "51685", "51153",
    "24021", "24031", "24033", "24017",
    "11001",
}

MEASURE_PREFIX = "ems"
DATA_SOURCE = "hifld"
YEAR = 2021
ACS_YEAR = 2021


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def load_centroids() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load BG centroids, return (geoids, lats, lons) arrays."""
    centroids = pd.read_csv(CENTROIDS_PATH, dtype={"geoid": str})
    return centroids["geoid"].values, centroids["lat"].values, centroids["lon"].values


def load_ems_providers(
    bg_geoids: np.ndarray,
    bg_lats: np.ndarray,
    bg_lons: np.ndarray,
) -> pd.DataFrame:
    """Load EMS stations from CSV, snap each to nearest block group centroid.

    Returns DataFrame with columns: lid, bg_geoid, capacity, lat, lon, provider_state
    """
    csv_path = ORIG_DIR / "va_hifld_2021_ems_stations.csv"
    providers_raw = pd.read_csv(csv_path, dtype=str)
    providers_raw["lat"] = providers_raw["lat"].astype(float)
    providers_raw["lon"] = providers_raw["lon"].astype(float)

    log.info("Loaded %d EMS stations from %s", len(providers_raw), csv_path.name)

    bg_assignments = []
    for _, row in providers_raw.iterrows():
        dists = _haversine_km(bg_lats, bg_lons, row["lat"], row["lon"])
        bg_assignments.append(bg_geoids[np.argmin(dists)])

    return pd.DataFrame({
        "lid": providers_raw["ID"].values,
        "bg_geoid": bg_assignments,
        "capacity": 1,
        "lat": providers_raw["lat"].values,
        "lon": providers_raw["lon"].values,
        "provider_state": providers_raw["STATE"].values,
    })


def run() -> list[RunResult]:
    t0 = time.time()
    results = []

    try:
        config = load_config()
        DIST_DIR.mkdir(parents=True, exist_ok=True)

        bg_geoids, bg_lats, bg_lons = load_centroids()
        providers = load_ems_providers(bg_geoids, bg_lats, bg_lons)
        log.info("Snapped %d EMS stations to block groups", len(providers))

        travel_times = load_travel_times()

        census = CensusClient()
        pop_data = census.get_acs_multi(
            variables={"total_pop": "B01001_001"},
            years=[ACS_YEAR],
            geographies=["block_group"],
            states=["51", "24", "11"],
        )

        consumer_geoids = pop_data["geoid"].values
        consumer_pop = pop_data["total_pop"].values.astype(float)

        # --- VA ---
        va_mask = np.array([g.startswith("51") for g in consumer_geoids])
        va_providers = providers[providers["bg_geoid"].str.startswith("51")]
        if len(va_providers) > 0:
            log.info("VA: %d consumer BGs, %d provider locations", va_mask.sum(), len(va_providers))
            va_bg = run_fca_variants(
                consumer_geoids[va_mask], consumer_pop[va_mask],
                va_providers, travel_times, MEASURE_PREFIX,
            )
            va_long = aggregate_bg_to_levels(
                va_bg, MEASURE_PREFIX, YEAR, consumer_pop=consumer_pop[va_mask],
            )
            va_name = build_file_name(
                coverage_area="va",
                data_source=DATA_SOURCE,
                years=[YEAR],
                title=f"access_scores_{MEASURE_PREFIX}",
                geographies=["county", "tract", "block_group"],
            )
            va_path = write_data(va_long, DIST_DIR / f"{va_name}.csv.xz")
            log.info("Wrote VA: %s (%d rows)", va_path.name, len(va_long))
            results.append(RunResult(
                success=True, rows=len(va_long),
                output_path=str(va_path), duration_sec=time.time() - t0,
            ))

        # --- NCR ---
        ncr_mask = np.array([g[:5] in NCR_COUNTIES for g in consumer_geoids])
        if ncr_mask.any():
            ncr_providers = providers[providers["bg_geoid"].str[:5].isin(NCR_COUNTIES)]
            if len(ncr_providers) > 0:
                log.info("NCR: %d consumer BGs, %d provider locations", ncr_mask.sum(), len(ncr_providers))
                ncr_bg = run_fca_variants(
                    consumer_geoids[ncr_mask], consumer_pop[ncr_mask],
                    ncr_providers, travel_times, MEASURE_PREFIX,
                )
                ncr_long = aggregate_bg_to_levels(
                    ncr_bg, MEASURE_PREFIX, YEAR, consumer_pop=consumer_pop[ncr_mask],
                )
                ncr_name = build_file_name(
                    coverage_area="ncr",
                    data_source=DATA_SOURCE,
                    years=[YEAR],
                    title=f"access_scores_{MEASURE_PREFIX}",
                    geographies=["county", "tract", "block_group"],
                )
                ncr_path = write_data(ncr_long, DIST_DIR / f"{ncr_name}.csv.xz")
                log.info("Wrote NCR: %s (%d rows)", ncr_path.name, len(ncr_long))
                results.append(RunResult(
                    success=True, rows=len(ncr_long),
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
