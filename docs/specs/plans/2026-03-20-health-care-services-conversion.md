# Health Care Services FCA Pipeline Conversion

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert 9 R-based Health Care Services floating catchment area pipelines to Python using a shared module and `sdc_core.catchment`.

**Architecture:** A shared `compute_service_access.py` module handles the common FCA workflow (load providers → snap to BG → build cost matrix → run 3 FCA variants → aggregate → output). Each pipeline gets a thin `ingest.py` that calls the shared module with pipeline-specific config (provider file, capacity column, population variables, measure prefix). All 9 pipelines produce identical output structure.

**Tech Stack:** sdc_core.catchment (already implemented), geopandas (for GeoJSON), sdc_core.census (ACS population), pandas, numpy.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `health/Health Care Services/code/compute_service_access.py` | CREATE — shared FCA computation module |
| `health/Health Care Services/code/test_compute_service_access.py` | CREATE — unit tests for shared module |
| `health/Health Care Services/Dentists/Service Catchment Scores/code/distribution/ingest.py` | CREATE — thin config + call to shared module |
| `health/Health Care Services/Dentists/Service Catchment Scores/pipeline.yaml` | CREATE — pipeline config |
| `health/Health Care Services/EMS/Service Catchment Scores/code/distribution/ingest.py` | CREATE |
| `health/Health Care Services/EMS/Service Catchment Scores/pipeline.yaml` | CREATE |
| `health/Health Care Services/Drug and Rehab/Service Catchment Scores/code/distribution/ingest.py` | CREATE |
| `health/Health Care Services/Drug and Rehab/Service Catchment Scores/pipeline.yaml` | CREATE |
| `health/Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/code/distribution/ingest.py` | CREATE |
| `health/Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/pipeline.yaml` | CREATE |
| `health/Health Care Services/Mental Health/Service Access Scores/code/distribution/ingest.py` | CREATE |
| `health/Health Care Services/Mental Health/Service Access Scores/pipeline.yaml` | CREATE |
| `health/Health Care Services/Physicians/Primary Care/Service Access Scores/code/distribution/ingest.py` | CREATE |
| `health/Health Care Services/Physicians/Primary Care/Service Access Scores/pipeline.yaml` | CREATE |
| `health/Health Care Services/Physicians/OB-GYN/Service Access Scores/code/distribution/ingest.py` | CREATE |
| `health/Health Care Services/Physicians/OB-GYN/Service Access Scores/pipeline.yaml` | CREATE |
| `health/Health Care Services/Physicians/Pediatric/Service Access Scores/code/distribution/ingest.py` | CREATE |
| `health/Health Care Services/Physicians/Pediatric/Service Access Scores/pipeline.yaml` | CREATE |
| `health/Health Care Services/Urgent Care Centers/Service Access Scores/code/distribution/ingest.py` | CREATE |
| `health/Health Care Services/Urgent Care Centers/Service Access Scores/pipeline.yaml` | CREATE |

## Pipeline Configuration Reference

Each pipeline varies only in these parameters:

| Pipeline | Provider GeoJSON | Capacity Col | Population | Measure Prefix | Data Source | Years |
|----------|-----------------|--------------|------------|----------------|-------------|-------|
| Dentists | `ncr_webmd_2022_dentists_points.geojson` | `doctors` | total pop | `dent` | webmd | 2022 |
| EMS | `ncr_hifld_2022_ems_points.geojson` | 1 (count) | total pop | `ems` | hifld | 2022 |
| Drug & Rehab | `ncr_samhsa_2022_substance_abuse_points.geojson` | 1 (count) | total pop | `substance` | samhsa | 2022 |
| Hospitals | `ncr_hifld_{year}_hospitals_points.geojson` | 1 (count) | total pop | `hosp` | hifld | 2015-2022 |
| Mental Health | `ncr_samhsa_2022_mental_health_points.geojson` | 1 (count) | total pop | `mental` | samhsa | 2022 |
| Primary Care | `ncr_webmd_2022_primary_care_points.geojson` | `doctors` | total pop | `primcare` | webmd | 2022 |
| OB-GYN | `ncr_webmd_2022_obgyn_points.geojson` | `doctors` | female 14+ | `obgyn` | webmd | 2022 |
| Pediatric | `ncr_webmd_2022_pediatric_points.geojson` | `doctors` | ages 0-17 | `peds` | webmd | 2022 |
| Urgent Care | `ncr_gmap_2022_urgent_care_points.geojson` | 1 (count) | total pop | `urgent` | gmap | 2022 |

