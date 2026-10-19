"""Tests for the EVChargingStations RDF graph (to_rdf.py)."""

from __future__ import annotations

import json
import lzma
import re
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml
from pyshacl import validate
from rdflib import RDF, XSD, Graph, Literal
from sdc_core.io import write_data, write_point_data
from sdc_rdf import SDC, SDCID, cube_to_long_format, load_core_ontology, load_core_shapes, read_csv_exact

sys.path.insert(0, str(Path(__file__).resolve().parent))
from to_rdf import POINT_COLUMNS, SDCE, build_graph, charger_level_iri, points_from_graph, station_iri

TOPIC_DIR = Path(__file__).resolve().parents[2]
ENERGY_DIR = TOPIC_DIR.parent
ONTOLOGY = Graph().parse(ENERGY_DIR / "rdf/ontology.ttl")
SHAPES = Graph().parse(ENERGY_DIR / "rdf/shapes.ttl") + load_core_shapes()

POINTS = pd.DataFrame(
    {
        "facility_id": ["va_1_existing_l2", "va_1_existing_l3", "1149486296_l2"],
        "facility_name": ["VA Charging Station va_1_existing"] * 2 + ["VA Charging Station 1149486296"],
        "lat": [38.0, 38.0, 37.5],
        "lon": [-78.5, -78.5, -77.4],
        "year": [2030] * 3,
        "type": ["l2", "l3", "l2"],
        "count": [4, 2, 1],
        "fuel_type_code": ["ELEC"] * 3,
        "geoid": ["51540", "51540", "51760"],
        "station_id": ["va_1_existing", "va_1_existing", "1149486296"],
    },
    columns=POINT_COLUMNS,
)

COUNTY = pd.DataFrame(
    {
        "geoid": ["51540", "51540", "51760", "51760"],
        "datetime": ["2030-01-01"] * 4,
        "measure": ["total_charger_count", "total_station_count"] * 2,
        "value": [6.0, 1.0, 1.0, 1.0],
        "moe": [pd.NA] * 4,
        "region_type": ["county"] * 4,
        "data_method": ["simulated"] * 4,
        "scenario": ["va_2030_run30"] * 4,
    }
)


def build(points=POINTS, county=COUNTY):
    return build_graph(
        points, county, ontology=ONTOLOGY, measure_info={}, county_dataset_id="test",
        description="test scenario",
    )


def conforms(g: Graph) -> tuple[bool, str]:
    ok, _, report = validate(g + ONTOLOGY + load_core_ontology(), shacl_graph=SHAPES)
    return ok, report


def test_synthetic_graph_conforms():
    g, unknown = build()
    assert unknown == set()
    ok, report = conforms(g)
    assert ok, report


def test_one_station_node_with_a_group_per_level():
    g, _ = build()
    st = station_iri("va_1_existing")
    assert len(set(g.subjects(RDF.type, SDCE.EVChargingStation))) == 2
    groups = {g.value(grp, SDCE.chargerLevel): g.value(grp, SDCE.chargerCount)
              for grp in g.objects(st, SDCE.hasChargerGroup)}
    assert groups == {charger_level_iri("l2"): Literal(4, datatype=XSD.integer),
                      charger_level_iri("l3"): Literal(2, datatype=XSD.integer)}


def test_static_datetime_is_scenario_year():
    g, _ = build()
    assert set(g.objects(None, SDC.refPeriod)) == {Literal("2030", datatype=XSD.gYear)}


def test_unknown_level_reported_and_fails_shacl():
    g, unknown = build(points=POINTS.assign(type=["l2", "l4", "l2"],
                                            facility_id=["a_l2", "a_l4", "b_l2"]))
    assert unknown == {"l4"}
    ok, report = conforms(g)
    assert not ok and "charger-l4" in report


def test_conflicting_station_attributes_rejected():
    with pytest.raises(ValueError, match="conflicting"):
        build(points=POINTS.assign(lat=[38.0, 38.1, 37.5]))


def test_points_round_trip_synthetic():
    g, _ = build()
    pd.testing.assert_frame_equal(points_from_graph(g), POINTS.sort_values("facility_id", ignore_index=True))


def test_conflicting_fuel_code_rejected():
    with pytest.raises(ValueError, match="conflicting"):
        build(points=POINTS.assign(fuel_type_code=["ELEC", "CNG", "ELEC"]))


