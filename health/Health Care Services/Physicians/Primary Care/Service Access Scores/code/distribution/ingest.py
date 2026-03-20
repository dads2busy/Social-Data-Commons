"""Ingest primary care physician accessibility scores for VA and NCR.

Uses WebMD primary care physician locations, ACS total population at block
group level, and pre-computed BG-to-BG travel times to compute 2SFCA,
E2SFCA, and 3SFCA access scores. Physician count is used as provider capacity.
"""

import sys
import time
from pathlib import Path

import numpy as np
import yaml
from sdc_core.census import CensusClient
from sdc_core.log import get_logger
from sdc_core.result import RunResult

HCS_DIR = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HCS_DIR / "code"))
from compute_service_access import (
    load_providers,
    load_travel_times,
    run_fca_variants,
    aggregate_and_output,
)

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data" / "distribution"

log = get_logger("primcare.ingest")

NCR_COUNTIES = {
    "51059", "51600", "51610", "51107", "51013", "51510",
    "51683", "51685", "51153",
    "24021", "24031", "24033", "24017",
    "11001",
}

MEASURE_PREFIX = "primcare"
DATA_SOURCE = "webmd"
YEAR = 2022
ACS_YEAR = 2021


def run() -> list[RunResult]:
    t0 = time.time()
    results = []

    try:
        config = yaml.safe_load((TOPIC_DIR / "pipeline.yaml").read_text())

        geojson_path = TOPIC_DIR / config["sources"]["providers"]["file"]
        capacity_col = config["sources"]["providers"].get("capacity_col", "doctors")
        providers = load_providers(geojson_path, capacity_col=capacity_col)
        log.info("Loaded %d provider locations", len(providers))

        travel_times = load_travel_times()

        census = CensusClient()
        pop_data = census.get_acs_multi(
            variables={"total_pop": "B01001_001"},
            year=ACS_YEAR,
            geography="block group",
            state="51",
        )

        consumer_geoids = pop_data["geoid"].values
        consumer_pop = pop_data["total_pop"].values.astype(float)

        # VA
        va_mask = np.array([g.startswith("51") for g in consumer_geoids])
        va_result = run_fca_variants(
            consumer_geoids[va_mask], consumer_pop[va_mask],
            providers[providers["bg_geoid"].str.startswith("51")],
            travel_times, MEASURE_PREFIX,
        )
        va_path = aggregate_and_output(
            va_result, MEASURE_PREFIX, YEAR, "va", DATA_SOURCE, DIST_DIR,
            pop_col_for_weighting=consumer_pop[va_mask],
        )
        results.append(RunResult(success=True, rows=len(va_result), output_path=str(va_path), duration_sec=time.time() - t0))

        # NCR
        ncr_mask = np.array([g[:5] in NCR_COUNTIES for g in consumer_geoids])
        if ncr_mask.any():
            ncr_providers = providers[providers["bg_geoid"].str[:5].isin(NCR_COUNTIES)]
            ncr_result = run_fca_variants(
                consumer_geoids[ncr_mask], consumer_pop[ncr_mask],
                ncr_providers, travel_times, MEASURE_PREFIX,
            )
            ncr_path = aggregate_and_output(
                ncr_result, MEASURE_PREFIX, YEAR, "ncr", DATA_SOURCE, DIST_DIR,
                pop_col_for_weighting=consumer_pop[ncr_mask],
            )
            results.append(RunResult(success=True, rows=len(ncr_result), output_path=str(ncr_path), duration_sec=time.time() - t0))

    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        results.append(RunResult(success=False, error=str(e), duration_sec=time.time() - t0))

    return results


if __name__ == "__main__":
    results = run()
    for r in results:
        if r.success:
            log.info("OK: %d rows → %s", r.rows, r.output_path)
        else:
            log.error("FAIL: %s", r.error)
    if any(not r.success for r in results):
        raise SystemExit(1)
