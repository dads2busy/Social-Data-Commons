"""Ingest primary care physician accessibility scores for VA and NCR.

Uses CMS Doctors and Clinicians data (primary care specialties), ACS total
population at block group level, and pre-computed BG-to-BG travel times to
compute 2SFCA, E2SFCA, and 3SFCA access scores.  Writes BG+tract+county
output to data/distribution/ (no health district aggregation — that is done
by prepare.py).
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
CENTROIDS_PATH = REPO_DIR / "geographies" / "osrm" / "bg_centroids_2020.csv"

log = get_logger("primcare.ingest")

NCR_COUNTIES = {
    "51059", "51600", "51610", "51107", "51013", "51510",
    "51683", "51685", "51153",
    "24021", "24031", "24033", "24017",
    "11001",
}

PRIMARY_CARE_SPECIALTIES = ["FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE"]

MEASURE_PREFIX = "primcare"
DATA_SOURCE = "cms"
YEAR = 2022
ACS_YEAR = 2021


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def load_cms_providers(config: dict) -> pd.DataFrame:
    """Load CMS physician data, filter to 2022 primary care, geocode, snap to BG.

    Returns DataFrame with columns: lid, bg_geoid, capacity, lat, lon
    """
    cms_path = TOPIC_DIR / config["sources"]["cms"]["data_file"]
    geo_path = TOPIC_DIR / config["sources"]["cms"]["geocoded_file"]
    specialties = config["sources"]["cms"]["specialties"]
    year = config["sources"]["cms"]["year"]

    cms = pd.read_csv(cms_path, dtype={"postalcode": str})
    geo = pd.read_csv(geo_path, dtype={"postalcode": str})

    # Filter to target year and primary care specialties
    pc = cms[(cms["year"] == year) & (cms["primary_specialty"].isin(specialties))].copy()
    log.info("CMS %d primary care rows: %d (%d unique NPIs)", year, len(pc), pc["npi"].nunique())

    # Build geocode lookup keyed by address (not NPI — NPIs can have multiple locations)
    geo_addr = (
        geo[["street", "city", "state", "postalcode", "lat", "long"]]
        .drop_duplicates(subset=["street", "city", "state", "postalcode"])
    )

    # Group CMS rows by address, count unique NPIs per location
    addr_groups = (
        pc.groupby(["address_line_1", "city", "state", "postalcode"])
        .agg(capacity=("npi", "nunique"))
        .reset_index()
    )

    # Join with geocoded addresses on address fields
    addr_groups = addr_groups.merge(
        geo_addr,
        left_on=["address_line_1", "city", "state", "postalcode"],
        right_on=["street", "city", "state", "postalcode"],
        how="left",
    )
    missing = addr_groups["lat"].isna().sum()
    if missing > 0:
        log.warning("Dropping %d addresses with missing geocodes", missing)
        addr_groups = addr_groups.dropna(subset=["lat"])
    log.info("Unique provider addresses: %d, total capacity: %d", len(addr_groups), addr_groups["capacity"].sum())

    # Snap each address to nearest block group centroid
    centroids = pd.read_csv(CENTROIDS_PATH, dtype={"geoid": str})
    bg_geoids = centroids["geoid"].values
    bg_lats = centroids["lat"].values
    bg_lons = centroids["lon"].values

    bg_assignments = []
    for _, row in addr_groups.iterrows():
        dists = _haversine_km(bg_lats, bg_lons, row["lat"], row["long"])
        bg_assignments.append(bg_geoids[np.argmin(dists)])

    providers = pd.DataFrame({
        "lid": range(len(addr_groups)),
        "bg_geoid": bg_assignments,
        "capacity": addr_groups["capacity"].values,
        "lat": addr_groups["lat"].values,
        "lon": addr_groups["long"].values,
        "provider_state": addr_groups["state"].values,
    })

    log.info("Snapped %d provider locations to block groups", len(providers))
    return providers


def run() -> list[RunResult]:
    t0 = time.time()
    results = []

    try:
        config = load_config()

        providers = load_cms_providers(config)
        log.info("Loaded %d provider locations (total capacity %d)", len(providers), providers["capacity"].sum())

        travel_times = load_travel_times()

        # Fetch BG population for VA + MD + DC (all states needed for NCR)
        census = CensusClient()
        pop_data = census.get_acs_multi(
            variables={"total_pop": "B01001_001"},
            years=[ACS_YEAR],
            geographies=["block_group"],
            states=["51", "24", "11"],
        )

        consumer_geoids = pop_data["geoid"].values
        consumer_pop = pop_data["total_pop"].values.astype(float)

        DIST_DIR.mkdir(parents=True, exist_ok=True)

        # --- VA: all Virginia block groups ---
        va_mask = np.array([g.startswith("51") for g in consumer_geoids])
        va_providers = providers[providers["bg_geoid"].str.startswith("51")]
        va_bg = run_fca_variants(
            consumer_geoids[va_mask], consumer_pop[va_mask],
            va_providers, travel_times, MEASURE_PREFIX,
        )
        va_long = aggregate_bg_to_levels(
            va_bg, MEASURE_PREFIX, YEAR, consumer_pop=consumer_pop[va_mask],
        )
        va_name = build_file_name(
            coverage_area="va",
            data_source=DATA_SOURCE,
            years=[YEAR],
            title=f"access_scores_{MEASURE_PREFIX}",
            geographies=["county", "tract", "block_group"],
        )
        va_path = write_data(va_long, DIST_DIR / f"{va_name}.csv.xz")
        log.info("Wrote VA: %s (%d rows)", va_path.name, len(va_long))
        results.append(RunResult(
            success=True, rows=len(va_long),
            output_path=str(va_path), duration_sec=time.time() - t0,
        ))

        # --- NCR: selected counties in VA/MD/DC ---
        ncr_mask = np.array([g[:5] in NCR_COUNTIES for g in consumer_geoids])
        if ncr_mask.any():
            ncr_providers = providers[providers["bg_geoid"].str[:5].isin(NCR_COUNTIES)]
            ncr_bg = run_fca_variants(
                consumer_geoids[ncr_mask], consumer_pop[ncr_mask],
                ncr_providers, travel_times, MEASURE_PREFIX,
            )
            ncr_long = aggregate_bg_to_levels(
                ncr_bg, MEASURE_PREFIX, YEAR, consumer_pop=consumer_pop[ncr_mask],
            )
            ncr_name = build_file_name(
                coverage_area="ncr",
                data_source=DATA_SOURCE,
                years=[YEAR],
                title=f"access_scores_{MEASURE_PREFIX}",
                geographies=["county", "tract", "block_group"],
            )
            ncr_path = write_data(ncr_long, DIST_DIR / f"{ncr_name}.csv.xz")
            log.info("Wrote NCR: %s (%d rows)", ncr_path.name, len(ncr_long))
            results.append(RunResult(
                success=True, rows=len(ncr_long),
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
