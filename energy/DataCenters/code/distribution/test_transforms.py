"""Unit tests for IM3 Atlas data center transforms."""

import pandas as pd
import pytest

from transforms import (
    aggregate_to_counties,
    filter_and_shape,
)


def _sample_raw():
    """Sample of the source CSV. Mix of VA, MD, DC rows; mix of geometry types.

    Note: state_id and county_id are zero-padded strings (2- and 3-digit
    respectively), matching what pd.read_csv produces with dtype=str.
    The full 5-digit FIPS is constructed by string concat in filter_and_shape.
    """
    return pd.DataFrame({
        "id": [101, 102, 103, 104, 105, 106],
        "state": ["Virginia", "Virginia", "Virginia", "Maryland", "Virginia", "Virginia"],
        "state_abb": ["VA", "VA", "VA", "MD", "VA", "VA"],
        "state_id": ["51", "51", "51", "24", "51", "51"],
        "county": ["Loudoun", "Loudoun", "Fairfax", "Montgomery", "Loudoun", "Loudoun"],
        "county_id": ["107", "107", "059", "031", "107", "107"],
        "ref": ["n1", "w2", "r3", "n4", "n5", "w6"],
        "operator": ["Equinix", "Equinix", "Amazon", "Microsoft", "QTS", None],
        "name": ["DC1", "DC1 Building", "Ashburn Campus", "MD-1", "QTS LO1", None],
        "sqft": [pd.NA, 50000.0, 250000.0, 100000.0, pd.NA, 35000.0],
        "lat": [39.0, 39.0, 38.9, 39.1, 39.05, 39.06],
        "lon": [-77.5, -77.5, -77.3, -77.0, -77.51, -77.52],
        "type": ["point", "building", "campus", "campus", "point", "building"],
    })


def test_filter_drops_non_va_rows():
    out = filter_and_shape(_sample_raw(), state_filter="VA", snapshot_year=2026)
    # 1 MD row dropped → 5 VA rows remain
    assert len(out) == 5
    assert "MD" not in out.get("state_abb", pd.Series(dtype=str)).values


def test_filter_produces_required_point_columns():
    out = filter_and_shape(_sample_raw(), state_filter="VA", snapshot_year=2026)
    required = {"facility_id", "facility_name", "lat", "lon", "year", "type"}
    assert required.issubset(out.columns)


def test_filter_facility_id_is_composite_with_type():
    out = filter_and_shape(_sample_raw(), state_filter="VA", snapshot_year=2026)
    # id 101 is type=point, id 102 is type=building → distinct facility_id
    assert "im3_101_point" in out["facility_id"].values
    assert "im3_102_building" in out["facility_id"].values
    assert out["facility_id"].is_unique


def test_filter_uses_real_name_when_present():
    out = filter_and_shape(_sample_raw(), state_filter="VA", snapshot_year=2026)
    row = out[out["facility_id"] == "im3_103_campus"].iloc[0]
    assert row["facility_name"] == "Ashburn Campus"


def test_filter_falls_back_to_operator_name_when_name_null():
    out = filter_and_shape(_sample_raw(), state_filter="VA", snapshot_year=2026)
    # id 106 has name=NaN, operator=NaN → must still produce something non-empty
    row = out[out["facility_id"] == "im3_106_building"].iloc[0]
    assert pd.notna(row["facility_name"]) and row["facility_name"] != ""


def test_filter_falls_back_to_operator_when_name_null_but_operator_present():
    # Inject a row with name=NaN but operator="QTS" → name should fall back to operator string
    raw = _sample_raw()
    raw.loc[raw["id"] == 105, "name"] = None
    out = filter_and_shape(raw, state_filter="VA", snapshot_year=2026)
    row = out[out["facility_id"] == "im3_105_point"].iloc[0]
    assert "QTS" in row["facility_name"]


def test_filter_year_is_snapshot_year():
    out = filter_and_shape(_sample_raw(), state_filter="VA", snapshot_year=2026)
    assert (out["year"] == 2026).all()


def test_filter_keeps_pipeline_attributes():
    out = filter_and_shape(_sample_raw(), state_filter="VA", snapshot_year=2026)
    for col in ["operator", "sqft", "county_id", "state_abb", "source_id"]:
        assert col in out.columns
    row = out[out["facility_id"] == "im3_103_campus"].iloc[0]
    assert row["county_id"] == "51059"
    assert row["sqft"] == 250000.0
    assert row["source_id"] == 103


def test_filter_lat_lon_propagate():
    out = filter_and_shape(_sample_raw(), state_filter="VA", snapshot_year=2026)
    row = out[out["facility_id"] == "im3_103_campus"].iloc[0]
    assert row["lat"] == 38.9
    assert row["lon"] == -77.3


