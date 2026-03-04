"""Prepare Health Opportunity Index indicators for dashboard sites.

Aggregates tract-level HOI data to county and health district levels
using population-weighted averages, then reformats for the VA dashboard.

Population weights use ACS total population (B01003_001) at the tract level.
"""

from pathlib import Path

import pandas as pd
import yaml
from sdc_core.census import CensusClient
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name

TOPIC_DIR = Path(__file__).resolve().parents[2]


def _find_repo_root() -> Path:
    p = TOPIC_DIR
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    raise FileNotFoundError("Could not find repo root (pyproject.toml)")


REPO_DIR = _find_repo_root()
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("health_opportunity_index.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path) -> Path | None:
    candidates = sorted(
        p for p in dist_dir.glob("va_*vdh_*health_opportunity_index*.csv.xz")
        if "hdcttr" not in p.name
    )
    return candidates[-1] if candidates else None


def fetch_tract_population(client: CensusClient) -> pd.DataFrame:
    """Fetch VA tract-level total population for weighting.

    Returns DataFrame with columns: geoid, year, pop
    Uses ACS 2017 for HOI year 2017 and ACS 2021 for HOI year 2020
    (matching the R code in aggregate_tr_to_hdct.R).
    """
    pop_frames: list[pd.DataFrame] = []
    for acs_year, data_year in [(2017, 2017), (2021, 2020)]:
        log.info("Fetching ACS %d tract population for data year %d", acs_year, data_year)
        pop = client.get_acs_wide(
            variables={"pop": "B01003_001"},
            geography="tract",
            state="VA",
            year=acs_year,
            estimate_only=True,
        )
        pop = pop[["geoid", "pop"]].copy()
        pop["year"] = data_year
        pop_frames.append(pop)

    return pd.concat(pop_frames, ignore_index=True)


def weighted_aggregate_to_county(
    tract_df: pd.DataFrame, pop_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregate tract -> county using population-weighted average.

    Returns (county_df, intermediate_df) where intermediate_df contains
    the population totals needed for subsequent HD aggregation.
    """
    merged = tract_df.merge(pop_df, on=["geoid", "year"], how="left")
    merged["pop_wgt_val"] = merged["value"] * merged["pop"]
    merged["county_fips"] = merged["geoid"].str[:5]

    agg = (
        merged.groupby(["county_fips", "year", "measure"])
        .agg(ct_pop=("pop", "sum"), ct_pop_wgt_val=("pop_wgt_val", "sum"))
        .reset_index()
    )
    agg["value"] = agg["ct_pop_wgt_val"] / agg["ct_pop"]
    agg = agg.rename(columns={"county_fips": "geoid"})
    agg["moe"] = pd.NA
    agg["region_type"] = "county"

    county_df = agg[["geoid", "year", "measure", "value", "moe", "region_type"]].copy()
    intermediate = agg[["geoid", "year", "measure", "ct_pop", "ct_pop_wgt_val"]].copy()
    return county_df, intermediate


def weighted_aggregate_to_hd(
    intermediate: pd.DataFrame, crosswalk: pd.DataFrame
) -> pd.DataFrame:
    """Aggregate county -> health district using population-weighted average.

    Uses the intermediate population totals from the county aggregation step.
    """
    merged = intermediate.merge(
        crosswalk[["ct_geoid", "hd_geoid"]],
        left_on="geoid",
        right_on="ct_geoid",
        how="inner",
    )

    hd = (
        merged.groupby(["hd_geoid", "year", "measure"])
        .agg(hd_pop=("ct_pop", "sum"), hd_pop_wgt_val=("ct_pop_wgt_val", "sum"))
        .reset_index()
    )
    hd["value"] = hd["hd_pop_wgt_val"] / hd["hd_pop"]
    hd = hd.rename(columns={"hd_geoid": "geoid"})
    hd["moe"] = pd.NA
    hd["region_type"] = "health_district"

    return hd[["geoid", "year", "measure", "value", "moe", "region_type"]]


def run() -> None:
    config = load_config()
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    va_source = find_source(DIST_DIR)
    if not va_source:
        raise FileNotFoundError(
            f"No HOI ingest output found in {DIST_DIR}. Run ingest.py first."
        )

    log.info("Reading ingest output: %s", va_source)
    tracts = read_data(va_source)

    # Fetch population weights
    client = CensusClient()
    pop_df = fetch_tract_population(client)

    # Aggregate tract -> county (population-weighted)
    log.info("Aggregating tracts to counties (population-weighted)")
    county_df, intermediate = weighted_aggregate_to_county(tracts, pop_df)
    log.info("  %d county rows", len(county_df))

    # Aggregate county -> health district (population-weighted)
    log.info("Aggregating counties to health districts (population-weighted)")
    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})
    hd_df = weighted_aggregate_to_hd(intermediate, xwalk)
    log.info("  %d health district rows", len(hd_df))

    # Combine all levels
    combined = pd.concat([hd_df, county_df, tracts], ignore_index=True)
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

    filename = (
        build_file_name(
            coverage_area="va",
            data_source="vdh",
            years=combined["year"].unique().tolist(),
            title="health_opportunity_index",
            geographies=["health_district", "county", "tract"],
        )
        + ".csv.xz"
    )
    out_path = write_data(combined, DIST_DIR / filename)
    log.info("Wrote %d rows to %s", len(combined), out_path)

    # Reformat for VA dashboard
    for p in data_reformat_for_site(
        source_path=out_path,
        output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
        levels=["health_district", "county", "tract"],
        coverage_area="va",
        data_source="vdh",
        title="health_opportunity_index",
        measure_info_path=measure_info,
    ):
        log.info("Wrote %s", p)


if __name__ == "__main__":
    run()
