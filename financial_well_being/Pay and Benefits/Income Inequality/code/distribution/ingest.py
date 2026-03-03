"""Ingest Gini index of income inequality from ACS B19083."""

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

log = get_logger("income_inequality.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def compute_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Pass gini_index through to long format; drop rows where ACS suppressed the value."""
    id_cols = ["geoid", "year", "region_type"]
    result = df[id_cols].copy()
    result["measure"] = "gini_index"
    result["value"] = df["gini_index"].round(4)
    result["moe"] = df["gini_index_moe"].round(4) if "gini_index_moe" in df.columns else pd.NA
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
            title="income_inequality",
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
