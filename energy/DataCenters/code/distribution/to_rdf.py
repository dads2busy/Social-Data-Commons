"""RDF graph for the DataCenters pipeline (IM3 Open Source Data Center Atlas, VA).

Each point-CSV row becomes an sdce:DataCenterRecord (ontology in
energy/rdf/ontology.ttl): one OSM-derived point, building or campus record, of
which a facility may have several. County rows become qb:Observations via
sdc_rdf, with the atlas snapshot date as the reference period.

The graph is lossless with respect to both distribution CSVs:
``points_from_graph`` and ``sdc_rdf.cube_to_long_format`` rebuild them. The
point CSV's state_abb is always "VA" (checked on the way in, regenerated on the
way out). Pure functions only. prepare.py does the file I/O.
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
    is_missing,
    long_format_to_cube,
    number_value,
    point_lat_lon,
    ref_year,
    scenario_iri,
    year_literal,
)

SDCE = Namespace("https://w3id.org/social-data-commons/ns/energy#")

STATE_ABB = "VA"

# Column order of the point CSV written by ingest.py.
POINT_COLUMNS = [
    "facility_id", "facility_name", "lat", "lon", "year", "type", "county_id",
    "operator", "source_id", "sqft", "state_abb",
]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def record_iri(facility_id: str) -> URIRef:
    return SDCID[f"data-center-record/{facility_id}"]


def record_type_iri(record_type: str) -> URIRef:
    return SDCE[f"dcrecord-{record_type}"]


def add_records(
    g: Graph,
    points: pd.DataFrame,
    *,
    scenario: URIRef,
    known_types: set[URIRef],
) -> set[str]:
    """Add one sdce:DataCenterRecord per point row. Returns undeclared record types.

    Expects ``sdc_rdf.read_csv_exact`` input.
    """
    if points["facility_id"].duplicated().any():
        raise ValueError("duplicate facility_id in point CSV")
    if set(points["state_abb"]) != {STATE_ABB}:
        raise ValueError(f"state_abb other than {STATE_ABB!r}; the graph regenerates it as a constant")
    unknown: set[str] = set()
    for row in points.to_dict("records"):
        fid = row["facility_id"]
        rec = record_iri(fid)
        g.add((rec, RDF.type, SDCE.DataCenterRecord))
        g.add((rec, DCTERMS.identifier, Literal(fid)))
        g.add((rec, RDFS.label, Literal(row["facility_name"])))
        g.add((rec, SDC.refPeriod, year_literal(row["year"])))
        g.add((rec, SDCE.inCounty, add_region(g, "county", str(row["county_id"]))))
        g.add((rec, SDCE.sourceId, Literal(row["source_id"])))
        g.add((rec, PROV.wasDerivedFrom, scenario))
        add_point_geometry(g, rec, row["lat"], row["lon"])

        rtype = record_type_iri(row["type"])
        if rtype not in known_types:
            unknown.add(row["type"])
        g.add((rtype, SKOS.notation, Literal(row["type"])))  # self-contained inverse
        g.add((rec, SDCE.recordType, rtype))

        if not is_missing(row["sqft"]):
            g.add((rec, SDCE.facilityAreaSqFt, decimal_literal(row["sqft"])))
        if not is_missing(operator := row["operator"]):
            g.add((rec, SDCE.operatorName, Literal(operator)))
            org = SDCID[f"operator/{_slug(operator)}"]
            g.add((rec, SDCE.operatedBy, org))
            g.add((org, RDF.type, ORG.Organization))
            g.add((org, RDFS.label, Literal(operator)))
    return unknown


def build_graph(
    points: pd.DataFrame,
    county: pd.DataFrame,
    *,
    ontology: Graph,
    measure_info: Mapping[str, Mapping],
    county_dataset_id: str,
    source_url: str | None = None,
) -> tuple[Graph, set[str]]:
    """Data center records + county observations + atlas snapshot, as one graph.

    Returns the graph and any record types not declared in ``ontology``.
    """
    snapshots = county[["scenario", "datetime"]].drop_duplicates()
    if len(snapshots) != 1:
        raise ValueError(f"expected one atlas snapshot, found {snapshots.to_dict('records')}")
    label, period = snapshots.iloc[0]

    g = bind_prefixes(Graph(), sdce=SDCE)
    long_format_to_cube(
        g, county, dataset_id=county_dataset_id,
        label="Existing data centers (IM3 atlas), Virginia counties", measure_info=measure_info,
    )
    scenario = scenario_iri(label)
    g.add((scenario, RDFS.label, Literal(f"IM3 Open Source Data Center Atlas snapshot {period}")))
    g.add((scenario, PROV.generatedAtTime, Literal(period, datatype=XSD.date)))
    if source_url:
        g.add((scenario, PROV.wasDerivedFrom, URIRef(source_url)))

    known = set(ontology.subjects(RDF.type, SDCE.DataCenterRecordType))
    unknown = add_records(g, points, scenario=scenario, known_types=known)
    return g, unknown


def points_from_graph(g: Graph) -> pd.DataFrame:
    """Rebuild the point CSV frame from the graph (inverse of ``add_records``).

    Rows are sorted by facility_id; blank cells come back as NaN.
    """
    rows = []
    for rec in g.subjects(RDF.type, SDCE.DataCenterRecord):
        lat, lon = point_lat_lon(g, rec)
        operator = g.value(rec, SDCE.operatorName)
        rows.append({
            "facility_id": str(g.value(rec, DCTERMS.identifier)),
            "facility_name": str(g.value(rec, RDFS.label)),
            "lat": lat,
            "lon": lon,
            "year": ref_year(g, rec),
            "type": str(g.value(g.value(rec, SDCE.recordType), SKOS.notation)),
            "county_id": int(str(g.value(g.value(rec, SDCE.inCounty), SDC.geoid))),
            "operator": str(operator) if operator is not None else float("nan"),
            "source_id": str(g.value(rec, SDCE.sourceId)),
            "sqft": number_value(g.value(rec, SDCE.facilityAreaSqFt), integer=False),
            "state_abb": STATE_ABB,
        })
    return pd.DataFrame(rows, columns=POINT_COLUMNS).sort_values("facility_id", ignore_index=True)
