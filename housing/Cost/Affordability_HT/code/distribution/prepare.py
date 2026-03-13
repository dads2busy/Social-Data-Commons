"""Prepare H+T Affordability Index for dashboard sites."""

from pathlib import Path

import pandas as pd
import yaml
from sdc_core.geo import aggregate_with_crosswalk
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"
WORKING_DIR = TOPIC_DIR / "data/working"
MEASURE_INFO = DIST_DIR / "measure_info_reproduce.json"

TITLE = "affordability_index"
DATA_SOURCE = "cnt"

log = get_logger("affordability_ht.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def combine_sources(working_dir: Path, prefix: str) -> pd.DataFrame | None:
    """Find all per-year reproduced files in working dir, concatenate, and return combined DataFrame."""
    candidates = sorted(
        working_dir.glob(f"{prefix}_*reproduced*affordability_ht_index*.csv.xz")
    )
    if not candidates:
        return None

    frames = []
    for f in candidates:
        df = pd.read_csv(f)
        log.info("Read %d rows from %s", len(df), f.name)
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["geoid", "year", "measure", "region_type"])
    log.info("Combined: %d rows across %d years", len(combined), combined["year"].nunique())
    return combined


def build_va_with_health_districts(df: pd.DataFrame, crosswalk_path: Path) -> Path:
    """Drop block groups, aggregate counties to health districts, write combined VA file."""
    # Ensure geoid is string for crosswalk merge
    df["geoid"] = df["geoid"].astype(str)

    # Drop block group rows
    df = df[df["region_type"] != "block_group"].copy()
    log.info("After dropping block_group: %d rows", len(df))

    counties = df[df["region_type"] == "county"].copy()
    non_counties = df[df["region_type"] != "county"].copy()

    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})
    hd = aggregate_with_crosswalk(
        counties, crosswalk=xwalk,
        source_col="ct_geoid", target_col="hd_geoid",
        method="mean",
        value_col="value", target_region_type="health_district",
    )
    hd["moe"] = pd.NA

    combined = pd.concat([non_counties, counties, hd], ignore_index=True)
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

    filename = build_file_name(
        coverage_area="va", data_source=DATA_SOURCE,
        years=combined["year"].unique().tolist(),
        title=TITLE, geographies=["health_district", "county", "tract"],
    ) + ".csv.xz"
    out_path = write_data(combined, DIST_DIR / filename)
    log.info("Wrote %d rows to %s", len(combined), out_path)
    return out_path


def write_ncr_distribution(df: pd.DataFrame) -> Path:
    """Write combined NCR distribution file with proper naming."""
    filename = build_file_name(
        coverage_area="ncr", data_source=DATA_SOURCE,
        years=df["year"].unique().tolist(),
        title=TITLE, geographies=["county", "tract", "block_group"],
    ) + ".csv.xz"
    out_path = write_data(df, DIST_DIR / filename)
    log.info("Wrote %d rows to %s", len(df), out_path)
    return out_path


def run() -> None:
    config = load_config()
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]

    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None
    if measure_info is None:
        fallback = DIST_DIR / "measure_info.json"
        if fallback.exists():
            measure_info = fallback

    # --- VA pipeline ---
    va_df = combine_sources(WORKING_DIR, "va")
    if va_df is not None:
        va_dist = build_va_with_health_districts(va_df, crosswalk_path)
        for p in data_reformat_for_site(
            source_path=va_dist,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county", "tract"],
            coverage_area="va", data_source=DATA_SOURCE, title=TITLE,
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)
    else:
        log.warning("No VA source found in %s", WORKING_DIR)

    # --- NCR pipeline ---
    ncr_df = combine_sources(WORKING_DIR, "ncr")
    if ncr_df is not None:
        ncr_dist = write_ncr_distribution(ncr_df)
        for p in data_reformat_for_site(
            source_path=ncr_dist,
            output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
            levels=["county", "tract", "block_group"],
            coverage_area="ncr", data_source=DATA_SOURCE, title=TITLE,
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)
    else:
        log.warning("No NCR source found in %s", WORKING_DIR)

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
