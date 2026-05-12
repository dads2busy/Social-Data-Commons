"""Tests for point-schema I/O in sdc_core.io."""

import pandas as pd
import pytest

from sdc_core.io import (
    POINT_SCHEMA_OPTIONAL,
    POINT_SCHEMA_REQUIRED,
    read_point_data,
    write_point_data,
)


def _sample_points():
    return pd.DataFrame({
        "facility_id": ["dc-001", "dc-002"],
        "facility_name": ["Reston DC1", "Ashburn Campus"],
        "lat": [38.96, 39.04],
        "lon": [-77.36, -77.49],
        "year": [2026, 2026],
        "type": ["point", "campus"],
        "operator": ["Equinix", "Amazon"],   # pipeline-specific attribute
    })


def test_point_schema_required_columns():
    assert set(POINT_SCHEMA_REQUIRED) == {
        "facility_id", "facility_name", "lat", "lon", "year", "type",
    }


def test_point_schema_optional_includes_description():
    assert "description" in POINT_SCHEMA_OPTIONAL


def test_write_point_data_writes_csv_xz(tmp_path):
    df = _sample_points()
    out = write_point_data(df, tmp_path / "us_pt_osm_2026_data_centers.csv.xz")
    assert out.exists()
    assert out.suffix == ".xz"

    round_trip = pd.read_csv(out, dtype={"facility_id": str})
    assert list(round_trip["facility_id"]) == ["dc-001", "dc-002"]
    # Pipeline-specific column passes through
    assert "operator" in round_trip.columns


def test_write_point_data_rejects_missing_required_column(tmp_path):
    df = _sample_points().drop(columns=["lat"])
    with pytest.raises(ValueError, match="missing required point column"):
        write_point_data(df, tmp_path / "bad.csv.xz")


def test_write_point_data_drops_rows_with_null_coords(tmp_path):
    df = _sample_points()
    df.loc[0, "lat"] = None
    out = write_point_data(df, tmp_path / "us_pt_osm_2026_data_centers.csv.xz")
    round_trip = pd.read_csv(out, dtype={"facility_id": str})
    assert list(round_trip["facility_id"]) == ["dc-002"]


def test_write_point_data_rejects_out_of_range_coords(tmp_path):
    df = _sample_points()
    df.loc[0, "lon"] = 999.0
    with pytest.raises(ValueError, match="lon out of range"):
        write_point_data(df, tmp_path / "bad.csv.xz")


def test_read_point_data_preserves_string_ids(tmp_path):
    df = _sample_points()
    out = write_point_data(df, tmp_path / "us_pt_osm_2026_data_centers.csv.xz")
    loaded = read_point_data(out)
    assert loaded["facility_id"].dtype == object
    assert list(loaded["facility_id"]) == ["dc-001", "dc-002"]
    assert loaded["lat"].dtype == float
