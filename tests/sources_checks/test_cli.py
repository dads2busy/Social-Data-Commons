import json
import textwrap

import httpx
from click.testing import CliRunner

import sdc_core.sources.checks as checks_pkg
from sdc_core.cli import main
from sdc_core.sources.checks.probes._http import make_client

REGISTRY = textwrap.dedent(
    """
    sources:
      chr_va:
        probe: html_years
        url: https://chr.example/va
        pattern: "Rankings (\\\\d{4})"
        pipelines:
          - {path: demographics/Age, latest: 2023}
          - {path: "demographics/Geographic Mobility (HOI)", latest: 2024}
      alice:
        probe: http_file
        url: https://alice.example/va.xlsx
        pipelines:
          - {path: demographics/Age}
    untracked:
      - {path: energy/Thing, reason: exploratory}
    """
)


def handler(request: httpx.Request) -> httpx.Response:
    if request.url.host == "chr.example":
        return httpx.Response(200, text="Rankings 2024")
    return httpx.Response(200, headers={"ETag": '"v1"'})


def prepare(repo, monkeypatch, registry=REGISTRY):
    (repo / "meta" / "source_checks.yaml").write_text(registry)
    monkeypatch.chdir(repo / "demographics" / "Age")  # CLI must walk up to the root
    monkeypatch.setattr(
        checks_pkg, "make_client", lambda: make_client(transport=httpx.MockTransport(handler))
    )
    return CliRunner()


def test_check_table_exit_code_and_no_state_write(repo, monkeypatch):
    runner = prepare(repo, monkeypatch)
    result = runner.invoke(main, ["sources", "check"])
    assert result.exit_code == 1, result.output
    lines = result.output.splitlines()
    assert lines[0].startswith("STATUS")
    assert lines[1].startswith("new_vintage") and "demographics/Age" in lines[1]
    assert any(line.startswith("baseline") for line in lines)
    assert any(line.startswith("current") and "Geographic Mobility (HOI)" in line for line in lines)
    assert any(
        line.startswith("not_tracked") and "energy/Thing" in line and "exploratory" in line
        for line in lines
    )
    assert not (repo / "meta" / "source_checks_state.json").exists()


def test_check_update_state_then_current(repo, monkeypatch):
    runner = prepare(repo, monkeypatch)
    result = runner.invoke(main, ["sources", "check", "--update-state", "--source", "alice"])
    assert result.exit_code == 0, result.output
    state = json.loads((repo / "meta" / "source_checks_state.json").read_text())
    assert state["alice"]["value"] == '"v1"'
    assert "chr_va" not in state  # filtered out, so not observed
    again = runner.invoke(main, ["sources", "check", "--source", "alice"])
    assert again.exit_code == 0
    assert "current" in again.output


def test_check_json_output_and_pipeline_filter_with_special_chars(repo, monkeypatch):
    runner = prepare(repo, monkeypatch)
    out = repo / "rows.json"
    result = runner.invoke(
        main,
        [
            "sources",
            "check",
            "--pipeline",
            "demographics/Geographic Mobility (HOI)",
            "--json",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    rows = json.loads(out.read_text())
    assert [(r["source"], r["pipeline"], r["status"]) for r in rows] == [
        ("chr_va", "demographics/Geographic Mobility (HOI)", "current")
    ]


def test_audit_clean_and_dirty(repo, monkeypatch):
    runner = prepare(repo, monkeypatch)
    clean = runner.invoke(main, ["sources", "audit"])
    assert clean.exit_code == 0, clean.output
    assert "agree" in clean.output
    dirty_registry = REGISTRY.replace(
        "untracked:\n  - {path: energy/Thing, reason: exploratory}\n",
        "untracked:\n  - {path: ghost/P, reason: gone}\n",
    )
    runner = prepare(repo, monkeypatch, dirty_registry)
    dirty = runner.invoke(main, ["sources", "audit"])
    assert dirty.exit_code == 1
    assert "energy/Thing" in dirty.output and "ghost/P" in dirty.output


def test_sync_latest_dry_run_and_write(repo, monkeypatch):
    # Fixture: Age years max 2023 (registry says 2023: unchanged). The Geographic Mobility ref
    # names no `source`, so the walk covers va years (2024) and chr urls (2025) -> 2025.
    runner = prepare(repo, monkeypatch)
    registry_file = repo / "meta" / "source_checks.yaml"
    dry = runner.invoke(main, ["sources", "sync-latest", "--dry-run"])
    assert dry.exit_code == 0, dry.output
    assert "WOULD SET" in dry.output and "2024 -> 2025" in dry.output
    assert "Geographic Mobility (HOI)" in dry.output
    assert "1 would change" in dry.output
    assert "latest: 2024" in registry_file.read_text()  # dry run wrote nothing
    wet = runner.invoke(main, ["sources", "sync-latest"])
    assert wet.exit_code == 0, wet.output
    assert "SET" in wet.output and "1 changed" in wet.output
    text = registry_file.read_text()
    assert text.startswith("# Machine-maintained")
    assert "latest: 2025" in text and "latest: 2023" in text and "latest: 2024" not in text


def test_malformed_registry_is_a_clean_error_not_a_traceback(repo, monkeypatch):
    runner = prepare(repo, monkeypatch, REGISTRY.replace("probe: http_file", "probe: nope"))
    for args in (["sources", "check"], ["sources", "audit"], ["sources", "sync-latest"]):
        result = runner.invoke(main, args)
        assert result.exit_code == 1, (args, result.output)
        assert "unknown probe 'nope'" in result.output
        assert "Traceback" not in result.output
        assert result.exception is None or isinstance(result.exception, SystemExit)
