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


# --- compute_adoption_measures tests ---

from transforms import compute_adoption_measures


def _household_sample():
    """4 households across 2 counties (51001 and 51107). Each county has 1 tract."""
    return pd.DataFrame({
        "admin1": [51, 51, 51, 51],
        "admin2": [1, 1, 107, 107],
        "admin3": [90100, 90100, 612101, 612101],
        "admin4": [1, 1, 2, 2],
        "hid": [11, 12, 13, 14],
        "hh_unit_wt": [10, 5, 20, 15],
    })


def _adoption_sample():
    """Matches the household sample on hid. 51001: 1 PV + 1 EV + 0 batt. 51107: 0 PV + 2 EV + 1 batt."""
    return pd.DataFrame({
        "admin1": [51, 51, 51, 51],
        "admin2": [1, 1, 107, 107],
        "admin3": [90100, 90100, 612101, 612101],
        "admin4": [1, 1, 2, 2],
        "hid": [11, 12, 13, 14],
        "is_pv": [1, 0, 0, 0],
        "is_ev": [1, 0, 1, 1],
        "is_battery": [0, 0, 0, 1],
    })


def test_adoption_measures_county_produces_4_measures():
    out = compute_adoption_measures(
        _household_sample(), _adoption_sample(),
        region_type="county", scenario="s1",
    )
    assert set(out["measure"].unique()) == {
        "synthetic_household_count", "pv_adoption_rate",
        "ev_adoption_rate", "battery_adoption_rate",
    }


def test_adoption_measures_long_format_schema():
    out = compute_adoption_measures(
        _household_sample(), _adoption_sample(),
        region_type="county", scenario="s1",
    )
    assert set(out.columns) == {
        "geoid", "datetime", "measure", "value", "moe",
        "region_type", "data_method", "scenario",
    }


def test_adoption_measures_county_household_count():
    out = compute_adoption_measures(
        _household_sample(), _adoption_sample(),
        region_type="county", scenario="s1",
    )
    r = out[(out["geoid"] == "51001") & (out["measure"] == "synthetic_household_count")].iloc[0]
    assert r["value"] == 2
    r = out[(out["geoid"] == "51107") & (out["measure"] == "synthetic_household_count")].iloc[0]
    assert r["value"] == 2


def test_adoption_measures_county_pv_rate():
    out = compute_adoption_measures(
        _household_sample(), _adoption_sample(),
        region_type="county", scenario="s1",
    )
    # 51001: 1 of 2 PV adopters = 0.5; 51107: 0 of 2 = 0.0
    r = out[(out["geoid"] == "51001") & (out["measure"] == "pv_adoption_rate")].iloc[0]
    assert r["value"] == 0.5
    r = out[(out["geoid"] == "51107") & (out["measure"] == "pv_adoption_rate")].iloc[0]
    assert r["value"] == 0.0


def test_adoption_measures_county_ev_rate():
    out = compute_adoption_measures(
        _household_sample(), _adoption_sample(),
        region_type="county", scenario="s1",
    )
    # 51001: 1 of 2; 51107: 2 of 2 = 1.0
    r = out[(out["geoid"] == "51001") & (out["measure"] == "ev_adoption_rate")].iloc[0]
    assert r["value"] == 0.5
    r = out[(out["geoid"] == "51107") & (out["measure"] == "ev_adoption_rate")].iloc[0]
    assert r["value"] == 1.0


def test_adoption_measures_county_battery_rate():
    out = compute_adoption_measures(
        _household_sample(), _adoption_sample(),
        region_type="county", scenario="s1",
    )
    r = out[(out["geoid"] == "51107") & (out["measure"] == "battery_adoption_rate")].iloc[0]
    assert r["value"] == 0.5


def test_adoption_measures_datetime_is_static():
    out = compute_adoption_measures(
        _household_sample(), _adoption_sample(),
        region_type="county", scenario="s1",
    )
    assert (out["datetime"] == "2030-01-01").all()


def test_adoption_measures_data_method_simulated():
    out = compute_adoption_measures(
        _household_sample(), _adoption_sample(),
        region_type="county", scenario="s1",
    )
    assert (out["data_method"] == "simulated").all()


def test_adoption_measures_region_type_propagates():
    out = compute_adoption_measures(
        _household_sample(), _adoption_sample(),
        region_type="tract", scenario="s1",
    )
    assert (out["region_type"] == "tract").all()
    # Tract resolution → all geoids are 11 chars
    assert all(len(g) == 11 for g in out["geoid"])


def test_adoption_measures_scenario_propagates():
    out = compute_adoption_measures(
        _household_sample(), _adoption_sample(),
        region_type="county", scenario="my_scenario",
    )
    assert (out["scenario"] == "my_scenario").all()


def test_adoption_measures_moe_is_null():
    out = compute_adoption_measures(
        _household_sample(), _adoption_sample(),
        region_type="county", scenario="s1",
    )
    assert out["moe"].isna().all()


# --- compute_residential_load tests ---

from transforms import compute_residential_load


