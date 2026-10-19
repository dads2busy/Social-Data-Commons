"""Tests for the PowerInfrastructure RDF graph (to_rdf.py)."""

from __future__ import annotations

import json
import lzma
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml
from pyshacl import validate
from rdflib import RDF, Graph
from sdc_core.io import write_data
from sdc_rdf import SDCID, cube_to_long_format, load_core_ontology, load_core_shapes, read_csv_exact

sys.path.insert(0, str(Path(__file__).resolve().parent))
from to_rdf import SDCE, build_graph

TOPIC_DIR = Path(__file__).resolve().parents[2]
ENERGY_RDF_DIR = TOPIC_DIR.parent / "rdf"
ONTOLOGY = Graph().parse(ENERGY_RDF_DIR / "ontology.ttl")
SHAPES = Graph().parse(ENERGY_RDF_DIR / "shapes.ttl") + load_core_shapes()

POINTS = pd.DataFrame(
    {
        "facility_id": ["hifld_pp_1", "hifld_pp_2", "hifld_ss_3"],
        "facility_name": ["Plant A", "Plant B", "Sub C"],
        "lat": [37.5, 37.6, 38.0],
        "lon": [-76.8, -77.0, -78.0],
        "year": [2026] * 3,
        "type": ["power_plant", "power_plant", "substation"],
        "geoid": ["51101", "51101", "51003"],
        "lines": [None, None, 3.0],
        "max_voltage": [None, None, -999999.0],
        "operator": ["ACME POWER", None, None],
        "plant_capacity_mw": [101.0, None, None],
        "plant_source": ["NG", "XYZ", None],
        "source_id": [1.0, 2.0, 3.0],
        "status": ["OP", "NOT AVAILABLE", "IN SERVICE"],
    }
)

COUNTY = pd.DataFrame(
    {
        "geoid": ["51101", "51003"],
        "datetime": ["2026-05-29"] * 2,
        "measure": ["power_plant_count"] * 2,
        "value": [2.0, 0.0],
        "moe": [pd.NA] * 2,
        "region_type": ["county"] * 2,
        "data_method": ["observed"] * 2,
        "scenario": ["hifld_snapshot_2026_05_29"] * 2,
    }
)


def build(points=POINTS, county=COUNTY):
    return build_graph(
        points, county, ontology=ONTOLOGY, measure_info={}, county_dataset_id="test",
        layer_urls=["https://example.org/layer"], null_sentinel=-999999,
    )


def conforms(g: Graph) -> tuple[bool, str]:
    ok, _, report = validate(g + ONTOLOGY + load_core_ontology(), shacl_graph=SHAPES)
    return ok, report


def test_synthetic_graph_conforms():
    g, _ = build(points=POINTS.assign(plant_source=["NG", "SUN", None]))
    ok, report = conforms(g)
    assert ok, report


def test_undeclared_code_fails_shacl():
    g, _ = build()  # plant_source "XYZ" is not in the ontology's code list
    ok, report = conforms(g)
    assert not ok and "fuel-XYZ" in report


def test_facility_typing_and_attributes():
    g, _ = build()
    a = SDCID["facility/hifld_pp_1"]
    assert (a, RDF.type, SDCE.PowerPlant) in g
    assert (a, SDCE.primaryFuel, SDCE["fuel-NG"]) in g
    assert str(g.value(a, SDCE.sourceId)) == "1"  # float-read IDs come back as integers
    assert (SDCID["facility/hifld_ss_3"], SDCE.operatingStatus, SDCE["status-IN_SERVICE"]) in g


def test_missing_values_are_omitted_not_zeroed():
    g, _ = build()
    assert g.value(SDCID["facility/hifld_pp_2"], SDCE.operatingCapacityMW) is None
    assert g.value(SDCID["facility/hifld_pp_2"], SDCE.operatingStatus) is None  # NOT AVAILABLE
    assert g.value(SDCID["facility/hifld_ss_3"], SDCE.maxVoltageKV) is None  # -999999 sentinel


def test_unknown_codes_reported():
    _, unknown = build()
    assert unknown == {"fuel:XYZ"}


def test_multiple_snapshots_rejected():
    county = COUNTY.assign(scenario=["a", "b"])
    with pytest.raises(ValueError, match="one HIFLD snapshot"):
        build(county=county)


@pytest.fixture(scope="module")
def real_graph():
    config = yaml.safe_load((TOPIC_DIR / "pipeline.yaml").read_text())
    point_csv = TOPIC_DIR / config["output"]["point_csv"]
    county_csv = TOPIC_DIR / config["output"]["county_csv"]
    if not (point_csv.exists() and county_csv.exists()):
        pytest.skip("distribution CSVs not present")
    g, unknown = build_graph(
        read_csv_exact(point_csv), read_csv_exact(county_csv), ontology=ONTOLOGY,
        measure_info=json.loads((TOPIC_DIR / "measure_info.json").read_text()),
        county_dataset_id=county_csv.name.removesuffix(".csv.xz"),
        layer_urls=[], null_sentinel=config["source"]["null_sentinel"],
    )
    return g, unknown


def test_distribution_graph_conforms(real_graph):
    g, unknown = real_graph
    assert unknown == set()
    ok, report = conforms(g)
    assert ok, report


def test_distribution_county_counts_match_facilities(real_graph):
    g, _ = real_graph
    query = (TOPIC_DIR / "rdf/queries/county_count_consistency.rq").read_text()
    assert list(g.query(query)) == []


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
