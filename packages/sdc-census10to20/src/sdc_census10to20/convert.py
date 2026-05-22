"""Apply 2010→2020 crosswalks to long-format census data."""

from __future__ import annotations

import warnings

import pandas as pd

from sdc_census10to20.crosswalk import create_crosswalk

__all__ = ["convert_2010_to_2020_bounds", "standardize_all"]


_SUB_COUNTY_LENGTHS = {11, 12}  # tract, block group
_GEOID_LEN_TO_REGION_TYPE = {11: "tract", 12: "block_group"}


def convert_2010_to_2020_bounds(
    data: pd.DataFrame,
    *,
    geoid_col: str = "geoid",
    val_col: str = "value",
    state_fips: str = "51",
) -> pd.DataFrame:
    """Redistribute a single year/measure of 2010-vintage values onto 2020 boundaries.

    The input frame must contain exactly one row per GEOID (one year, one
    measure). For "moved" boundaries the value is split by area-proportional
    weighting; "same" and "split" boundaries pass the value through unchanged.

    Parameters
    ----------
    data : pd.DataFrame
        Input frame with at least ``geoid_col`` and ``val_col``.
    geoid_col : str
        Name of the GEOID column (default ``"geoid"``).
    val_col : str
        Name of the value column (default ``"value"``).
    state_fips : str
        State FIPS for the block-group crosswalk (default Virginia, "51").

    Returns
    -------
    pd.DataFrame
        Two columns: ``geoid`` (2020 boundaries) and ``val_col`` (redistributed).
    """
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
            "we recommend manual insertion of values based on contextual specifications.",
            stacklevel=2,
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
    """Standardize 2010 geographies to 2020 boundaries for tract and block-group rows.

    Returns both the original measure (with ``_geo10`` suffix for pre-2020 sub-county
    rows, ``_geo20`` otherwise) and the redistributed measure (``_geo20`` suffix) so
    downstream consumers can compare or pick.

    Assumes SDC long format: ``(geoid, year, measure, value, moe[, region_type])``.
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
            if row[year_col] < 2020 and len(row[geoid_col]) in _SUB_COUNTY_LENGTHS
            else f"{row[measure_col]}_geo20"
        ),
        axis=1,
    )

    standardized_parts: list[pd.DataFrame] = []

    for yr in years:
        if yr < 2020:
            for meas in measures:
                for geoid_len in _SUB_COUNTY_LENGTHS:
                    temp = data[
                        (data[year_col] == yr)
                        & (data[measure_col] == meas)
                        & (data[geoid_col].str.len() == geoid_len)
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
                        converted[region_type_col] = _GEOID_LEN_TO_REGION_TYPE[geoid_len]
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
