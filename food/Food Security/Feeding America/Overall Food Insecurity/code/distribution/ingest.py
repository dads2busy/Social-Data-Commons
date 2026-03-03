"""Ingest Feeding America Map the Meal Gap data for food security measures.

Reads 6 annual MMG Excel files (2014-2019) for county-level data and
US_tract_2020.xlsx for tract-level 2020 data.  Computes 6 measures,
aggregates VA counties to health districts using ACS population data,
and writes master working files for downstream topic-specific prepare scripts.

Measures:
  Food_Insecurity_Rate, Child_Food_Insecurity_Rate, Cost_Per_Meal,
  Num_Food_Insecure, Num_Child_Food_Insecure, weighted_budget_shortfall
"""

from pathlib import Path

import pandas as pd
import yaml
from sdc_core.census import CensusClient
from sdc_core.io import write_data
from sdc_core.log import get_logger

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[3]
ORIG_DIR = TOPIC_DIR / "data/original"
WORK_DIR = TOPIC_DIR / "data/working"

log = get_logger("feeding_america.ingest")

RATE_MEASURES = {"Food_Insecurity_Rate", "Child_Food_Insecurity_Rate"}
ALL_MEASURES = [
    "Food_Insecurity_Rate",
    "Child_Food_Insecurity_Rate",
    "Cost_Per_Meal",
    "Num_Food_Insecure",
    "Num_Child_Food_Insecure",
    "weighted_budget_shortfall",
]


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def read_mmg_file(orig_dir: Path, spec: dict) -> pd.DataFrame:
    """Read one MMG Excel file and extract the 6 standard measures."""
    year = spec["year"]
    path = orig_dir / spec["file"]
    sheet = spec.get("sheet", 0)
    header = spec.get("header", 0)

    df = pd.read_excel(path, sheet_name=sheet, header=header)

    col_map = {
        "FIPS": "FIPS",
        f"{year} Food Insecurity Rate": "Food_Insecurity_Rate",
        f"{year} Child food insecurity rate": "Child_Food_Insecurity_Rate",
        f"{year} Cost Per Meal": "Cost_Per_Meal",
        f"# of Food Insecure Persons in {year}": "Num_Food_Insecure",
        f"# of Food Insecure Children in {year}": "Num_Child_Food_Insecure",
        f"{year} Weighted Annual Food Budget Shortfall": "weighted_budget_shortfall",
    }

    df = df.rename(columns=col_map)
    df = df[list(col_map.values())].copy()
    df["year"] = year
    return df


def read_all_mmg(orig_dir: Path, file_specs: list[dict]) -> pd.DataFrame:
    """Read and stack all MMG county files for 2014-2019."""
    parts = []
    for spec in file_specs:
        df = read_mmg_file(orig_dir, spec)
        parts.append(df)
        log.info("Read %d rows for %d from %s", len(df), spec["year"], spec["file"])
    return pd.concat(parts, ignore_index=True)


