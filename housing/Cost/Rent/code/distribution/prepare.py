"""Prepare HUD Fair Market Rent data for dashboard sites."""

from pathlib import Path

import pandas as pd
import yaml
from sdc_core.geo import aggregate_with_crosswalk
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[2]  # housing/Cost/Rent is 3 levels deep
DIST_DIR = TOPIC_DIR / "data" / "distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("housing_cost.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path, prefix: str) -> Path | None:
    """Find ingest output file (cttr, not hdcttr).

    Prefer multi-year files (longer names) over single-year legacy files.
    """
    candidates = sorted(
        dist_dir.glob(f"{prefix}_cttr_hud*housing_cost*.csv.xz"),
        key=lambda p: len(p.name),
    )
    return candidates[-1] if candidates else None


def build_va_with_health_districts(va_source: Path, crosswalk_path: Path) -> Path:
    """Add health district aggregation to VA distribution file."""
    df = read_data(va_source)
    counties = df[df["geoid"].str.len() == 5].copy()
    tracts = df[df["geoid"].str.len() != 5].copy()

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
    hd["data_method"] = "scaled"

    combined = pd.concat([hd, counties, tracts], ignore_index=True)
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

    years = sorted(combined["year"].unique().tolist())
    filename = build_file_name(
        coverage_area="va",
        data_source="hud",
        years=years,
        title="housing_cost",
        geographies=["health_district", "county", "tract"],
    ) + ".csv.xz"
    out_path = write_data(combined, DIST_DIR / filename, census_standardize=False)
    log.info("Wrote VA with HD: %d rows → %s", len(combined), out_path.name)
    return out_path


def run() -> None:
    config = load_config()
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    # VA: add health districts, then reformat for dashboard
    va_source = find_source(DIST_DIR, "va")
    if va_source:
        log.info("VA source: %s", va_source.name)
        va_dist = build_va_with_health_districts(va_source, crosswalk_path)
        for p in data_reformat_for_site(
            source_path=va_dist,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county", "tract"],
            coverage_area="va",
            data_source="hud",
            title="housing_cost",
            measure_info_path=measure_info,
        ):
            log.info("Wrote dashboard: %s", p)
    else:
        log.warning("No VA ingest output found")

    # NCR: reformat for dashboard (no HD aggregation)
    ncr_source = find_source(DIST_DIR, "ncr")
    if ncr_source:
        log.info("NCR source: %s", ncr_source.name)
        for p in data_reformat_for_site(
            source_path=ncr_source,
            output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
            levels=["county", "tract"],
            coverage_area="ncr",
            data_source="hud",
            title="housing_cost",
            measure_info_path=measure_info,
        ):
            log.info("Wrote dashboard: %s", p)
    else:
        log.warning("No NCR ingest output found")

    # Clean up ingest-only VA file (replaced by hdcttr version)
    if va_source and va_source.exists():
        va_source.unlink()
        log.info("Removed ingest-only VA file: %s", va_source.name)


if __name__ == "__main__":
    run()
    update_version(TOPIC_DIR)
