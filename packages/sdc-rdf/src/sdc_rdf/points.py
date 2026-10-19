"""Helpers for point entities (facilities, sites, stations) that must round-trip.

Point graphs are meant to regenerate their point CSVs exactly, so geometry and
numbers are written in forms that parse back to the same floats.
"""

from __future__ import annotations

import math
import re
from decimal import Decimal

from rdflib import RDF, XSD, Graph, Literal, URIRef

from .namespaces import GEO, SDC

CRS84 = "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>"
WKT_POINT_RE = re.compile(r"POINT\((\S+) (\S+)\)$")


def is_missing(v) -> bool:
    """True for None, NaN and blank strings (the CSV's empty cells)."""
    return v is None or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, str) and v == "")


def decimal_literal(v) -> Literal:
    """Exact, plain-notation xsd:decimal ("5e-06" → "0.000005"; exponents are not valid xsd:decimal)."""
    d = Decimal(repr(float(v))) if isinstance(v, float) else Decimal(str(v))
    return Literal(format(d, "f"), datatype=XSD.decimal)


def integer_literal(v) -> Literal:
    """xsd:integer; refuses non-integral values instead of truncating them."""
    if float(v) != int(float(v)):
        raise ValueError(f"{v!r} is not integral")
    return Literal(int(float(v)), datatype=XSD.integer)


def year_literal(year) -> Literal:
    return Literal(f"{int(year):04d}", datatype=XSD.gYear)


def add_point_geometry(g: Graph, feature: URIRef, lat, lon) -> URIRef:
    """Attach ``{feature}/geometry`` with a CRS84 WKT point that round-trips exactly."""
    geom = URIRef(f"{feature}/geometry")
    g.add((feature, GEO.hasGeometry, geom))
    g.add((geom, RDF.type, GEO.Geometry))
    wkt = f"{CRS84} POINT({float(lon)!r} {float(lat)!r})"
    g.add((geom, GEO.asWKT, Literal(wkt, datatype=GEO.wktLiteral)))
    return geom


def point_lat_lon(g: Graph, feature: URIRef) -> tuple[float, float]:
    """(lat, lon) of a feature's WKT point (inverse of ``add_point_geometry``)."""
    wkt = str(g.value(g.value(feature, GEO.hasGeometry), GEO.asWKT))
    lon, lat = WKT_POINT_RE.search(wkt).groups()
    return float(lat), float(lon)


def ref_year(g: Graph, entity: URIRef) -> int:
    return int(str(g.value(entity, SDC.refPeriod)))


def number_value(lit: Literal | None, *, integer: bool):
    """Python value of a numeric literal for a CSV column: int, float, or NaN when absent."""
    if lit is None:
        return float("nan")
    return int(lit) if integer else float(lit.toPython())
