"""Ingest substance abuse treatment facility accessibility scores for VA and NCR.

Reads SAMHSA facility locations downloaded by download.py, snaps to nearest
block group centroids, fetches ACS total population, and computes 2SFCA,
E2SFCA, and 3SFCA access scores. Capacity=1 per facility (no capacity data).
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sdc_core.census import CensusClient
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

log = get_logger("substance.ingest")

NCR_COUNTIES = {
    "51059", "51600", "51610", "51107", "51013", "51510",
    "51683", "51685", "51153",
    "24021", "24031", "24033", "24017",
    "11001",
}

MEASURE_PREFIX = "substance"
DATA_SOURCE = "samhsa"
YEAR = 2025
ACS_YEAR = 2023  # Latest available ACS 5-year


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def load_centroids() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load BG centroids, return (geoids, lats, lons) arrays."""
    centroids = pd.read_csv(CENTROIDS_PATH, dtype={"geoid": str})
    return centroids["geoid"].values, centroids["lat"].values, centroids["lon"].values


def snap_facilities_to_bgs(
    facilities: pd.DataFrame,
    bg_geoids: np.ndarray,
    bg_lats: np.ndarray,
    bg_lons: np.ndarray,
) -> pd.DataFrame:
    """Snap facility lat/lon to nearest block group centroid."""
    bg_assignments = []
    for _, row in facilities.iterrows():
        dists = _haversine_km(bg_lats, bg_lons, row["lat"], row["lon"])
        bg_assignments.append(bg_geoids[np.argmin(dists)])

    return pd.DataFrame({
        "lid": range(len(facilities)),
        "bg_geoid": bg_assignments,
        "capacity": 1,
        "lat": facilities["lat"].values,
        "lon": facilities["lon"].values,
    })


def run() -> list[RunResult]:
    t0 = time.time()
    results = []

    try:
        config = load_config()

        # Load downloaded SAMHSA facilities
        facilities_path = WORKING_DIR / config["sources"]["samhsa"]["facilities_file"]
        if not facilities_path.exists():
            raise FileNotFoundError(
                f"Facilities file not found: {facilities_path}. Run download.py first."
            )
        facilities = pd.read_csv(facilities_path)
        log.info("Loaded %d facilities from %s", len(facilities), facilities_path.name)

        # Load centroids and snap facilities to BGs
        bg_geoids, bg_lats, bg_lons = load_centroids()
        providers = snap_facilities_to_bgs(facilities, bg_geoids, bg_lats, bg_lons)
        log.info("Snapped %d facilities to block groups", len(providers))

        # Load travel times
        travel_times = load_travel_times()

        # ACS population
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
            from sdc_core.io import write_data
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
                from sdc_core.io import write_data
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
