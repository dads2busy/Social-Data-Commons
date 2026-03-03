"""Prepare personal income (earnings per job) for dashboard sites."""

from pathlib import Path

import yaml
from sdc_core.io import data_reformat_for_site
from sdc_core.log import get_logger

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("personal_income.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path) -> Path | None:
    candidates = sorted(dist_dir.glob("va_hdct_bea*personal_income*.csv.xz"))
    return candidates[-1] if candidates else None


def run() -> None:
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    source = find_source(DIST_DIR)
    if source:
        for p in data_reformat_for_site(
            source_path=source,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county"],
            coverage_area="va",
            data_source="bea",
            title="personal_income",
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)
    else:
        log.warning("No source file found in %s", DIST_DIR)


if __name__ == "__main__":
    run()
