"""Prepare Employment Access Index for VA dashboard.

Aggregates county-level data to health districts using population-weighted
mean, combines with tract data, and writes dashboard files.
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

log = get_logger("employment_access.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path) -> Path | None:
    """Find ingest output (cttr, not hdcttr)."""
    candidates = sorted(dist_dir.glob("va_cttr_lodes*employment_access*.csv.xz"))
    if not candidates:
        # Fallback to old naming convention
        candidates = sorted(dist_dir.glob("va_cttr_mixed*employment_access*.csv.xz"))
    return candidates[-1] if candidates else None


def build_va_with_health_districts(source: Path, crosswalk_path: Path) -> Path:
    df = read_data(source)

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

    years_list = sorted(combined["year"].unique().tolist())
    filename = build_file_name(
        coverage_area="va", data_source="lodes", years=years_list,
        title="employment_access",
        geographies=["health_district", "county", "tract"],
    ) + ".csv.xz"

    out_path = write_data(combined, DIST_DIR / filename)
    log.info("Wrote %d rows to %s", len(combined), out_path)
    return out_path


def run() -> None:
    config = load_config()
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    source = find_source(DIST_DIR)
    if not source:
        log.warning("No Employment Access ingest output found in %s", DIST_DIR)
        return

    va_dist = build_va_with_health_districts(source, crosswalk_path)

    paths = data_reformat_for_site(
        source_path=va_dist,
        output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
        levels=["health_district", "county", "tract"],
        coverage_area="va",
        data_source="lodes",
        title="employment_access",
        measure_info_path=measure_info,
    )
    for p in paths:
        log.info("Wrote %s", p)

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