def _resstock_sample():
    """Resstock rows for 3 households (all in county 51001 / tract 51001090100).

    Hourly columns: total_kwh_1..total_kwh_24. Use a sparse pattern so the
    test can verify per-hour means without arithmetic ambiguity.

    hid 99 is not in _household_for_load(), so the join drops it — ensuring
    county 51107 has no ResStock representation.
    """
    base = {
        "hid": [11, 12, 99],
    }
    # total_kwh_1 (hour 0): 1, 2, 3 → mean 2.0
    # total_kwh_7 (hour 6): 10, 20, 30 → mean 20.0
    # All other hours: 0
    for h in range(1, 25):
        if h == 1:
            base[f"total_kwh_{h}"] = [1.0, 2.0, 3.0]
        elif h == 7:
            base[f"total_kwh_{h}"] = [10.0, 20.0, 30.0]
        else:
            base[f"total_kwh_{h}"] = [0.0, 0.0, 0.0]
    return pd.DataFrame(base)


def _household_for_load():
    """4 synthetic households across 2 counties — county 51001 has 2,
    county 51107 has 2 — but only county 51001 has any ResStock representation."""
    return pd.DataFrame({
        "admin1": [51, 51, 51, 51],
        "admin2": [1, 1, 107, 107],
        "admin3": [90100, 90100, 612101, 612101],
        "admin4": [1, 1, 2, 2],
        "hid": [11, 12, 13, 14],
        "hh_unit_wt": [10, 5, 20, 15],
    })


def test_load_returns_24_hours_per_geoid_with_resstock():
    out = compute_residential_load(
        _resstock_sample(), _household_for_load(),
        region_type="county", scenario="s1", scenario_year=2030,
    )
    # County 51001 has ResStock rows → 24 hourly values produced
    rows_51001 = out[out["geoid"] == "51001"]
    assert len(rows_51001) == 24
    assert set(rows_51001["datetime"]) == {
        f"2030-01-01T{h:02d}:00:00" for h in range(24)
    }


def test_load_hour_0_value_scales_mean_by_county_count():
    # County 51001 has 2 synthetic households (hids 11,12 in household_df).
    # But ResStock covers hids 11,12,13 — only 11,12 are in this county
    # after joining ResStock to household. mean total_kwh_1 across hids 11,12 = (1+2)/2 = 1.5
    # × n_synth_households_in_51001 (2) = 3.0
    out = compute_residential_load(
        _resstock_sample(), _household_for_load(),
        region_type="county", scenario="s1", scenario_year=2030,
    )
    r = out[(out["geoid"] == "51001") & (out["datetime"] == "2030-01-01T00:00:00")].iloc[0]
    assert r["value"] == 3.0


def test_load_hour_6_value():
    # mean total_kwh_7 across hids 11,12 = (10+20)/2 = 15.0 × 2 = 30.0
    out = compute_residential_load(
        _resstock_sample(), _household_for_load(),
        region_type="county", scenario="s1", scenario_year=2030,
    )
    r = out[(out["geoid"] == "51001") & (out["datetime"] == "2030-01-01T06:00:00")].iloc[0]
    assert r["value"] == 30.0


def test_load_county_without_resstock_emits_nan():
    # County 51107 has 2 synthetic households but NO ResStock rows.
    # Per design: emit NaN for all 24 hours.
    out = compute_residential_load(
        _resstock_sample(), _household_for_load(),
        region_type="county", scenario="s1", scenario_year=2030,
    )
    rows_51107 = out[out["geoid"] == "51107"]
    assert len(rows_51107) == 24
    assert rows_51107["value"].isna().all()


def test_load_only_one_measure_name():
    out = compute_residential_load(
        _resstock_sample(), _household_for_load(),
        region_type="county", scenario="s1", scenario_year=2030,
    )
    assert set(out["measure"].unique()) == {"residential_load_kwh"}


def test_load_long_format_schema():
    out = compute_residential_load(
        _resstock_sample(), _household_for_load(),
        region_type="county", scenario="s1", scenario_year=2030,
    )
    assert set(out.columns) == {
        "geoid", "datetime", "measure", "value", "moe",
        "region_type", "data_method", "scenario",
    }


def test_load_data_method_simulated():
    out = compute_residential_load(
        _resstock_sample(), _household_for_load(),
        region_type="county", scenario="s1", scenario_year=2030,
    )
    assert (out["data_method"] == "simulated").all()


def test_load_region_type_propagates_tract():
    out = compute_residential_load(
        _resstock_sample(), _household_for_load(),
        region_type="tract", scenario="s1", scenario_year=2030,
    )
    assert (out["region_type"] == "tract").all()
    # 11-char geoids
    for g in out["geoid"].dropna():
        assert len(g) == 11


# --- compute_pv_generation tests ---

from transforms import compute_pv_generation


def _pv_profiles_sample():
    """Profiles for 2 households (hids 11, 12 in county 51001).

    avg_h: kW at hour h (0-indexed columns). Use a sparse pattern.
    """
    base = {"hid": [11, 12]}
    for h in range(24):
        if h == 12:
            base[f"avg_{h}"] = [2.0, 4.0]   # noon peak
        else:
            base[f"avg_{h}"] = [0.0, 0.0]
        base[f"std_{h}"] = [0.1, 0.1]
    base["avg_daily"] = [2.0, 4.0]
    base["std_daily"] = [0.1, 0.1]
    return pd.DataFrame(base)


