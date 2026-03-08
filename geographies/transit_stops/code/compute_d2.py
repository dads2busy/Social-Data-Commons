"""Compute D2A (land use entropy) and D2B (employment entropy) from LODES + ACS.

D2A_EPHHM = entropy of (households, retail, office, industrial, service, entertainment)
D2B_E5MIX = entropy of (retail, office, industrial, service, entertainment)

Uses LODES 8 WAC (Workplace Area Characteristics) for employment by NAICS sector
and ACS B11001 for household counts, both at the block group level.

Usage:
    uv run python compute_d2.py --coverage ncr --years 2017 2018 2019 2020 2021 2022 2023

Output: data/d2/{coverage}_d2_bg2020_{year}.parquet
"""

import argparse
import gzip
import urllib.request
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
from sdc_core.log import get_logger

BASE_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BASE_DIR.parents[1]
LODES_CACHE = BASE_DIR / "data/lodes_cache"
OUT_DIR = BASE_DIR / "data/d2"

log = get_logger("transit_stops.compute_d2")

LODES8_URL = "https://lehd.ces.census.gov/data/lodes/LODES8/{state}/wac/{state}_wac_S000_JT00_{year}.csv.gz"

STATE_ABBRS = {
    "ncr": {"11": "dc", "24": "md", "51": "va"},
    "va": {"51": "va"},
}

# 5-tier employment mapping from LODES CNS codes
E5_TIERS = {
    "E5_Ret": ["CNS07"],
    "E5_Off": ["CNS09", "CNS10", "CNS11", "CNS13", "CNS20"],
    "E5_Ind": ["CNS01", "CNS02", "CNS03", "CNS04", "CNS05", "CNS06", "CNS08"],
    "E5_Svc": ["CNS12", "CNS14", "CNS15", "CNS16", "CNS19"],
    "E5_Ent": ["CNS17", "CNS18"],
}


def download_lodes(state_abbr: str, year: int) -> pd.DataFrame:
    """Download and cache a LODES WAC file."""
    cache_path = LODES_CACHE / f"{state_abbr}_wac_{year}.parquet"
    if cache_path.exists():
        return pd.read_parquet(cache_path)

    url = LODES8_URL.format(state=state_abbr, year=year)
    log.info("Downloading LODES WAC: %s %d", state_abbr.upper(), year)

    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            raw = resp.read()
    except Exception as e:
        log.warning("Failed to download LODES %s %d: %s", state_abbr, year, e)
        return pd.DataFrame()

    csv_data = gzip.decompress(raw)
    cns_cols = [f"CNS{i:02d}" for i in range(1, 21)]
    use_cols = ["w_geocode", "C000"] + cns_cols

    df = pd.read_csv(
        BytesIO(csv_data),
        usecols=lambda c: c in use_cols,
        dtype={"w_geocode": str},
    )

    LODES_CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_path, index=False)
    log.info("Cached %d blocks for %s %d", len(df), state_abbr.upper(), year)
    return df


