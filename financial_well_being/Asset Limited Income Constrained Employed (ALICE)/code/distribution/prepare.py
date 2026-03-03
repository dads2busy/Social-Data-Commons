"""Prepare ALICE data for dashboard sites.

County-level only (no tract, no health district). No aggregation needed.
"""
from pathlib import Path

import yaml
from sdc_core.io import data_reformat_for_site
from sdc_core.log import get_logger

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("alice.prepare")


def find_source(dist_dir: Path) -> Path | None:
    """Return the most recent ALICE ingest output file, or None if not found."""
    candidates = sorted(dist_dir.glob("va_ct_alice*alice*.csv.xz"))
    return candidates[-1] if candidates else None


def run() -> None:
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    va_source = find_source(DIST_DIR)
    if not va_source:
        log.error(
            "No ALICE distribution file found in %s — run ingest.py first", DIST_DIR
        )
        raise SystemExit(1)

    log.info("Reformatting %s for VA dashboard", va_source.name)
    paths = data_reformat_for_site(
        source_path=va_source,
        output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
        levels=["county"],
        coverage_area="va",
        data_source="alice",
        title="alice",
        measure_info_path=measure_info,
    )
    for p in paths:
        log.info("Wrote %s", p)


if __name__ == "__main__":
    run()
