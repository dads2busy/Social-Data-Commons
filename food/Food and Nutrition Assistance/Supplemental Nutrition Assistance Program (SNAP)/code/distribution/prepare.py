"""Prepare SNAP data for dashboard sites.

Steps:
1. Read VA ingest output (county/tract/block_group)
2. Aggregate county counts to health districts via crosswalk
3. Recompute percentage from aggregated counts
4. Write updated VA distribution file with HD level
5. Reformat VA and NCR distribution files for dashboards
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
REPO_DIR = TOPIC_DIR.parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("snap.prepare")

BEDFORD_CITY = "51515"
CENTRAL_VA_HD = "51_hd_05"

DASHBOARD_MAP = {
    "ncr": "dashboard_data/national_capital_region_data",
    "va": "dashboard_data/virginia_public_health_data",
}


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path, prefix: str) -> Path | None:
    """Find the most recent ingest output for a coverage area."""
    candidates = sorted(dist_dir.glob(f"{prefix}_*_hh_receiving_snap.csv.xz"))
    # Exclude prepare outputs that have 'hd' in the geo prefix
    candidates = [c for c in candidates if "hd" not in c.name.split("_")[1]]
    return candidates[-1] if candidates else None


def build_va_with_health_districts(va_source: Path, crosswalk_path: Path) -> Path:
    """Aggregate county counts to health districts, recompute percentage."""
    log.info("Reading VA source: %s", va_source)
    df = read_data(va_source)
    df["geoid"] = df["geoid"].astype(str)

    counties = df[df["region_type"] == "county"].copy()
    non_counties = df[df["region_type"] != "county"].copy()

    log.info(
        "Aggregating %d county rows to health districts", len(counties)
    )

    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})

    # Bedford City (51515) merged into Bedford County in 2013;
    # assign it to Central Virginia HD for the single year it appears
    if (counties["geoid"] == BEDFORD_CITY).any():
        bedford_row = pd.DataFrame(
            {"ct_geoid": [BEDFORD_CITY], "hd_geoid": [CENTRAL_VA_HD]}
        )
        xwalk = pd.concat([xwalk, bedford_row], ignore_index=True)

    # Aggregate count and population by sum
    # After census standardization, county rows carry the _geo20 suffix.
    sum_measures = counties[
        counties["measure"].isin(["hh_received_snap_cnt_geo20", "population_geo20"])
    ]
    hd_sums = aggregate_with_crosswalk(
        sum_measures,
        crosswalk=xwalk,
        source_col="ct_geoid",
        target_col="hd_geoid",
        method="sum",
        value_col="value",
        target_region_type="health_district",
    )

    # Recompute percentage from summed counts
    hd_wide = hd_sums.pivot_table(
        index=["geoid", "year", "region_type"],
        columns="measure",
        values="value",
    ).reset_index()

    hd_pct = hd_wide[["geoid", "year", "region_type"]].copy()
    hd_pct["measure"] = "hh_received_snap_pct_geo20"
    hd_pct["value"] = (
        hd_wide["hh_received_snap_cnt_geo20"] / hd_wide["population_geo20"] * 100
    ).where(hd_wide["population_geo20"].gt(0), other=0.0)
    hd_pct["moe"] = pd.NA

    hd_sums["moe"] = pd.NA
    health_districts = pd.concat([hd_sums, hd_pct], ignore_index=True)

    combined = pd.concat([non_counties, counties, health_districts], ignore_index=True)
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(
        drop=True
    )

    years = sorted(combined["year"].unique())
    filename = (
        build_file_name(
            coverage_area="va",
            data_source="acs",
            years=years,
            title="hh_receiving_snap",
            geographies=["health_district", "county", "tract", "block_group"],
        )
        + ".csv.xz"
    )

    out_path = write_data(combined, DIST_DIR / filename)
    log.info("Wrote %d rows (with HD) to %s", len(combined), out_path)
    return out_path


def run() -> None:
    config = load_config()
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    # --- VA: aggregate to health districts, then dashboard ---
    va_source = find_source(DIST_DIR, "va")
    if va_source:
        va_dist = build_va_with_health_districts(va_source, crosswalk_path)

        dashboard_rel = DASHBOARD_MAP.get("va")
        if dashboard_rel:
            paths = data_reformat_for_site(
                source_path=va_dist,
                output_dir=REPO_DIR / dashboard_rel,
                levels=["health_district", "county", "tract", "block_group"],
                coverage_area="va",
                data_source="acs",
                title="hh_receiving_snap",
                measure_info_path=measure_info,
            )
            for p in paths:
                log.info("Wrote %s", p)
    else:
        log.warning("No VA source in %s", DIST_DIR)

    # --- NCR: straight to dashboard ---
    ncr_source = find_source(DIST_DIR, "ncr")
    if ncr_source:
        dashboard_rel = DASHBOARD_MAP.get("ncr")
        if dashboard_rel:
            paths = data_reformat_for_site(
                source_path=ncr_source,
                output_dir=REPO_DIR / dashboard_rel,
                levels=["county", "tract", "block_group"],
                coverage_area="ncr",
                data_source="acs",
                title="hh_receiving_snap",
                measure_info_path=measure_info,
            )
            for p in paths:
                log.info("Wrote %s", p)
    else:
        log.warning("No NCR source in %s", DIST_DIR)


if __name__ == "__main__":
    run()
    update_version(TOPIC_DIR)
