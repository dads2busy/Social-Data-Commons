"""Standardized I/O for SDC datasets.

Handles reading/writing compressed CSVs in the standard SDC long format,
column reindexing, and output directory conventions.

Usage:
    from sdc_core.io import read_data, write_data

    df = read_data("data/working/raw_broadband.csv.xz")
    write_data(df, "data/distribution/broadband_2021.csv.xz")
"""

from __future__ import annotations

import pathlib
import shutil

import pandas as pd

from sdc_core.geo import infer_region_types, standardize_all
from sdc_core.naming import REGION_TYPE_ABBR, build_file_name

# Standard SDC column order
STANDARD_COLUMNS = ["geoid", "year", "measure", "value", "moe", "region_type", "data_method"]

# Standardized point-data schema for facility/lat-lon datasets.
# Pipeline-specific attribute columns may ride alongside these and
# pass through to GeoJSON `properties` in export_point_layer.
POINT_SCHEMA_REQUIRED = [
    "facility_id",
    "facility_name",
    "lat",
    "lon",
    "year",
    "type",
]

POINT_SCHEMA_OPTIONAL = [
    "description",
]


def read_data(
    path: str | pathlib.Path,
    *,
    geoid_col: str | None = None,
    dtype: dict | None = None,
) -> pd.DataFrame:
    """Read a CSV or compressed CSV, ensuring geoid is treated as string.

    Parameters
    ----------
    path : str or Path
        Path to .csv or .csv.xz file.
    geoid_col : str or None
        If the GEOID column has a non-standard name, specify it here
        and it will be renamed to "geoid".
    dtype : dict or None
        Additional dtype overrides. GEOID-like columns are always read as str.
    """
    path = pathlib.Path(path)

    # Build dtype map — always read geoid-like columns as string
    geoid_candidates = ["geoid", "GEOID", "GEOID21", "GEOID20", "GEOID10", "fips", "FIPS"]
    type_map = {col: str for col in geoid_candidates}
    if dtype:
        type_map.update(dtype)

    df = pd.read_csv(path, dtype=type_map)

    if geoid_col and geoid_col != "geoid" and geoid_col in df.columns:
        df = df.rename(columns={geoid_col: "geoid"})

    return df


def write_data(
    df: pd.DataFrame,
    path: str | pathlib.Path,
    *,
    standardize: bool = True,
    census_standardize: bool = False,
    compress: bool = True,
    measure_info=None,
    input_only_measures=None,
    vintage_cutoff_year: int = 2020,
) -> pathlib.Path:
    """Write a DataFrame in standard SDC format.

    Parameters
    ----------
    df : pd.DataFrame
        Data to write.
    path : str or Path
        Output path. If compress=True and path doesn't end in .xz, it's added.
    standardize : bool
        If True, reindex to STANDARD_COLUMNS (dropping extra cols, adding
        missing ones as NaN).
    census_standardize : bool
        If True, apply 2010→2020 census geography standardization and output
        both _geo10/_geo20 variants when applicable.
    compress : bool
        If True, write as .csv.xz.
    measure_info : optional measure_info.json dict or path; passed to
        standardize_all for type-aware census standardization.
    input_only_measures : forwarded to standardize_all; helper measures excluded from output.

    Returns
    -------
    pathlib.Path
        The actual path written to.
    """
    path = pathlib.Path(path)

    if compress and path.suffix != ".xz":
        if path.suffix == ".csv":
            path = path.with_suffix(".csv.xz")
        else:
            path = pathlib.Path(str(path) + ".csv.xz")

    if census_standardize:
        df = standardize_all(df, measure_info=measure_info, input_only_measures=input_only_measures, vintage_cutoff_year=vintage_cutoff_year)

    if standardize:
        # Keep only standard columns, in order; fill missing with NaN
        present = [col for col in STANDARD_COLUMNS if col in df.columns]
        df = df.reindex(columns=STANDARD_COLUMNS)

    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def data_reformat_for_site(
    source_path: str | pathlib.Path,
    output_dir: str | pathlib.Path,
    levels: list[str] | None = None,
    *,
    geoid_col: str = "geoid",
    year_col: str = "year",
    measure_col: str = "measure",
    value_col: str = "value",
    coverage_area: str | None = None,
    data_source: str | None = None,
    title: str | None = None,
    measure_info_path: str | pathlib.Path | None = None,
) -> list[pathlib.Path]:
    """Reformat a tall SDC distribution file into wide per-level files for dashboards.

    Reads a tall-format .csv.xz, infers region type from geoid pattern/length,
    pivots to wide format (one column per measure), splits by level, and writes
    one .csv.xz per level to output_dir.

    Parameters
    ----------
    source_path : path to the tall .csv.xz input file
    output_dir : directory to write output files into (created if absent)
    levels : region types to include, e.g. ["health_district", "county", "tract"].
             If None, all inferred levels (excluding "other") are written.
    geoid_col, year_col, measure_col, value_col : column name overrides
    coverage_area : coverage area for output filename (e.g. "va", "ncr")
    data_source : data source abbreviation (e.g. "sdad", "census_acs")
    title : title segment for output filename (e.g. "gender_demographics")
    measure_info_path : optional path to a measure_info.json to copy into output_dir

    Returns
    -------
    list[pathlib.Path]
        Paths of files written, one per level.
    """
    output_dir = pathlib.Path(output_dir)

    df = read_data(source_path)
    df["_region_type"] = infer_region_types(df[geoid_col])

    if levels is not None:
        df = df[df["_region_type"].isin(levels)]
    else:
        df = df[df["_region_type"] != "other"]

    written: list[pathlib.Path] = []

    for level, level_df in df.groupby("_region_type"):
        level = str(level)
        wide = (
            level_df
            .pivot_table(
                index=[geoid_col, year_col],
                columns=measure_col,
                values=value_col,
                aggfunc="first",
            )
            .reset_index()
        )
        wide.columns.name = None

        # Rename to dashboard convention
        wide = wide.rename(columns={geoid_col: "ID", year_col: "time"})

        # Stable column order: ID, time, then measures alphabetically
        measure_cols = sorted(c for c in wide.columns if c not in ("ID", "time"))
        wide = wide[["ID", "time"] + measure_cols]

        abbr = REGION_TYPE_ABBR.get(level, level)
        filename = (
            build_file_name(
                coverage_area=coverage_area,
                resolution=abbr,
                data_source=data_source,
                years=wide["time"].unique().tolist(),
                title=title,
            )
            + ".csv.xz"
        )

        out_path = write_data(wide, output_dir / filename, standardize=False)
        written.append(out_path)

    if measure_info_path is not None:
        src = pathlib.Path(measure_info_path)
        dest = output_dir / "measure_info.json"
        shutil.copy2(src, dest)

    return written


