"""Tests for the DataCenters RDF graph (to_rdf.py), including lossless round trips."""

from __future__ import annotations

import json
import lzma
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml
from pyshacl import validate
from rdflib import RDFS, Graph
from sdc_core.io import write_data, write_point_data
from sdc_rdf import (
    cube_to_long_format,
    dataset_iri,
    load_core_ontology,
    load_core_shapes,
    read_csv_exact,
    read_graph,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from to_rdf import POINT_COLUMNS, SDCE, build_graph, points_from_graph, record_iri

TOPIC_DIR = Path(__file__).resolve().parents[2]
ENERGY_RDF_DIR = TOPIC_DIR.parent / "rdf"
ONTOLOGY = Graph().parse(ENERGY_RDF_DIR / "ontology.ttl")
SHAPES = Graph().parse(ENERGY_RDF_DIR / "shapes.ttl") + load_core_shapes()
CONFIG = yaml.safe_load((TOPIC_DIR / "pipeline.yaml").read_text())
NAN = float("nan")

POINTS = pd.DataFrame(
    {
        "facility_id": ["im3_1_campus", "im3_2_building", "im3_3_point"],
        "facility_name": ["Meta Henrico Data Center", "Microsoft Data Center 1", "Unnamed"],
        "lat": [37.482763284885785, 38.8024111256264, 38.9],
        "lon": [-77.23645509442149, -77.58237918867958, -77.4],
        "year": [2026] * 3,
        "type": ["campus", "building", "point"],
        "county_id": [51087, 51153, 51153],
        "operator": ["Meta", "Microsoft", NAN],
        "source_id": ["1", "2", "3"],
        "sqft": [4671056.0, 248706.0, NAN],
        "state_abb": ["VA"] * 3,
    },
    columns=POINT_COLUMNS,
)

COUNTY = pd.DataFrame(
    {
        "geoid": ["51087", "51153", "51087", "51153"],
        "datetime": ["2026-02-09"] * 4,
        "measure": ["total_data_center_count"] * 2 + ["point_data_center_count"] * 2,
        "value": [1.0, 2.0, 0.0, 1.0],
        "moe": [NAN] * 4,
        "region_type": ["county"] * 4,
        "data_method": ["observed"] * 4,
        "scenario": ["im3_atlas_v2026_02_09"] * 4,
    }
)


def build(points=POINTS, county=COUNTY):
    return build_graph(points, county, ontology=ONTOLOGY, measure_info={},
                       county_dataset_id="test", source_url="https://example.org/atlas")


def conforms(g: Graph) -> tuple[bool, str]:
    ok, _, report = validate(g + ONTOLOGY + load_core_ontology(), shacl_graph=SHAPES)
    return ok, report


def test_synthetic_graph_conforms():
    g, unknown = build()
    assert unknown == set()
    ok, report = conforms(g)
    assert ok, report


def test_records_typed_and_operator_linked():
    g, _ = build()
    rec = record_iri("im3_1_campus")
    assert g.value(rec, SDCE.recordType) == SDCE["dcrecord-campus"]
    assert str(g.value(g.value(rec, SDCE.operatedBy), RDFS.label)) == "Meta"
    assert g.value(record_iri("im3_3_point"), SDCE.operatedBy) is None
    assert g.value(record_iri("im3_3_point"), SDCE.facilityAreaSqFt) is None


def test_points_round_trip_synthetic():
    g, _ = build()
    pd.testing.assert_frame_equal(points_from_graph(g), POINTS.sort_values("facility_id", ignore_index=True))


def test_non_va_state_rejected():
    with pytest.raises(ValueError, match="state_abb"):
        build(points=POINTS.assign(state_abb=["VA", "MD", "VA"]))


def test_unknown_record_type_reported_and_fails_shacl():
    g, unknown = build(points=POINTS.assign(type=["campus", "building", "polygon"]))
    assert unknown == {"polygon"}
    ok, report = conforms(g)
    assert not ok and "dcrecord-polygon" in report


def test_consistency_query_flags_mismatch():
    query = (TOPIC_DIR / "rdf/queries/county_count_consistency.rq").read_text()
    g, _ = build()
    assert list(g.query(query)) == []
    g, _ = build(county=COUNTY.assign(value=[1.0, 2.0, 1.0, 1.0]))  # 51087 claims a point record
    assert len(list(g.query(query))) == 1
    g, _ = build(county=COUNTY.assign(value=[1.0, 3.0, 0.0, 1.0]))  # 51153 total off by one
    assert len(list(g.query(query))) == 1


# --- distribution data: lossless round trip ----------------------------------


@pytest.fixture(scope="module")
def written_graph(tmp_path_factory):
    """Build from the distribution CSVs, write .nt.xz, and read it back, like prepare.py."""
    from sdc_rdf import write_graph

    point_csv = TOPIC_DIR / CONFIG["output"]["point_csv"]
    county_csv = TOPIC_DIR / CONFIG["output"]["county_csv"]
    if not (point_csv.exists() and county_csv.exists()):
        pytest.skip("distribution CSVs not present")
    g, unknown = build_graph(
        read_csv_exact(point_csv), read_csv_exact(county_csv), ontology=ONTOLOGY,
        measure_info=json.loads((TOPIC_DIR / "measure_info.json").read_text()),
        county_dataset_id=county_csv.name.removesuffix(".csv.xz"),
        source_url=CONFIG["source"].get("source_url"),
    )
    assert unknown == set()
    path = write_graph(g, tmp_path_factory.mktemp("rdf") / "graph.nt.xz")
    return read_graph(path), point_csv, county_csv


def _lines(path: Path) -> tuple[str, list[str]]:
    header, *rows = lzma.open(path, "rt").read().splitlines()
    return header, sorted(rows)


def test_distribution_graph_conforms(written_graph):
    ok, report = conforms(written_graph[0])
    assert ok, report


def test_distribution_counts_match_records(written_graph):
    query = (TOPIC_DIR / "rdf/queries/county_count_consistency.rq").read_text()
    assert list(written_graph[0].query(query)) == []


def test_distribution_point_csv_regenerates_from_graph(written_graph, tmp_path):
    g, point_csv, _ = written_graph
    out = write_point_data(points_from_graph(g), tmp_path / point_csv.name)
    assert _lines(out) == _lines(point_csv)


def test_distribution_county_csv_regenerates_from_graph(written_graph, tmp_path):
    g, _, county_csv = written_graph
    out = write_data(cube_to_long_format(g, dataset_iri(county_csv.name.removesuffix(".csv.xz"))),
                     tmp_path / county_csv.name, standardize=False, census_standardize=False)
    assert _lines(out) == _lines(county_csv)
