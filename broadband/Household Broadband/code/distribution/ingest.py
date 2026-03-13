"""Ingest household broadband adoption raw counts from ACS Table B28002.

Fetches data for each source profile defined in pipeline.yaml and writes
county+tract+block_group raw counts to data/distribution/. Health district
aggregation and percentage computation happen in prepare.py.
"""

import time
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.census import CensusClient
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.profiles import resolve_states
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
WORKING_DIR = TOPIC_DIR / "data/working"

log = get_logger("household_broadband.ingest")

RAW_COUNT_COLS = ["total_hh", "hh_without_internet", "hh_with_broadband", "hh_with_cable_fiber_dsl"]


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def run_source(name: str, src: dict, config: dict, client: CensusClient) -> RunResult:
    """Fetch and write raw counts for one coverage-area source."""
    t0 = time.time()
    try:
        log.info("Ingesting source '%s' (profile=%s)", name, src.get("profile"))

        df = client.get_acs_multi(
            variables=src["variables"],
            years=src["years"],
            geographies=src["geographies"],
            profile=src.get("profile"),
            states=src.get("states"),
            cache_dir=TOPIC_DIR / "data/working/acs_cache",
        )
        log.info("Fetched %d raw rows for '%s'", len(df), name)

        # Keep county+tract+block_group rows only (no HD aggregation)
        tract_rows = df[df["geoid"].str.len() == 11].copy()
        county_rows = df[df["geoid"].str.len() == 5].copy()
        bg_rows = df[df["geoid"].str.len() == 12].copy()

        combined = pd.concat([tract_rows, county_rows, bg_rows], ignore_index=True)

        log.info(
            "Combined: %d tracts + %d counties + %d block groups for '%s'",
            len(tract_rows), len(county_rows), len(bg_rows), name,
        )

        # Write raw counts (wide format) — percentage computation happens in prepare.py
        keep_cols = ["geoid", "year", "region_type"] + RAW_COUNT_COLS
        result = combined[keep_cols].copy()

        states = resolve_states(src)
        auto_name = build_file_name(
            df=result,
            states=states,
            years=src.get("years"),
            source_type=src.get("type"),
            title="household_broadband_raw",
        )
        filename = f"{auto_name}.csv.xz"
        WORKING_DIR.mkdir(parents=True, exist_ok=True)
        out_path = write_data(result, WORKING_DIR / filename, standardize=False)
        log.info("Wrote %d rows to %s", len(result), out_path)

        return RunResult(
            success=True,
            rows=len(result),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Ingest failed for source '%s': %s", name, e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


def run() -> list[RunResult]:
    config = load_config()
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    client = CensusClient()

    results = []
    for name, src in config["sources"].items():
        results.append(run_source(name, src, config, client))
    return results


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
