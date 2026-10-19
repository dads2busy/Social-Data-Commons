"""Tests for sdc_rdf.cube (long-format → RDF Data Cube)."""

from __future__ import annotations

import pandas as pd
import pytest
from pyshacl import validate
from rdflib import RDF, XSD, Graph, Literal
from rdflib.namespace import QB, SKOS

from sdc_rdf import (
    SDC,
    SDCID,
    load_core_ontology,
    load_core_shapes,
    long_format_to_cube,
    measure_iri,
)

STANDARD = pd.DataFrame(
    {
        "geoid": ["51001", "51001", "51003"],
        "year": [2022, 2023, 2023],
        "measure": ["pop_total"] * 3,
        "value": [33000.0, 33100.0, 112000.0],
        "moe": [pd.NA, 120.0, pd.NA],
        "region_type": ["county"] * 3,
        "data_method": ["observed"] * 3,
    }
)

ENERGY = pd.DataFrame(
    {
        "geoid": ["51001", "51001"],
        "datetime": ["2026-05-29", "2026-05-29 13:00:00"],
        "measure": ["plant_count", "demand_kwh"],
        "value": [3.0, 12.5],
        "moe": [pd.NA, pd.NA],
        "region_type": ["county", "county"],
        "data_method": ["observed", "simulated"],
        "scenario": ["snap_a", "run_b"],
    }
)


def build(df: pd.DataFrame, **kw) -> Graph:
    g = Graph()
    long_format_to_cube(g, df, dataset_id="test_ds", label="Test", **kw)
    return g


def conforms(g: Graph) -> bool:
    ok, _, report = validate(g + load_core_ontology(), shacl_graph=load_core_shapes())
    assert ok, report
    return ok


def test_standard_format_one_observation_per_row():
    g = build(STANDARD)
    assert len(list(g.subjects(RDF.type, QB.Observation))) == 3
    obs = SDCID["obs/test_ds/county/51001/2023/pop_total"]
    assert (obs, SDC.refPeriod, Literal("2023", datatype=XSD.gYear)) in g
    assert (obs, measure_iri("pop_total"), Literal("33100.0", datatype=XSD.decimal)) in g
    assert conforms(g)


def test_missing_moe_is_omitted():
    g = build(STANDARD)
    obs = SDCID["obs/test_ds/county/51001/2022/pop_total"]
    assert g.value(obs, SDC.marginOfError) is None
    assert g.value(SDCID["obs/test_ds/county/51001/2023/pop_total"], SDC.marginOfError) is not None


def test_energy_format_dates_and_scenarios():
    g = build(ENERGY)
    periods = set(g.objects(None, SDC.refPeriod))
    assert Literal("2026-05-29", datatype=XSD.date) in periods
    assert Literal("2026-05-29T13:00:00", datatype=XSD.dateTime) in periods
    assert (SDCID["scenario/snap_a"], RDF.type, SDC.Scenario) in g
    assert conforms(g)


def test_measure_info_text_attached():
    info = {"pop_total": {"short_description": "Total population.", "unit": "person"}}
    g = build(STANDARD, measure_info=info)
    m = measure_iri("pop_total")
    assert g.value(m, SKOS.notation) == Literal("pop_total")
    assert str(g.value(m, SDC.unit)) == "person"


def test_duplicate_keys_rejected():
    with pytest.raises(ValueError, match="duplicate observation"):
        build(pd.concat([STANDARD, STANDARD.iloc[[0]]]))


def test_missing_columns_rejected():
    with pytest.raises(ValueError, match="missing columns"):
        build(STANDARD.drop(columns=["year", "data_method"]))


def test_unknown_region_type_rejected():
    with pytest.raises(ValueError, match="unknown region_type"):
        build(STANDARD.assign(region_type="zcta"))


def test_every_data_method_is_declared():
    ont = load_core_ontology()
    for method in ["observed", "modeled", "simulated", "scaled", "interpolated", "extrapolated"]:
        assert (SDC[f"method-{method}"], RDF.type, SDC.DataMethod) in ont


def test_turtle_xz_round_trip(tmp_path):
    from sdc_rdf import read_turtle, write_turtle

    g = build(STANDARD)
    out = write_turtle(g, tmp_path / "graph.ttl.xz")
    assert out.read_bytes()[:6] == b"\xfd7zXZ\x00"  # xz magic
    assert len(read_turtle(out)) == len(g)
