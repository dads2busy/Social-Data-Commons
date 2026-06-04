"""Ingest average years of schooling from ACS B15003.

Fetches educational attainment counts for each grade level (population 25+),
computes a weighted average years of schooling, and writes one long-format
.csv.xz per coverage area to data/distribution/.

Grade-to-years mapping follows the R script convention:
  B15003_005-016: grades 1-12 (some share 12)
  B15003_017-018: GED / high school diploma equivalents (12)
  B15003_019: some college (12.5)
  B15003_020: associate's (13), B15003_021: bachelor's (14)
  B15003_022: bachelor's alt (16), B15003_023: master's (18)
  B15003_024: professional (19), B15003_025: doctorate (20)
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
DIST_DIR = TOPIC_DIR / "data/distribution"
WORKING_DIR = TOPIC_DIR / "data/working"

log = get_logger("years_of_schooling.ingest")

# ACS variable -> years of schooling value
GRADE_VALUES: dict[str, float] = {
    "B15003_005": 1,
    "B15003_006": 2,
    "B15003_007": 3,
    "B15003_008": 4,
    "B15003_009": 5,
    "B15003_010": 6,
    "B15003_011": 7,
    "B15003_012": 8,
    "B15003_013": 9,
    "B15003_014": 10,
    "B15003_015": 11,
    "B15003_016": 12,
    "B15003_017": 12,
    "B15003_018": 12,
    "B15003_019": 12.5,
    "B15003_020": 13,
    "B15003_021": 14,
    "B15003_022": 16,
    "B15003_023": 18,
    "B15003_024": 19,
    "B15003_025": 20,
}

TOTAL_VAR = "B15003_001"


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def compute_avg_years(df: pd.DataFrame) -> pd.DataFrame:
    """Convert wide ACS grade counts into average years of schooling."""
    total = df[TOTAL_VAR]
    score = sum(
        df[var] / total * years_val
        for var, years_val in GRADE_VALUES.items()
        if var in df.columns
    )
    out = df[["geoid", "year", "region_type"]].copy()
    out["measure"] = "average_years_schooling"
    out["value"] = score.round(2)
    out["moe"] = pd.NA
    # Drop rows where total population is 0 or NaN
    out = out[total.gt(0) & total.notna()].copy()
    return out


def run_source(
    name: str, src: dict, out_dir: Path, client: CensusClient
) -> RunResult:
    t0 = time.time()
    try:
        log.info("Ingesting source '%s'", name)
        variables = {var: var for var in [TOTAL_VAR] + list(GRADE_VALUES.keys())}

        df = client.get_acs_multi(
            variables=variables,
            years=src["years"],
            geographies=src["geographies"],
            profile=src.get("profile"),
            states=src.get("states"),
        )
        if df.empty:
            return RunResult(
                success=False,
                error=f"No data for source '{name}'",
                duration_sec=time.time() - t0,
            )

        result = compute_avg_years(df)

        states = resolve_states(src)
        auto_name = build_file_name(
            df=result,
            states=states,
            years=src.get("years"),
            source_type=src.get("type"),
            title="years_of_schooling",
        )
        out_path = write_data(
            result,
            out_dir / f"{auto_name}.csv.xz",
            census_standardize=True,
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
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    client = CensusClient()

    results = []
    for name, src in config["sources"].items():
        # VA ingest output is intermediate (prepare adds HD aggregation)
        out_dir = WORKING_DIR if name == "va" else DIST_DIR
        results.append(run_source(name, src, out_dir, client))
    return results


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
