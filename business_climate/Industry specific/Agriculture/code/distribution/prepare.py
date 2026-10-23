"""Prepare agriculture data for dashboard sites.

Reads ingest output (county-level NASS data for VA) and reformats into
per-level wide files for the VA and NCR dashboards.

Ingest writes one file per census year; the VA dashboard gets all years combined.
"""

import tempfile
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.versioning import update_version

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


def write_va_dashboard(sources: list[Path], measure_info: Path | None) -> None:
    combined = pd.concat([read_data(p) for p in sources], ignore_index=True)
    with tempfile.TemporaryDirectory() as tmp:
        combined_path = write_data(combined, Path(tmp) / "va_ct_industry_agriculture.csv.xz", standardize=False)
        paths = data_reformat_for_site(
            source_path=combined_path,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["county"],
            coverage_area="va",
            data_source="nass",
            title="industry_agriculture",
            measure_info_path=measure_info,
        )
    for p in paths:
        log.info("Wrote %s", p)


def run() -> None:
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    sources = sorted(DIST_DIR.glob("va_ct_*_industry_agriculture.csv.xz"))
    if sources:
        write_va_dashboard(sources, measure_info)

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

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
