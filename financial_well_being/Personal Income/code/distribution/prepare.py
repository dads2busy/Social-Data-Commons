"""Prepare personal income (earnings per job) for dashboard sites.

Reads county-level ingest output, aggregates to health districts (summing
tot_compensation and tot_employment, then recomputing earnings_per_job),
writes combined HD+county file, and reformats for the VA dashboard.
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

log = get_logger("personal_income.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path) -> Path | None:
    """Find the ingest output file (county-only, no HD rows)."""
    candidates = sorted(dist_dir.glob("va_ct_bea*personal_income*.csv.xz"))
    return candidates[-1] if candidates else None


def build_va_with_health_districts(va_source: Path, crosswalk_path: Path) -> Path:
    """Aggregate county measures to health districts and write combined file.

    For tot_compensation and tot_employment, HD values are the sum of counties.
    For earnings_per_job, HD values are recomputed as
    tot_compensation / tot_employment at the HD level (not averaged).
    """
    log.info("Reading VA source: %s", va_source)
    df = read_data(va_source)

    counties = df[df["geoid"].str.len() == 5].copy()
    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})

    # Sum tot_compensation and tot_employment to HD level
    sum_measures = ["tot_compensation", "tot_employment"]
    sum_subset = counties[counties["measure"].isin(sum_measures)]
    hd_sums = aggregate_with_crosswalk(
        sum_subset,
        crosswalk=xwalk,
        source_col="ct_geoid",
        target_col="hd_geoid",
        method="sum",
        value_col="value",
        target_region_type="health_district",
    )
    hd_sums["moe"] = pd.NA

    # Recompute earnings_per_job at HD level from the summed values
    hd_comp = hd_sums[hd_sums["measure"] == "tot_compensation"][["geoid", "year", "value"]].rename(
        columns={"value": "tot_compensation"}
    )
    hd_emp = hd_sums[hd_sums["measure"] == "tot_employment"][["geoid", "year", "value"]].rename(
        columns={"value": "tot_employment"}
    )
    hd_wide = hd_comp.merge(hd_emp, on=["geoid", "year"], how="inner")
    hd_wide["value"] = hd_wide["tot_compensation"] / hd_wide["tot_employment"].replace(0, float("nan"))

    hd_epj = hd_wide[["geoid", "year", "value"]].copy()
    hd_epj["measure"] = "earnings_per_job"
    hd_epj["moe"] = pd.NA
    hd_epj["region_type"] = "health_district"

    # Combine county + HD rows
    combined = pd.concat([counties, hd_sums, hd_epj], ignore_index=True)
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

    years = combined["year"].unique().tolist()
    filename = (
        build_file_name(
            coverage_area="va",
            data_source="bea",
            years=years,
            title="personal_income",
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
    if source:
        va_dist = build_va_with_health_districts(source, crosswalk_path)
        for p in data_reformat_for_site(
            source_path=va_dist,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county"],
            coverage_area="va",
            data_source="bea",
            title="personal_income",
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)
    else:
        log.warning("No source file found in %s", DIST_DIR)

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
