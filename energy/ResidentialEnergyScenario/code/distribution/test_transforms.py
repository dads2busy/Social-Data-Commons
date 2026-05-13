"""Unit tests for ResidentialEnergyScenario transforms."""

import pandas as pd
import pytest

from transforms import (
    ENERGY_LONG_FORMAT_COLUMNS,
    add_geoid,
)


# --- add_geoid tests ---


def _admin_sample():
    return pd.DataFrame({
        "admin1": [51, 51, 51, 51],
        "admin2": [1, 107, 59, 199],          # 1=Accomack, 107=Loudoun, 59=Fairfax, 199=York
        "admin3": [90100, 612101, 460402, 50204],
        "admin4": [1, 2, 1, 3],
        "hid": [1, 2, 3, 4],
    })


def test_add_geoid_county_produces_5_digit_string():
    out = add_geoid(_admin_sample(), region_type="county")
    assert list(out["geoid"]) == ["51001", "51107", "51059", "51199"]
    assert out["geoid"].dtype == object
    assert all(len(g) == 5 for g in out["geoid"])


def test_add_geoid_tract_produces_11_digit_string():
    out = add_geoid(_admin_sample(), region_type="tract")
    assert list(out["geoid"]) == ["51001090100", "51107612101", "51059460402", "51199050204"]
    assert all(len(g) == 11 for g in out["geoid"])


def test_add_geoid_zero_pads_admin3():
    # admin3 with fewer than 6 digits must zero-pad on the left
    df = pd.DataFrame({"admin1": [51], "admin2": [1], "admin3": [502], "admin4": [1], "hid": [1]})
    out = add_geoid(df, region_type="tract")
    assert out["geoid"].iloc[0] == "51001000502"


def test_add_geoid_zero_pads_admin1_admin2():
    # An admin1=1 should become "01" (2 digits); admin2=1 should become "001" (3 digits)
    df = pd.DataFrame({"admin1": [1], "admin2": [1], "admin3": [90100], "admin4": [1], "hid": [1]})
    out = add_geoid(df, region_type="county")
    assert out["geoid"].iloc[0] == "01001"


def test_add_geoid_invalid_region_type_raises():
    with pytest.raises(ValueError, match="region_type"):
        add_geoid(_admin_sample(), region_type="block_group")


def test_add_geoid_preserves_other_columns():
    out = add_geoid(_admin_sample(), region_type="county")
    # The hid column should still be there
    assert "hid" in out.columns
    assert list(out["hid"]) == [1, 2, 3, 4]


def test_energy_long_format_columns_constant():
    assert ENERGY_LONG_FORMAT_COLUMNS == [
        "geoid", "datetime", "measure", "value", "moe",
        "region_type", "data_method", "scenario",
    ]
