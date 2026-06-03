"""Tests for sdc_redistribute."""

import pandas as pd
import pytest

geopandas = pytest.importorskip("geopandas")
shapely = pytest.importorskip("shapely")

from shapely.geometry import box

from sdc_redistribute import redistribute_direct, redistribute_parcels


@pytest.fixture
def source_geo(tmp_path):
    """Two non-overlapping source polygons (left/right halves of a 10x10 square)."""
    gdf = geopandas.GeoDataFrame(
        {"geoid": ["A", "B"]},
        geometry=[box(0, 0, 5, 10), box(5, 0, 10, 10)],
        crs="EPSG:3857",
    )
    path = tmp_path / "source.geojson"
    gdf.to_file(path, driver="GeoJSON")
    return path


@pytest.fixture
def target_geo(tmp_path):
    """Two target polygons (top/bottom halves of the same 10x10 square)."""
    gdf = geopandas.GeoDataFrame(
        {"geoid": ["T1", "T2"]},
        geometry=[box(0, 5, 10, 10), box(0, 0, 10, 5)],
        crs="EPSG:3857",
    )
    path = tmp_path / "target.geojson"
    gdf.to_file(path, driver="GeoJSON")
    return path


@pytest.fixture
def source_df():
    """Source data: polygon A has population 100, polygon B has population 200."""
    return pd.DataFrame(
        {
            "geoid": ["A", "A", "B", "B"],
            "year": [2020, 2020, 2020, 2020],
            "measure": ["total_pop", "young", "total_pop", "young"],
            "value": [100.0, 40.0, 200.0, 80.0],
        }
    )


class TestRedistributeDirect:
    def test_basic_redistribution(self, source_df, source_geo, target_geo):
        """Each target covers half of each source, so values split evenly."""
        result = redistribute_direct(
            source_df=source_df,
            source_geo=source_geo,
            target_geos={"test": target_geo},
            count_cols=["total_pop", "young"],
        )

        assert not result.empty
        assert all(result["measure"].str.endswith("_direct"))

        # Each target polygon overlaps 50% of source A and 50% of source B.
        # T1 gets: 50% of 100 + 50% of 200 = 150 (total_pop)
        # T2 gets: 50% of 100 + 50% of 200 = 150 (total_pop)
        pop = result[result["measure"] == "total_pop_direct"].set_index("geoid")["value"]
        assert pop["T1"] == pytest.approx(150.0, rel=0.01)
        assert pop["T2"] == pytest.approx(150.0, rel=0.01)

    def test_percentage_specs(self, source_df, source_geo, target_geo):
        """Derived percentages are computed after redistribution."""
        result = redistribute_direct(
            source_df=source_df,
            source_geo=source_geo,
            target_geos={"test": target_geo},
            count_cols=["total_pop", "young"],
            pct_specs={"pct_young": ("young", "total_pop")},
        )

        pct = result[result["measure"] == "pct_young_direct"].set_index("geoid")["value"]
        # young/total_pop = (50%*40 + 50%*80) / (50%*100 + 50%*200) = 60/150 = 40%
        assert pct["T1"] == pytest.approx(40.0, rel=0.01)

    def test_multiple_years(self, source_geo, target_geo):
        """Multiple years are processed independently."""
        df = pd.DataFrame(
            {
                "geoid": ["A", "B", "A", "B"],
                "year": [2019, 2019, 2020, 2020],
                "measure": ["pop", "pop", "pop", "pop"],
                "value": [100.0, 200.0, 300.0, 400.0],
            }
        )
        result = redistribute_direct(
            source_df=df,
            source_geo=source_geo,
            target_geos={"test": target_geo},
            count_cols=["pop"],
        )

        assert set(result["year"].unique()) == {2019, 2020}

    def test_rescaling_preserves_totals(self, source_df, source_geo, target_geo):
        """After redistribution, sum of target values matches sum of source values."""
        result = redistribute_direct(
            source_df=source_df,
            source_geo=source_geo,
            target_geos={"test": target_geo},
            count_cols=["total_pop"],
        )

        pop = result[result["measure"] == "total_pop_direct"]
        assert pop["value"].sum() == pytest.approx(300.0, rel=0.01)


class TestRedistributeParcels:
    def test_basic_parcels(self, source_geo, target_geo):
        """Parcel centroids distribute values to target regions."""
        from shapely.geometry import Point

        source_df = pd.DataFrame(
            {
                "geoid": ["A", "B"],
                "year": [2020, 2020],
                "measure": ["pop", "pop"],
                "value": [100.0, 200.0],
            }
        )

        # 4 parcels in source A (left half, x<5), 4 in source B (right half, x>5)
        # 2 from each source in T1 (top, y>5) and 2 in T2 (bottom, y<5)
        # Use EPSG:3857 coords directly to match source/target geometries
        parcels = geopandas.GeoDataFrame(
            geometry=[
                Point(1, 2), Point(1, 3),  # A, T2
                Point(1, 7), Point(1, 8),  # A, T1
                Point(6, 2), Point(6, 3),  # B, T2
                Point(6, 7), Point(6, 8),  # B, T1
            ],
            crs="EPSG:3857",
        )

        result = redistribute_parcels(
            source_df=source_df,
            parcel_centroids=parcels,
            source_geo=source_geo,
            target_geos={"test": target_geo},
            count_cols=["pop"],
        )

        assert not result.empty
        assert all(result["measure"].str.endswith("_parcels"))

        pop = result[result["measure"] == "pop_parcels"].set_index("geoid")["value"]
        # Source A (100) has 4 parcels → 25 each. Source B (200) has 4 parcels → 50 each.
        # T1 (top, y>5): 2 from A (50) + 2 from B (100) = 150
        # T2 (bottom, y<5): 2 from A (50) + 2 from B (100) = 150
        assert pop["T1"] == pytest.approx(150.0, rel=0.01)
        assert pop["T2"] == pytest.approx(150.0, rel=0.01)
