"""Ingest EPA National Walkability Index from Smart Location Database V3.

The SLD CSV contains block-group-level data on 2010 census geographies.
This script:
1. Downloads the CSV (if not cached)
2. Filters to VA and NCR block groups with TotPop > 0
3. Reconstructs GEOIDs from component columns (STATEFP, COUNTYFP, TRACTCE, BLKGRPCE)
4. Aggregates NatWalkInd to tract and county using population-weighted mean
5. Produces _geo10 (original 2010 boundaries) and _geo20 (converted to 2020)

Note: The GEOID10/GEOID20 columns in the CSV are stored as scientific notation
and have lost precision, so we reconstruct from the component FIPS columns instead.

Configuration is read from Walkability (HOI)/pipeline.yaml.
"""

import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sdc_core.geo import convert_2010_to_2020_bounds
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.profiles import resolve_profile
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"
WORKING_DIR = TOPIC_DIR / "data/working"

log = get_logger("walkability.ingest")

SLD_URL = "https://edg.epa.gov/EPADataCommons/public/OA/EPA_SmartLocationDatabase_V3_Jan_2021_Final.csv"
SLD_FILE = "sld_v3.csv"

STATE_ABBR_TO_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
    "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
    "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
    "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55",
    "WY": "56",
}

# Year label: SLD V3 uses ACS 2015-2019 on 2010-vintage block groups
DATA_YEAR = 2019


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def download_sld(working_dir: Path) -> Path:
    """Download the SLD CSV if not already cached."""
    dest = working_dir / SLD_FILE
    if dest.exists():
        log.info("Using cached SLD file: %s", dest)
        return dest
    working_dir.mkdir(parents=True, exist_ok=True)
    log.info("Downloading SLD from %s", SLD_URL)
    urllib.request.urlretrieve(SLD_URL, dest)
    log.info("Downloaded %s", dest)
    return dest


def load_and_filter(csv_path: Path, profile_name: str) -> pd.DataFrame:
    """Load SLD CSV and filter to the given profile's block groups."""
    df = pd.read_csv(
        csv_path,
        usecols=["STATEFP", "COUNTYFP", "TRACTCE", "BLKGRPCE", "TotPop", "NatWalkInd"],
        dtype={"STATEFP": str, "COUNTYFP": str, "TRACTCE": str, "BLKGRPCE": str},
    )
    df["TotPop"] = pd.to_numeric(df["TotPop"], errors="coerce").fillna(0)
    df["NatWalkInd"] = pd.to_numeric(df["NatWalkInd"], errors="coerce")

    # Zero-pad FIPS components and reconstruct GEOIDs
    df["STATEFP"] = df["STATEFP"].str.zfill(2)
    df["COUNTYFP"] = df["COUNTYFP"].str.zfill(3)
    df["TRACTCE"] = df["TRACTCE"].str.zfill(6)
    df["BLKGRPCE"] = df["BLKGRPCE"].str.zfill(1)
    df["tr_geoid"] = df["STATEFP"] + df["COUNTYFP"] + df["TRACTCE"]
    df["ct_geoid"] = df["STATEFP"] + df["COUNTYFP"]

    profile = resolve_profile(profile_name)
    if profile.counties:
        parts = []
        for st_abbr, county_fips_list in profile.counties.items():
            st_fips = STATE_ABBR_TO_FIPS[st_abbr.upper()]
            mask = (df["STATEFP"] == st_fips) & (df["COUNTYFP"].isin(county_fips_list))
            parts.append(df[mask])
        filtered = pd.concat(parts, ignore_index=True)
    else:
        st_fips_list = [STATE_ABBR_TO_FIPS[s.upper()] for s in profile.states]
        filtered = df[df["STATEFP"].isin(st_fips_list)]

    filtered = filtered[filtered["TotPop"] > 0].copy()
    log.info("Profile '%s': %d block groups after filtering", profile_name, len(filtered))
    return filtered


