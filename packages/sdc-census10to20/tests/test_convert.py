"""Tests for sdc_census10to20.convert."""

from __future__ import annotations

import pandas as pd
import pytest

from sdc_census10to20 import convert


@pytest.fixture
def fake_crosswalk() -> pd.DataFrame:
    """A pre-built crosswalk frame that bypasses get_2010_2020_bound_changes."""
    return pd.DataFrame(
        {
            "geoid20": [
                "51001000001",  # same
                "51001000002",  # split child A
                "51001000003",  # split child B
                "51001000004",  # moved partial A
                "51001000005",  # moved partial B
            ],
            "geoid10": [
                "51001000010",
                "51001000020",
                "51001000020",
                "51001000030",
                "51001000030",
            ],
            "area20": [1000, 600, 400, 600, 600],
            "area10": [1000, 1000, 1000, 1000, 1000],
            "area_part": [1000, 600, 400, 400, 400],
            "type_change": ["same", "split", "split", "moved", "moved"],
        }
    )


def test_convert_passes_same_values_through(monkeypatch, fake_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({"geoid": ["51001000010"], "value": [100.0]})
    out = convert.convert_2010_to_2020_bounds(data)

    assert out.loc[out["geoid"] == "51001000001", "value"].iloc[0] == 100.0


def test_convert_distributes_split_values(monkeypatch, fake_crosswalk):
    """A split source tract sends its full value to each child tract."""
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({"geoid": ["51001000020"], "value": [500.0]})
    out = convert.convert_2010_to_2020_bounds(data)

    children = out[out["geoid"].isin(["51001000002", "51001000003"])]
    assert (children["value"] == 500.0).all()


def test_convert_area_weights_moved_values(monkeypatch, fake_crosswalk):
    """Moved relationships scale by area_part / area20."""
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({"geoid": ["51001000030"], "value": [1200.0]})
    out = convert.convert_2010_to_2020_bounds(data)

    # Each moved row: area_part=400, area20=600 → pct_overlap = 2/3 → value 800
    moved = out[out["geoid"].isin(["51001000004", "51001000005"])]
    assert moved["value"].tolist() == pytest.approx([800.0, 800.0])


def test_convert_rejects_missing_geoids():
    data = pd.DataFrame({"geoid": [pd.NA, "51001000010"], "value": [1.0, 2.0]})
    with pytest.raises(ValueError, match="missing values"):
        convert.convert_2010_to_2020_bounds(data)


def test_convert_rejects_duplicate_geoids():
    data = pd.DataFrame(
        {"geoid": ["51001000010", "51001000010"], "value": [1.0, 2.0]}
    )
    with pytest.raises(ValueError, match="not unique"):
        convert.convert_2010_to_2020_bounds(data)


def test_standardize_all_emits_geo10_and_geo20_measures(monkeypatch, fake_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame(
        {
            "geoid": ["51001000010", "51001000020", "51001000030"],
            "year": [2018, 2018, 2018],
            "measure": ["pop", "pop", "pop"],
            "value": [100.0, 500.0, 1200.0],
            "moe": [pd.NA, pd.NA, pd.NA],
            "region_type": ["tract", "tract", "tract"],
        }
    )
    out = convert.standardize_all(data)

    measures = set(out["measure"])
    assert "pop_geo10" in measures
    assert "pop_geo20" in measures


def test_standardize_all_keeps_2020_rows_as_geo20_only(monkeypatch, fake_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame(
        {
            "geoid": ["51001000001"],
            "year": [2020],
            "measure": ["pop"],
            "value": [123.0],
            "moe": [pd.NA],
            "region_type": ["tract"],
        }
    )
    out = convert.standardize_all(data)

    assert set(out["measure"]) == {"pop_geo20"}
