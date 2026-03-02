"""Ingest veteran demographics from ACS.

Configuration is read from veteran/pipeline.yaml.
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

TOPIC_DIR = Path(__file__).resolve().parents[1]
log = get_logger("veteran.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def compute_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Compute veteran counts and percentages."""
    df = df.copy()
    df["veteran_count"] = df["veteran"]
    df["veteran_percent"] = 100 * df["veteran"] / df["vet_denom"]

    id_cols = ["geoid", "year", "region_type"]
    measure_cols = [c for c in df.columns if c.startswith("veteran_")]

    long = df[id_cols + measure_cols].melt(
        id_vars=id_cols,
        var_name="measure",
        value_name="value",
    )
    long["moe"] = pd.NA
    return long


def run(pipeline=None) -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        src = config["source"]
        out = config["output"]

        log.info("Starting veteran ingest (profile=%s)", src.get("profile"))

        client = CensusClient()
        df = client.get_acs_multi(
            variables=src["variables"],
            years=src["years"],
            geographies=src["geographies"],
            profile=src.get("profile"),
            states=src.get("states"),
        )
        log.info("Fetched %d raw rows from Census API", len(df))

        result = compute_measures(df)

        out_dir = TOPIC_DIR / out["path"]
        states = resolve_states(src)
        auto_name = build_file_name(
            df=result,
            states=states,
            years=src.get("years"),
            source_type=src.get("type"),
            title=config.get("name"),
        )
        filename = f"{auto_name}.csv.xz" if auto_name else out["filename"]
        out_path = write_data(
            result,
            out_dir / filename,
            census_standardize=out.get("standardize", False),
        )
        log.info("Wrote %d rows to %s", len(result), out_path)

        return RunResult(
            success=True,
            rows=len(result),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Veteran ingest failed: %s", e, exc_info=True)
        return RunResult(
            success=False,
            error=str(e),
            duration_sec=time.time() - t0,
        )


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
