"""Ingest race and ethnicity demographics from ACS.

Configuration is read from race/pipeline.yaml.
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
log = get_logger("race.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def compute_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Compute race/ethnicity counts and percentages, melt to long format."""
    df = df.copy()

    # Combine Asian + Pacific Islander into AAPI
    df["AAPI"] = df["asian_alone"] + df["pacific_islander_alone"]

    # Counts
    df["race_total_count"] = df["total_race"]
    df["race_wht_alone_count"] = df["wht_alone"]
    df["race_afr_amer_alone_count"] = df["afr_amer_alone"]
    df["race_native_alone_count"] = df["native_alone"]
    df["race_AAPI_count"] = df["AAPI"]
    df["race_other_count"] = df["other"]
    df["race_two_or_more_count"] = df["two_or_more"]
    df["race_hispanic_or_latino_count"] = df["hispanic_or_latino"]

    # Percentages
    df["race_wht_alone_percent"] = 100 * df["wht_alone"] / df["total_race"]
    df["race_afr_amer_alone_percent"] = 100 * df["afr_amer_alone"] / df["total_race"]
    df["race_native_alone_percent"] = 100 * df["native_alone"] / df["total_race"]
    df["race_AAPI_percent"] = 100 * df["AAPI"] / df["total_race"]
    df["race_other_percent"] = 100 * df["other"] / df["total_race"]
    df["race_two_or_more_percent"] = 100 * df["two_or_more"] / df["total_race"]
    df["race_hispanic_or_latino_percent"] = (
        100 * df["hispanic_or_latino"] / df["eth_total"]
    )

    id_cols = ["geoid", "year", "region_type"]
    measure_cols = [c for c in df.columns if c.startswith("race_")]

    long = df[id_cols + measure_cols].melt(
        id_vars=id_cols,
        var_name="measure",
        value_name="value",
    )
    long["moe"] = pd.NA
    return long


def run_source(
    name: str,
    src: dict,
    out_dir: Path,
    client: CensusClient,
    standardize: bool,
) -> RunResult:
    """Fetch and write one coverage-area source."""
    t0 = time.time()
    try:
        log.info("Ingesting source '%s' (profile=%s)", name, src.get("profile"))

        df = client.get_acs_multi(
            variables=src["variables"],
            years=src["years"],
            geographies=src["geographies"],
            profile=src.get("profile"),
            states=src.get("states"),
        )
        log.info("Fetched %d raw rows for '%s'", len(df), name)

        result = compute_measures(df)

        states = resolve_states(src)
        auto_name = build_file_name(
            df=result,
            states=states,
            years=src.get("years"),
            source_type=src.get("type"),
            title="race_demographics",
        )
        filename = f"{auto_name}.csv.xz"
        out_path = write_data(
            result,
            out_dir / filename,
            census_standardize=standardize,
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
    out_dir = TOPIC_DIR / config["output"]["path"]
    standardize = config["output"].get("standardize", False)
    client = CensusClient()

    results = []
    for name, src in config["sources"].items():
        results.append(run_source(name, src, out_dir, client, standardize))
    return results


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