def aggregate_to_block_groups(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate block-level LODES data to block groups."""
    # Block group GEOID = first 12 chars of 15-char block geocode
    df = df.copy()
    df["geoid"] = df["w_geocode"].str[:12]

    cns_cols = [c for c in df.columns if c.startswith("CNS")]
    agg_cols = ["C000"] + cns_cols

    bg = df.groupby("geoid")[agg_cols].sum().reset_index()
    bg = bg.rename(columns={"C000": "TotEmp"})
    return bg


def compute_5tier(bg: pd.DataFrame) -> pd.DataFrame:
    """Compute 5-tier employment aggregates."""
    bg = bg.copy()
    for tier, cns_codes in E5_TIERS.items():
        cols = [c for c in cns_codes if c in bg.columns]
        bg[tier] = bg[cols].sum(axis=1)
    return bg


def entropy(shares: np.ndarray) -> np.ndarray:
    """Compute entropy: -sum(p * ln(p)) / ln(N), handling zeros.

    Args:
        shares: (n_obs, n_categories) array of proportions (rows sum to 1)

    Returns:
        (n_obs,) array of entropy values in [0, 1]
    """
    # Count non-zero categories per row
    nonzero = (shares > 0).sum(axis=1)

    # Compute -sum(p * ln(p)), treating 0*ln(0) as 0
    with np.errstate(divide="ignore", invalid="ignore"):
        log_shares = np.where(shares > 0, np.log(shares), 0.0)
    raw = -(shares * log_shares).sum(axis=1)

    # Normalize by ln(N) where N = number of non-zero categories
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(nonzero > 1, raw / np.log(nonzero), 0.0)

    return result


def compute_d2(bg: pd.DataFrame, hh: pd.DataFrame) -> pd.DataFrame:
    """Compute D2A and D2B for block groups.

    Args:
        bg: block group employment data with E5 tiers and TotEmp
        hh: block group household counts with geoid and HH columns
    """
    # Merge employment and households
    merged = bg.merge(hh, on="geoid", how="left")
    merged["HH"] = merged["HH"].fillna(0)

    tiers = ["E5_Ret", "E5_Off", "E5_Ind", "E5_Svc", "E5_Ent"]

    # --- D2B: Employment entropy (5-tier) ---
    emp_vals = merged[tiers].values.astype(float)
    tot_emp = emp_vals.sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        emp_shares = np.where(tot_emp > 0, emp_vals / tot_emp, 0.0)
    merged["D2B_E5MIX"] = entropy(emp_shares)

    # --- D2A: Employment + Household entropy (6 categories) ---
    hh_vals = merged[["HH"]].values.astype(float)
    all_vals = np.hstack([hh_vals, emp_vals])  # HH + 5 employment tiers
    tot_act = all_vals.sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        all_shares = np.where(tot_act > 0, all_vals / tot_act, 0.0)
    merged["D2A_EPHHM"] = entropy(all_shares)

    return merged[["geoid", "TotEmp", "HH", "D2A_EPHHM", "D2B_E5MIX"] + tiers]


def get_acs_households(year: int, state_fips_list: list[str]) -> pd.DataFrame:
    """Get ACS household counts by block group.

    Uses the Census API for ACS 5-year estimates, table B11001.
    """
    from sdc_core.census import CensusClient

    client = CensusClient()
    try:
        df = client.get_acs_wide(
            variables={"HH": "B11001_001"},
            geography="block_group",
            state=state_fips_list,
            year=year,
            show_progress=False,
        )
    except Exception as e:
        log.warning("Failed to get ACS HH for year %d: %s", year, e)
        return pd.DataFrame(columns=["geoid", "HH"])

    df["HH"] = pd.to_numeric(df["HH"], errors="coerce").fillna(0)
    return df[["geoid", "HH"]]


def run(coverage: str, years: list[int]):
    states = STATE_ABBRS[coverage]
    state_fips_list = list(states.keys())

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for year in years:
        log.info("=== Year %d ===", year)

        # Download and aggregate LODES
        parts = []
        for fips, abbr in states.items():
            lodes = download_lodes(abbr, year)
            if lodes.empty:
                continue
            parts.append(lodes)

        if not parts:
            log.warning("No LODES data for year %d", year)
            continue

        all_blocks = pd.concat(parts, ignore_index=True)
        bg = aggregate_to_block_groups(all_blocks)
        bg = compute_5tier(bg)
        log.info("Block groups with employment: %d", len(bg))

        # Get ACS households (use matching 5-year estimate)
        acs_year = min(year, 2023)  # ACS available through 2023
        hh = get_acs_households(acs_year, state_fips_list)
        log.info("Block groups with ACS households: %d", len(hh))

        # Compute D2A and D2B
        result = compute_d2(bg, hh)
        result["year"] = year

        out_path = OUT_DIR / f"{coverage}_d2_bg2020_{year}.parquet"
        result.to_parquet(out_path, index=False)

        log.info(
            "Year %d: D2A mean=%.3f, D2B mean=%.3f (%d block groups) → %s",
            year, result["D2A_EPHHM"].mean(), result["D2B_E5MIX"].mean(),
            len(result), out_path.name,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute D2A/D2B from LODES + ACS")
    parser.add_argument("--coverage", required=True, choices=["ncr", "va"])
    parser.add_argument("--years", type=int, nargs="+", required=True)
    args = parser.parse_args()
    run(args.coverage, args.years)
