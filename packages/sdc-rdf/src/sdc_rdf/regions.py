"""Region IRIs and region nodes (counties, tracts, block groups, health districts).

Regions are 2020 Census geographies unless a vintage is given: a 2010 tract is
``sdcid:tract-2010/{geoid}`` with ``sdc:vintage "2010"``, so the same GEOID in
two vintages never names the same node.
"""

from __future__ import annotations

import json
from pathlib import Path

from rdflib import RDF, RDFS, XSD, Graph, Literal, URIRef

from .namespaces import SDC, SDCID

REGION_CLASSES = {
    "county": SDC.County,
    "tract": SDC.Tract,
    "block_group": SDC.BlockGroup,
    "health_district": SDC.HealthDistrict,
}


DEFAULT_VINTAGE = 2020


def region_iri(region_type: str, geoid: str, vintage: int | None = None) -> URIRef:
    """IRI for a region, e.g. ``region_iri("county", "51001")`` → sdcid:county/51001.

    A non-2020 ``vintage`` qualifies the IRI: ``region_iri("tract", g, 2010)`` →
    sdcid:tract-2010/{g}.
    """
    if region_type not in REGION_CLASSES:
        raise ValueError(f"unknown region_type {region_type!r}; expected one of {sorted(REGION_CLASSES)}")
    if vintage is None or vintage == DEFAULT_VINTAGE:
        return SDCID[f"{region_type}/{geoid}"]
    return SDCID[f"{region_type}-{vintage}/{geoid}"]


def add_region(
    g: Graph, region_type: str, geoid: str, label: str | None = None, *, vintage: int | None = None
) -> URIRef:
    """Type a region node and attach its GEOID (label and non-2020 vintage, if given)."""
    r = region_iri(region_type, geoid, vintage)
    g.add((r, RDF.type, REGION_CLASSES[region_type]))
    g.add((r, SDC.geoid, Literal(geoid)))
    if vintage is not None and vintage != DEFAULT_VINTAGE:
        g.add((r, SDC.vintage, Literal(f"{vintage:04d}", datatype=XSD.gYear)))
    if label:
        g.add((r, RDFS.label, Literal(label)))
    return r


def add_region_labels_from_geojson(
    g: Graph,
    path: str | Path,
    region_type: str,
    *,
    name_property: str = "region_name",
    vintage: int | None = None,
) -> int:
    """Add a region node with an rdfs:label for every feature in a geographies GeoJSON.

    Expects the commons geography schema (``geoid`` + ``region_name`` properties).
    Returns the number of regions added.
    """
    features = json.loads(Path(path).read_text())["features"]
    for feat in features:
        p = feat["properties"]
        add_region(g, region_type, str(p["geoid"]), p.get(name_property), vintage=vintage)
    return len(features)
