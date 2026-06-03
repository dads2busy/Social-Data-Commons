"""Apply 2010→2020 crosswalks to long-format census data."""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

import pandas as pd

from sdc_census10to20.crosswalk import create_crosswalk

__all__ = ["convert_2010_to_2020_bounds", "parse_geo_standardize_info", "standardize_all"]


_SUB_COUNTY_LENGTHS = {11, 12}  # tract, block group
_GEOID_LEN_TO_REGION_TYPE = {11: "tract", 12: "block_group"}

_GEO_SUFFIX_RE = re.compile(r"_(geo10|geo20)$")


def _strip_geo_suffix(name: str) -> str:
    return _GEO_SUFFIX_RE.sub("", name)


def parse_geo_standardize_info(measure_info) -> dict[str, dict]:
    """Map base measure name -> its geo_standardize spec.

    ``measure_info`` may be a dict (already-loaded measure_info.json) or a path
    to a measure_info.json file. Keys are suffixed (``..._geo20``); we strip the
    suffix so lookups match the base measure names carried in the data frame.
    Entries without a ``geo_standardize`` block, and underscore-prefixed keys
    (e.g. ``_references``), are skipped.
    """
    if isinstance(measure_info, (str, Path)):
        with open(measure_info, encoding="utf-8") as f:
            measure_info = json.load(f)
    specs: dict[str, dict] = {}
    for key, val in measure_info.items():
        if key.startswith("_") or not isinstance(val, dict):
            continue
        block = val.get("geo_standardize")
        if block:
            # If both _geo10 and _geo20 variants appear, the later key wins.
            # That is fine: both share identical geo_standardize metadata.
            specs[_strip_geo_suffix(key)] = block
    return specs


_COUNT_HINTS = ("count", "_pop", "population", "households", "total")
# Broad "intensive" hints for the ratio catch-all in _classify_by_name. Some entries
# (density, median, mean/average/avg, ratio) are also matched by earlier dedicated
# branches there; they are kept here for completeness/defensiveness when the tuple is
# reused, but in _classify_by_name those earlier branches win.
_INTENSIVE_HINTS = (
    "percent", "_pct", "rate", "median", "mean", "average", "avg",
    "index", "score", "gini", "density", "ratio", "frac",
)


def _classify_by_name(measure: str) -> str:
    """Fallback classification when no geo_standardize metadata is provided."""
    m = measure.lower()
    if "density" in m:
        return "density"
    if "median" in m:
        return "median"
    if any(h in m for h in ("mean", "average", "avg")):
        return "mean"
    if any(h in m for h in _INTENSIVE_HINTS):
        return "ratio"
    if any(h in m for h in _COUNT_HINTS):
        return "count"
    return "count"  # safest default: behaves as today (area-weighted)


def _measure_slice(data: pd.DataFrame, yr, geoid_len, meas, *, year_col, geoid_col, measure_col, value_col) -> pd.DataFrame:
    s = data[
        (data[year_col] == yr)
        & (data[measure_col] == meas)
        & (data[geoid_col].str.len() == geoid_len)
    ]
    return s[[geoid_col, value_col]].copy()


def _redistribute_ratio_exact(num_slice, denom_slice, scale, *, geoid_col, value_col, state_fips):
    """ratio_geo20 = scale * numerator_geo20 / denominator_geo20.

    The merge uses ``on="geoid"`` because ``convert_2010_to_2020_bounds`` always
    returns a frame whose geography column is named ``"geoid"`` (the 2020 GEOID),
    regardless of the caller's ``geoid_col``.

    ``scale`` converts the count-derived fraction to display units (e.g. 100 for
    percent, 100 000 for per-100k rates).  When ``denominator_geo20`` is 0 the
    result is NaN/inf — intentionally left unguarded, as a zero denominator means
    an empty geography and an undefined rate by convention.
    """
    num = convert_2010_to_2020_bounds(
        num_slice, geoid_col=geoid_col, val_col=value_col, state_fips=state_fips,
    )
    den = convert_2010_to_2020_bounds(
        denom_slice, geoid_col=geoid_col, val_col=value_col, state_fips=state_fips,
    )
    m = num.merge(den, on="geoid", suffixes=("_num", "_den"))
    m[value_col] = scale * m[f"{value_col}_num"] / m[f"{value_col}_den"]
    return m[["geoid", value_col]]


