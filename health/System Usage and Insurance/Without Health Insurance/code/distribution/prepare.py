"""Prepare health insurance coverage for dashboard sites.

Steps:
1. Read the VA ACS distribution file (county/tract)
2. Aggregate county-level measures to health districts via crosswalk
3. Combine all levels and write updated VA distribution file
4. Reformat both VA and NCR distribution files to wide per-level files
   for their respective dashboard repos
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
REPO_DIR = TOPIC_DIR.parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("without_health_insurance.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_va_source(dist_dir: Path) -> Path | None:
    """Find the most recent VA ACS distribution file (ingest output only)."""
    candidates = sorted(
        p for p in dist_dir.glob("va_cttr_*without_health_insurance*.csv.xz")
        if "hdcttr" not in p.name
    )
    return candidates[-1] if candidates else None


def find_ncr_source(dist_dir: Path) -> Path | None:
    """Find the most recent NCR ACS distribution file."""
    candidates = sorted(dist_dir.glob("ncr_cttrbg_*without_health_insurance*.csv.xz"))
    return candidates[-1] if candidates else None


def build_va_with_health_districts(va_source: Path, crosswalk_path: Path) -> Path:
    """Aggregate county data to health districts and write combined VA file."""
    log.info("Reading VA source: %s", va_source)
    df = read_data(va_source)
    df["geoid"] = df["geoid"].astype(str)

    counties = df[df["geoid"].str.len() == 5].copy()
    non_counties = df[df["geoid"].str.len() != 5].copy()

    log.info(
        "Aggregating %d county×year×measure rows to health districts",
        len(counties),
    )

    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})

    # Both measures are percentages — aggregate with mean
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

    years = combined["year"].unique().tolist()
    filename = (
        build_file_name(
            coverage_area="va",
            data_source="census_acs",
            years=years,
            title="without_health_insurance",
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
    va_source = find_va_source(DIST_DIR)
    if va_source:
        va_dist = build_va_with_health_districts(va_source, crosswalk_path)
        if va_dist != va_source:
            va_source.unlink()
            log.info("Removed ingest-only file: %s", va_source.name)
        for p in data_reformat_for_site(
            source_path=va_dist,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county", "tract"],
            coverage_area="va",
            data_source="census_acs",
            title="without_health_insurance",
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)
    else:
        log.warning("No VA source file found in %s", DIST_DIR)

    # --- NCR pipeline ---
    ncr_source = find_ncr_source(DIST_DIR)
    if ncr_source:
        for p in data_reformat_for_site(
            source_path=ncr_source,
            output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
            levels=["county", "tract", "block_group"],
            coverage_area="ncr",
            data_source="census_acs",
            title="without_health_insurance",
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)
    else:
        log.warning("No NCR source file found in %s", DIST_DIR)


if __name__ == "__main__":
    run()
    update_version(TOPIC_DIR)
