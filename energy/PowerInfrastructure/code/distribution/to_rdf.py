"""RDF graph for the PowerInfrastructure pipeline (HIFLD, VA).

Facility points become sdce:PowerPlant / sdce:Substation nodes (ontology in
energy/rdf/ontology.ttl); county rows become qb:Observations via sdc_rdf.

The graph is lossless with respect to both distribution CSVs:
``points_from_graph`` and ``sdc_rdf.cube_to_long_format`` rebuild them. Blank
cells are absent; HIFLD's own "NOT AVAILABLE" codes are kept as concepts (fuel,
status) or verbatim text (operator). Pure functions only. prepare.py does the
file I/O.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

import pandas as pd
from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, ORG, PROV, SKOS
from sdc_rdf import (
    SDC,
    SDCID,
    add_point_geometry,
    add_region,
    bind_prefixes,
    decimal_literal,
    integer_literal,
    is_missing,
    long_format_to_cube,
    number_value,
    point_lat_lon,
    ref_year,
    scenario_iri,
    year_literal,
)

SDCE = Namespace("https://w3id.org/social-data-commons/ns/energy#")

FACILITY_CLASS = {"power_plant": SDCE.PowerPlant, "substation": SDCE.Substation}
NOT_AVAILABLE = "NOT AVAILABLE"

# Column order of the point CSV written by ingest.py.
POINT_COLUMNS = [
    "facility_id", "facility_name", "lat", "lon", "year", "type", "geoid", "lines",
    "max_voltage", "operator", "plant_capacity_mw", "plant_source", "source_id", "status",
]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def facility_iri(facility_id: str) -> URIRef:
    return SDCID[f"facility/{facility_id}"]


def concept_iri(prefix: str, code: str) -> URIRef:
    """sdce:fuel-NG, sdce:status-IN_SERVICE, sdce:status-NOT_AVAILABLE, ..."""
    return SDCE[f"{prefix}-{code.upper().replace(' ', '_')}"]


def add_facilities(
    g: Graph,
    points: pd.DataFrame,
    *,
    scenario: URIRef,
    known_concepts: set[URIRef],
    null_sentinel: float | None = None,
) -> set[str]:
    """Add one facility node per point row. Returns codes missing from the ontology.

    Expects ``sdc_rdf.read_csv_exact`` input. ``null_sentinel`` (HIFLD's -999999)
    must already have been mapped to blank by ingest; finding it is an error.
    """
    if points["facility_id"].duplicated().any():
        raise ValueError("duplicate facility_id in point CSV")
    if null_sentinel is not None:
        numeric = points[["lines", "max_voltage", "plant_capacity_mw"]]
        if (numeric == null_sentinel).any().any():
            raise ValueError(f"HIFLD null sentinel {null_sentinel} reached the point CSV")
    unknown: set[str] = set()

    def concept(prefix: str, code) -> URIRef | None:
        if is_missing(code):
            return None
        iri = concept_iri(prefix, code)
        if iri not in known_concepts:
            unknown.add(f"{prefix}:{code}")
        g.add((iri, SKOS.notation, Literal(code)))  # keeps the data graph self-contained
        return iri

    for row in points.to_dict("records"):
        fid, kind = row["facility_id"], row["type"]
        f = facility_iri(fid)
        g.add((f, RDF.type, FACILITY_CLASS[kind]))
        g.add((f, DCTERMS.identifier, Literal(fid)))
        g.add((f, RDFS.label, Literal(row["facility_name"])))
        g.add((f, SDC.refPeriod, year_literal(row["year"])))
        g.add((f, SDCE.inCounty, add_region(g, "county", row["geoid"])))
        g.add((f, SDCE.sourceId, Literal(row["source_id"])))
        g.add((f, PROV.wasDerivedFrom, scenario))
        add_point_geometry(g, f, row["lat"], row["lon"])

        if (status := concept("status", row["status"])) is not None:
            g.add((f, SDCE.operatingStatus, status))
        if (fuel := concept("fuel", row["plant_source"])) is not None:
            g.add((f, SDCE.primaryFuel, fuel))
        if not is_missing(row["plant_capacity_mw"]):
            g.add((f, SDCE.operatingCapacityMW, decimal_literal(row["plant_capacity_mw"])))
        if not is_missing(row["max_voltage"]):
            g.add((f, SDCE.maxVoltageKV, decimal_literal(row["max_voltage"])))
        if not is_missing(row["lines"]):
            g.add((f, SDCE.lineCount, integer_literal(row["lines"])))
        if not is_missing(operator := row["operator"]):
            g.add((f, SDCE.operatorName, Literal(operator)))
            if operator != NOT_AVAILABLE:
                op = SDCID[f"operator/{_slug(operator)}"]
                g.add((f, SDCE.operatedBy, op))
                g.add((op, RDF.type, ORG.Organization))
                g.add((op, RDFS.label, Literal(operator)))
    return unknown


def build_graph(
    points: pd.DataFrame,
    county: pd.DataFrame,
    *,
    ontology: Graph,
    measure_info: Mapping[str, Mapping],
    county_dataset_id: str,
    layer_urls: list[str],
    null_sentinel: float | None = None,
) -> tuple[Graph, set[str]]:
    """Facilities + county observations + snapshot provenance, as one graph.

    ``ontology`` is the energy extension; its code lists decide which fuel and
    status codes count as known. Returns the graph and any unknown codes.
    """
    snapshots = county[["scenario", "datetime"]].drop_duplicates()
    if len(snapshots) != 1:
        raise ValueError(f"expected one HIFLD snapshot, found {snapshots.to_dict('records')}")
    label, period = snapshots.iloc[0]

    g = bind_prefixes(Graph(), sdce=SDCE)
    long_format_to_cube(
        g, county, dataset_id=county_dataset_id,
        label="HIFLD power infrastructure, Virginia counties", measure_info=measure_info,
    )
    scenario = scenario_iri(label)
    g.add((scenario, RDFS.label, Literal(f"HIFLD snapshot {period}")))
    g.add((scenario, PROV.generatedAtTime, Literal(period, datatype=XSD.date)))
    for url in layer_urls:
        g.add((scenario, PROV.wasDerivedFrom, URIRef(url)))

    known = set(ontology.subjects(RDF.type, SDCE.EnergySource)) | set(
        ontology.subjects(RDF.type, SDCE.OperatingStatus)
    )
    unknown = add_facilities(
        g, points, scenario=scenario, known_concepts=known, null_sentinel=null_sentinel
    )
    return g, unknown


def points_from_graph(g: Graph) -> pd.DataFrame:
    """Rebuild the point CSV frame from the graph (inverse of ``add_facilities``).

    Rows are sorted by facility_id; blank cells come back as NaN.
    """
    type_of = {cls: kind for kind, cls in FACILITY_CLASS.items()}
    rows = []
    for kind_cls, kind in type_of.items():
        for f in g.subjects(RDF.type, kind_cls):
            lat, lon = point_lat_lon(g, f)

            def text(pred):
                v = g.value(f, pred)
                return str(v) if v is not None else float("nan")

            def code(pred):
                c = g.value(f, pred)
                return str(g.value(c, SKOS.notation)) if c is not None else float("nan")

            rows.append({
                "facility_id": str(g.value(f, DCTERMS.identifier)),
                "facility_name": str(g.value(f, RDFS.label)),
                "lat": lat,
                "lon": lon,
                "year": ref_year(g, f),
                "type": kind,
                "geoid": str(g.value(g.value(f, SDCE.inCounty), SDC.geoid)),
                "lines": number_value(g.value(f, SDCE.lineCount), integer=False),
                "max_voltage": number_value(g.value(f, SDCE.maxVoltageKV), integer=False),
                "operator": text(SDCE.operatorName),
                "plant_capacity_mw": number_value(g.value(f, SDCE.operatingCapacityMW), integer=False),
                "plant_source": code(SDCE.primaryFuel),
                "source_id": str(g.value(f, SDCE.sourceId)),
                "status": code(SDCE.operatingStatus),
            })
    return pd.DataFrame(rows, columns=POINT_COLUMNS).sort_values("facility_id", ignore_index=True)
