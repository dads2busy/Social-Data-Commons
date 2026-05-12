"""Tests for point-resolution and nationwide-coverage naming extensions."""

from sdc_core.naming import (
    DEFAULT_COVERAGE_MAP,
    REGION_TYPE_ABBR,
    RESOLUTION_ORDER,
    build_file_name,
    infer_coverage_area_from_states,
    infer_resolution_from_region_types,
)


def test_point_region_type_maps_to_pt():
    assert REGION_TYPE_ABBR["point"] == "pt"
    assert REGION_TYPE_ABBR["pt"] == "pt"


def test_pt_is_in_resolution_order():
    assert "pt" in RESOLUTION_ORDER


def test_infer_resolution_includes_pt():
    assert infer_resolution_from_region_types(["point"]) == "pt"


def test_us_coverage_inference_from_states():
    assert ("us",) in DEFAULT_COVERAGE_MAP
    assert infer_coverage_area_from_states(["us"]) == "us"


def test_build_file_name_for_nationwide_points():
    name = build_file_name(
        coverage_area="us",
        resolution="pt",
        data_source="osm",
        years=[2026],
        title="data_centers",
    )
    assert name == "us_pt_osm_2026_data_centers"
