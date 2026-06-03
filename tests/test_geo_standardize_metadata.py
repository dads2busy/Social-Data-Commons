"""Phase 1 harness: verify geo_standardize metadata is complete, consistent,
and produces correct intensive _geo20 values through the real standardize_all.

Scope: Phase 1A datasets (exact-ratio: percent denominators are published counts).
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from sdc_census10to20 import convert, parse_geo_standardize_info

REPO_ROOT = Path(__file__).resolve().parents[1]

# Phase 1A: datasets whose percent denominators are published counts in-frame.
PHASE_1A = ["demographics/Age", "demographics/Race", "demographics/Gender"]

VALID_TYPES = {"count", "ratio", "rate", "median", "mean", "density", "index"}


def _measure_info(dataset: str) -> dict:
    path = REPO_ROOT / dataset / "data/distribution/measure_info.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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


@pytest.mark.parametrize("dataset", PHASE_1A)
def test_every_geo20_measure_has_valid_geo_standardize(dataset):
    mi = _measure_info(dataset)
    geo20_keys = [k for k in mi if k.endswith("_geo20")]
    assert geo20_keys, f"{dataset}: no _geo20 measures found"
    specs = parse_geo_standardize_info(mi)
    for key in geo20_keys:
        base = key[: -len("_geo20")]
        assert base in specs, f"{dataset}: {key} missing geo_standardize block"
        mtype = specs[base].get("measure_type")
        assert mtype in VALID_TYPES, f"{dataset}: {key} bad measure_type {mtype!r}"


@pytest.mark.parametrize("dataset", PHASE_1A)
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


@pytest.mark.parametrize("dataset", PHASE_1A)
def test_ratios_recompute_to_parent_value(dataset, monkeypatch, split_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: split_crosswalk)
    mi = _measure_info(dataset)
    specs = parse_geo_standardize_info(mi)
    counts = sorted(b for b, s in specs.items() if s.get("measure_type") == "count")
    ratios = {b: s for b, s in specs.items() if s.get("measure_type") in ("ratio", "rate")}
    assert ratios, f"{dataset}: no ratio measures in metadata"

    # Distinct positive values per count so a numerator/denominator swap would fail.
    values = {c: 100.0 * (i + 1) for i, c in enumerate(counts)}
    parent = "51001000020"
    rows = [(parent, c, values[c]) for c in counts]
    rows += [(parent, b, 0.0) for b in ratios]  # ratio input value is recomputed, irrelevant
    data = pd.DataFrame({
        "geoid":       [r[0] for r in rows],
        "year":        [2018] * len(rows),
        "measure":     [r[1] for r in rows],
        "value":       [r[2] for r in rows],
        "moe":         [pd.NA] * len(rows),
        "region_type": ["tract"] * len(rows),
    })
    out = convert.standardize_all(data, measure_info=mi)

    for base, spec in ratios.items():
        expected = spec["scale"] * values[spec["numerator"]] / values[spec["denominator"]]
        got = out[out["measure"] == f"{base}_geo20"].set_index("geoid")["value"]
        assert got["51001000002"] == pytest.approx(expected), f"{dataset}:{base} child A"
        assert got["51001000003"] == pytest.approx(expected), f"{dataset}:{base} child B"


@pytest.mark.parametrize("dataset", PHASE_1A)
def test_ingest_wires_measure_info(dataset):
    src = (REPO_ROOT / dataset / "code/distribution/ingest.py").read_text(encoding="utf-8")
    assert "MEASURE_INFO" in src, f"{dataset}: ingest.py missing MEASURE_INFO constant"
    assert "measure_info=" in src, f"{dataset}: ingest.py write_data not passing measure_info"