def _redistribute_ratio_weighted(meas_slice, weight_slice, *, geoid_col, value_col, state_fips):
    """Population-weighted average: convert(value*weight) / convert(weight).

    Values are already in display units (e.g. 42.0), so no scale factor. The
    merge key is "geoid" because convert_2010_to_2020_bounds always returns a
    frame whose geography column is named "geoid".
    """
    merged = meas_slice.merge(weight_slice, on=geoid_col, suffixes=("_v", "_w"))
    merged["_vw"] = merged[f"{value_col}_v"] * merged[f"{value_col}_w"]
    vw = merged[[geoid_col, "_vw"]].rename(columns={"_vw": value_col})
    num = convert_2010_to_2020_bounds(
        vw, geoid_col=geoid_col, val_col=value_col, state_fips=state_fips,
    )
    den = convert_2010_to_2020_bounds(
        weight_slice, geoid_col=geoid_col, val_col=value_col, state_fips=state_fips,
    )
    m = num.merge(den, on="geoid", suffixes=("_num", "_den"))
    m[value_col] = m[f"{value_col}_num"] / m[f"{value_col}_den"]
    return m[["geoid", value_col]]


def convert_2010_to_2020_bounds(
    data: pd.DataFrame,
    *,
    geoid_col: str = "geoid",
    val_col: str = "value",
    state_fips: str = "51",
) -> pd.DataFrame:
    """Redistribute a single year/measure of 2010-vintage values onto 2020 boundaries.

    The input frame must contain exactly one row per GEOID (one year, one
    measure). Each 2010 source distributes its value to the overlapping 2020
    tracts by the fraction of the *source* area in each overlap
    (``area_part / area10``); a source's overlaps tile it, so the fractions sum to
    1 and the total is conserved (count-preserving areal interpolation, using the
    Census relationship file's land-area overlaps).

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

    # Areal interpolation that conserves counts: each 2010 source distributes its
    # value to overlapping 2020 tracts by the fraction of the *source* area in the
    # overlap (area_part / area10). A source's overlaps tile it, so the fractions
    # sum to 1 and the source's full value is distributed. type_change does not
    # affect the math -- the geometry in area_part/area10 already encodes same vs
    # split vs moved.
    joined["value"] = joined["value"] * (joined["area_part"] / joined["area10"])
    redistributed = joined.groupby("geoid20", as_index=False)["value"].sum()
    redistributed = redistributed.rename(columns={"geoid20": "geoid", "value": val_col})
    return redistributed


def standardize_all(
    data: pd.DataFrame,
    *,
    measure_info=None,
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

    specs = parse_geo_standardize_info(measure_info) if measure_info is not None else {}

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

                    spec = specs.get(meas)
                    mtype = spec["measure_type"] if spec else _classify_by_name(meas)

                    if mtype == "count":
                        converted = convert_2010_to_2020_bounds(
                            temp, geoid_col=geoid_col, val_col=value_col,
                            state_fips=state_fips,
                        )
                    elif mtype in ("ratio", "rate"):
                        if spec and spec.get("numerator") and spec.get("denominator"):
                            num_slice = _measure_slice(
                                data, yr, geoid_len, spec["numerator"],
                                year_col=year_col, geoid_col=geoid_col,
                                measure_col=measure_col, value_col=value_col,
                            )
                            den_slice = _measure_slice(
                                data, yr, geoid_len, spec["denominator"],
                                year_col=year_col, geoid_col=geoid_col,
                                measure_col=measure_col, value_col=value_col,
                            )
                            if num_slice.empty or den_slice.empty:
                                raise ValueError(
                                    f"ratio {meas!r}: numerator/denominator "
                                    f"counts missing from frame for year {yr}"
                                )
                            converted = _redistribute_ratio_exact(
                                num_slice, den_slice, spec.get("scale", 100),
                                geoid_col=geoid_col, value_col=value_col,
                                state_fips=state_fips,
                            )
                        else:
                            weight = spec.get("weight") if spec else None
                            if not weight:
                                raise ValueError(
                                    f"ratio {meas!r}: declare numerator+denominator "
                                    f"or a weight in geo_standardize"
                                )
                            w_slice = _measure_slice(
                                data, yr, geoid_len, weight,
                                year_col=year_col, geoid_col=geoid_col,
                                measure_col=measure_col, value_col=value_col,
                            )
                            if w_slice.empty:
                                raise ValueError(
                                    f"ratio {meas!r}: weight {weight!r} missing "
                                    f"from frame for year {yr}"
                                )
                            converted = _redistribute_ratio_weighted(
                                temp[[geoid_col, value_col]], w_slice,
                                geoid_col=geoid_col, value_col=value_col,
                                state_fips=state_fips,
                            )
                    else:
                        raise NotImplementedError(
                            f"measure_type {mtype!r} not yet handled (measure {meas!r})"
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
