"""Prepare Ookla broadband speed data for dashboard sites.

Steps:
1. Read the VA ingest distribution file (county/tract/block_group)
2. Aggregate county-level measures to health districts via crosswalk
3. Combine all levels and write updated VA distribution file
4. Reformat both VA and NCR distribution files to wide per-level files
   for their respective dashboard repos
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

log = get_logger("ookla.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_va_source(dist_dir: Path) -> Path | None:
    """Find the most recent VA Ookla distribution file."""
    candidates = sorted(dist_dir.glob("va_*ookla*broadband_speed.csv.xz"))
    if candidates:
        return candidates[-1]
    candidates = sorted(dist_dir.glob("va_*broadband_speed.csv.xz"))
    return candidates[-1] if candidates else None


def find_ncr_source(dist_dir: Path) -> Path | None:
    """Find the most recent NCR Ookla distribution file."""
    candidates = sorted(dist_dir.glob("ncr_*ookla*broadband_speed.csv.xz"))
    return candidates[-1] if candidates else None


def build_va_with_health_districts(va_source: Path, crosswalk_path: Path) -> Path:
    """Aggregate county data to health districts and write combined VA file."""
    log.info("Reading VA source: %s", va_source)
    df = read_data(va_source)

    counties = df[df["geoid"].str.len() == 5].copy()
    non_counties = df[df["geoid"].str.len() != 5].copy()

    log.info(
        "Aggregating %d county×year×measure rows to health districts",
        len(counties),
    )

    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})

    # All Ookla speed measures use mean aggregation
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

    # Exclude block groups from VA distribution (not used by VA dashboard)
    non_counties = non_counties[non_counties["geoid"].str.len() != 12]

    combined = pd.concat([non_counties, counties, hd], ignore_index=True)
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

    years = combined["year"].unique().tolist()
    filename = build_file_name(
        coverage_area="va",
        data_source="ookla",
        years=years,
        title="broadband_speed",
        geographies=["health_district", "county", "tract"],
    ) + ".csv.xz"

    out_path = write_data(combined, DIST_DIR / filename)
    log.info("Wrote %d rows to %s", len(combined), out_path)
    return out_path


def run() -> None:
    config = load_config()
    prepare_cfg = config.get("prepare", {})
    crosswalk_path = (TOPIC_DIR / prepare_cfg["crosswalk"]).resolve()
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    # --- VA pipeline ---
    va_source = find_va_source(DIST_DIR)
    if va_source:
        va_dist = build_va_with_health_districts(va_source, crosswalk_path)
        if va_dist != va_source:
            va_source.unlink()
            log.info("Removed ingest-only file: %s", va_source.name)
        paths = data_reformat_for_site(
            source_path=va_dist,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county", "tract"],
            coverage_area="va",
            data_source="ookla",
            title="broadband_speed",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)
    else:
        log.warning("No VA source file found in %s", DIST_DIR)

    # --- NCR pipeline ---
    ncr_source = find_ncr_source(DIST_DIR)
    if ncr_source:
        paths = data_reformat_for_site(
            source_path=ncr_source,
            output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
            levels=["county", "tract", "block_group"],
            coverage_area="ncr",
            data_source="ookla",
            title="broadband_speed",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)
    else:
        log.warning("No NCR source file found in %s", DIST_DIR)


if __name__ == "__main__":
    run()
    update_version(TOPIC_DIR)
