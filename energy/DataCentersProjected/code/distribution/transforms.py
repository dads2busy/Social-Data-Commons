"""Pure transformation functions for the DataCentersProjected pipeline.

Source: IM3 CERF projected data center siting (20 scenarios). Pure functions
only; all file I/O and geopandas reproject/centroid/sjoin lives in ingest.py.
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


def scenario_label(growth_scenario: str, market_gravity_weight: int) -> str:
    """Canonical scenario label: 'im3_cerf_{tier}_{weight}'."""
    return f"im3_cerf_{growth_scenario}_{int(market_gravity_weight)}"


def shape_to_point_schema(rows: pd.DataFrame, *, snapshot_year: int) -> pd.DataFrame:
    """Reshape enriched rows into the energy point schema.

    Input must already have these columns attached:
        id, growth_scenario, market_gravity_weight, scenario, region,
        geoid, lat, lon, plus all the source attribute columns.
    """
    out = pd.DataFrame({
        "facility_id": "im3_cerf_" + rows["id"].astype(str)
                       + "_" + rows["growth_scenario"].astype(str)
                       + "_" + rows["market_gravity_weight"].astype(int).astype(str),
        "facility_name": "Projected Data Center (" + rows["scenario"].astype(str) + ")",
        "lat": rows["lat"].astype(float),
        "lon": rows["lon"].astype(float),
        "year": snapshot_year,
        "type": "projected_data_center",
        "scenario": rows["scenario"].astype(str),
        "geoid": rows["geoid"].astype(str).astype(object),
        "growth_scenario": rows["growth_scenario"].astype(str),
        "market_gravity_weight": rows["market_gravity_weight"].astype(int),
        "data_center_it_power_mw": rows["data_center_it_power_mw"],
        "campus_size_square_ft": rows["campus_size_square_ft"],
        "total_cost_million_usd": rows["total_cost_million_usd"],
        "cooling_water_demand_mgy": rows["cooling_water_demand_mgy"],
        "cooling_water_consumption_mgy": rows["cooling_water_consumption_mgy"],
        "cooling_energy_demand_mwh": rows["cooling_energy_demand_mwh"],
        "mechanical_cooling_frac": rows["mechanical_cooling_frac"],
        "water_cooling_frac": rows["water_cooling_frac"],
        "normalized_locational_cost": rows["normalized_locational_cost"],
        "normalized_gravity_score": rows["normalized_gravity_score"],
        "weighted_siting_score": rows["weighted_siting_score"],
        "source_id": rows["id"].astype(str),
    })
    return out


def aggregate_to_counties(
    point_rows: pd.DataFrame,
    *,
    scenario_date: str,
) -> pd.DataFrame:
    """Aggregate shaped point rows to (county, scenario) long-format measures.

    Required input columns:
        geoid, scenario, type, data_center_it_power_mw, campus_size_square_ft,
        total_cost_million_usd, cooling_water_demand_mgy,
        cooling_water_consumption_mgy, cooling_energy_demand_mwh

    Produces 6 measures per (geoid, scenario):
        projected_data_center_count            row count
        total_projected_it_power_mw            sum
        total_projected_campus_sqft            sum
        total_projected_cost_million_usd       sum
        total_projected_water_demand_mgy       sum
        total_projected_water_consumption_mgy  sum
    """
    if len(point_rows) == 0:
        return pd.DataFrame(columns=ENERGY_LONG_FORMAT_COLUMNS)

    rows = []

    # Count
    counts = point_rows.groupby(["geoid", "scenario"]).size()
    for (geoid, scenario), value in counts.items():
        rows.append({
            "geoid": str(geoid),
            "datetime": scenario_date,
            "measure": "projected_data_center_count",
            "value": int(value),
            "moe": pd.NA,
            "region_type": "county",
            "data_method": "simulated",
            "scenario": scenario,
        })

    # Sum-style measures
    sum_specs = [
        ("data_center_it_power_mw", "total_projected_it_power_mw"),
        ("campus_size_square_ft", "total_projected_campus_sqft"),
        ("total_cost_million_usd", "total_projected_cost_million_usd"),
        ("cooling_water_demand_mgy", "total_projected_water_demand_mgy"),
        ("cooling_water_consumption_mgy", "total_projected_water_consumption_mgy"),
    ]

    for src_col, measure_name in sum_specs:
        sums = (
            point_rows.assign(_v=pd.to_numeric(point_rows[src_col], errors="coerce").fillna(0))
            .groupby(["geoid", "scenario"])["_v"]
            .sum()
        )
        for (geoid, scenario), value in sums.items():
            rows.append({
                "geoid": str(geoid),
                "datetime": scenario_date,
                "measure": measure_name,
                "value": float(value),
                "moe": pd.NA,
                "region_type": "county",
                "data_method": "simulated",
                "scenario": scenario,
            })

    out = pd.DataFrame(rows)
    return out[ENERGY_LONG_FORMAT_COLUMNS]