def read_measure_info(path: str | pathlib.Path) -> dict:
    """Read a measure_info.json file."""
    import json

    path = pathlib.Path(path)
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Point-schema I/O helpers (write_point_data, read_point_data).
# export_point_layer (Task 3) will live here alongside these functions.
# ---------------------------------------------------------------------------


def write_point_data(
    df: pd.DataFrame,
    path: str | pathlib.Path,
    *,
    compress: bool = True,
) -> pathlib.Path:
    """Validate and write a point-schema DataFrame to .csv.xz.

    Required columns: facility_id, facility_name, lat, lon, year, type.
    Any extra columns pass through (e.g. operator, sq_ft, description).

    Rows with null lat or lon are dropped. Rows with out-of-range
    coordinates raise ValueError.
    """
    missing = [c for c in POINT_SCHEMA_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"missing required point column(s): {missing}")

    df = df.copy()
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["facility_id", "lat", "lon"])

    bad_lat = df[(df["lat"] < -90) | (df["lat"] > 90)]
    if not bad_lat.empty:
        raise ValueError(
            f"lat out of range in {len(bad_lat)} rows "
            f"(min={bad_lat['lat'].min()}, max={bad_lat['lat'].max()})"
        )
    bad_lon = df[(df["lon"] < -180) | (df["lon"] > 180)]
    if not bad_lon.empty:
        raise ValueError(
            f"lon out of range in {len(bad_lon)} rows "
            f"(min={bad_lon['lon'].min()}, max={bad_lon['lon'].max()})"
        )

    df["facility_id"] = df["facility_id"].astype(str)

    path = pathlib.Path(path)
    if compress and path.suffix != ".xz":
        if path.suffix == ".csv":
            path = path.with_suffix(".csv.xz")
        else:
            path = pathlib.Path(str(path) + ".csv.xz")

    # Stable column order: required first, then any extras alphabetically.
    extras = sorted(c for c in df.columns if c not in POINT_SCHEMA_REQUIRED)
    df = df[POINT_SCHEMA_REQUIRED + extras]

    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def read_point_data(path: str | pathlib.Path) -> pd.DataFrame:
    """Read a point-schema .csv.xz, preserving string IDs and numeric coords."""
    path = pathlib.Path(path)
    df = pd.read_csv(path, dtype={"facility_id": object})
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    return df


def export_point_layer(
    source_path: str | pathlib.Path,
    output_dir: str | pathlib.Path,
    *,
    coverage_area: str | None = None,
    data_source: str | None = None,
    title: str | None = None,
) -> pathlib.Path:
    """Read a point-schema CSV and write a GeoJSON FeatureCollection.

    Output filename is built via build_file_name() using resolution="pt"
    and the time period inferred from the year column. Each row becomes
    a Point feature; lat/lon move into geometry, everything else
    (including year and type) goes into properties. Null property
    values are omitted rather than serialized as `null`.

    Parameters
    ----------
    source_path : path to a .csv.xz written by write_point_data
    output_dir  : directory to write the .geojson into (created if absent)
    coverage_area, data_source, title : filename parts forwarded to build_file_name
    """
    import json

    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = read_point_data(source_path)

    features = []
    for row in df.to_dict(orient="records"):
        lat = row.pop("lat")
        lon = row.pop("lon")
        properties = {k: v for k, v in row.items() if pd.notna(v)}
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": properties,
        })

    payload = {"type": "FeatureCollection", "features": features}

    filename = build_file_name(
        coverage_area=coverage_area,
        resolution="pt",
        data_source=data_source,
        years=df["year"].unique().tolist(),
        title=title,
    ) + ".geojson"

    out_path = output_dir / filename
    out_path.write_text(json.dumps(payload))
    return out_path
