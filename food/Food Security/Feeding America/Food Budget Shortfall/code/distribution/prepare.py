"""Prepare food budget shortfall data for dashboard sites.

Reads the master working files from Overall Food Insecurity,
filters to weighted_budget_shortfall, and writes distribution + dashboard files.
"""

from pathlib import Path

from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[3]
MASTER_DIR = TOPIC_DIR.parent / "Overall Food Insecurity" / "data" / "working"
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("budget_shortfall.prepare")

MEASURES = {"weighted_budget_shortfall"}

DASHBOARD_MAP = {
    "ncr": "dashboard_data/national_capital_region_data",
    "va": "dashboard_data/virginia_public_health_data",
}


def run() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    # --- NCR ---
    ncr = read_data(MASTER_DIR / "ncr_ct_fa_2014_2019_food_security.csv.xz")
    ncr = ncr[ncr["measure"].isin(MEASURES)]
    ncr_path = write_data(ncr, DIST_DIR / "ncr_ct_fa_2014_2019_food_budget_shortfall.csv.xz")
    log.info("Wrote %d NCR rows to %s", len(ncr), ncr_path)

    dashboard_rel = DASHBOARD_MAP.get("ncr")
    if dashboard_rel:
        paths = data_reformat_for_site(
            source_path=ncr_path,
            output_dir=REPO_DIR / dashboard_rel,
            levels=["county"],
            coverage_area="ncr",
            data_source="fa",
            title="food_budget_shortfall",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)

    # --- VA ---
    va = read_data(MASTER_DIR / "va_hdct_fa_2014_2019_food_security.csv.xz")
    va = va[va["measure"].isin(MEASURES)]
    va_path = write_data(va, DIST_DIR / "va_hdct_fa_2014_2019_food_budget_shortfall.csv.xz")
    log.info("Wrote %d VA rows to %s", len(va), va_path)

    dashboard_rel = DASHBOARD_MAP.get("va")
    if dashboard_rel:
        paths = data_reformat_for_site(
            source_path=va_path,
            output_dir=REPO_DIR / dashboard_rel,
            levels=["health_district", "county"],
            coverage_area="va",
            data_source="fa",
            title="food_budget_shortfall",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
