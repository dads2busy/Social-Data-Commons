import textwrap

import pytest
import yaml

from sdc_core.sources.checks.registry import (
    PipelineRef,
    RegistryError,
    audit,
    compute_latest,
    discover_pipelines,
    load_registry,
    max_year,
    sync_latest,
)

GOOD = textwrap.dedent(
    """
    sources:
      acs5:
        probe: census_vintage
        dataset: acs/acs5
        pipelines:
          - {path: demographics/Age, latest: 2023}
          - {path: "demographics/Geographic Mobility (HOI)", source: va, latest: 2023}
      chr_va:
        probe: html_years
        url: https://chr.example/va
        pattern: "(\\\\d{4}) County Health"
        pipelines:
          - {path: "demographics/Geographic Mobility (HOI)", source: chr, latest: 2024}
      alice:
        probe: http_file
        url: https://alice.example/va.xlsx
        pipelines:
          - {path: demographics/Age}
      hoi:
        probe: manual
        url: https://vdh.example/hoi
        note: look by hand
        pipelines:
          - {path: demographics/Age}
    untracked:
      - {path: energy/Thing, reason: exploratory scenario data}
    """
)


def write_registry(repo, text=GOOD):
    p = repo / "meta" / "source_checks.yaml"
    p.write_text(text)
    return p


def test_load_good(repo):
    reg = load_registry(write_registry(repo))
    assert [s.id for s in reg.sources] == ["acs5", "chr_va", "alice", "hoi"]
    acs = reg.sources[0]
    assert acs.probe == "census_vintage"
    assert acs.params == {"dataset": "acs/acs5"}
    assert acs.pipelines[1] == PipelineRef(
        path="demographics/Geographic Mobility (HOI)", latest=2023, source="va", key=None
    )
    assert reg.untracked == {"energy/Thing": "exploratory scenario data"}
    assert reg.tracked_paths() == {"demographics/Age", "demographics/Geographic Mobility (HOI)"}


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda d: d["sources"]["acs5"].update(probe="nope"), "unknown probe"),
        (lambda d: d["sources"]["acs5"].pop("dataset"), "missing keys"),
        (lambda d: d["sources"]["acs5"].update(bogus=1), "unknown keys"),
        (lambda d: d["sources"]["acs5"]["pipelines"][0].pop("latest"), "requires integer latest"),
        (lambda d: d["sources"]["alice"]["pipelines"][0].update(latest=2020), "only allowed on vintage"),
        (lambda d: d["sources"]["chr_va"].update(pattern="(a)(b)"), "exactly one capture group"),
        (lambda d: d["sources"]["acs5"].update(pipelines=[]), "no pipelines"),
        (lambda d: d["sources"]["acs5"]["pipelines"][0].update(extra="x"), "unknown pipeline keys"),
        (lambda d: d["untracked"].append({"path": "x"}), "path and reason"),
    ],
)
def test_load_rejects(repo, mutation, message):
    data = yaml.safe_load(GOOD)
    mutation(data)
    p = write_registry(repo, yaml.safe_dump(data))
    with pytest.raises(RegistryError, match=message):
        load_registry(p)


def test_discover_pipelines_skips_hidden_and_worktrees(repo):
    assert discover_pipelines(repo) == [
        "demographics/Age",
        "demographics/Geographic Mobility (HOI)",
        "energy/Thing",
    ]


def test_audit_clean(repo):
    reg = load_registry(write_registry(repo))
    assert audit(reg, repo) == ([], [])


def test_audit_reports_both_directions(repo):
    data = yaml.safe_load(GOOD)
    data["untracked"] = [{"path": "ghost/Pipeline", "reason": "gone"}]
    reg = load_registry(write_registry(repo, yaml.safe_dump(data)))
    assert audit(reg, repo) == (["energy/Thing"], ["ghost/Pipeline"])


def test_max_year_walks_years_lists_and_urls_keys():
    assert max_year({"years": [2019, 2021]}) == 2021
    assert max_year({"a": {"urls": {2022: "u", "2025": "v"}}, "b": [{"years": [2023]}]}) == 2025
    assert max_year({"years": "2024"}) is None
    assert max_year({}) is None


def test_compute_latest_whole_source_subkey_and_missing(repo):
    gm = "demographics/Geographic Mobility (HOI)"
    assert compute_latest(repo, PipelineRef(path="demographics/Age")) == 2023
    assert compute_latest(repo, PipelineRef(path=gm)) == 2025  # all sources
    assert compute_latest(repo, PipelineRef(path=gm, source="va")) == 2024
    assert compute_latest(repo, PipelineRef(path=gm, source="chr")) == 2025
    # `urls` itself is a dict of year -> url; nothing walkable below it
    assert compute_latest(repo, PipelineRef(path=gm, source="chr", key="urls")) is None
    assert compute_latest(repo, PipelineRef(path=gm, source="nope")) is None
    assert compute_latest(repo, PipelineRef(path="energy/Thing")) is None


def test_sync_latest_dry_run_reports_without_writing(repo):
    p = write_registry(repo)
    before = p.read_text()
    changes = sync_latest(p, repo, dry_run=True)
    assert ("acs5", "demographics/Age", 2023, 2023) in changes
    assert ("acs5", "demographics/Geographic Mobility (HOI)", 2023, 2024) in changes
    assert ("chr_va", "demographics/Geographic Mobility (HOI)", 2024, 2025) in changes
    assert all(c[0] not in {"alice", "hoi"} for c in changes)  # content/manual skipped
    assert p.read_text() == before


def test_sync_latest_writes_and_preserves_special_paths(repo):
    p = write_registry(repo)
    sync_latest(p, repo, dry_run=False)
    reg = load_registry(p)
    acs = {r.path: r.latest for r in reg.sources[0].pipelines}
    assert acs == {"demographics/Age": 2023, "demographics/Geographic Mobility (HOI)": 2024}
    assert reg.sources[1].pipelines[0].latest == 2025
    assert p.read_text().startswith("# Machine-maintained")
    assert reg.untracked == {"energy/Thing": "exploratory scenario data"}


def test_sync_latest_unresolvable_left_untouched(repo):
    data = yaml.safe_load(GOOD)
    data["sources"]["acs5"]["pipelines"][0]["source"] = "missing"
    p = write_registry(repo, yaml.safe_dump(data))
    changes = sync_latest(p, repo, dry_run=False)
    assert ("acs5", "demographics/Age", 2023, None) in changes
    assert load_registry(p).sources[0].pipelines[0].latest == 2023


def test_note_is_accepted_on_every_probe_kind(repo):
    data = yaml.safe_load(GOOD)
    data["sources"]["acs5"]["note"] = "catalog is slow"
    data["sources"]["alice"]["note"] = "republished in place"
    data["sources"]["chr_va"]["note"] = "VA page"
    reg = load_registry(write_registry(repo, yaml.safe_dump(data)))
    by_id = {e.id: e for e in reg.sources}
    assert by_id["acs5"].params == {"dataset": "acs/acs5", "note": "catalog is slow"}
    assert by_id["alice"].params["note"] == "republished in place"
    assert by_id["chr_va"].params["note"] == "VA page"
