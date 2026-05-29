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
