"""Prepare daycare access data for dashboard sites."""

from pathlib import Path

import yaml
from sdc_core.io import data_reformat_for_site
from sdc_core.log import get_logger
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("daycare.prepare")


def run() -> None:
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    source = sorted(DIST_DIR.glob("va_*daycare_access*.csv.xz"))
    if not source:
        log.warning("No daycare access source file found in %s", DIST_DIR)
        return

    src_path = source[-1]
    log.info("Reformatting %s for VA dashboard", src_path)
    paths = data_reformat_for_site(
        source_path=src_path,
        output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
        levels=["health_district", "county", "tract", "block_group"],
        coverage_area="va",
        data_source="vdss",
        title="daycare_access",
        measure_info_path=measure_info,
    )
    for p in paths:
        log.info("Wrote %s", p)

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
