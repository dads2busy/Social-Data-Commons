"""Tests for the ResidentialEnergyScenario RDF graph (to_rdf.py), including the lossless round trip."""

from __future__ import annotations

import json
import lzma
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml
from pyshacl import validate
from rdflib import RDF, XSD, Graph, Literal
from rdflib.namespace import QB
from sdc_core.io import write_data
from sdc_rdf import SDC, SDCID, SDCM, dataset_iri, load_core_ontology, load_core_shapes, read_csv_exact, read_graph

sys.path.insert(0, str(Path(__file__).resolve().parent))
from to_rdf import build_graph, long_format_from_graph

TOPIC_DIR = Path(__file__).resolve().parents[2]
CONFIG = yaml.safe_load((TOPIC_DIR / "pipeline.yaml").read_text())
NAN = float("nan")

COMBINED = pd.DataFrame(
    {
        "geoid": ["51001", "51001090100", "51001090200", "51001", "51001090100", "51001090100"],
        "datetime": ["2030-01-01"] * 3 + ["2030-01-01T12:00:00", "2030-01-01T12:00:00", "2030-01-01T13:00:00"],
        "measure": ["synthetic_household_count"] * 3 + ["pv_generation_kwh"] * 3,
        "value": [300.0, 120.0, 180.0, 55.5, 20.25, 5e-06],
        "moe": [NAN] * 6,
        "region_type": ["county", "tract", "tract", "county", "tract", "tract"],
        "data_method": ["simulated"] * 6,
        "scenario": ["va_2030_solar_324k_0_25ev"] * 6,
    }
)


def build(df=COMBINED, vintage=2010):
    return build_graph(df, measure_info={}, dataset_stem="test", tract_vintage=vintage, description="d")


def conforms(g: Graph) -> tuple[bool, str]:
    ok, _, report = validate(g + load_core_ontology(), shacl_graph=load_core_shapes())
    return ok, report


def test_synthetic_graph_conforms():
    ok, report = conforms(build())
    assert ok, report


def test_static_and_hourly_become_separate_datasets():
    g = build()
    static, hourly = dataset_iri("test/static"), dataset_iri("test/hourly")
    assert len(list(g.subjects(QB.dataSet, static))) == 3
    assert len(list(g.subjects(QB.dataSet, hourly))) == 3
    assert g.value(static, SDC.periodConvention) == SDC["period-yearAnchor"]
    assert g.value(hourly, SDC.periodConvention) == SDC["period-hourOfDayProfile"]


def test_tracts_are_2010_vintage_counties_are_not():
    g = build()
    t = SDCID["tract-2010/51001090100"]
    assert (t, RDF.type, SDC.Tract) in g
    assert g.value(t, SDC.vintage) == Literal("2010", datatype=XSD.gYear)
    assert (SDCID["tract/51001090100"], None, None) not in g
    assert g.value(SDCID["county/51001"], SDC.vintage) is None


def test_combined_round_trip_synthetic():
    back = long_format_from_graph(build(), "test")
    expected = COMBINED.sort_values(["geoid", "datetime", "scenario", "measure"], ignore_index=True)
    pd.testing.assert_frame_equal(back, expected)


def test_unknown_datetime_rejected():
    with pytest.raises(ValueError, match="outside both conventions"):
        build(COMBINED.assign(datetime=["2030-06-01"] + list(COMBINED.datetime[1:])))


# A second county, so a query that cross-joins counties with each other's tract
# sums (rather than matching them) cannot pass.
TWO_COUNTIES = pd.concat([COMBINED, pd.DataFrame({
    "geoid": ["51003", "51003010300"], "datetime": ["2030-01-01"] * 2,
    "measure": ["synthetic_household_count"] * 2, "value": [70.0, 70.0], "moe": [NAN] * 2,
    "region_type": ["county", "tract"], "data_method": ["simulated"] * 2,
    "scenario": ["va_2030_solar_324k_0_25ev"] * 2,
})], ignore_index=True)


def test_household_query_flags_mismatch():
    query = (TOPIC_DIR / "rdf/queries/county_tract_household_consistency.rq").read_text()
    assert list(build(TWO_COUNTIES).query(query)) == []
    off = TWO_COUNTIES.assign(value=[301.0] + list(TWO_COUNTIES.value[1:]))
    assert [str(r.county) for r in build(off).query(query)] == [str(SDCID["county/51001"])]
    orphan = TWO_COUNTIES[TWO_COUNTIES.geoid != "51003010300"]  # county 51003 with no tracts
    assert [str(r.county) for r in build(orphan).query(query)] == [str(SDCID["county/51003"])]


# --- distribution data: lossless round trip ----------------------------------


@pytest.fixture(scope="module")
def written_graph(tmp_path_factory):
    """Build from the distribution CSV, write .nt.xz, and read it back, like prepare.py."""
    from sdc_rdf import write_graph

    combined_csv = TOPIC_DIR / CONFIG["output"]["combined_csv"]
    if not combined_csv.exists():
        pytest.skip("distribution CSV not present")
    g = build_graph(
        read_csv_exact(combined_csv),
        measure_info=json.loads((TOPIC_DIR / "measure_info.json").read_text()),
        dataset_stem=combined_csv.name.removesuffix(".csv.xz"),
        tract_vintage=CONFIG["geographies"]["tract_vintage"],
        description="",
    )
    path = write_graph(g, tmp_path_factory.mktemp("rdf") / "graph.nt.xz")
    return read_graph(path), combined_csv


def test_distribution_csv_regenerates_from_graph(written_graph, tmp_path):
    g, combined_csv = written_graph
    stem = combined_csv.name.removesuffix(".csv.xz")
    out = write_data(long_format_from_graph(g, stem), tmp_path / combined_csv.name,
                     standardize=False, census_standardize=False)

    def lines(path):
        header, *rows = lzma.open(path, "rt").read().splitlines()
        return header, sorted(rows)

    assert lines(out) == lines(combined_csv)


def test_distribution_households_add_up(written_graph):
    """Same check as county_tract_household_consistency.rq (tested above on synthetic
    data), done by walking triples: rdflib needs ~95 s for the SPARQL at full size."""
    g, _ = written_graph
    county, tracts = {}, {}
    for obs, n in g.subject_objects(SDCM.synthetic_household_count):
        area = g.value(obs, SDC.refArea)
        geoid = str(g.value(area, SDC.geoid))
        if (area, RDF.type, SDC.County) in g:
            county[geoid] = n.toPython()
        else:
            tracts[geoid[:5]] = tracts.get(geoid[:5], 0) + n.toPython()
    assert len(county) == 133 and county == tracts


def test_distribution_sample_conforms(written_graph):
    g, _ = written_graph
    sample = Graph()
    for obs in list(g.subjects(RDF.type, QB.Observation))[:1500]:
        for s in [obs, *g.objects(obs, None)]:
            for t in g.triples((s, None, None)):
                sample.add(t)
    for ds in g.subjects(RDF.type, QB.DataSet):
        for t in g.triples((ds, None, None)):
            sample.add(t)
    ok, report = conforms(sample)
    assert ok, report
