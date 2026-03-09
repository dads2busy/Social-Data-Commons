"""Prepare employment measures for dashboard sites.

Steps:
1. Find VA and NCR distribution files produced by ingest.py
2. VA emp_rate: reformat for VA dashboard (health_district, county, tract)
3. VA labor_participate_rate: aggregate counties to health districts (mean),
   combine with non-county rows, write combined VA file, reformat for VA dashboard
4. NCR emp_rate and NCR labor_participate_rate: reformat for NCR dashboard (county, tract)
"""

from pathlib import Path

import pandas as pd
import yaml
from sdc_core.geo import aggregate_with_crosswalk
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("employment.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path, prefix: str, title: str) -> Path | None:
    """Find ingest output (cttr, not hdcttr)."""
    candidates = sorted(dist_dir.glob(f"{prefix}_cttr_census_acs*{title}*.csv.xz"))
    candidates = [c for c in candidates if "_hdcttr_" not in c.name]
    return candidates[-1] if candidates else None


def build_va_with_health_districts(va_source: Path, crosswalk_path: Path, title: str) -> Path:
    log.info("Reading VA source: %s", va_source)
    df = read_data(va_source)

    counties = df[df["geoid"].str.len() == 5].copy()
    non_counties = df[df["geoid"].str.len() != 5].copy()

    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})

    hd = aggregate_with_crosswalk(
        counties,
        crosswalk=xwalk,
        source_col="ct_geoid",
        target_col="hd_geoid",
        method="mean",
        value_col="value",
        target_region_type="health_district",
    )
    hd["moe"] = pd.NA

    combined = pd.concat([non_counties, counties, hd], ignore_index=True)
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

    years_list = combined["year"].unique().tolist()
    filename = (
        build_file_name(
            coverage_area="va",
            data_source="census_acs",
            years=years_list,
            title=title,
            geographies=["health_district", "county", "tract"],
        )
        + ".csv.xz"
    )
    out_path = write_data(combined, DIST_DIR / filename)
    log.info("Wrote %d rows to %s", len(combined), out_path)
    return out_path


def run() -> None:
    config = load_config()
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    va_dashboard = REPO_DIR / "dashboard_data/virginia_public_health_data"
    ncr_dashboard = REPO_DIR / "dashboard_data/national_capital_region_data"

    # --- VA emp_rate ---
    va_emp_source = find_source(DIST_DIR, "va", "employment_rate")
    if va_emp_source:
        va_emp_dist = build_va_with_health_districts(va_emp_source, crosswalk_path, "employment_rate")
        paths = data_reformat_for_site(
            source_path=va_emp_dist,
            output_dir=va_dashboard,
            levels=["health_district", "county", "tract"],
            coverage_area="va",
            data_source="census_acs",
            title="employment_rate",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)
        va_emp_source.unlink(missing_ok=True)
    else:
        log.warning("No VA emp_rate source file found in %s", DIST_DIR)

    # --- VA labor_participate_rate ---
    va_labor_source = find_source(DIST_DIR, "va", "labor_participate_rate")
    if va_labor_source:
        va_labor_dist = build_va_with_health_districts(va_labor_source, crosswalk_path, "labor_participate_rate")
        paths = data_reformat_for_site(
            source_path=va_labor_dist,
            output_dir=va_dashboard,
            levels=["health_district", "county", "tract"],
            coverage_area="va",
            data_source="census_acs",
            title="labor_participate_rate",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)
    else:
        log.warning("No VA labor_participate_rate source file found in %s", DIST_DIR)

    # --- NCR emp_rate ---
    ncr_emp_source = find_source(DIST_DIR, "ncr", "employment_rate")
    if ncr_emp_source:
        paths = data_reformat_for_site(
            source_path=ncr_emp_source,
            output_dir=ncr_dashboard,
            levels=["county", "tract"],
            coverage_area="ncr",
            data_source="census_acs",
            title="employment_rate",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)
    else:
        log.warning("No NCR emp_rate source file found in %s", DIST_DIR)

    # --- NCR labor_participate_rate ---
    ncr_labor_source = find_source(DIST_DIR, "ncr", "labor_participate_rate")
    if ncr_labor_source:
        paths = data_reformat_for_site(
            source_path=ncr_labor_source,
            output_dir=ncr_dashboard,
            levels=["county", "tract"],
            coverage_area="ncr",
            data_source="census_acs",
            title="labor_participate_rate",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)
    else:
        log.warning("No NCR labor_participate_rate source file found in %s", DIST_DIR)

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
