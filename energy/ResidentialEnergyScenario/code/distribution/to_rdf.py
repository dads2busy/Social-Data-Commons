"""RDF graph for the ResidentialEnergyScenario pipeline (simulated VA 2030).

The combined county + tract CSV mixes two period conventions and two tract
vintages, so it becomes four qb:DataSets in one graph:

- ``{stem}/static`` and ``{stem}/hourly``: the ``*_geo20`` measures (counties and
  2020 tracts). Static rows are adoption rates and household counts, whose
  datetime 2030-01-01 marks the scenario year; hourly rows are
  pv_generation_kwh as a typical-day profile (year plus sdc:hourOfDay).
- ``{stem}/static-geo10`` and ``{stem}/hourly-geo10``: the ``*_geo10`` measures,
  the simulation's original values on 2010 tracts, published on
  vintage-qualified tract IRIs (sdcid:tract-2010/{geoid}).

There is no point data and no household microdata, only the published
aggregates. ``long_format_from_graph`` rebuilds the combined CSV. Pure functions
only. prepare.py does the file I/O.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd
from rdflib import RDFS, Graph, Literal
from sdc_rdf import bind_prefixes, cube_to_long_format, dataset_iri, long_format_to_cube, scenario_iri
from sdc_rdf.cube import HOUR_OF_DAY_RE, YEAR_ANCHOR_RE

PARTS = ("static", "hourly", "static-geo10", "hourly-geo10")
LABELS = {
    "static": "adoption and households, counties and 2020 tracts",
    "hourly": "hourly PV generation, counties and 2020 tracts",
    "static-geo10": "adoption and households, original 2010 tracts",
    "hourly-geo10": "hourly PV generation, original 2010 tracts",
}


def split_parts(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Rows per dataset: period convention (static/hourly) x vintage (geo20/geo10)."""
    dt = df["datetime"].astype(str)
    static, hourly = dt.str.match(YEAR_ANCHOR_RE.pattern), dt.str.match(HOUR_OF_DAY_RE.pattern)
    if not (static | hourly).all():
        raise ValueError(f"datetimes outside both conventions: {sorted(set(dt[~(static | hourly)]))[:3]}")
    geo10 = df["measure"].str.endswith("_geo10")
    if not df["measure"].str.endswith(("_geo10", "_geo20")).all():
        raise ValueError("measures must carry a _geo10 or _geo20 suffix (spec §7.1)")
    if (geo10 & (df["region_type"] != "tract")).any():
        raise ValueError("_geo10 measures must be tract rows")
    return {
        "static": df[static & ~geo10],
        "hourly": df[hourly & ~geo10],
        "static-geo10": df[static & geo10],
        "hourly-geo10": df[hourly & geo10],
    }


def build_graph(
    combined: pd.DataFrame,
    *,
    measure_info: Mapping[str, Mapping],
    dataset_stem: str,
    geo10_tract_vintage: int,
    description: str,
) -> Graph:
    """The four county/tract cubes for the scenario, as one graph."""
    scenarios = combined["scenario"].unique()
    if len(scenarios) != 1:
        raise ValueError(f"expected one residential scenario, found {sorted(scenarios)}")

    g = bind_prefixes(Graph())
    for part, rows in split_parts(combined).items():
        if rows.empty:
            continue
        long_format_to_cube(
            g, rows, dataset_id=f"{dataset_stem}/{part}",
            label=f"Residential energy scenario 2030: {LABELS[part]}",
            measure_info=measure_info,
            year_anchor=part.startswith("static"),
            hour_of_day_profile=part.startswith("hourly"),
            region_vintages={"tract": geo10_tract_vintage} if part.endswith("geo10") else None,
        )
    scenario = scenario_iri(scenarios[0])
    g.add((scenario, RDFS.label, Literal(f"Residential energy scenario {scenarios[0]}")))
    g.add((scenario, RDFS.comment, Literal(description)))
    return g


def long_format_from_graph(g: Graph, dataset_stem: str) -> pd.DataFrame:
    """Rebuild the combined CSV frame (inverse of ``build_graph``), sorted like a cube."""
    frames = [
        cube_to_long_format(g, dataset_iri(f"{dataset_stem}/{part}"))
        for part in PARTS
        if (dataset_iri(f"{dataset_stem}/{part}"), None, None) in g
    ]
    return pd.concat(frames, ignore_index=True).sort_values(
        ["geoid", "datetime", "scenario", "measure"], ignore_index=True
    )
