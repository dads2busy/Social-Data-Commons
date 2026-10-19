"""Tests for the DataCentersProjected RDF graph (to_rdf.py), including lossless round trips."""

from __future__ import annotations

import json
import lzma
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml
from pyshacl import validate
from rdflib import XSD, Graph, Literal
from sdc_core.io import write_data, write_point_data
from sdc_rdf import (
    SDC,
    SDCID,
    cube_to_long_format,
    load_core_ontology,
    load_core_shapes,
    read_csv_exact,
    read_graph,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from to_rdf import POINT_COLUMNS, SDCE, build_graph, points_from_graph, site_iri

TOPIC_DIR = Path(__file__).resolve().parents[2]
ENERGY_DIR = TOPIC_DIR.parent
ONTOLOGY = Graph().parse(ENERGY_DIR / "rdf/ontology.ttl")
SHAPES = Graph().parse(ENERGY_DIR / "rdf/shapes.ttl") + load_core_shapes()
CONFIG = yaml.safe_load((TOPIC_DIR / "pipeline.yaml").read_text())


def _point(fid, scenario, tier, weight, geoid, **kw):
    row = {
        "facility_id": fid, "facility_name": f"Projected Data Center ({scenario})",
        "lat": 37.09495040774823, "lon": -81.13105561140871, "year": 2035,
        "type": "projected_data_center", "campus_size_square_ft": 1000000,
        "cooling_energy_demand_mwh": 0.0, "cooling_water_consumption_mgy": 34.815746,
        "cooling_water_demand_mgy": 43.51968, "data_center_it_power_mw": 36, "geoid": geoid,
        "growth_scenario": tier, "market_gravity_weight": weight, "mechanical_cooling_frac": 0.0,
        "normalized_gravity_score": 0.763875, "normalized_locational_cost": 5e-06,
        "scenario": scenario, "source_id": fid.split("_")[2] + "_" + fid.split("_")[3],
        "total_cost_million_usd": 485.88, "water_cooling_frac": 1.0, "weighted_siting_score": 0.0,
    }
    row.update(kw)
    return row


POINTS = pd.DataFrame(
    [
        _point("im3_cerf_51_0_high_0", "im3_cerf_high_0", "high", 0, 51021),
        _point("im3_cerf_51_0_moderate_50", "im3_cerf_moderate_50", "moderate", 50, 51107),
        _point("im3_cerf_51_1_moderate_50", "im3_cerf_moderate_50", "moderate", 50, 51107),
    ],
    columns=POINT_COLUMNS,
)

COUNTY = pd.DataFrame(
    {
        "geoid": ["51021", "51107"],
        "datetime": ["2035-01-01"] * 2,
        "measure": ["projected_data_center_count"] * 2,
        "value": [1.0, 2.0],
        "moe": [float("nan")] * 2,
        "region_type": ["county"] * 2,
        "data_method": ["simulated"] * 2,
        "scenario": ["im3_cerf_high_0", "im3_cerf_moderate_50"],
    }
)


def build(points=POINTS, county=COUNTY):
    return build_graph(points, county, measure_info={}, county_dataset_id="test",
                       default_scenario="im3_cerf_moderate_50")


def conforms(g: Graph) -> tuple[bool, str]:
    ok, _, report = validate(g + ONTOLOGY + load_core_ontology(), shacl_graph=SHAPES)
    return ok, report


def test_synthetic_graph_conforms():
    ok, report = conforms(build())
    assert ok, report


def test_scenarios_carry_tier_weight_and_default():
    g = build()
    s = SDCID["scenario/im3_cerf_moderate_50"]
    assert g.value(s, SDCE.growthTier) == SDCE["growth-moderate"]
    assert g.value(s, SDCE.marketGravityWeight) == Literal(50, datatype=XSD.integer)
    assert g.value(SDCID["dataset/test"], SDC.defaultScenario) == s


def test_same_cerf_id_in_two_scenarios_is_two_sites():
    g = build()
    a, b = site_iri("im3_cerf_51_0_high_0"), site_iri("im3_cerf_51_0_moderate_50")
    assert a != b and g.value(a, SDCE.sourceId) == g.value(b, SDCE.sourceId)


def test_points_round_trip_synthetic():
    back = points_from_graph(build())
    expected = POINTS.assign(geoid=POINTS["geoid"].astype(str)).sort_values("facility_id", ignore_index=True)
    pd.testing.assert_frame_equal(back, expected)


def test_small_float_is_valid_decimal():
    g = build()
    lit = g.value(site_iri("im3_cerf_51_0_high_0"), SDCE.normalizedLocationalCost)
    assert str(lit) == "0.000005" and float(lit.toPython()) == 5e-06


def test_scenario_label_mismatch_rejected():
    bad = POINTS.assign(market_gravity_weight=[0, 25, 50])
    with pytest.raises(ValueError, match="disagree"):
        build(points=bad)


# --- distribution data: lossless round trip ----------------------------------


@pytest.fixture(scope="module")
def written_graph(tmp_path_factory):
    """Build from the distribution CSVs, write .nt.xz, and read it back, like prepare.py."""
    from sdc_rdf import write_graph

    point_csv = TOPIC_DIR / CONFIG["output"]["point_csv"]
    county_csv = TOPIC_DIR / CONFIG["output"]["county_csv"]
    if not (point_csv.exists() and county_csv.exists()):
        pytest.skip("distribution CSVs not present")
    g = build_graph(
        read_csv_exact(point_csv), read_csv_exact(county_csv),
        measure_info=json.loads((TOPIC_DIR / "measure_info.json").read_text()),
        county_dataset_id=county_csv.name.removesuffix(".csv.xz"),
        default_scenario=CONFIG["source"]["scenario_canonical"],
    )
    path = write_graph(g, tmp_path_factory.mktemp("rdf") / "graph.nt.xz")
    return read_graph(path), point_csv, county_csv


def _lines(path: Path) -> tuple[str, list[str]]:
    header, *rows = lzma.open(path, "rt").read().splitlines()
    return header, sorted(rows)


def test_distribution_graph_conforms(written_graph):
    g, _, _ = written_graph
    ok, report = conforms(g)
    assert ok, report


def test_point_csv_regenerates_from_graph(written_graph, tmp_path):
    g, point_csv, _ = written_graph
    out = write_point_data(points_from_graph(g), tmp_path / point_csv.name)
    assert _lines(out) == _lines(point_csv)


def test_county_csv_regenerates_from_graph(written_graph, tmp_path):
    g, _, county_csv = written_graph
    dataset = SDCID[f"dataset/{county_csv.name.removesuffix('.csv.xz')}"]
    out = write_data(cube_to_long_format(g, dataset), tmp_path / county_csv.name,
                     standardize=False, census_standardize=False)
    assert _lines(out) == _lines(county_csv)
