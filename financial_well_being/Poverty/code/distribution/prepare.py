"""Prepare poverty measures for dashboard sites.

The poverty data is NCR tract-level only (no VA health district aggregation).
Reformats ingest output for the NCR dashboard.
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

log = get_logger("poverty.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def run() -> None:
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None
    ncr_dashboard = REPO_DIR / "dashboard_data/national_capital_region_data"

    # NCR adults
    adults = sorted(DIST_DIR.glob("ncr_tr_census_acs*poverty_adults*.csv.xz"))
    if adults:
        for p in data_reformat_for_site(
            source_path=adults[-1],
            output_dir=ncr_dashboard,
            levels=["tract"],
            coverage_area="ncr",
            data_source="census_acs",
            title="poverty_adults",
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)
    else:
        log.warning("No NCR adults poverty source found")

    # NCR children
    children = sorted(DIST_DIR.glob("ncr_tr_census_acs*poverty_children*.csv.xz"))
    if children:
        for p in data_reformat_for_site(
            source_path=children[-1],
            output_dir=ncr_dashboard,
            levels=["tract"],
            coverage_area="ncr",
            data_source="census_acs",
            title="poverty_children",
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)
    else:
        log.warning("No NCR children poverty source found")

    # FFX demographics — no dashboard reformat needed (single-county output)
    # The va059_tr file is already in final form from ingest

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
