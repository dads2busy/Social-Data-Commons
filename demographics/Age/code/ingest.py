"""Ingest age demographics from ACS.

Configuration is read from age/pipeline.yaml. The 49 individual age/sex
variables are aggregated into three age bands: under 20, 20-64, 65+.
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
log = get_logger("age.ingest")

# Age group definitions (column name prefixes to sum)
UNDER_20 = [
    "m_under_5",
    "m_5_9",
    "m_10_14",
    "m_15_17",
    "m_18_19",
    "f_under_5",
    "f_5_9",
    "f_10_14",
    "f_15_17",
    "f_18_19",
]
AGE_20_64 = [
    "m_20",
    "m_21",
    "m_22_24",
    "m_25_29",
    "m_30_34",
    "m_35_39",
    "m_40_44",
    "m_45_49",
    "m_50_54",
    "m_55_59",
    "m_60_61",
    "m_62_64",
    "f_20",
    "f_21",
    "f_22_24",
    "f_25_29",
    "f_30_34",
    "f_35_39",
    "f_40_44",
    "f_45_49",
    "f_50_54",
    "f_55_59",
    "f_60_61",
    "f_62_64",
]
AGE_65_PLUS = [
    "m_65_66",
    "m_67_69",
    "m_70_74",
    "m_75_79",
    "m_80_84",
    "m_85_plus",
    "f_65_66",
    "f_67_69",
    "f_70_74",
    "f_75_79",
    "f_80_84",
    "f_85_plus",
]


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def compute_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate age/sex groups into three age bands, compute counts + percentages."""
    df = df.copy()

    df["age_total_count"] = df["total_pop"]
    df["age_under_20_count"] = df[UNDER_20].sum(axis=1)
    df["age_20_64_count"] = df[AGE_20_64].sum(axis=1)
    df["age_65_plus_count"] = df[AGE_65_PLUS].sum(axis=1)

    df["age_under_20_percent"] = 100 * df["age_under_20_count"] / df["total_pop"]
    df["age_20_64_percent"] = 100 * df["age_20_64_count"] / df["total_pop"]
    df["age_65_plus_percent"] = 100 * df["age_65_plus_count"] / df["total_pop"]

    id_cols = ["geoid", "year", "region_type"]
    measure_cols = [c for c in df.columns if c.startswith("age_")]

    long = df[id_cols + measure_cols].melt(
        id_vars=id_cols,
        var_name="measure",
        value_name="value",
    )
    long["moe"] = pd.NA
    return long.dropna(subset=["value"])


def run(pipeline=None) -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        src = config["source"]
        out = config["output"]

        log.info("Starting age ingest (profile=%s)", src.get("profile"))

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
        log.error("Age ingest failed: %s", e, exc_info=True)
        return RunResult(
            success=False,
            error=str(e),
            duration_sec=time.time() - t0,
        )


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
