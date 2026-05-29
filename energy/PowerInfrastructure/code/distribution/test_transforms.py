"""Unit tests for PowerInfrastructure pure transforms."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from transforms import parse_capacity


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("100 MW", 100.0),
        ("2.5 MW", 2.5),
        ("750000 W", 0.75),
        ("750 kW", 0.75),
        ("1.5 GW", 1500.0),
        ("100MW", 100.0),       # no space
        ("100", 100.0),         # bare number assumed MW
        ("yes", math.nan),      # non-numeric sentinel
        ("", math.nan),
        (None, math.nan),
    ],
)
def test_parse_capacity(raw, expected):
    result = parse_capacity(raw)
    if math.isnan(expected):
        assert math.isnan(result)
    else:
        assert result == pytest.approx(expected)


from transforms import shape_to_point_schema


def _sample_enriched_rows():
    """Mimic the DataFrame ingest passes in after centroid + sjoin.

    Columns use OSM tag names verbatim (colons preserved) plus element_type,
    osmid, lat, lon, geoid added by ingest.
    """
    return pd.DataFrame(
        {
            "element_type": ["way", "node"],
            "osmid": [111, 222],
            "power": ["plant", "substation"],
            "name": ["North Anna Power Station", None],
            "operator": ["Dominion", "Dominion"],
            "plant:source": ["nuclear", None],
            "plant:output:electricity": ["1892 MW", None],
            "voltage": [None, "230000;115000"],
            "lat": [38.06, 38.90],
            "lon": [-77.79, -77.40],
            "geoid": ["51085", "51059"],
        }
    )


def test_shape_to_point_schema_columns_and_types():
    out = shape_to_point_schema(_sample_enriched_rows(), snapshot_year=2026)

    required = ["facility_id", "facility_name", "lat", "lon", "year", "type"]
    for col in required:
        assert col in out.columns
    for col in ["operator", "plant_source", "plant_capacity_mw", "voltage", "osm_id", "geoid"]:
        assert col in out.columns

    assert list(out["type"]) == ["power_plant", "substation"]
    assert list(out["year"]) == [2026, 2026]


def test_shape_to_point_schema_facility_id_and_name_fallback():
    out = shape_to_point_schema(_sample_enriched_rows(), snapshot_year=2026)

    assert list(out["facility_id"]) == ["osm_way_111", "osm_node_222"]
    # Named feature keeps its name; unnamed gets a generated fallback.
    assert out.loc[0, "facility_name"] == "North Anna Power Station"
    assert out.loc[1, "facility_name"] == "substation (OSM 222)"


def test_shape_to_point_schema_capacity_parsed():
    out = shape_to_point_schema(_sample_enriched_rows(), snapshot_year=2026)
    assert out.loc[0, "plant_capacity_mw"] == pytest.approx(1892.0)
    assert math.isnan(out.loc[1, "plant_capacity_mw"])


def test_shape_to_point_schema_handles_missing_optional_columns():
    """If no feature carried e.g. `operator`, the column may be absent entirely."""
    rows = _sample_enriched_rows().drop(columns=["operator", "voltage"])
    out = shape_to_point_schema(rows, snapshot_year=2026)
    assert "operator" in out.columns
    assert out["operator"].isna().all()
    assert "voltage" in out.columns
    assert out["voltage"].isna().all()
