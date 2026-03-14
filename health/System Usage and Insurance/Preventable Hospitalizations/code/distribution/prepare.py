"""Prepare preventable hospitalizations for dashboard sites.

Reads ingest output, aggregates county rows to health districts for VA,
and reformats for the VA dashboard.
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

log = get_logger("preventable_hospitalizations.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path, prefix: str) -> Path | None:
    """Find ingest output (county-only) but not prepare output (with HD)."""
    candidates = sorted(
        p for p in dist_dir.glob(f"{prefix}_*county_health_rankings*preventable_hospitalizations*.csv.xz")
        if "hdct" not in p.name and "_hd_" not in p.name
    )
    return candidates[-1] if candidates else None


def build_va_with_health_districts(va_source: Path, crosswalk_path: Path) -> Path:
    """Aggregate county rows to health districts and write combined file."""
    df = read_data(va_source)
    counties = df[df["region_type"] == "county"].copy()

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

    combined = pd.concat([counties, hd], ignore_index=True)
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

    filename = build_file_name(
        coverage_area="va",
        data_source="county_health_rankings",
        years=sorted(combined["year"].unique().tolist()),
        title="preventable_hospitalizations",
        geographies=["health_district", "county"],
    ) + ".csv.xz"
    out_path = write_data(combined, DIST_DIR / filename)
    log.info("Wrote %d rows (with health districts) to %s", len(combined), out_path)
    return out_path


def run() -> None:
    config = load_config()
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    va_source = find_source(DIST_DIR, "va")
    if not va_source:
        log.warning("No VA ingest output found in %s", DIST_DIR)
        return

    va_dist = build_va_with_health_districts(va_source, crosswalk_path)
    for p in data_reformat_for_site(
        source_path=va_dist,
        output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
        levels=["health_district", "county"],
        coverage_area="va",
        data_source="county_health_rankings",
        title="preventable_hospitalizations",
        measure_info_path=measure_info,
    ):
        log.info("Wrote %s", p)

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
