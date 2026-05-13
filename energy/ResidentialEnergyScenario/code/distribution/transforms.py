"""Pure transformation functions for the ResidentialEnergyScenario pipeline.

The three compute functions (compute_adoption_measures,
compute_residential_load, compute_pv_generation) land in a follow-up task.
This file currently provides shared infrastructure.
"""

from __future__ import annotations

import pandas as pd


ENERGY_LONG_FORMAT_COLUMNS = [
    "geoid",
    "datetime",
    "measure",
    "value",
    "moe",
    "region_type",
    "data_method",
    "scenario",
]


def add_geoid(df: pd.DataFrame, *, region_type: str) -> pd.DataFrame:
    """Add a 5- or 11-digit FIPS `geoid` column from admin codes.

    Required columns: admin1, admin2; admin3 also required for region_type="tract".

    region_type:
        "county" → geoid = admin1.zfill(2) + admin2.zfill(3)        (5 chars)
        "tract"  → geoid = admin1.zfill(2) + admin2.zfill(3) + admin3.zfill(6)  (11 chars)
    """
    if region_type not in ("county", "tract"):
        raise ValueError(
            f"region_type must be 'county' or 'tract', got {region_type!r}"
        )

    out = df.copy()
    geoid_str = (
        out["admin1"].astype(int).astype(str).str.zfill(2)
        + out["admin2"].astype(int).astype(str).str.zfill(3)
    )
    if region_type == "tract":
        geoid_str = geoid_str + out["admin3"].astype(int).astype(str).str.zfill(6)

    # Force numpy object dtype (not pandas StringDtype) so tests that assert
    # `dtype == object` pass under pandas 3.x.
    out["geoid"] = geoid_str.astype(object)
    return out


def compute_adoption_measures(
    household_df: pd.DataFrame,
    adoption_df: pd.DataFrame,
    *,
    region_type: str,
    scenario: str,
) -> pd.DataFrame:
    """Compute 4 static measures (counts + 3 adoption rates) per geoid.

    Joins household + adoption on `hid`, constructs `geoid` for the requested
    resolution, then groups to compute counts and means.
    """
    merged = household_df[["hid", "admin1", "admin2", "admin3", "admin4"]].merge(
        adoption_df[["hid", "is_pv", "is_ev", "is_battery"]],
        on="hid",
        how="inner",
    )
    merged = add_geoid(merged, region_type=region_type)

    grp = merged.groupby("geoid")
    counts = grp.size()
    pv = grp["is_pv"].mean()
    ev = grp["is_ev"].mean()
    bat = grp["is_battery"].mean()

    geoids = counts.index.tolist()
    rows = []

    base = dict(
        datetime="2030-01-01",
        moe=pd.NA,
        region_type=region_type,
        data_method="simulated",
        scenario=scenario,
    )

    for g in geoids:
        rows.append({"geoid": g, "measure": "synthetic_household_count", "value": float(counts[g]), **base})
        rows.append({"geoid": g, "measure": "pv_adoption_rate", "value": float(pv[g]), **base})
        rows.append({"geoid": g, "measure": "ev_adoption_rate", "value": float(ev[g]), **base})
        rows.append({"geoid": g, "measure": "battery_adoption_rate", "value": float(bat[g]), **base})

    out = pd.DataFrame(rows)
    return out[ENERGY_LONG_FORMAT_COLUMNS]


