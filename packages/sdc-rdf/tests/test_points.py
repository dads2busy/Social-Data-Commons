"""Tests for sdc_rdf.points round-trip helpers."""

from __future__ import annotations

import math

import pytest
from rdflib import XSD, Graph, URIRef

from sdc_rdf import (
    add_point_geometry,
    decimal_literal,
    integer_literal,
    is_missing,
    number_value,
    point_lat_lon,
)


def test_geometry_round_trips_full_precision():
    g, f = Graph(), URIRef("https://example.org/f/1")
    add_point_geometry(g, f, 36.685957525459116, -78.36179413976103)
    assert point_lat_lon(g, f) == (36.685957525459116, -78.36179413976103)


@pytest.mark.parametrize("v,lex", [(5e-06, "0.000005"), (1490.3700000000001, "1490.3700000000001"),
                                   (1e16, "10000000000000000"), (3.0, "3.0")])
def test_decimal_literal_plain_and_exact(v, lex):
    lit = decimal_literal(v)
    assert str(lit) == lex and lit.datatype == XSD.decimal and float(lit.toPython()) == v


def test_integer_literal_refuses_fractions():
    assert int(integer_literal(7.0)) == 7
    with pytest.raises(ValueError, match="not integral"):
        integer_literal(2.5)


def test_number_value_and_missing():
    assert number_value(integer_literal(3), integer=True) == 3
    assert number_value(decimal_literal(3.0), integer=False) == 3.0
    assert math.isnan(number_value(None, integer=False))
    assert is_missing(float("nan")) and is_missing("") and is_missing(None) and not is_missing("NOT AVAILABLE")
