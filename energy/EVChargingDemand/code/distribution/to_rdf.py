"""RDF graph for the EVChargingDemand pipeline (simulated VA 2026).

Charging locations become sdce:EVChargingLocation nodes (ontology in
energy/rdf/ontology.ttl), with public-station locations linked to the
EVChargingStations station IRI. County rows become qb:Observations via
sdc_rdf, using the hour-of-day-profile convention (refPeriod = year +
sdc:hourOfDay).

The graph is lossless with respect to both distribution CSVs:
``points_from_graph`` and ``sdc_rdf.cube_to_long_format`` rebuild them (the point
CSV's id_format column always equals type, which is checked on the way in).
Pure functions only. prepare.py does the file I/O.
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
    decimal_literal,
    integer_literal,
    is_missing,
    long_format_to_cube,
    point_lat_lon,
    ref_year,
    scenario_iri,
    year_literal,
)

SDCE = Namespace("https://w3id.org/sdc/ns/energy#")

# Column order of the point CSV written by ingest.py (no geoid: counties come
# from prepare.py's spatial join and are graph-only).
POINT_COLUMNS = [
    "facility_id", "facility_name", "lat", "lon", "year", "type", "id_format",
    "n_hours_active", "total_kwh",
]


def location_iri(charging_station_id: str) -> URIRef:
    return SDCID[f"ev-charging-location/{charging_station_id}"]


def station_iri(station_id: str) -> URIRef:
    """Same IRI the EVChargingStations pipeline uses for a public station."""
    return SDCID[f"ev-station/{station_id}"]


def location_type_iri(location_type: str) -> URIRef:
    return SDCE[f"evloc-{location_type}"]


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
    if (points["id_format"] != points["type"]).any():
        raise ValueError("id_format differs from type; the graph stores type only")
    numeric = points[["total_kwh", "n_hours_active"]]
    if numeric.map(is_missing).any().any():
        raise ValueError("missing total_kwh / n_hours_active in point CSV")
    unknown: set[str] = set()
    for row in points.to_dict("records"):
        lid = str(row["facility_id"])
        loc = location_iri(lid)
        g.add((loc, RDF.type, SDCE.EVChargingLocation))
        g.add((loc, DCTERMS.identifier, Literal(lid)))
        g.add((loc, RDFS.label, Literal(row["facility_name"])))
        g.add((loc, SDC.refPeriod, year_literal(row["year"])))
        g.add((loc, SDCE.inCounty, add_region(g, "county", str(row["geoid"]))))
        g.add((loc, PROV.wasDerivedFrom, scenario))
        add_point_geometry(g, loc, row["lat"], row["lon"])

        loc_type = location_type_iri(row["type"])
        if loc_type not in known_types:
            unknown.add(row["type"])
        g.add((loc_type, SKOS.notation, Literal(row["type"])))  # self-contained inverse
        g.add((loc, SDCE.locationType, loc_type))
        g.add((loc, SDCE.typicalDayEnergyKWh, decimal_literal(row["total_kwh"])))
        g.add((loc, SDCE.activeHours, integer_literal(row["n_hours_active"])))

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


def points_from_graph(g: Graph) -> pd.DataFrame:
    """Rebuild the point CSV frame from the graph (inverse of ``add_locations``).

    Rows are sorted by facility_id. id_format is regenerated from type.
    """
    rows = []
    for loc in g.subjects(RDF.type, SDCE.EVChargingLocation):
        lat, lon = point_lat_lon(g, loc)
        loc_type = str(g.value(g.value(loc, SDCE.locationType), SKOS.notation))
        rows.append({
            "facility_id": str(g.value(loc, DCTERMS.identifier)),
            "facility_name": str(g.value(loc, RDFS.label)),
            "lat": lat,
            "lon": lon,
            "year": ref_year(g, loc),
            "type": loc_type,
            "id_format": loc_type,
            "n_hours_active": int(g.value(loc, SDCE.activeHours)),
            "total_kwh": float(g.value(loc, SDCE.typicalDayEnergyKWh).toPython()),
        })
    return pd.DataFrame(rows, columns=POINT_COLUMNS).sort_values("facility_id", ignore_index=True)
