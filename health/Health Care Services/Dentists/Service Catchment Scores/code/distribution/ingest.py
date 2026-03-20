"""Ingest dental service accessibility scores for NCR.

Uses WebMD dental directory locations (GeoJSON), ACS total population at
block group level, and pre-computed BG-to-BG travel times to compute
2SFCA, E2SFCA, and 3SFCA access scores.  NCR-only — provider GeoJSON
covers the NCR region only, no statewide VA data available.
"""

import sys
import time
from pathlib import Path

import numpy as np
import yaml
from sdc_core.census import CensusClient
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

HCS_DIR = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HCS_DIR / "code"))
from compute_service_access import (
    aggregate_bg_to_levels,
    load_providers,
    load_travel_times,
    run_fca_variants,
)

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data" / "distribution"

log = get_logger("dentists.ingest")

NCR_COUNTIES = {
    "51059", "51600", "51610", "51107", "51013", "51510",
    "51683", "51685", "51153",
    "24021", "24031", "24033", "24017",
    "11001",
}

MEASURE_PREFIX = "dent"
DATA_SOURCE = "webmd"
YEAR = 2022
ACS_YEAR = 2021


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def run() -> list[RunResult]:
    t0 = time.time()
    results = []

    try:
        config = load_config()

        geojson_path = TOPIC_DIR / config["sources"]["providers"]["file"]
        capacity_col = config["sources"]["providers"].get("capacity_col", "doctors")
        providers = load_providers(geojson_path, capacity_col=capacity_col)
        log.info("Loaded %d provider locations", len(providers))

        travel_times = load_travel_times()

        # Fetch population for VA + MD + DC block groups (NCR spans all three)
        census = CensusClient()
        pop_data = census.get_acs_multi(
            variables={"total_pop": "B01001_001"},
            years=[ACS_YEAR],
            geographies=["block_group"],
            states=["51", "24", "11"],
        )

        consumer_geoids = pop_data["geoid"].values
        consumer_pop = pop_data["total_pop"].values.astype(float)

        # NCR only — filter consumers to NCR counties
        ncr_mask = np.array([g[:5] in NCR_COUNTIES for g in consumer_geoids])
        ncr_providers = providers[providers["bg_geoid"].str[:5].isin(NCR_COUNTIES)]

        if not ncr_mask.any() or len(ncr_providers) == 0:
            msg = "No NCR consumers or providers found"
            log.error(msg)
            return [RunResult(success=False, error=msg, duration_sec=time.time() - t0)]

        log.info(
            "NCR: %d consumer BGs, %d provider locations",
            ncr_mask.sum(), len(ncr_providers),
        )

        ncr_bg = run_fca_variants(
            consumer_geoids[ncr_mask],
            consumer_pop[ncr_mask],
            ncr_providers,
            travel_times,
            MEASURE_PREFIX,
        )

        ncr_long = aggregate_bg_to_levels(
            ncr_bg, MEASURE_PREFIX, YEAR,
            consumer_pop=consumer_pop[ncr_mask],
        )
        log.info("NCR: %d long-format rows", len(ncr_long))

        DIST_DIR.mkdir(parents=True, exist_ok=True)
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
