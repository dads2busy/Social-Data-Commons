"""Ingest health insurance coverage from ACS table B27010.

Computes uninsured and insured percentages for the working-age population
(19-64) using ACS 5-year estimates.
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
MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"
log = get_logger("without_health_insurance.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def compute_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Compute uninsured and insured percentages from ACS B27010 variables."""
    df = df.copy()

    total = df["total_19_34"] + df["total_35_64"]
    uninsured = df["uninsured_19_34"] + df["uninsured_35_64"]

    df["no_hlth_ins_pct"] = 100 * uninsured / total
    df["hlth_ins_pct"] = 100 - df["no_hlth_ins_pct"]

    df["no_hlth_ins_count"] = uninsured
    df["hlth_ins_count"] = total - uninsured
    df["hlth_ins_total_count"] = total

    id_cols = ["geoid", "year", "region_type"]
    measure_cols = [
        "no_hlth_ins_pct", "hlth_ins_pct",
        "no_hlth_ins_count", "hlth_ins_count", "hlth_ins_total_count",
    ]

    long = df[id_cols + measure_cols].melt(
        id_vars=id_cols,
        var_name="measure",
        value_name="value",
    )
    long["moe"] = pd.NA
    return long.dropna(subset=["value"])


def run_source(name: str, src: dict, out_dir: Path, standardize: bool) -> RunResult:
    t0 = time.time()
    try:
        log.info("Ingesting source '%s' (profile=%s)", name, src.get("profile"))

        cache_dir = TOPIC_DIR / "data/working/acs_cache"
        client = CensusClient()
        df = client.get_acs_multi(
            variables=src["variables"],
            years=src["years"],
            geographies=src["geographies"],
            profile=src.get("profile"),
            states=src.get("states"),
            cache_dir=cache_dir,
        )
        log.info("Fetched %d raw rows for '%s'", len(df), name)

        result = compute_measures(df)

        states = resolve_states(src)
        auto_name = build_file_name(
            df=result,
            states=states,
            years=src.get("years"),
            source_type=src.get("type"),
            title="without_health_insurance",
        )
        out_path = write_data(
            result,
            out_dir / f"{auto_name}.csv.xz",
            census_standardize=standardize,
            measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,
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
    out_dir.mkdir(parents=True, exist_ok=True)
    standardize = config["output"].get("standardize", False)

    return [
        run_source(name, src, out_dir, standardize)
        for name, src in config["sources"].items()
    ]


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