def test_filter_county_id_is_string_5_digit():
    out = filter_and_shape(_sample_raw(), state_filter="VA", snapshot_year=2026)
    # FIPS must stay as zero-padded string, not int
    assert out["county_id"].dtype == object
    assert all(len(c) == 5 for c in out["county_id"])


def _shaped_va_points():
    """Pre-shaped VA rows for aggregation tests. 4 facilities, 2 counties."""
    return pd.DataFrame({
        "facility_id": [
            "im3_101_point", "im3_102_building", "im3_103_campus",
            "im3_105_point", "im3_106_building",
        ],
        "source_id": [101, 102, 103, 105, 106],
        "county_id": ["51107", "51107", "51059", "51107", "51107"],
        "lat": [39.0, 39.0, 38.9, 39.05, 39.06],
        "lon": [-77.5, -77.5, -77.3, -77.51, -77.52],
        "year": [2026, 2026, 2026, 2026, 2026],
        "type": ["point", "building", "campus", "point", "building"],
        "operator": ["Equinix", "Equinix", "Amazon", "QTS", "QTS"],
        "sqft": [pd.NA, 50000.0, 250000.0, pd.NA, 35000.0],
    })


def test_aggregate_produces_expected_measure_names():
    out = aggregate_to_counties(_shaped_va_points(), scenario="s1", scenario_date="2026-02-09")
    expected = {
        "total_data_center_count",
        "point_data_center_count",
        "building_data_center_count",
        "campus_data_center_count",
        "total_data_center_sqft",
    }
    assert set(out["measure"].unique()) == expected


def test_aggregate_long_format_schema():
    out = aggregate_to_counties(_shaped_va_points(), scenario="s1", scenario_date="2026-02-09")
    assert set(out.columns) == {
        "geoid", "datetime", "measure", "value", "moe", "region_type", "data_method", "scenario",
    }


def test_aggregate_total_count_is_row_count_per_county():
    # 51107 has 4 rows, 51059 has 1
    out = aggregate_to_counties(_shaped_va_points(), scenario="s1", scenario_date="2026-02-09")
    r = out[(out["geoid"] == "51107") & (out["measure"] == "total_data_center_count")].iloc[0]
    assert r["value"] == 4
    r = out[(out["geoid"] == "51059") & (out["measure"] == "total_data_center_count")].iloc[0]
    assert r["value"] == 1


def test_aggregate_counts_by_type():
    # 51107 has 2 point, 2 building, 0 campus.
    out = aggregate_to_counties(_shaped_va_points(), scenario="s1", scenario_date="2026-02-09")
    r = out[(out["geoid"] == "51107") & (out["measure"] == "point_data_center_count")].iloc[0]
    assert r["value"] == 2
    r = out[(out["geoid"] == "51107") & (out["measure"] == "building_data_center_count")].iloc[0]
    assert r["value"] == 2
    # campus count for 51107 should be 0 — present in output, not missing
    r = out[(out["geoid"] == "51107") & (out["measure"] == "campus_data_center_count")]
    assert len(r) == 1
    assert r.iloc[0]["value"] == 0


def test_aggregate_sqft_sums_nulls_treated_as_zero():
    # 51107 sqft: NaN + 50000 + NaN + 35000 = 85000
    out = aggregate_to_counties(_shaped_va_points(), scenario="s1", scenario_date="2026-02-09")
    r = out[(out["geoid"] == "51107") & (out["measure"] == "total_data_center_sqft")].iloc[0]
    assert r["value"] == 85000.0
    r = out[(out["geoid"] == "51059") & (out["measure"] == "total_data_center_sqft")].iloc[0]
    assert r["value"] == 250000.0


def test_aggregate_scenario_and_datetime_propagate():
    out = aggregate_to_counties(_shaped_va_points(), scenario="im3_atlas_v2026_02_09", scenario_date="2026-02-09")
    assert (out["scenario"] == "im3_atlas_v2026_02_09").all()
    assert (out["datetime"] == "2026-02-09").all()


def test_aggregate_data_method_is_observed():
    out = aggregate_to_counties(_shaped_va_points(), scenario="s1", scenario_date="2026-02-09")
    assert (out["data_method"] == "observed").all()


def test_aggregate_region_type_is_county():
    out = aggregate_to_counties(_shaped_va_points(), scenario="s1", scenario_date="2026-02-09")
    assert (out["region_type"] == "county").all()


def test_aggregate_moe_is_null():
    out = aggregate_to_counties(_shaped_va_points(), scenario="s1", scenario_date="2026-02-09")
    assert out["moe"].isna().all()


def test_aggregate_empty_input_returns_empty_frame():
    empty = pd.DataFrame(columns=["facility_id", "source_id", "county_id", "type", "sqft"])
    out = aggregate_to_counties(empty, scenario="s1", scenario_date="2026-02-09")
    assert len(out) == 0
    assert set(out.columns) == {
        "geoid", "datetime", "measure", "value", "moe", "region_type", "data_method", "scenario",
    }
