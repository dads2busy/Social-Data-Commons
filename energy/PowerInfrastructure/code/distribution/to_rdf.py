"""RDF graph for the PowerInfrastructure pipeline (HIFLD, VA).

Facility points become sdce:PowerPlant / sdce:Substation nodes (ontology in
../../rdf/ontology.ttl); county rows become qb:Observations via sdc_rdf. Pure
functions only. prepare.py does the file I/O.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from decimal import Decimal

import pandas as pd
from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, ORG, PROV
from sdc_rdf import GEO, SDCID, bind_prefixes, long_format_to_cube, region_iri, scenario_iri

SDCE = Namespace("https://w3id.org/sdc/ns/energy#")

FACILITY_CLASS = {"power_plant": SDCE.PowerPlant, "substation": SDCE.Substation}
MISSING_TEXT = {"", "NOT AVAILABLE"}
CRS84 = "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>"


def _text(v) -> str | None:
    """Trimmed string, or None for NaN / blank / HIFLD 'NOT AVAILABLE'."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)  # numeric IDs read as float
    s = str(v).strip()
    return None if s.upper() in MISSING_TEXT else s


def _decimal(v, *, null_sentinel: float | None = None) -> Decimal | None:
    s = _text(v)
    if s is None:
        return None
    d = Decimal(s)
    return None if null_sentinel is not None and d == Decimal(str(null_sentinel)) else d


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def concept_iri(prefix: str, code: str) -> URIRef:
    """sdce:fuel-NG, sdce:status-IN_SERVICE, ..."""
    return SDCE[f"{prefix}-{code.strip().upper().replace(' ', '_')}"]


def add_facilities(
    g: Graph,
    points: pd.DataFrame,
    *,
    scenario: URIRef,
    known_concepts: set[URIRef],
    null_sentinel: float | None = None,
) -> set[str]:
    """Add one facility node per point row. Returns codes missing from the ontology."""
    unknown: set[str] = set()

    def concept(prefix: str, raw) -> URIRef | None:
        if (code := _text(raw)) is None:
            return None
        iri = concept_iri(prefix, code)
        if iri not in known_concepts:
            unknown.add(f"{prefix}:{code}")
        return iri

    for row in points.to_dict("records"):
        fid = _text(row["facility_id"])
        f = SDCID[f"facility/{fid}"]
        kind = row["type"]
        g.add((f, RDF.type, FACILITY_CLASS[kind]))
        g.add((f, DCTERMS.identifier, Literal(fid)))
        g.add((f, RDFS.label, Literal(_text(row["facility_name"]) or fid)))
        g.add((f, SDCE.inCounty, region_iri("county", _text(row["geoid"]))))
        g.add((f, PROV.wasDerivedFrom, scenario))
        if (sid := _text(row.get("source_id"))) is not None:
            g.add((f, SDCE.sourceId, Literal(sid)))

        geom = SDCID[f"facility/{fid}/geometry"]
        g.add((f, GEO.hasGeometry, geom))
        g.add((geom, RDF.type, GEO.Geometry))
        wkt = f"{CRS84} POINT({row['lon']} {row['lat']})"
        g.add((geom, GEO.asWKT, Literal(wkt, datatype=GEO.wktLiteral)))

        if (status := concept("status", row.get("status"))) is not None:
            g.add((f, SDCE.operatingStatus, status))

        if kind == "power_plant":
            if (fuel := concept("fuel", row.get("plant_source"))) is not None:
                g.add((f, SDCE.primaryFuel, fuel))
            cap = _decimal(row.get("plant_capacity_mw"), null_sentinel=null_sentinel)
            if cap is not None:
                g.add((f, SDCE.operatingCapacityMW, Literal(cap, datatype=XSD.decimal)))
            if (operator := _text(row.get("operator"))) is not None:
                op = SDCID[f"operator/{_slug(operator)}"]
                g.add((f, SDCE.operatedBy, op))
                g.add((op, RDF.type, ORG.Organization))
                g.add((op, RDFS.label, Literal(operator)))
        else:
            kv = _decimal(row.get("max_voltage"), null_sentinel=null_sentinel)
            if kv is not None:
                g.add((f, SDCE.maxVoltageKV, Literal(kv, datatype=XSD.decimal)))
            if (lines := _decimal(row.get("lines"))) is not None:
                g.add((f, SDCE.lineCount, Literal(int(lines), datatype=XSD.integer)))
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
