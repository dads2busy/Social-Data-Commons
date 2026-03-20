"""Prepare dental access scores for NCR dashboard.

NCR-only pipeline — no health district aggregation (NCR spans VA, MD, DC).
Reads ingest output and writes per-level dashboard files to
dashboard_data/national_capital_region_data/.
"""

from pathlib import Path

import yaml
from sdc_core.io import data_reformat_for_site, read_data
from sdc_core.log import get_logger
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[3]
DIST_DIR = TOPIC_DIR / "data" / "distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

MEASURE_PREFIX = "dent"
DATA_SOURCE = "webmd"

log = get_logger("dentists.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_ncr_source(dist_dir: Path) -> Path | None:
    """Find NCR ingest output (county+tract+BG)."""
    candidates = sorted(
        dist_dir.glob(f"ncr_cttrbg_{DATA_SOURCE}*access_scores_{MEASURE_PREFIX}*.csv.xz")
    )
    return candidates[-1] if candidates else None


def run() -> None:
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    ncr_source = find_ncr_source(DIST_DIR)
    if ncr_source:
        log.info("Reading NCR source: %s", ncr_source.name)
        for p in data_reformat_for_site(
            source_path=ncr_source,
            output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
            levels=["county", "tract", "block_group"],
            coverage_area="ncr",
            data_source=DATA_SOURCE,
            title=f"access_scores_{MEASURE_PREFIX}",
            measure_info_path=measure_info,
        ):
            log.info("Wrote NCR dashboard: %s", p)
    else:
        log.warning("No NCR source file found in %s", DIST_DIR)


if __name__ == "__main__":
    run()
    update_version(TOPIC_DIR)
