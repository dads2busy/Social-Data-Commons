"""Prepare Industry Minority owned employment metrics for dashboard sites."""

from pathlib import Path

import yaml
from sdc_core.io import data_reformat_for_site
from sdc_core.log import get_logger

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[2]
DIST_DIR = TOPIC_DIR / "data" / "distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("industry_minority_owned.prepare")

DASHBOARD_MAP = {
    "ncr": "dashboard_data/national_capital_region_data",
}


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path, prefix: str, title: str) -> Path | None:
    candidates = sorted(dist_dir.glob(f"{prefix}_*_mi_*_{title}.csv.xz"))
    return candidates[-1] if candidates else None


def run() -> None:
    config = load_config()
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None
    title = "employment_metrics_by_Industry_Minority_owned"

    for prefix in config["sources"]:
        source_path = find_source(DIST_DIR, prefix, title)
        if not source_path:
            log.warning("No ingest output for %s", prefix)
            continue

        dashboard_rel = DASHBOARD_MAP.get(prefix)
        if not dashboard_rel:
            log.info("No dashboard mapping for %s, skipping", prefix)
            continue

        paths = data_reformat_for_site(
            source_path=source_path,
            output_dir=REPO_DIR / dashboard_rel,
            levels=["block_group", "tract", "county"],
            coverage_area=prefix,
            data_source="mi",
            title=title,
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)


if __name__ == "__main__":
    run()
