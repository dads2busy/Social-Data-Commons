"""Ingest transportation population characteristics from ACS subject tables S0801 and S2504.

Measures:
- commute_time: Mean travel time to work (minutes) — S0801_C01_046E
- perc_carpool: % carpooled to work — S0801_C01_004E
- perc_no_vehicle: % households with no vehicle available — S2504_C02_027E

Configuration is read from Population Characteristics/pipeline.yaml.
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

log = get_logger("population_characteristics.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def compute_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Reshape wide ACS subject table data to long format.

    Subject table variables already contain computed values (means, percentages),
    so no derived calculations are needed — just melt to long format.
    """
    df = df.copy()
    id_cols = ["geoid", "year", "region_type"]
    measures = ["commute_time", "perc_carpool", "perc_no_vehicle"]

    long = df[id_cols + measures].melt(
        id_vars=id_cols, var_name="measure", value_name="value",
    )
    long["moe"] = pd.NA
    # Drop NaN and Census suppression sentinel (-666666666)
    long = long.dropna(subset=["value"])
    long = long[long["value"] > -666666000]
    return long


def run_source(name: str, src: dict, out_dir: Path, client: CensusClient) -> RunResult:
    t0 = time.time()
    try:
        log.info("Ingesting source '%s' (profile=%s)", name, src.get("profile"))

        df = client.get_acs_multi(
            variables=src["variables"],
            years=src["years"],
            geographies=src["geographies"],
            profile=src.get("profile"),
            states=src.get("states"),
            table_type=src.get("table_type", "subject"),
            cache_dir=TOPIC_DIR / "data/working/acs_cache",
        )
        if df.empty:
            return RunResult(success=False, error=f"No data for '{name}'", duration_sec=time.time() - t0)

        log.info("Fetched %d raw rows for '%s'", len(df), name)
        result = compute_measures(df)

        states = resolve_states(src)
        auto_name = build_file_name(
            df=result, states=states, years=src.get("years"),
            source_type=src.get("type"), title="population_characteristics",
        )
        out_path = write_data(
            result, out_dir / f"{auto_name}.csv.xz",
            census_standardize=True,
        )
        log.info("Wrote %d rows to %s", len(result), out_path)
        return RunResult(success=True, rows=len(result), output_path=str(out_path), duration_sec=time.time() - t0)
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
