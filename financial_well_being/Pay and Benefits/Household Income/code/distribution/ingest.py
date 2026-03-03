"""Ingest median household income from ACS B19013.

Fetches B19013_001 (median household income in past 12 months, 2019 inflation-
adjusted dollars) for county, tract, and block group geographies. Writes one
long-format .csv.xz per coverage area (NCR, VA) to data/distribution/.
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
DIST_DIR = TOPIC_DIR / "data/distribution"

log = get_logger("household_income.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def compute_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Pass median household income through to long format; drop suppressed rows."""
    id_cols = ["geoid", "year", "region_type"]
    result = df[id_cols].copy()
    result["measure"] = "median_household_income"
    result["value"] = df["median_household_income"].round(0)
    result["moe"] = (
        df["median_household_income_moe"].round(0)
        if "median_household_income_moe" in df.columns
        else pd.NA
    )
    return result.dropna(subset=["value"])


def run_source(name: str, src: dict, out_dir: Path, client: CensusClient) -> RunResult:
    t0 = time.time()
    try:
        log.info("Ingesting source '%s'", name)
        df = client.get_acs_multi(
            variables=src["variables"],
            years=src["years"],
            geographies=src["geographies"],
            profile=src.get("profile"),
            states=src.get("states"),
            estimate_only=False,
        )
        if df.empty:
            return RunResult(
                success=False,
                error=f"No data for source '{name}'",
                duration_sec=time.time() - t0,
            )

        result = compute_measures(df)

        states = resolve_states(src)
        auto_name = build_file_name(
            df=result,
            states=states,
            years=src.get("years"),
            source_type=src.get("type"),
            title="household_income",
        )
        out_path = write_data(
            result,
            out_dir / f"{auto_name}.csv.xz",
            census_standardize=True,
        )
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
    return [run_source(name, src, DIST_DIR, client) for name, src in config["sources"].items()]


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
