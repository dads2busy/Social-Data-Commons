"""Compute Employment Intensity (gravity model) from LODES WAC + TIGER centroids.

Employment Intensity for each VA Census block group is calculated as:
    E = sum(jobs_i / dist_i^2)
using a hierarchical distance approximation:
    - Within 34 miles: individual block-level job counts
    - 34-165 miles: tract-level aggregated job counts
    - 165-200 miles: county-level aggregated job counts

Data sources:
    - LODES WAC: https://lehd.ces.census.gov/data/lodes/
    - TIGER/Line: https://www2.census.gov/geo/tiger/TIGER2020/
"""

import io
import time
import zipfile
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"
WORK_DIR = TOPIC_DIR / "data/working"
TIGER_CACHE = WORK_DIR / "tiger_cache"

log = get_logger("employment_access.ingest")

LODES8_URL = "https://lehd.ces.census.gov/data/lodes/LODES8/{state}/wac/{state}_wac_S000_JT00_{year}.csv.gz"
LODES7_URL = "https://lehd.ces.census.gov/data/lodes/LODES7/{state}/wac/{state}_wac_S000_JT00_{year}.csv.gz"

TIGER_BLOCK_URL = "https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/tl_2020_{fips}_tabblock20.zip"
TIGER_BG_URL = "https://www2.census.gov/geo/tiger/TIGER2020/BG/tl_2020_{fips}_bg.zip"
TIGER_TRACT_URL = "https://www2.census.gov/geo/tiger/TIGER2020/TRACT/tl_2020_{fips}_tract.zip"
TIGER_COUNTY_URL = "https://www2.census.gov/geo/tiger/TIGER2020/COUNTY/tl_2020_us_county.zip"

EARTH_RADIUS_MILES = 3958.8


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# LODES WAC download
# ---------------------------------------------------------------------------

def download_lodes_wac(state: str, year: int, client: httpx.Client) -> pd.DataFrame | None:
    """Download a LODES WAC file and return block-level geoid + total jobs."""
    for url_template in [LODES8_URL, LODES7_URL]:
        url = url_template.format(state=state, year=year)
        try:
            resp = client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                df = pd.read_csv(
                    io.BytesIO(resp.content),
                    compression="gzip",
                    dtype={"w_geocode": str},
                    usecols=["w_geocode", "C000"],
                )
                df = df.rename(columns={"w_geocode": "geoid", "C000": "jobs"})
                df["jobs"] = pd.to_numeric(df["jobs"], errors="coerce").fillna(0).astype(int)
                df = df[df["jobs"] > 0].copy()
                log.info("Downloaded LODES %s %d: %d blocks with jobs",
                         state.upper(), year, len(df))
                return df
        except Exception as e:
            log.warning("Failed %s %d (%s): %s", state, year,
                        "LODES8" if "LODES8" in url_template else "LODES7", e)
    log.error("Could not download LODES WAC for %s %d", state, year)
    return None


def download_all_lodes(states: dict, year: int, client: httpx.Client) -> pd.DataFrame:
    """Download LODES WAC for all nearby states and combine."""
    frames = []
    for abbr in sorted(states.keys()):
        df = download_lodes_wac(abbr, year, client)
        if df is not None:
            frames.append(df)
        time.sleep(0.3)
    if not frames:
        return pd.DataFrame(columns=["geoid", "jobs"])
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# TIGER centroid download + caching
# ---------------------------------------------------------------------------

def _download_and_cache(url: str, cache_path: Path, client: httpx.Client) -> Path:
    """Download a file if not cached; return local path."""
    if cache_path.exists():
        return cache_path
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading %s", url)
    resp = client.get(url, follow_redirects=True, timeout=120)
    resp.raise_for_status()
    cache_path.write_bytes(resp.content)
    return cache_path


def _read_shapefile_centroids(zip_path: Path, geoid_col: str) -> pd.DataFrame:
    """Read a TIGER shapefile zip, extract GEOID + internal point lat/lon."""
    import geopandas as gpd

    gdf = gpd.read_file(f"zip://{zip_path}")
    lat_col = [c for c in gdf.columns if "INTPTLAT" in c][0]
    lon_col = [c for c in gdf.columns if "INTPTLON" in c][0]
    geo_col = [c for c in gdf.columns if c.startswith("GEOID")][0]

    result = pd.DataFrame({
        "geoid": gdf[geo_col].astype(str),
        "lat": pd.to_numeric(gdf[lat_col], errors="coerce"),
        "lon": pd.to_numeric(gdf[lon_col], errors="coerce"),
    })
    return result.dropna(subset=["lat", "lon"])


