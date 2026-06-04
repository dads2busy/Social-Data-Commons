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


def test_parse_geo_standardize_info_reads_from_path(tmp_path):
    import json
    from sdc_census10to20 import convert
    p = tmp_path / "measure_info.json"
    p.write_text(json.dumps({
        "pop_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "_references": {"x": 1},
    }))
    specs = convert.parse_geo_standardize_info(p)
    assert specs["pop_count"]["measure_type"] == "count"
    assert "_references" not in specs


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


def test_standardize_all_accepts_measure_info_and_keeps_count_behavior(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({
        "geoid": ["51001000020"],
        "year": [2018],
        "measure": ["pop"],
        "value": [500.0],
        "moe": [pd.NA],
        "region_type": ["tract"],
    })
    mi = {"pop_geo20": {"geo_standardize": {"measure_type": "count"}}}
    out = convert.standardize_all(data, measure_info=mi)

    geo20 = out[out["measure"] == "pop_geo20"].set_index("geoid")["value"]
    # split by area_part/area10: child .002 = 300, child .003 = 200
    assert geo20["51001000002"] == pytest.approx(300.0)
    assert geo20["51001000003"] == pytest.approx(200.0)


def test_standardize_all_ratio_exact_recomputes_from_counts(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    # Parent .020 splits into .002/.003. Under-20=300, total=1000 -> 30% everywhere.
    data = pd.DataFrame({
        "geoid":       ["51001000020", "51001000020", "51001000020"],
        "year":        [2018, 2018, 2018],
        "measure":     ["under20_count", "total_count", "under20_percent"],
        "value":       [300.0, 1000.0, 30.0],
        "moe":         [pd.NA, pd.NA, pd.NA],
        "region_type": ["tract", "tract", "tract"],
    })
    mi = {
        "under20_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "total_count_geo20":   {"geo_standardize": {"measure_type": "count"}},
        "under20_percent_geo20": {"geo_standardize": {
            "measure_type": "ratio",
            "numerator": "under20_count",
            "denominator": "total_count",
            "scale": 100,
        }},
    }
    out = convert.standardize_all(data, measure_info=mi)
    pct = out[out["measure"] == "under20_percent_geo20"].set_index("geoid")["value"]
    assert pct["51001000002"] == pytest.approx(30.0)
    assert pct["51001000003"] == pytest.approx(30.0)


def test_standardize_all_ratio_population_weighted_split_is_exact(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    # Pure split parent .020 at 42% with weight (pop) 1000 -> each child 42%.
    data = pd.DataFrame({
        "geoid":       ["51001000020", "51001000020"],
        "year":        [2018, 2018],
        "measure":     ["uninsured_pct", "total_population"],
        "value":       [42.0, 1000.0],
        "moe":         [pd.NA, pd.NA],
        "region_type": ["tract", "tract"],
    })
    mi = {
        "total_population_geo20": {"geo_standardize": {"measure_type": "count"}},
        "uninsured_pct_geo20": {"geo_standardize": {
            "measure_type": "ratio", "weight": "total_population",
        }},
    }
    out = convert.standardize_all(data, measure_info=mi)
    pct = out[out["measure"] == "uninsured_pct_geo20"].set_index("geoid")["value"]
    assert pct["51001000002"] == pytest.approx(42.0)
    assert pct["51001000003"] == pytest.approx(42.0)


def test_standardize_all_ratio_population_weighted_merge_is_count_weighted(monkeypatch):
    from sdc_census10to20 import convert
    # Merge: 2020 tract 51999000300 fed by two 2010 parents with different pcts + pops.
    # Geoids are 11 chars (tract length) so standardize_all processes them.
    crosswalk = pd.DataFrame({
        "geoid20":     ["51999000300", "51999000300"],
        "geoid10":     ["51999000100", "51999000200"],
        "area10":      [1000, 1000],
        "area20":      [2000, 2000],
        "area_part":   [1000, 1000],   # each parent fully into 300
        "type_change": ["moved", "moved"],
    })
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: crosswalk)

    data = pd.DataFrame({
        "geoid":       ["51999000100", "51999000200", "51999000100", "51999000200"],
        "year":        [2018, 2018, 2018, 2018],
        "measure":     ["pct", "pct", "pop", "pop"],
        "value":       [10.0, 50.0, 300.0, 100.0],   # weighted avg = (10*300+50*100)/400 = 20
        "moe":         [pd.NA, pd.NA, pd.NA, pd.NA],
        "region_type": ["tract", "tract", "tract", "tract"],
    })
    mi = {
        "pop_geo20": {"geo_standardize": {"measure_type": "count"}},
        "pct_geo20": {"geo_standardize": {"measure_type": "ratio", "weight": "pop"}},
    }
    out = convert.standardize_all(data, measure_info=mi)
    pct = out[out["measure"] == "pct_geo20"].set_index("geoid")["value"]
    assert pct["51999000300"] == pytest.approx(20.0)


def test_standardize_all_median_replicates_dominant_parent(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    # Parent .020 (median income 70000) splits into .002/.003 -> both 70000.
    data = pd.DataFrame({
        "geoid":       ["51001000020"],
        "year":        [2018],
        "measure":     ["median_income"],
        "value":       [70000.0],
        "moe":         [pd.NA],
        "region_type": ["tract"],
    })
    mi = {"median_income_geo20": {"geo_standardize": {
        "measure_type": "median", "replicate": True,
    }}}
    out = convert.standardize_all(data, measure_info=mi)
    med = out[out["measure"] == "median_income_geo20"].set_index("geoid")["value"]
    assert med["51001000002"] == pytest.approx(70000.0)
    assert med["51001000003"] == pytest.approx(70000.0)


def test_standardize_all_density_recomputed_from_count_and_area20(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    # Parent .020: population 1000 splits 600/400 into children with area20 600/400.
    # child .002: pop 600 / area20 600 = 1.0 ; child .003: pop 400 / area20 400 = 1.0
    data = pd.DataFrame({
        "geoid":       ["51001000020", "51001000020"],
        "year":        [2018, 2018],
        "measure":     ["pop_count", "pop_density"],
        "value":       [1000.0, 1.0],
        "moe":         [pd.NA, pd.NA],
        "region_type": ["tract", "tract"],
    })
    mi = {
        "pop_count_geo20":   {"geo_standardize": {"measure_type": "count"}},
        "pop_density_geo20": {"geo_standardize": {
            "measure_type": "density", "count": "pop_count",
        }},
    }
    out = convert.standardize_all(data, measure_info=mi)
    dens = out[out["measure"] == "pop_density_geo20"].set_index("geoid")["value"]
    assert dens["51001000002"] == pytest.approx(1.0)
    assert dens["51001000003"] == pytest.approx(1.0)


def test_standardize_all_index_is_not_interpolated(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({
        "geoid":       ["51001000020"],
        "year":        [2018],
        "measure":     ["hazard_index"],
        "value":       [0.7],
        "moe":         [pd.NA],
        "region_type": ["tract"],
    })
    mi = {"hazard_index_geo20": {"geo_standardize": {
        "measure_type": "index", "interpolate": False,
    }}}
    out = convert.standardize_all(data, measure_info=mi)
    measures = set(out["measure"])
    # original pre-2020 row is suffixed _geo10; NO interpolated _geo20 emitted
    assert "hazard_index_geo10" in measures
    assert "hazard_index_geo20" not in measures


def test_standardize_all_warns_when_no_metadata_uses_heuristic(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({
        "geoid": ["51001000020"], "year": [2018], "measure": ["mystery_count"],
        "value": [500.0], "moe": [pd.NA], "region_type": ["tract"],
    })
    with pytest.warns(UserWarning, match="no geo_standardize metadata"):
        out = convert.standardize_all(data, measure_info={})  # empty -> heuristic
    # 'mystery_count' heuristically a count -> still produces a _geo20
    assert "mystery_count_geo20" in set(out["measure"])


def test_standardize_all_raises_on_unknown_measure_type(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({
        "geoid": ["51001000020"], "year": [2018], "measure": ["weird"],
        "value": [1.0], "moe": [pd.NA], "region_type": ["tract"],
    })
    mi = {"weird_geo20": {"geo_standardize": {"measure_type": "bogus"}}}
    with pytest.raises(ValueError, match="unknown measure_type"):
        convert.standardize_all(data, measure_info=mi)


def test_standardize_all_mixed_measure_types_integration(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    g = "51001000020"  # splits 600/400 into .002/.003
    rows = [
        (g, "under20_count", 300.0),
        (g, "total_count",   1000.0),
        (g, "under20_pct",   30.0),    # exact ratio -> 30 / 30
        (g, "uninsured_pct", 42.0),    # weighted ratio -> 42 / 42
        (g, "median_income", 70000.0), # replicate -> 70000 / 70000
        (g, "pop_density",   1.0),     # 600/600, 400/400 -> 1.0 / 1.0
        (g, "hazard_index",  0.7),     # skipped
    ]
    data = pd.DataFrame({
        "geoid":       [r[0] for r in rows],
        "year":        [2018] * len(rows),
        "measure":     [r[1] for r in rows],
        "value":       [r[2] for r in rows],
        "moe":         [pd.NA] * len(rows),
        "region_type": ["tract"] * len(rows),
    })
    mi = {
        "under20_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "total_count_geo20":   {"geo_standardize": {"measure_type": "count"}},
        "under20_pct_geo20":   {"geo_standardize": {"measure_type": "ratio",
            "numerator": "under20_count", "denominator": "total_count", "scale": 100}},
        "uninsured_pct_geo20": {"geo_standardize": {"measure_type": "ratio",
            "weight": "total_count"}},
        "median_income_geo20": {"geo_standardize": {"measure_type": "median"}},
        "pop_density_geo20":   {"geo_standardize": {"measure_type": "density",
            "count": "under20_count"}},  # using under20_count as the extensive count for the test
        "hazard_index_geo20":  {"geo_standardize": {"measure_type": "index",
            "interpolate": False}},
    }
    out = convert.standardize_all(data, measure_info=mi)
    g20 = out[out["measure"].str.endswith("_geo20")]
    by = lambda m: g20[g20["measure"] == m].set_index("geoid")["value"]

    assert by("under20_pct_geo20")["51001000002"] == pytest.approx(30.0)
    assert by("uninsured_pct_geo20")["51001000003"] == pytest.approx(42.0)
    assert by("median_income_geo20")["51001000002"] == pytest.approx(70000.0)
    # density uses under20_count(300) split 180/120 over area20 600/400 = 0.3/0.3
    assert by("pop_density_geo20")["51001000002"] == pytest.approx(0.3)
    assert "hazard_index_geo20" not in set(g20["measure"])


def test_standardize_all_replicate_type_replicates_dominant_parent(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({
        "geoid": ["51001000020"], "year": [2018], "measure": ["some_score"],
        "value": [0.42], "moe": [pd.NA], "region_type": ["tract"],
    })
    mi = {"some_score_geo20": {"geo_standardize": {"measure_type": "replicate"}}}
    out = convert.standardize_all(data, measure_info=mi)
    s = out[out["measure"] == "some_score_geo20"].set_index("geoid")["value"]
    assert s["51001000002"] == pytest.approx(0.42)
    assert s["51001000003"] == pytest.approx(0.42)
