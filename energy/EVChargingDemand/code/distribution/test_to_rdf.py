"""Tests for the EVChargingDemand RDF graph (to_rdf.py)."""

from __future__ import annotations

import json
import lzma
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
import yaml
from pyshacl import validate
from rdflib import RDF, XSD, Graph, Literal
from sdc_core.io import write_data, write_point_data
from sdc_rdf import SDC, SDCID, SDCM, cube_to_long_format, load_core_ontology, load_core_shapes, read_csv_exact

sys.path.insert(0, str(Path(__file__).resolve().parent))
from to_rdf import POINT_COLUMNS, SDCE, build_graph, location_iri, points_from_graph, station_iri

TOPIC_DIR = Path(__file__).resolve().parents[2]
ENERGY_RDF_DIR = TOPIC_DIR.parent / "rdf"
ONTOLOGY = Graph().parse(ENERGY_RDF_DIR / "ontology.ttl")
SHAPES = Graph().parse(ENERGY_RDF_DIR / "shapes.ttl") + load_core_shapes()

POINTS = pd.DataFrame(
    {
        "facility_id": ["19422703", "va_223306_existing", "dnwcbueu7"],
        "facility_name": ["Charging Location 19422703 (residential_or_other)",
                          "Charging Location va_223306_existing (public_station)",
                          "Charging Location dnwcbueu7 (unknown)"],
        "lat": [38.03, 38.04, 37.0],
        "lon": [-78.47, -78.49, -76.0],
        "year": [2026] * 3,
        "type": ["residential_or_other", "public_station", "unknown"],
        "id_format": ["residential_or_other", "public_station", "unknown"],
        "n_hours_active": [2, 1, 1],
        "total_kwh": [30.0, 12.5, 5.0],
        "geoid": ["51003", "51540", "51003"],
    }
)

COUNTY = pd.DataFrame(
    {
        "geoid": ["51003", "51003", "51540"],
        "datetime": ["2026-01-01T07:00:00", "2026-01-01T18:00:00", "2026-01-01T07:00:00"],
        "measure": ["ev_charging_demand_kwh"] * 3,
        "value": [20.0, 15.0, 12.5],
        "moe": [pd.NA] * 3,
        "region_type": ["county"] * 3,
        "data_method": ["simulated"] * 3,
        "scenario": ["va_2026_run2_eval30"] * 3,
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


def test_hourly_observations_use_year_plus_hour():
    g, _ = build()
    obs = SDCID["obs/test/county/51003/2026/h18/va_2026_run2_eval30/ev_charging_demand_kwh"]
    assert (obs, SDC.refPeriod, Literal("2026", datatype=XSD.gYear)) in g
    assert (obs, SDC.hourOfDay, Literal(18, datatype=XSD.integer)) in g


def test_only_public_stations_link_to_station_inventory():
    g, _ = build()
    assert (location_iri("va_223306_existing"), SDCE.atStation, station_iri("va_223306_existing")) in g
    assert g.value(location_iri("19422703"), SDCE.atStation) is None
    assert g.value(location_iri("dnwcbueu7"), SDCE.atStation) is None


def test_unknown_location_type_reported_and_fails_shacl():
    g, unknown = build(points=POINTS.assign(type=["residential_or_other", "public_station", "depot"],
                                       id_format=["residential_or_other", "public_station", "depot"]))
    assert unknown == {"depot"}
    ok, report = conforms(g)
    assert not ok and "evloc-depot" in report


def test_unassigned_county_rejected():
    with pytest.raises(ValueError, match="no county"):
        build(points=POINTS.assign(geoid=["51003", None, "51003"]))


def test_points_round_trip_synthetic():
    g, _ = build()
    expected = POINTS.drop(columns="geoid").sort_values("facility_id", ignore_index=True)
    pd.testing.assert_frame_equal(points_from_graph(g), expected[POINT_COLUMNS])


def test_id_format_must_equal_type():
    with pytest.raises(ValueError, match="id_format"):
        build(points=POINTS.assign(id_format=["public_station", "public_station", "unknown"]))


def test_duplicate_location_ids_rejected():
    # Regression: mixed int/str parsing once split location 161663971 into two rows.
    with pytest.raises(ValueError, match="duplicate charging location"):
        build(points=POINTS.assign(facility_id=["161663971", "va_223306_existing", "161663971"]))


def test_consistency_query_flags_mismatch():
    query = (TOPIC_DIR / "rdf/queries/county_energy_consistency.rq").read_text()
    g, _ = build()
    assert list(g.query(query)) == []  # 35 = 30 + 5 and 12.5 = 12.5
    g, _ = build(county=COUNTY.assign(value=[20.0, 15.0, 99.0]))
    assert [str(r.county) for r in g.query(query)] == [str(SDCID["county/51540"])]


# --- distribution data -------------------------------------------------------
# The full graph is ~780k triples, too large for rdflib SPARQL or pyshacl in a
# test run, so these checks walk the triples directly and SHACL-validate a sample.


@pytest.fixture(scope="module")
def real_graph():
    import prepare

    config = yaml.safe_load((TOPIC_DIR / "pipeline.yaml").read_text())
    point_csv = TOPIC_DIR / config["output"]["point_csv"]
    county_csv = TOPIC_DIR / config["output"]["county_csv"]
    counties = prepare.REPO_DIR / config["geographies"]["va_counties"]
    if not (point_csv.exists() and county_csv.exists() and counties.exists()):
        pytest.skip("distribution CSVs or county geographies not present")
    points = prepare.locations_with_county(point_csv, counties)
    county = read_csv_exact(county_csv)
    g, unknown = build_graph(
        points, county, ontology=ONTOLOGY,
        measure_info=json.loads((TOPIC_DIR / "measure_info.json").read_text()),
        county_dataset_id=county_csv.name.removesuffix(".csv.xz"), description="",
    )
    return g, unknown, points, county


def test_distribution_entities_complete(real_graph):
    g, unknown, points, county = real_graph
    assert unknown == set()
    assert len(set(g.subjects(RDF.type, SDCE.EVChargingLocation))) == len(points)
    assert len(set(g.subjects(RDF.type, SDCE.EVChargingStation))) == (points["type"] == "public_station").sum()
    assert len(set(g.subjects(SDC.hourOfDay, None))) == len(county)


def test_distribution_county_energy_matches_locations(real_graph):
    g, _, _, _ = real_graph
    cube, locs = defaultdict(Decimal), defaultdict(Decimal)
    for obs, kwh in g.subject_objects(SDCM.ev_charging_demand_kwh):
        cube[g.value(obs, SDC.refArea)] += kwh.toPython()
    for loc, kwh in g.subject_objects(SDCE.typicalDayEnergyKWh):
        locs[g.value(loc, SDCE.inCounty)] += kwh.toPython()
    assert cube.keys() == locs.keys()
    for county, total in cube.items():
        assert abs(total - locs[county]) <= Decimal("1e-6") * total, county


def test_distribution_sample_conforms(real_graph):
    g, _, points, _ = real_graph
    sample = Graph()
    for lid in points.groupby("type").head(200)["facility_id"]:
        loc = location_iri(str(lid))
        for s in [loc, *g.objects(loc, None)]:
            for t in g.triples((s, None, None)):
                sample.add(t)
    for obs in list(g.subjects(SDC.hourOfDay, None))[:500]:
        for s in [obs, *g.objects(obs, None)]:
            for t in g.triples((s, None, None)):
                sample.add(t)
    ok, report = conforms(sample)
    assert ok, report


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
