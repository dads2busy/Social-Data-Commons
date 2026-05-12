"""Unit tests for EV charging station transforms."""

import pandas as pd
import pytest

from transforms import (
    aggregate_to_counties,
    expand_multi_type_rows,
)


def _sample_stations():
    return pd.DataFrame({
        "ID": [1001, 1002, 1003, 1004],
        "longitude": [-77.0, -78.0, -79.0, -80.0],
        "latitude": [38.0, 38.5, 39.0, 39.5],
        "l1_charger_count": [0, 1, 0, 0],   # only station 1002 has L1
        "l2_charger_count": [1, 1, 0, 0],   # stations 1001 and 1002 have L2
        "l3_charger_count": [0, 0, 2, 0],   # station 1003 has 2 L3
        "Fuel_Type_Code": ["ELEC", "ELEC", "ELEC", "ELEC"],
    })


def test_expand_returns_one_row_per_nonzero_level():
    out = expand_multi_type_rows(_sample_stations())
    # Station 1001 (L2=1) -> 1 row
    # Station 1002 (L1=1, L2=1) -> 2 rows
    # Station 1003 (L3=2) -> 1 row
    # Station 1004 (all zero) -> 0 rows
    assert len(out) == 4


def test_expand_produces_required_point_columns():
    out = expand_multi_type_rows(_sample_stations())
    required = {"facility_id", "facility_name", "lat", "lon", "year", "type"}
    assert required.issubset(out.columns)


def test_expand_facility_id_is_unique_per_row():
    out = expand_multi_type_rows(_sample_stations())
    assert out["facility_id"].is_unique


def test_expand_facility_name_uses_synthetic_format():
    out = expand_multi_type_rows(_sample_stations())
    # Station 1001 has L2
    row = out[out["facility_id"] == "1001_l2"].iloc[0]
    assert row["facility_name"] == "VA Charging Station 1001"


def test_expand_type_values_are_lowercase_level_strings():
    out = expand_multi_type_rows(_sample_stations())
    assert set(out["type"].unique()) <= {"l1", "l2", "l3"}


def test_expand_year_is_2030():
    out = expand_multi_type_rows(_sample_stations())
    assert (out["year"] == 2030).all()


def test_expand_keeps_count_as_pipeline_attribute():
    out = expand_multi_type_rows(_sample_stations())
    # Station 1003 had l3_charger_count = 2
    row = out[out["facility_id"] == "1003_l3"].iloc[0]
    assert row["count"] == 2
    # Station 1001 had l2_charger_count = 1
    row = out[out["facility_id"] == "1001_l2"].iloc[0]
    assert row["count"] == 1


def test_expand_keeps_station_id_for_dedup():
    out = expand_multi_type_rows(_sample_stations())
    # station_id is the raw ID column, used for dedup in aggregation
    assert "station_id" in out.columns
    row = out[out["facility_id"] == "1002_l1"].iloc[0]
    assert row["station_id"] == 1002


def test_expand_lat_lon_propagate_unchanged():
    out = expand_multi_type_rows(_sample_stations())
    row = out[out["facility_id"] == "1003_l3"].iloc[0]
    assert row["lat"] == 39.0
    assert row["lon"] == -79.0


def test_expand_drops_all_zero_stations():
    out = expand_multi_type_rows(_sample_stations())
    assert 1004 not in out["station_id"].values


def _expanded_with_geoid():
    """Sample expanded rows with county FIPS assigned. Two counties, mix of types."""
    return pd.DataFrame({
        "facility_id": ["1001_l2", "1002_l1", "1002_l2", "1003_l3"],
        "station_id": [1001, 1002, 1002, 1003],
        "geoid": ["51001", "51001", "51001", "51003"],
        "lat": [38.0, 38.5, 38.5, 39.0],
        "lon": [-77.0, -78.0, -78.0, -79.0],
        "year": [2030, 2030, 2030, 2030],
        "type": ["l2", "l1", "l2", "l3"],
        "count": [1, 1, 1, 2],
        "fuel_type_code": ["ELEC"] * 4,
    })


def test_aggregate_produces_expected_measure_names():
    out = aggregate_to_counties(_expanded_with_geoid(), scenario="s1", scenario_date="2030-01-01")
    expected = {
        "l1_station_count", "l2_station_count", "l3_station_count", "total_station_count",
        "l1_charger_count", "l2_charger_count", "l3_charger_count", "total_charger_count",
    }
    assert set(out["measure"].unique()) == expected


def test_aggregate_long_format_schema():
    out = aggregate_to_counties(_expanded_with_geoid(), scenario="s1", scenario_date="2030-01-01")
    assert set(out.columns) == {
        "geoid", "datetime", "measure", "value", "moe", "region_type", "data_method", "scenario",
    }


def test_aggregate_station_counts_dedupe_per_level():
    # County 51001 has 2 unique stations (1001 and 1002).
    # Both have L2 chargers (station_count=2 for l2).
    # Only station 1002 has L1 (station_count=1 for l1).
    out = aggregate_to_counties(_expanded_with_geoid(), scenario="s1", scenario_date="2030-01-01")
    r = out[(out["geoid"] == "51001") & (out["measure"] == "l2_station_count")].iloc[0]
    assert r["value"] == 2
    r = out[(out["geoid"] == "51001") & (out["measure"] == "l1_station_count")].iloc[0]
    assert r["value"] == 1


def test_aggregate_total_station_count_is_unique_stations():
    # County 51001 has 2 unique stations (1001, 1002) even though there are 3 rows there.
    out = aggregate_to_counties(_expanded_with_geoid(), scenario="s1", scenario_date="2030-01-01")
    r = out[(out["geoid"] == "51001") & (out["measure"] == "total_station_count")].iloc[0]
    assert r["value"] == 2


def test_aggregate_charger_counts_sum():
    # County 51003 has 1 row with l3 count=2.
    out = aggregate_to_counties(_expanded_with_geoid(), scenario="s1", scenario_date="2030-01-01")
    r = out[(out["geoid"] == "51003") & (out["measure"] == "l3_charger_count")].iloc[0]
    assert r["value"] == 2
    r = out[(out["geoid"] == "51003") & (out["measure"] == "total_charger_count")].iloc[0]
    assert r["value"] == 2


def test_aggregate_scenario_and_datetime_propagate():
    out = aggregate_to_counties(_expanded_with_geoid(), scenario="my_scenario", scenario_date="2030-06-15")
    assert (out["scenario"] == "my_scenario").all()
    assert (out["datetime"] == "2030-06-15").all()


def test_aggregate_data_method_is_simulated():
    out = aggregate_to_counties(_expanded_with_geoid(), scenario="s1", scenario_date="2030-01-01")
    assert (out["data_method"] == "simulated").all()


def test_aggregate_region_type_is_county():
    out = aggregate_to_counties(_expanded_with_geoid(), scenario="s1", scenario_date="2030-01-01")
    assert (out["region_type"] == "county").all()


def test_aggregate_moe_is_null():
    out = aggregate_to_counties(_expanded_with_geoid(), scenario="s1", scenario_date="2030-01-01")
    assert out["moe"].isna().all()
