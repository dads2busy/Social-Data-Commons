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

Each dataset records its period convention (sdc:periodConvention), so
``cube_to_long_format`` can rebuild the original frame from the graph alone.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

import pandas as pd
from rdflib import RDF, RDFS, XSD, Graph, Literal, URIRef
from rdflib.namespace import PROV, QB, SKOS

from .namespaces import SDC, SDCID, SDCM
from .points import decimal_literal, integer_literal
from .regions import REGION_CLASSES, add_region

REQUIRED_COLUMNS = ["geoid", "measure", "value", "region_type", "data_method"]

# Column order of the two long-format variants, as written by the pipelines.
STANDARD_COLUMNS = ["geoid", "year", "measure", "value", "moe", "region_type", "data_method"]
ENERGY_COLUMNS = ["geoid", "datetime", "measure", "value", "moe", "region_type", "data_method", "scenario"]

# sdc:periodConvention values: how refPeriod (+ hourOfDay) maps back to year/datetime.
PERIOD_YEAR = SDC["period-year"]
PERIOD_DATETIME = SDC["period-datetime"]
PERIOD_YEAR_ANCHOR = SDC["period-yearAnchor"]
PERIOD_HOUR_OF_DAY = SDC["period-hourOfDayProfile"]

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


def dataset_iri(dataset_id: str) -> URIRef:
    """IRI of the qb:DataSet built from a distribution file stem."""
    return SDCID[f"dataset/{dataset_id}"]


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


def _number(v, integer: bool) -> Literal | None:
    """xsd:integer for integer columns; otherwise a plain-notation xsd:decimal
    ("5e-06" → "0.000005") that is exact for floats. None for missing values."""
    if v is None or pd.isna(v) or str(v).strip() == "":
        return None
    return integer_literal(v) if integer else decimal_literal(v)


def _column(literals: list[Literal | None]) -> list:
    """Python values for a rebuilt column: ints if every literal is xsd:integer, else floats."""
    present = [lit for lit in literals if lit is not None]
    if present and all(lit.datatype == XSD.integer for lit in present) and len(present) == len(literals):
        return [int(lit) for lit in literals]
    return [float(lit.toPython()) if lit is not None else float("nan") for lit in literals]