def _adoption_for_pv():
    """4 households: 3 in 51001 (2 PV adopters, 1 not), 1 in 51107 (PV adopter).
    PV profile file only covers hids 11, 12 (which ARE the 51001 adopters).
    """
    return pd.DataFrame({
        "admin1": [51, 51, 51, 51],
        "admin2": [1, 1, 1, 107],
        "admin3": [90100, 90100, 90100, 612101],
        "admin4": [1, 1, 1, 2],
        "hid": [11, 12, 13, 14],
        "is_pv": [1, 1, 0, 1],
    })


def _household_for_pv():
    """Same 4 households as the adoption sample (admin codes only)."""
    return pd.DataFrame({
        "admin1": [51, 51, 51, 51],
        "admin2": [1, 1, 1, 107],
        "admin3": [90100, 90100, 90100, 612101],
        "admin4": [1, 1, 1, 2],
        "hid": [11, 12, 13, 14],
    })


def test_pv_hour_12_value_scales_mean_by_total_adopters_in_county():
    # County 51001: profiled adopters are hids 11, 12 → mean avg_12 = (2+4)/2 = 3.0 kW
    # n_pv_adopters in 51001 = 2 (both are is_pv=1)
    # value = 3.0 × 2 = 6.0 kWh
    out = compute_pv_generation(
        _pv_profiles_sample(), _adoption_for_pv(), _household_for_pv(),
        region_type="county", scenario="s1", scenario_year=2030,
    )
    r = out[(out["geoid"] == "51001") & (out["datetime"] == "2030-01-01T12:00:00")].iloc[0]
    assert r["value"] == 6.0


def test_pv_hour_0_value_is_zero_for_profiled_county():
    out = compute_pv_generation(
        _pv_profiles_sample(), _adoption_for_pv(), _household_for_pv(),
        region_type="county", scenario="s1", scenario_year=2030,
    )
    r = out[(out["geoid"] == "51001") & (out["datetime"] == "2030-01-01T00:00:00")].iloc[0]
    assert r["value"] == 0.0


def test_pv_county_with_adopter_but_no_profile_emits_nan():
    # County 51107 has 1 PV adopter (hid 14) but NO profile for hid 14.
    # Per design: emit NaN for all 24 hours.
    out = compute_pv_generation(
        _pv_profiles_sample(), _adoption_for_pv(), _household_for_pv(),
        region_type="county", scenario="s1", scenario_year=2030,
    )
    rows_51107 = out[out["geoid"] == "51107"]
    assert len(rows_51107) == 24
    assert rows_51107["value"].isna().all()


def test_pv_only_one_measure_name():
    out = compute_pv_generation(
        _pv_profiles_sample(), _adoption_for_pv(), _household_for_pv(),
        region_type="county", scenario="s1", scenario_year=2030,
    )
    assert set(out["measure"].unique()) == {"pv_generation_kwh"}


def test_pv_24_hours_per_geoid():
    out = compute_pv_generation(
        _pv_profiles_sample(), _adoption_for_pv(), _household_for_pv(),
        region_type="county", scenario="s1", scenario_year=2030,
    )
    # 2 distinct geoids × 24 hours = 48 rows
    assert len(out) == 48


def test_pv_long_format_schema():
    out = compute_pv_generation(
        _pv_profiles_sample(), _adoption_for_pv(), _household_for_pv(),
        region_type="county", scenario="s1", scenario_year=2030,
    )
    assert set(out.columns) == {
        "geoid", "datetime", "measure", "value", "moe",
        "region_type", "data_method", "scenario",
    }


def test_pv_data_method_simulated():
    out = compute_pv_generation(
        _pv_profiles_sample(), _adoption_for_pv(), _household_for_pv(),
        region_type="county", scenario="s1", scenario_year=2030,
    )
    assert (out["data_method"] == "simulated").all()


def test_pv_county_with_zero_adopters_is_absent():
    # If a county has zero PV adopters AND zero profiles, it shouldn't appear at all.
    # Build a 3-household sample where county 51199 has rows but no PV.
    household = pd.DataFrame({
        "admin1": [51, 51, 51],
        "admin2": [1, 1, 199],
        "admin3": [90100, 90100, 50204],
        "admin4": [1, 1, 1],
        "hid": [11, 12, 15],
    })
    adoption = pd.DataFrame({
        "admin1": [51, 51, 51],
        "admin2": [1, 1, 199],
        "admin3": [90100, 90100, 50204],
        "admin4": [1, 1, 1],
        "hid": [11, 12, 15],
        "is_pv": [1, 1, 0],
    })
    out = compute_pv_generation(
        _pv_profiles_sample(), adoption, household,
        region_type="county", scenario="s1", scenario_year=2030,
    )
    # County 51199 has zero PV adopters AND zero profiles → not in output
    assert "51199" not in out["geoid"].values
