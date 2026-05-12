"""Ingest IM3 CERF projected data center scenarios, filter to Virginia,
reproject polygons, take centroids, attach county FIPS, write outputs.

Reads `data/original/{growth_tier}/{growth_tier}_{gravity_weight}_market_gravity.geojson`
for all 20 (growth_tier, gravity_weight) combinations, and writes:

  data/distribution/{point_csv}    point-schema rows, all scenarios combined
  data/distribution/{county_csv}   long-format (county × scenario) aggregates

Run: uv run python energy/DataCentersProjected/code/distribution/ingest.py
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
from transforms import aggregate_to_counties, scenario_label, shape_to_point_schema

log = get_logger("data_centers_projected.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_scenario_files(input_root: Path) -> list[Path]:
    """Return all 20 (growth_tier, gravity_weight) GeoJSON files under input_root."""
    files = []
    for growth_dir in sorted(input_root.glob("*_growth")):
        for geojson in sorted(growth_dir.glob("*_market_gravity.geojson")):
            files.append(geojson)
    return files


def load_and_tag_scenarios(paths: list[Path]) -> gpd.GeoDataFrame:
    """Load each GeoJSON, add a `scenario` column, concatenate all 20 files."""
    parts = []
    for p in paths:
        gdf = gpd.read_file(p)
        # `growth_scenario` and `market_gravity_weight` are already columns in each feature.
        # Compose the canonical label from them.
        gdf["scenario"] = [
            scenario_label(gs, gw)
            for gs, gw in zip(gdf["growth_scenario"], gdf["market_gravity_weight"])
        ]
        parts.append(gdf)
    combined = pd.concat(parts, ignore_index=True)
    return gpd.GeoDataFrame(combined, geometry="geometry", crs=parts[0].crs)


def filter_to_state(gdf: gpd.GeoDataFrame, state_filter: str) -> gpd.GeoDataFrame:
    """Filter on the `region` column (lowercase state name)."""
    return gdf[gdf["region"] == state_filter].copy()


def reproject_and_centroid(gdf: gpd.GeoDataFrame, target_crs: str) -> gpd.GeoDataFrame:
    """Reproject to target_crs and replace polygons with centroid Points."""
    reprojected = gdf.to_crs(target_crs)
    centroids = reprojected.geometry.centroid
    out = reprojected.copy()
    out["geometry"] = centroids
    out["lat"] = centroids.y
    out["lon"] = centroids.x
    return out


def attach_county_fips(centroids: gpd.GeoDataFrame, counties_path: Path) -> pd.DataFrame:
    """Spatial-join centroid points to 5-digit county FIPS."""
    counties = gpd.read_file(counties_path)[["geoid", "geometry"]]
    if centroids.crs != counties.crs:
        counties = counties.to_crs(centroids.crs)

    joined = gpd.sjoin(centroids, counties, how="left", predicate="intersects")

    dropped = joined["geoid"].isna().sum()
    if dropped:
        log.warning("%d centroids fell outside any VA county polygon and were dropped", dropped)
    joined = joined.dropna(subset=["geoid"])

    # Stations on county polygon boundaries can match multiple counties; keep first.
    boundary_dups = joined.duplicated(subset=["id", "scenario"]).sum()
    if boundary_dups:
        log.warning("%d (id, scenario) pairs matched multiple counties; keeping first", boundary_dups)
    joined = joined.drop_duplicates(subset=["id", "scenario"], keep="first")

    return pd.DataFrame(joined.drop(columns=["geometry", "index_right"], errors="ignore"))


def run() -> None:
    config = load_config()
    source = config["source"]
    geos = config["geographies"]
    out = config["output"]

    input_root = TOPIC_DIR / source["input_root"]
    counties_path = REPO_DIR / geos["va_counties"]
    point_csv = TOPIC_DIR / out["point_csv"]
    county_csv = TOPIC_DIR / out["county_csv"]

    log.info("Finding scenario files under %s", input_root)
    files = find_scenario_files(input_root)
    log.info("Found %d scenario files", len(files))
    if len(files) != 20:
        log.warning("Expected 20 scenario files, found %d", len(files))

    log.info("Loading and tagging all scenarios")
    gdf = load_and_tag_scenarios(files)
    log.info("Loaded %d features across all scenarios", len(gdf))

    log.info("Filtering to region=%s", source["state_filter"])
    gdf = filter_to_state(gdf, source["state_filter"])
    log.info("Retained %d VA features", len(gdf))

    log.info("Reprojecting %s -> %s and taking centroids", source["source_crs"], source["target_crs"])
    gdf = reproject_and_centroid(gdf, source["target_crs"])

    log.info("Spatial-joining centroids to VA counties from %s", counties_path)
    enriched = attach_county_fips(gdf, counties_path)
    log.info("Retained %d centroids with assigned county FIPS", len(enriched))

    log.info("Shaping to point schema")
    point_rows = shape_to_point_schema(enriched, snapshot_year=source["snapshot_year"])
    log.info("Produced %d point rows", len(point_rows))

    log.info("Writing point CSV → %s", point_csv)
    point_csv.parent.mkdir(parents=True, exist_ok=True)
    write_point_data(point_rows, point_csv)

    log.info("Aggregating to (county, scenario)")
    scenario_date = f"{source['snapshot_year']}-01-01"
    county_rows = aggregate_to_counties(point_rows, scenario_date=scenario_date)
    log.info("Produced %d (county, scenario, measure) rows", len(county_rows))

    log.info("Writing county CSV → %s", county_csv)
    county_csv.parent.mkdir(parents=True, exist_ok=True)
    write_data(county_rows, county_csv, standardize=False, census_standardize=False)

    log.info("Done.")


if __name__ == "__main__":
    run()