def long_format_to_cube(
    g: Graph,
    df: pd.DataFrame,
    *,
    dataset_id: str,
    label: str,
    measure_info: Mapping[str, Mapping] | None = None,
    hour_of_day_profile: bool = False,
    year_anchor: bool = False,
    default_scenario: str | None = None,
) -> URIRef:
    """Add one qb:DataSet (with its structure) and one qb:Observation per row of ``df``.

    ``dataset_id`` should be the distribution file stem (e.g.
    ``va_ct_hifld_2026_power_infrastructure``); it scopes the dataset,
    structure and observation IRIs. Set ``hour_of_day_profile`` or ``year_anchor``
    for energy files that follow those conventions (see module docstring).
    ``default_scenario`` marks the scenario a dashboard should show first. Returns
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
    # Integer-typed columns stay xsd:integer so the inverse can restore "24" rather than "24.0".
    integer_value = pd.api.types.is_integer_dtype(df["value"])
    integer_moe = has_moe and pd.api.types.is_integer_dtype(df["moe"])

    ds = dataset_iri(dataset_id)
    dsd = SDCID[f"dataset/{dataset_id}/structure"]
    g.add((ds, RDF.type, QB.DataSet))
    g.add((ds, RDFS.label, Literal(label)))
    g.add((ds, QB.structure, dsd))
    g.add((dsd, RDF.type, QB.DataStructureDefinition))
    if hour_of_day_profile:
        convention = PERIOD_HOUR_OF_DAY
    elif year_anchor:
        convention = PERIOD_YEAR_ANCHOR
    elif "year" in df.columns:
        convention = PERIOD_YEAR
    else:
        convention = PERIOD_DATETIME
    g.add((ds, SDC.periodConvention, convention))
    if default_scenario is not None:
        if not has_scenario or default_scenario not in set(df["scenario"]):
            raise ValueError(f"default_scenario {default_scenario!r} is not in the frame")
        g.add((ds, SDC.defaultScenario, scenario_iri(default_scenario)))

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
        if (value := _number(row["value"], integer_value)) is not None:
            g.add((obs, m, value))
        g.add((obs, SDC.dataMethod, SDC[f"method-{row['data_method']}"]))
        if has_moe and (moe := _number(row["moe"], integer_moe)) is not None:
            g.add((obs, SDC.marginOfError, moe))
        if has_scenario:
            if row["scenario"] not in seen_scenarios:
                g.add((ds, PROV.wasDerivedFrom, add_scenario(g, row["scenario"])))
                seen_scenarios.add(row["scenario"])
            g.add((obs, SDC.scenario, scenario_iri(row["scenario"])))
    return ds


def cube_to_long_format(g: Graph, dataset: URIRef) -> pd.DataFrame:
    """Rebuild the long-format frame a dataset was made from (inverse of ``long_format_to_cube``).

    Columns follow the standard or energy layout depending on the dataset's
    period convention; ``moe`` and ``scenario`` appear when the structure has
    them. Rows are sorted by (geoid, period, scenario, measure).
    """
    convention = g.value(dataset, SDC.periodConvention)
    if convention is None:
        raise ValueError(f"{dataset} has no sdc:periodConvention (regenerate it with sdc-rdf >= 0.4)")
    dsd = g.value(dataset, QB.structure)
    components = {p for c in g.objects(dsd, QB.component) for p in g.objects(c, None)}
    columns = list(STANDARD_COLUMNS if convention == PERIOD_YEAR else ENERGY_COLUMNS)
    if SDC.marginOfError not in components:
        columns.remove("moe")
    if SDC.scenario not in components and "scenario" in columns:
        columns.remove("scenario")

    class_to_region_type = {cls: rt for rt, cls in REGION_CLASSES.items()}
    region_cache: dict[URIRef, tuple[str, str]] = {}
    notation = {}

    def note(iri: URIRef) -> str:
        if iri not in notation:
            notation[iri] = str(g.value(iri, SKOS.notation))
        return notation[iri]

    rows, values, moes = [], [], []
    for obs in g.subjects(QB.dataSet, dataset):
        area = g.value(obs, SDC.refArea)
        if area not in region_cache:
            region_type = next(class_to_region_type[c] for c in g.objects(area, RDF.type)
                               if c in class_to_region_type)
            region_cache[area] = (str(g.value(area, SDC.geoid)), region_type)
        geoid, region_type = region_cache[area]
        measure = g.value(obs, QB.measureType)
        year = str(g.value(obs, SDC.refPeriod))
        if convention == PERIOD_HOUR_OF_DAY:
            period = f"{year}-01-01T{int(g.value(obs, SDC.hourOfDay)):02d}:00:00"
        elif convention == PERIOD_YEAR_ANCHOR:
            period = f"{year}-01-01"
        elif convention == PERIOD_YEAR:
            period = int(year)
        else:
            period = year
        row = {
            "geoid": geoid,
            "year" if convention == PERIOD_YEAR else "datetime": period,
            "measure": note(measure),
            "region_type": region_type,
            "data_method": str(g.value(obs, SDC.dataMethod)).removeprefix(str(SDC["method-"])),
        }
        if "scenario" in columns:
            row["scenario"] = note(g.value(obs, SDC.scenario))
        rows.append(row)
        values.append(g.value(obs, measure))
        moes.append(g.value(obs, SDC.marginOfError))

    # Convert literals before they reach pandas, which would coerce them to plain str.
    for row, value, moe in zip(rows, _column(values), _column(moes)):
        row["value"], row["moe"] = value, moe
    df = pd.DataFrame(rows, columns=columns)
    sort_keys = [c for c in ["geoid", "year", "datetime", "scenario", "measure"] if c in columns]
    return df.sort_values(sort_keys, ignore_index=True)


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
