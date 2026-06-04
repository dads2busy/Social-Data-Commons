"""Tests for Zenodo deposit metadata building (sdc_core.zenodo)."""
from sdc_core.zenodo import build_zenodo_description


def _build(measure_info):
    config = {
        "name": "demo_index",
        "description": "A demonstration index.",
        "sources": {"va": {"years": [2018, 2019], "geographies": ["tract", "county"]}},
    }
    md, _ = build_zenodo_description(config, measure_info)
    return md


def test_describes_intensive_standardization():
    # A replicate (intensive) measure should get the dominant-parent standardization note.
    mi = {"demo_index_geo20": {
        "long_description": "Demo index. Computed somehow.",
        "geo_standardize": {"measure_type": "replicate"},
    }}
    md = _build(mi)
    assert "standardized from 2010 to 2020 census tract boundaries" in md
    assert "area-dominant 2010 tract" in md


def test_count_mentions_area_weighting():
    mi = {"pop_count_geo20": {
        "long_description": "Population count. Counted somehow.",
        "geo_standardize": {"measure_type": "count"},
    }}
    md = _build(mi)
    assert "land-area weighting" in md
    assert "conserves regional totals" in md


def test_geo2020_native_omits_conversion_note():
    # geo2020-native data underwent no 2010->2020 conversion: no method note,
    # but still reports _geo20 = 2020 boundaries.
    mi = {"x_geo20": {
        "long_description": "X. Native 2020.",
        "geo_standardize": {"measure_type": "geo2020"},
    }}
    md = _build(mi)
    assert "standardized from 2010 to 2020" not in md
    assert "2020 Census tract boundaries" in md
