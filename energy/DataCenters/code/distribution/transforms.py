"""Pure transformation functions for the DataCenters pipeline.

Source: IM3 Open Source Data Center Atlas (OSM-derived). Pure functions only;
all file I/O lives in ingest.py.
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

GEOMETRY_TYPES = ("point", "building", "campus")


def _facility_name(name, operator):
    """Choose a non-empty facility name from source `name` / `operator` columns."""
    if pd.notna(name) and str(name).strip():
        return str(name)
    if pd.notna(operator) and str(operator).strip():
        return f"Data Center (operator: {operator})"
    return "Data Center (unnamed)"


def filter_and_shape(
    raw: pd.DataFrame,
    *,
    state_filter: str,
    snapshot_year: int,
) -> pd.DataFrame:
    """Filter source rows to one state and reshape to the point schema.

    Required source columns:
      id, state_abb, state_id, county_id, operator, name, sqft, lat, lon, type

    The output `county_id` is the 5-digit FIPS, built by concatenating the
    source's 2-digit `state_id` and 3-digit `county_id`. Both must be
    zero-padded strings (use dtype=str when reading the source CSV).
    """
    sub = raw[raw["state_abb"] == state_filter].copy()

    return pd.DataFrame({
        "facility_id": "im3_" + sub["id"].astype(str) + "_" + sub["type"].astype(str),
        "facility_name": [
            _facility_name(n, o) for n, o in zip(sub["name"], sub["operator"])
        ],
        "lat": sub["lat"].astype(float),
        "lon": sub["lon"].astype(float),
        "year": snapshot_year,
        "type": sub["type"].astype(str),
        "operator": sub["operator"],
        "sqft": pd.to_numeric(sub["sqft"], errors="coerce"),
        "state_abb": sub["state_abb"].astype(str),
        "county_id": (sub["state_id"].astype(str) + sub["county_id"].astype(str)).astype(object),
        "source_id": sub["id"],
    })


def aggregate_to_counties(
    point_rows: pd.DataFrame,
    *,
    scenario: str,
    scenario_date: str,
) -> pd.DataFrame:
    """Aggregate shaped point rows to county-level long-format measures.

    Required input columns: county_id, source_id, type, sqft.

    Produces 5 measures per county:
        total_data_center_count             count of rows
        {geom}_data_center_count            count per geometry type (point, building, campus)
        total_data_center_sqft              sum of sqft, NaN treated as 0
    """
    rows = []

    # Per-geometry-type counts (emit zero rows so dashboards see all 3 types per county)
    for geom in GEOMETRY_TYPES:
        per_county_all = point_rows.groupby("county_id").size()
        per_county_this = (
            point_rows[point_rows["type"] == geom]
            .groupby("county_id")
            .size()
            .reindex(per_county_all.index, fill_value=0)
        )
        for county_id, value in per_county_this.items():
            rows.append({
                "geoid": str(county_id),
                "datetime": scenario_date,
                "measure": f"{geom}_data_center_count",
                "value": int(value),
                "moe": pd.NA,
                "region_type": "county",
                "data_method": "observed",
                "scenario": scenario,
            })

    # Total count per county (all geometry types)
    per_county = point_rows.groupby("county_id").size()
    for county_id, value in per_county.items():
        rows.append({
            "geoid": str(county_id),
            "datetime": scenario_date,
            "measure": "total_data_center_count",
            "value": int(value),
            "moe": pd.NA,
            "region_type": "county",
            "data_method": "observed",
            "scenario": scenario,
        })

    # Total sqft per county (sum, NaN -> 0)
    sqft_sums = (
        point_rows.assign(_sqft=pd.to_numeric(point_rows.get("sqft"), errors="coerce").fillna(0))
        .groupby("county_id")["_sqft"]
        .sum()
    )
    for county_id, value in sqft_sums.items():
        rows.append({
            "geoid": str(county_id),
            "datetime": scenario_date,
            "measure": "total_data_center_sqft",
            "value": float(value),
            "moe": pd.NA,
            "region_type": "county",
            "data_method": "observed",
            "scenario": scenario,
        })

    if not rows:
        return pd.DataFrame(columns=ENERGY_LONG_FORMAT_COLUMNS)

    out = pd.DataFrame(rows)
    return out[ENERGY_LONG_FORMAT_COLUMNS]
