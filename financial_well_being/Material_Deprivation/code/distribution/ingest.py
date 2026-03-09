"""Ingest Townsend Material Deprivation Index from ACS.

Fetches multiple ACS tables (B23025, B25014, B25044, S2502) for each source
defined in pipeline.yaml. For VA, aggregates county raw counts to health
districts. Then computes the Townsend index (z-score-based normalization of
4 deprivation indicators) at all levels.
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sdc_core.census import CensusClient
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.profiles import resolve_profile, resolve_states
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"

B_VARIABLES = {
    "adult_pop": "B23025_002",
    "unemployed": "B23025_005",
    "occupancy_all": "B25014_001",
    "occupant_1": "B25014_005",
    "occupant_2": "B25014_006",
    "occupant_3": "B25014_007",
    "occupant_4": "B25014_011",
    "occupant_5": "B25014_012",
    "occupant_6": "B25014_013",
    "households_total": "B25044_001",
    "hh_owner_no_veh": "B25044_003",
    "hh_renter_no_veh": "B25044_010",
}

RAW_COUNT_COLS = list(B_VARIABLES.keys()) + ["all_units", "rent_units"]

log = get_logger("material_deprivation.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def _s2502_vars(year: int) -> dict[str, str]:
    """Return S2502 variable mapping for a given year."""
    rent_var = "S2502_C03_001" if year <= 2016 else "S2502_C05_001"
    return {"all_units": "S2502_C01_001", "rent_units": rent_var}


def fetch_wide(
    client: CensusClient,
    years: list[int],
    geos: list[str],
    states: list[str],
    cache_dir: Path | None = None,
) -> pd.DataFrame:
    """Fetch B-table and S-table ACS variables for all years and geographies."""
    all_frames: list[pd.DataFrame] = []

    for year in years:
        s_vars = _s2502_vars(year)
        for geo in geos:
            log.info("Fetching B-tables for year=%d geo=%s states=%s", year, geo, states)
            try:
                b_df = client.get_acs_wide(
                    variables=B_VARIABLES,
                    geography=geo,
                    state=states,
                    year=year,
                    estimate_only=True,
                    table_type="detail",
                    cache_dir=cache_dir,
                )
            except Exception as exc:
                log.warning("B-table fetch failed year=%d geo=%s: %s", year, geo, exc)
                continue

            log.info("Fetching S2502 for year=%d geo=%s states=%s", year, geo, states)
            try:
                s_df = client.get_acs_wide(
                    variables=s_vars,
                    geography=geo,
                    state=states,
                    year=year,
                    estimate_only=True,
                    table_type="subject",
                    cache_dir=cache_dir,
                )
            except Exception as exc:
                log.warning("S-table fetch failed year=%d geo=%s: %s", year, geo, exc)
                continue

            if b_df.empty or s_df.empty:
                log.warning("Empty fetch result year=%d geo=%s — skipping", year, geo)
                continue

            merge_keys = ["geoid", "NAME", "year", "region_type"]
            combined = pd.merge(
                b_df,
                s_df[["geoid", "NAME", "year", "region_type", "all_units", "rent_units"]],
                on=merge_keys,
                how="inner",
            )

            all_frames.append(combined)
            time.sleep(0.1)

    if not all_frames:
        return pd.DataFrame()

    return pd.concat(all_frames, ignore_index=True)


def aggregate_to_hd(counties: pd.DataFrame, crosswalk_path: Path) -> pd.DataFrame:
    """Aggregate county raw counts to health districts via crosswalk."""
    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})

    merged = counties.merge(xwalk, left_on="geoid", right_on="ct_geoid", how="inner")

    hd_frames: list[pd.DataFrame] = []
    for year, group in merged.groupby("year"):
        hd_agg = (
            group.groupby("hd_geoid")[RAW_COUNT_COLS]
            .sum()
            .reset_index()
            .rename(columns={"hd_geoid": "geoid"})
        )
        hd_agg["year"] = year
        hd_agg["region_type"] = "health_district"
        hd_frames.append(hd_agg)

    if not hd_frames:
        return pd.DataFrame(columns=["geoid", "year", "region_type"] + RAW_COUNT_COLS)

    return pd.concat(hd_frames, ignore_index=True)


def _zscore_within_groups(df: pd.DataFrame, col: str, groups: list[str]) -> pd.Series:
    """Z-score a column within (year, region_type) groups."""
    return df.groupby(groups)[col].transform(
        lambda x: (x - x.mean()) / x.std(ddof=1) if x.std(ddof=1) != 0 else 0.0
    )


def _minmax_within_groups(df: pd.DataFrame, col: str, groups: list[str]) -> pd.Series:
    """Min-max rescale a column to [0, 1] within (year, region_type) groups."""
    return df.groupby(groups)[col].transform(
        lambda x: (x - x.min()) / (x.max() - x.min()) if (x.max() - x.min()) != 0 else 0.0
    )


def compute_townsend(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the Townsend Material Deprivation Index.

    Steps:
    1. Compute 4 raw indicators (with log transforms where specified).
    2. Z-score each indicator within (year, region_type).
    3. Sum the 4 z-scores -> townsend_sum.
    4. Z-score townsend_sum within (year, region_type).
    5. Min-max rescale the final z-score to [0, 1] within (year, region_type).
    6. Return long format with measure = "material_deprivation_indicator".
    """
    work = df.copy()
    groups = ["year", "region_type"]

    # --- 4 raw indicators ---

    # Unemployment rate: unemployed / adult_pop, then log(x + 1)
    unemp_raw = work["unemployed"] / work["adult_pop"].where(work["adult_pop"] > 0, np.nan)
    unemp_raw = unemp_raw.fillna(0.0)
    work["ind_unemp"] = np.log(unemp_raw + 1)

    # Non-car ownership: (hh_owner_no_veh + hh_renter_no_veh) / households_total
    noncar_raw = (work["hh_owner_no_veh"] + work["hh_renter_no_veh"]) / work["households_total"].where(work["households_total"] > 0, np.nan)
    work["ind_noncar"] = noncar_raw.fillna(0.0)

    # Non-home ownership: rent_units / all_units
    nonhome_raw = work["rent_units"] / work["all_units"].where(work["all_units"] > 0, np.nan)
    work["ind_nonhome"] = nonhome_raw.fillna(0.0)

    # Overcrowding: sum of occupant_1..6 / occupancy_all, then log(1 + x)
    overcrowd_num = (
        work["occupant_1"] + work["occupant_2"] + work["occupant_3"]
        + work["occupant_4"] + work["occupant_5"] + work["occupant_6"]
    )
    overcrowd_raw = overcrowd_num / work["occupancy_all"].where(work["occupancy_all"] > 0, np.nan)
    overcrowd_raw = overcrowd_raw.fillna(0.0)
    work["ind_overcrowd"] = np.log(1 + overcrowd_raw)

    # --- Z-score each indicator within (year, region_type) ---
    indicators = ["ind_unemp", "ind_noncar", "ind_nonhome", "ind_overcrowd"]
    for ind in indicators:
        work[f"z_{ind}"] = _zscore_within_groups(work, ind, groups)

    # --- Sum z-scores ---
    work["townsend_sum"] = (
        work["z_ind_unemp"]
        + work["z_ind_noncar"]
        + work["z_ind_nonhome"]
        + work["z_ind_overcrowd"]
    )

    # --- Z-score the sum within (year, region_type) ---
    work["townsend_z"] = _zscore_within_groups(work, "townsend_sum", groups)

    # --- Min-max rescale to [0, 1] within (year, region_type) ---
    work["townsend_final"] = _minmax_within_groups(work, "townsend_z", groups)

    # --- Build long-format output ---
    out = work[["geoid", "year", "region_type"]].copy()
    out["measure"] = "material_deprivation_indicator"
    out["value"] = work["townsend_final"].round(4)
    out["moe"] = pd.NA

    return out.reset_index(drop=True)


