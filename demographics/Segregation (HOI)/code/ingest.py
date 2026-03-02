"""Ingest segregation data from ACS.

Configuration is read from segregation/pipeline.yaml.
Note: DP05 variable IDs changed between 2016 and 2017.
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

TOPIC_DIR = Path(__file__).resolve().parents[1]
log = get_logger("segregation.ingest")

RACE_COLS = [
    "hisp_latin",
    "white",
    "black",
    "american_indian",
    "asian",
    "nhopi",
    "sor",
    "two",
]


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def fetch_segregation_data(client: CensusClient, config: dict) -> pd.DataFrame:
    """Fetch ACS data for both year ranges and combine."""
    src = config["source"]
    years = src["years"]
    geographies = src["geographies"]
    profile = src.get("profile")
    states = src.get("states")

    early_years = [y for y in years if y <= 2016]
    late_years = [y for y in years if y >= 2017]

    dfs = []

    if early_years:
        log.info("Fetching %d early years (2015-2016 variable IDs)", len(early_years))
        df_early = client.get_acs_multi(
            variables=src["variables_2015_2016"],
            years=early_years,
            geographies=geographies,
            profile=profile,
            states=states,
        )
        dfs.append(df_early)

    if late_years:
        log.info("Fetching %d late years (2017+ variable IDs)", len(late_years))
        df_late = client.get_acs_multi(
            variables=src["variables_2017_plus"],
            years=late_years,
            geographies=geographies,
            profile=profile,
            states=states,
        )
        dfs.append(df_late)

    return pd.concat(dfs, ignore_index=True)


def compute_entropy(df: pd.DataFrame) -> pd.DataFrame:
    """Compute entropy-based segregation index per tract.

    Entropy = -sum(p * log(p)) for each racial/ethnic proportion p > 0.
    Higher values indicate more diversity; 0 means complete homogeneity.
    """
    df = df[df["total_pop"] > 0].copy()

    for col in RACE_COLS:
        df[f"{col}_prop"] = df[col] / df["total_pop"]

    prop_cols = [f"{col}_prop" for col in RACE_COLS]
    props = df[prop_cols].values
    props = np.where(props > 0, props, np.nan)
    entropy = -np.nansum(props * np.log(props), axis=1)

    df["value"] = np.round(entropy, 2)
    df["measure"] = "segregation_indicator"
    df["moe"] = pd.NA

    return df[["geoid", "year", "measure", "value", "moe", "region_type"]]


def run(pipeline=None) -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        out = config["output"]

        log.info("Starting segregation ingest")

        client = CensusClient()
        df = fetch_segregation_data(client, config)
        log.info("Fetched %d raw rows from Census API", len(df))

        result = compute_entropy(df)

        out_dir = TOPIC_DIR / out["path"]
        states = resolve_states(config["source"])
        auto_name = build_file_name(
            df=result,
            states=states,
            years=config["source"].get("years"),
            source_type=config["source"].get("type"),
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
        log.error("Segregation ingest failed: %s", e, exc_info=True)
        return RunResult(
            success=False,
            error=str(e),
            duration_sec=time.time() - t0,
        )


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
