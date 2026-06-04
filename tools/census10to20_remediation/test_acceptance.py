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


def test_check_conservation_detects_committed_age_inflation():
    age = REPO_ROOT / "demographics/Age/data/distribution/ncr_cttrbg_census_acs_2009_2024_age_demographics.csv.xz"
    rep = check_conservation(age)
    assert rep["status"] == "fail"
    assert rep["max_ratio"] > 1.1