def run_source(
    name: str,
    src: dict,
    config: dict,
    client: CensusClient,
) -> RunResult:
    """Ingest one source (VA or NCR)."""
    t0 = time.time()
    try:
        years = src["years"]
        geos = src["geographies"]

        # Resolve states from profile or explicit list
        if src.get("profile"):
            prof = resolve_profile(src["profile"])
            states = prof.states
        else:
            states = src.get("states", ["VA"])

        cache_dir = TOPIC_DIR / "data/working/acs_cache"
        log.info("Ingesting source '%s' (states=%s)", name, states)
        raw = fetch_wide(client, years, geos, states, cache_dir=cache_dir)

        if raw.empty:
            return RunResult(
                success=False,
                error=f"No data fetched for source '{name}'",
                duration_sec=time.time() - t0,
            )

        # Separate tracts (11-digit) and counties (5-digit)
        tract_rows = raw[raw["geoid"].str.len() == 11].copy()
        county_rows = raw[raw["geoid"].str.len() == 5].copy()

        frames = [tract_rows, county_rows]
        level_names = ["county", "tract"]

        # Only aggregate to health districts for VA source
        if name == "va" and "va_county_to_hd" in config.get("crosswalks", {}):
            crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
            log.info("Aggregating %d county rows to health districts", len(county_rows))
            hd_rows = aggregate_to_hd(county_rows, crosswalk_path)
            frames.append(hd_rows)
            level_names = ["health_district", "county", "tract"]

        log.info(
            "Combining: %d tracts + %d counties%s",
            len(tract_rows),
            len(county_rows),
            f" + {len(frames[-1]) if len(frames) > 2 else 0} health districts"
            if len(frames) > 2 else "",
        )
        combined = pd.concat(frames, ignore_index=True)

        log.info("Computing Townsend index on %d rows for '%s'", len(combined), name)
        result = compute_townsend(combined)

        src_states = resolve_states(src)
        filename = (
            build_file_name(
                df=result,
                states=src_states,
                years=years,
                source_type=src.get("type"),
                title="material_deprivation",
            )
            + ".csv.xz"
        )

        out_path = write_data(result, DIST_DIR / filename, census_standardize=True)
        log.info("Wrote %d rows to %s", len(result), out_path)

        return RunResult(
            success=True,
            rows=len(result),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )

    except Exception as exc:
        log.error("Ingest failed for source '%s': %s", name, exc, exc_info=True)
        return RunResult(success=False, error=str(exc), duration_sec=time.time() - t0)


def run() -> list[RunResult]:
    config = load_config()
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    client = CensusClient()

    results = []
    for name, src in config["sources"].items():
        results.append(run_source(name, src, config, client))
    return results


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