def test_duplicate_rows_rejected():
    with pytest.raises(ValueError, match="duplicate facility_id"):
        build(points=pd.concat([POINTS, POINTS.iloc[[0]]]))


def test_consistency_query_flags_mismatch():
    query = (TOPIC_DIR / "rdf/queries/county_count_consistency.rq").read_text()
    g, _ = build()
    assert list(g.query(query)) == []
    g, _ = build(county=COUNTY.assign(value=[7.0, 1.0, 1.0, 1.0]))
    assert len(list(g.query(query))) == 1


# --- distribution data -------------------------------------------------------


@pytest.fixture(scope="module")
def real_graph():
    config = yaml.safe_load((TOPIC_DIR / "pipeline.yaml").read_text())
    point_csv = TOPIC_DIR / config["output"]["point_csv"]
    county_csv = TOPIC_DIR / config["output"]["county_csv"]
    if not (point_csv.exists() and county_csv.exists()):
        pytest.skip("distribution CSVs not present")
    points = read_csv_exact(point_csv)
    g, unknown = build_graph(
        points, read_csv_exact(county_csv), ontology=ONTOLOGY,
        measure_info=json.loads((TOPIC_DIR / "measure_info.json").read_text()),
        county_dataset_id=county_csv.name.removesuffix(".csv.xz"), description="",
    )
    return g, unknown, points


def test_distribution_graph_conforms(real_graph):
    g, unknown, points = real_graph
    assert unknown == set()
    assert len(set(g.subjects(RDF.type, SDCE.EVChargingStation))) == points["station_id"].nunique()
    assert len(set(g.subjects(RDF.type, SDCE.ChargerGroup))) == len(points)
    ok, report = conforms(g)
    assert ok, report


def test_distribution_county_counts_match_stations(real_graph):
    g, _, _ = real_graph
    query = (TOPIC_DIR / "rdf/queries/county_count_consistency.rq").read_text()
    assert list(g.query(query)) == []


def test_every_demand_station_link_resolves(real_graph):
    """EVChargingDemand's sdce:atStation targets must all be stations in this graph."""
    g, _, _ = real_graph
    demand_cfg = yaml.safe_load((ENERGY_DIR / "EVChargingDemand/pipeline.yaml").read_text())
    demand_graph = ENERGY_DIR / "EVChargingDemand" / demand_cfg["output"]["rdf_graph"]
    if not demand_graph.exists():
        pytest.skip("EVChargingDemand graph not present")
    # Scan the sorted N-Triples text instead of parsing ~780k triples.
    pattern = re.compile(
        r"<https://w3id\.org/sdc/ns/energy#atStation> <(https://w3id\.org/sdc/id/ev-station/[^>]+)>"
    )
    with lzma.open(demand_graph, "rt") as f:
        targets = {m[1] for line in f if (m := pattern.search(line))}
    assert len(targets) == 1224
    stations = {str(s) for s in g.subjects(RDF.type, SDCE.EVChargingStation)}
    assert targets <= stations


def test_distribution_county_csv_regenerates_from_graph(real_graph, tmp_path):
    """Lossless: the county CSV can be rebuilt from the graph alone."""
    g = real_graph[0]
    config = yaml.safe_load((TOPIC_DIR / "pipeline.yaml").read_text())
    county_csv = TOPIC_DIR / config["output"]["county_csv"]
    dataset = SDCID[f"dataset/{county_csv.name.removesuffix('.csv.xz')}"]
    out = write_data(cube_to_long_format(g, dataset), tmp_path / county_csv.name,
                     standardize=False, census_standardize=False)

    def lines(path):
        header, *rows = lzma.open(path, "rt").read().splitlines()
        return header, sorted(rows)

    assert lines(out) == lines(county_csv)


def test_distribution_point_csv_regenerates_from_graph(real_graph, tmp_path):
    """Lossless: the point CSV can be rebuilt from the graph alone."""
    g = real_graph[0]
    config = yaml.safe_load((TOPIC_DIR / "pipeline.yaml").read_text())
    point_csv = TOPIC_DIR / config["output"]["point_csv"]
    out = write_point_data(points_from_graph(g), tmp_path / point_csv.name)

    def lines(path):
        header, *rows = lzma.open(path, "rt").read().splitlines()
        return header, sorted(rows)

    assert lines(out) == lines(point_csv)
