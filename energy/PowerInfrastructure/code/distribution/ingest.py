"""Ingest OpenStreetMap power plants and substations for Virginia.

Fetches `power=plant` / `power=substation` features via osmnx (Overpass API),
caches the raw GeoDataFrame to data/original/, takes polygon centroids,
spatial-joins them to VA county polygons for FIPS, and writes:

  data/distribution/{point_csv}    point-schema rows (one per OSM feature)
  data/distribution/{county_csv}   long-format county counts + capacity

Run: uv run python energy/PowerInfrastructure/code/distribution/ingest.py
Force a fresh Overpass query (ignore cache): add --refresh
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import osmnx as ox
import pandas as pd
import yaml
from sdc_core.io import write_data, write_point_data
from sdc_core.log import get_logger

THIS_DIR = Path(__file__).resolve().parent
TOPIC_DIR = THIS_DIR.parents[1]
REPO_DIR = TOPIC_DIR.parents[1]

sys.path.insert(0, str(THIS_DIR))
from transforms import aggregate_to_counties, shape_to_point_schema

log = get_logger("power_infrastructure.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def fetch_features(source: dict, cache_path: Path, *, refresh: bool) -> gpd.GeoDataFrame:
    """Query Overpass via osmnx (or read cache). Returns a flat GeoDataFrame
    with element_type/osmid as columns and OSM tags as columns."""
    if cache_path.exists() and not refresh:
        log.info("Reading cached features from %s", cache_path)
        gdf = gpd.read_parquet(cache_path)
    else:
        log.info("Querying Overpass for tags=%s in place=%s", source["tags"], source["place"])
        gdf = ox.features_from_place(source["place"], tags=source["tags"])
        log.info("Overpass returned %d features", len(gdf))
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        # reset_index so element_type/osmid become columns and parquet round-trips.
        gdf = gdf.reset_index()
        gdf.to_parquet(cache_path)
        log.info("Cached raw features to %s", cache_path)
    if "element_type" not in gdf.columns:
        gdf = gdf.reset_index()
    return gdf


def reproject_and_centroid(gdf: gpd.GeoDataFrame, target_crs: str) -> gpd.GeoDataFrame:
    """Reproject to target_crs and replace geometry with centroid Points; record lat/lon (WGS84)."""
    reprojected = gdf.to_crs(target_crs)
    centroids = reprojected.geometry.centroid
    out = reprojected.copy()
    out["geometry"] = centroids
    wgs84 = gpd.GeoSeries(centroids, crs=target_crs).to_crs("EPSG:4326")
    out["lat"] = wgs84.y.values
    out["lon"] = wgs84.x.values
    return out


def attach_county_fips(centroids: gpd.GeoDataFrame, counties_path: Path) -> pd.DataFrame:
    """Spatial-join centroid points to 5-digit county FIPS; drop misses, keep first on ties."""
    counties = gpd.read_file(counties_path)[["geoid", "geometry"]]
    if centroids.crs != counties.crs:
        counties = counties.to_crs(centroids.crs)

    joined = gpd.sjoin(centroids, counties, how="left", predicate="intersects")

    dropped = joined["geoid"].isna().sum()
    if dropped:
        log.warning("%d centroids fell outside any VA county polygon and were dropped", dropped)
    joined = joined.dropna(subset=["geoid"])

    boundary_dups = joined.duplicated(subset=["element_type", "osmid"]).sum()
    if boundary_dups:
        log.warning("%d (element_type, osmid) pairs matched multiple counties; keeping first", boundary_dups)
    joined = joined.drop_duplicates(subset=["element_type", "osmid"], keep="first")

    return pd.DataFrame(joined.drop(columns=["geometry", "index_right"], errors="ignore"))


def run(refresh: bool = False) -> None:
    config = load_config()
    source = config["source"]
    geos = config["geographies"]
    out = config["output"]

    cache_path = TOPIC_DIR / source["cache_file"]
    counties_path = REPO_DIR / geos["va_counties"]
    point_csv = TOPIC_DIR / out["point_csv"]
    county_csv = TOPIC_DIR / out["county_csv"]

    gdf = fetch_features(source, cache_path, refresh=refresh)
    log.info("Working with %d features", len(gdf))
    if len(gdf) == 0:
        raise SystemExit("Overpass returned no features — check tags/place in pipeline.yaml")

    log.info("Reprojecting to %s and taking centroids", source["target_crs"])
    gdf = reproject_and_centroid(gdf, source["target_crs"])

    log.info("Spatial-joining centroids to VA counties from %s", counties_path)
    enriched = attach_county_fips(gdf, counties_path)
    log.info("Retained %d features with assigned county FIPS", len(enriched))

    log.info("Shaping to point schema")
    point_rows = shape_to_point_schema(enriched, snapshot_year=source["snapshot_year"])
    log.info("Produced %d point rows", len(point_rows))

    log.info("Writing point CSV → %s", point_csv)
    point_csv.parent.mkdir(parents=True, exist_ok=True)
    write_point_data(point_rows, point_csv)

    log.info("Aggregating to county long-format")
    county_rows = aggregate_to_counties(
        point_rows,
        scenario=source["scenario"],
        scenario_date=source["snapshot_date"],
    )
    log.info("Produced %d county-level rows", len(county_rows))

    log.info("Writing county CSV → %s", county_csv)
    county_csv.parent.mkdir(parents=True, exist_ok=True)
    write_data(county_rows, county_csv, standardize=False, census_standardize=False)

    log.info("Done.")


if __name__ == "__main__":
    run(refresh="--refresh" in sys.argv)
