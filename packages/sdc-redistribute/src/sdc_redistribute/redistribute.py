"""Spatial redistribution of data between geographic frameworks.

Two methods for estimating values at non-census geographies:

- **direct** (areal interpolation): Allocates source polygon values to target
  polygons proportionally by area overlap. Assumes uniform distribution within
  each source unit.

- **parcels** (centroid-based dasymetric): Distributes source values evenly
  across parcel centroids within each source unit, then aggregates centroids
  falling within each target polygon. More accurate where parcel data exists.

Both methods produce long-format DataFrames with a ``_direct`` or ``_parcels``
suffix appended to each measure name.

Usage:
    from sdc_core.redistribute import redistribute_direct

    result = redistribute_direct(
        source_df=acs_long,
        source_geo="path/to/tracts_2020.geojson",
        target_geos={"zip_code": "path/to/zip_codes.geojson"},
        count_cols=["total_pop", "pop_under_20"],
        pct_specs={"perc_under_20": ("pop_under_20", "total_pop")},
    )
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    import geopandas as gpd

log = logging.getLogger(__name__)


def _load_geo(path: str | Path) -> gpd.GeoDataFrame:
    """Read a GeoJSON file into a projected GeoDataFrame."""
    import geopandas

    gdf = geopandas.read_file(path)
    if gdf.crs is None or gdf.crs.is_geographic:
        gdf = gdf.to_crs(epsg=3857)
    return gdf


def redistribute_direct(
    source_df: pd.DataFrame,
    source_geo: str | Path,
    target_geos: dict[str, str | Path],
    count_cols: list[str],
    pct_specs: dict[str, tuple[str, str]] | None = None,
    *,
    source_id: str = "geoid",
    year_col: str = "year",
    measure_col: str = "measure",
    value_col: str = "value",
) -> pd.DataFrame:
    """Redistribute census data to target geographies using areal interpolation.

    Parameters
    ----------
    source_df : pd.DataFrame
        Long-format data with columns: geoid, year, measure, value.
        Must contain count measures (not percentages) for redistribution.
    source_geo : path
        GeoJSON file for source census geometries (tracts or block groups).
    target_geos : dict
        Mapping of ``{region_type: geojson_path}`` for each target geography.
    count_cols : list[str]
        Measure names that are counts and should be redistributed (area-weighted
        sum). These must exist in ``source_df[measure_col]``.
    pct_specs : dict or None
        Derived percentages to compute after redistribution.
        ``{new_measure: (numerator_measure, denominator_measure)}``.
    source_id : str
        ID column name in source GeoJSON (default ``"geoid"``).
    year_col, measure_col, value_col : str
        Column name overrides.

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame with redistributed values for all target
        geographies, measure names suffixed with ``_direct``.
    """
    import geopandas

    source_gdf = _load_geo(source_geo)
    source_gdf[source_id] = source_gdf[source_id].astype(str)
    source_gdf["_source_area"] = source_gdf.geometry.area

    years = sorted(source_df[year_col].unique())
    all_parts: list[pd.DataFrame] = []

    # Rename source_id to avoid collisions with target geoid columns
    _src_col = "_src_geoid"
    source_gdf = source_gdf.rename(columns={source_id: _src_col})

    for target_name, target_path in target_geos.items():
        target_gdf = _load_geo(target_path)
        target_id = "geoid" if "geoid" in target_gdf.columns else target_gdf.columns[0]
        _tgt_col = "_tgt_geoid"
        target_gdf = target_gdf.rename(columns={target_id: _tgt_col})
        target_gdf = target_gdf[[_tgt_col, "geometry"]].copy()
        target_gdf[_tgt_col] = target_gdf[_tgt_col].astype(str)

        # Pre-compute intersection weights (source → target → weight).
        # Weights are the fraction of the source polygon's area that overlaps
        # each target polygon.
        log.info("Computing intersection weights: source → %s", target_name)
        intersections = geopandas.overlay(
            source_gdf[[_src_col, "_source_area", "geometry"]],
            target_gdf,
            how="intersection",
            keep_geom_type=True,
        )
        intersections["_int_area"] = intersections.geometry.area
        intersections["_weight"] = intersections["_int_area"] / intersections["_source_area"]
        weights = intersections[[_src_col, _tgt_col, "_weight"]].copy()

        for yr in years:
            yr_data = source_df[source_df[year_col] == yr]

            # Pivot to wide: one row per source geoid, one column per count measure
            counts_long = yr_data[yr_data[measure_col].isin(count_cols)]
            if counts_long.empty:
                continue

            wide = (
                counts_long.pivot_table(
                    index=source_id, columns=measure_col, values=value_col, aggfunc="first"
                )
                .reset_index()
                .rename(columns={source_id: _src_col})
            )
            wide.columns.name = None

            # Merge with weights and redistribute
            merged = weights.merge(wide, on=_src_col, how="inner")
            for col in count_cols:
                if col in merged.columns:
                    merged[col] = merged[col] * merged["_weight"]

            # Aggregate to target regions
            agg = merged.groupby(_tgt_col)[count_cols].sum().reset_index()

            # Rescale so target totals match source totals
            for col in count_cols:
                source_total = wide[col].sum()
                target_total = agg[col].sum()
                if target_total > 0 and source_total > 0:
                    agg[col] = agg[col] * (source_total / target_total)

            # Compute derived percentages
            if pct_specs:
                for pct_name, (num, denom) in pct_specs.items():
                    if num in agg.columns and denom in agg.columns:
                        agg[pct_name] = 100 * agg[num] / agg[denom]

            # Melt to long format
            all_measure_cols = [c for c in agg.columns if c != _tgt_col]
            long = agg.melt(
                id_vars=[_tgt_col],
                value_vars=all_measure_cols,
                var_name=measure_col,
                value_name=value_col,
            )
            long = long.rename(columns={_tgt_col: source_id})
            long[year_col] = yr
            long["region_type"] = target_name
            long["moe"] = pd.NA

            all_parts.append(long)

    if not all_parts:
        return pd.DataFrame(columns=[source_id, year_col, measure_col, value_col, "moe"])

    result = pd.concat(all_parts, ignore_index=True)
    result[measure_col] = result[measure_col] + "_direct"
    return result


def redistribute_parcels(
    source_df: pd.DataFrame,
    parcel_centroids: pd.DataFrame | gpd.GeoDataFrame,
    source_geo: str | Path,
    target_geos: dict[str, str | Path],
    count_cols: list[str],
    pct_specs: dict[str, tuple[str, str]] | None = None,
    *,
    source_id: str = "geoid",
    year_col: str = "year",
    measure_col: str = "measure",
    value_col: str = "value",
    parcel_lon: str = "lon",
    parcel_lat: str = "lat",
) -> pd.DataFrame:
    """Redistribute census data via parcel centroids (dasymetric method).

    Parameters
    ----------
    source_df : pd.DataFrame
        Long-format data with columns: geoid, year, measure, value.
    parcel_centroids : DataFrame or GeoDataFrame
        Parcel centroids with at least ``lon``, ``lat`` columns (or geometry).
    source_geo : path
        GeoJSON for source census geometries (block groups or tracts).
    target_geos : dict
        ``{region_type: geojson_path}`` for each target geography.
    count_cols : list[str]
        Count measure names to redistribute.
    pct_specs : dict or None
        ``{new_measure: (numerator, denominator)}`` for derived percentages.
    source_id : str
        ID column in source GeoJSON.
    year_col, measure_col, value_col : str
        Column name overrides.
    parcel_lon, parcel_lat : str
        Longitude/latitude column names in parcel_centroids (ignored if
        parcel_centroids is already a GeoDataFrame with geometry).

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame with ``_parcels`` suffixed measure names.
    """
    import geopandas
    from shapely.geometry import Point

    source_gdf = _load_geo(source_geo)
    _src_col = "_src_geoid"
    source_gdf = source_gdf.rename(columns={source_id: _src_col})
    source_gdf[_src_col] = source_gdf[_src_col].astype(str)

    # Build GeoDataFrame of parcel centroids if needed
    if not isinstance(parcel_centroids, geopandas.GeoDataFrame):
        geometry = [
            Point(x, y) for x, y in zip(parcel_centroids[parcel_lon], parcel_centroids[parcel_lat])
        ]
        parcels_gdf = geopandas.GeoDataFrame(
            parcel_centroids, geometry=geometry, crs="EPSG:4326"
        )
    else:
        parcels_gdf = parcel_centroids.copy()

    if parcels_gdf.crs is None or parcels_gdf.crs.is_geographic:
        parcels_gdf = parcels_gdf.to_crs(epsg=3857)

    # Step 1: Assign each parcel centroid to a source geography
    log.info("Joining %d parcel centroids to source polygons", len(parcels_gdf))
    parcels_in_source = geopandas.sjoin(
        parcels_gdf, source_gdf[[_src_col, "geometry"]], how="inner", predicate="within"
    )

    # Count parcels per source unit
    parcel_counts = parcels_in_source.groupby(_src_col).size().reset_index(name="_n_parcels")

    # Step 2: Assign each parcel centroid to target geographies
    _tgt_col = "_tgt_geoid"
    target_assignments: dict[str, pd.DataFrame] = {}
    for target_name, target_path in target_geos.items():
        target_gdf = _load_geo(target_path)
        target_id = "geoid" if "geoid" in target_gdf.columns else target_gdf.columns[0]
        target_gdf = target_gdf.rename(columns={target_id: _tgt_col})
        target_gdf = target_gdf[[_tgt_col, "geometry"]].copy()
        target_gdf[_tgt_col] = target_gdf[_tgt_col].astype(str)

        log.info("Joining parcel centroids to %s polygons", target_name)
        parcels_in_target = geopandas.sjoin(
            parcels_in_source[[_src_col, "geometry"]],
            target_gdf,
            how="inner",
            predicate="within",
        )
        target_assignments[target_name] = parcels_in_target[[_src_col, _tgt_col]].copy()

    years = sorted(source_df[year_col].unique())
    all_parts: list[pd.DataFrame] = []

    for yr in years:
        yr_data = source_df[source_df[year_col] == yr]
        counts_long = yr_data[yr_data[measure_col].isin(count_cols)]
        if counts_long.empty:
            continue

        wide = (
            counts_long.pivot_table(
                index=source_id, columns=measure_col, values=value_col, aggfunc="first"
            )
            .reset_index()
            .rename(columns={source_id: _src_col})
        )
        wide.columns.name = None

        # Disaggregate: divide source values evenly across parcels
        wide = wide.merge(parcel_counts, on=_src_col, how="inner")
        for col in count_cols:
            if col in wide.columns:
                wide[col] = wide[col] / wide["_n_parcels"]

        for target_name, assignment in target_assignments.items():
            # Join parcel-level values to target assignment
            parcel_values = assignment.merge(wide, on=_src_col, how="inner")

            # Reaggregate to target regions
            agg = parcel_values.groupby(_tgt_col)[count_cols].sum().reset_index()

            # Compute derived percentages
            if pct_specs:
                for pct_name, (num, denom) in pct_specs.items():
                    if num in agg.columns and denom in agg.columns:
                        agg[pct_name] = 100 * agg[num] / agg[denom]

            # Melt to long format
            all_measure_cols = [c for c in agg.columns if c != _tgt_col]
            long = agg.melt(
                id_vars=[_tgt_col],
                value_vars=all_measure_cols,
                var_name=measure_col,
                value_name=value_col,
            )
            long = long.rename(columns={_tgt_col: source_id})
            long[year_col] = yr
            long["region_type"] = target_name
            long["moe"] = pd.NA

            all_parts.append(long)

    if not all_parts:
        return pd.DataFrame(columns=[source_id, year_col, measure_col, value_col, "moe"])

    result = pd.concat(all_parts, ignore_index=True)
    result[measure_col] = result[measure_col] + "_parcels"
    return result


import re

_GEO_SUFFIX_RE = re.compile(r"_(geo\d+)$")


def _strip_geo_suffix(name: str) -> tuple[str, str]:
    """Strip ``_geo20`` / ``_geo10`` suffix, returning (base_name, suffix).

    Returns (name, "") if no geo suffix is found.
    """
    m = _GEO_SUFFIX_RE.search(name)
    if m:
        return name[: m.start()], m.group(0)
    return name, ""


def _load_parcels(parcels_dir: Path, coverage_area: str) -> pd.DataFrame:
    """Load all parcel centroid parquet files for a coverage area."""
    parts: list[pd.DataFrame] = []

    if coverage_area == "ncr":
        subdirs = ["va", "dc", "md"]
    else:
        subdirs = [coverage_area]

    for subdir in subdirs:
        d = parcels_dir / subdir
        if not d.exists():
            continue
        for pq in sorted(d.glob("*_parcel_centroids.parquet")):
            parts.append(pd.read_parquet(pq))

    if not parts:
        raise FileNotFoundError(f"No parcel centroids found in {parcels_dir} for {coverage_area}")
    return pd.concat(parts, ignore_index=True)


def run_redistribution(
    df: pd.DataFrame,
    config: dict,
    repo_dir: Path,
    coverage_area: str = "ncr",
    *,
    source_id: str = "geoid",
    year_col: str = "year",
    measure_col: str = "measure",
    value_col: str = "value",
    logger: logging.Logger | None = None,
) -> pd.DataFrame:
    """High-level redistribution wrapper that handles geo-suffix conventions.

    Reads redistribution configuration, splits input data by geo vintage
    (``_geo20`` vs ``_geo10``), runs ``redistribute_direct`` and/or
    ``redistribute_parcels``, and produces measure names with the correct
    suffix ordering: ``{base}_{method}_{vintage}`` (e.g.
    ``perc_moving_direct_geo20``).

    Parameters
    ----------
    df : pd.DataFrame
        Long-format data (output of ingest/crosswalk steps). Must have
        ``region_type``, ``measure``, ``value``, ``year``, ``geoid`` columns.
        Measure names should already carry ``_geo20``/``_geo10`` suffixes.
    config : dict
        The ``prepare.redistribution`` section from pipeline.yaml::

            source_level: tract
            methods: [direct, parcels]
            count_measures: [total_pop, pop_moving]  # base names, no geo suffix
            pct_specs:
              perc_moving: [pop_moving, total_pop]   # base names
            target_geos:
              block_group:
                geo20: path/to/block_groups_2020.geojson
                geo10: path/to/block_groups_2010.geojson
            source_geos:
              geo20: path/to/tracts_2020.geojson
              geo10: path/to/tracts_2010.geojson
            parcels_dir: geographies/parcels  # optional, for parcels method

    repo_dir : Path
        Repository root for resolving relative paths in config.
    coverage_area : str
        Coverage area code (``"va"``, ``"ncr"``, etc.) for loading parcels.
    logger : logging.Logger or None
        Logger instance. Falls back to module-level logger.

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame with redistributed values. Measure names
        follow ``{base}_{method}_{vintage}`` convention.
    """
    _log = logger or log

    source_level = config["source_level"]
    methods = config.get("methods", ["direct"])
    base_count_measures = config["count_measures"]
    base_pct_specs = config.get("pct_specs") or {}
    target_geos_cfg = config["target_geos"]
    source_geos_cfg = config["source_geos"]
    parcels_dir_rel = config.get("parcels_dir")

    # Filter to source-level rows only
    source_df = df[df["region_type"] == source_level].copy()
    if source_df.empty:
        _log.warning("No rows with region_type=%s for redistribution", source_level)
        return pd.DataFrame(columns=[source_id, year_col, measure_col, value_col, "moe"])

    # Identify geo vintages present in the data
    measures_in_data = source_df[measure_col].unique()
    vintages: dict[str, list[str]] = {}  # e.g. {"_geo20": [...measure names...]}
    for m in measures_in_data:
        _, suffix = _strip_geo_suffix(m)
        if suffix:
            vintages.setdefault(suffix, []).append(m)

    if not vintages:
        _log.warning("No _geoNN suffixed measures found; skipping redistribution")
        return pd.DataFrame(columns=[source_id, year_col, measure_col, value_col, "moe"])

    all_results: list[pd.DataFrame] = []

    for geo_suffix, suffixed_measures in vintages.items():
        vintage_key = geo_suffix.lstrip("_")  # "geo20" or "geo10"

        # Resolve source and target GeoJSON paths for this vintage
        source_geo_rel = source_geos_cfg.get(vintage_key)
        if not source_geo_rel:
            _log.info("No source geo for vintage %s; skipping", vintage_key)
            continue
        source_geo_path = repo_dir / source_geo_rel

        target_geos: dict[str, Path] = {}
        for tgt_name, tgt_cfg in target_geos_cfg.items():
            tgt_path_rel = tgt_cfg.get(vintage_key) if isinstance(tgt_cfg, dict) else tgt_cfg
            if tgt_path_rel:
                target_geos[tgt_name] = repo_dir / tgt_path_rel

        if not target_geos:
            _log.info("No target geos for vintage %s; skipping", vintage_key)
            continue

        # Build the suffixed count_cols and pct_specs for this vintage
        count_cols_suffixed = [f"{c}{geo_suffix}" for c in base_count_measures]
        # Filter to only count cols actually present in data
        count_cols_suffixed = [c for c in count_cols_suffixed if c in suffixed_measures]

        pct_specs_suffixed: dict[str, tuple[str, str]] | None = None
        if base_pct_specs:
            pct_specs_suffixed = {}
            for pct_name, (num, denom) in base_pct_specs.items():
                pct_specs_suffixed[f"{pct_name}{geo_suffix}"] = (
                    f"{num}{geo_suffix}",
                    f"{denom}{geo_suffix}",
                )

        if not count_cols_suffixed:
            _log.warning("No count measures found for vintage %s; skipping", vintage_key)
            continue

        # Subset source data to this vintage's measures only
        vintage_df = source_df[source_df[measure_col].isin(suffixed_measures)].copy()

        # Strip geo suffix so redistribute_direct/parcels work with base names
        vintage_df[measure_col] = vintage_df[measure_col].str.replace(
            _GEO_SUFFIX_RE, "", regex=True
        )
        count_cols_bare = [c.replace(geo_suffix, "") for c in count_cols_suffixed]
        pct_specs_bare: dict[str, tuple[str, str]] | None = None
        if pct_specs_suffixed:
            pct_specs_bare = {
                k.replace(geo_suffix, ""): (n.replace(geo_suffix, ""), d.replace(geo_suffix, ""))
                for k, (n, d) in pct_specs_suffixed.items()
            }

        _log.info(
            "Redistributing %d measures (%s) to %s",
            len(count_cols_bare),
            vintage_key,
            list(target_geos.keys()),
        )

        for method in methods:
            if method == "direct":
                result = redistribute_direct(
                    source_df=vintage_df,
                    source_geo=source_geo_path,
                    target_geos=target_geos,
                    count_cols=count_cols_bare,
                    pct_specs=pct_specs_bare,
                    source_id=source_id,
                    year_col=year_col,
                    measure_col=measure_col,
                    value_col=value_col,
                )
                # redistribute_direct appends "_direct" → now append geo suffix
                result[measure_col] = result[measure_col] + geo_suffix

            elif method == "parcels":
                if not parcels_dir_rel:
                    _log.warning("parcels method requested but no parcels_dir configured")
                    continue
                parcels_dir = repo_dir / parcels_dir_rel
                parcel_centroids = _load_parcels(parcels_dir, coverage_area)
                result = redistribute_parcels(
                    source_df=vintage_df,
                    parcel_centroids=parcel_centroids,
                    source_geo=source_geo_path,
                    target_geos=target_geos,
                    count_cols=count_cols_bare,
                    pct_specs=pct_specs_bare,
                    source_id=source_id,
                    year_col=year_col,
                    measure_col=measure_col,
                    value_col=value_col,
                )
                # redistribute_parcels appends "_parcels" → now append geo suffix
                result[measure_col] = result[measure_col] + geo_suffix

            else:
                _log.warning("Unknown redistribution method: %s", method)
                continue

            if not result.empty:
                _log.info(
                    "  %s/%s: %d rows across %d target regions",
                    method,
                    vintage_key,
                    len(result),
                    result[source_id].nunique(),
                )
                all_results.append(result)

    if not all_results:
        return pd.DataFrame(columns=[source_id, year_col, measure_col, value_col, "moe"])

    return pd.concat(all_results, ignore_index=True)
