"""Ingest Townsend Material Deprivation Index raw counts from ACS.

Fetches multiple ACS tables (B23025, B25014, B25044, S2502) for each source
defined in pipeline.yaml. Writes county+tract raw counts to data/distribution/.
Health district aggregation and Townsend index computation happen in prepare.py.
"""

import time
from pathlib import Path

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
WORKING_DIR = TOPIC_DIR / "data/working"

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


def run_source(
    name: str,
    src: dict,
    config: dict,
    client: CensusClient,
) -> RunResult:
    """Ingest one source (VA or NCR). Writes county+tract raw counts only."""
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

        # Keep only county+tract rows (no HD aggregation — that's done in prepare.py)
        tract_rows = raw[raw["geoid"].str.len() == 11].copy()
        county_rows = raw[raw["geoid"].str.len() == 5].copy()
        combined = pd.concat([tract_rows, county_rows], ignore_index=True)

        log.info(
            "Combined: %d tracts + %d counties for '%s'",
            len(tract_rows),
            len(county_rows),
            name,
        )

        # Write raw counts (wide format) — Townsend computation happens in prepare.py
        # Keep only the columns needed: geoid, year, region_type, and raw count columns
        keep_cols = ["geoid", "year", "region_type"] + RAW_COUNT_COLS
        result = combined[keep_cols].copy()

        src_states = resolve_states(src)
        filename = (
            build_file_name(
                df=result,
                states=src_states,
                years=years,
                source_type=src.get("type"),
                title="material_deprivation_raw",
            )
            + ".csv.xz"
        )

        WORKING_DIR.mkdir(parents=True, exist_ok=True)
        out_path = write_data(result, WORKING_DIR / filename, standardize=False, census_standardize=False)
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