def standardize_county(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize FIPS codes and convert rates to percentages."""
    df = df.copy()
    df["FIPS"] = df["FIPS"].astype(str)
    # Pad 4-digit FIPS with leading zero
    df["FIPS"] = df["FIPS"].apply(lambda x: x.zfill(5) if len(x) == 4 else x)

    # Rates are decimals in the Excel; multiply by 100
    df["Food_Insecurity_Rate"] = pd.to_numeric(df["Food_Insecurity_Rate"], errors="coerce") * 100
    df["Child_Food_Insecurity_Rate"] = pd.to_numeric(df["Child_Food_Insecurity_Rate"], errors="coerce") * 100
    df["Cost_Per_Meal"] = pd.to_numeric(df["Cost_Per_Meal"], errors="coerce")
    df["Num_Food_Insecure"] = pd.to_numeric(df["Num_Food_Insecure"], errors="coerce")
    df["Num_Child_Food_Insecure"] = pd.to_numeric(df["Num_Child_Food_Insecure"], errors="coerce")
    df["weighted_budget_shortfall"] = pd.to_numeric(df["weighted_budget_shortfall"], errors="coerce")

    return df


def to_long(df: pd.DataFrame, id_col: str = "FIPS") -> pd.DataFrame:
    """Melt wide county data to long format."""
    long = df.melt(
        id_vars=[id_col, "year"],
        value_vars=ALL_MEASURES,
        var_name="measure",
        value_name="value",
    )
    long = long.rename(columns={id_col: "geoid"})
    long["region_type"] = "county"
    long["moe"] = pd.NA
    return long[["geoid", "year", "measure", "value", "moe", "region_type"]]


def aggregate_health_districts(
    va_wide: pd.DataFrame, crosswalk_path: Path, acs_pop: pd.DataFrame
) -> pd.DataFrame:
    """Aggregate VA county data to health districts using ACS population."""
    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})

    # Merge county FA data with ACS population and crosswalk
    merged = va_wide.merge(
        acs_pop[["geoid", "year", "tpop", "child_pop"]],
        left_on=["FIPS", "year"],
        right_on=["geoid", "year"],
        how="left",
    ).merge(
        xwalk[["ct_geoid", "hd_geoid"]],
        left_on="FIPS",
        right_on="ct_geoid",
        how="left",
    )

    # Group by health district and year
    hd = merged.groupby(["hd_geoid", "year"]).apply(
        _agg_hd_group, include_groups=False
    ).reset_index()

    hd = hd.rename(columns={"hd_geoid": "geoid"})

    # Melt to long format
    long = hd.melt(
        id_vars=["geoid", "year"],
        value_vars=ALL_MEASURES,
        var_name="measure",
        value_name="value",
    )
    long["region_type"] = "health_district"
    long["moe"] = pd.NA
    return long[["geoid", "year", "measure", "value", "moe", "region_type"]]


def _agg_hd_group(group: pd.DataFrame) -> pd.Series:
    """Aggregate a single HD-year group."""
    tpop = group["tpop"].sum()
    child_pop = group["child_pop"].sum()

    num_fi = group["Num_Food_Insecure"].sum()
    num_cfi = group["Num_Child_Food_Insecure"].sum()
    budget = group["weighted_budget_shortfall"].sum()

    fi_rate = (num_fi / tpop * 100) if tpop > 0 else 0.0
    cfi_rate = (num_cfi / child_pop * 100) if child_pop > 0 else 0.0
    cost = (group["Cost_Per_Meal"] * group["tpop"]).sum() / tpop if tpop > 0 else 0.0

    return pd.Series({
        "Food_Insecurity_Rate": fi_rate,
        "Child_Food_Insecurity_Rate": cfi_rate,
        "Cost_Per_Meal": cost,
        "Num_Food_Insecure": num_fi,
        "Num_Child_Food_Insecure": num_cfi,
        "weighted_budget_shortfall": budget,
    })


def fetch_acs_population(config: dict) -> pd.DataFrame:
    """Fetch ACS population for VA counties (2014-2019) for HD aggregation."""
    client = CensusClient()
    years = [spec["year"] for spec in config["excel_files"]]

    df = client.get_acs_multi(
        variables=config["acs_variables"],
        years=years,
        geographies=["county"],
        states=["VA"],
        estimate_only=True,
    )

    df["child_pop"] = (
        df["male_under_5"] + df["male_5_9"] + df["male_10_14"] + df["male_15_17"]
        + df["female_under_5"] + df["female_5_9"] + df["female_10_14"] + df["female_15_17"]
    )
    return df[["geoid", "year", "tpop", "child_pop"]]


def read_tract_2020(orig_dir: Path, tract_file: str) -> pd.DataFrame:
    """Read tract-level 2020 food insecurity data."""
    df = pd.read_excel(orig_dir / tract_file, sheet_name=0)

    df = df.rename(columns={
        "TractID": "geoid",
        "percent_food_insecure_2020": "percent_food_insecure",
        "number_food_insecure_2020": "number_food_insecure",
    })
    df["geoid"] = df["geoid"].astype(str)
    df["percent_food_insecure"] = df["percent_food_insecure"] * 100
    df["year"] = 2020
    df["region_type"] = "tract"
    df["moe"] = pd.NA

    long = df.melt(
        id_vars=["geoid", "year", "region_type", "moe", "state"],
        value_vars=["percent_food_insecure", "number_food_insecure"],
        var_name="measure",
        value_name="value",
    )
    return long[["geoid", "year", "measure", "value", "moe", "region_type", "state"]]


def run() -> None:
    config = load_config()
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    ncr_counties = set(config["ncr_counties"])
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]

    # --- County data (2014-2019) ---
    log.info("Reading MMG Excel files")
    raw = read_all_mmg(ORIG_DIR, config["excel_files"])
    county = standardize_county(raw)

    # NCR county data (all 6 measures)
    ncr = county[county["FIPS"].isin(ncr_counties)]
    ncr_long = to_long(ncr)
    ncr_path = write_data(ncr_long, WORK_DIR / "ncr_ct_fa_2014_2019_food_security.csv.xz")
    log.info("Wrote %d NCR county rows to %s", len(ncr_long), ncr_path)

    # VA county data
    va = county[county["FIPS"].str[:2] == "51"]
    va_long = to_long(va)

    # VA health district aggregation
    log.info("Fetching ACS population for VA HD aggregation")
    acs_pop = fetch_acs_population(config)

    hd_long = aggregate_health_districts(va, crosswalk_path, acs_pop)
    log.info("Computed %d HD rows", len(hd_long))

    va_all = pd.concat([va_long, hd_long], ignore_index=True)
    va_all = va_all.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)
    va_path = write_data(va_all, WORK_DIR / "va_hdct_fa_2014_2019_food_security.csv.xz")
    log.info("Wrote %d VA county+HD rows to %s", len(va_all), va_path)

    # --- Tract data (2020) ---
    log.info("Reading tract 2020 data")
    tract = read_tract_2020(ORIG_DIR, config["tract_file"])

    ncr_prefixes = tuple(ncr_counties)
    ncr_tract = tract[
        tract["geoid"].str[:5].isin(ncr_counties)
        | tract["state"].isin(["MD", "DC"])
        & tract["geoid"].str[:5].isin(ncr_counties)
    ].drop(columns=["state"])

    # Actually: NCR tracts = tracts whose 5-digit county prefix is in ncr_counties
    ncr_tract = tract[tract["geoid"].str[:5].isin(ncr_counties)].drop(columns=["state"])
    va_tract = tract[tract["state"] == "VA"].drop(columns=["state"])

    ncr_tr_path = write_data(ncr_tract, WORK_DIR / "ncr_tr_fa_2020_food_insecurity.csv.xz")
    va_tr_path = write_data(va_tract, WORK_DIR / "va_tr_fa_2020_food_insecurity.csv.xz")
    log.info("Wrote %d NCR tract rows, %d VA tract rows", len(ncr_tract), len(va_tract))


if __name__ == "__main__":
    run()
