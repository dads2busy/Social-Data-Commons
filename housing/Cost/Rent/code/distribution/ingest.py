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
