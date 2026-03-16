"""Ingest HUD Fair Market Rents from FMR and SAFMR Excel files.

Downloads county-level FMR and ZIP-level SAFMR data for each fiscal year,
computes population-weighted county and tract averages, and writes
long-format distribution files for VA and NCR.
"""

import time
from pathlib import Path

import pandas as pd
import requests
import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data" / "distribution"
WORKING_DIR = TOPIC_DIR / "data" / "working"

log = get_logger("housing_cost.ingest")

MEASURES = ["monthly_rent_0br", "monthly_rent_1br", "monthly_rent_2br",
            "monthly_rent_3br", "monthly_rent_4br"]
RENT_COLS = ["rent_0br", "rent_1br", "rent_2br", "rent_3br", "rent_4br"]
FMR_COLS = ["fmr_0", "fmr_1", "fmr_2", "fmr_3", "fmr_4"]


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def download_file(url: str, dest: Path) -> Path:
    """Download a file if not already cached."""
    if dest.exists():
        log.info("Using cached %s", dest.name)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading %s", url)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    log.info("Saved %s (%d bytes)", dest.name, len(resp.content))
    return dest


def parse_safmr(path: Path) -> pd.DataFrame:
    """Parse SAFMR Excel → DataFrame with columns: zip, rent_0br..rent_4br.

    SAFMR files have 18 columns: ZIP code, then for each bedroom size (0-4BR)
    three columns: base SAFMR, 90% payment standard, 110% payment standard.
    We keep only the ZIP and the 5 base SAFMR columns.
    """
    df = pd.read_excel(path, engine="openpyxl")
    # First column is ZIP (may have embedded newline in header)
    zip_col = df.columns[0]
    # Columns: ZIP, HUD Area Code, HUD Area Name, then triplets of
    # (SAFMR, 90% payment, 110% payment) for each of 0BR..4BR.
    # Rent columns are at 0-indexed positions 3, 6, 9, 12, 15.
    rent_indices = [3, 6, 9, 12, 15]
    cols_to_keep = [zip_col] + [df.columns[i] for i in rent_indices]
    df = df[cols_to_keep].copy()
    df.columns = ["zip"] + RENT_COLS
    df["zip"] = df["zip"].astype(str).str.zfill(5)
    for col in RENT_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def parse_fmr(path: Path) -> pd.DataFrame:
    """Parse FMR Excel → DataFrame with columns: county_fips, fmr_0..fmr_4.

    FMR files have a 'fips' column with trailing '99999' (county FIPS + metro
    area suffix). We truncate to 5 digits for county FIPS.
    """
    df = pd.read_excel(path, engine="openpyxl")
    df["county_fips"] = df["fips"].astype(str).str[:5].str.zfill(5)
    # FMR columns: typically named fmr_0 through fmr_4
    fmr_found = [c for c in df.columns if c.startswith("fmr_")]
    if len(fmr_found) < 5:
        log.warning("Found %d fmr_* columns (expected 5), check Excel layout", len(fmr_found))
    keep = ["county_fips"] + fmr_found
    df = df[keep].copy()
    # Normalize column names to fmr_0..fmr_4
    rename = {}
    for i, c in enumerate(sorted(fmr_found)):
        rename[c] = f"fmr_{i}"
    df = df.rename(columns=rename)
    # Deduplicate: same county FIPS can appear multiple times (metro areas)
    df = df.drop_duplicates(subset="county_fips", keep="first")
    for col in FMR_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_zip_tract_crosswalk(path: Path) -> pd.DataFrame:
    """Load ZIP-to-tract crosswalk. Returns columns: zip, tract.

    The CSV has columns: zip, geoid (tract FIPS), res_ratio, bus_ratio, etc.
    Both zip and geoid are stored as integers, so zero-padding is needed.
    """
    df = pd.read_csv(path, dtype=str)
    df = df.rename(columns={"geoid": "tract"})
    df["zip"] = df["zip"].str.zfill(5)
    df["tract"] = df["tract"].str.zfill(11)
    return df[["zip", "tract"]].copy()


def load_zcta_county(path: Path) -> pd.DataFrame:
    """Load ZCTA-county relationship file. Returns columns: zcta, county_fips, pop."""
    df = pd.read_csv(path)
    df["zcta"] = df["ZCTA5"].astype(str).str.zfill(5)
    df["county_fips"] = df["GEOID"].astype(str).str.zfill(5)
    df["pop"] = pd.to_numeric(df["POPPT"], errors="coerce").fillna(0)
    return df[["zcta", "county_fips", "pop"]].copy()


