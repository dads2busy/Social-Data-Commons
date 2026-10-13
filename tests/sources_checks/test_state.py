import json
from datetime import datetime, timezone

import pytest

from sdc_core.sources.checks.compare import Observation
from sdc_core.sources.checks.paths import find_repo_root, registry_path, state_path
from sdc_core.sources.checks.state import load_state, save_state

NOW = datetime(2026, 10, 13, 14, 0, tzinfo=timezone.utc)


def test_load_missing_is_empty(tmp_path):
    assert load_state(tmp_path / "nope.json") == {}


def test_roundtrip_sorted_and_newline_terminated(tmp_path):
    p = tmp_path / "meta" / "state.json"
    state = {
        "zeta": Observation("content", "abc", NOW, "ETag"),
        "acs5": Observation("vintage", 2024, NOW, "api.census.gov/data.json"),
    }
    save_state(p, state)
    text = p.read_text()
    assert text.endswith("\n")
    assert list(json.loads(text)) == ["acs5", "zeta"]
    assert load_state(p) == state


def test_find_repo_root_walks_up(repo):
    assert find_repo_root(repo / "demographics" / "Age") == repo
    assert find_repo_root(repo) == repo


def test_find_repo_root_fails_without_marker(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_repo_root(tmp_path)


def test_paths(repo):
    assert registry_path(repo) == repo / "meta" / "source_checks.yaml"
    assert state_path(repo) == repo / "meta" / "source_checks_state.json"
