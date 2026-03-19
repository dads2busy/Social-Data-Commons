"""Ingest store and restaurant locations from OpenStreetMap for MRFEI.

Queries OSM Overpass API for shops (supermarkets, convenience, variety,
department) and amenities (fast_food) within the NCR boundary + 1 km buffer.
Produces two GeoJSON files — supermarkets.geojson and fastfood.geojson — in
the working directory.
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
import osmnx as ox
import yaml
from sdc_core.log import get_logger

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[2]
WORK_DIR = TOPIC_DIR / "data" / "working"

log = get_logger("healthy_food_availability.ingest")

# Buffer around NCR boundary to capture stores just outside county lines
QUERY_BUFFER_METERS = 1000


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def _ncr_polygon(config: dict) -> gpd.GeoDataFrame:
    """Load NCR county boundaries and return a single buffered polygon."""
    geo_path = config["geographies"]["county"]
    counties = gpd.read_file(REPO_DIR / geo_path)
    # Union all counties → single polygon, buffer by 1 km in projected CRS
    union = counties.to_crs("EPSG:32618").union_all().buffer(QUERY_BUFFER_METERS)
    return gpd.GeoDataFrame(geometry=[union], crs="EPSG:32618").to_crs("EPSG:4326")


def _to_points(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Reduce to point geometries (centroids for polygons)."""
    if gdf.empty:
        return gdf
    mask = gdf.geometry.geom_type == "Point"
    points = gdf.loc[mask].copy()
    polys = gdf.loc[~mask].copy()
    if not polys.empty:
        polys = polys.copy()
        polys["geometry"] = polys.to_crs("EPSG:32618").geometry.centroid.to_crs("EPSG:4326")
        points = gpd.GeoDataFrame(
            pd.concat([points, polys], ignore_index=True),
            crs=gdf.crs,
        )
    return points


def run() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    config = load_config()

    # Get NCR boundary polygon for spatial queries
    ncr_gdf = _ncr_polygon(config)
    ncr_poly = ncr_gdf.geometry.iloc[0]

    # --- Shops ---
    log.info("Querying OSM shops within NCR boundary")
    shops = ox.features_from_polygon(ncr_poly, tags={"shop": True})
    shops = _to_points(shops)

    # Classify shops
    shop_col = shops.get("shop", pd.Series(dtype=str))
    name_col = shops.get("name", pd.Series(dtype=str)).fillna("")

    supermarkets = shops[shop_col.str.contains("supermarket", na=False)].copy()
    department = shops[
        shop_col.str.contains("department", na=False)
        & name_col.str.contains("Target|Walmart", case=False, na=False)
    ].copy()
    convenience = shops[shop_col.str.contains("convenience", na=False)].copy()
    variety = shops[shop_col.str.contains("variety", na=False)].copy()

    # Healthy = supermarkets + qualifying department stores
    healthy = gpd.GeoDataFrame(
        pd.concat([supermarkets, department], ignore_index=True), crs="EPSG:4326"
    )[["geometry"]].drop_duplicates()

    # --- Fast food ---
    log.info("Querying OSM fast food within NCR boundary")
    fastfood = ox.features_from_polygon(ncr_poly, tags={"amenity": "fast_food"})
    fastfood = _to_points(fastfood)

    # Unhealthy = fast food + convenience + variety
    unhealthy = gpd.GeoDataFrame(
        pd.concat(
            [fastfood, convenience, variety],
            ignore_index=True,
        ),
        crs="EPSG:4326",
    )[["geometry"]].drop_duplicates()

    # Write
    healthy_path = WORK_DIR / "supermarkets.geojson"
    unhealthy_path = WORK_DIR / "fastfood.geojson"
    healthy.to_file(healthy_path, driver="GeoJSON")
    log.info("Wrote %d supermarket locations to %s", len(healthy), healthy_path)
    unhealthy.to_file(unhealthy_path, driver="GeoJSON")
    log.info("Wrote %d fast-food/convenience locations to %s", len(unhealthy), unhealthy_path)


if __name__ == "__main__":
    run()
