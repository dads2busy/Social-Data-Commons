"""Prepare postsecondary education attainment for dashboard sites.

Steps:
1. Find VA and NCR distribution files produced by ingest.py
2. For VA: aggregate county -> health district (sum for counts, mean for percents),
   write combined VA file, reformat for VA dashboard
3. For NCR: reformat for NCR dashboard (county, tract)
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

log = get_logger("postsecondary.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path, prefix: str) -> Path | None:
    candidates = sorted(dist_dir.glob(f"{prefix}_cttr_*postsecondary*.csv.xz"))
    return candidates[-1] if candidates else None


def build_va_with_health_districts(va_source: Path, crosswalk_path: Path) -> Path:
    log.info("Reading VA source: %s", va_source)
    df = read_data(va_source)

    counties = df[df["geoid"].str.len() == 5].copy()
    non_counties = df[df["geoid"].str.len() != 5].copy()

    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})

    count_measures = [m for m in counties["measure"].unique() if "count" in m]
    percent_measures = [m for m in counties["measure"].unique() if "percent" in m]

    hd_parts = []
    for measures, method in [(count_measures, "sum"), (percent_measures, "mean")]:
        subset = counties[counties["measure"].isin(measures)]
        if subset.empty:
            continue
        hd = aggregate_with_crosswalk(
            subset,
            crosswalk=xwalk,
            source_col="ct_geoid",
            target_col="hd_geoid",
            method=method,
            value_col="value",
            target_region_type="health_district",
        )
        hd["moe"] = pd.NA
        hd_parts.append(hd)

    health_districts = (
        pd.concat(hd_parts, ignore_index=True) if hd_parts else pd.DataFrame()
    )

    combined = pd.concat(
        [non_counties, counties, health_districts], ignore_index=True
    )
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

    years = combined["year"].unique().tolist()
    filename = (
        build_file_name(
            coverage_area="va",
            data_source="census_acs",
            years=years,
            title="postsecondary",
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

    # --- VA pipeline ---
    va_source = find_source(DIST_DIR, "va")
    if va_source:
        va_dist = build_va_with_health_districts(va_source, crosswalk_path)
        paths = data_reformat_for_site(
            source_path=va_dist,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county", "tract"],
            coverage_area="va",
            data_source="census_acs",
            title="postsecondary",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)
    else:
        log.warning("No VA source file found in %s", DIST_DIR)

    # --- NCR pipeline ---
    ncr_source = find_source(DIST_DIR, "ncr")
    if ncr_source:
        paths = data_reformat_for_site(
            source_path=ncr_source,
            output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
            levels=["county", "tract"],
            coverage_area="ncr",
            data_source="census_acs",
            title="postsecondary",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)
    else:
        log.warning("No NCR source file found in %s", DIST_DIR)

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
