"""Prepare material deprivation index for dashboard sites.

The ingest output already includes health district, county, and tract rows
(HD aggregation is done on raw counts before computing the index). This script
only splits the combined file into per-level dashboard files.
"""

from pathlib import Path

import yaml
from sdc_core.io import data_reformat_for_site
from sdc_core.log import get_logger

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("material_deprivation.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path) -> Path | None:
    """Find the ingest output file containing all three geography levels."""
    candidates = sorted(dist_dir.glob("va_hdcttr_census_acs*material_deprivation*.csv.xz"))
    return candidates[-1] if candidates else None


def run() -> None:
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    source = find_source(DIST_DIR)
    if not source:
        log.warning("No material deprivation source file found in %s", DIST_DIR)
        return

    log.info("Reformatting %s for VA dashboard", source)
    paths = data_reformat_for_site(
        source_path=source,
        output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
        levels=["health_district", "county", "tract"],
        coverage_area="va",
        data_source="census_acs",
        title="material_deprivation",
        measure_info_path=measure_info,
    )
    for p in paths:
        log.info("Wrote %s", p)


if __name__ == "__main__":
    run()
