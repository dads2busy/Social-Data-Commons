"""Ingest multi-year walkability index from transit stops pipeline.

Reads block-group-level walkability parquets produced by
geographies/transit_stops/code/compute_walkability.py and aggregates
to tract and county using population-weighted mean.

Produces _geo10 (original 2010 boundaries) and _geo20 (converted via crosswalk).

Configuration is read from Walkability/pipeline.yaml.
"""

import time
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
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
WALKABILITY_DIR = REPO_DIR / "geographies/transit_stops/data/walkability"

log = get_logger("walkability.ingest")

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


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def load_walkability(coverage: str) -> pd.DataFrame:
    """Load all walkability parquets for a coverage area."""
    pattern = f"{coverage.lower()}_walkability_*.parquet"
    files = sorted(WALKABILITY_DIR.glob(pattern))
    if not files:
        raise FileNotFoundError(
            f"No walkability parquets found at {WALKABILITY_DIR}/{pattern}. "
            "Run geographies/transit_stops/code/compute_walkability.py first."
        )

    dfs = [pd.read_parquet(f) for f in files]
    df = pd.concat(dfs, ignore_index=True)
    log.info("Loaded %d BG-year rows for %s from %d files", len(df), coverage.upper(), len(files))
    return df


def filter_to_profile(df: pd.DataFrame, profile_name: str) -> pd.DataFrame:
    """Filter block groups to a profile's geography."""
    profile = resolve_profile(profile_name)

    if profile.counties:
        parts = []
        for st_abbr, county_fips_list in profile.counties.items():
            st_fips = STATE_ABBR_TO_FIPS[st_abbr.upper()]
            mask = (df["geoid"].str[:2] == st_fips) & (df["geoid"].str[2:5].isin(county_fips_list))
            parts.append(df[mask])
        filtered = pd.concat(parts, ignore_index=True)
    else:
        st_fips_list = [STATE_ABBR_TO_FIPS[s.upper()] for s in profile.states]
        filtered = df[df["geoid"].str[:2].isin(st_fips_list)]

    filtered = filtered[filtered["tot_pop"] > 0].copy()
    log.info("Profile '%s': %d BG-year rows after filtering", profile_name, len(filtered))
    return filtered


def aggregate_to_levels(df: pd.DataFrame, include_bg: bool = False) -> pd.DataFrame:
    """Aggregate BG walkability to tract and county using population-weighted mean."""
    df = df.copy()
    df["tr_geoid"] = df["geoid"].str[:11]
    df["ct_geoid"] = df["geoid"].str[:5]

    def wmean(group):
        w = group["tot_pop"].values
        v = group["walkability_index"].values
        total_w = w.sum()
        if total_w == 0:
            return np.nan
        return np.average(v, weights=w)

    parts = []

    # Block group level (optional)
    if include_bg:
        bg = df[["geoid", "year", "walkability_index"]].copy()
        bg = bg.rename(columns={"walkability_index": "value"})
        bg["region_type"] = "block_group"
        parts.append(bg)

    # Tract level
    tr = df.groupby(["tr_geoid", "year"]).apply(wmean, include_groups=False).reset_index()
    tr.columns = ["geoid", "year", "value"]
    tr["region_type"] = "tract"
    parts.append(tr)

    # County level
    ct = df.groupby(["ct_geoid", "year"]).apply(wmean, include_groups=False).reset_index()
    ct.columns = ["geoid", "year", "value"]
    ct["region_type"] = "county"
    parts.append(ct)

    result = pd.concat(parts, ignore_index=True)
    result["measure"] = "walkability_index"
    result["moe"] = pd.NA
    result["value"] = result["value"].round(2)
    return result[["geoid", "year", "measure", "value", "moe", "region_type"]]


def add_geo_suffixes(df: pd.DataFrame, state_fips_list: list[str]) -> pd.DataFrame:
    """Add _geo10/_geo20 suffixes to measures.

    - _geo10: original 2010-vintage values
    - _geo20: tracts converted via crosswalk, counties unchanged

    For national coverage (many states), processes all tracts per year
    in a single call to avoid repeated downloads of the national crosswalk.
    """
    block_groups = df[df["region_type"] == "block_group"].copy()
    tracts = df[df["region_type"] == "tract"].copy()
    counties = df[df["region_type"] == "county"].copy()

    # Block groups: _geo10 only (no BG-level crosswalk)
    block_groups["measure"] = block_groups["measure"] + "_geo10"

    # Tracts: _geo10 is the original
    geo10 = tracts.copy()
    geo10["measure"] = geo10["measure"] + "_geo10"

    # Tracts: _geo20 via convert_2010_to_2020_bounds
    geo20_parts = []
    national = len(state_fips_list) > 5

    for year, year_df in tracts.groupby("year"):
        if national:
            # National: one call per year (tract crosswalk is a national file)
            converted = convert_2010_to_2020_bounds(
                year_df[["geoid", "value"]],
            )
            converted["year"] = year
            converted["measure"] = "walkability_index_geo20"
            converted["moe"] = pd.NA
            converted["region_type"] = "tract"
            geo20_parts.append(converted)
        else:
            # Regional: per state per year
            for st_fips in state_fips_list:
                st_tracts = year_df[year_df["geoid"].str[:2] == st_fips]
                if st_tracts.empty:
                    continue
                converted = convert_2010_to_2020_bounds(
                    st_tracts[["geoid", "value"]],
                    state_fips=st_fips,
                )
                converted["year"] = year
                converted["measure"] = "walkability_index_geo20"
                converted["moe"] = pd.NA
                converted["region_type"] = "tract"
                geo20_parts.append(converted)

    geo20_tracts = pd.concat(geo20_parts, ignore_index=True) if geo20_parts else pd.DataFrame()

    # Counties: _geo20 only (boundaries unchanged between censuses)
    counties["measure"] = counties["measure"] + "_geo20"

    parts = [block_groups, geo10, counties] if not block_groups.empty else [geo10, counties]
    if not geo20_tracts.empty:
        parts.append(geo20_tracts)
    return pd.concat(parts, ignore_index=True)


def run() -> list[RunResult]:
    config = load_config()
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for source_key in config["sources"]:
        # Extract coverage from key name: "va_walkability" → "va"
        coverage = source_key.split("_")[0]
        t0 = time.time()
        try:
            raw = load_walkability(coverage)

            if coverage == "us":
                # National: no profile filtering, use all BGs with population
                filtered = raw[raw["tot_pop"] > 0].copy()
                st_fips_list = sorted(filtered["geoid"].str[:2].unique().tolist())
                log.info("US national: %d BG-year rows, %d states", len(filtered), len(st_fips_list))
            else:
                filtered = filter_to_profile(raw, coverage)
                profile = resolve_profile(coverage)
                st_fips_list = [STATE_ABBR_TO_FIPS[s.upper()] for s in profile.states]

            aggregated = aggregate_to_levels(filtered, include_bg=(coverage == "us"))
            combined = add_geo_suffixes(aggregated, st_fips_list)

            years = sorted(combined["year"].unique())
            log.info("Coverage '%s': %d rows, years %s", coverage.upper(), len(combined), years)

            auto_name = build_file_name(
                df=combined, coverage_area=coverage, years=years,
                source_type="bi", title="walkability_index",
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
            log.error("Ingest failed for '%s': %s", coverage, e, exc_info=True)
            results.append(RunResult(success=False, error=str(e), duration_sec=time.time() - t0))
    return results


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
