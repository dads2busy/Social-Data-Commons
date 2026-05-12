"""Unit tests for EV charging demand transforms."""

import pandas as pd
import pytest

from transforms import (
    aggregate_to_county_hour,
    aggregate_to_locations,
    infer_location_type,
)


# --- infer_location_type tests ---


def test_infer_type_public_station_format():
    assert infer_location_type("va_223306_existing") == "public_station"


def test_infer_type_numeric_residential():
    assert infer_location_type("1001065827") == "residential_or_other"
    assert infer_location_type("100665830") == "residential_or_other"


def test_infer_type_unknown_format():
    assert infer_location_type("foo_bar") == "unknown"
    assert infer_location_type("") == "unknown"


def test_infer_type_numeric_string_with_letters_is_unknown():
    # mixed-format IDs that don't match either pattern
    assert infer_location_type("va_123") == "unknown"


# --- aggregate_to_locations tests ---


def _sample_events():
    """Sample events: 3 locations, mix of formats and hour coverage."""
    return pd.DataFrame({
        "charging_station_id": [
            # Location 1: public station, 3 hours of activity
            "va_223306_existing", "va_223306_existing", "va_223306_existing",
            # Location 2: residential, 2 hours
            "1001065827", "1001065827",
            # Location 3: residential, 1 hour
            "100665830",
        ],
        "latitude": [38.0, 38.0, 38.0, 36.9, 36.9, 37.5],
        "longitude": [-77.0, -77.0, -77.0, -76.3, -76.3, -78.0],
        "hour": [7, 8, 9, 18, 19, 20],
        "total_kWh_added": [10.0, 25.0, 5.0, 7.5, 8.5, 12.0],
    })


def test_aggregate_locations_one_row_per_unique_station():
    out = aggregate_to_locations(_sample_events(), snapshot_year=2026)
    assert len(out) == 3
    assert set(out["facility_id"]) == {"va_223306_existing", "1001065827", "100665830"}


def test_aggregate_locations_has_point_schema_columns():
    out = aggregate_to_locations(_sample_events(), snapshot_year=2026)
    required = {"facility_id", "facility_name", "lat", "lon", "year", "type"}
    assert required.issubset(out.columns)


def test_aggregate_locations_type_inferred_per_id():
    out = aggregate_to_locations(_sample_events(), snapshot_year=2026)
    row = out[out["facility_id"] == "va_223306_existing"].iloc[0]
    assert row["type"] == "public_station"
    row = out[out["facility_id"] == "1001065827"].iloc[0]
    assert row["type"] == "residential_or_other"


def test_aggregate_locations_total_kwh_sums_across_hours():
    out = aggregate_to_locations(_sample_events(), snapshot_year=2026)
    row = out[out["facility_id"] == "va_223306_existing"].iloc[0]
    # 10 + 25 + 5 = 40
    assert row["total_kwh"] == 40.0
    row = out[out["facility_id"] == "1001065827"].iloc[0]
    # 7.5 + 8.5 = 16.0
    assert row["total_kwh"] == 16.0


def test_aggregate_locations_n_hours_active_counts_nonzero():
    out = aggregate_to_locations(_sample_events(), snapshot_year=2026)
    row = out[out["facility_id"] == "va_223306_existing"].iloc[0]
    assert row["n_hours_active"] == 3
    row = out[out["facility_id"] == "100665830"].iloc[0]
    assert row["n_hours_active"] == 1


def test_aggregate_locations_n_hours_excludes_zero_kwh():
    events = _sample_events()
    # Add a zero-kWh row for location 3 — shouldn't increment n_hours_active
    events = pd.concat([events, pd.DataFrame({
        "charging_station_id": ["100665830"],
        "latitude": [37.5], "longitude": [-78.0], "hour": [21],
        "total_kWh_added": [0.0],
    })], ignore_index=True)
    out = aggregate_to_locations(events, snapshot_year=2026)
    row = out[out["facility_id"] == "100665830"].iloc[0]
    assert row["n_hours_active"] == 1   # not 2


def test_aggregate_locations_facility_name_is_synthetic_with_type():
    out = aggregate_to_locations(_sample_events(), snapshot_year=2026)
    row = out[out["facility_id"] == "va_223306_existing"].iloc[0]
    assert "va_223306_existing" in row["facility_name"]
    assert "public_station" in row["facility_name"]


def test_aggregate_locations_lat_lon_from_first_observation():
    # All rows for a given station should have the same lat/lon; take the first.
    out = aggregate_to_locations(_sample_events(), snapshot_year=2026)
    row = out[out["facility_id"] == "1001065827"].iloc[0]
    assert row["lat"] == 36.9
    assert row["lon"] == -76.3


def test_aggregate_locations_year_is_snapshot_year():
    out = aggregate_to_locations(_sample_events(), snapshot_year=2026)
    assert (out["year"] == 2026).all()


def test_aggregate_locations_keeps_id_format_attribute():
    out = aggregate_to_locations(_sample_events(), snapshot_year=2026)
    assert "id_format" in out.columns
    # id_format mirrors `type` here (since they're derived from the same classifier)
    row = out[out["facility_id"] == "va_223306_existing"].iloc[0]
    assert row["id_format"] == "public_station"


# --- aggregate_to_county_hour tests ---


