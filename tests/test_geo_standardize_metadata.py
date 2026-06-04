"""Phase 1 harness: verify geo_standardize metadata is complete, consistent,
and produces correct intensive _geo20 values through the real standardize_all.
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from sdc_census10to20 import convert, parse_geo_standardize_info

REPO_ROOT = Path(__file__).resolve().parents[1]

# Percents recompute exactly from published in-frame counts.
EXACT_RATIO_DATASETS = ["demographics/Age", "demographics/Race", "demographics/Gender"]

# Intensive measures replicate the area-dominant parent (median/mean/replicate).
REPLICATE_DATASETS = [
    "financial_well_being/Household Income",
    "education/Years of Schooling",
    "financial_well_being/Income Inequality",
    "transportation/Population Characteristics",
    "demographics/Cooperative extension",
    "financial_well_being/Employment Rates",
]

# Composite index skipped here; recomputed from standardized inputs in Phase 2.
INDEX_SKIP_DATASETS = ["financial_well_being/Material_Deprivation"]

# Percents recompute exactly from a denominator melted into the frame as a helper
# count (dropped from output via input_only auto-derive).
EXACT_RATIO_FRAMECHANGE_DATASETS = [
    "demographics/Veteran",
    "demographics/Language",
    "education/Postsecondary",
    "health/System Usage and Insurance/Without Health Insurance",
    "financial_well_being/Employment Rates",
    "broadband/Household Broadband",
]

# Density measures recomputed as count_geo20 / (area20 / area_divisor); the count
# is melted into the frame as a helper and dropped from output.
DENSITY_DATASETS = ["demographics/Population Density"]

ALL_DATASETS = list(dict.fromkeys(
    EXACT_RATIO_DATASETS
    + REPLICATE_DATASETS
    + INDEX_SKIP_DATASETS
    + EXACT_RATIO_FRAMECHANGE_DATASETS
    + DENSITY_DATASETS
))

# Where each dataset's census_standardize=True write_data call lives.
STANDARDIZE_FILE = {d: "code/distribution/ingest.py" for d in ALL_DATASETS}
STANDARDIZE_FILE["financial_well_being/Material_Deprivation"] = "code/distribution/prepare.py"
STANDARDIZE_FILE["broadband/Household Broadband"] = "code/distribution/prepare.py"

VALID_TYPES = {"count", "ratio", "rate", "median", "mean", "replicate", "density", "index"}
REPLICATE_TYPES = {"median", "mean", "replicate"}


def _measure_info(dataset: str) -> dict:
    path = REPO_ROOT / dataset / "data/distribution/measure_info.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _measure_keys(mi: dict) -> list:
    """Top-level measure keys, excluding underscore-prefixed metadata (_references)."""
    return [k for k in mi if not k.startswith("_")]


def _base(key: str) -> str:
    return key[: -len("_geo20")] if key.endswith("_geo20") else key


@pytest.fixture
def split_crosswalk() -> pd.DataFrame:
    # Parent 51001000020 splits into .002 (area 600) and .003 (area 400).
    return pd.DataFrame({
        "geoid20":     ["51001000002", "51001000003"],
        "geoid10":     ["51001000020", "51001000020"],
        "area20":      [600, 400],
        "area10":      [1000, 1000],
        "area_part":   [600, 400],
        "type_change": ["split", "split"],
    })


def _synthetic_frame(parent, measure_values):
    rows = [(parent, m, v) for m, v in measure_values.items()]
    return pd.DataFrame({
        "geoid":       [r[0] for r in rows],
        "year":        [2018] * len(rows),
        "measure":     [r[1] for r in rows],
        "value":       [r[2] for r in rows],
        "moe":         [pd.NA] * len(rows),
        "region_type": ["tract"] * len(rows),
    })


@pytest.mark.parametrize("dataset", ALL_DATASETS)
def test_every_measure_has_valid_geo_standardize(dataset):
    mi = _measure_info(dataset)
    keys = _measure_keys(mi)
    assert keys, f"{dataset}: no measures found"
    specs = parse_geo_standardize_info(mi)
    for key in keys:
        base = _base(key)
        assert base in specs, f"{dataset}: {key} missing geo_standardize block"
        mtype = specs[base].get("measure_type")
        assert mtype in VALID_TYPES, f"{dataset}: {key} bad measure_type {mtype!r}"


@pytest.mark.parametrize("dataset", EXACT_RATIO_DATASETS)
def test_ratio_specs_reference_published_counts(dataset):
    mi = _measure_info(dataset)
    specs = parse_geo_standardize_info(mi)
    count_bases = {b for b, s in specs.items() if s.get("measure_type") == "count"}
    ratios = {b: s for b, s in specs.items() if s.get("measure_type") in ("ratio", "rate")}
    assert ratios, f"{dataset}: no ratio measures in metadata"
    for base, spec in ratios.items():
        num, den = spec.get("numerator"), spec.get("denominator")
        assert num and den, f"{dataset}: {base} ratio missing numerator/denominator"
        assert "scale" in spec, f"{dataset}: {base} ratio missing scale"
        assert spec["scale"] > 0, f"{dataset}: {base} scale must be positive, got {spec['scale']!r}"
        assert num in count_bases, f"{dataset}: {base} numerator {num!r} not a published count"
        assert den in count_bases, f"{dataset}: {base} denominator {den!r} not a published count"


@pytest.mark.parametrize("dataset", EXACT_RATIO_DATASETS)
def test_ratios_recompute_to_parent_value(dataset, monkeypatch, split_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: split_crosswalk)
    mi = _measure_info(dataset)
    specs = parse_geo_standardize_info(mi)
    counts = sorted(b for b, s in specs.items() if s.get("measure_type") == "count")
    ratios = {b: s for b, s in specs.items() if s.get("measure_type") in ("ratio", "rate")}
    assert ratios, f"{dataset}: no ratio measures in metadata"
    values = {c: 100.0 * (i + 1) for i, c in enumerate(counts)}
    measure_values = {c: values[c] for c in counts}
    measure_values.update({b: 0.0 for b in ratios})  # ratio input recomputed
    data = _synthetic_frame("51001000020", measure_values)
    out = convert.standardize_all(data, measure_info=mi)
    for base, spec in ratios.items():
        expected = spec["scale"] * values[spec["numerator"]] / values[spec["denominator"]]
        got = out[out["measure"] == f"{base}_geo20"].set_index("geoid")["value"]
        assert got["51001000002"] == pytest.approx(expected), f"{dataset}:{base} A"
        assert got["51001000003"] == pytest.approx(expected), f"{dataset}:{base} B"


@pytest.mark.parametrize("dataset", REPLICATE_DATASETS)
def test_replicate_measures_take_parent_value(dataset, monkeypatch, split_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: split_crosswalk)
    mi = _measure_info(dataset)
    specs = parse_geo_standardize_info(mi)
    repl = sorted(b for b, s in specs.items() if s.get("measure_type") in REPLICATE_TYPES)
    assert repl, f"{dataset}: no replicate/median/mean measures in metadata"
    values = {b: 10.0 * (i + 1) for i, b in enumerate(repl)}
    data = _synthetic_frame("51001000020", values)
    out = convert.standardize_all(data, measure_info=mi)
    for base in repl:
        got = out[out["measure"] == f"{base}_geo20"].set_index("geoid")["value"]
        assert got["51001000002"] == pytest.approx(values[base]), f"{dataset}:{base} A"
        assert got["51001000003"] == pytest.approx(values[base]), f"{dataset}:{base} B"


@pytest.mark.parametrize("dataset", INDEX_SKIP_DATASETS)
def test_index_measures_not_interpolated(dataset, monkeypatch, split_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: split_crosswalk)
    mi = _measure_info(dataset)
    specs = parse_geo_standardize_info(mi)
    idx = sorted(b for b, s in specs.items() if s.get("measure_type") == "index")
    assert idx, f"{dataset}: no index measures in metadata"
    data = _synthetic_frame("51001000020", {b: 0.5 for b in idx})
    out = convert.standardize_all(data, measure_info=mi)
    measures = set(out["measure"])
    for base in idx:
        assert f"{base}_geo10" in measures, f"{dataset}:{base} _geo10 should exist"
        assert f"{base}_geo20" not in measures, f"{dataset}:{base} _geo20 should be skipped"


@pytest.mark.parametrize("dataset", EXACT_RATIO_FRAMECHANGE_DATASETS)
def test_framechange_ratios_recompute_and_drop_helpers(dataset, monkeypatch, split_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: split_crosswalk)
    mi = _measure_info(dataset)
    specs = parse_geo_standardize_info(mi)
    helpers = convert.referenced_helper_measures(mi)
    assert helpers, f"{dataset}: expected helper (input-only) counts referenced by ratios"
    ratios = {b: s for b, s in specs.items() if s.get("measure_type") in ("ratio", "rate")}
    assert ratios, f"{dataset}: no ratio measures"

    counts = set()
    for s in ratios.values():
        counts.add(s["numerator"])
        counts.add(s["denominator"])
    values = {c: 100.0 * (i + 1) for i, c in enumerate(sorted(counts))}
    measure_values = dict(values)
    measure_values.update({b: 0.0 for b in ratios})  # ratio input recomputed
    data = _synthetic_frame("51001000020", measure_values)

    out = convert.standardize_all(data, measure_info=mi)  # auto-derives input_only
    out_measures = set(out["measure"])
    for base, spec in ratios.items():
        expected = spec["scale"] * values[spec["numerator"]] / values[spec["denominator"]]
        got = out[out["measure"] == f"{base}_geo20"].set_index("geoid")["value"]
        assert got["51001000002"] == pytest.approx(expected), f"{dataset}:{base} A"
        assert got["51001000003"] == pytest.approx(expected), f"{dataset}:{base} B"
    for h in helpers:
        assert f"{h}_geo20" not in out_measures, f"{dataset}: helper {h} leaked _geo20"
        assert f"{h}_geo10" not in out_measures, f"{dataset}: helper {h} leaked _geo10"


@pytest.mark.parametrize("dataset", DENSITY_DATASETS)
def test_density_recompute_and_drop_helper(dataset, monkeypatch, split_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: split_crosswalk)
    mi = _measure_info(dataset)
    specs = parse_geo_standardize_info(mi)
    helpers = convert.referenced_helper_measures(mi)
    assert helpers, f"{dataset}: expected a helper (input-only) count for density"
    dens = {b: s for b, s in specs.items() if s.get("measure_type") == "density"}
    assert dens, f"{dataset}: no density measures"

    counts = {s["count"] for s in dens.values()}
    # pop == area10 (1000 in the fixture) so count_geo20/area20 == 1.0 per child;
    # then density == area_divisor.
    measure_values = {c: 1000.0 for c in counts}
    measure_values.update({b: 0.0 for b in dens})
    data = _synthetic_frame("51001000020", measure_values)

    out = convert.standardize_all(data, measure_info=mi)  # auto-derives input_only
    out_measures = set(out["measure"])
    for base, spec in dens.items():
        ad = spec.get("area_divisor", 1.0)
        got = out[out["measure"] == f"{base}_geo20"].set_index("geoid")["value"]
        assert got["51001000002"] == pytest.approx(ad), f"{dataset}:{base} A"
        assert got["51001000003"] == pytest.approx(ad), f"{dataset}:{base} B"
    for h in helpers:
        assert f"{h}_geo20" not in out_measures, f"{dataset}: helper {h} leaked _geo20"
        assert f"{h}_geo10" not in out_measures, f"{dataset}: helper {h} leaked _geo10"


@pytest.mark.parametrize("dataset", ALL_DATASETS)
def test_standardize_call_wires_measure_info(dataset):
    rel = STANDARDIZE_FILE[dataset]
    src = (REPO_ROOT / dataset / rel).read_text(encoding="utf-8")
    assert "measure_info=" in src, f"{dataset}: {rel} write_data not passing measure_info="
