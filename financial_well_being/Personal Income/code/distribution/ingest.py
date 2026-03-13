"""Ingest earnings per job and compensation from BEA CAINC4 for Virginia counties."""

import os
import time
from pathlib import Path

import pandas as pd
import httpx
import yaml
from dotenv import load_dotenv
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"

load_dotenv()

log = get_logger("personal_income.ingest")

YEARS = [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]

# BEA CAINC4 line codes
LINE_CODES = {
    "tot_employment": 10,
    "wage_sal": 50,
    "wage_sup": 60,
    "prop_inc": 70,
}

# Individual FIPS codes assigned (in order) to the combined county+city rows
# that BEA aggregates together starting at row index 82 (0-indexed, after state
# total removed and sorted by GeoFips).
COMBINED_FIPS = [
    "51003", "51540", "51005", "51580", "51015", "51790", "51820", "51031", "51680", "51035",
    "51640", "51053", "51570", "51730", "51059", "51600", "51610", "51069", "51840", "51081",
    "51595", "51089", "51690", "51095", "51830", "51121", "51750", "51143", "51590", "51149",
    "51670", "51153", "51683", "51685", "51161", "51775", "51163", "51530", "51678", "51165",
    "51660", "51175", "51620", "51177", "51630", "51191", "51520", "51195", "51720", "51199",
    "51735",
]

BEA_BASE_URL = "https://apps.bea.gov/api/data/"


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def fetch_line(key: str, line_code: int, years: list[int], geo_fips: str, api_key: str) -> pd.DataFrame:
    """Fetch one BEA CAINC4 line code and return a wide DataFrame (GeoFips x year)."""
    year_str = ",".join(str(y) for y in years)
    params = (
        f"UserID={api_key}&method=GetData&datasetname=Regional"
        f"&TableName=CAINC4&LineCode={line_code}"
        f"&Year={year_str}&GeoFips={geo_fips}&ResultFormat=json"
    )
    url = f"{BEA_BASE_URL}?{params}"
    log.info("Fetching BEA line %d (%s)", line_code, key)
    resp = httpx.get(url, timeout=60)
    resp.raise_for_status()

    records = resp.json()["BEAAPI"]["Results"]["Data"]
    df = pd.DataFrame(records)

    # Coerce DataValue to numeric (strip commas, handle "(D)" suppressed values)
    df["DataValue"] = pd.to_numeric(df["DataValue"].str.replace(",", "", regex=False), errors="coerce")

    # Filter out state total and national aggregate
    df = df[~df["GeoFips"].isin(["51000", "00000"])].copy()

    # Pivot wide: one column per year
    wide = df.pivot_table(
        index=["GeoFips", "GeoName"],
        columns="TimePeriod",
        values="DataValue",
        aggfunc="first",
    ).reset_index()
    wide.columns.name = None

    return wide


def clean_and_split_geoname(wide: pd.DataFrame) -> pd.DataFrame:
    """Clean GeoName, split combined county+city rows, and assign individual FIPS."""
    df = wide.copy()

    # Remove asterisks and " VA" substrings, strip whitespace
    df["GeoName"] = df["GeoName"].str.replace("*", "", regex=False)
    df["GeoName"] = df["GeoName"].str.replace(r"\bVA\b", "", regex=True).str.strip()

    # Sort by GeoFips to match the R pipeline's ordering (state total already removed)
    df = df.sort_values("GeoFips").reset_index(drop=True)

    # Rows from index 82 onward contain combined entries (joined by "+" or ",")
    before = df.iloc[:82].copy()
    combined_block = df.iloc[82:].copy()

    # Split on "+"
    rows_plus = []
    for _, row in combined_block.iterrows():
        name = row["GeoName"]
        if "+" in name:
            parts = [p.strip() for p in name.split("+")]
            for part in parts:
                new_row = row.copy()
                new_row["GeoName"] = part
                rows_plus.append(new_row)
        else:
            rows_plus.append(row)

    after_plus = pd.DataFrame(rows_plus).reset_index(drop=True)

    # Split on "," for specific remaining combined entries
    rows_comma = []
    for _, row in after_plus.iterrows():
        name = row["GeoName"]
        if "," in name:
            parts = [p.strip() for p in name.split(",")]
            for part in parts:
                new_row = row.copy()
                new_row["GeoName"] = part
                rows_comma.append(new_row)
        else:
            rows_comma.append(row)

    after_comma = pd.DataFrame(rows_comma).reset_index(drop=True)

    # Assign COMBINED_FIPS in order to all rows in the combined block
    if len(after_comma) != len(COMBINED_FIPS):
        log.warning(
            "Expected %d combined rows after splitting, got %d",
            len(COMBINED_FIPS),
            len(after_comma),
        )
    for i, fips in enumerate(COMBINED_FIPS):
        if i < len(after_comma):
            after_comma.at[i, "GeoFips"] = fips

    result = pd.concat([before, after_comma], ignore_index=True)
    return result


