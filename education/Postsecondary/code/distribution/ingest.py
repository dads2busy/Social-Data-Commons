"""Ingest postsecondary education attainment from ACS B06009.

Fetches counts for in-college, college-complete, and post-college populations,
computes count and percent measures with propagated margins of error, and
writes one long-format .csv.xz per coverage area to data/distribution/.

MOE propagation follows the Census Bureau's standard formula:
  moe_sum  = 1.645 * sqrt(sum((moe_i / 1.645)^2))
  moe_pct  = (1 / total) * sqrt(moe_count^2 - (pct/100)^2 * moe_total^2)
             (ratio formula; falls back to moe_count / total when negative)
"""

import time
from pathlib import Path

import numpy as np
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

log = get_logger("postsecondary.ingest")

Z = 1.645  # 90% confidence interval used by Census


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def compute_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Compute postsecondary count/percent and their MOEs, melt to long format."""
    # Estimates
    count = df["in_college"] + df["college_complete"] + df["post_college"]
    pct = count / df["total"] * 100
    pct = pct.where(df["total"].gt(0), other=0.0)

    # Standard errors (se = moe / Z)
    se_in = df.get("in_college_moe", pd.Series(0, index=df.index)) / Z
    se_cc = df.get("college_complete_moe", pd.Series(0, index=df.index)) / Z
    se_pc = df.get("post_college_moe", pd.Series(0, index=df.index)) / Z
    se_tot = df.get("total_moe", pd.Series(0, index=df.index)) / Z

    # MOE for count: sqrt of sum of squared SEs, back to 90% CI
    moe_count = Z * np.sqrt(se_in**2 + se_cc**2 + se_pc**2)

    # MOE for percent (ratio formula)
    discriminant = (moe_count / Z) ** 2 - (pct / 100) ** 2 * se_tot**2
    se_pct = np.where(
        discriminant >= 0,
        np.sqrt(discriminant.clip(lower=0)) / df["total"].replace(0, np.nan),
        (moe_count / Z) / df["total"].replace(0, np.nan),
    )
    moe_pct = Z * pd.Series(se_pct, index=df.index) * 100
    moe_pct = moe_pct.fillna(0)

    id_cols = ["geoid", "year", "region_type"]
    rows = []
    for measure, val, moe in [
        ("acs_postsecondary_count", count, moe_count),
        ("acs_postsecondary_percent", pct, moe_pct),
    ]:
        part = df[id_cols].copy()
        part["measure"] = measure
        part["value"] = val.round(4)
        part["moe"] = moe.round(4)
        rows.append(part)

    return pd.concat(rows, ignore_index=True)


def run_source(
    name: str, src: dict, out_dir: Path, client: CensusClient
) -> RunResult:
    t0 = time.time()
    try:
        log.info("Ingesting source '%s'", name)
        variables = src["variables"]

        df = client.get_acs_multi(
            variables=variables,
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
            title="postsecondary",
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
