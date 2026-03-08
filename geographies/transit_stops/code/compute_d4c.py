"""Compute D4C (distance to nearest transit stop) for block group centroids.

For each block group in a target geography, calculates the haversine distance
(in miles) from the block group centroid to the nearest transit stop.

Usage:
    uv run python compute_d4c.py --geo-vintage 2020 --coverage ncr
    uv run python compute_d4c.py --geo-vintage 2010 --coverage ncr

Output: data/d4c/{coverage}_d4c_bg{vintage}_{year}.parquet
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sdc_core.log import get_logger

BASE_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BASE_DIR.parents[1]
STOPS_DIR = BASE_DIR / "data/stops"
OUT_DIR = BASE_DIR / "data/d4c"

log = get_logger("transit_stops.compute_d4c")

GEO_PATHS = {
    "ncr": {
        2020: "geographies/NCR/Census Geographies/Block Group/2020/data/distribution/ncr_geo_census_cb_2020_census_block_groups.geojson",
        2010: "geographies/NCR/Census Geographies/Block Group/2010/data/distribution/ncr_geo_census_cb_2010_census_block_groups.geojson",
    },
    "va": {
        2020: "geographies/VA/Census Geographies/Block Group/2020/data/distribution/va_geo_census_cb_2020_census_block_groups.geojson",
        2010: "geographies/VA/Census Geographies/Block Group/2010/data/distribution/va_geo_census_cb_2010_census_block_groups.geojson",
    },
}

EARTH_RADIUS_MI = 3958.8


def load_block_group_centroids(geojson_path: Path) -> pd.DataFrame:
    """Load block group boundaries and compute centroids."""
    with open(geojson_path) as f:
        gj = json.load(f)

    records = []
    for feat in gj["features"]:
        geoid = feat["properties"]["geoid"]
        geom = feat["geometry"]

        # Collect all exterior ring coordinates
        coords = []
        if geom["type"] == "Polygon":
            coords = geom["coordinates"][0]
        elif geom["type"] == "MultiPolygon":
            for poly in geom["coordinates"]:
                coords.extend(poly[0])

        arr = np.array(coords)
        lon = arr[:, 0].mean()
        lat = arr[:, 1].mean()
        records.append({"geoid": geoid, "lat": lat, "lon": lon})

    return pd.DataFrame(records)


def haversine_nearest(bg_lats: np.ndarray, bg_lons: np.ndarray,
                      stop_lats: np.ndarray, stop_lons: np.ndarray,
                      chunk_size: int = 2000) -> np.ndarray:
    """Find distance to nearest stop for each block group using haversine.

    Processes in chunks to manage memory for large stop arrays.
    Returns distances in miles.
    """
    n_bg = len(bg_lats)
    min_dist = np.full(n_bg, np.inf)

    bg_lat_r = np.radians(bg_lats)
    bg_lon_r = np.radians(bg_lons)
    stop_lat_r = np.radians(stop_lats)
    stop_lon_r = np.radians(stop_lons)

    # Process stops in chunks to limit memory
    for i in range(0, len(stop_lats), chunk_size):
        s_lat = stop_lat_r[i:i + chunk_size][None, :]  # (1, chunk)
        s_lon = stop_lon_r[i:i + chunk_size][None, :]

        dlat = s_lat - bg_lat_r[:, None]  # (N, chunk)
        dlon = s_lon - bg_lon_r[:, None]

        a = np.sin(dlat / 2) ** 2 + np.cos(bg_lat_r[:, None]) * np.cos(s_lat) * np.sin(dlon / 2) ** 2
        c = 2 * np.arcsin(np.sqrt(a))
        chunk_dist = EARTH_RADIUS_MI * c

        chunk_min = chunk_dist.min(axis=1)
        min_dist = np.minimum(min_dist, chunk_min)

    return min_dist


def compute_for_year(bg_df: pd.DataFrame, year: int, coverage: str,
                     buffer_deg: float = 0.5) -> pd.DataFrame:
    """Compute D4C for all block groups using transit stops from a given year."""
    stops_path = STOPS_DIR / f"us_transit_stops_{year}.parquet"
    if not stops_path.exists():
        log.warning("No stops file for year %d, skipping", year)
        return pd.DataFrame()

    stops = pd.read_parquet(stops_path)

    # Filter stops to coverage area bounding box + buffer
    area_stops = stops[
        (stops.stop_lat.between(bg_df.lat.min() - buffer_deg, bg_df.lat.max() + buffer_deg)) &
        (stops.stop_lon.between(bg_df.lon.min() - buffer_deg, bg_df.lon.max() + buffer_deg))
    ]
    log.info("Year %d: %d stops in %s area (from %d total)",
             year, len(area_stops), coverage.upper(), len(stops))

    if area_stops.empty:
        log.warning("No stops found in area for year %d", year)
        return pd.DataFrame()

    distances = haversine_nearest(
        bg_df.lat.values, bg_df.lon.values,
        area_stops.stop_lat.values, area_stops.stop_lon.values,
    )

    # Find nearest stop details
    bg_lat_r = np.radians(bg_df.lat.values)
    bg_lon_r = np.radians(bg_df.lon.values)
    stop_lat_r = np.radians(area_stops.stop_lat.values)
    stop_lon_r = np.radians(area_stops.stop_lon.values)

    # Recompute to get indices (cheaper for small result)
    nearest_idx = np.zeros(len(bg_df), dtype=int)
    for i in range(len(bg_df)):
        dlat = stop_lat_r - bg_lat_r[i]
        dlon = stop_lon_r - bg_lon_r[i]
        a = np.sin(dlat / 2) ** 2 + np.cos(bg_lat_r[i]) * np.cos(stop_lat_r) * np.sin(dlon / 2) ** 2
        nearest_idx[i] = a.argmin()

    result = pd.DataFrame({
        "geoid": bg_df.geoid.values,
        "year": year,
        "d4c_dist_mi": np.round(distances, 4),
        "nearest_stop_name": area_stops.iloc[nearest_idx]["stop_name"].values,
        "nearest_stop_agency": area_stops.iloc[nearest_idx]["agency_name"].values,
    })

    return result


def run(geo_vintage: int, coverage: str, years: list[int] | None = None):
    geo_path = REPO_DIR / GEO_PATHS[coverage][geo_vintage]
    if not geo_path.exists():
        raise FileNotFoundError(f"Block group GeoJSON not found: {geo_path}")

    log.info("Loading %s block groups (vintage %d)", coverage.upper(), geo_vintage)
    bg_df = load_block_group_centroids(geo_path)
    log.info("Loaded %d block group centroids", len(bg_df))

    if years is None:
        # Find all available years
        years = sorted(
            int(p.stem.split("_")[-1])
            for p in STOPS_DIR.glob("us_transit_stops_*.parquet")
        )
    log.info("Computing D4C for years: %s", years)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for year in years:
        result = compute_for_year(bg_df, year, coverage)
        if result.empty:
            continue

        out_path = OUT_DIR / f"{coverage}_d4c_bg{geo_vintage}_{year}.parquet"
        result.to_parquet(out_path, index=False)
        log.info(
            "Year %d: median=%.3f mi, mean=%.3f mi, max=%.3f mi → %s",
            year, result.d4c_dist_mi.median(), result.d4c_dist_mi.mean(),
            result.d4c_dist_mi.max(), out_path.name,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute D4C transit proximity")
    parser.add_argument("--geo-vintage", type=int, required=True, choices=[2010, 2020])
    parser.add_argument("--coverage", required=True, choices=["ncr", "va"])
    parser.add_argument("--years", type=int, nargs="*", help="Specific years (default: all available)")
    args = parser.parse_args()
    run(args.geo_vintage, args.coverage, args.years)
