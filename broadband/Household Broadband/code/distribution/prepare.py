"""Prepare household broadband data for dashboard sites.

Reads raw count data from ingest, aggregates VA county counts to health
districts (sum), computes percentage measures on all levels, writes combined
distribution files, and reformats for VA and NCR dashboards.
"""

from pathlib import Path

import pandas as pd
import yaml
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
WORKING_DIR = TOPIC_DIR / "data/working"
MEASURE_INFO = DIST_DIR / "measure_info.json"

RAW_COUNT_COLS = ["total_hh", "hh_without_internet", "hh_with_broadband", "hh_with_cable_fiber_dsl"]

log = get_logger("household_broadband.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path, prefix: str) -> Path | None:
    """Find the ingest raw counts file for a given coverage area prefix."""
    candidates = sorted(dist_dir.glob(f"{prefix}_*census_acs*household_broadband_raw*.csv.xz"))
    return candidates[-1] if candidates else None


def aggregate_counties_to_hd(counties: pd.DataFrame, crosswalk_path: Path) -> pd.DataFrame:
    """Aggregate county raw counts to health districts via crosswalk (sum)."""
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


def compute_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Compute percentage measures from raw counts and melt to long format."""
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


def run() -> None:
    config = load_config()
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    # --- VA pipeline ---
    va_source = find_source(WORKING_DIR, "va")
    if va_source:
        log.info("Reading VA raw counts: %s", va_source)
        va_raw = read_data(va_source)

        county_rows = va_raw[va_raw["geoid"].str.len() == 5].copy()
        tract_rows = va_raw[va_raw["geoid"].str.len() == 11].copy()
        bg_rows = va_raw[va_raw["geoid"].str.len() == 12].copy()

        log.info("Aggregating %d county rows to health districts", len(county_rows))
        hd_rows = aggregate_counties_to_hd(county_rows, crosswalk_path)

        # Combine all levels, then compute percentages
        combined_raw = pd.concat([tract_rows, county_rows, bg_rows, hd_rows], ignore_index=True)
        log.info("Computing percentage measures on %d rows", len(combined_raw))
        va_long = compute_measures(combined_raw)

        # Write combined distribution file with census standardization
        years = va_long["year"].unique().tolist()
        filename = (
            build_file_name(
                coverage_area="va",
                data_source="census_acs",
                years=years,
                title="household_broadband",
                geographies=["health_district", "county", "tract", "block_group"],
            )
            + ".csv.xz"
        )
        va_dist_path = write_data(va_long, DIST_DIR / filename, census_standardize=True)
        log.info("Wrote %d rows to %s", len(va_long), va_dist_path)

        paths = data_reformat_for_site(
            source_path=va_dist_path,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county", "tract", "block_group"],
            coverage_area="va",
            data_source="census_acs",
            title="household_broadband",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)
    else:
        log.warning("No VA household broadband raw source file found in %s", DIST_DIR)

    # --- NCR pipeline (no HD aggregation needed) ---
    ncr_source = find_source(WORKING_DIR, "ncr")
    if ncr_source:
        log.info("Reading NCR raw counts: %s", ncr_source)
        ncr_raw = read_data(ncr_source)

        log.info("Computing percentage measures on %d NCR rows", len(ncr_raw))
        ncr_long = compute_measures(ncr_raw)

        # Write combined distribution file with census standardization
        years = ncr_long["year"].unique().tolist()
        filename = (
            build_file_name(
                coverage_area="ncr",
                data_source="census_acs",
                years=years,
                title="household_broadband",
                geographies=["county", "tract", "block_group"],
            )
            + ".csv.xz"
        )
        ncr_dist_path = write_data(ncr_long, DIST_DIR / filename, census_standardize=True)
        log.info("Wrote %d rows to %s", len(ncr_long), ncr_dist_path)

        paths = data_reformat_for_site(
            source_path=ncr_dist_path,
            output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
            levels=["county", "tract", "block_group"],
            coverage_area="ncr",
            data_source="census_acs",
            title="household_broadband",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)
    else:
        log.warning("No NCR household broadband raw source file found in %s", DIST_DIR)

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
