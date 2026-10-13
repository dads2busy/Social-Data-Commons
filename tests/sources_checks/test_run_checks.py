import textwrap
from datetime import datetime, timezone

import httpx

from sdc_core.sources.checks import run_checks
from sdc_core.sources.checks.compare import Observation
from sdc_core.sources.checks.probes._http import make_client
from sdc_core.sources.checks.registry import load_registry

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

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
      broken_json:
        probe: census_vintage
        dataset: acs/acs5
        pipelines:
          - {path: demographics/Age, latest: 2023}
      hoi:
        probe: manual
        url: https://vdh.example/hoi
        pipelines:
          - {path: demographics/Age}
    untracked:
      - {path: energy/Thing, reason: exploratory}
    """
)


def handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if host == "chr.example":
        return httpx.Response(200, text="Rankings 2024 and Rankings 2023")
    if host == "alice.example":
        return httpx.Response(200, headers={"ETag": '"v2"'})
    if host == "api.census.gov":
        return httpx.Response(200, text="this is not json")
    raise AssertionError(f"unexpected host {host}")


def setup(repo, state=None):
    p = repo / "meta" / "source_checks.yaml"
    p.write_text(REGISTRY)
    registry = load_registry(p)
    client = make_client(transport=httpx.MockTransport(handler))
    return run_checks(registry, state or {}, repo, client=client)


def test_full_run_statuses_and_not_tracked(repo):
    rows, observed = setup(repo)
    by = {(r.source, r.pipeline): r for r in rows}
    assert by[("chr_va", "demographics/Age")].status == "new_vintage"
    assert by[("chr_va", "demographics/Age")].upstream == 2024
    assert by[("chr_va", "demographics/Geographic Mobility (HOI)")].status == "current"
    assert by[("alice", "demographics/Age")].status == "baseline"
    assert by[("alice", "demographics/Age")].upstream is None
    assert by[("hoi", "demographics/Age")].status == "unverified"
    err = by[("broken_json", "demographics/Age")]
    assert err.status == "error" and "JSONDecodeError" in err.detail and err.fetched_at is None
    assert by[(None, "energy/Thing")].status == "not_tracked"
    assert by[(None, "energy/Thing")].detail == "exploratory"
    assert rows[0].status == "new_vintage" and rows[-1].status == "not_tracked"


def test_observed_excludes_errors_and_manual(repo):
    _, observed = setup(repo)
    assert set(observed) == {"chr_va", "alice"}
    assert observed["alice"].value == '"v2"'


def test_prior_state_drives_changed_and_current(repo):
    prior = {"alice": Observation("content", '"v1"', NOW, "ETag")}
    rows, _ = setup(repo, prior)
    alice = next(r for r in rows if r.source == "alice")
    assert alice.status == "changed"
    assert alice.detail == 'ETag changed (was "v1")'
    rows2, _ = setup(repo, {"alice": Observation("content", '"v2"', NOW, "ETag")})
    assert next(r for r in rows2 if r.source == "alice").status == "current"


def test_filters_hide_not_tracked_and_select(repo):
    p = repo / "meta" / "source_checks.yaml"
    p.write_text(REGISTRY)
    registry = load_registry(p)
    client = make_client(transport=httpx.MockTransport(handler))
    rows, _ = run_checks(registry, {}, repo, source_filter={"alice"}, client=client)
    assert [(r.source, r.pipeline) for r in rows] == [("alice", "demographics/Age")]
    rows, _ = run_checks(
        registry, {}, repo, pipeline_filter={"demographics/Geographic Mobility (HOI)"}, client=client
    )
    assert [(r.source, r.pipeline) for r in rows] == [
        ("chr_va", "demographics/Geographic Mobility (HOI)")
    ]
    assert all(r.status != "not_tracked" for r in rows)
