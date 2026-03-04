"""Prepare 3rd grade reading scores for the VA dashboard.

Steps:
1. Find the county-level distribution file produced by ingest.py
2. Aggregate county -> health district (mean pass rate)
3. Write combined VA distribution file
4. Reformat for VA dashboard (health_district, county)

Note: Reading scores are VA-only; there is no NCR equivalent.
"""

from pathlib import Path

import pandas as pd
import yaml
from sdc_core.geo import aggregate_with_crosswalk
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("reading_scores.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path) -> Path | None:
    # Match new Python-generated files (pass_rate naming), not old R outputs (mean_read_score)
    candidates = sorted(dist_dir.glob("va_*read_pass_rate*.csv.xz"))
    return candidates[-1] if candidates else None


def build_va_with_health_districts(source: Path, crosswalk_path: Path) -> Path:
    log.info("Reading source: %s", source)
    df = read_data(source)

    counties = df[df["region_type"] == "county"].copy()
    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})

    hd = aggregate_with_crosswalk(
        counties,
        crosswalk=xwalk,
        source_col="ct_geoid",
        target_col="hd_geoid",
        method="mean",
        value_col="value",
        target_region_type="health_district",
    )
    hd["moe"] = pd.NA

    combined = pd.concat([counties, hd], ignore_index=True)
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

    years = combined["year"].unique().tolist()
    filename = (
        build_file_name(
            coverage_area="va",
            data_source="vdoe",
            years=years,
            title="3rd_grade_read_pass_rate",
            geographies=["health_district", "county"],
        )
        + ".csv.xz"
    )
    out_path = write_data(combined, DIST_DIR / filename)
    log.info("Wrote %d rows to %s", len(combined), out_path)
    return out_path


def run() -> None:
    config = load_config()
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    source = find_source(DIST_DIR)
    if not source:
        log.error("No reading score distribution file found in %s — run ingest.py first", DIST_DIR)
        raise SystemExit(1)

    va_dist = build_va_with_health_districts(source, crosswalk_path)

    paths = data_reformat_for_site(
        source_path=va_dist,
        output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
        levels=["health_district", "county"],
        coverage_area="va",
        data_source="vdoe",
        title="reading_scores",
        measure_info_path=measure_info,
    )
    for p in paths:
        log.info("Wrote %s", p)

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
