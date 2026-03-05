"""Geographic utilities for GEOID manipulation and multi-level aggregation.

The core pattern across SDC pipelines: start with block-group-level data
and roll up to tract and county levels using GEOID string slicing.

Usage:
    from sdc_core.geo import aggregate_to_geographies

    df = aggregate_to_geographies(
        block_group_df,
        measure="perc_hh_with_broadband",
        method="mean",
    )
"""

from __future__ import annotations

import re
import warnings
from typing import Literal

import pandas as pd

# GEOID lengths by geography level
GEOID_LENGTHS: dict[str, int] = {
    "county": 5,
    "tract": 11,
    "block_group": 12,
}

# Reverse lookup (standard census geographies only; health_district uses pattern matching)
LENGTH_TO_GEO: dict[int, str] = {v: k for k, v in GEOID_LENGTHS.items()}

# Health district geoids contain _hd_ (e.g. 51_hd_35); check this before length
_HD_PATTERN = re.compile(r"_hd_")
# Civic association geoids contain _ca_ (e.g. 51013_ca_01)
_CA_PATTERN = re.compile(r"_ca_")

AggMethod = Literal["mean", "sum", "median", "min", "max"]


def geoid_to_county(geoid: pd.Series) -> pd.Series:
    """Extract county FIPS (first 5 chars) from a GEOID series."""
    return geoid.str[:5]


def geoid_to_tract(geoid: pd.Series) -> pd.Series:
    """Extract tract FIPS (first 11 chars) from a GEOID series."""
    return geoid.str[:11]


def geoid_level(geoid: pd.Series) -> str:
    """Infer the geography level from GEOID string length."""
    length = geoid.str.len().mode().iloc[0]
    if length not in LENGTH_TO_GEO:
        raise ValueError(f"Cannot infer geography from GEOID length {length}")
    return LENGTH_TO_GEO[length]


def infer_region_type(geoid: str) -> str:
    """Infer region type from geoid pattern/length.

    The region_type column is deprecated in SDC pipeline outputs; region type
    must be inferred from the geoid itself. Pattern check runs before length
    check so health districts (which embed _hd_) are correctly identified.

    Returns one of: "health_district", "county", "tract", "block_group", "other".
    """
    if _HD_PATTERN.search(geoid):
        return "health_district"
    if _CA_PATTERN.search(geoid):
        return "civic_association"
    n = len(geoid)
    if n == 5:
        return "county"
    if n == 11:
        return "tract"
    if n == 12:
        return "block_group"
    return "other"


def infer_region_types(geoid_series: pd.Series) -> pd.Series:
    """Vectorized region type inference from a geoid Series."""
    return geoid_series.apply(infer_region_type)


def aggregate_up(
    df: pd.DataFrame,
    target_geo: str,
    method: AggMethod = "mean",
    value_col: str = "value",
) -> pd.DataFrame:
    """Aggregate a DataFrame to a higher geography level.

    Parameters
    ----------
    df : pd.DataFrame
        Must have columns: geoid, year, value (at minimum).
    target_geo : str
        Target geography: "tract" or "county".
    method : str
        Aggregation method for the value column.
    value_col : str
        Column to aggregate.

    Returns
    -------
    pd.DataFrame
        Aggregated DataFrame with geoid, year, measure, value, region_type.
    """
    target_length = GEOID_LENGTHS[target_geo]
    result = df.copy()
    result["_target_geoid"] = result["geoid"].str[:target_length]

    group_cols = ["_target_geoid", "year"]
    if "measure" in result.columns:
        group_cols.append("measure")

    agg = result.groupby(group_cols)[value_col].agg(method).reset_index()
    agg = agg.rename(columns={"_target_geoid": "geoid"})
    agg["region_type"] = target_geo
    return agg


def aggregate_to_geographies(
    df: pd.DataFrame,
    measure: str,
    method: AggMethod = "mean",
    levels: list[str] | None = None,
    value_col: str = "value",
) -> pd.DataFrame:
    """Aggregate block-group data to multiple geography levels and combine.

    This is the standard SDC pattern: take block-group-level data and produce
    a single DataFrame with county, tract, and block group rows.

    Parameters
    ----------
    df : pd.DataFrame
        Block-group-level data with columns: geoid, year, value.
    measure : str
        Measure name to set in the output.
    method : str
        Aggregation method ("mean" for percentages, "sum" for counts).
    levels : list[str] or None
        Geography levels to include. Default: ["county", "tract", "block_group"].
    value_col : str
        Column to aggregate.

    Returns
    -------
    pd.DataFrame
        Combined DataFrame with all geography levels, sorted by geoid.
    """
    if levels is None:
        levels = ["county", "tract", "block_group"]

    source_level = geoid_level(df["geoid"])
    parts = []

    for level in levels:
        if level == source_level:
            part = df.copy()
            part["region_type"] = level
        else:
            part = aggregate_up(df, level, method=method, value_col=value_col)

        part["measure"] = measure
        parts.append(part)

    combined = pd.concat(parts, ignore_index=True)
    return combined.sort_values(["region_type", "geoid", "year"]).reset_index(drop=True)


