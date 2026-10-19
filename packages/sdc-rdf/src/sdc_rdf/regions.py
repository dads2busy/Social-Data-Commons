"""Region IRIs and region nodes (counties, tracts, block groups, health districts)."""

from __future__ import annotations

import json
from pathlib import Path

from rdflib import RDF, RDFS, Graph, Literal, URIRef

from .namespaces import SDC, SDCID

REGION_CLASSES = {
    "county": SDC.County,
    "tract": SDC.Tract,
    "block_group": SDC.BlockGroup,
    "health_district": SDC.HealthDistrict,
}


def region_iri(region_type: str, geoid: str) -> URIRef:
    """IRI for a region, e.g. ``region_iri("county", "51001")`` → sdcid:county/51001."""
    if region_type not in REGION_CLASSES:
        raise ValueError(f"unknown region_type {region_type!r}; expected one of {sorted(REGION_CLASSES)}")
    return SDCID[f"{region_type}/{geoid}"]


def add_region(g: Graph, region_type: str, geoid: str, label: str | None = None) -> URIRef:
    """Type a region node and attach its GEOID (and label, if given)."""
    r = region_iri(region_type, geoid)
    g.add((r, RDF.type, REGION_CLASSES[region_type]))
    g.add((r, SDC.geoid, Literal(geoid)))
    if label:
        g.add((r, RDFS.label, Literal(label)))
    return r


def add_region_labels_from_geojson(
    g: Graph, path: str | Path, region_type: str, *, name_property: str = "region_name"
) -> int:
    """Add a region node with an rdfs:label for every feature in a geographies GeoJSON.

    Expects the commons geography schema (``geoid`` + ``region_name`` properties).
    Returns the number of regions added.
    """
    features = json.loads(Path(path).read_text())["features"]
    for feat in features:
        p = feat["properties"]
        add_region(g, region_type, str(p["geoid"]), p.get(name_property))
    return len(features)
