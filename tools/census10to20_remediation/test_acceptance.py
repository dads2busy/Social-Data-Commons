import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import pytest
from acceptance_test import check_conservation

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(tmp_path, rows):
    df = pd.DataFrame(rows, columns=["geoid", "year", "measure", "value", "region_type"])
    df["moe"] = pd.NA
    p = tmp_path / "d.csv.xz"
    df.to_csv(p, index=False)
    return p


def test_check_conservation_passes_when_county_totals_match(tmp_path):
    rows = [
        ("51001000001", 2018, "pop_count_geo10", 1000, "tract"),
        ("51001000002", 2018, "pop_count_geo20", 600, "tract"),
        ("51001000003", 2018, "pop_count_geo20", 400, "tract"),
    ]
    rep = check_conservation(_write(tmp_path, rows))
    assert rep["status"] == "pass"
    assert rep["max_ratio"] == pytest.approx(1.0)


def test_check_conservation_fails_on_inflation(tmp_path):
    rows = [
        ("51001000001", 2018, "pop_count_geo10", 1000, "tract"),
        ("51001000002", 2018, "pop_count_geo20", 600, "tract"),
        ("51001000003", 2018, "pop_count_geo20", 600, "tract"),
    ]
    rep = check_conservation(_write(tmp_path, rows))
    assert rep["status"] == "fail"
    assert rep["max_ratio"] == pytest.approx(1.2)


def test_check_conservation_fails_on_deflation(tmp_path):
    # geo20 sum (900) < geo10 sum (1000) -> ratio 0.9 -> two-sided fail
    rows = [
        ("51001000001", 2018, "pop_count_geo10", 1000, "tract"),
        ("51001000002", 2018, "pop_count_geo20", 500, "tract"),
        ("51001000003", 2018, "pop_count_geo20", 400, "tract"),
    ]
    rep = check_conservation(_write(tmp_path, rows))
    assert rep["status"] == "fail"
    assert rep["max_ratio"] == pytest.approx(0.9)


def test_check_conservation_passes_within_5pct(tmp_path):
    # ratio 1.045 (real age_65+ subgroup boundary-leakage residual) -> within 5% -> pass
    rows = [
        ("51001000001", 2018, "pop_count_geo10", 1000, "tract"),
        ("51001000002", 2018, "pop_count_geo20", 627, "tract"),
        ("51001000003", 2018, "pop_count_geo20", 418, "tract"),
    ]
    rep = check_conservation(_write(tmp_path, rows))
    assert rep["status"] == "pass"


def test_check_conservation_fails_just_over_5pct(tmp_path):
    # ratio 1.06 -> exceeds 5% -> fail (gate stays sensitive above the residual band)
    rows = [
        ("51001000001", 2018, "pop_count_geo10", 1000, "tract"),
        ("51001000002", 2018, "pop_count_geo20", 636, "tract"),
        ("51001000003", 2018, "pop_count_geo20", 424, "tract"),
    ]
    rep = check_conservation(_write(tmp_path, rows))
    assert rep["status"] == "fail"
    assert rep["max_ratio"] == pytest.approx(1.06)


def test_check_ratio_consistency_passes_when_percent_matches_counts(tmp_path):
    rows = [
        ("51001000002", 2018, "u20_count_geo20", 30, "tract"),
        ("51001000002", 2018, "tot_count_geo20", 100, "tract"),
        ("51001000002", 2018, "u20_pct_geo20", 30.0, "tract"),  # 100*30/100
    ]
    measure_info = {
        "u20_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "tot_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "u20_pct_geo20": {"geo_standardize": {"measure_type": "ratio",
            "numerator": "u20_count", "denominator": "tot_count", "scale": 100}},
    }
    from acceptance_test import check_ratio_consistency
    rep = check_ratio_consistency(_write(tmp_path, rows), measure_info)
    assert rep["status"] == "pass"


def test_check_ratio_consistency_fails_on_diluted_percent(tmp_path):
    rows = [
        ("51001000002", 2018, "u20_count_geo20", 30, "tract"),
        ("51001000002", 2018, "tot_count_geo20", 100, "tract"),
        ("51001000002", 2018, "u20_pct_geo20", 18.0, "tract"),  # diluted (should be 30)
    ]
    measure_info = {
        "u20_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "tot_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "u20_pct_geo20": {"geo_standardize": {"measure_type": "ratio",
            "numerator": "u20_count", "denominator": "tot_count", "scale": 100}},
    }
    from acceptance_test import check_ratio_consistency
    rep = check_ratio_consistency(_write(tmp_path, rows), measure_info)
    assert rep["status"] == "fail"


def test_check_ratio_consistency_ignores_non_tract_rows(tmp_path):
    import json
    rows = [
        ("51001000002", 2018, "sub_count_geo20", 30, "tract"),
        ("51001000002", 2018, "tot_count_geo20", 100, "tract"),
        ("51001000002", 2018, "sub_pct_geo20", 30.0, "tract"),        # tract: correct
        ("51_hd_07", 2018, "sub_count_geo20", 30, "health_district"),
        ("51_hd_07", 2018, "tot_count_geo20", 100, "health_district"),
        ("51_hd_07", 2018, "sub_pct_geo20", 18.0, "health_district"), # HD: wrong, must be IGNORED
    ]
    mi = {"sub_count_geo20": {"geo_standardize": {"measure_type": "count"}},
          "tot_count_geo20": {"geo_standardize": {"measure_type": "count"}},
          "sub_pct_geo20": {"geo_standardize": {"measure_type": "ratio",
              "numerator": "sub_count", "denominator": "tot_count", "scale": 100}}}
    p = _write(tmp_path, rows)
    from acceptance_test import check_ratio_consistency
    rep = check_ratio_consistency(p, mi)
    assert rep["status"] == "pass"  # HD mismatch ignored; tract is correct
