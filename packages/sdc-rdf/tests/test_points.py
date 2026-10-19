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


def test_assert_same_csv_rows(tmp_path):
    import lzma

    from sdc_rdf import assert_same_csv_rows

    a = tmp_path / "a.csv.xz"
    a.write_bytes(lzma.compress(b"h1,h2\n1,x\n2,y\n"))
    b = tmp_path / "b.csv"
    b.write_text("h1,h2\n2,y\n1,x\n")
    assert_same_csv_rows(a, b)  # row order ignored
    b.write_text("h1,h2\n2,y\n1,z\n")
    with pytest.raises(ValueError, match="2 rows differ"):
        assert_same_csv_rows(a, b)
    b.write_text("h1,h3\n1,x\n2,y\n")
    with pytest.raises(ValueError, match="header"):
        assert_same_csv_rows(a, b)


def test_stage_vocabulary(tmp_path):
    from rdflib import Graph

    from sdc_rdf import stage_vocabulary

    ext = tmp_path / "ext.ttl"
    ext.write_text("@prefix ex: <https://example.org/> . ex:a ex:b ex:c .\n")
    written = stage_vocabulary(tmp_path / "vocab", {"sdc-test.ttl": ext})
    assert sorted(p.name for p in written) == ["sdc-core-shapes.ttl", "sdc-core.ttl", "sdc-test.ttl"]
    for p in written:
        Graph().parse(p)  # each one is valid Turtle
