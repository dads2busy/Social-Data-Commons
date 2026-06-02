"""Pure transformation functions for the PowerInfrastructure pipeline.

Source: HIFLD Electric Substations + Power Plants ArcGIS REST services,
filtered to Virginia. Pure functions only — all HTTP I/O and file writes live
in ingest.py.
"""

from __future__ import annotations

import math

import geopandas as gpd
import pandas as pd

# 5-digit county FIPS pattern; geoids that don't match are missing/invalid.
FIPS_RE = r"\d{5}"

# Planar CRS (NAD83 / CONUS Albers) used for nearest-county distance math so
# the backfill measures real ground distance rather than degrees.
BACKFILL_PLANAR_CRS = "EPSG:5070"


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


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    """Return df[name] if present, else an all-NA Series aligned to df index."""
    if name in df.columns:
        return df[name]
    return pd.Series([pd.NA] * len(df), index=df.index)


def clean_numeric(value, *, sentinel: float = -999999) -> float:
    """Coerce a HIFLD numeric field to float.

    Maps HIFLD's null marker (values <= the sentinel, default -999999) and any
    non-numeric / missing value to NaN.
    """
    try:
        num = float(value)
    except (TypeError, ValueError):
        return math.nan
    if math.isnan(num) or num <= sentinel:
        return math.nan
    return num


def shape_records(
    df: pd.DataFrame,
    *,
    kind: str,
    id_field: str,
    id_prefix: str,
    snapshot_year: int,
    sentinel: float = -999999,
) -> pd.DataFrame:
    """Map raw HIFLD attribute rows to the point schema + extras.

    kind: "power_plant" or "substation". id_field/id_prefix build facility_id as
    "{id_prefix}_{id_value}". Required input columns: id_field, NAME, COUNTYFIPS,
    LATITUDE, LONGITUDE. Optional HIFLD columns (may be absent for one layer):
    STATUS, OPERATOR, PRIM_FUEL, OPER_CAP, MAX_VOLT, LINES.
    """
    src_id = _col(df, id_field).astype(str)
    facility_id = f"{id_prefix}_" + src_id

    name = _col(df, "NAME")
    fallback = pd.Series([f"{kind} ({i})" for i in src_id], index=df.index)
    facility_name = name.where(
        name.notna() & ~name.astype(str).isin(["", "nan", "None"]), fallback
    )

    capacity = _col(df, "OPER_CAP").map(lambda v: clean_numeric(v, sentinel=sentinel))
    voltage = _col(df, "MAX_VOLT").map(lambda v: clean_numeric(v, sentinel=sentinel))

    out = pd.DataFrame({
        "facility_id": facility_id.values,
        "facility_name": facility_name.values,
        "lat": pd.to_numeric(_col(df, "LATITUDE"), errors="coerce").values,
        "lon": pd.to_numeric(_col(df, "LONGITUDE"), errors="coerce").values,
        "year": int(snapshot_year),
        "type": kind,
        "status": _col(df, "STATUS").values,
        "operator": _col(df, "OPERATOR").values,
        "plant_source": _col(df, "PRIM_FUEL").values,
        "plant_capacity_mw": capacity.values,
        "max_voltage": voltage.values,
        "lines": pd.to_numeric(_col(df, "LINES"), errors="coerce").values,
        "geoid": _col(df, "COUNTYFIPS").astype(str).values,
        "source_id": src_id.values,
    })
    return out


def backfill_geoid_by_location(
    point_rows: pd.DataFrame,
    counties: gpd.GeoDataFrame,
    *,
    planar_crs: str = BACKFILL_PLANAR_CRS,
) -> pd.DataFrame:
    """Fill missing/invalid county FIPS from each point's lat/lon.

    HIFLD assigns county via its COUNTYFIPS field, but a few VA facilities ship
    with no usable FIPS (e.g. the offshore Coastal Virginia Offshore Wind farm,
    whose COUNTYFIPS is "NOT AVAILABLE"). Without a county they'd be dropped
    from the county aggregation while still showing on the point map — an
    off-by-one between the two outputs.

    For every row whose ``geoid`` is not a 5-digit FIPS and that has finite
    lat/lon, this assigns the *nearest* county polygon (distance 0 when the
    point is inside one, the adjacent county for offshore points). Rows with a
    valid geoid are returned unchanged; rows that still can't be located (no
    coordinates) keep their original geoid and are dropped downstream.

    Pure transform: ``counties`` is an already-loaded GeoDataFrame with a
    ``geoid`` column (file I/O stays in ingest.py).
    """
    geoid = point_rows["geoid"].astype(str)
    missing = ~geoid.str.fullmatch(FIPS_RE) & point_rows["lat"].notna() & point_rows["lon"].notna()
    if not missing.any():
        return point_rows

    counties = counties[["geoid", "geometry"]].rename(columns={"geoid": "_assigned_geoid"})
    counties = counties.to_crs(planar_crs)

    subset = point_rows.loc[missing]
    pts = gpd.GeoDataFrame(
        subset,
        geometry=gpd.points_from_xy(subset["lon"], subset["lat"]),
        crs="EPSG:4326",
    ).to_crs(planar_crs)

    joined = gpd.sjoin_nearest(pts, counties, how="left")
    # A point equidistant from two counties yields duplicate index rows; keep one.
    joined = joined[~joined.index.duplicated(keep="first")].reindex(subset.index)

    out = point_rows.copy()
    out.loc[missing, "geoid"] = joined["_assigned_geoid"].astype(str).values
    return out


def aggregate_to_counties(
    point_rows: pd.DataFrame,
    *,
    scenario: str,
    scenario_date: str,
) -> pd.DataFrame:
    """Aggregate shaped point rows to county-level long-format measures.

    Required input columns: geoid, type, plant_capacity_mw. Rows whose geoid is
    not a 5-digit FIPS string are dropped before aggregation.

    Produces 4 measures per county:
        power_plant_count        count of type == "power_plant"
        substation_count         count of type == "substation"
        power_facility_count     total feature count
        total_plant_capacity_mw  sum of plant_capacity_mw (NaN -> 0)
    """
    valid = point_rows[point_rows["geoid"].astype(str).str.fullmatch(r"\d{5}")]
    if len(valid) == 0:
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
    total_counts = valid.groupby("geoid").size()
    for geoid, value in total_counts.items():
        emit(geoid, "power_facility_count", int(value))

    # Per-type counts — zero-filled so every county has both measures.
    type_to_measure = {"power_plant": "power_plant_count", "substation": "substation_count"}
    type_counts = valid.groupby(["geoid", "type"]).size()
    for geoid in total_counts.index:
        for type_val, measure in type_to_measure.items():
            emit(geoid, measure, int(type_counts.get((geoid, type_val), 0)))

    # Capacity sum (NaN -> 0)
    capacity = pd.to_numeric(valid["plant_capacity_mw"], errors="coerce").fillna(0)
    cap_sums = capacity.groupby(valid["geoid"]).sum()
    for geoid, value in cap_sums.items():
        emit(geoid, "total_plant_capacity_mw", float(value))

    out = pd.DataFrame(rows)
    return out[ENERGY_LONG_FORMAT_COLUMNS]
