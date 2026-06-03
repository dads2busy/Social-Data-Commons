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
    """A split source tract splits its value among children by source-area share."""
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({"geoid": ["51001000020"], "value": [500.0]})
    out = convert.convert_2010_to_2020_bounds(data)

    vals = out.set_index("geoid")["value"]
    # area_part/area10: child A = 500*600/1000 = 300; child B = 500*400/1000 = 200
    assert vals["51001000002"] == pytest.approx(300.0)
    assert vals["51001000003"] == pytest.approx(200.0)
    assert vals[["51001000002", "51001000003"]].sum() == pytest.approx(500.0)


def test_convert_area_weights_moved_values(monkeypatch, fake_crosswalk):
    """Moved relationships scale by area_part / area10 (source-area share)."""
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({"geoid": ["51001000030"], "value": [1200.0]})
    out = convert.convert_2010_to_2020_bounds(data)

    # Each moved row: area_part=400, area10=1000 -> 1200 * 0.4 = 480
    moved = out[out["geoid"].isin(["51001000004", "51001000005"])]
    assert moved["value"].tolist() == pytest.approx([480.0, 480.0])


def test_convert_conserves_total_over_complete_crosswalk(monkeypatch):
    """When a source's overlaps tile it (sum area_part == area10), the total is preserved."""
    crosswalk = pd.DataFrame({
        "geoid20":    ["51001000101", "51001000102"],
        "geoid10":    ["51001000100", "51001000100"],
        "area10":     [1000, 1000],
        "area20":     [600, 400],
        "area_part":  [600, 400],   # sums to area10 -> fully tiled
        "type_change": ["split", "split"],
    })
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: crosswalk)

    data = pd.DataFrame({"geoid": ["51001000100"], "value": [1000.0]})
    out = convert.convert_2010_to_2020_bounds(data)
    assert out["value"].sum() == pytest.approx(1000.0)


def test_convert_conserves_county_total(monkeypatch):
    """A county's total is unchanged by reprojection (county boundary fixed).

    Two 2010 sources fully tile into 2020 tracts within the same county,
    including a 2020 tract (M) fed by both sources (a merge).
    """
    crosswalk = pd.DataFrame({
        "geoid20":    ["51999000A", "51999000M", "51999000M", "51999000D"],
        "geoid10":    ["51999000S1", "51999000S1", "51999000S2", "51999000S2"],
        "area10":     [1000, 1000, 1000, 1000],
        "area20":     [600, 1000, 1000, 800],
        "area_part":  [600, 400, 600, 400],  # S1: 600+400=1000; S2: 600+400=1000
        "type_change": ["split", "moved", "moved", "split"],
    })
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: crosswalk)

    data = pd.DataFrame({"geoid": ["51999000S1", "51999000S2"], "value": [1000.0, 2000.0]})
    out = convert.convert_2010_to_2020_bounds(data)

    # county boundary fixed -> all output geoids are in county 51999, total preserved
    assert (out["geoid"].str[:5] == "51999").all()
    assert out["value"].sum() == pytest.approx(3000.0)
    vals = out.set_index("geoid")["value"]
    assert vals["51999000A"] == pytest.approx(600.0)   # 1000 * 600/1000
    assert vals["51999000M"] == pytest.approx(1600.0)  # 1000*400/1000 + 2000*600/1000
    assert vals["51999000D"] == pytest.approx(800.0)   # 2000 * 400/1000


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


def test_parse_geo_standardize_info_strips_suffix_and_extracts_block():
    from sdc_census10to20 import convert
    mi = {
        "_references": {"ignored": True},
        "age_under_20_percent_geo20": {
            "label": "Under 20",
            "geo_standardize": {
                "measure_type": "ratio",
                "numerator": "age_under_20_count",
                "denominator": "age_total_count",
                "scale": 100,
            },
        },
        "age_total_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "no_block_geo20": {"label": "no geo_standardize here"},
    }
    specs = convert.parse_geo_standardize_info(mi)
    assert specs["age_under_20_percent"]["measure_type"] == "ratio"
    assert specs["age_under_20_percent"]["numerator"] == "age_under_20_count"
    assert specs["age_total_count"]["measure_type"] == "count"
    assert "no_block" not in specs          # no geo_standardize block
    assert "_references" not in specs        # underscore keys skipped
