"""Prepare primary care access scores for dashboard sites.

Steps:
1. Read VA and NCR ingest output from data/distribution/
2. Aggregate VA county data to health districts via crosswalk
3. Write combined VA distribution file (BG+tract+county+HD)
4. Call data_reformat_for_site for VA and NCR dashboard files
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
REPO_DIR = TOPIC_DIR.parents[4]
DIST_DIR = TOPIC_DIR / "data" / "distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

MEASURE_PREFIX = "primcare"
DATA_SOURCE = "cms"

log = get_logger("primcare.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_va_source(dist_dir: Path) -> Path | None:
    """Find VA ingest output (county+tract+BG, no HD)."""
    candidates = sorted(
        p for p in dist_dir.glob(f"va_cttrbg_*access_scores_{MEASURE_PREFIX}*.csv.xz")
        if "hdcttrbg" not in p.name
    )
    return candidates[-1] if candidates else None


def find_ncr_source(dist_dir: Path) -> Path | None:
    """Find NCR ingest output (county+tract+BG)."""
    candidates = sorted(
        dist_dir.glob(f"ncr_cttrbg_*access_scores_{MEASURE_PREFIX}*.csv.xz")
    )
    return candidates[-1] if candidates else None


def build_va_with_health_districts(va_source: Path, crosswalk_path: Path) -> Path:
    """Read VA ingest output, add health district aggregation, write combined file."""
    log.info("Reading VA source: %s", va_source.name)
    df = read_data(va_source)
    df["geoid"] = df["geoid"].astype(str)

    # County rows are 5-char GEOIDs — aggregate those to health districts
    counties = df[df["geoid"].str.len() == 5].copy()
    non_counties = df[df["geoid"].str.len() != 5].copy()

    log.info("Aggregating %d county rows to health districts", len(counties))

    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})

    # FCA measures use population-weighted mean at county→HD, but
    # aggregate_with_crosswalk only supports simple agg methods.
    # For county→HD (few counties per HD), simple mean is acceptable.
    # Count measures need sum; travel time measures need mean.
    count_measures = counties[counties["measure"].str.endswith("_cnt")]["measure"].unique()
    other_measures = counties[~counties["measure"].isin(count_measures)]["measure"].unique()

    hd_frames = []

    # Sum for count measures
    if len(count_measures) > 0:
        cnt_data = counties[counties["measure"].isin(count_measures)]
        hd_cnt = aggregate_with_crosswalk(
            cnt_data,
            crosswalk=xwalk,
            source_col="ct_geoid",
            target_col="hd_geoid",
            method="sum",
            value_col="value",
            target_region_type="health_district",
        )
        hd_cnt["moe"] = pd.NA
        hd_cnt["data_method"] = "observed"
        hd_frames.append(hd_cnt)

    # Mean for FCA and travel time measures
    if len(other_measures) > 0:
        other_data = counties[counties["measure"].isin(other_measures)]
        hd_other = aggregate_with_crosswalk(
            other_data,
            crosswalk=xwalk,
            source_col="ct_geoid",
            target_col="hd_geoid",
            method="mean",
            value_col="value",
            target_region_type="health_district",
        )
        hd_other["moe"] = pd.NA
        # Preserve data_method from source rows
        fca_measure_names = {
            m for m in other_measures
            if m.endswith(("_2sfca", "_e2sfca", "_3sfca"))
        }
        hd_other["data_method"] = hd_other["measure"].apply(
            lambda m: "modeled" if m in fca_measure_names else "observed"
        )
        hd_frames.append(hd_other)

    hd = pd.concat(hd_frames, ignore_index=True) if hd_frames else pd.DataFrame()

    combined = pd.concat([non_counties, counties, hd], ignore_index=True)
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

    years = combined["year"].unique().tolist()
    filename = (
        build_file_name(
            coverage_area="va",
            data_source=DATA_SOURCE,
            years=years,
            title=f"access_scores_{MEASURE_PREFIX}",
            geographies=["health_district", "county", "tract", "block_group"],
        )
        + ".csv.xz"
    )

    out_path = write_data(combined, DIST_DIR / filename)
    log.info("Wrote %d rows to %s", len(combined), out_path.name)
    return out_path


def run() -> None:
    config = load_config()
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    # --- VA pipeline ---
    va_source = find_va_source(DIST_DIR)
    if va_source:
        va_dist = build_va_with_health_districts(va_source, crosswalk_path)
        # Remove ingest-only file if prepare wrote a different (HD-inclusive) file
        if va_dist != va_source:
            va_source.unlink()
            log.info("Removed ingest-only file: %s", va_source.name)
        for p in data_reformat_for_site(
            source_path=va_dist,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county", "tract", "block_group"],
            coverage_area="va",
            data_source=DATA_SOURCE,
            title=f"access_scores_{MEASURE_PREFIX}",
            measure_info_path=measure_info,
        ):
            log.info("Wrote VA dashboard: %s", p)
    else:
        log.warning("No VA source file found in %s", DIST_DIR)

    # --- NCR pipeline (no health districts) ---
    ncr_source = find_ncr_source(DIST_DIR)
    if ncr_source:
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
