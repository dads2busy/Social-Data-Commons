"""Ingest simulated 2026 VA EV charging-demand events, attach county FIPS,
produce per-location and per-county-hour outputs.

Reads `data/original/charging_events_va_2026.csv`, derives a unique-location
spatial join to VA county FIPS (joining ~65k points once rather than 376k
event rows), then writes:

  data/distribution/{point_csv}    per-location summary, energy point schema
  data/distribution/{county_csv}   per-(county, hour-of-day) long-format

Run: uv run python energy/EVChargingDemand/code/distribution/ingest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml
from sdc_core.io import write_data, write_point_data
from sdc_core.log import get_logger

THIS_DIR = Path(__file__).resolve().parent
TOPIC_DIR = THIS_DIR.parents[1]
REPO_DIR = TOPIC_DIR.parents[1]

sys.path.insert(0, str(THIS_DIR))
from transforms import aggregate_to_county_hour, aggregate_to_locations

log = get_logger("ev_charging_demand.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def spatial_join_unique_locations(events: pd.DataFrame, counties_geojson: Path) -> pd.DataFrame:
    """Compute a per-unique-location geoid via sjoin, then merge back onto events.

    Avoids the cost of joining all 376k event rows directly.
    Returns the original events DataFrame with a new `geoid` column.
    Events whose location falls outside any VA county polygon are dropped.
    """
    counties = gpd.read_file(counties_geojson)[["geoid", "geometry"]]

    locations = (
        events[["charging_station_id", "latitude", "longitude"]]
        .drop_duplicates(subset=["charging_station_id"])
        .reset_index(drop=True)
    )

    points = gpd.GeoDataFrame(
        locations,
        geometry=gpd.points_from_xy(locations["longitude"], locations["latitude"]),
        crs=counties.crs,
    )

    joined = gpd.sjoin(points, counties, how="left", predicate="intersects")

    dropped = joined["geoid"].isna().sum()
    if dropped:
        log.warning("%d locations fell outside any VA county polygon and were dropped", dropped)
    joined = joined.dropna(subset=["geoid"])

    boundary_dups = joined.duplicated(subset=["charging_station_id"]).sum()
    if boundary_dups:
        log.warning("%d locations matched multiple county polygons (boundary); keeping first", boundary_dups)
    joined = joined.drop_duplicates(subset=["charging_station_id"], keep="first")

    location_to_geoid = pd.DataFrame(joined[["charging_station_id", "geoid"]])

    return events.merge(location_to_geoid, on="charging_station_id", how="inner")


def run() -> None:
    config = load_config()
    source = config["source"]
    geos = config["geographies"]
    out = config["output"]

    input_path = TOPIC_DIR / source["input_file"]
    counties_path = REPO_DIR / geos["va_counties"]
    point_csv = TOPIC_DIR / out["point_csv"]
    county_csv = TOPIC_DIR / out["county_csv"]

    log.info("Reading %s", input_path)
    events = pd.read_csv(input_path)
    log.info("Loaded %d event rows", len(events))

    log.info("Spatial join (unique-location optimization) with %s", counties_path)
    enriched = spatial_join_unique_locations(events, counties_path)
    log.info("Retained %d event rows after county sjoin", len(enriched))

    log.info("Building per-location summary (point schema)")
    point_rows = aggregate_to_locations(enriched, snapshot_year=source["scenario_year"])
    log.info("Produced %d unique-location rows", len(point_rows))

    log.info("Writing point CSV → %s", point_csv)
    point_csv.parent.mkdir(parents=True, exist_ok=True)
    write_point_data(point_rows, point_csv)

    log.info("Aggregating to (county, hour-of-day) long-format")
    county_rows = aggregate_to_county_hour(
        enriched,
        scenario=source["scenario"],
        scenario_year=source["scenario_year"],
    )
    log.info("Produced %d (county, hour, measure) rows", len(county_rows))

    log.info("Writing county CSV → %s", county_csv)
    county_csv.parent.mkdir(parents=True, exist_ok=True)
    write_data(county_rows, county_csv, standardize=False, census_standardize=False)

    log.info("Done.")


if __name__ == "__main__":
    run()
