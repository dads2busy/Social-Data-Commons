"""Ingest OB-GYN physician accessibility scores for VA and NCR.

Uses CMS Doctors and Clinicians data (OB-GYN specialty), ACS female
population age 15+ at block group level, and pre-computed BG-to-BG travel
times to compute 2SFCA, E2SFCA, and 3SFCA access scores.  Loops over all
available years (2017-2025) and writes combined multi-year BG+tract+county
output to data/distribution/ (no health district aggregation -- that is
done by prepare.py).
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sdc_core.census import CensusClient
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

HCS_DIR = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(HCS_DIR / "code"))
from compute_service_access import (
    _haversine_km,
    aggregate_bg_to_levels,
    load_travel_times,
    run_fca_variants,
)

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = Path(__file__).resolve().parents[7]
DIST_DIR = TOPIC_DIR / "data" / "distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"
ORIGINAL_DIR = TOPIC_DIR / "data" / "original"
CENTROIDS_PATH = REPO_DIR / "geographies" / "osrm" / "bg_centroids_2020.csv"

log = get_logger("obgyn.ingest")

NCR_COUNTIES = {
    "51059", "51600", "51610", "51107", "51013", "51510",
    "51683", "51685", "51153",
    "24021", "24031", "24033", "24017",
    "11001",
}

OBGYN_SPECIALTIES = ["OBSTETRICS/GYNECOLOGY"]

MEASURE_PREFIX = "obgyn"
DATA_SOURCE = "cms"

# ACS 5-year latest available year
ACS_MAX_YEAR = 2023

# ACS B01001 female age 15+ variables (B01001_030 through B01001_049)
POP_VARIABLES = {f"f_{i}": f"B01001_{i:03d}" for i in range(30, 50)}


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def load_geocoded_addresses(config: dict) -> pd.DataFrame:
    """Load geocoded address lookup, deduped by address."""
    geo_path = TOPIC_DIR / config["sources"]["cms"]["geocoded_file"]
    if not geo_path.exists():
        raise FileNotFoundError(f"No geocoded file found at {geo_path}")
    geo = pd.read_csv(geo_path, dtype={"postalcode": str})
    geo_addr = (
        geo[["street", "city", "state", "postalcode", "lat", "long"]]
        .drop_duplicates(subset=["street", "city", "state", "postalcode"])
    )
    return geo_addr


def load_centroids() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load BG centroids, return (geoids, lats, lons) arrays."""
    centroids = pd.read_csv(CENTROIDS_PATH, dtype={"geoid": str})
    return centroids["geoid"].values, centroids["lat"].values, centroids["lon"].values


def snap_to_block_groups(
    addr_groups: pd.DataFrame,
    bg_geoids: np.ndarray,
    bg_lats: np.ndarray,
    bg_lons: np.ndarray,
) -> pd.DataFrame:
    """Snap provider addresses to nearest block group centroid."""
    bg_assignments = []
    for _, row in addr_groups.iterrows():
        dists = _haversine_km(bg_lats, bg_lons, row["lat"], row["long"])
        bg_assignments.append(bg_geoids[np.argmin(dists)])

    return pd.DataFrame({
        "lid": range(len(addr_groups)),
        "bg_geoid": bg_assignments,
        "capacity": addr_groups["capacity"].values,
        "lat": addr_groups["lat"].values,
        "lon": addr_groups["long"].values,
        "provider_state": addr_groups["state"].values,
    })


def load_providers_for_year(
    year: int,
    specialties: list[str],
    geo_addr: pd.DataFrame,
    bg_geoids: np.ndarray,
    bg_lats: np.ndarray,
    bg_lons: np.ndarray,
) -> pd.DataFrame | None:
    """Load CMS data for one year, join geocodes, snap to BGs.

    Returns provider DataFrame or None if year file is missing.
    """
    cms_path = ORIGINAL_DIR / f"vadcmd_cms_{year}_obgyn.csv"
    if not cms_path.exists():
        log.warning("No CMS file for %d: %s", year, cms_path)
        return None

    cms = pd.read_csv(cms_path, dtype={"postalcode": str})

    # Filter to OB-GYN specialty (any of primary, secondary_1, secondary_2)
    spec_mask = (
        cms["primary_specialty"].isin(specialties)
        | cms["secondary_specialty_1"].fillna("").isin(specialties)
        | cms["secondary_specialty_2"].fillna("").isin(specialties)
    )
    pc = cms[spec_mask].copy()
    log.info("CMS %d OB-GYN rows: %d (%d unique NPIs)", year, len(pc), pc["npi"].nunique())

    # Group by address, count unique NPIs per location
    addr_groups = (
        pc.groupby(["address_line_1", "city", "state", "postalcode"])
        .agg(capacity=("npi", "nunique"))
        .reset_index()
    )

    # Join with geocoded addresses
    addr_groups = addr_groups.merge(
        geo_addr,
        left_on=["address_line_1", "city", "state", "postalcode"],
        right_on=["street", "city", "state", "postalcode"],
        how="left",
    )
    missing = addr_groups["lat"].isna().sum()
    if missing > 0:
        log.warning("Year %d: dropping %d addresses with missing geocodes", year, missing)
        addr_groups = addr_groups.dropna(subset=["lat"])
    log.info(
        "Year %d: %d unique addresses, total capacity %d",
        year, len(addr_groups), addr_groups["capacity"].sum(),
    )

    if addr_groups.empty:
        log.warning("Year %d: no geocoded addresses -- skipping", year)
        return None

    providers = snap_to_block_groups(addr_groups, bg_geoids, bg_lats, bg_lons)
    log.info("Year %d: snapped %d provider locations to block groups", year, len(providers))
    return providers


