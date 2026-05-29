"""Unit tests for PowerInfrastructure pure transforms (HIFLD source)."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from transforms import (
    ENERGY_LONG_FORMAT_COLUMNS,
    aggregate_to_counties,
    clean_numeric,
    shape_records,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        (8.4, 8.4),
        ("21.6", 21.6),
        (0, 0.0),
        (161, 161.0),
        (-999999, math.nan),
        (-999999.0, math.nan),
        ("-999999", math.nan),
        (None, math.nan),
        ("", math.nan),
        ("abc", math.nan),
    ],
)
def test_clean_numeric(raw, expected):
    result = clean_numeric(raw)
    if isinstance(expected, float) and math.isnan(expected):
        assert math.isnan(result)
    else:
        assert result == pytest.approx(expected)


def _sample_plants():
    return pd.DataFrame(
        {
            "PLANT_CODE": ["3803", "3804"],
            "NAME": ["BUCK HYDRO", ""],
            "COUNTYFIPS": ["51035", "51155"],
            "LATITUDE": [36.808, 37.074],
            "LONGITUDE": [-80.938, -80.584],
            "TYPE": ["CONVENTIONAL HYDROELECTRIC", "NUCLEAR"],
            "STATUS": ["OP", "OP"],
            "OPERATOR": ["APPALACHIAN POWER CO", "DOMINION"],
            "PRIM_FUEL": ["WAT", "NUC"],
            "OPER_CAP": [8.4, -999999],
        }
    )


def _sample_substations():
    return pd.DataFrame(
        {
            "ID": ["108970", "109426"],
            "NAME": ["IMBODEN", "UNKNOWN109426"],
            "COUNTYFIPS": ["51195", "51105"],
            "LATITUDE": [36.881, 36.726],
            "LONGITUDE": [-82.812, -83.110],
            "TYPE": ["SUBSTATION", "SUBSTATION"],
            "STATUS": ["IN SERVICE", "IN SERVICE"],
            "MAX_VOLT": [161, -999999],
            "MIN_VOLT": [69, -999999],
            "LINES": [7, 1],
        }
    )


def test_shape_records_plants_columns_and_ids():
    out = shape_records(
        _sample_plants(), kind="power_plant", id_field="PLANT_CODE",
        id_prefix="hifld_pp", snapshot_year=2026,
    )
    for col in ["facility_id", "facility_name", "lat", "lon", "year", "type",
                "status", "operator", "plant_source", "plant_capacity_mw",
                "max_voltage", "lines", "geoid", "source_id"]:
        assert col in out.columns
    assert list(out["facility_id"]) == ["hifld_pp_3803", "hifld_pp_3804"]
    assert (out["type"] == "power_plant").all()
    assert (out["year"] == 2026).all()
    assert list(out["geoid"]) == ["51035", "51155"]


def test_shape_records_name_fallback_and_capacity_sentinel():
    out = shape_records(
        _sample_plants(), kind="power_plant", id_field="PLANT_CODE",
        id_prefix="hifld_pp", snapshot_year=2026,
    )
    assert out.loc[0, "facility_name"] == "BUCK HYDRO"
    assert out.loc[1, "facility_name"] == "power_plant (3804)"   # empty NAME -> fallback
    assert out.loc[0, "plant_capacity_mw"] == pytest.approx(8.4)
    assert math.isnan(out.loc[1, "plant_capacity_mw"])           # -999999 -> NaN


def test_shape_records_substations_voltage_sentinel():
    out = shape_records(
        _sample_substations(), kind="substation", id_field="ID",
        id_prefix="hifld_ss", snapshot_year=2026,
    )
    assert list(out["facility_id"]) == ["hifld_ss_108970", "hifld_ss_109426"]
    assert (out["type"] == "substation").all()
    assert out.loc[0, "max_voltage"] == pytest.approx(161.0)
    assert math.isnan(out.loc[1, "max_voltage"])                 # -999999 -> NaN
    # substations have no OPER_CAP column -> capacity all NaN
    assert out["plant_capacity_mw"].isna().all()


def _sample_point_rows():
    return pd.DataFrame(
        {
            "facility_id": ["hifld_pp_1", "hifld_pp_2", "hifld_ss_3", "hifld_ss_4", "hifld_pp_5"],
            "type": ["power_plant", "power_plant", "substation", "substation", "power_plant"],
            "plant_capacity_mw": [100.0, 50.0, float("nan"), float("nan"), 25.0],
            "geoid": ["51035", "51035", "51035", "51155", ""],   # last row has invalid geoid
        }
    )


def test_aggregate_to_counties_schema():
    out = aggregate_to_counties(
        _sample_point_rows(), scenario="hifld_snapshot_2026_05_29",
        scenario_date="2026-05-29",
    )
    assert list(out.columns) == ENERGY_LONG_FORMAT_COLUMNS
    assert set(out["measure"]) == {
        "power_plant_count", "substation_count",
        "power_facility_count", "total_plant_capacity_mw",
    }
    assert (out["region_type"] == "county").all()
    assert (out["data_method"] == "observed").all()
    assert (out["scenario"] == "hifld_snapshot_2026_05_29").all()
    assert (out["datetime"] == "2026-05-29").all()


def test_aggregate_to_counties_values_and_invalid_geoid_dropped():
    out = aggregate_to_counties(
        _sample_point_rows(), scenario="hifld_snapshot_2026_05_29",
        scenario_date="2026-05-29",
    )

    def val(geoid, measure):
        sel = out[(out["geoid"] == geoid) & (out["measure"] == measure)]
        return sel["value"].iloc[0] if len(sel) else None

    # The row with empty geoid is dropped, so 51035 has 2 plants (not 3).
    assert val("51035", "power_plant_count") == 2
    assert val("51035", "substation_count") == 1
    assert val("51035", "power_facility_count") == 3
    assert val("51035", "total_plant_capacity_mw") == pytest.approx(150.0)
    assert val("51155", "substation_count") == 1
    assert val("51155", "power_plant_count") == 0   # zero-filled
    assert val("51155", "total_plant_capacity_mw") == pytest.approx(0.0)
    # No county row for the invalid/empty geoid.
    assert "" not in set(out["geoid"])


def test_aggregate_to_counties_empty():
    out = aggregate_to_counties(
        pd.DataFrame(columns=["facility_id", "type", "plant_capacity_mw", "geoid"]),
        scenario="s", scenario_date="2026-05-29",
    )
    assert list(out.columns) == ENERGY_LONG_FORMAT_COLUMNS
    assert len(out) == 0