def compute_county_measures(
    tot_emp: pd.DataFrame,
    wage_sal: pd.DataFrame,
    wage_sup: pd.DataFrame,
    prop_inc: pd.DataFrame,
    years: list[int],
) -> pd.DataFrame:
    """Join the four wide DataFrames and compute the three measures in long format."""
    year_cols = [str(y) for y in years]

    # Use tot_emp as the base frame (GeoFips column is the key)
    base = tot_emp[["GeoFips"]].copy()

    rows = []
    for fips in base["GeoFips"]:
        te_row = tot_emp[tot_emp["GeoFips"] == fips]
        ws_row = wage_sal[wage_sal["GeoFips"] == fips]
        wsu_row = wage_sup[wage_sup["GeoFips"] == fips]
        pi_row = prop_inc[prop_inc["GeoFips"] == fips]

        if te_row.empty or ws_row.empty or wsu_row.empty or pi_row.empty:
            log.debug("Skipping GeoFips %s — missing in one or more series", fips)
            continue

        for yr in year_cols:
            te = te_row[yr].values[0] if yr in te_row.columns else None
            ws = ws_row[yr].values[0] if yr in ws_row.columns else None
            wsu = wsu_row[yr].values[0] if yr in wsu_row.columns else None
            pi = pi_row[yr].values[0] if yr in pi_row.columns else None

            # tot_compensation in dollars (source values are in thousands)
            if pd.notna(ws) and pd.notna(wsu) and pd.notna(pi):
                tot_comp = (ws + wsu + pi) * 1000
            else:
                tot_comp = float("nan")

            # earnings_per_job in dollars
            if pd.notna(te) and te != 0 and pd.notna(tot_comp):
                epj = (ws + wsu + pi) / te * 1000
            else:
                epj = float("nan")

            rows.append({"geoid": fips, "year": int(yr), "measure": "tot_compensation", "value": tot_comp, "moe": pd.NA, "region_type": "county"})
            rows.append({"geoid": fips, "year": int(yr), "measure": "tot_employment", "value": te, "moe": pd.NA, "region_type": "county"})
            rows.append({"geoid": fips, "year": int(yr), "measure": "earnings_per_job", "value": epj, "moe": pd.NA, "region_type": "county"})

    return pd.DataFrame(rows)


def run() -> list[RunResult]:
    t0 = time.time()
    config = load_config()
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("BEA_API_KEY", "")
    if not api_key:
        log.error("BEA_API_KEY environment variable is not set")
        return [RunResult(success=False, error="BEA_API_KEY not set", duration_sec=time.time() - t0)]

    src = config["sources"]["va"]
    years = src["years"]
    geo_fips = src["geo_fips"]
    line_codes = src["line_codes"]

    try:
        # Fetch all four line codes
        wide_frames: dict[str, pd.DataFrame] = {}
        for name, code in line_codes.items():
            wide_frames[name] = fetch_line(name, code, years, geo_fips, api_key)

        # Split combined Virginia county+city entries using tot_employment as the reference
        # (all four frames have the same GeoFips structure)
        log.info("Splitting combined Virginia county+city rows")
        split_frames: dict[str, pd.DataFrame] = {}
        for name, df in wide_frames.items():
            split_frames[name] = clean_and_split_geoname(df)

        # Compute county-level measures in long format
        log.info("Computing county-level measures")
        county_long = compute_county_measures(
            tot_emp=split_frames["tot_employment"],
            wage_sal=split_frames["wage_sal"],
            wage_sup=split_frames["wage_sup"],
            prop_inc=split_frames["prop_inc"],
            years=years,
        )

        if county_long.empty:
            return [RunResult(success=False, error="No county data computed", duration_sec=time.time() - t0)]

        # Write county-only output (HD aggregation happens in prepare.py)
        county_long = county_long.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

        filename = (
            build_file_name(
                coverage_area="va",
                data_source="bea",
                years=years,
                title="personal_income",
                geographies=["county"],
            )
            + ".csv.xz"
        )
        out_path = write_data(county_long, DIST_DIR / filename, census_standardize=False)
        log.info("Wrote %d rows to %s", len(county_long), out_path)

        return [RunResult(
            success=True,
            rows=len(county_long),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )]

    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        return [RunResult(success=False, error=str(e), duration_sec=time.time() - t0)]


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
