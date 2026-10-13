import json
from datetime import datetime, timezone

from sdc_core.sources.checks.compare import Row
from sdc_core.sources.checks.report import exit_code, render_json, render_table, sort_rows

NOW = datetime(2026, 10, 13, 14, 0, tzinfo=timezone.utc)


def row(status, source, pipeline, ours=None, upstream=None, detail=""):
    return Row(status, source, pipeline, ours, upstream, detail, NOW if source else None)


ROWS = [
    row("current", "acs5", "demographics/Race", 2024, 2024, "api"),
    row("not_tracked", None, "energy/X", detail="exploratory"),
    row("new_vintage", "acs5", "demographics/Age", 2023, 2024, "api"),
    row("error", "ookla", "broadband/Ookla Speed", 2025, None, "HTTP 503 after retry"),
    row("changed", "alice", "fwb/ALICE", detail="ETag changed (was x)"),
    row("baseline", "vera", "ps/Incarceration (HOI)", detail="Last-Modified recorded"),
    row("unverified", "hoi", "health/HOI", detail="https://vdh"),
    row("new_vintage", "acs5", "broadband/Household Broadband", 2023, 2024, "api"),
]


def test_sort_rows_action_first_then_source_then_pipeline():
    ordered = [(r.status, r.source, r.pipeline) for r in sort_rows(ROWS)]
    assert ordered == [
        ("new_vintage", "acs5", "broadband/Household Broadband"),
        ("new_vintage", "acs5", "demographics/Age"),
        ("changed", "alice", "fwb/ALICE"),
        ("unverified", "hoi", "health/HOI"),
        ("error", "ookla", "broadband/Ookla Speed"),
        ("baseline", "vera", "ps/Incarceration (HOI)"),
        ("current", "acs5", "demographics/Race"),
        ("not_tracked", None, "energy/X"),
    ]


def test_render_table_header_dashes_and_alignment():
    text = render_table(sort_rows(ROWS))
    lines = text.splitlines()
    assert lines[0].split() == ["STATUS", "SOURCE", "PIPELINE", "OURS", "UPSTREAM", "DETAIL"]
    assert "not_tracked  -" in lines[-1]
    assert "exploratory" in lines[-1]
    ours_col = lines[0].index("OURS")
    assert all(len(line) > ours_col for line in lines[1:])
    assert "2023  2024" in text


def test_render_json_shape():
    data = json.loads(render_json(ROWS[:2]))
    assert set(data[0]) == {"status", "source", "pipeline", "ours", "upstream", "detail", "fetched_at"}
    assert data[0]["fetched_at"] == "2026-10-13T14:00:00+00:00"
    assert data[1]["fetched_at"] is None
    assert render_json([]) == "[]\n"


def test_exit_code():
    assert exit_code([ROWS[0], ROWS[1], ROWS[5]]) == 0
    for action in ("new_vintage", "changed", "unverified", "error"):
        assert exit_code([ROWS[0], row(action, "s", "p")]) == 1
    assert exit_code([]) == 0
