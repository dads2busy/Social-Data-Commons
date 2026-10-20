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
        "geoid": ["51001", "51001090100", "51001090101", "51001090102",
                  "51001", "51001090100", "51001090101"],
        "datetime": ["2030-01-01"] * 4 + ["2030-01-01T12:00:00"] * 3,
        "measure": ["synthetic_household_count_geo20", "synthetic_household_count_geo10",
                    "synthetic_household_count_geo20", "synthetic_household_count_geo20",
                    "pv_generation_kwh_geo20", "pv_generation_kwh_geo10", "pv_generation_kwh_geo20"],
        "value": [300.0, 300.0, 180.0, 120.0, 55.5, 20.25, 5e-06],
        "moe": [NAN] * 7,
        "region_type": ["county", "tract", "tract", "tract", "county", "tract", "tract"],
        "data_method": ["simulated"] * 7,
        "scenario": ["va_2030_solar_324k_0_25ev"] * 7,
    }
)


def build(df=COMBINED):
    return build_graph(df, measure_info={}, dataset_stem="test", geo10_tract_vintage=2010, description="d")


def conforms(g: Graph) -> tuple[bool, str]:
    ok, _, report = validate(g + load_core_ontology(), shacl_graph=load_core_shapes())
    return ok, report


def test_synthetic_graph_conforms():
    ok, report = conforms(build())
    assert ok, report


def test_four_datasets_by_period_and_vintage():
    g = build()
    counts = {part: len(list(g.subjects(QB.dataSet, dataset_iri(f"test/{part}"))))
              for part in ["static", "hourly", "static-geo10", "hourly-geo10"]}
    assert counts == {"static": 3, "hourly": 2, "static-geo10": 1, "hourly-geo10": 1}
    assert g.value(dataset_iri("test/static"), SDC.periodConvention) == SDC["period-yearAnchor"]
    assert g.value(dataset_iri("test/hourly-geo10"), SDC.periodConvention) == SDC["period-hourOfDayProfile"]


def test_geo10_rows_on_2010_tracts_geo20_rows_on_2020_tracts():
    g = build()
    t10 = SDCID["tract-2010/51001090100"]
    assert (t10, RDF.type, SDC.Tract) in g
    assert g.value(t10, SDC.vintage) == Literal("2010", datatype=XSD.gYear)
    assert (SDCID["tract/51001090101"], RDF.type, SDC.Tract) in g
    assert g.value(SDCID["tract/51001090101"], SDC.vintage) is None
    assert (SDCID["tract/51001090100"], None, None) not in g  # the 2010 tract is not a 2020 node
    assert g.value(SDCID["county/51001"], SDC.vintage) is None


def test_combined_round_trip_synthetic():
    back = long_format_from_graph(build(), "test")
    expected = COMBINED.sort_values(["geoid", "datetime", "scenario", "measure"], ignore_index=True)
    pd.testing.assert_frame_equal(back, expected)


@pytest.mark.parametrize("change,match", [
    ({"datetime": ["2030-06-01"] + list(COMBINED.datetime[1:])}, "outside both conventions"),
    ({"measure": ["synthetic_household_count"] + list(COMBINED.measure[1:])}, "suffix"),
    ({"region_type": ["county"] * 7}, "_geo10 measures must be tract rows"),
])
def test_bad_input_rejected(change, match):
    with pytest.raises(ValueError, match=match):
        build(COMBINED.assign(**change))


# A second county, so a query that cross-joins counties with each other's tract
# sums (rather than matching them) cannot pass.
TWO_COUNTIES = pd.concat([COMBINED, pd.DataFrame({
    "geoid": ["51003", "51003010300"], "datetime": ["2030-01-01"] * 2,
    "measure": ["synthetic_household_count_geo20", "synthetic_household_count_geo10"],
    "value": [70.0, 70.0], "moe": [NAN] * 2, "region_type": ["county", "tract"],
    "data_method": ["simulated"] * 2, "scenario": ["va_2030_solar_324k_0_25ev"] * 2,
})], ignore_index=True)


def test_household_query_flags_mismatch():
    query = (TOPIC_DIR / "rdf/queries/county_tract_household_consistency.rq").read_text()
    assert list(build(TWO_COUNTIES).query(query)) == []
    off = TWO_COUNTIES.assign(value=[301.0] + list(TWO_COUNTIES.value[1:]))
    assert [str(r.county) for r in build(off).query(query)] == [str(SDCID["county/51001"])]
    orphan = TWO_COUNTIES[TWO_COUNTIES.geoid != "51003010300"]  # county 51003 with no 2010 tracts
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
        geo10_tract_vintage=CONFIG["geographies"]["geo10_tract_vintage"],
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
    data), done by walking triples: rdflib needs ~95 s for the SPARQL at full size.

    Counties equal their 2010 tracts exactly. The interpolated 2020 tracts conserve
    the statewide total; per county they can differ where 2010 and 2020 tract
    boundaries cross county lines.
    """
    g, _ = written_graph

    def by_county(pred, region_class):
        sums = {}
        for obs, n in g.subject_objects(pred):
            area = g.value(obs, SDC.refArea)
            if (area, RDF.type, region_class) in g:
                geoid = str(g.value(area, SDC.geoid))[:5]
                sums[geoid] = sums.get(geoid, 0) + n.toPython()
        return sums

    county = by_county(SDCM.synthetic_household_count_geo20, SDC.County)
    tracts10 = by_county(SDCM.synthetic_household_count_geo10, SDC.Tract)
    tracts20 = by_county(SDCM.synthetic_household_count_geo20, SDC.Tract)
    assert len(county) == 133 and county == tracts10
    total = sum(county.values())
    assert abs(float(sum(tracts20.values())) - float(total)) / float(total) < 1e-5


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
