"""RDF graph for the DataCentersProjected pipeline (IM3 CERF, 20 scenarios).

Each projected site becomes an sdce:ProjectedDataCenter tied to its scenario
(ontology in energy/rdf/ontology.ttl); each of the 20 scenarios carries its
growth tier and market-gravity weight. County rows become qb:Observations via
sdc_rdf, with the 2035-01-01 datetime read as the projection year.

The graph is lossless with respect to both distribution CSVs:
``points_from_graph`` and ``sdc_rdf.cube_to_long_format`` rebuild them. Pure
functions only. prepare.py does the file I/O.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal

import pandas as pd
from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, SKOS
from sdc_rdf import (
    GEO,
    SDC,
    SDCID,
    add_region,
    bind_prefixes,
    long_format_to_cube,
    scenario_iri,
)

SDCE = Namespace("https://w3id.org/sdc/ns/energy#")

CRS84 = "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>"
WKT_RE = re.compile(r"POINT\((\S+) (\S+)\)$")
SCENARIO_RE = re.compile(r"^im3_cerf_(low|moderate|high|higher)_(\d+)$")
POINT_TYPE = "projected_data_center"

# Point CSV column → property for the per-site numeric attributes.
NUMERIC_PROPERTIES = {
    "campus_size_square_ft": SDCE.campusAreaSqFt,
    "cooling_energy_demand_mwh": SDCE.coolingEnergyDemandMWh,
    "cooling_water_consumption_mgy": SDCE.coolingWaterConsumptionMGY,
    "cooling_water_demand_mgy": SDCE.coolingWaterDemandMGY,
    "data_center_it_power_mw": SDCE.itPowerMW,
    "mechanical_cooling_frac": SDCE.mechanicalCoolingFraction,
    "normalized_gravity_score": SDCE.normalizedGravityScore,
    "normalized_locational_cost": SDCE.normalizedLocationalCost,
    "total_cost_million_usd": SDCE.siteCostMillionUSD,
    "water_cooling_frac": SDCE.waterCoolingFraction,
    "weighted_siting_score": SDCE.weightedSitingScore,
}

# Column order of the point CSV written by ingest.py.
POINT_COLUMNS = [
    "facility_id", "facility_name", "lat", "lon", "year", "type",
    "campus_size_square_ft", "cooling_energy_demand_mwh", "cooling_water_consumption_mgy",
    "cooling_water_demand_mgy", "data_center_it_power_mw", "geoid", "growth_scenario",
    "market_gravity_weight", "mechanical_cooling_frac", "normalized_gravity_score",
    "normalized_locational_cost", "scenario", "source_id", "total_cost_million_usd",
    "water_cooling_frac", "weighted_siting_score",
]


def site_iri(facility_id: str) -> URIRef:
    return SDCID[f"projected-data-center/{facility_id}"]


def growth_tier_iri(tier: str) -> URIRef:
    return SDCE[f"growth-{tier}"]


def _number(v, integer: bool) -> Literal:
    if integer:
        return Literal(int(v), datatype=XSD.integer)
    # Plain notation: repr() may give "5e-06", which is not a valid xsd:decimal lexical form.
    return Literal(format(Decimal(repr(float(v))), "f"), datatype=XSD.decimal)


def add_scenarios(g: Graph, labels, points: pd.DataFrame) -> None:
    """Scenario nodes with growth tier + gravity weight (parsed from the label, checked
    against the points' growth_scenario / market_gravity_weight columns)."""
    for label in sorted(labels):
        match = SCENARIO_RE.match(label)
        if not match:
            raise ValueError(f"scenario {label!r} is not im3_cerf_<tier>_<weight>")
        tier, weight = match[1], int(match[2])
        rows = points[points["scenario"] == label]
        if not rows.empty and (
            set(rows["growth_scenario"]) != {tier} or set(rows["market_gravity_weight"]) != {weight}
        ):
            raise ValueError(f"points disagree with scenario label {label!r}")
        s = scenario_iri(label)
        g.add((s, RDFS.label, Literal(f"IM3 CERF {tier} growth, market gravity {weight}")))
        g.add((s, SDCE.growthTier, growth_tier_iri(tier)))
        g.add((s, SDCE.marketGravityWeight, Literal(weight, datatype=XSD.integer)))


def add_sites(g: Graph, points: pd.DataFrame) -> None:
    if points["facility_id"].astype(str).duplicated().any():
        raise ValueError("duplicate facility_id in point CSV")
    if set(points["type"]) != {POINT_TYPE}:
        raise ValueError(f"unexpected point types {sorted(set(points['type']) - {POINT_TYPE})}")
    integer_cols = {c for c in NUMERIC_PROPERTIES if pd.api.types.is_integer_dtype(points[c])}

    for row in points.to_dict("records"):
        fid = str(row["facility_id"])
        site = site_iri(fid)
        g.add((site, RDF.type, SDCE.ProjectedDataCenter))
        g.add((site, DCTERMS.identifier, Literal(fid)))
        g.add((site, RDFS.label, Literal(row["facility_name"])))
        g.add((site, SDC.refPeriod, Literal(f"{int(row['year']):04d}", datatype=XSD.gYear)))
        g.add((site, SDC.scenario, scenario_iri(row["scenario"])))
        g.add((site, SDCE.inCounty, add_region(g, "county", str(row["geoid"]))))
        g.add((site, SDCE.sourceId, Literal(str(row["source_id"]))))
        geom = SDCID[f"projected-data-center/{fid}/geometry"]
        g.add((site, GEO.hasGeometry, geom))
        g.add((geom, RDF.type, GEO.Geometry))
        wkt = f"{CRS84} POINT({float(row['lon'])!r} {float(row['lat'])!r})"
        g.add((geom, GEO.asWKT, Literal(wkt, datatype=GEO.wktLiteral)))
        for col, prop in NUMERIC_PROPERTIES.items():
            g.add((site, prop, _number(row[col], col in integer_cols)))


def build_graph(
    points: pd.DataFrame,
    county: pd.DataFrame,
    *,
    measure_info: Mapping[str, Mapping],
    county_dataset_id: str,
    default_scenario: str,
) -> Graph:
    """Projected sites + per-scenario county observations + the 20 scenarios, as one graph."""
    g = bind_prefixes(Graph(), sdce=SDCE)
    long_format_to_cube(
        g, county, dataset_id=county_dataset_id,
        label="Projected data centers (IM3 CERF, 2035), Virginia counties",
        measure_info=measure_info, year_anchor=True, default_scenario=default_scenario,
    )
    add_scenarios(g, set(county["scenario"]) | set(points["scenario"]), points)
    add_sites(g, points)
    return g


def points_from_graph(g: Graph) -> pd.DataFrame:
    """Rebuild the point CSV frame from the graph (inverse of ``add_sites``).

    Rows are sorted by facility_id; integer-typed literals come back as ints.
    """
    scenario_cache: dict[URIRef, tuple[str, str, int]] = {}
    rows = []
    for site in g.subjects(RDF.type, SDCE.ProjectedDataCenter):
        scen = g.value(site, SDC.scenario)
        if scen not in scenario_cache:
            tier = g.value(scen, SDCE.growthTier)
            scenario_cache[scen] = (
                str(g.value(scen, SKOS.notation)),
                str(tier).removeprefix(str(SDCE["growth-"])),
                int(g.value(scen, SDCE.marketGravityWeight)),
            )
        label, tier, weight = scenario_cache[scen]
        lon, lat = WKT_RE.search(str(g.value(g.value(site, GEO.hasGeometry), GEO.asWKT))).groups()
        row = {
            "facility_id": str(g.value(site, DCTERMS.identifier)),
            "facility_name": str(g.value(site, RDFS.label)),
            "lat": float(lat),
            "lon": float(lon),
            "year": int(str(g.value(site, SDC.refPeriod))),
            "type": POINT_TYPE,
            "geoid": str(g.value(g.value(site, SDCE.inCounty), SDC.geoid)),
            "growth_scenario": tier,
            "market_gravity_weight": weight,
            "scenario": label,
            "source_id": str(g.value(site, SDCE.sourceId)),
        }
        for col, prop in NUMERIC_PROPERTIES.items():
            lit = g.value(site, prop)
            row[col] = int(lit) if lit.datatype == XSD.integer else float(lit.toPython())
        rows.append(row)
    return pd.DataFrame(rows, columns=POINT_COLUMNS).sort_values("facility_id", ignore_index=True)
