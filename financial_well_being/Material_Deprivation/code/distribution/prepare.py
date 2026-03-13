"""Prepare material deprivation index for dashboard sites.

Reads raw count data from ingest, aggregates VA county counts to health
districts, computes the Townsend Material Deprivation Index on all levels
(z-scored within year × region_type groups), writes combined distribution
files, and reformats for VA and NCR dashboards.
"""

from pathlib import Path

import numpy as np
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

RAW_COUNT_COLS = [
    "adult_pop", "unemployed", "occupancy_all",
    "occupant_1", "occupant_2", "occupant_3",
    "occupant_4", "occupant_5", "occupant_6",
    "households_total", "hh_owner_no_veh", "hh_renter_no_veh",
    "all_units", "rent_units",
]

log = get_logger("material_deprivation.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path, prefix: str) -> Path | None:
    """Find the ingest raw counts file for a given coverage area prefix."""
    candidates = sorted(dist_dir.glob(f"{prefix}_cttr_census_acs*material_deprivation_raw*.csv.xz"))
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


def _zscore_within_groups(df: pd.DataFrame, col: str, groups: list[str]) -> pd.Series:
    """Z-score a column within (year, region_type) groups."""
    return df.groupby(groups)[col].transform(
        lambda x: (x - x.mean()) / x.std(ddof=1) if x.std(ddof=1) != 0 else 0.0
    )


def _minmax_within_groups(df: pd.DataFrame, col: str, groups: list[str]) -> pd.Series:
    """Min-max rescale a column to [0, 1] within (year, region_type) groups."""
    return df.groupby(groups)[col].transform(
        lambda x: (x - x.min()) / (x.max() - x.min()) if (x.max() - x.min()) != 0 else 0.0
    )


def compute_townsend(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the Townsend Material Deprivation Index.

    Steps:
    1. Compute 4 raw indicators (with log transforms where specified).
    2. Z-score each indicator within (year, region_type).
    3. Sum the 4 z-scores -> townsend_sum.
    4. Z-score townsend_sum within (year, region_type).
    5. Min-max rescale the final z-score to [0, 1] within (year, region_type).
    6. Return long format with measure = "material_deprivation_indicator".
    """
    work = df.copy()
    groups = ["year", "region_type"]

    # --- 4 raw indicators ---

    # Unemployment rate: unemployed / adult_pop, then log(x + 1)
    unemp_raw = work["unemployed"] / work["adult_pop"].where(work["adult_pop"] > 0, np.nan)
    unemp_raw = unemp_raw.fillna(0.0)
    work["ind_unemp"] = np.log(unemp_raw + 1)

    # Non-car ownership: (hh_owner_no_veh + hh_renter_no_veh) / households_total
    noncar_raw = (work["hh_owner_no_veh"] + work["hh_renter_no_veh"]) / work["households_total"].where(work["households_total"] > 0, np.nan)
    work["ind_noncar"] = noncar_raw.fillna(0.0)

    # Non-home ownership: rent_units / all_units
    nonhome_raw = work["rent_units"] / work["all_units"].where(work["all_units"] > 0, np.nan)
    work["ind_nonhome"] = nonhome_raw.fillna(0.0)

    # Overcrowding: sum of occupant_1..6 / occupancy_all, then log(1 + x)
    overcrowd_num = (
        work["occupant_1"] + work["occupant_2"] + work["occupant_3"]
        + work["occupant_4"] + work["occupant_5"] + work["occupant_6"]
    )
    overcrowd_raw = overcrowd_num / work["occupancy_all"].where(work["occupancy_all"] > 0, np.nan)
    overcrowd_raw = overcrowd_raw.fillna(0.0)
    work["ind_overcrowd"] = np.log(1 + overcrowd_raw)

    # --- Z-score each indicator within (year, region_type) ---
    indicators = ["ind_unemp", "ind_noncar", "ind_nonhome", "ind_overcrowd"]
    for ind in indicators:
        work[f"z_{ind}"] = _zscore_within_groups(work, ind, groups)

    # --- Sum z-scores ---
    work["townsend_sum"] = (
        work["z_ind_unemp"]
        + work["z_ind_noncar"]
        + work["z_ind_nonhome"]
        + work["z_ind_overcrowd"]
    )

    # --- Z-score the sum within (year, region_type) ---
    work["townsend_z"] = _zscore_within_groups(work, "townsend_sum", groups)

    # --- Min-max rescale to [0, 1] within (year, region_type) ---
    work["townsend_final"] = _minmax_within_groups(work, "townsend_z", groups)

    # --- Build long-format output ---
    out = work[["geoid", "year", "region_type"]].copy()
    out["measure"] = "material_deprivation_indicator"
    out["value"] = work["townsend_final"].round(4)
    out["moe"] = pd.NA

    return out.reset_index(drop=True)


def build_va_with_health_districts(va_raw: pd.DataFrame, crosswalk_path: Path) -> pd.DataFrame:
    """Aggregate VA county raw counts to HD, compute Townsend on all levels."""
    county_rows = va_raw[va_raw["geoid"].str.len() == 5].copy()
    tract_rows = va_raw[va_raw["geoid"].str.len() == 11].copy()

    log.info("Aggregating %d county rows to health districts", len(county_rows))
    hd_rows = aggregate_counties_to_hd(county_rows, crosswalk_path)

    # Combine all levels, then compute Townsend (z-scores within year × region_type)
    combined_raw = pd.concat([tract_rows, county_rows, hd_rows], ignore_index=True)
    log.info("Computing Townsend index on %d rows (tract+county+HD)", len(combined_raw))
    return compute_townsend(combined_raw)


def run() -> None:
    config = load_config()
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    # --- VA pipeline ---
    va_source = find_source(WORKING_DIR, "va")
    if va_source:
        log.info("Reading VA raw counts: %s", va_source)
        va_raw = read_data(va_source)
        va_townsend = build_va_with_health_districts(va_raw, crosswalk_path)

        # Write combined distribution file with census standardization
        years = va_townsend["year"].unique().tolist()
        filename = (
            build_file_name(
                coverage_area="va",
                data_source="census_acs",
                years=years,
                title="material_deprivation",
                geographies=["health_district", "county", "tract"],
            )
            + ".csv.xz"
        )
        va_dist_path = write_data(va_townsend, DIST_DIR / filename, census_standardize=True)
        log.info("Wrote %d rows to %s", len(va_townsend), va_dist_path)

        paths = data_reformat_for_site(
            source_path=va_dist_path,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county", "tract"],
            coverage_area="va",
            data_source="census_acs",
            title="material_deprivation",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)
    else:
        log.warning("No VA material deprivation raw source file found in %s", DIST_DIR)

    # --- NCR pipeline (no HD aggregation needed) ---
    ncr_source = find_source(WORKING_DIR, "ncr")
    if ncr_source:
        log.info("Reading NCR raw counts: %s", ncr_source)
        ncr_raw = read_data(ncr_source)

        # Compute Townsend on county+tract only
        log.info("Computing Townsend index on %d NCR rows", len(ncr_raw))
        ncr_townsend = compute_townsend(ncr_raw)

        # Write combined distribution file with census standardization
        years = ncr_townsend["year"].unique().tolist()
        filename = (
            build_file_name(
                coverage_area="ncr",
                data_source="census_acs",
                years=years,
                title="material_deprivation",
                geographies=["county", "tract"],
            )
            + ".csv.xz"
        )
        ncr_dist_path = write_data(ncr_townsend, DIST_DIR / filename, census_standardize=True)
        log.info("Wrote %d rows to %s", len(ncr_townsend), ncr_dist_path)

        paths = data_reformat_for_site(
            source_path=ncr_dist_path,
            output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
            levels=["county", "tract"],
            coverage_area="ncr",
            data_source="census_acs",
            title="material_deprivation",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)
    else:
        log.warning("No NCR material deprivation raw source file found in %s", DIST_DIR)

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