def run() -> list[RunResult]:
    t0 = time.time()
    results = []

    try:
        config = load_config()
        specialties = config["sources"]["cms"]["specialties"]
        years = config["output"]["years"]

        geo_addr = load_geocoded_addresses(config)
        bg_geoids, bg_lats, bg_lons = load_centroids()
        travel_times = load_travel_times()
        census = CensusClient()

        DIST_DIR.mkdir(parents=True, exist_ok=True)

        va_year_frames = []
        ncr_year_frames = []

        for year in years:
            yt0 = time.time()
            log.info("=== Processing year %d ===", year)

            providers = load_providers_for_year(
                year, specialties, geo_addr, bg_geoids, bg_lats, bg_lons,
            )
            if providers is None:
                continue

            # ACS population year: use cms_year - 1, capped at ACS_MAX_YEAR
            acs_year = min(year - 1, ACS_MAX_YEAR)
            log.info("Year %d: using ACS year %d for population", year, acs_year)

            pop_data = census.get_acs_multi(
                variables=POP_VARIABLES,
                years=[acs_year],
                geographies=["block_group"],
                states=["51", "24", "11"],
            )

            # Sum all female age 15+ columns for the target population
            age_cols = [c for c in pop_data.columns if c.startswith("f_")]
            pop_data["target_pop"] = pop_data[age_cols].sum(axis=1)

            consumer_geoids = pop_data["geoid"].values
            consumer_pop = pop_data["target_pop"].values.astype(float)

            # --- VA ---
            va_mask = np.array([g.startswith("51") for g in consumer_geoids])
            va_providers = providers[providers["bg_geoid"].str.startswith("51")]
            if len(va_providers) > 0:
                va_bg = run_fca_variants(
                    consumer_geoids[va_mask], consumer_pop[va_mask],
                    va_providers, travel_times, MEASURE_PREFIX,
                )
                va_long = aggregate_bg_to_levels(
                    va_bg, MEASURE_PREFIX, year, consumer_pop=consumer_pop[va_mask],
                )
                va_year_frames.append(va_long)
                log.info("Year %d VA: %d rows", year, len(va_long))

            # --- NCR ---
            ncr_mask = np.array([g[:5] in NCR_COUNTIES for g in consumer_geoids])
            if ncr_mask.any():
                ncr_providers = providers[providers["bg_geoid"].str[:5].isin(NCR_COUNTIES)]
                if len(ncr_providers) > 0:
                    ncr_bg = run_fca_variants(
                        consumer_geoids[ncr_mask], consumer_pop[ncr_mask],
                        ncr_providers, travel_times, MEASURE_PREFIX,
                    )
                    ncr_long = aggregate_bg_to_levels(
                        ncr_bg, MEASURE_PREFIX, year, consumer_pop=consumer_pop[ncr_mask],
                    )
                    ncr_year_frames.append(ncr_long)
                    log.info("Year %d NCR: %d rows", year, len(ncr_long))

            log.info("Year %d done in %.1fs", year, time.time() - yt0)

        # Combine all years and write output
        if va_year_frames:
            va_all = pd.concat(va_year_frames, ignore_index=True)
            va_name = build_file_name(
                coverage_area="va",
                data_source=DATA_SOURCE,
                years=years,
                title=f"access_scores_{MEASURE_PREFIX}",
                geographies=["county", "tract", "block_group"],
            )
            va_path = write_data(va_all, DIST_DIR / f"{va_name}.csv.xz",
                                census_standardize=True, measure_info=MEASURE_INFO,
                                vintage_cutoff_year=2021)
            log.info("Wrote VA: %s (%d rows)", va_path.name, len(va_all))
            results.append(RunResult(
                success=True, rows=len(va_all),
                output_path=str(va_path), duration_sec=time.time() - t0,
            ))

        if ncr_year_frames:
            ncr_all = pd.concat(ncr_year_frames, ignore_index=True)
            ncr_name = build_file_name(
                coverage_area="ncr",
                data_source=DATA_SOURCE,
                years=years,
                title=f"access_scores_{MEASURE_PREFIX}",
                geographies=["county", "tract", "block_group"],
            )
            ncr_path = write_data(ncr_all, DIST_DIR / f"{ncr_name}.csv.xz",
                                census_standardize=True, measure_info=MEASURE_INFO,
                                vintage_cutoff_year=2021)
            log.info("Wrote NCR: %s (%d rows)", ncr_path.name, len(ncr_all))
            results.append(RunResult(
                success=True, rows=len(ncr_all),
                output_path=str(ncr_path), duration_sec=time.time() - t0,
            ))

    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        results.append(RunResult(success=False, error=str(e), duration_sec=time.time() - t0))

    return results


if __name__ == "__main__":
    results = run()
    for r in results:
        if r.success:
            log.info("OK: %d rows -> %s", r.rows, r.output_path)
        else:
            log.error("FAIL: %s", r.error)
    if any(not r.success for r in results):
        raise SystemExit(1)