## FCA Parameters (same for all 9 pipelines)

All pipelines compute 3 FCA variants:

| Variant | Weight | Scale | normalize_weight | return_type |
|---------|--------|-------|-------------------|-------------|
| 2SFCA | `30.0` (binary threshold) | — | False | 1000 |
| E2SFCA | `[(10, 0.962), (20, 0.704), (30, 0.377), (60, 0.042)]` | — | False | 1000 |
| 3SFCA | `"gaussian"` | `20 / sqrt(2)` | True | 1000 |

## ACS Population Variables

| Population Type | ACS Variables (B01001) | Used By |
|----------------|----------------------|---------|
| Total pop | `B01001_001` (total) | Dentists, EMS, Drug/Rehab, Hospitals, Mental Health, Primary Care, Urgent Care |
| Female 14+ | `B01001_030` through `B01001_049` (female 15-85+) | OB-GYN |
| Ages 0-17 | `B01001_003`-`B01001_006` + `B01001_027`-`B01001_030` (male+female under 18) | Pediatric |

---

### Task 1: Shared compute_service_access.py Module

**Files:**
- Create: `health/Health Care Services/code/compute_service_access.py`
- Create: `health/Health Care Services/code/test_compute_service_access.py`

This is the core module that all 9 pipelines will call. It handles:
1. Loading provider GeoJSON and snapping to nearest BG
2. Loading BG-to-BG travel times
3. Building the cost matrix (consumer BGs × provider locations)
4. Running 3 FCA variants via `sdc_core.catchment.catchment_ratio`
5. Computing additional measures (provider count per BG, nearest-10 travel time stats)
6. Aggregating BG → tract → county → health district

- [ ] **Step 1: Write tests for provider loading and BG snapping**

Create `health/Health Care Services/code/test_compute_service_access.py`:

```python
"""Tests for compute_service_access shared module."""

import json
import numpy as np
import pandas as pd
import pytest
from pathlib import Path
from numpy.testing import assert_allclose


@pytest.fixture
def tmp_geojson(tmp_path):
    """Create a minimal provider GeoJSON file."""
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"ID": "l1", "address": "123 Main St", "doctors": 3},
                "geometry": {"type": "Point", "coordinates": [-77.0, 38.9]},
            },
            {
                "type": "Feature",
                "properties": {"ID": "l2", "address": "456 Oak Ave", "doctors": 1},
                "geometry": {"type": "Point", "coordinates": [-77.1, 38.8]},
            },
        ],
    }
    path = tmp_path / "providers.geojson"
    path.write_text(json.dumps(geojson))
    return path


@pytest.fixture
def tmp_centroids(tmp_path):
    """Create a minimal BG centroids CSV."""
    df = pd.DataFrame({
        "geoid": ["510590101001", "510590101002", "510590102001"],
        "lat": [38.9, 38.85, 38.8],
        "lon": [-77.0, -77.05, -77.1],
    })
    path = tmp_path / "bg_centroids_2020.csv"
    df.to_csv(path, index=False)
    return path


class TestLoadProviders:
    def test_load_and_snap(self, tmp_geojson, tmp_centroids):
        from compute_service_access import load_providers
        providers = load_providers(
            tmp_geojson, tmp_centroids, capacity_col="doctors",
        )
        assert len(providers) == 2
        assert "bg_geoid" in providers.columns
        assert "capacity" in providers.columns
        assert providers["capacity"].sum() == 4  # 3 + 1

    def test_load_no_capacity_col_defaults_to_one(self, tmp_geojson, tmp_centroids):
        from compute_service_access import load_providers
        providers = load_providers(
            tmp_geojson, tmp_centroids, capacity_col=None,
        )
        assert providers["capacity"].sum() == 2  # 1 + 1


class TestBuildCostMatrix:
    def test_shape(self):
        from compute_service_access import build_cost_matrix
        consumer_geoids = np.array(["510590101001", "510590101002"])
        provider_bgs = np.array(["510590101001", "510590102001"])
        travel_times = pd.DataFrame({
            "bg_orig": ["510590101001", "510590101001", "510590101002", "510590101002"],
            "bg_dest": ["510590101001", "510590102001", "510590101001", "510590102001"],
            "time_mins": [0.0, 10.0, 12.0, 8.0],
        })
        cost = build_cost_matrix(consumer_geoids, provider_bgs, travel_times)
        assert cost.shape == (2, 2)
        assert_allclose(cost[0, 0], 0.0)
        assert_allclose(cost[0, 1], 10.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest "health/Health Care Services/code/test_compute_service_access.py" -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement compute_service_access.py**

Create `health/Health Care Services/code/compute_service_access.py`:

```python
"""Shared module for Health Care Services floating catchment area pipelines.

All 9 service access pipelines (Dentists, EMS, Drug/Rehab, Hospitals,
Mental Health, Primary Care, OB-GYN, Pediatric, Urgent Care) share this
common workflow:

1. Load provider locations from GeoJSON → snap to nearest block group
2. Load ACS population at block group level
3. Build cost matrix from pre-computed BG-to-BG travel times
4. Run 3 FCA variants (2SFCA, E2SFCA, 3SFCA) via sdc_core.catchment
5. Compute supplementary measures (provider count, nearest-N travel stats)
6. Aggregate BG → tract → county → health district
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
# so module_scale = 20/sqrt(2) ≈ 14.14 to match R's exp(-(t/20)^2) if R used that form.
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
            "data_method": "observed",
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
                "data_method": "observed",
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest "health/Health Care Services/code/test_compute_service_access.py" -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/ads7fg/git/sdc-monorepo
git add "health/Health Care Services/code/compute_service_access.py" \
        "health/Health Care Services/code/test_compute_service_access.py"
git commit -m "feat(health): add shared compute_service_access module for FCA pipelines"
```

---

### Task 2: Dentists Pipeline (first pipeline — validates the pattern)

**Files:**
- Create: `health/Health Care Services/Dentists/Service Catchment Scores/code/distribution/ingest.py`
- Create: `health/Health Care Services/Dentists/Service Catchment Scores/pipeline.yaml`

- [ ] **Step 1: Create pipeline.yaml**

```yaml
name: dentists_access_scores
version: "1.0.0"
title: "Dental Service Accessibility (FCA)"
description: >-
  Floating catchment area analysis measuring dental service accessibility
  at block group level using travel times. Computes 2SFCA, E2SFCA, and
  3SFCA variants with provider counts from WebMD dental directory.

sources:
  providers:
    type: geojson
    description: "WebMD Dental Directory geocoded locations"
    file: "data/distribution/ncr_webmd_2022_dentists_points.geojson"
    capacity_col: "doctors"

output:
  path: data/distribution
  geographies: [block_group, tract, county, health_district]
  years: [2022]
  coverage_areas: [va, ncr]
```

- [ ] **Step 2: Create ingest.py**

```python
"""Ingest dental service accessibility scores for VA and NCR.

Uses WebMD dental directory locations, ACS total population at block group
level, and pre-computed BG-to-BG travel times to compute 2SFCA, E2SFCA,
and 3SFCA access scores.
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sdc_core.census import CensusClient
from sdc_core.log import get_logger
from sdc_core.result import RunResult

# Add shared module to path
HCS_DIR = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HCS_DIR / "code"))
from compute_service_access import (
    load_providers,
    load_travel_times,
    run_fca_variants,
    aggregate_and_output,
)

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data" / "distribution"

