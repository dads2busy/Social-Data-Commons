"""Naming helpers for SDC table file names.

Convention: <coverage_area>_<resolution>_<data_source>_<time_period>_<title>

The helpers here build names using available parts and infer coverage,
resolution, data source, and time period when possible. Missing parts
are omitted from the final name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

# Resolution order requested by user
RESOLUTION_ORDER = ["hd", "ct", "tr", "bg", "bl", "nb", "ca", "pl", "bz", "pr", "pt"]

# Common region_type values mapped to abbreviations
REGION_TYPE_ABBR = {
    "health_district": "hd",
    "health district": "hd",
    "county": "ct",
    "tract": "tr",
    "block_group": "bg",
    "block group": "bg",
    "block": "bl",
    "neighborhood": "nb",
    "place": "pl",
    "business": "bz",
    "civic_association": "ca",
    "civic association": "ca",
    "person": "pr",
    "point": "pt",
    "facility": "pt",
    # Sometimes pipelines use abbreviations already
    "hd": "hd",
    "ct": "ct",
    "tr": "tr",
    "bg": "bg",
    "bl": "bl",
    "nb": "nb",
    "pl": "pl",
    "bz": "bz",
    "ca": "ca",
    "pr": "pr",
    "pt": "pt",
}

DEFAULT_COVERAGE_MAP = {
    ("us",): "us",
    ("dc", "md", "va"): "ncr",
    ("va",): "va",
    ("md",): "md",
    ("dc",): "dc",
}


@dataclass(frozen=True)
class TableNameParts:
    coverage_area: Optional[str] = None
    resolution: Optional[str] = None
    data_source: Optional[str] = None
    time_period: Optional[str] = None
    title: Optional[str] = None


def _slugify(value: str) -> str:
    """Normalize a string for filenames: lowercase and underscores."""
    value = value.strip().lower()
    value = re.sub(r"[^\w]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")


def infer_resolution_from_region_types(region_types: Iterable[str]) -> Optional[str]:
    """Infer a combined resolution string from a list of region_type values."""
    present = set()
    for rt in region_types:
        if rt is None:
            continue
        key = str(rt).strip().lower()
        abbr = REGION_TYPE_ABBR.get(key)
        if abbr:
            present.add(abbr)

    if not present:
        return None

    ordered = [abbr for abbr in RESOLUTION_ORDER if abbr in present]
    return "".join(ordered) if ordered else None


def infer_resolution_from_df(df, region_col: str = "region_type") -> Optional[str]:
    """Infer resolution from a DataFrame's region_type column."""
    if df is None:
        return None
    if region_col not in df.columns:
        return None
    return infer_resolution_from_region_types(df[region_col].dropna().unique())


def infer_resolution_from_geographies(geographies: Iterable[str] | None) -> Optional[str]:
    """Infer a combined resolution string from a list of geography values."""
    if not geographies:
        return None
    present = set()
    for geo in geographies:
        if geo is None:
            continue
        key = str(geo).strip().lower()
        abbr = REGION_TYPE_ABBR.get(key)
        if abbr:
            present.add(abbr)

    if not present:
        return None

    ordered = [abbr for abbr in RESOLUTION_ORDER if abbr in present]
    return "".join(ordered) if ordered else None


def infer_coverage_area_from_states(
    states: Iterable[str] | None,
    *,
    mapping: Optional[dict[tuple[str, ...], str]] = None,
) -> Optional[str]:
    """Infer coverage area abbreviation from a list of state codes."""
    if not states:
        return None
    normalized = tuple(sorted({str(s).strip().lower() for s in states if s}))
    if not normalized:
        return None
    effective_map = mapping or DEFAULT_COVERAGE_MAP
    if effective_map and normalized in effective_map:
        return effective_map[normalized]
    if len(normalized) == 1:
        return normalized[0]
    return None


def infer_time_period_from_years(years: Iterable[int] | None) -> Optional[str]:
    """Infer a YYYY or YYYY_YYYY time period string from years."""
    if not years:
        return None
    cleaned = sorted({int(y) for y in years if y is not None})
    if not cleaned:
        return None
    if len(cleaned) == 1:
        return str(cleaned[0])
    return f"{cleaned[0]}_{cleaned[-1]}"


def infer_data_source(
    source_type: Optional[str],
    *,
    mapping: Optional[dict[str, str]] = None,
) -> Optional[str]:
    """Infer a data source abbreviation from a source type string."""
    if not source_type:
        return None
    key = str(source_type).strip().lower()
    if mapping and key in mapping:
        return mapping[key]
    return key


def build_file_name(
    *,
    coverage_area: Optional[str] = None,
    resolution: Optional[str] = None,
    data_source: Optional[str] = None,
    time_period: Optional[str] = None,
    title: Optional[str] = None,
    df=None,
    region_col: str = "region_type",
    geographies: Iterable[str] | None = None,
    states: Iterable[str] | None = None,
    years: Iterable[int] | None = None,
    source_type: Optional[str] = None,
    coverage_map: Optional[dict[tuple[str, ...], str]] = None,
    data_source_map: Optional[dict[str, str]] = None,
) -> str:
    """Build a table filename from available parts.

    Missing parts are omitted. If resolution, coverage, data source, or time
    period are not provided and supporting inputs are, they are inferred.

    Returns a string without file extension.
    """
    resolved_resolution = (
        resolution
        or infer_resolution_from_df(df, region_col=region_col)
        or infer_resolution_from_geographies(geographies)
    )
    resolved_coverage_area = coverage_area or infer_coverage_area_from_states(
        states, mapping=coverage_map
    )
    resolved_data_source = data_source or infer_data_source(source_type, mapping=data_source_map)
    resolved_time_period = time_period or infer_time_period_from_years(years)

    parts = [
        resolved_coverage_area,
        resolved_resolution,
        resolved_data_source,
        resolved_time_period,
        title,
    ]

    cleaned = [_slugify(p) for p in parts if p]
    return "_".join(cleaned)


__all__ = [
    "TableNameParts",
    "build_file_name",
    "infer_coverage_area_from_states",
    "infer_time_period_from_years",
    "infer_data_source",
    "infer_resolution_from_df",
    "infer_resolution_from_geographies",
    "infer_resolution_from_region_types",
    "RESOLUTION_ORDER",
    "REGION_TYPE_ABBR",
    "DEFAULT_COVERAGE_MAP",
]
