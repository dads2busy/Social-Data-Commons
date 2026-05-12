"""Tests for point-schema I/O in sdc_core.io."""

import pandas as pd
import pytest

import json

from sdc_core.io import (
    POINT_SCHEMA_OPTIONAL,
    POINT_SCHEMA_REQUIRED,
    export_point_layer,
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


def test_write_point_data_error_message_includes_bounds(tmp_path):
    df = _sample_points()
    df.loc[0, "lat"] = 95.0
    df.loc[1, "lat"] = 100.0
    with pytest.raises(ValueError, match="lat out of range.*min=95.*max=100"):
        write_point_data(df, tmp_path / "bad.csv.xz")


def test_write_point_data_drops_rows_with_null_facility_id(tmp_path):
    df = _sample_points()
    df.loc[0, "facility_id"] = None
    out = write_point_data(df, tmp_path / "us_pt_osm_2026_data_centers.csv.xz")
    round_trip = pd.read_csv(out, dtype={"facility_id": object})
    assert list(round_trip["facility_id"]) == ["dc-002"]
    assert "nan" not in round_trip["facility_id"].values


def test_export_point_layer_writes_geojson_featurecollection(tmp_path):
    df = _sample_points()
    src = write_point_data(df, tmp_path / "src.csv.xz")

    out = export_point_layer(
        source_path=src,
        output_dir=tmp_path / "site",
        coverage_area="us",
        data_source="osm",
        title="data_centers",
    )

    assert out.suffix == ".geojson"
    assert out.parent == tmp_path / "site"
    assert out.name == "us_pt_osm_2026_data_centers.geojson"

    payload = json.loads(out.read_text())
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 2

    f0 = payload["features"][0]
    assert f0["type"] == "Feature"
    assert f0["geometry"]["type"] == "Point"
    # GeoJSON coordinate order is [lon, lat]
    assert f0["geometry"]["coordinates"] == [-77.36, 38.96]
    props = f0["properties"]
    assert props["facility_id"] == "dc-001"
    assert props["facility_name"] == "Reston DC1"
    assert props["year"] == 2026
    assert props["type"] == "point"
    # Pipeline-specific attributes pass through
    assert props["operator"] == "Equinix"
    # lat/lon are NOT duplicated into properties
    assert "lat" not in props
    assert "lon" not in props


def test_export_point_layer_filename_uses_year_range(tmp_path):
    df = _sample_points()
    df.loc[0, "year"] = 2024
    df.loc[1, "year"] = 2026
    src = write_point_data(df, tmp_path / "src.csv.xz")

    out = export_point_layer(
        source_path=src,
        output_dir=tmp_path / "site",
        coverage_area="us",
        data_source="osm",
        title="data_centers",
    )
    assert out.name == "us_pt_osm_2024_2026_data_centers.geojson"


def test_export_point_layer_creates_output_dir(tmp_path):
    df = _sample_points()
    src = write_point_data(df, tmp_path / "src.csv.xz")
    out_dir = tmp_path / "deep" / "site"
    assert not out_dir.exists()

    out = export_point_layer(
        source_path=src,
        output_dir=out_dir,
        coverage_area="us",
        data_source="osm",
        title="data_centers",
    )
    assert out.parent == out_dir
    assert out.exists()


def test_export_point_layer_omits_null_property_values(tmp_path):
    df = _sample_points()
    df.loc[0, "operator"] = None
    src = write_point_data(df, tmp_path / "src.csv.xz")

    out = export_point_layer(
        source_path=src,
        output_dir=tmp_path / "site",
        coverage_area="us",
        data_source="osm",
        title="data_centers",
    )
    payload = json.loads(out.read_text())
    f0 = payload["features"][0]
    # Null values should be omitted from properties, not serialized as null
    assert "operator" not in f0["properties"]
    f1 = payload["features"][1]
    assert f1["properties"]["operator"] == "Amazon"


def test_public_imports_work():
    # These are the documented public entry points used by pipelines.
    from sdc_core.io import (
        POINT_SCHEMA_OPTIONAL,
        POINT_SCHEMA_REQUIRED,
        export_point_layer,
        read_point_data,
        write_point_data,
    )
    assert callable(write_point_data)
    assert callable(read_point_data)
    assert callable(export_point_layer)
    assert len(POINT_SCHEMA_REQUIRED) == 6
    assert len(POINT_SCHEMA_OPTIONAL) >= 1