def _sample_events_with_geoid():
    """Events with geoid pre-attached (post-sjoin)."""
    return pd.DataFrame({
        "charging_station_id": [
            # County 51107 (Loudoun): 2 locations, hour 7 and hour 8
            "loc_a", "loc_a", "loc_b",
            # County 51059 (Fairfax): 1 location, hour 7 only
            "loc_c",
        ],
        "geoid": ["51107", "51107", "51107", "51059"],
        "hour": [7, 8, 7, 7],
        "total_kWh_added": [10.0, 15.0, 5.0, 8.0],
    })


def test_aggregate_county_hour_produces_expected_measures():
    out = aggregate_to_county_hour(
        _sample_events_with_geoid(), scenario="s1", scenario_year=2026,
    )
    assert set(out["measure"].unique()) == {
        "ev_charging_demand_kwh",
        "n_active_charging_locations",
    }


def test_aggregate_county_hour_long_format_schema():
    out = aggregate_to_county_hour(
        _sample_events_with_geoid(), scenario="s1", scenario_year=2026,
    )
    assert set(out.columns) == {
        "geoid", "datetime", "measure", "value", "moe",
        "region_type", "data_method", "scenario",
    }


def test_aggregate_county_hour_kwh_sums():
    out = aggregate_to_county_hour(
        _sample_events_with_geoid(), scenario="s1", scenario_year=2026,
    )
    # 51107 hour 7: loc_a (10) + loc_b (5) = 15
    r = out[
        (out["geoid"] == "51107")
        & (out["datetime"] == "2026-01-01T07:00:00")
        & (out["measure"] == "ev_charging_demand_kwh")
    ].iloc[0]
    assert r["value"] == 15.0
    # 51107 hour 8: loc_a (15) = 15
    r = out[
        (out["geoid"] == "51107")
        & (out["datetime"] == "2026-01-01T08:00:00")
        & (out["measure"] == "ev_charging_demand_kwh")
    ].iloc[0]
    assert r["value"] == 15.0
    # 51059 hour 7: loc_c (8) = 8
    r = out[
        (out["geoid"] == "51059")
        & (out["datetime"] == "2026-01-01T07:00:00")
        & (out["measure"] == "ev_charging_demand_kwh")
    ].iloc[0]
    assert r["value"] == 8.0


def test_aggregate_county_hour_active_location_counts_unique():
    out = aggregate_to_county_hour(
        _sample_events_with_geoid(), scenario="s1", scenario_year=2026,
    )
    # 51107 hour 7 has 2 distinct locations (loc_a, loc_b)
    r = out[
        (out["geoid"] == "51107")
        & (out["datetime"] == "2026-01-01T07:00:00")
        & (out["measure"] == "n_active_charging_locations")
    ].iloc[0]
    assert r["value"] == 2
    # 51107 hour 8 has 1 location (just loc_a)
    r = out[
        (out["geoid"] == "51107")
        & (out["datetime"] == "2026-01-01T08:00:00")
        & (out["measure"] == "n_active_charging_locations")
    ].iloc[0]
    assert r["value"] == 1


def test_aggregate_county_hour_datetime_uses_zero_padded_hour():
    out = aggregate_to_county_hour(
        _sample_events_with_geoid(), scenario="s1", scenario_year=2026,
    )
    # Hour 7 → "2026-01-01T07:00:00" (zero-padded)
    assert "2026-01-01T07:00:00" in out["datetime"].values
    # Hour 8 → "2026-01-01T08:00:00"
    assert "2026-01-01T08:00:00" in out["datetime"].values


def test_aggregate_county_hour_zero_padding_extends_to_double_digit_hours():
    events = pd.DataFrame({
        "charging_station_id": ["x"],
        "geoid": ["51107"],
        "hour": [23],
        "total_kWh_added": [1.0],
    })
    out = aggregate_to_county_hour(events, scenario="s1", scenario_year=2026)
    assert "2026-01-01T23:00:00" in out["datetime"].values


def test_aggregate_county_hour_data_method_is_simulated():
    out = aggregate_to_county_hour(
        _sample_events_with_geoid(), scenario="s1", scenario_year=2026,
    )
    assert (out["data_method"] == "simulated").all()


def test_aggregate_county_hour_region_type_is_county():
    out = aggregate_to_county_hour(
        _sample_events_with_geoid(), scenario="s1", scenario_year=2026,
    )
    assert (out["region_type"] == "county").all()


def test_aggregate_county_hour_scenario_propagates():
    out = aggregate_to_county_hour(
        _sample_events_with_geoid(),
        scenario="va_2026_run2_eval30",
        scenario_year=2026,
    )
    assert (out["scenario"] == "va_2026_run2_eval30").all()


def test_aggregate_county_hour_moe_is_null():
    out = aggregate_to_county_hour(
        _sample_events_with_geoid(), scenario="s1", scenario_year=2026,
    )
    assert out["moe"].isna().all()


def test_aggregate_county_hour_empty_input_returns_empty_frame():
    empty = pd.DataFrame(columns=["charging_station_id", "geoid", "hour", "total_kWh_added"])
    out = aggregate_to_county_hour(empty, scenario="s1", scenario_year=2026)
    assert len(out) == 0
    assert set(out.columns) == {
        "geoid", "datetime", "measure", "value", "moe",
        "region_type", "data_method", "scenario",
    }
