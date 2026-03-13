"""Prepare reproduced H+T Affordability Index for dashboard sites.

Concatenates per-year reproduced output files and splits into per-level
dashboard files for VA and NCR.
"""

from pathlib import Path

import pandas as pd
import yaml
from sdc_core.io import data_reformat_for_site, write_data
from sdc_core.log import get_logger
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info_reproduce.json"

log = get_logger("affordability_ht.prepare_reproduce")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def combine_sources(dist_dir: Path, prefix: str) -> Path | None:
    """Find all per-year reproduced files, concatenate, and write combined file."""
    candidates = sorted(
        dist_dir.glob(f"{prefix}_*reproduced*affordability_ht_index*.csv.xz")
    )
    if not candidates:
        return None

    frames = []
    for f in candidates:
        df = pd.read_csv(f)
        log.info("Read %d rows from %s", len(df), f.name)
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["geoid", "year", "measure", "region_type"])
    log.info("Combined: %d rows across %d years", len(combined), combined["year"].nunique())

    out_path = dist_dir / f"{prefix}_cttrbg_reproduced_all_years_affordability_ht_index.csv.xz"
    write_data(combined, out_path)
    return out_path


def run() -> None:
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    # If no reproduced measure_info, fall back to original
    if measure_info is None:
        fallback = DIST_DIR / "measure_info.json"
        if fallback.exists():
            measure_info = fallback

    # --- VA pipeline ---
    va_source = combine_sources(DIST_DIR, "va")
    if va_source:
        log.info("Reformatting %s for VA dashboard", va_source)
        paths = data_reformat_for_site(
            source_path=va_source,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["county", "tract", "block_group"],
            coverage_area="va",
            data_source="reproduced",
            title="affordability_ht_index",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)
    else:
        log.warning("No VA reproduced source found in %s", DIST_DIR)

    # --- NCR pipeline ---
    ncr_source = combine_sources(DIST_DIR, "ncr")
    if ncr_source:
        log.info("Reformatting %s for NCR dashboard", ncr_source)
        paths = data_reformat_for_site(
            source_path=ncr_source,
            output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
            levels=["county", "tract", "block_group"],
            coverage_area="ncr",
            data_source="reproduced",
            title="affordability_ht_index",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)
    else:
        log.warning("No NCR reproduced source found in %s", DIST_DIR)

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
