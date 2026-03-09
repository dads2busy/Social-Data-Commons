"""Ingest household broadband adoption from ACS Table B28002.

Fetches data for each source profile defined in pipeline.yaml, computes
percentage measures, aggregates VA counties to health districts, and writes
one tall-format .csv.xz per coverage area to data/distribution/.
"""

import time
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.census import CensusClient
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.profiles import resolve_profile, resolve_states
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"

log = get_logger("household_broadband.ingest")

RAW_COUNT_COLS = ["total_hh", "hh_without_internet", "hh_with_broadband", "hh_with_cable_fiber_dsl"]


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def compute_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Compute percentage measures and melt to long format."""
    df = df.copy()
    total = df["total_hh"].where(df["total_hh"] > 0, pd.NA)
    df["perc_hh_with_broadband"] = 100 * df["hh_with_broadband"] / total
    df["perc_hh_with_cable_fiber_dsl"] = 100 * df["hh_with_cable_fiber_dsl"] / total
    df["perc_hh_without_internet"] = 100 * df["hh_without_internet"] / total

    # Fill NaN percentages (0/0 case) with 0
    for col in ["perc_hh_with_broadband", "perc_hh_with_cable_fiber_dsl", "perc_hh_without_internet"]:
        df[col] = df[col].fillna(0.0)

    id_cols = ["geoid", "year", "region_type"]
    measure_cols = [c for c in df.columns if c.startswith("perc_hh_")]

    long = df[id_cols + measure_cols].melt(
        id_vars=id_cols,
        var_name="measure",
        value_name="value",
    )
    long["moe"] = pd.NA
    return long


def aggregate_to_hd(counties: pd.DataFrame, crosswalk_path: Path) -> pd.DataFrame:
    """Aggregate county raw counts to health districts via crosswalk."""
    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})
    merged = counties.merge(xwalk, left_on="geoid", right_on="ct_geoid", how="inner")

    hd_frames: list[pd.DataFrame] = []
    for year, group in merged.groupby("year"):
        hd_agg = (
            group.groupby("hd_geoid")[RAW_COUNT_COLS]
            .sum()
            .reset_index()
            .rename(columns={"hd_geoid": "geoid"})
        )
        hd_agg["year"] = year
        hd_agg["region_type"] = "health_district"
        hd_frames.append(hd_agg)

    if not hd_frames:
        return pd.DataFrame(columns=["geoid", "year", "region_type"] + RAW_COUNT_COLS)
    return pd.concat(hd_frames, ignore_index=True)


def run_source(name: str, src: dict, config: dict, client: CensusClient) -> RunResult:
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
            cache_dir=TOPIC_DIR / "data/working/acs_cache",
        )
        log.info("Fetched %d raw rows for '%s'", len(df), name)

        # Separate by geo level
        tract_rows = df[df["geoid"].str.len() == 11].copy()
        county_rows = df[df["geoid"].str.len() == 5].copy()
        bg_rows = df[df["geoid"].str.len() == 12].copy()

        frames = [tract_rows, county_rows, bg_rows]

        # Aggregate VA counties to health districts
        if name == "va" and "va_county_to_hd" in config.get("crosswalks", {}):
            crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
            log.info("Aggregating %d county rows to health districts", len(county_rows))
            hd_rows = aggregate_to_hd(county_rows, crosswalk_path)
            frames.append(hd_rows)

        combined = pd.concat(frames, ignore_index=True)
        result = compute_measures(combined)

        states = resolve_states(src)
        auto_name = build_file_name(
            df=result,
            states=states,
            years=src.get("years"),
            source_type=src.get("type"),
            title="household_broadband",
        )
        filename = f"{auto_name}.csv.xz"
        out_path = write_data(result, DIST_DIR / filename, census_standardize=True)
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

    results = []
    for name, src in config["sources"].items():
        results.append(run_source(name, src, config, client))
    return results


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