def compute_county_fmr(
    safmr: pd.DataFrame,
    zcta_county: pd.DataFrame,
    county_fips_list: list[str],
    fmr_fallback: pd.DataFrame,
) -> pd.DataFrame:
    """Compute county-level FMR as population-weighted average of ZCTA SAFMRs.

    For counties with no ZCTA overlap in the SAFMR data, falls back to
    direct HUD county FMR from the FMR Excel file.

    Returns DataFrame with columns: geoid, rent_0br..rent_4br, data_method.
    """
    # Join ZCTA SAFMRs with ZCTA-county population weights
    # SAFMR zip ≈ ZCTA for this purpose
    merged = zcta_county.merge(safmr, left_on="zcta", right_on="zip", how="inner")

    rows = []
    for fips in county_fips_list:
        county_data = merged[merged["county_fips"] == fips]
        total_pop = county_data["pop"].sum()
        if total_pop > 0 and not county_data[RENT_COLS].isna().all().any():
            row = {"geoid": fips, "data_method": "observed"}
            for col in RENT_COLS:
                row[col] = (county_data[col] * county_data["pop"]).sum() / total_pop
            rows.append(row)
        else:
            # Fallback to direct HUD FMR
            fmr_row = fmr_fallback[fmr_fallback["county_fips"] == fips]
            if not fmr_row.empty:
                row = {"geoid": fips, "data_method": "observed"}
                for i, col in enumerate(RENT_COLS):
                    row[col] = fmr_row[FMR_COLS[i]].iloc[0]
                rows.append(row)
            else:
                log.warning("No FMR data for county %s", fips)

    return pd.DataFrame(rows)


def compute_tract_fmr(
    safmr: pd.DataFrame,
    zip_tract: pd.DataFrame,
    zip_pop: pd.DataFrame,
    county_fmr: pd.DataFrame,
    fmr_fallback: pd.DataFrame,
    state_fips: list[str],
    tract_geoids: list[str] | None = None,
) -> pd.DataFrame:
    """Compute tract-level FMR as population-weighted average of ZIP SAFMRs.

    Fallback chain:
    1. ZIP-weighted SAFMR average (data_method = "observed")
    2. County pop-weighted average from county_fmr (data_method = "scaled")
    3. Direct HUD county FMR from fmr_fallback (data_method = "scaled")
    """
    # Filter crosswalk to relevant states
    state_mask = zip_tract["tract"].str[:2].isin(state_fips)
    xwalk = zip_tract[state_mask].copy()

    # Join crosswalk with SAFMR and population
    merged = xwalk.merge(safmr, on="zip", how="left")
    merged = merged.merge(zip_pop, on="zip", how="left")
    merged["pop"] = merged["pop"].fillna(0)

    # Determine tract list
    if tract_geoids is not None:
        tracts = tract_geoids
    else:
        tracts = sorted(xwalk["tract"].unique())

    # Build county FMR lookup for fallback
    county_lookup = {}
    if not county_fmr.empty:
        for _, row in county_fmr.iterrows():
            county_lookup[row["geoid"]] = row

    rows = []
    for tract in tracts:
        tract_data = merged[merged["tract"] == tract]
        # Remove rows with no SAFMR data or no population
        valid = tract_data.dropna(subset=RENT_COLS)
        valid = valid[valid["pop"] > 0]
        total_pop = valid["pop"].sum()

        county = tract[:5]

        if total_pop > 0:
            # Primary: ZIP-weighted average
            row = {"geoid": tract, "data_method": "observed"}
            for col in RENT_COLS:
                row[col] = (valid[col] * valid["pop"]).sum() / total_pop
            # Check for zero values (treat as missing)
            if any(row[col] == 0 for col in RENT_COLS):
                row["data_method"] = "scaled"
                county_row = county_lookup.get(county)
                if county_row is not None:
                    for col in RENT_COLS:
                        if row[col] == 0:
                            row[col] = county_row[col]
            rows.append(row)
        elif county in county_lookup:
            # Fallback: county pop-weighted average
            county_row = county_lookup[county]
            row = {"geoid": tract, "data_method": "scaled"}
            for col in RENT_COLS:
                row[col] = county_row[col]
            rows.append(row)
        else:
            # Last resort: direct HUD county FMR
            fmr_row = fmr_fallback[fmr_fallback["county_fips"] == county]
            if not fmr_row.empty:
                row = {"geoid": tract, "data_method": "scaled"}
                for i, col in enumerate(RENT_COLS):
                    row[col] = fmr_row[FMR_COLS[i]].iloc[0]
                rows.append(row)
            else:
                log.warning("No FMR data for tract %s (county %s)", tract, county)

    return pd.DataFrame(rows)