log = get_logger("dentists.ingest")

# NCR county FIPS
NCR_COUNTIES = {
    "51059", "51600", "51610", "51107", "51013", "51510",
    "51683", "51685", "51153",
    "24021", "24031", "24033", "24017",
    "11001",
}

MEASURE_PREFIX = "dent"
DATA_SOURCE = "webmd"
YEAR = 2022
ACS_YEAR = 2021  # ACS 5-year vintage for population


def run() -> list[RunResult]:
    t0 = time.time()
    results = []

    try:
        config = yaml.safe_load((TOPIC_DIR / "pipeline.yaml").read_text())

        # Load providers
        geojson_path = TOPIC_DIR / config["sources"]["providers"]["file"]
        capacity_col = config["sources"]["providers"].get("capacity_col", "doctors")
        providers = load_providers(geojson_path, capacity_col=capacity_col)
        log.info("Loaded %d provider locations", len(providers))

        # Load travel times
        travel_times = load_travel_times()

        # Fetch ACS total population at BG level
        census = CensusClient()
        pop_data = census.get_acs_multi(
            variables={"total_pop": "B01001_001"},
            year=ACS_YEAR,
            geography="block group",
            state="51",  # VA
        )

        consumer_geoids = pop_data["geoid"].values
        consumer_pop = pop_data["total_pop"].values.astype(float)

        # --- VA ---
        va_mask = np.array([g.startswith("51") for g in consumer_geoids])
        va_result = run_fca_variants(
            consumer_geoids[va_mask], consumer_pop[va_mask],
            providers[providers["bg_geoid"].str.startswith("51")],
            travel_times, MEASURE_PREFIX,
        )
        va_path = aggregate_and_output(
            va_result, MEASURE_PREFIX, YEAR, "va", DATA_SOURCE, DIST_DIR,
            pop_col_for_weighting=consumer_pop[va_mask],
        )
        results.append(RunResult(
            success=True, rows=len(va_result),
            output_path=str(va_path), duration_sec=time.time() - t0,
        ))

        # --- NCR ---
        ncr_mask = np.array([g[:5] in NCR_COUNTIES for g in consumer_geoids])
        if ncr_mask.any():
            ncr_providers = providers[providers["bg_geoid"].str[:5].isin(NCR_COUNTIES)]
            ncr_result = run_fca_variants(
                consumer_geoids[ncr_mask], consumer_pop[ncr_mask],
                ncr_providers, travel_times, MEASURE_PREFIX,
            )
            ncr_path = aggregate_and_output(
                ncr_result, MEASURE_PREFIX, YEAR, "ncr", DATA_SOURCE, DIST_DIR,
                pop_col_for_weighting=consumer_pop[ncr_mask],
            )
            results.append(RunResult(
                success=True, rows=len(ncr_result),
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
            log.info("OK: %d rows → %s", r.rows, r.output_path)
        else:
            log.error("FAIL: %s", r.error)
    if any(not r.success for r in results):
        raise SystemExit(1)
```

- [ ] **Step 3: Verify the ingest runs** (may need Census API key)

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run python "health/Health Care Services/Dentists/Service Catchment Scores/code/distribution/ingest.py" 2>&1 | tail -20`

If it fails due to missing API key or data, verify the code is syntactically correct:
`cd /Users/ads7fg/git/sdc-monorepo && uv run python -c "import sys; sys.path.insert(0, 'health/Health Care Services/code'); from compute_service_access import load_providers; print('OK')"`

- [ ] **Step 4: Commit**

```bash
cd /Users/ads7fg/git/sdc-monorepo
git add "health/Health Care Services/Dentists/Service Catchment Scores/code/distribution/ingest.py" \
        "health/Health Care Services/Dentists/Service Catchment Scores/pipeline.yaml"
git commit -m "feat(health/dentists): convert to Python FCA pipeline using shared module"
```

---

### Task 3: Remaining 7 Standard Pipelines (total pop denominator)

These all use total population as the denominator. Each gets a thin ingest.py + pipeline.yaml following the exact Dentists pattern. The only differences are: provider GeoJSON path, capacity_col, measure_prefix, data_source.

**Files:** Create ingest.py + pipeline.yaml for each of:

| Pipeline | Directory | GeoJSON | capacity_col | prefix | source |
|----------|-----------|---------|-------------|--------|--------|
| EMS | `EMS/Service Catchment Scores` | `ncr_hifld_2022_ems_points.geojson` | None (count=1) | `ems` | `hifld` |
| Drug/Rehab | `Drug and Rehab/Service Catchment Scores` | `ncr_samhsa_2022_substance_abuse_points.geojson` | None | `substance` | `samhsa` |
| Hospitals | `Hospitals and Emergency Rooms/Service Access Scores` | `ncr_hifld_2022_hospitals_points.geojson` | None | `hosp` | `hifld` |
| Mental Health | `Mental Health/Service Access Scores` | `ncr_samhsa_2022_mental_health_points.geojson` | None | `mental` | `samhsa` |
| Primary Care | `Physicians/Primary Care/Service Access Scores` | `ncr_webmd_2022_primary_care_points.geojson` | `doctors` | `primcare` | `webmd` |
| Urgent Care | `Urgent Care Centers/Service Access Scores` | `ncr_gmap_2022_urgent_care_points.geojson` | None | `urgent` | `gmap` |

- [ ] **Step 1: Create all 6 pipeline.yaml files**

Each follows the Dentists pattern with the values from the table above. For Hospitals, note the multi-year support (2015-2022) but start with 2022 only.

- [ ] **Step 2: Create all 6 ingest.py files**

Each is a copy of the Dentists ingest.py with only these lines changed:
- `MEASURE_PREFIX = "..."`
- `DATA_SOURCE = "..."`
- `YEAR = 2022`
- Provider GeoJSON path in pipeline.yaml
- `capacity_col` in pipeline.yaml

- [ ] **Step 3: Verify one of them imports correctly**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run python -c "
import sys; sys.path.insert(0, 'health/Health Care Services/code')
from compute_service_access import load_providers, run_fca_variants
print('OK')
"`

- [ ] **Step 4: Commit**

```bash
cd /Users/ads7fg/git/sdc-monorepo
git add "health/Health Care Services/EMS/" \
        "health/Health Care Services/Drug and Rehab/" \
        "health/Health Care Services/Hospitals and Emergency Rooms/" \
        "health/Health Care Services/Mental Health/" \
        "health/Health Care Services/Physicians/Primary Care/" \
        "health/Health Care Services/Urgent Care Centers/"
git commit -m "feat(health): convert 6 standard service access pipelines to Python"
```

---

### Task 4: OB-GYN Pipeline (female 14+ population)

**Files:**
- Create: `health/Health Care Services/Physicians/OB-GYN/Service Access Scores/code/distribution/ingest.py`
- Create: `health/Health Care Services/Physicians/OB-GYN/Service Access Scores/pipeline.yaml`

This pipeline differs from the standard pattern because it uses **female population age 14+** as the consumer denominator instead of total population.

- [ ] **Step 1: Create pipeline.yaml**

```yaml
name: obgyn_access_scores
version: "1.0.0"
title: "OB-GYN Service Accessibility (FCA)"
description: >-
  Floating catchment area analysis measuring OB-GYN accessibility using
  female population age 15+ as consumer demand.

sources:
  providers:
    type: geojson
    description: "WebMD OB-GYN directory geocoded locations"
    file: "data/distribution/ncr_webmd_2022_obgyn_points.geojson"
    capacity_col: "doctors"

population:
  type: acs
  table: B01001
  description: "Female population age 15+"
  variables:
    # Female age 15-17 through 85+: B01001_030 through B01001_049
    female_15_17: "B01001_030"
    female_18_19: "B01001_031"
    female_20: "B01001_032"
    female_21: "B01001_033"
    female_22_24: "B01001_034"
    female_25_29: "B01001_035"
    female_30_34: "B01001_036"
    female_35_39: "B01001_037"
    female_40_44: "B01001_038"
    female_45_49: "B01001_039"
    female_50_54: "B01001_040"
    female_55_59: "B01001_041"
    female_60_61: "B01001_042"
    female_62_64: "B01001_043"
    female_65_66: "B01001_044"
    female_67_69: "B01001_045"
    female_70_74: "B01001_046"
    female_75_79: "B01001_047"
    female_80_84: "B01001_048"
    female_85_plus: "B01001_049"

output:
  path: data/distribution
  geographies: [block_group, tract, county, health_district]
  years: [2022]
  coverage_areas: [va, ncr]
```

- [ ] **Step 2: Create ingest.py**

Same structure as Dentists but fetches female 14+ ACS variables and sums them:

```python
"""Ingest OB-GYN service accessibility scores.

Uses female population age 15+ as consumer demand denominator.
"""
# ... same imports and structure as Dentists ...

MEASURE_PREFIX = "obgyn"
DATA_SOURCE = "webmd"
YEAR = 2022
ACS_YEAR = 2021

# ACS B01001 female age 15+ variables
POP_VARIABLES = {f"f_{i}": f"B01001_{i:03d}" for i in range(30, 50)}


def run() -> list[RunResult]:
    # ... same as Dentists but replace total_pop fetch with:
    pop_data = census.get_acs_multi(
        variables=POP_VARIABLES,
        year=ACS_YEAR,
        geography="block group",
        state="51",
    )
    # Sum all female age columns for total female 14+ population
    age_cols = [c for c in pop_data.columns if c.startswith("f_")]
    pop_data["target_pop"] = pop_data[age_cols].sum(axis=1)
    consumer_pop = pop_data["target_pop"].values.astype(float)
    # ... rest same as Dentists using consumer_pop ...
```

- [ ] **Step 3: Commit**

```bash
cd /Users/ads7fg/git/sdc-monorepo
git add "health/Health Care Services/Physicians/OB-GYN/"
git commit -m "feat(health/obgyn): convert to Python FCA with female 14+ population"
```

---

### Task 5: Pediatric Pipeline (ages 0-17 population)

**Files:**
- Create: `health/Health Care Services/Physicians/Pediatric/Service Access Scores/code/distribution/ingest.py`
- Create: `health/Health Care Services/Physicians/Pediatric/Service Access Scores/pipeline.yaml`

Uses **population ages 0-17** (male + female under 18) as consumer denominator.

- [ ] **Step 1: Create pipeline.yaml and ingest.py**

```python
# ACS B01001 ages 0-17: male under 5 through 15-17 + female under 5 through 15-17
POP_VARIABLES = {
    "male_under_5": "B01001_003",
    "male_5_9": "B01001_004",
    "male_10_14": "B01001_005",
    "male_15_17": "B01001_006",
    "female_under_5": "B01001_027",
    "female_5_9": "B01001_028",
    "female_10_14": "B01001_029",
    "female_15_17": "B01001_030",
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/ads7fg/git/sdc-monorepo
git add "health/Health Care Services/Physicians/Pediatric/"
git commit -m "feat(health/pediatric): convert to Python FCA with ages 0-17 population"
```

---

### Task 6: Run One Pipeline End-to-End and Push

- [ ] **Step 1: Run the Dentists pipeline to verify full workflow**

```bash
cd /Users/ads7fg/git/sdc-monorepo
uv run python "health/Health Care Services/Dentists/Service Catchment Scores/code/distribution/ingest.py" 2>&1 | tail -30
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/ads7fg/git/sdc-monorepo
uv run pytest "health/Health Care Services/code/test_compute_service_access.py" -v
```

- [ ] **Step 3: Push all commits**

```bash
cd /Users/ads7fg/git/sdc-monorepo && git push
```
