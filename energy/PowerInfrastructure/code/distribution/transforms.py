"""Pure transformation functions for the PowerInfrastructure pipeline.

Source: OpenStreetMap power=plant / power=substation features (Overpass via
osmnx). Pure functions only — all file I/O, geocoding, reproject/centroid/sjoin
live in ingest.py.
"""

from __future__ import annotations

import math
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

# OSM `power` tag value -> point-schema `type` value
POWER_TYPE_MAP = {
    "plant": "power_plant",
    "substation": "substation",
}

# Multipliers to convert a unit to megawatts
_UNIT_TO_MW = {
    "w": 1e-6,
    "kw": 1e-3,
    "mw": 1.0,
    "gw": 1e3,
}


def parse_capacity(value) -> float:
    """Parse an OSM `plant:output:electricity` string into megawatts.

    Handles "100 MW", "2.5 MW", "750000 W", "750 kW", "1.5 GW", "100MW",
    and bare numbers (assumed MW). Returns NaN for empty/None/non-numeric
    values such as "yes".
    """
    if value is None:
        return math.nan
    text = str(value).strip()
    if not text:
        return math.nan
    match = re.match(r"^\s*([0-9]*\.?[0-9]+)\s*([a-zA-Z]*)", text)
    if not match:
        return math.nan
    number = float(match.group(1))
    unit = match.group(2).lower()
    if unit == "":
        return number  # bare number assumed MW
    if unit not in _UNIT_TO_MW:
        return math.nan
    return number * _UNIT_TO_MW[unit]


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    """Return df[name] if present, else an all-NA Series aligned to df index."""
    if name in df.columns:
        return df[name]
    return pd.Series([pd.NA] * len(df), index=df.index)


def shape_to_point_schema(rows: pd.DataFrame, *, snapshot_year: int) -> pd.DataFrame:
    """Reshape post-sjoin OSM rows into the point schema + extras.

    Required input columns: element_type, osmid, power, lat, lon, geoid.
    Optional OSM tag columns (may be absent): name, operator, plant:source,
    plant:output:electricity, voltage.
    """
    element_type = _col(rows, "element_type").astype(str)
    osmid = _col(rows, "osmid").astype(str)
    power = _col(rows, "power").astype(str)
    name = _col(rows, "name")

    facility_id = "osm_" + element_type + "_" + osmid
    type_col = power.map(POWER_TYPE_MAP).fillna(power)

    # Name with fallback "{type} (OSM {osmid})" for unnamed features.
    fallback = type_col.astype(str) + " (OSM " + osmid + ")"
    facility_name = name.where(name.notna() & (name.astype(str) != ""), fallback)

    capacity = _col(rows, "plant:output:electricity").map(parse_capacity)

    out = pd.DataFrame({
        "facility_id": facility_id.values,
        "facility_name": facility_name.values,
        "lat": pd.to_numeric(rows["lat"], errors="coerce").values,
        "lon": pd.to_numeric(rows["lon"], errors="coerce").values,
        "year": int(snapshot_year),
        "type": type_col.values,
        "operator": _col(rows, "operator").values,
        "plant_source": _col(rows, "plant:source").values,
        "plant_capacity_mw": capacity.values,
        "voltage": _col(rows, "voltage").values,
        "osm_id": osmid.values,
        "geoid": _col(rows, "geoid").astype(str).values,
    })
    return out


def aggregate_to_counties(
    point_rows: pd.DataFrame,
    *,
    scenario: str,
    scenario_date: str,
) -> pd.DataFrame:
    """Aggregate shaped point rows to county-level long-format measures.

    Required input columns: geoid, type, plant_capacity_mw.

    Produces 4 measures per county:
        power_plant_count        count of type == "power_plant"
        substation_count         count of type == "substation"
        power_facility_count     total feature count
        total_plant_capacity_mw  sum of plant_capacity_mw (NaN -> 0)
    """
    if len(point_rows) == 0:
        return pd.DataFrame(columns=ENERGY_LONG_FORMAT_COLUMNS)

    rows = []

    def emit(geoid, measure, value):
        rows.append({
            "geoid": str(geoid),
            "datetime": scenario_date,
            "measure": measure,
            "value": value,
            "moe": pd.NA,
            "region_type": "county",
            "data_method": "observed",
            "scenario": scenario,
        })

    # Total feature count
    total_counts = point_rows.groupby("geoid").size()
    for geoid, value in total_counts.items():
        emit(geoid, "power_facility_count", int(value))

    # Per-type counts
    type_to_measure = {"power_plant": "power_plant_count", "substation": "substation_count"}
    type_counts = point_rows.groupby(["geoid", "type"]).size()
    for (geoid, type_val), value in type_counts.items():
        measure = type_to_measure.get(type_val)
        if measure:
            emit(geoid, measure, int(value))

    # Capacity sum (NaN -> 0)
    capacity = pd.to_numeric(point_rows["plant_capacity_mw"], errors="coerce").fillna(0)
    cap_sums = capacity.groupby(point_rows["geoid"]).sum()
    for geoid, value in cap_sums.items():
        emit(geoid, "total_plant_capacity_mw", float(value))

    out = pd.DataFrame(rows)
    return out[ENERGY_LONG_FORMAT_COLUMNS]