def load_block_centroids(state_fips_list: list[str], client: httpx.Client) -> pd.DataFrame:
    """Load block centroids for all states from TIGER shapefiles."""
    frames = []
    for fips in state_fips_list:
        url = TIGER_BLOCK_URL.format(fips=fips)
        cache = TIGER_CACHE / f"tl_2020_{fips}_tabblock20.zip"
        path = _download_and_cache(url, cache, client)
        df = _read_shapefile_centroids(path, "GEOID20")
        frames.append(df)
        log.info("Loaded %d block centroids for state %s", len(df), fips)
    return pd.concat(frames, ignore_index=True)


def load_bg_centroids(state_fips_list: list[str], client: httpx.Client) -> pd.DataFrame:
    """Load block group centroids for target state(s) from TIGER shapefiles."""
    frames = []
    for fips in state_fips_list:
        url = TIGER_BG_URL.format(fips=fips)
        cache = TIGER_CACHE / f"tl_2020_{fips}_bg.zip"
        path = _download_and_cache(url, cache, client)
        df = _read_shapefile_centroids(path, "GEOID20")
        frames.append(df)
        log.info("Loaded %d block group centroids for state %s", len(df), fips)
    return pd.concat(frames, ignore_index=True)


def load_tract_centroids(state_fips_list: list[str], client: httpx.Client) -> pd.DataFrame:
    """Load tract centroids from TIGER shapefiles."""
    frames = []
    for fips in state_fips_list:
        url = TIGER_TRACT_URL.format(fips=fips)
        cache = TIGER_CACHE / f"tl_2020_{fips}_tract.zip"
        path = _download_and_cache(url, cache, client)
        df = _read_shapefile_centroids(path, "GEOID20")
        frames.append(df)
        log.info("Loaded %d tract centroids for state %s", len(df), fips)
    return pd.concat(frames, ignore_index=True)


def load_county_centroids(client: httpx.Client) -> pd.DataFrame:
    """Load county centroids from national TIGER shapefile."""
    url = TIGER_COUNTY_URL
    cache = TIGER_CACHE / "tl_2020_us_county.zip"
    path = _download_and_cache(url, cache, client)
    df = _read_shapefile_centroids(path, "GEOID20")
    log.info("Loaded %d county centroids (national)", len(df))
    return df


# ---------------------------------------------------------------------------
# Job aggregation to tract / county levels
# ---------------------------------------------------------------------------

