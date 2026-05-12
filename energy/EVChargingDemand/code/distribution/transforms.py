"""Pure transformation functions for the EVChargingDemand pipeline.

Source: simulated 2026 VA charging events (rows at location × hour-of-day
granularity). Pure functions only; all file I/O and spatial joins live in
ingest.py.
"""

from __future__ import annotations

import re

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

# Matches the public-station id pattern: "va_<digits>_existing"
_VA_EXISTING_RE = re.compile(r"^va_\d+_existing$")
# Matches purely numeric ids (residential/synthetic origin)
_NUMERIC_RE = re.compile(r"^\d+$")


def infer_location_type(station_id: str) -> str:
    """Classify a charging_station_id by format."""
    s = str(station_id)
    if _VA_EXISTING_RE.match(s):
        return "public_station"
    if _NUMERIC_RE.match(s):
        return "residential_or_other"
    return "unknown"


def aggregate_to_locations(
    events: pd.DataFrame,
    *,
    snapshot_year: int,
) -> pd.DataFrame:
    """Per-location summary: one row per unique charging_station_id.

    Required source columns: charging_station_id, latitude, longitude, hour, total_kWh_added.

    Output columns:
        facility_id, facility_name, lat, lon, year, type,
        total_kwh, n_hours_active, id_format
    """
    df = events.copy()
    df["__active"] = (df["total_kWh_added"] > 0).astype(int)

    # First-observation lat/lon per station (all rows for a station share coords; first is fine)
    coords = df.groupby("charging_station_id")[["latitude", "longitude"]].first()

    # Sum kWh per station
    sums = df.groupby("charging_station_id")["total_kWh_added"].sum()

    # Count hours with non-zero kWh per station
    n_active = df.groupby("charging_station_id")["__active"].sum()

    ids = coords.index.tolist()
    types = [infer_location_type(i) for i in ids]

    out = pd.DataFrame({
        "facility_id": ids,
        "facility_name": [f"Charging Location {i} ({t})" for i, t in zip(ids, types)],
        "lat": coords["latitude"].astype(float).values,
        "lon": coords["longitude"].astype(float).values,
        "year": snapshot_year,
        "type": types,
        "total_kwh": sums.reindex(ids).astype(float).values,
        "n_hours_active": n_active.reindex(ids).astype(int).values,
        "id_format": types,
    })
    return out


def aggregate_to_county_hour(
    events_with_geoid: pd.DataFrame,
    *,
    scenario: str,
    scenario_year: int,
) -> pd.DataFrame:
    """Aggregate events to (county, hour-of-day) long-format measures.

    Required input columns: charging_station_id, geoid, hour, total_kWh_added.

    Produces 2 measures per (geoid, hour) bucket:
        ev_charging_demand_kwh         sum of total_kWh_added
        n_active_charging_locations    count of distinct charging_station_id with kWh > 0

    `datetime` is formatted as "{scenario_year}-01-01THH:00:00" with zero-padded hour.
    """
    if len(events_with_geoid) == 0:
        return pd.DataFrame(columns=ENERGY_LONG_FORMAT_COLUMNS)

    df = events_with_geoid.copy()
    df["__active"] = df["total_kWh_added"] > 0

    rows = []

    # ev_charging_demand_kwh per (geoid, hour)
    kwh_sums = df.groupby(["geoid", "hour"])["total_kWh_added"].sum()
    for (geoid, hour), value in kwh_sums.items():
        rows.append({
            "geoid": str(geoid),
            "datetime": f"{scenario_year}-01-01T{int(hour):02d}:00:00",
            "measure": "ev_charging_demand_kwh",
            "value": float(value),
            "moe": pd.NA,
            "region_type": "county",
            "data_method": "simulated",
            "scenario": scenario,
        })

    # n_active_charging_locations per (geoid, hour) — distinct station ids where kWh > 0
    active = df[df["__active"]]
    if len(active):
        n_active = active.groupby(["geoid", "hour"])["charging_station_id"].nunique()
        for (geoid, hour), value in n_active.items():
            rows.append({
                "geoid": str(geoid),
                "datetime": f"{scenario_year}-01-01T{int(hour):02d}:00:00",
                "measure": "n_active_charging_locations",
                "value": int(value),
                "moe": pd.NA,
                "region_type": "county",
                "data_method": "simulated",
                "scenario": scenario,
            })

    out = pd.DataFrame(rows)
    return out[ENERGY_LONG_FORMAT_COLUMNS]
