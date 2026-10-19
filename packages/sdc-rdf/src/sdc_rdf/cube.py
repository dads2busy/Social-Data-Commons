"""Long-format distribution files → RDF Data Cube observations.

Handles both long-format variants in the commons:

- standard: ``geoid, year, measure, value, moe, region_type, data_method``
- energy:   ``geoid, datetime, measure, value, moe, region_type, data_method, scenario``

Energy files may also follow the hour-of-day-profile convention (energy/README.md):
``datetime = "{year}-01-01THH:00:00"`` marks hour HH of a typical day, not a real
timestamp. With ``hour_of_day_profile=True`` those rows become refPeriod = the
year (xsd:gYear) plus an sdc:hourOfDay dimension, so no false date is asserted.

Static scenario files likewise use ``datetime = "{year}-01-01"`` as a marker for the
scenario year. With ``year_anchor=True`` those rows become refPeriod = the year.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal

import pandas as pd
from rdflib import RDF, RDFS, XSD, Graph, Literal, URIRef
from rdflib.namespace import PROV, QB, SKOS

from .namespaces import SDC, SDCID, SDCM
from .regions import add_region

REQUIRED_COLUMNS = ["geoid", "measure", "value", "region_type", "data_method"]

HOUR_OF_DAY_RE = re.compile(r"^(\d{4})-01-01[T ](\d{2}):00:00$")
YEAR_ANCHOR_RE = re.compile(r"^(\d{4})-01-01$")

# measure_info.json field → (predicate, language-tagged?)
MEASURE_INFO_FIELDS = {
    "short_description": (RDFS.comment, True),
    "long_description": (SKOS.definition, True),
    "provenance": (SDC.provenance, False),
    "unit": (SDC.unit, False),
    "aggregation_method": (SDC.aggregationMethod, False),
    "category": (SDC.category, False),
}


def measure_iri(measure: str) -> URIRef:
    return SDCM[measure]


def scenario_iri(scenario: str) -> URIRef:
    return SDCID[f"scenario/{scenario}"]


def add_measure(g: Graph, measure: str, info: Mapping | None = None) -> URIRef:
    """Declare ``measure`` as a qb:MeasureProperty, with measure_info.json text if given."""
    m = measure_iri(measure)
    g.add((m, RDF.type, QB.MeasureProperty))
    g.add((m, RDFS.range, XSD.decimal))
    g.add((m, SKOS.notation, Literal(measure)))
    g.add((m, RDFS.label, Literal(measure.replace("_", " "))))
    for field, (pred, tagged) in MEASURE_INFO_FIELDS.items():
        if info and info.get(field):
            g.add((m, pred, Literal(info[field], lang="en" if tagged else None)))
    return m


def add_scenario(g: Graph, scenario: str) -> URIRef:
    s = scenario_iri(scenario)
    g.add((s, RDF.type, SDC.Scenario))
    g.add((s, SKOS.notation, Literal(scenario)))
    return s


def period_literal(row: Mapping) -> Literal:
    """``year`` → xsd:gYear; ``datetime`` → xsd:date or xsd:dateTime."""
    if "year" in row and not pd.isna(row["year"]):
        return Literal(f"{int(row['year']):04d}", datatype=XSD.gYear)
    dt = str(row["datetime"]).strip()
    if len(dt) == 10:
        return Literal(dt, datatype=XSD.date)
    return Literal(dt.replace(" ", "T"), datatype=XSD.dateTime)


def hour_of_day_period(row: Mapping) -> tuple[Literal, int]:
    """``"2026-01-01T07:00:00"`` → (``"2026"^^xsd:gYear``, 7) under the profile convention."""
    dt = str(row["datetime"]).strip()
    match = HOUR_OF_DAY_RE.match(dt)
    if not match or int(match[2]) > 23:
        raise ValueError(f"datetime {dt!r} does not follow the hour-of-day convention YYYY-01-01THH:00:00")
    return Literal(match[1], datatype=XSD.gYear), int(match[2])


def year_anchor_period(row: Mapping) -> Literal:
    """``"2030-01-01"`` → ``"2030"^^xsd:gYear`` under the static scenario-year convention."""
    dt = str(row["datetime"]).strip()
    match = YEAR_ANCHOR_RE.match(dt)
    if not match:
        raise ValueError(f"datetime {dt!r} does not follow the year-anchor convention YYYY-01-01")
    return Literal(match[1], datatype=XSD.gYear)


def _decimal(v) -> Decimal | None:
    if v is None or pd.isna(v) or str(v).strip() == "":
        return None
    return Decimal(str(v))


def long_format_to_cube(
    g: Graph,
    df: pd.DataFrame,
    *,
    dataset_id: str,
    label: str,
    measure_info: Mapping[str, Mapping] | None = None,
    hour_of_day_profile: bool = False,
    year_anchor: bool = False,
) -> URIRef:
    """Add one qb:DataSet (with its structure) and one qb:Observation per row of ``df``.

    ``dataset_id`` should be the distribution file stem (e.g.
    ``va_ct_hifld_2026_power_infrastructure``); it scopes the dataset,
    structure and observation IRIs. Set ``hour_of_day_profile`` or ``year_anchor``
    for energy files that follow those conventions (see module docstring). Returns
    the dataset IRI.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if "year" not in df.columns and "datetime" not in df.columns:
        missing.append("year|datetime")
    if hour_of_day_profile and year_anchor:
        raise ValueError("hour_of_day_profile and year_anchor are mutually exclusive")
    if (hour_of_day_profile or year_anchor) and "datetime" not in df.columns:
        missing.append("datetime")
    if missing:
        raise ValueError(f"long-format frame is missing columns: {missing}")

    measure_info = measure_info or {}
    has_scenario = "scenario" in df.columns
    has_moe = "moe" in df.columns

    ds = SDCID[f"dataset/{dataset_id}"]
    dsd = SDCID[f"dataset/{dataset_id}/structure"]
    g.add((ds, RDF.type, QB.DataSet))
    g.add((ds, RDFS.label, Literal(label)))
    g.add((ds, QB.structure, dsd))
    g.add((dsd, RDF.type, QB.DataStructureDefinition))

    dimensions = (
        [SDC.refArea, SDC.refPeriod]
        + ([SDC.hourOfDay] if hour_of_day_profile else [])
        + ([SDC.scenario] if has_scenario else [])
        + [QB.measureType]
    )
    for order, dim in enumerate(dimensions, start=1):
        _component(g, dsd, QB.dimension, dim, order=order)
    _component(g, dsd, QB.attribute, SDC.dataMethod, required=True)
    if has_moe:
        _component(g, dsd, QB.attribute, SDC.marginOfError, required=False)
    for measure in sorted(df["measure"].unique()):
        _component(g, dsd, QB.measure, add_measure(g, measure, measure_info.get(measure)))

    seen_regions: set[tuple[str, str]] = set()
    seen_scenarios: set[str] = set()
    for row in df.to_dict("records"):
        geoid, region_type, measure = str(row["geoid"]), row["region_type"], row["measure"]
        if (region_type, geoid) not in seen_regions:
            add_region(g, region_type, geoid)
            seen_regions.add((region_type, geoid))
        hour = None
        if hour_of_day_profile:
            period, hour = hour_of_day_period(row)
        elif year_anchor:
            period = year_anchor_period(row)
        else:
            period = period_literal(row)

        key = [region_type, geoid, str(period)]
        if hour is not None:
            key.append(f"h{hour:02d}")
        if has_scenario:
            key.append(row["scenario"])
        key.append(measure)
        obs = SDCID[f"obs/{dataset_id}/" + "/".join(key)]
        if (obs, RDF.type, QB.Observation) in g:
            raise ValueError(f"duplicate observation key {key} in {dataset_id}")

        m = measure_iri(measure)
        g.add((obs, RDF.type, QB.Observation))
        g.add((obs, QB.dataSet, ds))
        g.add((obs, SDC.refArea, SDCID[f"{region_type}/{geoid}"]))
        g.add((obs, SDC.refPeriod, period))
        if hour is not None:
            g.add((obs, SDC.hourOfDay, Literal(hour, datatype=XSD.integer)))
        g.add((obs, QB.measureType, m))
        if (value := _decimal(row["value"])) is not None:
            g.add((obs, m, Literal(value, datatype=XSD.decimal)))
        g.add((obs, SDC.dataMethod, SDC[f"method-{row['data_method']}"]))
        if has_moe and (moe := _decimal(row["moe"])) is not None:
            g.add((obs, SDC.marginOfError, Literal(moe, datatype=XSD.decimal)))
        if has_scenario:
            if row["scenario"] not in seen_scenarios:
                g.add((ds, PROV.wasDerivedFrom, add_scenario(g, row["scenario"])))
                seen_scenarios.add(row["scenario"])
            g.add((obs, SDC.scenario, scenario_iri(row["scenario"])))
    return ds


def _component(g: Graph, dsd: URIRef, kind: URIRef, prop: URIRef, *, order=None, required=None):
    # Named (not blank) so regenerated files are byte-stable.
    local = re.split(r"[#/]", str(prop))[-1]
    c = URIRef(f"{dsd}/component/{local}")
    g.add((dsd, QB.component, c))
    g.add((c, kind, prop))
    if order is not None:
        g.add((c, QB.order, Literal(order)))
    if required is not None:
        g.add((c, QB.componentRequired, Literal(required)))