def aggregate_jobs(block_jobs: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Aggregate block-level jobs to tract and county levels."""
    # Tract: first 11 chars of 15-digit block FIPS
    tract = block_jobs.copy()
    tract["geoid"] = tract["geoid"].str[:11]
    tract = tract.groupby("geoid", as_index=False)["jobs"].sum()

    # County: first 5 chars
    county = block_jobs.copy()
    county["geoid"] = county["geoid"].str[:5]
    county = county.groupby("geoid", as_index=False)["jobs"].sum()

    return {"block": block_jobs, "tract": tract, "county": county}


# ---------------------------------------------------------------------------
# Haversine distance (vectorized)
# ---------------------------------------------------------------------------

def haversine_miles(lat1: np.ndarray, lon1: np.ndarray,
                    lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    """Vectorized Haversine distance in miles. Inputs in degrees."""
    lat1, lon1, lat2, lon2 = (np.radians(x) for x in (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(a))


# ---------------------------------------------------------------------------
# Gravity model computation
# ---------------------------------------------------------------------------

def _miles_to_deg_lat(miles: float) -> float:
    """Approximate degrees latitude per mile."""
    return miles / 69.0


def _miles_to_deg_lon(miles: float, lat_deg: float) -> float:
    """Approximate degrees longitude per mile at given latitude."""
    return miles / (69.0 * np.cos(np.radians(lat_deg)))


def compute_gravity(
    va_bg: pd.DataFrame,
    job_levels: dict[str, pd.DataFrame],
    block_centroids: pd.DataFrame,
    tract_centroids: pd.DataFrame,
    county_centroids: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    """Compute Employment Intensity for all VA block groups.

    Uses hierarchical distance approximation:
      - ≤ block_threshold: block-level jobs
      - block_threshold to tract_threshold: tract-level jobs
      - tract_threshold to max_distance: county-level jobs
    """
    grav_cfg = config["sources"]["va"]["gravity"]
    max_dist = grav_cfg["max_distance_miles"]
    block_thresh = grav_cfg["block_threshold_miles"]
    tract_thresh = grav_cfg["tract_threshold_miles"]
    min_dist = grav_cfg["min_distance_miles"]

    # Merge job counts onto centroid DataFrames
    block_data = block_centroids.merge(job_levels["block"], on="geoid", how="inner")
    tract_data = tract_centroids.merge(job_levels["tract"], on="geoid", how="inner")
    county_data = county_centroids.merge(job_levels["county"], on="geoid", how="inner")

    # Convert to numpy arrays for fast computation
    blk_lat = block_data["lat"].values
    blk_lon = block_data["lon"].values
    blk_jobs = block_data["jobs"].values.astype(np.float64)

    tr_lat = tract_data["lat"].values
    tr_lon = tract_data["lon"].values
    tr_jobs = tract_data["jobs"].values.astype(np.float64)

    ct_lat = county_data["lat"].values
    ct_lon = county_data["lon"].values
    ct_jobs = county_data["jobs"].values.astype(np.float64)

    bg_geoids = va_bg["geoid"].values
    bg_lats = va_bg["lat"].values
    bg_lons = va_bg["lon"].values

    n_bg = len(va_bg)
    gravity_values = np.zeros(n_bg)

    log.info("Computing gravity for %d VA block groups "
             "(blocks=%d, tracts=%d, counties=%d)",
             n_bg, len(block_data), len(tract_data), len(county_data))

    for i in range(n_bg):
        lat_i = bg_lats[i]
        lon_i = bg_lons[i]

        total = 0.0

        # --- Tier 1: Blocks within block_threshold miles ---
        dlat = _miles_to_deg_lat(block_thresh)
        dlon = _miles_to_deg_lon(block_thresh, lat_i)
        mask = (
            (np.abs(blk_lat - lat_i) <= dlat) &
            (np.abs(blk_lon - lon_i) <= dlon)
        )
        if mask.any():
            dists = haversine_miles(lat_i, lon_i, blk_lat[mask], blk_lon[mask])
            dists = np.maximum(dists, min_dist)
            within = dists <= block_thresh
            if within.any():
                total += np.sum(blk_jobs[mask][within] / dists[within] ** 2)

        # --- Tier 2: Tracts between block_threshold and tract_threshold ---
        dlat2 = _miles_to_deg_lat(tract_thresh)
        dlon2 = _miles_to_deg_lon(tract_thresh, lat_i)
        mask2 = (
            (np.abs(tr_lat - lat_i) <= dlat2) &
            (np.abs(tr_lon - lon_i) <= dlon2)
        )
        if mask2.any():
            dists2 = haversine_miles(lat_i, lon_i, tr_lat[mask2], tr_lon[mask2])
            dists2 = np.maximum(dists2, min_dist)
            band = (dists2 > block_thresh) & (dists2 <= tract_thresh)
            if band.any():
                total += np.sum(tr_jobs[mask2][band] / dists2[band] ** 2)

        # --- Tier 3: Counties between tract_threshold and max_distance ---
        dlat3 = _miles_to_deg_lat(max_dist)
        dlon3 = _miles_to_deg_lon(max_dist, lat_i)
        mask3 = (
            (np.abs(ct_lat - lat_i) <= dlat3) &
            (np.abs(ct_lon - lon_i) <= dlon3)
        )
        if mask3.any():
            dists3 = haversine_miles(lat_i, lon_i, ct_lat[mask3], ct_lon[mask3])
            dists3 = np.maximum(dists3, min_dist)
            band3 = (dists3 > tract_thresh) & (dists3 <= max_dist)
            if band3.any():
                total += np.sum(ct_jobs[mask3][band3] / dists3[band3] ** 2)

        gravity_values[i] = total

        if (i + 1) % 1000 == 0:
            log.info("  Processed %d / %d block groups", i + 1, n_bg)

    return pd.DataFrame({"geoid": bg_geoids, "emp_gravity": gravity_values})


def aggregate_bg_gravity(bg_gravity: pd.DataFrame) -> pd.DataFrame:
    """Aggregate block group gravity to tract and county via mean."""
    bg = bg_gravity.copy()
    bg["region_type"] = "block_group"

    # Tract: mean of block groups (first 11 chars)
    tr = bg.copy()
    tr["geoid"] = tr["geoid"].str[:11]
    tr = tr.groupby("geoid", as_index=False)["emp_gravity"].mean()
    tr["region_type"] = "tract"

    # County: mean of block groups (first 5 chars)
    ct = bg.copy()
    ct["geoid"] = ct["geoid"].str[:5]
    ct = ct.groupby("geoid", as_index=False)["emp_gravity"].mean()
    ct["region_type"] = "county"

    return pd.concat([tr, ct], ignore_index=True)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run() -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        DIST_DIR.mkdir(parents=True, exist_ok=True)
        TIGER_CACHE.mkdir(parents=True, exist_ok=True)

        src = config["sources"]["va"]
        nearby = src["nearby_states"]
        state_fips_list = list(nearby.values())
        target_fips = src["target_state_fips"]
        years = src["years"]

        with httpx.Client(timeout=120) as client:
            # --- Download TIGER centroids (one-time, cached) ---
            log.info("Loading TIGER centroids for %d states", len(state_fips_list))
            block_centroids = load_block_centroids(state_fips_list, client)
            va_bg_centroids = load_bg_centroids([target_fips], client)
            tract_centroids = load_tract_centroids(state_fips_list, client)
            county_centroids = load_county_centroids(client)

            # Filter county centroids to nearby states only
            county_centroids = county_centroids[
                county_centroids["geoid"].str[:2].isin(state_fips_list)
            ].copy()

            log.info("Centroids loaded: %d blocks, %d VA block groups, "
                     "%d tracts, %d counties",
                     len(block_centroids), len(va_bg_centroids),
                     len(tract_centroids), len(county_centroids))

            # --- Process each year ---
            all_frames = []
            for year in years:
                log.info("=== Processing year %d ===", year)
                yt0 = time.time()

                # Download LODES WAC for all nearby states
                block_jobs = download_all_lodes(nearby, year, client)
                if block_jobs.empty:
                    log.warning("No LODES data for year %d, skipping", year)
                    continue

                # Aggregate to tract/county levels
                job_levels = aggregate_jobs(block_jobs)

                # Compute gravity for all VA block groups
                bg_gravity = compute_gravity(
                    va_bg_centroids, job_levels,
                    block_centroids, tract_centroids, county_centroids,
                    config,
                )

                # Aggregate BG to tract + county
                result = aggregate_bg_gravity(bg_gravity)
                result["year"] = year
                result["measure"] = "employment_access_index"
                result["moe"] = pd.NA
                result = result.rename(columns={"emp_gravity": "value"})
                result = result[["geoid", "year", "measure", "value", "moe", "region_type"]]

                all_frames.append(result)
                log.info("Year %d complete: %d rows (%.1f sec)",
                         year, len(result), time.time() - yt0)

            if not all_frames:
                return RunResult(success=False, error="No data produced",
                                 duration_sec=time.time() - t0)

            combined = pd.concat(all_frames, ignore_index=True)
            combined = combined.sort_values(["geoid", "year"]).reset_index(drop=True)

            filename = build_file_name(
                coverage_area="va", data_source="lodes",
                years=years, title="employment_access",
                geographies=["county", "tract"],
            ) + ".csv.xz"

            out_path = write_data(combined, DIST_DIR / filename,
                                  census_standardize=True)
            log.info("Wrote %d rows to %s", len(combined), out_path)

            return RunResult(success=True, rows=len(combined),
                             output_path=str(out_path),
                             duration_sec=time.time() - t0)

    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        return RunResult(success=False, error=str(e),
                         duration_sec=time.time() - t0)


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
