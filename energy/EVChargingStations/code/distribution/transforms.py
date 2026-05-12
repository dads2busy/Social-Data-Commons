"""Pure transformation functions for the EV Charging Stations pipeline.

These functions take and return DataFrames; they do no file I/O. Wrappers
in ingest.py call them in sequence.
"""

from __future__ import annotations

import pandas as pd


CHARGER_LEVELS = ("l1", "l2", "l3")
SCENARIO_YEAR = 2030

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


def expand_multi_type_rows(stations: pd.DataFrame) -> pd.DataFrame:
    """Expand each station row into one row per non-zero charger level.

    A station with l1=0, l2=1, l3=2 produces two rows:
        type=l2, count=1
        type=l3, count=2

    Output columns:
        facility_id   str   "{ID}_{level}"     unique per row
        facility_name str   "VA Charging Station {ID}"
        lat, lon      float from the source columns
        year          int   SCENARIO_YEAR (2030)
        type          str   one of "l1", "l2", "l3"
        count         int   count of THAT level at this station
        station_id    int   raw source ID (for downstream dedup)
        fuel_type_code str  pass-through from source
    """
    parts = []
    for level in CHARGER_LEVELS:
        col = f"{level}_charger_count"
        mask = stations[col] > 0
        if not mask.any():
            continue
        sub = stations.loc[mask].copy()
        parts.append(pd.DataFrame({
            "facility_id": sub["ID"].astype(str) + f"_{level}",
            "facility_name": "VA Charging Station " + sub["ID"].astype(str),
            "lat": sub["latitude"].astype(float),
            "lon": sub["longitude"].astype(float),
            "year": SCENARIO_YEAR,
            "type": level,
            "count": sub[col].astype(int),
            "station_id": sub["ID"],
            "fuel_type_code": sub["Fuel_Type_Code"],
        }))

    if not parts:
        return pd.DataFrame(columns=[
            "facility_id", "facility_name", "lat", "lon", "year", "type",
            "count", "station_id", "fuel_type_code",
        ])

    return pd.concat(parts, ignore_index=True)


def aggregate_to_counties(
    point_rows: pd.DataFrame,
    *,
    scenario: str,
    scenario_date: str,
) -> pd.DataFrame:
    """Aggregate expanded point rows to county-level long-format measures.

    Required input columns: geoid, station_id, type, count.

    Produces 8 measures per county:
        {level}_station_count   unique-station count by level
        {level}_charger_count   sum of charger counts by level
        total_station_count     unique stations regardless of level
        total_charger_count     sum of all chargers regardless of level

    Output schema: ENERGY_LONG_FORMAT_COLUMNS.
    """
    rows = []

    # Per-level station counts (dedupe on station_id within each county+level)
    for level in CHARGER_LEVELS:
        sub = point_rows[point_rows["type"] == level]
        per_county = sub.groupby("geoid")["station_id"].nunique()
        for geoid, value in per_county.items():
            rows.append({
                "geoid": geoid,
                "datetime": scenario_date,
                "measure": f"{level}_station_count",
                "value": int(value),
                "moe": pd.NA,
                "region_type": "county",
                "data_method": "simulated",
                "scenario": scenario,
            })

    # Per-level charger counts (sum of `count` within each county+level)
    for level in CHARGER_LEVELS:
        sub = point_rows[point_rows["type"] == level]
        per_county = sub.groupby("geoid")["count"].sum()
        for geoid, value in per_county.items():
            rows.append({
                "geoid": geoid,
                "datetime": scenario_date,
                "measure": f"{level}_charger_count",
                "value": int(value),
                "moe": pd.NA,
                "region_type": "county",
                "data_method": "simulated",
                "scenario": scenario,
            })

    # Total station counts (dedupe on station_id across all levels)
    per_county = point_rows.groupby("geoid")["station_id"].nunique()
    for geoid, value in per_county.items():
        rows.append({
            "geoid": geoid,
            "datetime": scenario_date,
            "measure": "total_station_count",
            "value": int(value),
            "moe": pd.NA,
            "region_type": "county",
            "data_method": "simulated",
            "scenario": scenario,
        })

    # Total charger counts (sum of `count` across all levels)
    per_county = point_rows.groupby("geoid")["count"].sum()
    for geoid, value in per_county.items():
        rows.append({
            "geoid": geoid,
            "datetime": scenario_date,
            "measure": "total_charger_count",
            "value": int(value),
            "moe": pd.NA,
            "region_type": "county",
            "data_method": "simulated",
            "scenario": scenario,
        })

    out = pd.DataFrame(rows)
    return out[ENERGY_LONG_FORMAT_COLUMNS]
