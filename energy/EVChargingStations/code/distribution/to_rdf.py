"""RDF graph for the EVChargingStations pipeline (simulated VA 2030 inventory).

Each station becomes an sdce:EVChargingStation (ontology in
energy/rdf/ontology.ttl) with one sdce:ChargerGroup per non-zero charger level,
mirroring the point CSV's one-row-per-(station, level) layout. Station IRIs
match the ones EVChargingDemand links its public-station locations to. County
rows become qb:Observations via sdc_rdf, with the static 2030-01-01 datetime
read as the scenario year. Pure functions only. prepare.py does the file I/O.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd
from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV
from sdc_rdf import GEO, SDCID, bind_prefixes, long_format_to_cube, region_iri, scenario_iri

SDCE = Namespace("https://w3id.org/sdc/ns/energy#")

CRS84 = "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>"
STATION_COLUMNS = ["facility_name", "lat", "lon", "geoid"]


def station_iri(station_id: str) -> URIRef:
    """Shared with EVChargingDemand's sdce:atStation links."""
    return SDCID[f"ev-station/{station_id}"]


def charger_level_iri(level: str) -> URIRef:
    return SDCE[f"charger-{level}"]


def add_stations(
    g: Graph,
    points: pd.DataFrame,
    *,
    scenario: URIRef,
    known_levels: set[URIRef],
) -> set[str]:
    """Add station nodes and their charger groups. Returns undeclared charger levels."""
    points = points.assign(station_id=points["station_id"].astype(str))
    if points["facility_id"].astype(str).duplicated().any():
        raise ValueError("duplicate facility_id (station, level) rows in point CSV")
    inconsistent = points.groupby("station_id")[STATION_COLUMNS].nunique().gt(1).any(axis=1)
    if inconsistent.any():
        raise ValueError(f"stations with conflicting name/location/county: {sorted(inconsistent[inconsistent].index)[:5]}")

    for row in points.drop_duplicates("station_id").to_dict("records"):
        sid = row["station_id"]
        st = station_iri(sid)
        g.add((st, RDF.type, SDCE.EVChargingStation))
        g.add((st, DCTERMS.identifier, Literal(sid)))
        g.add((st, RDFS.label, Literal(row["facility_name"])))
        g.add((st, SDCE.inCounty, region_iri("county", str(row["geoid"]))))
        g.add((st, PROV.wasDerivedFrom, scenario))
        geom = SDCID[f"ev-station/{sid}/geometry"]
        g.add((st, GEO.hasGeometry, geom))
        g.add((geom, RDF.type, GEO.Geometry))
        wkt = f"{CRS84} POINT({row['lon']} {row['lat']})"
        g.add((geom, GEO.asWKT, Literal(wkt, datatype=GEO.wktLiteral)))

    unknown: set[str] = set()
    for row in points.to_dict("records"):
        level = row["type"]
        if charger_level_iri(level) not in known_levels:
            unknown.add(level)
        group = SDCID[f"ev-station/{row['station_id']}/chargers/{level}"]
        g.add((station_iri(row["station_id"]), SDCE.hasChargerGroup, group))
        g.add((group, RDF.type, SDCE.ChargerGroup))
        g.add((group, DCTERMS.identifier, Literal(str(row["facility_id"]))))
        g.add((group, SDCE.chargerLevel, charger_level_iri(level)))
        g.add((group, SDCE.chargerCount, Literal(int(row["count"]), datatype=XSD.integer)))
    return unknown


def build_graph(
    points: pd.DataFrame,
    county: pd.DataFrame,
    *,
    ontology: Graph,
    measure_info: Mapping[str, Mapping],
    county_dataset_id: str,
    description: str,
) -> tuple[Graph, set[str]]:
    """Stations + county observations + scenario, as one graph.

    Returns the graph and any charger levels not declared in ``ontology``.
    """
    scenarios = county["scenario"].unique()
    if len(scenarios) != 1:
        raise ValueError(f"expected one station-inventory scenario, found {sorted(scenarios)}")

    g = bind_prefixes(Graph(), sdce=SDCE)
    long_format_to_cube(
        g, county, dataset_id=county_dataset_id,
        label="Simulated EV charging stations, Virginia counties",
        measure_info=measure_info, year_anchor=True,
    )
    scenario = scenario_iri(scenarios[0])
    g.add((scenario, RDFS.label, Literal(f"EV charging station inventory scenario {scenarios[0]}")))
    g.add((scenario, RDFS.comment, Literal(description)))

    known = set(ontology.subjects(RDF.type, SDCE.ChargerLevel))
    unknown = add_stations(g, points, scenario=scenario, known_levels=known)
    return g, unknown
