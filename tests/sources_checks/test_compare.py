from datetime import datetime, timezone

import pytest

from sdc_core.sources.checks.compare import (
    ACTION_STATUSES,
    STATUS_ORDER,
    Observation,
    Row,
    compare,
    describe,
)

NOW = datetime(2026, 10, 13, 14, 0, tzinfo=timezone.utc)


def obs(kind, value, detail="d"):
    return Observation(kind=kind, value=value, fetched_at=NOW, detail=detail)


@pytest.mark.parametrize(
    "observation, latest, prior, expected",
    [
        (obs("vintage", 2024), 2023, None, "new_vintage"),
        (obs("vintage", 2024), 2024, None, "current"),
        (obs("vintage", 2023), 2024, None, "current"),
        (obs("content", "abc"), None, None, "baseline"),
        (obs("content", "abc"), None, obs("content", "xyz"), "changed"),
        (obs("content", "abc"), None, obs("content", "abc"), "current"),
        (obs("manual", None), None, None, "unverified"),
        (obs("manual", None), 2020, obs("content", "x"), "unverified"),
    ],
)
def test_compare_matrix(observation, latest, prior, expected):
    assert compare(observation, latest, prior) == expected


def test_vintage_without_latest_is_an_error():
    with pytest.raises(ValueError):
        compare(obs("vintage", 2024), None, None)


def test_content_prior_of_other_kind_is_baseline():
    assert compare(obs("content", "abc"), None, obs("vintage", 2020)) == "baseline"


def test_shared_source_two_pipelines_differ():
    o = obs("vintage", 2024)
    assert compare(o, 2023, None) == "new_vintage"
    assert compare(o, 2024, None) == "current"


def test_describe():
    o = obs("content", "new", detail="ETag")
    assert describe("changed", o, obs("content", "old")) == "ETag changed (was old)"
    assert describe("baseline", o, None) == "ETag recorded"
    assert describe("current", o, None) == "ETag"


def test_observation_roundtrip():
    o = obs("vintage", 2024, detail="api")
    assert Observation.from_dict(o.to_dict()) == o
    assert o.to_dict()["fetched_at"] == "2026-10-13T14:00:00+00:00"


def test_row_to_dict_serialises_datetime():
    r = Row("current", "acs5", "demographics/Age", 2024, 2024, "api", NOW)
    d = r.to_dict()
    assert d["fetched_at"] == "2026-10-13T14:00:00+00:00"
    assert Row("not_tracked", None, "energy/X", None, None, "", None).to_dict()["fetched_at"] is None


def test_status_order_and_actions():
    assert list(STATUS_ORDER) == [
        "new_vintage", "changed", "unverified", "error", "baseline", "current", "not_tracked",
    ]
    assert ACTION_STATUSES == {"new_vintage", "changed", "unverified", "error"}
