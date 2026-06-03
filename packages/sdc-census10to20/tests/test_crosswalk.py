"""Tests for sdc_census10to20.crosswalk."""

from __future__ import annotations

import pandas as pd
import pytest

from sdc_census10to20 import crosswalk as cw


def test_bound_changes_returns_expected_columns(monkeypatch, synthetic_tract_relationship_csv):
    monkeypatch.setattr(pd, "read_csv", lambda *a, **k: synthetic_tract_relationship_csv)

    out = cw.get_2010_2020_bound_changes(res="tract")

    assert list(out.columns) == [
        "geoid20",
        "geoid10",
        "area20",
        "area10",
        "area_part",
        "type_change",
    ]


def test_bound_changes_classifies_same_split_moved(monkeypatch, synthetic_tract_relationship_csv):
    monkeypatch.setattr(pd, "read_csv", lambda *a, **k: synthetic_tract_relationship_csv)

    out = cw.get_2010_2020_bound_changes(res="tract")

    by_geoid10 = out.set_index("geoid10")["type_change"]
    assert by_geoid10.loc["51001000010"] == "same"
    assert (by_geoid10.loc["51001000020"] == "split").all()
    assert (by_geoid10.loc["51001000030"] == "moved").all()


def test_bound_changes_filters_to_supplied_geoids(monkeypatch, synthetic_tract_relationship_csv):
    monkeypatch.setattr(pd, "read_csv", lambda *a, **k: synthetic_tract_relationship_csv)

    out = cw.get_2010_2020_bound_changes(res="tract", geoids=["51001000010"])

    assert set(out["geoid10"]) == {"51001000010"}


def test_bound_changes_rejects_unknown_resolution():
    with pytest.raises(ValueError, match='"tract" or "block group"'):
        cw.get_2010_2020_bound_changes(res="county")


def test_create_crosswalk_skips_unknown_resolution(
    capsys, monkeypatch, synthetic_tract_relationship_csv
):
    monkeypatch.setattr(pd, "read_csv", lambda *a, **k: synthetic_tract_relationship_csv)

    out = cw.create_crosswalk(["51001000010", "51001"])  # 11-char + 5-char

    captured = capsys.readouterr()
    assert "crosswalk not available for resolution: 5" in captured.out
    assert "geoid10" in out.columns


def test_relationship_file_fetched_once(monkeypatch, synthetic_tract_relationship_csv):
    calls = {"n": 0}

    def fake_read_csv(*a, **k):
        calls["n"] += 1
        return synthetic_tract_relationship_csv

    monkeypatch.setattr(pd, "read_csv", fake_read_csv)

    cw.get_2010_2020_bound_changes(res="tract")
    cw.get_2010_2020_bound_changes(res="tract", geoids=["51001000010"])

    assert calls["n"] == 1  # downloaded once, reused from cache


def test_load_relationship_returns_independent_copies(monkeypatch, synthetic_tract_relationship_csv):
    monkeypatch.setattr(pd, "read_csv", lambda *a, **k: synthetic_tract_relationship_csv)

    f1 = cw._load_relationship("tract", "51")
    f2 = cw._load_relationship("tract", "51")
    assert f1 is not f2  # fresh copy each call

    f1.loc[f1.index[0], "area10"] = -1  # mutate one copy
    f3 = cw._load_relationship("tract", "51")
    assert (f3["area10"] != -1).all()  # cache not corrupted


def test_create_crosswalk_empty_when_no_supported_resolutions(monkeypatch):
    out = cw.create_crosswalk(["51001"])  # only county-length

    assert out.empty
    assert list(out.columns) == [
        "geoid20",
        "geoid10",
        "area20",
        "area10",
        "area_part",
        "type_change",
    ]
