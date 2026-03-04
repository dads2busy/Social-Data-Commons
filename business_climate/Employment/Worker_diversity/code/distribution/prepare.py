"""Prepare worker diversity data for dashboard sites.

Reads ingest output (combined block_group/tract/county files per coverage area)
and reformats into per-level wide files for each dashboard.
"""

from pathlib import Path

import yaml
from sdc_core.io import data_reformat_for_site
from sdc_core.log import get_logger
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("worker_diversity.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


DASHBOARD_MAP = {
    "ncr": "dashboard_data/national_capital_region_data",
}


def find_source(dist_dir: Path, prefix: str) -> Path | None:
    candidates = sorted(dist_dir.glob(f"{prefix}_cttrbg_lodes*employment_by_minority_workers*.csv.xz"))
    return candidates[-1] if candidates else None


def run() -> None:
    config = load_config()
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    for name, src in config["sources"].items():
        source_path = find_source(DIST_DIR, name)
        if not source_path:
            log.warning("No ingest output found for source '%s' in %s", name, DIST_DIR)
            continue

        dashboard_rel = DASHBOARD_MAP.get(name)
        if not dashboard_rel:
            log.info("No dashboard mapping for source '%s', skipping", name)
            continue

        dashboard_dir = REPO_DIR / dashboard_rel
        levels = src.get("geographies", ["block_group", "tract", "county"])

        paths = data_reformat_for_site(
            source_path=source_path,
            output_dir=dashboard_dir,
            levels=levels,
            coverage_area=name,
            data_source="lodes",
            title="employment_by_minority_workers",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
