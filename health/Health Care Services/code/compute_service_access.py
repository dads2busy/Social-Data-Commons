"""Shared module for Health Care Services floating catchment area pipelines.

All 9 service access pipelines (Dentists, EMS, Drug/Rehab, Hospitals,
Mental Health, Primary Care, OB-GYN, Pediatric, Urgent Care) share this
common workflow:

1. Load provider locations from GeoJSON -> snap to nearest block group
2. Load ACS population at block group level
3. Build cost matrix from pre-computed BG-to-BG travel times
4. Run 3 FCA variants (2SFCA, E2SFCA, 3SFCA) via sdc_core.catchment
5. Compute supplementary measures (provider count, nearest-N travel stats)
6. Aggregate BG -> tract -> county -> health district
7. Write standard long-format output
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from sdc_core.catchment import catchment_ratio
from sdc_core.geo import aggregate_up
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name

log = get_logger("health_care_services")

REPO_DIR = Path(__file__).resolve().parents[3]
TRAVEL_TIMES_DIR = REPO_DIR / "geographies" / "osrm" / "travel_times"
CENTROIDS_PATH = REPO_DIR / "geographies" / "osrm" / "bg_centroids_2020.csv"
CROSSWALK_PATH = (
    REPO_DIR / "geographies" / "VA" / "State Geographies" / "Health Districts"
    / "2020" / "data" / "distribution" / "va_ct_to_hd_crosswalk.csv"
)

TRAVEL_TIME_FIPS = ["10", "11", "21", "24", "37", "47", "51", "54"]

# E2SFCA stepped weights (matches R legacy: 10min=0.962, 20min=0.704, 30min=0.377, 60min=0.042)
E2SFCA_WEIGHTS = [(10, 0.962), (20, 0.704), (30, 0.377), (60, 0.042)]

# 3SFCA Gaussian scale: R code used scale=20. Module Gaussian is exp(-t^2/(2*s^2)),
# so module_scale = 20/sqrt(2) ~ 14.14 to match R's exp(-(t/20)^2) if R used that form.
# However, R catchment package uses the standard Gaussian with scale=20 directly.
GAUSSIAN_SCALE = 20.0


def _haversine_km(lat1: np.ndarray, lon1: np.ndarray, lat2: float, lon2: float) -> np.ndarray:
    """Vectorized haversine distance in km."""
    R = 6371.0
    rlat1, rlat2 = np.radians(lat1), np.radians(lat2)
    dlat = rlat2 - rlat1
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(rlat1) * np.cos(rlat2) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def load_providers(
    geojson_path: Path,
    centroids_path: Path = CENTROIDS_PATH,
    capacity_col: str | None = "doctors",
) -> pd.DataFrame:
    """Load provider GeoJSON, extract lat/lon, snap to nearest block group.

    Parameters
    ----------
    geojson_path : Path
        GeoJSON FeatureCollection with Point geometries.
    centroids_path : Path
        CSV with geoid, lat, lon columns for block group centroids.
    capacity_col : str or None
        Property name for provider capacity (e.g., "doctors", "beds").
        If None, each provider location gets capacity=1.

    Returns
    -------
    DataFrame
        Columns: lid, bg_geoid, capacity, lat, lon
    """
    gdf = gpd.read_file(geojson_path)
    centroids = pd.read_csv(centroids_path, dtype={"geoid": str})

    bg_geoids = centroids["geoid"].values
    bg_lats = centroids["lat"].values
    bg_lons = centroids["lon"].values

    lids = []
    bg_assignments = []
    capacities = []
    lats = []
    lons = []

    for _, row in gdf.iterrows():
        coords = row.geometry
        lat, lon = coords.y, coords.x

        dists = _haversine_km(bg_lats, bg_lons, lat, lon)
        nearest_bg = bg_geoids[np.argmin(dists)]

        lid = row.get("ID", row.name)
        cap = row.get(capacity_col, 1) if capacity_col else 1
        if pd.isna(cap):
            cap = 1

        lids.append(lid)
        bg_assignments.append(nearest_bg)
        capacities.append(int(cap))
        lats.append(lat)
        lons.append(lon)

    return pd.DataFrame({
        "lid": lids,
        "bg_geoid": bg_assignments,
        "capacity": capacities,
        "lat": lats,
        "lon": lons,
    })


def load_travel_times(state_fips: list[str] | None = None) -> pd.DataFrame:
    """Load pre-computed BG-to-BG travel times from parquet files."""
    fips_list = state_fips or TRAVEL_TIME_FIPS
    frames = []
    for fips in fips_list:
        path = TRAVEL_TIMES_DIR / f"bg2bg_{fips}.parquet"
        if path.exists():
            frames.append(pd.read_parquet(path, columns=["bg_orig", "bg_dest", "time_mins"]))
    if not frames:
        raise FileNotFoundError(f"No travel time parquets found in {TRAVEL_TIMES_DIR}")
    tt = pd.concat(frames, ignore_index=True)
    tt = tt.drop_duplicates(subset=["bg_orig", "bg_dest"]).reset_index(drop=True)
    log.info("Loaded %d travel time pairs", len(tt))
    return tt


def build_cost_matrix(
    consumer_geoids: np.ndarray,
    provider_bgs: np.ndarray,
    travel_times: pd.DataFrame,
) -> np.ndarray:
    """Build a dense cost matrix from long-format travel times.

    Parameters
    ----------
    consumer_geoids : array of consumer BG GEOIDs
    provider_bgs : array of provider BG GEOIDs (one per aggregated provider location)
    travel_times : DataFrame with bg_orig, bg_dest, time_mins

    Returns
    -------
    ndarray of shape (n_consumers, n_providers), values in minutes.
    Unreachable pairs get 1e6 (effectively infinite cost).
    """
    n_consumers = len(consumer_geoids)
    n_providers = len(provider_bgs)
    cost = np.full((n_consumers, n_providers), 1e6, dtype=float)

    # Build lookup dict for fast access
    provider_bg_set = set(provider_bgs)
    tt_relevant = travel_times[travel_times["bg_dest"].isin(provider_bg_set)]
    tt_dict = {}
    for _, row in tt_relevant.iterrows():
        tt_dict[(row["bg_orig"], row["bg_dest"])] = row["time_mins"]

    consumer_idx = {g: i for i, g in enumerate(consumer_geoids)}

    for j, bg in enumerate(provider_bgs):
        for orig, i in consumer_idx.items():
            if orig == bg:
                cost[i, j] = 0.0
            else:
                t = tt_dict.get((orig, bg))
                if t is not None:
                    cost[i, j] = t

    return cost


def compute_nearest_n_stats(
    consumer_geoids: np.ndarray,
    provider_bgs: set[str],
    travel_times: pd.DataFrame,
    n: int = 10,
) -> tuple[pd.Series, pd.Series]:
    """Compute mean and median travel time to nearest N providers.

    Returns (mean_series, median_series) indexed by consumer GEOID.
    """
    tt_to_providers = travel_times[travel_times["bg_dest"].isin(provider_bgs)]

    # Add self-pairs for BGs that contain providers
    consumer_set = set(consumer_geoids)
    self_bgs = provider_bgs & consumer_set
    if self_bgs:
        self_df = pd.DataFrame({
            "bg_orig": list(self_bgs),
            "bg_dest": list(self_bgs),
            "time_mins": 0.0,
        })
        tt_to_providers = pd.concat([tt_to_providers, self_df], ignore_index=True)

    # For each consumer BG, get the N smallest travel times
    sorted_tt = tt_to_providers.sort_values("time_mins")
    nearest = sorted_tt.groupby("bg_orig").head(n)

    mean_vals = nearest.groupby("bg_orig")["time_mins"].mean()
    median_vals = nearest.groupby("bg_orig")["time_mins"].median()

    mean_result = pd.Series(np.nan, index=consumer_geoids)
    median_result = pd.Series(np.nan, index=consumer_geoids)
    for geoid in consumer_geoids:
        if geoid in mean_vals.index:
            mean_result[geoid] = mean_vals[geoid]
        if geoid in median_vals.index:
            median_result[geoid] = median_vals[geoid]

    return mean_result, median_result


def compute_provider_count(
    consumer_geoids: np.ndarray,
    providers: pd.DataFrame,
) -> pd.Series:
    """Count total provider capacity within each block group."""
    cap_by_bg = providers.groupby("bg_geoid")["capacity"].sum()
    result = pd.Series(0, index=consumer_geoids, dtype=int)
    matched = result.index.isin(cap_by_bg.index)
    result.loc[matched] = cap_by_bg.reindex(result.index[matched]).values
    return result


def run_fca_variants(
    consumer_geoids: np.ndarray,
    consumer_pop: np.ndarray,
    providers: pd.DataFrame,
    travel_times: pd.DataFrame,
    measure_prefix: str,
) -> pd.DataFrame:
    """Run 2SFCA, E2SFCA, and 3SFCA for a set of providers.

    Parameters
    ----------
    consumer_geoids : array of consumer BG GEOIDs
    consumer_pop : array of population values per consumer BG
    providers : DataFrame with lid, bg_geoid, capacity columns
    travel_times : DataFrame with bg_orig, bg_dest, time_mins
    measure_prefix : str, e.g. "dent", "hosp", "primcare"

    Returns
    -------
    DataFrame with columns: geoid + one column per measure
    """
    # Aggregate providers by BG (sum capacities for co-located providers)
    prov_agg = providers.groupby("bg_geoid")["capacity"].sum().reset_index()
    provider_bgs = prov_agg["bg_geoid"].values
    provider_caps = prov_agg["capacity"].values.astype(float)

    consumers_df = pd.DataFrame({"geoid": consumer_geoids, "value": consumer_pop})
    providers_df = pd.DataFrame({"geoid": provider_bgs, "value": provider_caps})

    cost = build_cost_matrix(consumer_geoids, provider_bgs, travel_times)

    log.info("Running 2SFCA (threshold=30)...")
    sfca2 = catchment_ratio(
        consumers_df, providers_df, cost,
        weight=30.0, return_type=1000,
    )

    log.info("Running E2SFCA (stepped weights)...")
    e2sfca = catchment_ratio(
        consumers_df, providers_df, cost,
        weight=E2SFCA_WEIGHTS, return_type=1000,
    )

    log.info("Running 3SFCA (Gaussian, scale=%s)...", GAUSSIAN_SCALE)
    sfca3 = catchment_ratio(
        consumers_df, providers_df, cost,
        weight="gaussian", scale=GAUSSIAN_SCALE,
        normalize_weight=True, return_type=1000,
    )

    # Supplementary measures
    provider_bg_set = set(provider_bgs)
    cnt = compute_provider_count(consumer_geoids, providers)
    near_mean, near_median = compute_nearest_n_stats(
        consumer_geoids, provider_bg_set, travel_times,
    )

    result = pd.DataFrame({
        "geoid": consumer_geoids,
        f"{measure_prefix}_cnt": cnt.values,
        f"{measure_prefix}_near_10_mean": near_mean.values,
        f"{measure_prefix}_near_10_median": near_median.values,
        f"{measure_prefix}_2sfca": sfca2.values,
        f"{measure_prefix}_e2sfca": e2sfca.values,
        f"{measure_prefix}_3sfca": sfca3.values,
    })

    log.info(
        "FCA results: %d BGs, 2sfca mean=%.4f, e2sfca mean=%.4f, 3sfca mean=%.4f",
        len(result),
        result[f"{measure_prefix}_2sfca"].mean(),
        result[f"{measure_prefix}_e2sfca"].mean(),
        result[f"{measure_prefix}_3sfca"].mean(),
    )

    return result


def aggregate_bg_to_levels(
    bg_data: pd.DataFrame,
    measure_prefix: str,
    year: int,
    consumer_pop: np.ndarray | None = None,
) -> pd.DataFrame:
    """Aggregate BG-level measures to tract and county, returning long-format DataFrame.

    Does NOT aggregate to health districts — that is the responsibility of prepare.py.

    Parameters
    ----------
    bg_data : DataFrame with geoid + measure columns (BG level)
    measure_prefix : str for identifying measure types
    year : data year
    consumer_pop : population array for weighted mean (same order as bg_data rows)

    Returns
    -------
    Long-format DataFrame with columns: geoid, year, measure, value, moe, region_type, data_method
    Includes BG + tract + county rows.
    """
    measures = [c for c in bg_data.columns if c != "geoid"]

    count_measures = [m for m in measures if m.endswith("_cnt")]
    time_measures = [m for m in measures if "near_10" in m]
    fca_measures = [m for m in measures if m.endswith(("_2sfca", "_e2sfca", "_3sfca"))]

    all_frames = []

    # BG level
    for measure in measures:
        frame = pd.DataFrame({
            "geoid": bg_data["geoid"],
            "year": year,
            "measure": measure,
            "value": bg_data[measure],
            "moe": pd.NA,
            "region_type": "block_group",
            "data_method": "modeled" if measure in fca_measures else "observed",
        })
        all_frames.append(frame)

    # Aggregate to tract and county
    bg = bg_data.copy()
    bg["tract_geoid"] = bg["geoid"].str[:11]
    bg["county_geoid"] = bg["geoid"].str[:5]

    for level, geoid_col in [("tract", "tract_geoid"), ("county", "county_geoid")]:
        valid = bg[bg[geoid_col].notna()]
        for measure in measures:
            if measure in count_measures:
                agged = valid.groupby(geoid_col)[measure].sum().reset_index()
            elif measure in time_measures:
                agged = valid.groupby(geoid_col)[measure].mean().reset_index()
            elif measure in fca_measures and consumer_pop is not None:
                valid_with_pop = valid.copy()
                valid_with_pop["_pop"] = consumer_pop[: len(valid_with_pop)]
                grouped = valid_with_pop.groupby(geoid_col).apply(
                    lambda g: np.average(g[measure], weights=g["_pop"]) if g["_pop"].sum() > 0 else 0.0,
                    include_groups=False,
                ).reset_index(name=measure)
                agged = grouped
            else:
                agged = valid.groupby(geoid_col)[measure].mean().reset_index()

            frame = pd.DataFrame({
                "geoid": agged[geoid_col],
                "year": year,
                "measure": measure,
                "value": agged[measure],
                "moe": pd.NA,
                "region_type": level,
                "data_method": "modeled" if measure in fca_measures else "observed",
            })
            all_frames.append(frame)

    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)
    return combined


def aggregate_and_output(
    bg_data: pd.DataFrame,
    measure_prefix: str,
    year: int,
    coverage_area: str,
    data_source: str,
    dist_dir: Path,
    pop_col_for_weighting: np.ndarray | None = None,
) -> Path:
    """Aggregate BG measures to tract/county/HD and write long-format output.

    Legacy convenience function — new pipelines should use aggregate_bg_to_levels
    in ingest.py and handle HD aggregation in prepare.py.

    Parameters
    ----------
    bg_data : DataFrame with geoid + measure columns
    measure_prefix : str for measure naming
    year : data year
    coverage_area : "va" or "ncr"
    data_source : e.g. "webmd", "hifld", "samhsa", "gmap"
    dist_dir : output directory
    pop_col_for_weighting : population array for weighted mean (same order as bg_data)

    Returns
    -------
    Path to output file
    """
    measures = [c for c in bg_data.columns if c != "geoid"]

    # Measures config: which aggregation method for each
    count_measures = [m for m in measures if m.endswith("_cnt")]
    time_measures = [m for m in measures if "near_10" in m]
    fca_measures = [m for m in measures if m.endswith(("_2sfca", "_e2sfca", "_3sfca"))]

    all_frames = []

    # BG level
    for measure in measures:
        frame = pd.DataFrame({
            "geoid": bg_data["geoid"],
            "year": year,
            "measure": measure,
            "value": bg_data[measure],
            "moe": pd.NA,
            "region_type": "block_group",
            "data_method": "modeled" if measure in fca_measures else "observed",
        })
        all_frames.append(frame)

    # Aggregate to higher levels
    xwalk = pd.read_csv(CROSSWALK_PATH, dtype={"ct_geoid": str, "hd_geoid": str})
    county_to_hd = dict(zip(xwalk["ct_geoid"], xwalk["hd_geoid"]))

    bg = bg_data.copy()
    bg["tract_geoid"] = bg["geoid"].str[:11]
    bg["county_geoid"] = bg["geoid"].str[:5]
    bg["hd_geoid"] = bg["county_geoid"].map(county_to_hd)

    for level, geoid_col in [("tract", "tract_geoid"), ("county", "county_geoid"), ("health_district", "hd_geoid")]:
        valid = bg[bg[geoid_col].notna()]
        for measure in measures:
            if measure in count_measures:
                agged = valid.groupby(geoid_col)[measure].sum().reset_index()
            elif measure in time_measures:
                agged = valid.groupby(geoid_col)[measure].mean().reset_index()
            elif measure in fca_measures and pop_col_for_weighting is not None:
                valid_with_pop = valid.copy()
                valid_with_pop["_pop"] = pop_col_for_weighting[: len(valid_with_pop)]
                grouped = valid_with_pop.groupby(geoid_col).apply(
                    lambda g: np.average(g[measure], weights=g["_pop"]) if g["_pop"].sum() > 0 else 0.0,
                    include_groups=False,
                ).reset_index(name=measure)
                agged = grouped
            else:
                agged = valid.groupby(geoid_col)[measure].mean().reset_index()

            frame = pd.DataFrame({
                "geoid": agged[geoid_col],
                "year": year,
                "measure": measure,
                "value": agged[measure],
                "moe": pd.NA,
                "region_type": level,
                "data_method": "modeled" if measure in fca_measures else "observed",
            })
            all_frames.append(frame)

    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

    dist_dir.mkdir(parents=True, exist_ok=True)
    out_name = build_file_name(
        coverage_area=coverage_area,
        data_source=data_source,
        years=[year],
        title=f"access_scores_{measure_prefix}",
        geographies=["health_district", "county", "tract", "block_group"],
    )
    out_path = write_data(combined, dist_dir / f"{out_name}.csv.xz")
    log.info("Wrote %s (%d rows)", out_path.name, len(combined))
    return out_path
