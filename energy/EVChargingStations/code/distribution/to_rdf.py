"""RDF graph for the EVChargingStations pipeline (simulated VA 2030 inventory).

Each station becomes an sdce:EVChargingStation (ontology in
energy/rdf/ontology.ttl) with one sdce:ChargerGroup per non-zero charger level,
mirroring the point CSV's one-row-per-(station, level) layout. Station IRIs
match the ones EVChargingDemand links its public-station locations to. County
rows become qb:Observations via sdc_rdf, with the static 2030-01-01 datetime
read as the scenario year.

The graph is lossless with respect to both distribution CSVs:
``points_from_graph`` and ``sdc_rdf.cube_to_long_format`` rebuild them. Pure
functions only. prepare.py does the file I/O.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd
from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, SKOS
from sdc_rdf import (
    SDC,
    SDCID,
    add_point_geometry,
    add_region,
    bind_prefixes,
    integer_literal,
    long_format_to_cube,
    point_lat_lon,
    ref_year,
    scenario_iri,
    year_literal,
)

SDCE = Namespace("https://w3id.org/social-data-commons/ns/energy#")

# Columns that describe the station (identical on each of its per-level rows).
STATION_COLUMNS = ["facility_name", "lat", "lon", "geoid", "year", "fuel_type_code"]

# Column order of the point CSV written by ingest.py.
POINT_COLUMNS = [
    "facility_id", "facility_name", "lat", "lon", "year", "type", "count",
    "fuel_type_code", "geoid", "station_id",
]


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
        raise ValueError(f"stations with conflicting attributes across levels: {sorted(inconsistent[inconsistent].index)[:5]}")

    for row in points.drop_duplicates("station_id").to_dict("records"):
        sid = row["station_id"]
        st = station_iri(sid)
        g.add((st, RDF.type, SDCE.EVChargingStation))
        g.add((st, DCTERMS.identifier, Literal(sid)))
        g.add((st, RDFS.label, Literal(row["facility_name"])))
        g.add((st, SDC.refPeriod, year_literal(row["year"])))
        g.add((st, SDCE.fuelTypeCode, Literal(row["fuel_type_code"])))
        g.add((st, SDCE.inCounty, add_region(g, "county", str(row["geoid"]))))
        g.add((st, PROV.wasDerivedFrom, scenario))
        add_point_geometry(g, st, row["lat"], row["lon"])

    unknown: set[str] = set()
    for row in points.to_dict("records"):
        level = row["type"]
        if charger_level_iri(level) not in known_levels:
            unknown.add(level)
        g.add((charger_level_iri(level), SKOS.notation, Literal(level)))  # self-contained inverse
        group = SDCID[f"ev-station/{row['station_id']}/chargers/{level}"]
        g.add((station_iri(row["station_id"]), SDCE.hasChargerGroup, group))
        g.add((group, RDF.type, SDCE.ChargerGroup))
        g.add((group, DCTERMS.identifier, Literal(str(row["facility_id"]))))
        g.add((group, SDCE.chargerLevel, charger_level_iri(level)))
        g.add((group, SDCE.chargerCount, integer_literal(row["count"])))
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


def points_from_graph(g: Graph) -> pd.DataFrame:
    """Rebuild the point CSV frame, one row per charger group (inverse of ``add_stations``).

    Rows are sorted by facility_id.
    """
    rows = []
    for st in g.subjects(SDCE.hasChargerGroup, None, unique=True):
        lat, lon = point_lat_lon(g, st)
        station = {
            "facility_name": str(g.value(st, RDFS.label)),
            "lat": lat,
            "lon": lon,
            "year": ref_year(g, st),
            "fuel_type_code": str(g.value(st, SDCE.fuelTypeCode)),
            "geoid": str(g.value(g.value(st, SDCE.inCounty), SDC.geoid)),
            "station_id": str(g.value(st, DCTERMS.identifier)),
        }
        for group in g.objects(st, SDCE.hasChargerGroup):
            rows.append({
                **station,
                "facility_id": str(g.value(group, DCTERMS.identifier)),
                "type": str(g.value(g.value(group, SDCE.chargerLevel), SKOS.notation)),
                "count": int(g.value(group, SDCE.chargerCount)),
            })
    return pd.DataFrame(rows, columns=POINT_COLUMNS).sort_values("facility_id", ignore_index=True)
