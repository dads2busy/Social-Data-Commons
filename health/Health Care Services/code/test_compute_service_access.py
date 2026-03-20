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

    def test_missing_pair_gets_large_value(self):
        from compute_service_access import build_cost_matrix
        consumer_geoids = np.array(["510590101001", "510590101002"])
        provider_bgs = np.array(["510590102001"])
        travel_times = pd.DataFrame({
            "bg_orig": ["510590101001"],
            "bg_dest": ["510590102001"],
            "time_mins": [15.0],
        })
        cost = build_cost_matrix(consumer_geoids, provider_bgs, travel_times)
        assert cost.shape == (2, 1)
        assert_allclose(cost[0, 0], 15.0)
        assert cost[1, 0] == 1e6  # unreachable


class TestComputeProviderCount:
    def test_counts(self):
        from compute_service_access import compute_provider_count
        consumer_geoids = np.array(["510590101001", "510590101002", "510590102001"])
        providers = pd.DataFrame({
            "bg_geoid": ["510590101001", "510590101001", "510590102001"],
            "capacity": [3, 2, 1],
        })
        result = compute_provider_count(consumer_geoids, providers)
        assert result["510590101001"] == 5
        assert result["510590101002"] == 0
        assert result["510590102001"] == 1


class TestComputeNearestNStats:
    def test_basic(self):
        from compute_service_access import compute_nearest_n_stats
        consumer_geoids = np.array(["510590101001", "510590101002"])
        provider_bgs = {"510590101001", "510590102001"}
        travel_times = pd.DataFrame({
            "bg_orig": [
                "510590101001", "510590101002", "510590101002",
            ],
            "bg_dest": [
                "510590102001", "510590101001", "510590102001",
            ],
            "time_mins": [10.0, 12.0, 8.0],
        })
        mean_s, median_s = compute_nearest_n_stats(
            consumer_geoids, provider_bgs, travel_times, n=2,
        )
        # Consumer 510590101001: self=0.0, to 510590102001=10.0 -> mean=5.0
        assert_allclose(mean_s["510590101001"], 5.0)
        # Consumer 510590101002: to 510590101001=12.0, to 510590102001=8.0 -> mean=10.0
        assert_allclose(mean_s["510590101002"], 10.0)


class TestHaversine:
    def test_same_point_is_zero(self):
        from compute_service_access import _haversine_km
        d = _haversine_km(np.array([38.9]), np.array([-77.0]), 38.9, -77.0)
        assert_allclose(d, 0.0, atol=1e-10)

    def test_known_distance(self):
        from compute_service_access import _haversine_km
        # DC to Baltimore ~ 56 km
        d = _haversine_km(np.array([38.9072]), np.array([-77.0369]), 39.2904, -76.6122)
        assert 50 < d[0] < 60
