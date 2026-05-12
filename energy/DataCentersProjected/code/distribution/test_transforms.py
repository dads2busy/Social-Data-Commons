"""Unit tests for IM3 CERF projected data center transforms."""

import pandas as pd
import pytest

from transforms import (
    aggregate_to_counties,
    scenario_label,
    shape_to_point_schema,
)


def test_scenario_label_canonical():
    assert scenario_label("moderate", 50) == "im3_cerf_moderate_50"


def test_scenario_label_extremes():
    assert scenario_label("low", 0) == "im3_cerf_low_0"
    assert scenario_label("higher", 100) == "im3_cerf_higher_100"


def _enriched_rows():
    """Sample of source rows AFTER scenario tagging, VA filter, reproject, centroid, and county FIPS sjoin."""
    return pd.DataFrame({
        "id": ["51_0", "51_1", "51_0", "51_2"],
        "growth_scenario": ["moderate", "moderate", "higher", "moderate"],
        "market_gravity_weight": [50, 50, 100, 50],
        "scenario": [
            "im3_cerf_moderate_50",
            "im3_cerf_moderate_50",
            "im3_cerf_higher_100",
            "im3_cerf_moderate_50",
        ],
        "region": ["virginia"] * 4,
        "geoid": ["51107", "51059", "51107", "51153"],
        "lat": [39.0, 38.9, 39.0, 38.7],
        "lon": [-77.5, -77.3, -77.5, -77.4],
        "total_cost_million_usd": [491.56, 520.00, 800.00, 470.00],
        "campus_size_square_ft": [1_000_000, 1_000_000, 1_000_000, 1_000_000],
        "data_center_it_power_mw": [36, 36, 50, 36],
        "mechanical_cooling_frac": [0.0, 0.25, 0.5, 0.0],
        "water_cooling_frac": [1.0, 0.75, 0.5, 1.0],
        "cooling_energy_demand_mwh": [0.0, 100.0, 500.0, 0.0],
        "cooling_water_demand_mgy": [43.5, 30.0, 25.0, 45.0],
        "cooling_water_consumption_mgy": [34.8, 24.0, 20.0, 36.0],
        "normalized_locational_cost": [0.14, 0.18, 0.22, 0.12],
        "normalized_gravity_score": [0.05, 0.04, 0.10, 0.06],
        "weighted_siting_score": [0.09, 0.11, 0.16, 0.09],
    })


def test_shape_required_point_columns():
    out = shape_to_point_schema(_enriched_rows(), snapshot_year=2035)
    required = {"facility_id", "facility_name", "lat", "lon", "year", "type"}
    assert required.issubset(out.columns)


def test_shape_facility_id_includes_scenario():
    # Same source id "51_0" appears in two scenarios → must produce distinct facility_id
    out = shape_to_point_schema(_enriched_rows(), snapshot_year=2035)
    assert "im3_cerf_51_0_moderate_50" in out["facility_id"].values
    assert "im3_cerf_51_0_higher_100" in out["facility_id"].values
    assert out["facility_id"].is_unique


def test_shape_facility_name_is_synthetic_with_scenario():
    out = shape_to_point_schema(_enriched_rows(), snapshot_year=2035)
    row = out[out["facility_id"] == "im3_cerf_51_0_moderate_50"].iloc[0]
    assert row["facility_name"] == "Projected Data Center (im3_cerf_moderate_50)"


def test_shape_type_is_uniform():
    out = shape_to_point_schema(_enriched_rows(), snapshot_year=2035)
    assert (out["type"] == "projected_data_center").all()


def test_shape_year_is_snapshot_year():
    out = shape_to_point_schema(_enriched_rows(), snapshot_year=2035)
    assert (out["year"] == 2035).all()


def test_shape_keeps_pipeline_attributes():
    out = shape_to_point_schema(_enriched_rows(), snapshot_year=2035)
    expected_attrs = {
        "scenario", "geoid", "growth_scenario", "market_gravity_weight",
        "data_center_it_power_mw", "campus_size_square_ft",
        "total_cost_million_usd", "cooling_water_demand_mgy",
        "cooling_water_consumption_mgy", "cooling_energy_demand_mwh",
        "mechanical_cooling_frac", "water_cooling_frac",
        "normalized_locational_cost", "normalized_gravity_score",
        "weighted_siting_score", "source_id",
    }
    assert expected_attrs.issubset(out.columns)
    row = out[out["facility_id"] == "im3_cerf_51_0_moderate_50"].iloc[0]
    assert row["data_center_it_power_mw"] == 36
    assert row["geoid"] == "51107"
    assert row["source_id"] == "51_0"


def test_shape_geoid_preserves_string():
    out = shape_to_point_schema(_enriched_rows(), snapshot_year=2035)
    assert out["geoid"].dtype == object
    assert all(len(str(g)) == 5 for g in out["geoid"])


def test_shape_lat_lon_propagate():
    out = shape_to_point_schema(_enriched_rows(), snapshot_year=2035)
    row = out[out["facility_id"] == "im3_cerf_51_0_moderate_50"].iloc[0]
    assert row["lat"] == 39.0
    assert row["lon"] == -77.5


# --- aggregate_to_counties tests ---