def aggregate_with_crosswalk(
    df: pd.DataFrame,
    crosswalk: pd.DataFrame,
    source_col: str,
    target_col: str,
    method: AggMethod = "mean",
    value_col: str = "value",
    target_region_type: str | None = None,
) -> pd.DataFrame:
    """Aggregate data to a custom geography using a crosswalk table.

    Used for geographies that can't be derived from GEOID string slicing,
    such as health districts, supervisor districts, or planning districts.

    Parameters
    ----------
    df : pd.DataFrame
        Source data with geoid, year, measure, value columns.
    crosswalk : pd.DataFrame
        Mapping table with at least source_col and target_col columns.
    source_col : str
        Column in crosswalk matching df's geoid (e.g., "ct_geoid").
    target_col : str
        Column in crosswalk for target geography (e.g., "hd_geoid").
    method : str
        Aggregation method.
    value_col : str
        Column to aggregate.
    target_region_type : str or None
        Region type label for the output. If None, uses target_col.

    Returns
    -------
    pd.DataFrame
        Aggregated data at the target geography level.
    """
    merged = df.merge(
        crosswalk[[source_col, target_col]].drop_duplicates(),
        left_on="geoid",
        right_on=source_col,
        how="inner",
    )

    group_cols = [target_col, "year"]
    if "measure" in merged.columns:
        group_cols.append("measure")

    agg = merged.groupby(group_cols)[value_col].agg(method).reset_index()
    agg = agg.rename(columns={target_col: "geoid"})
    agg["region_type"] = target_region_type or target_col

    # Drop the source join column if it's still there
    if source_col in agg.columns and source_col != "geoid":
        agg = agg.drop(columns=[source_col])

    return agg


def get_2010_2020_bound_changes(
    res: str = "tract",
    geoids: list[str] | None = None,
    *,
    state_fips: str = "51",
) -> pd.DataFrame:
    """Load 2010→2020 relationship data and classify boundary changes.

    Parameters
    ----------
    res : str
        Resolution: "tract" or "block group".
    geoids : list[str] or None
        Optional list of 2010 GEOIDs to filter.
    state_fips : str
        State FIPS for block group relationship file (default VA=51).

    Returns
    -------
    pd.DataFrame
        Crosswalk with columns: geoid20, geoid10, area20, area10, area_part,
        type_change.
    """
    if res == "tract":
        file_path = (
            "https://www2.census.gov/geo/docs/maps-data/data/rel2020/"
            "tract/tab20_tract20_tract10_natl.txt"
        )
        res_code = "TRACT"
    elif res == "block group":
        file_path = (
            "https://www2.census.gov/geo/docs/maps-data/data/rel2020/blkgrp/"
            f"tab20_blkgrp20_blkgrp10_st{state_fips}.txt"
        )
        res_code = "BLKGRP"
    else:
        raise ValueError('Invalid resolution. Use "tract" or "block group".')

    crosswalk = pd.read_csv(
        file_path,
        sep="|",
        dtype={
            f"GEOID_{res_code}_10": str,
            f"GEOID_{res_code}_20": str,
        },
    )

    keep_cols = [
        f"GEOID_{res_code}_20",
        f"GEOID_{res_code}_10",
        f"AREALAND_{res_code}_20",
        f"AREALAND_{res_code}_10",
        "AREALAND_PART",
    ]
    crosswalk = crosswalk[keep_cols]
    crosswalk = crosswalk[crosswalk["AREALAND_PART"] != 0]

    crosswalk.columns = ["geoid20", "geoid10", "area20", "area10", "area_part"]

    if geoids is not None:
        crosswalk = crosswalk[crosswalk["geoid10"].isin(geoids)]

    crosswalk["count_20"] = crosswalk.groupby("geoid20")["geoid20"].transform("size")
    crosswalk["count_10"] = crosswalk.groupby("geoid10")["geoid10"].transform("size")

    geoid_10_20 = (
        crosswalk[["geoid10", "area20"]]
        .groupby("geoid10", as_index=False)
        .sum()
        .rename(columns={"area20": "match_area"})
    )
    crosswalk = crosswalk.merge(geoid_10_20, on="geoid10", how="left")

    crosswalk["type_change"] = "moved"
    same_mask = (crosswalk["count_10"] == 1) & (crosswalk["count_20"] == 1)
    split_mask = crosswalk["area10"] == crosswalk["match_area"]
    crosswalk.loc[same_mask, "type_change"] = "same"
    crosswalk.loc[split_mask, "type_change"] = "split"

    crosswalk = crosswalk.drop(columns=["count_10", "count_20", "match_area"])
    return crosswalk