def compute_residential_load(
    resstock_df: pd.DataFrame,
    household_df: pd.DataFrame,
    *,
    region_type: str,
    scenario: str,
    scenario_year: int,
) -> pd.DataFrame:
    """Hourly residential load per (geoid, hour), scaled from ResStock sample.

    For each (geoid, hour h):
        mean_load_h = mean of `total_kwh_{h+1}` across ResStock households in geoid
                     (ResStock columns are 1-indexed; total_kwh_1 = hour 0)
        n_synth      = count of synthetic households in geoid (from household_df)
        value        = mean_load_h × n_synth

    Geoids without any ResStock representation emit NaN value for all 24 hours.
    """
    # Household-side: geoid + synthetic count per geoid
    hh = add_geoid(household_df[["admin1", "admin2", "admin3", "admin4", "hid"]].copy(),
                   region_type=region_type)
    n_synth = hh.groupby("geoid").size().rename("n_synth")

    # ResStock-side: attach geoid via household admin codes
    rs = resstock_df.merge(
        household_df[["hid", "admin1", "admin2", "admin3", "admin4"]],
        on="hid",
        how="inner",
    )
    rs = add_geoid(rs, region_type=region_type)

    # Per-geoid mean of total_kwh_{h+1} for each hour h
    hour_cols = [f"total_kwh_{i}" for i in range(1, 25)]
    means_by_geoid = rs.groupby("geoid")[hour_cols].mean()
    # Reindex onto the full set of geoids in n_synth (so geoids w/o ResStock get NaN)
    means_by_geoid = means_by_geoid.reindex(n_synth.index)

    rows = []
    base = dict(
        moe=pd.NA,
        region_type=region_type,
        data_method="simulated",
        scenario=scenario,
        measure="residential_load_kwh",
    )

    for g in n_synth.index:
        n = float(n_synth[g])
        for h in range(24):
            mean_kwh = means_by_geoid.at[g, f"total_kwh_{h + 1}"]
            value = pd.NA if pd.isna(mean_kwh) else float(mean_kwh) * n
            rows.append({
                "geoid": g,
                "datetime": f"{scenario_year}-01-01T{h:02d}:00:00",
                "value": value,
                **base,
            })

    out = pd.DataFrame(rows)
    return out[ENERGY_LONG_FORMAT_COLUMNS]


def compute_pv_generation(
    pv_profiles_df: pd.DataFrame,
    adoption_df: pd.DataFrame,
    household_df: pd.DataFrame,
    *,
    region_type: str,
    scenario: str,
    scenario_year: int,
) -> pd.DataFrame:
    """Hourly PV generation per (geoid, hour), scaled to total adopters.

    For each (geoid, hour h):
        profile_subset = PV profiles for is_pv=1 households whose hid is in the profile file
        mean_kw_h      = mean of `avg_{h}` across that subset in the geoid
        n_pv_adopters  = count of is_pv=1 households in the geoid (from full adoption_df)
        value          = mean_kw_h × n_pv_adopters    (kW × 1 hr → kWh)

    Geoids with PV adopters but no profile representation emit NaN.
    Geoids with zero PV adopters are absent from the output.
    """
    # Geoid-tagged adoption table
    ad = adoption_df[["admin1", "admin2", "admin3", "admin4", "hid", "is_pv"]].copy()
    ad = add_geoid(ad, region_type=region_type)

    # n_pv_adopters per geoid (only geoids with at least one adopter survive)
    n_pv = ad[ad["is_pv"] == 1].groupby("geoid").size().rename("n_pv")
    if n_pv.empty:
        return pd.DataFrame(columns=ENERGY_LONG_FORMAT_COLUMNS)

    # Profiles joined with admin codes (via household) and filtered to is_pv=1
    prof_join = (
        pv_profiles_df
        .merge(household_df[["hid", "admin1", "admin2", "admin3", "admin4"]], on="hid", how="inner")
        .merge(adoption_df[["hid", "is_pv"]], on="hid", how="inner")
    )
    prof_pv = prof_join[prof_join["is_pv"] == 1].copy()
    prof_pv = add_geoid(prof_pv, region_type=region_type)

    avg_cols = [f"avg_{h}" for h in range(24)]
    means_by_geoid = prof_pv.groupby("geoid")[avg_cols].mean()
    means_by_geoid = means_by_geoid.reindex(n_pv.index)

    rows = []
    base = dict(
        moe=pd.NA,
        region_type=region_type,
        data_method="simulated",
        scenario=scenario,
        measure="pv_generation_kwh",
    )

    for g in n_pv.index:
        n = float(n_pv[g])
        for h in range(24):
            mean_kw = means_by_geoid.at[g, f"avg_{h}"]
            value = pd.NA if pd.isna(mean_kw) else float(mean_kw) * n
            rows.append({
                "geoid": g,
                "datetime": f"{scenario_year}-01-01T{h:02d}:00:00",
                "value": value,
                **base,
            })

    out = pd.DataFrame(rows)
    return out[ENERGY_LONG_FORMAT_COLUMNS]
