"""Prepare median household income for dashboard sites.

No health district aggregation: medians cannot be averaged across geographic
units without the full income distribution. Dashboard files are written directly
from the ingest output at county, tract, and block_group levels.
"""

from pathlib import Path

import yaml
from sdc_core.io import data_reformat_for_site
from sdc_core.log import get_logger

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("household_income.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path, prefix: str) -> Path | None:
    # Ingest writes cttrbg (county+tract+block_group); no prepare combine step
    candidates = sorted(dist_dir.glob(f"{prefix}_cttrbg_census_acs*household_income*.csv.xz"))
    return candidates[-1] if candidates else None


def run() -> None:
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    # --- VA pipeline ---
    va_source = find_source(DIST_DIR, "va")
    if va_source:
        for p in data_reformat_for_site(
            source_path=va_source,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["county", "tract", "block_group"],
            coverage_area="va",
            data_source="census_acs",
            title="household_income",
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)
    else:
        log.warning("No VA source file found in %s", DIST_DIR)

    # --- NCR pipeline ---
    ncr_source = find_source(DIST_DIR, "ncr")
    if ncr_source:
        for p in data_reformat_for_site(
            source_path=ncr_source,
            output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
            levels=["county", "tract", "block_group"],
            coverage_area="ncr",
            data_source="census_acs",
            title="household_income",
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)
    else:
        log.warning("No NCR source file found in %s", DIST_DIR)


if __name__ == "__main__":
    run()
