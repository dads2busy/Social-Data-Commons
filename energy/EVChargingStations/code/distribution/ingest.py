"""Ingest the simulated VA EV charging-station inventory.

Reads `data/original/va_charging_stations_30.csv`, assigns county FIPS via
spatial join with the VA counties GeoJSON, expands each station into one
row per non-zero charger level, and writes:

  data/distribution/{point_csv}    point-schema rows (one per station-level)
  data/distribution/{county_csv}   long-format county aggregates

Run: uv run python energy/EVChargingStations/code/distribution/ingest.py
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

# Make transforms importable when running as a script
sys.path.insert(0, str(THIS_DIR))
from transforms import aggregate_to_counties, expand_multi_type_rows

log = get_logger("ev_charging_stations.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def spatial_join_counties(stations: pd.DataFrame, counties_geojson: Path) -> pd.DataFrame:
    """Assign 5-digit county FIPS (`geoid`) to each station via point-in-polygon."""
    counties = gpd.read_file(counties_geojson)[["geoid", "geometry"]]
    points = gpd.GeoDataFrame(
        stations,
        geometry=gpd.points_from_xy(stations["longitude"], stations["latitude"]),
        crs=counties.crs,
    )
    joined = gpd.sjoin(points, counties, how="left", predicate="intersects")

    dropped = joined["geoid"].isna().sum()
    if dropped:
        log.warning("%d stations fell outside any VA county polygon and were dropped", dropped)
    joined = joined.dropna(subset=["geoid"])

    return pd.DataFrame(joined.drop(columns=["geometry", "index_right"]))


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
    stations = pd.read_csv(input_path)
    log.info("Loaded %d source stations", len(stations))

    log.info("Spatial join with %s", counties_path)
    stations = spatial_join_counties(stations, counties_path)
    log.info("Retained %d stations inside VA county polygons", len(stations))

    log.info("Expanding to multi-type point rows")
    point_rows = expand_multi_type_rows(stations)
    # The spatial-join `geoid` is on the station-level frame; merge it onto the expanded rows.
    point_rows = point_rows.merge(
        stations[["ID", "geoid"]].rename(columns={"ID": "station_id"}),
        on="station_id",
        how="left",
    )
    log.info("Expanded to %d point rows", len(point_rows))

    log.info("Writing point CSV → %s", point_csv)
    point_csv.parent.mkdir(parents=True, exist_ok=True)
    # Persist the geoid as a pipeline-specific attribute so downstream consumers
    # can filter by county without redoing the spatial join.
    write_point_data(point_rows, point_csv)

    log.info("Aggregating to county-level long-format")
    county_rows = aggregate_to_counties(
        point_rows,
        scenario=source["scenario"],
        scenario_date=f"{source['scenario_year']}-01-01",
    )
    log.info("Produced %d county-level rows", len(county_rows))

    log.info("Writing county CSV → %s", county_csv)
    county_csv.parent.mkdir(parents=True, exist_ok=True)
    write_data(county_rows, county_csv, standardize=False, census_standardize=False)

    log.info("Done.")


if __name__ == "__main__":
    run()
