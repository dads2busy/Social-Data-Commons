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



HOURLY = pd.DataFrame(
    {
        "geoid": ["51001", "51001"],
        "datetime": ["2026-01-01T00:00:00", "2026-01-01T23:00:00"],
        "measure": ["demand_kwh"] * 2,
        "value": [31.9, 12.0],
        "moe": [pd.NA] * 2,
        "region_type": ["county"] * 2,
        "data_method": ["simulated"] * 2,
        "scenario": ["run_a"] * 2,
    }
)


def test_hour_of_day_profile_splits_year_and_hour():
    g = build(HOURLY, hour_of_day_profile=True)
    obs = SDCID["obs/test_ds/county/51001/2026/h23/run_a/demand_kwh"]
    assert (obs, SDC.refPeriod, Literal("2026", datatype=XSD.gYear)) in g
    assert (obs, SDC.hourOfDay, Literal(23, datatype=XSD.integer)) in g
    assert {p.datatype for p in g.objects(None, SDC.refPeriod)} == {XSD.gYear}
    assert conforms(g)


def test_hour_of_day_profile_adds_dimension_to_structure():
    g = build(HOURLY, hour_of_day_profile=True)
    dims = set(g.objects(None, QB.dimension))
    assert SDC.hourOfDay in dims
    assert SDC.hourOfDay not in set(build(HOURLY).objects(None, QB.dimension))


@pytest.mark.parametrize("bad", ["2026-03-01T07:00:00", "2026-01-01T07:30:00", "2026-01-01T24:00:00", "2026-01-01"])
def test_hour_of_day_profile_rejects_non_convention_datetimes(bad):
    with pytest.raises(ValueError, match="hour-of-day convention"):
        build(HOURLY.assign(datetime=[bad, "2026-01-01T01:00:00"]), hour_of_day_profile=True)


@pytest.mark.parametrize("name", ["g.ttl", "g.ttl.xz", "g.nt", "g.nt.xz"])
def test_write_read_graph_by_suffix(tmp_path, name):
    from sdc_rdf import read_graph, write_graph

    g = build(HOURLY, hour_of_day_profile=True)
    out = write_graph(g, tmp_path / name)
    assert out.read_bytes().startswith(b"\xfd7zXZ\x00") == name.endswith(".xz")
    assert read_graph(out).isomorphic(g)


def test_ntriples_output_is_sorted(tmp_path):
    from sdc_rdf import write_graph

    lines = write_graph(build(STANDARD), tmp_path / "g.nt").read_text().splitlines()
    assert lines == sorted(lines)


def test_write_graph_rejects_unknown_suffix(tmp_path):
    from sdc_rdf import write_graph

    with pytest.raises(ValueError, match="expected a .nt"):
        write_graph(build(STANDARD), tmp_path / "g.jsonld")


def test_regenerated_ntriples_are_byte_identical(tmp_path):
    from sdc_rdf import write_graph

    a = write_graph(build(HOURLY, hour_of_day_profile=True), tmp_path / "a.nt").read_bytes()
    b = write_graph(build(HOURLY, hour_of_day_profile=True), tmp_path / "b.nt").read_bytes()
    assert a == b and b"_:" not in a


STATIC = ENERGY.assign(datetime=["2030-01-01", "2030-01-01"])


def test_year_anchor_emits_year():
    g = build(STATIC, year_anchor=True)
    assert {p for p in g.objects(None, SDC.refPeriod)} == {Literal("2030", datatype=XSD.gYear)}
    assert conforms(g)


def test_year_anchor_rejects_real_dates():
    with pytest.raises(ValueError, match="year-anchor convention"):
        build(ENERGY.assign(datetime=["2030-05-29", "2030-01-01"]), year_anchor=True)


def test_period_conventions_are_exclusive():
    with pytest.raises(ValueError, match="mutually exclusive"):
        build(STATIC, year_anchor=True, hour_of_day_profile=True)


def _round_trip(df: pd.DataFrame, **kw) -> pd.DataFrame:
    from sdc_rdf import cube_to_long_format

    g = Graph()
    ds = long_format_to_cube(g, df, dataset_id="test_ds", label="Test", **kw)
    return cube_to_long_format(g, ds)


def _expected(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    out = df.copy()
    out["moe"] = pd.to_numeric(out["moe"]).astype(float)
    out["value"] = out["value"].astype(float)
    return out.sort_values(keys, ignore_index=True)


@pytest.mark.parametrize(
    "frame,kw,keys",
    [
        (STANDARD, {}, ["geoid", "year", "measure"]),
        (ENERGY.assign(datetime=["2026-05-29", "2026-05-30"]), {}, ["geoid", "datetime", "scenario", "measure"]),
        (HOURLY, {"hour_of_day_profile": True}, ["geoid", "datetime", "scenario", "measure"]),
        (STATIC, {"year_anchor": True}, ["geoid", "datetime", "scenario", "measure"]),
    ],
    ids=["standard", "datetime", "hour_of_day", "year_anchor"],
)
def test_cube_round_trip(frame, kw, keys):
    back = _round_trip(frame, **kw)
    pd.testing.assert_frame_equal(back, _expected(frame, keys), check_dtype=False)
    assert list(back.columns) == list(frame.columns)


def test_round_trip_preserves_float_precision():
    frame = HOURLY.assign(value=[31.935052636757312, 5e-06])
    back = _round_trip(frame, hour_of_day_profile=True)
    assert back["value"].tolist() == [31.935052636757312, 5e-06]  # hours 00, 23


def test_default_scenario_recorded_and_validated():
    g = Graph()
    ds = long_format_to_cube(g, ENERGY, dataset_id="d", label="L", default_scenario="run_b")
    assert g.value(ds, SDC.defaultScenario) == SDCID["scenario/run_b"]
    with pytest.raises(ValueError, match="default_scenario"):
        long_format_to_cube(Graph(), ENERGY, dataset_id="d", label="L", default_scenario="nope")


def test_inverse_requires_period_convention():
    from sdc_rdf import cube_to_long_format

    g = Graph()
    ds = long_format_to_cube(g, STANDARD, dataset_id="d", label="L")
    g.remove((ds, SDC.periodConvention, None))
    with pytest.raises(ValueError, match="periodConvention"):
        cube_to_long_format(g, ds)


def test_read_csv_exact_keeps_float_bits_and_text_ids(tmp_path):
    from sdc_rdf import read_csv_exact

    path = tmp_path / "x.csv"
    path.write_text("geoid,facility_id,lat,value\n01001,0042,36.685957525459116,1490.3700000000001\n")
    df = read_csv_exact(path)
    assert df["geoid"][0] == "01001" and df["facility_id"][0] == "0042"
    assert repr(float(df["lat"][0])) == "36.685957525459116"
    assert repr(float(df["value"][0])) == "1490.3700000000001"


def test_integer_values_round_trip_as_integers():
    frame = STATIC.assign(value=[24, 31])
    back = _round_trip(frame, year_anchor=True)
    assert pd.api.types.is_integer_dtype(back["value"]) and sorted(back["value"]) == [24, 31]
    floats = _round_trip(STATIC.assign(value=[24.0, 31.0]), year_anchor=True)
    assert pd.api.types.is_float_dtype(floats["value"])
