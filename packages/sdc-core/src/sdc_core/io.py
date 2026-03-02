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

import pandas as pd

from sdc_core.geo import standardize_all

# Standard SDC column order
STANDARD_COLUMNS = ["geoid", "year", "measure", "value", "moe", "region_type"]


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
        df = standardize_all(df)

    if standardize:
        # Keep only standard columns, in order; fill missing with NaN
        present = [col for col in STANDARD_COLUMNS if col in df.columns]
        df = df.reindex(columns=STANDARD_COLUMNS)

    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def read_measure_info(path: str | pathlib.Path) -> dict:
    """Read a measure_info.json file."""
    import json

    path = pathlib.Path(path)
    with open(path) as f:
        return json.load(f)
