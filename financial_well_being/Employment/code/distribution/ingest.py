"""Ingest employment rate and labor force participation rate from ACS B23025 and S2301.

Fetches ACS data for two measures:
  emp_rate: computed from B23025_004 / B23025_003 * 100 (detail table, no MOE)
  labor_participate_rate: S2301_C02_001 pre-computed by ACS (subject table, with MOE)

Writes one long-format .csv.xz per coverage area to data/distribution/.
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

log = get_logger("employment.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def compute_emp_rate(df: pd.DataFrame) -> pd.DataFrame:
    mask = df["civilian_lf"].gt(0) & df["civilian_lf"].notna()
    df = df[mask].copy()
    out = df[["geoid", "year", "region_type"]].copy()
    out["measure"] = "emp_rate"
    out["value"] = (df["employed"] / df["civilian_lf"] * 100).round(4)
    out["moe"] = pd.NA
    return out


def compute_labor_rate(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["geoid", "year", "region_type"]].copy()
    out["measure"] = "labor_participate_rate"
    out["value"] = df["labor_participate_rate"].round(4)
    out["moe"] = df["labor_participate_rate_moe"]
    return out


def run_source(
    name: str, src: dict, out_dir: Path, client: CensusClient
) -> RunResult:
    t0 = time.time()
    try:
        log.info("Ingesting source '%s'", name)
        variables = src["variables"]
        is_emp = "civilian_lf" in variables

        if is_emp:
            df = client.get_acs_multi(
                variables=variables,
                years=src["years"],
                geographies=src["geographies"],
                profile=src.get("profile"),
                estimate_only=True,
                table_type="detail",
            )
        else:
            df = client.get_acs_multi(
                variables=variables,
                years=src["years"],
                geographies=src["geographies"],
                profile=src.get("profile"),
                estimate_only=False,
                table_type="subject",
            )

        if df.empty:
            return RunResult(
                success=False,
                error=f"No data for source '{name}'",
                duration_sec=time.time() - t0,
            )

        if is_emp:
            result = compute_emp_rate(df)
            title = "employment_rate"
        else:
            result = compute_labor_rate(df)
            title = "labor_participate_rate"

        states = resolve_states(src)
        auto_name = build_file_name(
            df=result,
            states=states,
            years=src.get("years"),
            source_type=src.get("type"),
            title=title,
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
    out_dir = DIST_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    client = CensusClient()

    results = []
    for name, src in config["sources"].items():
        results.append(run_source(name, src, out_dir, client))
    return results


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
