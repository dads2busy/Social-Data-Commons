"""Prepare overall food insecurity data for dashboard sites.

Reads the master working files (all 6 measures) and tract 2020 data,
filters to overall food insecurity measures (percent_food_insecure,
number_food_insecure), combines county (2014-2019) with tract (2020),
and writes distribution files + dashboard files.
"""

from pathlib import Path

import pandas as pd
import yaml
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[3]
WORK_DIR = TOPIC_DIR / "data/working"
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("overall_food_insecurity.prepare")

OVERALL_MEASURES = {"Food_Insecurity_Rate", "Num_Food_Insecure"}
RENAME_MAP = {
    "Food_Insecurity_Rate": "percent_food_insecure",
    "Num_Food_Insecure": "number_food_insecure",
}

DASHBOARD_MAP = {
    "ncr": "dashboard_data/national_capital_region_data",
    "va": "dashboard_data/virginia_public_health_data",
}


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def filter_and_rename(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to overall measures and rename to distribution names."""
    out = df[df["measure"].isin(OVERALL_MEASURES)].copy()
    out["measure"] = out["measure"].map(RENAME_MAP)
    return out


def run() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    # --- NCR ---
    ncr_ct = read_data(WORK_DIR / "ncr_ct_fa_2014_2019_food_security.csv.xz")
    ncr_ct = filter_and_rename(ncr_ct)

    ncr_tr = read_data(WORK_DIR / "ncr_tr_fa_2020_food_insecurity.csv.xz")

    ncr = pd.concat([ncr_ct, ncr_tr], ignore_index=True)
    ncr_path = write_data(ncr, DIST_DIR / "ncr_cttr_fa_2014_2020_overall_food_insecurity.csv.xz")
    log.info("Wrote %d NCR rows to %s", len(ncr), ncr_path)

    dashboard_rel = DASHBOARD_MAP.get("ncr")
    if dashboard_rel:
        paths = data_reformat_for_site(
            source_path=ncr_path,
            output_dir=REPO_DIR / dashboard_rel,
            levels=["county", "tract"],
            coverage_area="ncr",
            data_source="fa",
            title="overall_food_insecurity",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)

    # --- VA ---
    va_ct = read_data(WORK_DIR / "va_hdct_fa_2014_2019_food_security.csv.xz")
    va_ct = filter_and_rename(va_ct)

    va_tr = read_data(WORK_DIR / "va_tr_fa_2020_food_insecurity.csv.xz")

    va = pd.concat([va_ct, va_tr], ignore_index=True)
    va_path = write_data(va, DIST_DIR / "va_hdcttr_fa_2014_2020_overall_food_insecurity.csv.xz")
    log.info("Wrote %d VA rows to %s", len(va), va_path)

    dashboard_rel = DASHBOARD_MAP.get("va")
    if dashboard_rel:
        paths = data_reformat_for_site(
            source_path=va_path,
            output_dir=REPO_DIR / dashboard_rel,
            levels=["health_district", "county", "tract"],
            coverage_area="va",
            data_source="fa",
            title="overall_food_insecurity",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)


if __name__ == "__main__":
    run()
