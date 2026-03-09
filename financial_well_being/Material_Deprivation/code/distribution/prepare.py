"""Prepare material deprivation index for dashboard sites.

The ingest output already includes health district, county, and tract rows
(HD aggregation is done on raw counts before computing the index). This script
splits the combined files into per-level dashboard files for VA and NCR.
"""

from pathlib import Path

import yaml
from sdc_core.io import data_reformat_for_site
from sdc_core.log import get_logger
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("material_deprivation.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path, prefix: str) -> Path | None:
    """Find the ingest output file for a given coverage area prefix."""
    candidates = sorted(dist_dir.glob(f"{prefix}_*census_acs*material_deprivation*.csv.xz"))
    return candidates[-1] if candidates else None


def run() -> None:
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    # --- VA pipeline ---
    va_source = find_source(DIST_DIR, "va")
    if va_source:
        log.info("Reformatting %s for VA dashboard", va_source)
        paths = data_reformat_for_site(
            source_path=va_source,
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
        log.warning("No VA material deprivation source file found in %s", DIST_DIR)

    # --- NCR pipeline ---
    ncr_source = find_source(DIST_DIR, "ncr")
    if ncr_source:
        log.info("Reformatting %s for NCR dashboard", ncr_source)
        paths = data_reformat_for_site(
            source_path=ncr_source,
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
        log.warning("No NCR material deprivation source file found in %s", DIST_DIR)

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