def _shaped_points():
    """Sample shape_to_point_schema output, pre-aggregation."""
    return pd.DataFrame({
        "facility_id": [
            "im3_cerf_51_0_moderate_50",
            "im3_cerf_51_1_moderate_50",
            "im3_cerf_51_0_higher_100",
            "im3_cerf_51_2_moderate_50",
        ],
        "source_id": ["51_0", "51_1", "51_0", "51_2"],
        "scenario": [
            "im3_cerf_moderate_50",
            "im3_cerf_moderate_50",
            "im3_cerf_higher_100",
            "im3_cerf_moderate_50",
        ],
        "geoid": ["51107", "51059", "51107", "51153"],
        "type": ["projected_data_center"] * 4,
        "data_center_it_power_mw": [36, 36, 50, 36],
        "campus_size_square_ft": [1_000_000, 1_000_000, 1_000_000, 1_000_000],
        "total_cost_million_usd": [491.56, 520.00, 800.00, 470.00],
        "cooling_water_demand_mgy": [43.5, 30.0, 25.0, 45.0],
        "cooling_water_consumption_mgy": [34.8, 24.0, 20.0, 36.0],
        "cooling_energy_demand_mwh": [0.0, 100.0, 500.0, 0.0],
    })


def test_aggregate_produces_expected_measures():
    out = aggregate_to_counties(_shaped_points(), scenario_date="2035-01-01")
    expected = {
        "projected_data_center_count",
        "total_projected_it_power_mw",
        "total_projected_campus_sqft",
        "total_projected_cost_million_usd",
        "total_projected_water_demand_mgy",
        "total_projected_water_consumption_mgy",
    }
    assert set(out["measure"].unique()) == expected


def test_aggregate_long_format_schema():
    out = aggregate_to_counties(_shaped_points(), scenario_date="2035-01-01")
    assert set(out.columns) == {
        "geoid", "datetime", "measure", "value", "moe",
        "region_type", "data_method", "scenario",
    }


def test_aggregate_groups_by_county_and_scenario():
    # 51107 has rows in BOTH "moderate_50" and "higher_100" — they must produce SEPARATE rows in the output.
    out = aggregate_to_counties(_shaped_points(), scenario_date="2035-01-01")
    count_rows = out[out["measure"] == "projected_data_center_count"]

    r_moderate_51107 = count_rows[
        (count_rows["geoid"] == "51107") & (count_rows["scenario"] == "im3_cerf_moderate_50")
    ].iloc[0]
    assert r_moderate_51107["value"] == 1

    r_higher_51107 = count_rows[
        (count_rows["geoid"] == "51107") & (count_rows["scenario"] == "im3_cerf_higher_100")
    ].iloc[0]
    assert r_higher_51107["value"] == 1

    # 51059 only has moderate_50
    r_moderate_51059 = count_rows[
        (count_rows["geoid"] == "51059") & (count_rows["scenario"] == "im3_cerf_moderate_50")
    ].iloc[0]
    assert r_moderate_51059["value"] == 1


def test_aggregate_power_sums():
    # 51107 moderate_50: just 1 row × 36 MW
    # 51107 higher_100: just 1 row × 50 MW
    out = aggregate_to_counties(_shaped_points(), scenario_date="2035-01-01")
    power_rows = out[out["measure"] == "total_projected_it_power_mw"]

    r = power_rows[
        (power_rows["geoid"] == "51107") & (power_rows["scenario"] == "im3_cerf_moderate_50")
    ].iloc[0]
    assert r["value"] == 36.0

    r = power_rows[
        (power_rows["geoid"] == "51107") & (power_rows["scenario"] == "im3_cerf_higher_100")
    ].iloc[0]
    assert r["value"] == 50.0


def test_aggregate_water_demand_sums():
    out = aggregate_to_counties(_shaped_points(), scenario_date="2035-01-01")
    rows = out[out["measure"] == "total_projected_water_demand_mgy"]
    r = rows[
        (rows["geoid"] == "51059") & (rows["scenario"] == "im3_cerf_moderate_50")
    ].iloc[0]
    assert r["value"] == 30.0


def test_aggregate_datetime_is_constant():
    out = aggregate_to_counties(_shaped_points(), scenario_date="2035-01-01")
    assert (out["datetime"] == "2035-01-01").all()


def test_aggregate_data_method_is_simulated():
    out = aggregate_to_counties(_shaped_points(), scenario_date="2035-01-01")
    assert (out["data_method"] == "simulated").all()


def test_aggregate_region_type_is_county():
    out = aggregate_to_counties(_shaped_points(), scenario_date="2035-01-01")
    assert (out["region_type"] == "county").all()


def test_aggregate_moe_is_null():
    out = aggregate_to_counties(_shaped_points(), scenario_date="2035-01-01")
    assert out["moe"].isna().all()


def test_aggregate_empty_input_returns_empty_frame():
    empty = pd.DataFrame(columns=[
        "facility_id", "source_id", "scenario", "geoid", "type",
        "data_center_it_power_mw", "campus_size_square_ft",
        "total_cost_million_usd", "cooling_water_demand_mgy",
        "cooling_water_consumption_mgy", "cooling_energy_demand_mwh",
    ])
    out = aggregate_to_counties(empty, scenario_date="2035-01-01")
    assert len(out) == 0
    assert set(out.columns) == {
        "geoid", "datetime", "measure", "value", "moe",
        "region_type", "data_method", "scenario",
    }
