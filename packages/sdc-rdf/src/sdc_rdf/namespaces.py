"""IRI namespaces for Social Data Commons RDF output.

All bases are placeholders under w3id.org/social-data-commons (not registered).
"""

from __future__ import annotations

from rdflib import Graph, Namespace
from rdflib.namespace import DCAT, DCTERMS, ORG, PROV, QB, SKOS

SDC = Namespace("https://w3id.org/social-data-commons/ns#")
"""Core vocabulary (classes, properties, code lists)."""

SDCID = Namespace("https://w3id.org/social-data-commons/id/")
"""Instance data: regions, scenarios, datasets, observations, facilities."""

SDCM = Namespace("https://w3id.org/social-data-commons/measure/")
"""One qb:MeasureProperty per measure_info.json key."""

GEO = Namespace("http://www.opengis.net/ont/geosparql#")


def bind_prefixes(g: Graph, **extra: Namespace) -> Graph:
    """Bind the standard SDC prefixes (plus any ``extra``) on ``g``."""
    for prefix, ns in {
        "sdc": SDC, "sdcid": SDCID, "sdcm": SDCM, "geo": GEO, "qb": QB, "skos": SKOS,
        "prov": PROV, "org": ORG, "dcat": DCAT, "dcterms": DCTERMS, **extra,
    }.items():
        g.bind(prefix, ns)
    return g
