"""Prepare agriculture data for dashboard sites.

Reads ingest output (county-level NASS data for VA) and reformats into
per-level wide files for the NCR dashboard.
"""

from pathlib import Path

import yaml
from sdc_core.io import data_reformat_for_site
from sdc_core.log import get_logger

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("agriculture.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path) -> Path | None:
    candidates = sorted(dist_dir.glob("va_ct_*_industry_agriculture.csv.xz"))
    return candidates[-1] if candidates else None


def run() -> None:
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    ncr_dashboard = REPO_DIR / "dashboard_data/national_capital_region_data"

    source_path = find_source(DIST_DIR)
    if not source_path:
        log.warning("No ingest output found in %s", DIST_DIR)
        return

    paths = data_reformat_for_site(
        source_path=source_path,
        output_dir=ncr_dashboard,
        levels=["county"],
        coverage_area="va",
        data_source="nass",
        title="industry_agriculture",
        measure_info_path=measure_info,
    )
    for p in paths:
        log.info("Wrote %s", p)


if __name__ == "__main__":
    run()
