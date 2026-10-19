"""RDF graph for the ResidentialEnergyScenario pipeline (simulated VA 2030).

The combined county + tract CSV mixes two period conventions, so it becomes two
qb:DataSets in one graph:

- ``{stem}/static``: adoption rates and household counts, whose datetime
  2030-01-01 marks the scenario year (refPeriod = 2030)
- ``{stem}/hourly``: pv_generation_kwh as a typical-day profile
  (refPeriod = 2030 plus sdc:hourOfDay)

There is no point data and no household microdata, only the published
aggregates. Tracts are 2010-vintage (``tract_vintage``) and get
vintage-qualified IRIs. ``long_format_from_graph`` rebuilds the combined CSV.
Pure functions only. prepare.py does the file I/O.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd
from rdflib import RDFS, Graph, Literal
from sdc_rdf import bind_prefixes, cube_to_long_format, dataset_iri, long_format_to_cube, scenario_iri
from sdc_rdf.cube import HOUR_OF_DAY_RE, YEAR_ANCHOR_RE

PARTS = ("static", "hourly")


def split_by_period(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Static (YYYY-01-01) and hourly (YYYY-01-01THH:00:00) rows; anything else is an error."""
    dt = df["datetime"].astype(str)
    static, hourly = dt.str.match(YEAR_ANCHOR_RE.pattern), dt.str.match(HOUR_OF_DAY_RE.pattern)
    if not (static | hourly).all():
        raise ValueError(f"datetimes outside both conventions: {sorted(set(dt[~(static | hourly)]))[:3]}")
    return {"static": df[static], "hourly": df[hourly]}


def build_graph(
    combined: pd.DataFrame,
    *,
    measure_info: Mapping[str, Mapping],
    dataset_stem: str,
    tract_vintage: int | None,
    description: str,
) -> Graph:
    """Static and hourly county/tract cubes for the scenario, as one graph."""
    scenarios = combined["scenario"].unique()
    if len(scenarios) != 1:
        raise ValueError(f"expected one residential scenario, found {sorted(scenarios)}")
    vintages = {"tract": tract_vintage} if tract_vintage else None

    g = bind_prefixes(Graph())
    parts = split_by_period(combined)
    long_format_to_cube(
        g, parts["static"], dataset_id=f"{dataset_stem}/static",
        label="Residential energy scenario 2030: adoption and households (county, tract)",
        measure_info=measure_info, year_anchor=True, region_vintages=vintages,
    )
    long_format_to_cube(
        g, parts["hourly"], dataset_id=f"{dataset_stem}/hourly",
        label="Residential energy scenario 2030: hourly PV generation (county, tract)",
        measure_info=measure_info, hour_of_day_profile=True, region_vintages=vintages,
    )
    scenario = scenario_iri(scenarios[0])
    g.add((scenario, RDFS.label, Literal(f"Residential energy scenario {scenarios[0]}")))
    g.add((scenario, RDFS.comment, Literal(description)))
    return g


def long_format_from_graph(g: Graph, dataset_stem: str) -> pd.DataFrame:
    """Rebuild the combined CSV frame (inverse of ``build_graph``), sorted like a cube."""
    frames = [cube_to_long_format(g, dataset_iri(f"{dataset_stem}/{part}")) for part in PARTS]
    return pd.concat(frames, ignore_index=True).sort_values(
        ["geoid", "datetime", "scenario", "measure"], ignore_index=True
    )