def aggregate_to_levels(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate block-group NatWalkInd to tract and county using population-weighted mean."""
    def wmean(group):
        return np.average(group["NatWalkInd"], weights=group["TotPop"])

    # Tract level
    tr = df.groupby("tr_geoid").apply(wmean, include_groups=False).reset_index()
    tr.columns = ["geoid", "value"]
    tr["region_type"] = "tract"

    # County level
    ct = df.groupby("ct_geoid").apply(wmean, include_groups=False).reset_index()
    ct.columns = ["geoid", "value"]
    ct["region_type"] = "county"

    result = pd.concat([tr, ct], ignore_index=True)
    result["measure"] = "walkability_index"
    result["year"] = DATA_YEAR
    result["moe"] = pd.NA
    return result[["geoid", "year", "measure", "value", "moe", "region_type"]]


def add_geo_suffixes(df: pd.DataFrame, state_fips_list: list[str]) -> pd.DataFrame:
    """Add _geo10/_geo20 suffixes to tract measures.

    - _geo10: original 2010-vintage tract values
    - _geo20: converted to 2020 boundaries via crosswalk
    - County measures get _geo20 only (county boundaries unchanged)
    """
    tracts = df[df["region_type"] == "tract"].copy()
    counties = df[df["region_type"] == "county"].copy()

    # Tracts: _geo10 is the original
    geo10 = tracts.copy()
    geo10["measure"] = geo10["measure"] + "_geo10"

    # Tracts: _geo20 via convert_2010_to_2020_bounds, per state
    geo20_parts = []
    for st_fips in state_fips_list:
        st_tracts = tracts[tracts["geoid"].str[:2] == st_fips]
        if st_tracts.empty:
            continue
        converted = convert_2010_to_2020_bounds(
            st_tracts[["geoid", "value"]],
            state_fips=st_fips,
        )
        converted["year"] = DATA_YEAR
        converted["measure"] = "walkability_index_geo20"
        converted["moe"] = pd.NA
        converted["region_type"] = "tract"
        geo20_parts.append(converted)

    geo20_tracts = pd.concat(geo20_parts, ignore_index=True) if geo20_parts else pd.DataFrame()

    # Counties: _geo20 only (county boundaries don't change between censuses)
    counties["measure"] = counties["measure"] + "_geo20"

    parts = [geo10, counties]
    if not geo20_tracts.empty:
        parts.append(geo20_tracts)
    return pd.concat(parts, ignore_index=True)


def run() -> list[RunResult]:
    config = load_config()
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = download_sld(WORKING_DIR)

    results = []
    for profile_name in config["sources"]["epa_sld"]["profiles"]:
        t0 = time.time()
        try:
            df = load_and_filter(csv_path, profile_name)
            aggregated = aggregate_to_levels(df)

            # Get state FIPS for this profile
            profile = resolve_profile(profile_name)
            st_fips_list = [STATE_ABBR_TO_FIPS[s.upper()] for s in profile.states]

            combined = add_geo_suffixes(aggregated, st_fips_list)
            log.info("Profile '%s': %d rows", profile_name, len(combined))

            coverage = profile_name.lower()
            auto_name = build_file_name(
                df=combined, coverage_area=coverage, years=[DATA_YEAR],
                source_type="epa_sld", title="walkability_index",
            )
            out_path = write_data(
                combined, DIST_DIR / f"{auto_name}.csv.xz",
                census_standardize=False,
            )
            log.info("Wrote %d rows to %s", len(combined), out_path)
            results.append(RunResult(
                success=True, rows=len(combined),
                output_path=str(out_path), duration_sec=time.time() - t0,
            ))
        except Exception as e:
            log.error("Ingest failed for '%s': %s", profile_name, e, exc_info=True)
            results.append(RunResult(success=False, error=str(e), duration_sec=time.time() - t0))
    return results


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
