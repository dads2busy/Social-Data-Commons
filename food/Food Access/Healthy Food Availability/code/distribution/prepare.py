"""Prepare MRFEI (Modified Retail Food Environment Index) for NCR.

Loads supermarket and fast-food GeoJSON point files produced by ingest.py,
downloads NCR census geography boundaries, performs spatial distance-buffer
joins (804.672 m ≈ half-mile), and computes:

    RFEI = supermarket_count / (supermarket_count + fastfood_count) * 100

Outputs at block group, tract, county, and civic association levels.
"""

from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml
from sdc_core.io import data_reformat_for_site, write_data
from sdc_core.log import get_logger
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[2]
WORK_DIR = TOPIC_DIR / "data" / "working"
DIST_DIR = TOPIC_DIR / "data" / "distribution"

log = get_logger("healthy_food_availability.prepare")

BUFFER_METERS = 804.672  # half-mile
PROJECT_CRS = "EPSG:32618"  # UTM 18N — covers the NCR region
YEAR = datetime.now(tz=timezone.utc).year

DASHBOARD_MAP = {
    "ncr": "dashboard_data/national_capital_region_data",
}


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def _count_within_buffer(
    regions: gpd.GeoDataFrame,
    points: gpd.GeoDataFrame,
    geoid_col: str = "geoid",
) -> pd.Series:
    """Count how many points fall within BUFFER_METERS of each region polygon.

    Both inputs must be in EPSG:4326; they are projected internally.
    Returns a Series indexed by geoid with integer counts.
    """
    regions_proj = regions.to_crs(PROJECT_CRS)
    points_proj = points.to_crs(PROJECT_CRS)

    # Buffer region geometries by half-mile
    buffered = regions_proj.copy()
    buffered["geometry"] = buffered.geometry.buffer(BUFFER_METERS)

    joined = gpd.sjoin(points_proj, buffered, how="inner", predicate="within")
    counts = joined.groupby(f"{geoid_col}_right").size() if f"{geoid_col}_right" in joined.columns else joined.groupby(geoid_col).size()

    return counts


def _compute_rfei(
    regions: gpd.GeoDataFrame,
    supermarkets: gpd.GeoDataFrame,
    fastfood: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Compute RFEI for a set of regions.

    Returns a DataFrame with geoid, region_name, region_type, value columns.
    """
    # Buffer regions → sjoin points
    regions_proj = regions.to_crs(PROJECT_CRS)
    super_proj = supermarkets.to_crs(PROJECT_CRS)
    fast_proj = fastfood.to_crs(PROJECT_CRS)

    buffered = regions_proj.copy()
    buffered["geometry"] = buffered.geometry.buffer(BUFFER_METERS)

    # Count supermarkets per region
    s_joined = gpd.sjoin(super_proj, buffered, how="inner", predicate="within")
    super_counts = s_joined.groupby("geoid").size().rename("super_count")

    # Count fast food per region
    f_joined = gpd.sjoin(fast_proj, buffered, how="inner", predicate="within")
    fast_counts = f_joined.groupby("geoid").size().rename("fast_count")

    # Merge counts onto regions
    result = regions[["geoid", "region_name", "region_type"]].drop_duplicates().copy()
    result = result.merge(super_counts, on="geoid", how="left")
    result = result.merge(fast_counts, on="geoid", how="left")
    result["super_count"] = result["super_count"].fillna(0)
    result["fast_count"] = result["fast_count"].fillna(0)

    total = result["super_count"] + result["fast_count"]
    result["value"] = (result["super_count"] / total * 100).fillna(0)

    return result[["geoid", "region_name", "region_type", "value"]]


def run() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    config = load_config()

    # Load store locations
    super_path = WORK_DIR / "supermarkets.geojson"
    fast_path = WORK_DIR / "fastfood.geojson"
    if not super_path.exists() or not fast_path.exists():
        log.info("GeoJSON files not found in working dir; running ingest first")
        from food_access_healthy_food_availability_ingest import run as ingest_run
        ingest_run()

    supermarkets = gpd.read_file(super_path)
    fastfood = gpd.read_file(fast_path)
    log.info("Loaded %d supermarkets, %d fast-food locations", len(supermarkets), len(fastfood))

    # Load geographies
    geo_paths = config["geographies"]
    parts = []
    for level, geo_path in geo_paths.items():
        log.info("Loading %s geographies", level)
        gdf = gpd.read_file(REPO_DIR / geo_path)
        rfei = _compute_rfei(gdf, supermarkets, fastfood)
        log.info("Computed RFEI for %d %s regions", len(rfei), level)
        parts.append(rfei)

    current = pd.concat(parts, ignore_index=True)
    current["year"] = YEAR
    current["measure"] = "mrfei"
    current["measure_type"] = "index"
    current["moe"] = pd.NA

    # Include prior-year R output (2023) for historical continuity
    prior_path = WORK_DIR / "ncr_cttrbgca_sdad_2023_mrfei.csv.xz"
    if prior_path.exists():
        prior = pd.read_csv(prior_path, dtype={"geoid": str})
        # Normalize region_type to underscore convention
        prior["region_type"] = prior["region_type"].str.replace(" ", "_")
        combined = pd.concat([prior, current], ignore_index=True)
        log.info("Combined %d prior rows with %d current rows", len(prior), len(current))
    else:
        combined = current

    # Write distribution file spanning all years
    years = sorted(combined["year"].unique())
    time_span = f"{years[0]}_{years[-1]}" if len(years) > 1 else str(years[0])
    dist_name = f"ncr_cttrbgca_sdad_{time_span}_mrfei.csv.xz"
    dist_path = write_data(combined, DIST_DIR / dist_name)
    log.info("Wrote %d rows to %s", len(combined), dist_path)

    # Write dashboard files
    dashboard_rel = DASHBOARD_MAP.get("ncr")
    if dashboard_rel:
        paths = data_reformat_for_site(
            source_path=dist_path,
            output_dir=REPO_DIR / dashboard_rel,
            levels=["county", "tract", "block_group", "civic_association"],
            coverage_area="ncr",
            data_source="sdad",
            title="mrfei",
        )
        for p in paths:
            log.info("Wrote %s", p)

    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