def create_crosswalk(geoids: list[str], *, state_fips: str = "51") -> pd.DataFrame:
    """Create a combined crosswalk for all resolutions found in geoids."""
    resolutions = sorted({len(g) for g in geoids})
    crosswalks: list[pd.DataFrame] = []

    for res in resolutions:
        if res == 11:
            crosswalks.append(
                get_2010_2020_bound_changes(res="tract", geoids=geoids, state_fips=state_fips)
            )
        elif res == 12:
            crosswalks.append(
                get_2010_2020_bound_changes(res="block group", geoids=geoids, state_fips=state_fips)
            )
        else:
            print(f"crosswalk not available for resolution: {res}")

    if not crosswalks:
        return pd.DataFrame(
            columns=["geoid20", "geoid10", "area20", "area10", "area_part", "type_change"]
        )

    return pd.concat(crosswalks, ignore_index=True)


def convert_2010_to_2020_bounds(
    data: pd.DataFrame,
    *,
    geoid_col: str = "geoid",
    val_col: str = "value",
    state_fips: str = "51",
) -> pd.DataFrame:
    """Redistribute 2010 values based on 2020 census boundaries."""
    if data[geoid_col].isna().any():
        raise ValueError("geoids contain missing values")

    data = data.copy()
    data[geoid_col] = data[geoid_col].astype(str)
    geoids = data[geoid_col].unique()

    if len(data[geoid_col]) > len(geoids):
        raise ValueError(
            "geoids are not unique -- data cannot contain more than one entry per geoid. "
            "Please double check that data only spans one year, measure, etc."
        )

    if data[val_col].isna().any():
        warnings.warn(
            "data contains missing values. the value of any new tract that overlaps "
            "with a NULL value will be coerced to NULL. If this is an issue, "
            "we recommend manual insertion of values based on contextual specifications."
        )

    data = data[[geoid_col, val_col]].copy()
    data = data.rename(columns={val_col: "value"})

    crosswalk = create_crosswalk(list(geoids), state_fips=state_fips)

    joined = crosswalk.merge(data, left_on="geoid10", right_on=geoid_col, how="left")

    same_bounds = (
        joined[joined["type_change"].isin(["same", "split"])]
        .groupby("geoid20", as_index=False)["value"]
        .first()
    )

    moved_bounds = joined[joined["type_change"] == "moved"].copy()
    moved_bounds["pct_overlap"] = moved_bounds["area_part"] / moved_bounds["area20"]
    moved_bounds["value"] = moved_bounds["value"] * moved_bounds["pct_overlap"]
    moved_bounds = moved_bounds.groupby("geoid20", as_index=False)["value"].sum()

    redistributed = pd.concat([same_bounds, moved_bounds], ignore_index=True)
    redistributed = redistributed.rename(columns={"geoid20": "geoid", "value": val_col})

    return redistributed


def standardize_all(
    data: pd.DataFrame,
    *,
    filter_geo: str = "state",
    geoid_col: str = "geoid",
    measure_col: str = "measure",
    year_col: str = "year",
    value_col: str = "value",
    moe_col: str = "moe",
    region_type_col: str = "region_type",
    state_fips: str = "51",
) -> pd.DataFrame:
    """Standardize 2010 geographies to 2020 boundaries for tract data.

    Assumes SDC conventions:
    columns: geoid, year, measure, value, moe, region_type.
    """
    years = data[year_col].unique()
    measures = data[measure_col].unique()

    columns = [geoid_col, measure_col, year_col, value_col, moe_col]
    if region_type_col in data.columns:
        columns.append(region_type_col)
    data = data[columns].copy()
    data[geoid_col] = data[geoid_col].astype(str)

    original = data.copy()
    original[measure_col] = original.apply(
        lambda row: (
            f"{row[measure_col]}_geo10"
            if row[year_col] < 2020 and len(row[geoid_col]) == 11
            else f"{row[measure_col]}_geo20"
        ),
        axis=1,
    )

    standardized_parts: list[pd.DataFrame] = []

    for yr in years:
        if yr < 2020:
            for meas in measures:
                temp = data[
                    (data[year_col] == yr)
                    & (data[measure_col] == meas)
                    & (data[geoid_col].str.len() == 11)
                ]
                if temp.empty:
                    continue

                converted = convert_2010_to_2020_bounds(
                    temp,
                    geoid_col=geoid_col,
                    val_col=value_col,
                    state_fips=state_fips,
                )
                converted[year_col] = yr
                converted[measure_col] = f"{meas}_geo20"
                converted[moe_col] = pd.NA
                if region_type_col in data.columns:
                    converted[region_type_col] = "tract"
                standardized_parts.append(converted)

    standardized = (
        pd.concat(standardized_parts, ignore_index=True)
        if standardized_parts
        else pd.DataFrame(columns=data.columns)
    )

    final = pd.concat([standardized, original], ignore_index=True)

    if filter_geo == "state":
        geoids = original[geoid_col].str[:2].unique()
        final = final[final[geoid_col].str[:2].isin(geoids)]
    elif filter_geo == "county":
        geoids = original[geoid_col].str[:5].unique()
        final = final[final[geoid_col].str[:5].isin(geoids)]

    return final
