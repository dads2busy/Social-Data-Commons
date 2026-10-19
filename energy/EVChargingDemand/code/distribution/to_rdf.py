"""RDF graph for the EVChargingDemand pipeline (simulated VA 2026).

Charging locations become sdce:EVChargingLocation nodes (ontology in
energy/rdf/ontology.ttl), with public-station locations linked to the
EVChargingStations station IRI. County rows become qb:Observations via
sdc_rdf, using the hour-of-day-profile convention (refPeriod = year +
sdc:hourOfDay). Pure functions only. prepare.py does the file I/O.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from decimal import Decimal

import pandas as pd
from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV
from sdc_rdf import GEO, SDCID, bind_prefixes, long_format_to_cube, region_iri, scenario_iri

SDCE = Namespace("https://w3id.org/sdc/ns/energy#")

CRS84 = "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>"


def location_iri(charging_station_id: str) -> URIRef:
    return SDCID[f"ev-charging-location/{charging_station_id}"]


def station_iri(station_id: str) -> URIRef:
    """Same IRI the EVChargingStations pipeline uses for a public station."""
    return SDCID[f"ev-station/{station_id}"]


def location_type_iri(location_type: str) -> URIRef:
    return SDCE[f"evloc-{location_type}"]


def _decimal(v) -> Decimal:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        raise ValueError("missing numeric value in point row")
    return Decimal(str(v))


def add_locations(
    g: Graph,
    points: pd.DataFrame,
    *,
    scenario: URIRef,
    known_types: set[URIRef],
) -> set[str]:
    """Add one sdce:EVChargingLocation per point row (needs a ``geoid`` column).

    Returns location types missing from the ontology.
    """
    unknown: set[str] = set()
    for row in points.to_dict("records"):
        lid = str(row["facility_id"])
        loc = location_iri(lid)
        g.add((loc, RDF.type, SDCE.EVChargingLocation))
        g.add((loc, DCTERMS.identifier, Literal(lid)))
        g.add((loc, RDFS.label, Literal(row["facility_name"])))
        g.add((loc, SDCE.inCounty, region_iri("county", str(row["geoid"]))))
        g.add((loc, PROV.wasDerivedFrom, scenario))

        geom = SDCID[f"ev-charging-location/{lid}/geometry"]
        g.add((loc, GEO.hasGeometry, geom))
        g.add((geom, RDF.type, GEO.Geometry))
        wkt = f"{CRS84} POINT({row['lon']} {row['lat']})"
        g.add((geom, GEO.asWKT, Literal(wkt, datatype=GEO.wktLiteral)))

        loc_type = location_type_iri(row["type"])
        if loc_type not in known_types:
            unknown.add(row["type"])
        g.add((loc, SDCE.locationType, loc_type))
        g.add((loc, SDCE.typicalDayEnergyKWh, Literal(_decimal(row["total_kwh"]), datatype=XSD.decimal)))
        g.add((loc, SDCE.activeHours, Literal(int(row["n_hours_active"]), datatype=XSD.integer)))

        if row["type"] == "public_station":
            # Public-station IDs are the EVChargingStations station_id (va_<n>_existing).
            st = station_iri(lid)
            g.add((loc, SDCE.atStation, st))
            g.add((st, RDF.type, SDCE.EVChargingStation))
            g.add((st, DCTERMS.identifier, Literal(lid)))
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
    """Charging locations + hourly county observations + scenario, as one graph.

    ``points`` must already carry a ``geoid`` column (see prepare.py). Returns
    the graph and any location types not declared in ``ontology``.
    """
    scenarios = county["scenario"].unique()
    if len(scenarios) != 1:
        raise ValueError(f"expected one EV demand scenario, found {sorted(scenarios)}")
    dupes = points["facility_id"].astype(str).duplicated()
    if dupes.any():
        raise ValueError(f"duplicate charging location ids: {sorted(points.loc[dupes, 'facility_id'].astype(str))[:5]}")
    if points["geoid"].isna().any():
        raise ValueError(f"{points['geoid'].isna().sum()} charging locations have no county")

    g = bind_prefixes(Graph(), sdce=SDCE)
    long_format_to_cube(
        g, county, dataset_id=county_dataset_id,
        label="Simulated EV charging demand, Virginia counties, typical-day hourly profile",
        measure_info=measure_info, hour_of_day_profile=True,
    )
    scenario = scenario_iri(scenarios[0])
    g.add((scenario, RDFS.label, Literal(f"EV charging demand scenario {scenarios[0]}")))
    g.add((scenario, RDFS.comment, Literal(description)))

    known = set(ontology.subjects(RDF.type, SDCE.EVLocationType))
    unknown = add_locations(g, points, scenario=scenario, known_types=known)
    return g, unknown
