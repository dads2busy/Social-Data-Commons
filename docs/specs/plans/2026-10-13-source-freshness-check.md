# Source Freshness Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `sdc sources check | audit | sync-latest` so one command reports which pipelines have a newer upstream vintage or a revised upstream file than what we last ingested.

**Architecture:** A central registry (`meta/source_checks.yaml`) maps upstream sources to consuming pipelines. Six probe kinds fetch an `Observation` per source; a pure `compare()` turns observation + our `latest` + prior state into a status; a reporter renders a table/JSON and an exit code. All code lives in a new, additive `sdc_core.sources.checks` package wired into the existing click CLI.

**Tech Stack:** Python 3.12, httpx (already a dependency), click, PyYAML, pytest with `httpx.MockTransport` (no network in tests). No new dependencies.

**Spec:** `docs/specs/2026-10-13-source-freshness-check-design.md`

## Global Constraints

- Package manager is **uv**. Run everything as `uv run …`. Never pip/conda/poetry.
- **No new dependencies.** httpx, click, pyyaml, pytest are already present.
- Python `>=3.12`; ruff line length 100 (`packages/sdc-core/pyproject.toml`).
- Only **additive** changes to sdc-core: a new subpackage and a new click group. No existing function changes.
- **No `pipeline.yaml` is modified.** Registry and state live in `meta/`.
- Tests under `tests/sources_checks/` must **never touch the network**.
- Timeout 30 s per request; one retry on transport error or 5xx; 4xx fails immediately.
- `--update-state` is the only thing that writes `meta/source_checks_state.json`; `error` rows never overwrite prior state.
- Exit code 0 iff every row is `current`, `baseline`, or `not_tracked`.
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Spec amendments made by this plan

Two facts surfaced while planning that the spec got wrong or left open. Task 6 and Task 9 edit the spec to match.

1. **There are 72 pipelines, not 39.** The brainstorm surveyed only `*/*/pipeline.yaml`; 32 more sit three to five levels deep (food, housing, business_climate, health subgroups) plus a depth-1 umbrella `demographics/pipeline.yaml`. The design is unchanged; the registry seed is larger.
2. **`audit` needs an acknowledged-untracked list.** The spec says `audit` exits 1 when any pipeline lacks a registry entry *and* that `audit` exits 0 against the seeded registry, yet computed/energy pipelines are `not_tracked` by design. Resolution: the registry gets a top-level `untracked:` list of `{path, reason}`. `audit` treats those as acknowledged; `check` still shows them as `not_tracked` with the reason in DETAIL.

## Review Focus

Inputs the spec implies but no obvious test exercises; each line's test is added to the owning task.

1. **Pipeline paths with spaces and parentheses** (e.g. `demographics/Geographic Mobility (HOI)`) must resolve on disk, match `--pipeline` filters, and survive the YAML round-trip in `sync-latest`. → Task 6 registry tests, Task 8 CLI test.
2. **Census `data.json` entries with no `c_vintage`** (timeseries datasets) and entries whose `c_dataset` differs only in a trailing segment (`acs/acs5/profile`) must be ignored, not crash or match. → Task 4.
3. **HEAD not allowed (405) or redirected** for `http_file` must fall back to GET and still produce a fingerprint; a 404 must become an `error` row, not a crash. → Task 2.
4. **Years matched outside 1900–2100** by `html_years` (e.g. `1024px`, `width=3000`) must be discarded; a page with no plausible year must raise `ProbeError`. → Task 3.
5. **A probe that raises something other than `ProbeError`** (JSON decode error, KeyError on an unexpected payload) must still become an `error` row for its pipelines and must not clobber prior state on `--update-state`. → Task 7.

---

## File structure

```
packages/sdc-core/src/sdc_core/sources/checks/
  __init__.py          run_checks(): orchestrates probes → compare → rows
  compare.py           Observation, Row, Status, compare(), describe()
  state.py             load_state()/save_state() for meta/source_checks_state.json
  paths.py             find_repo_root(), registry_path(), state_path()
  registry.py          load_registry(), discover_pipelines(), audit(), max_year(), compute_latest(), sync_latest()
  report.py            sort_rows(), render_table(), render_json(), exit_code()
  probes/
    __init__.py        PROBES: dict[str, ProbeSpec] (imports every probe module)
    _spec.py           ProbeSpec dataclass
    _http.py           ProbeError, make_client(), request_with_retry()
    manual.py
    http_file.py
    html_years.py
    lodes_vintage.py
    census_vintage.py
    bea_vintage.py
packages/sdc-core/src/sdc_core/cli.py          + `sources` click group (check, audit, sync-latest)
meta/source_checks.yaml                        registry (seeded in Task 9)
meta/source_checks_state.json                  baseline (created in Task 9 via --update-state)
tests/sources_checks/
  conftest.py          `repo` fixture: temp repo root with sync.yaml + 3 pipelines
  test_compare.py
  test_probe_manual.py
  test_probe_http_file.py
  test_probe_html_years.py     (also covers lodes_vintage)
  test_probe_census_vintage.py
  test_probe_bea_vintage.py
  test_state.py
  test_registry.py
  test_report.py
  test_run_checks.py
  test_cli.py
```

Every module imports only from modules above it in this list. Probes know nothing about pipelines; `compare` knows nothing about HTTP; `report` knows nothing about either.

---

### Task 1: Models and pure comparison

**Files:**
- Create: `packages/sdc-core/src/sdc_core/sources/__init__.py` (exists already; leave as is)
- Create: `packages/sdc-core/src/sdc_core/sources/checks/__init__.py` (empty for now; Task 7 fills it)
- Create: `packages/sdc-core/src/sdc_core/sources/checks/compare.py`
- Test: `tests/sources_checks/__init__.py` (empty), `tests/sources_checks/test_compare.py`

**Interfaces:**
- Produces:
  - `Kind = Literal["vintage", "content", "manual"]`
  - `Status = Literal["new_vintage", "changed", "unverified", "error", "baseline", "current", "not_tracked"]`
  - `STATUS_ORDER: dict[str, int]`, `ACTION_STATUSES: frozenset[str]`
  - `Observation(kind, value, fetched_at, detail)` frozen dataclass with `to_dict()` / `from_dict()`
  - `Row(status, source, pipeline, ours, upstream, detail, fetched_at)` frozen dataclass with `to_dict()`
  - `compare(observation: Observation, latest: int | None, prior: Observation | None) -> Status`
  - `describe(status: Status, observation: Observation, prior: Observation | None) -> str`

- [ ] **Step 1: Write the failing tests**

```python
# tests/sources_checks/test_compare.py
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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/sources_checks/test_compare.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'sdc_core.sources.checks'`

- [ ] **Step 3: Implement**

Create empty `packages/sdc-core/src/sdc_core/sources/checks/__init__.py` and empty `tests/sources_checks/__init__.py`, then:

```python
# packages/sdc-core/src/sdc_core/sources/checks/compare.py
"""Pure comparison of a probe observation against our recorded state.

No I/O here. Probes produce an ``Observation``; ``compare`` turns it, plus the
pipeline's ``latest`` year and the prior stored observation, into a ``Status``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

Kind = Literal["vintage", "content", "manual"]
Status = Literal["new_vintage", "changed", "unverified", "error", "baseline", "current", "not_tracked"]

STATUS_ORDER: dict[str, int] = {
    s: i
    for i, s in enumerate(
        ["new_vintage", "changed", "unverified", "error", "baseline", "current", "not_tracked"]
    )
}
ACTION_STATUSES: frozenset[str] = frozenset({"new_vintage", "changed", "unverified", "error"})


@dataclass(frozen=True)
class Observation:
    """What a probe saw upstream at one moment."""

    kind: Kind
    value: int | str | None  # year for vintage, fingerprint for content, None for manual
    fetched_at: datetime  # UTC
    detail: str  # one human-readable line: URL inspected, header used, ...

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "value": self.value,
            "fetched_at": self.fetched_at.isoformat(),
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Observation:
        return cls(
            kind=d["kind"],
            value=d.get("value"),
            fetched_at=datetime.fromisoformat(d["fetched_at"]),
            detail=d.get("detail", ""),
        )


@dataclass(frozen=True)
class Row:
    """One line of the report: a (source, pipeline) pair with its status."""

    status: Status
    source: str | None
    pipeline: str
    ours: int | None
    upstream: int | str | None
    detail: str
    fetched_at: datetime | None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["fetched_at"] = self.fetched_at.isoformat() if self.fetched_at else None
        return d


def compare(observation: Observation, latest: int | None, prior: Observation | None) -> Status:
    """Apply the status matrix from the spec (Section 3)."""
    if observation.kind == "manual":
        return "unverified"
    if observation.kind == "vintage":
        if latest is None:
            raise ValueError("vintage comparison requires the pipeline's `latest` year")
        return "new_vintage" if int(observation.value) > latest else "current"
    # content
    if prior is None or prior.kind != "content":
        return "baseline"
    return "changed" if observation.value != prior.value else "current"


def describe(status: Status, observation: Observation, prior: Observation | None) -> str:
    """Detail column text for a row."""
    if status == "changed" and prior is not None:
        return f"{observation.detail} changed (was {prior.value})"
    if status == "baseline":
        return f"{observation.detail} recorded"
    return observation.detail
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/sources_checks/test_compare.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-core/src/sdc_core/sources/checks tests/sources_checks
git commit -m "feat(sources): Observation/Row models and pure compare() for freshness checks

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: HTTP helper, probe spec, `manual` and `http_file` probes

**Files:**
- Create: `packages/sdc-core/src/sdc_core/sources/checks/probes/_spec.py`
- Create: `packages/sdc-core/src/sdc_core/sources/checks/probes/_http.py`
- Create: `packages/sdc-core/src/sdc_core/sources/checks/probes/manual.py`
- Create: `packages/sdc-core/src/sdc_core/sources/checks/probes/http_file.py`
- Create: `packages/sdc-core/src/sdc_core/sources/checks/probes/__init__.py` (registers only these two for now; Tasks 3–4 add more)
- Test: `tests/sources_checks/test_probe_manual.py`, `tests/sources_checks/test_probe_http_file.py`

**Interfaces:**
- Consumes: `Observation` from Task 1.
- Produces:
  - `ProbeSpec(name, kind, required, optional, run, validate=None)`; `run(params: dict, client: httpx.Client) -> Observation`; `validate(params: dict) -> None` raises `ValueError`.
  - `ProbeError(Exception)`
  - `make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client`
  - `request_with_retry(client, method: str, url: str, **kwargs) -> httpx.Response`
  - `PROBES: dict[str, ProbeSpec]` in `probes/__init__.py`
  - each probe module exposes `SPEC: ProbeSpec`

- [ ] **Step 1: Write the failing tests**

```python
# tests/sources_checks/test_probe_manual.py
import httpx

from sdc_core.sources.checks.probes import PROBES
from sdc_core.sources.checks.probes._http import make_client


def test_manual_registered():
    spec = PROBES["manual"]
    assert spec.kind == "manual"
    assert spec.required == {"url"}
    assert spec.optional == {"note"}


def test_manual_never_calls_network():
    def boom(request):  # pragma: no cover - would fail the test if called
        raise AssertionError("manual probe must not hit the network")

    client = make_client(transport=httpx.MockTransport(boom))
    obs = PROBES["manual"].run({"url": "https://x.example/page"}, client)
    assert obs.kind == "manual"
    assert obs.value is None
    assert obs.detail == "https://x.example/page"


def test_manual_appends_note():
    client = make_client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    obs = PROBES["manual"].run({"url": "https://x.example", "note": "look at tab 2"}, client)
    assert obs.detail == "https://x.example | look at tab 2"
```

```python
# tests/sources_checks/test_probe_http_file.py
import hashlib

import httpx
import pytest

from sdc_core.sources.checks.probes import PROBES
from sdc_core.sources.checks.probes._http import ProbeError, make_client, request_with_retry

URL = "https://files.example/data.xlsx"


def client_with(handler):
    return make_client(transport=httpx.MockTransport(handler))


def test_spec():
    spec = PROBES["http_file"]
    assert spec.kind == "content"
    assert spec.required == {"url"}
    assert spec.optional == frozenset()


def test_etag_preferred():
    def handler(request):
        assert request.method == "HEAD"
        return httpx.Response(200, headers={"ETag": 'W/"abc"', "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT"})

    obs = PROBES["http_file"].run({"url": URL}, client_with(handler))
    assert (obs.kind, obs.value, obs.detail) == ("content", 'W/"abc"', "ETag")


def test_last_modified_fallback():
    def handler(request):
        return httpx.Response(200, headers={"Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT"})

    obs = PROBES["http_file"].run({"url": URL}, client_with(handler))
    assert (obs.value, obs.detail) == ("Mon, 01 Jan 2024 00:00:00 GMT", "Last-Modified")


def test_sha256_fallback_when_no_headers():
    body = b"hello world"

    def handler(request):
        if request.method == "HEAD":
            return httpx.Response(200)
        return httpx.Response(200, content=body)

    obs = PROBES["http_file"].run({"url": URL}, client_with(handler))
    assert obs.detail == "SHA-256"
    assert obs.value == hashlib.sha256(body).hexdigest()


def test_head_405_falls_back_to_get():
    body = b"payload"

    def handler(request):
        if request.method == "HEAD":
            return httpx.Response(405)
        return httpx.Response(200, content=body)

    obs = PROBES["http_file"].run({"url": URL}, client_with(handler))
    assert obs.value == hashlib.sha256(body).hexdigest()


def test_redirect_followed():
    def handler(request):
        if request.url.path == "/old":
            return httpx.Response(302, headers={"Location": "https://files.example/new"})
        return httpx.Response(200, headers={"ETag": '"final"'})

    obs = PROBES["http_file"].run({"url": "https://files.example/old"}, client_with(handler))
    assert obs.value == '"final"'


def test_404_is_probe_error():
    def handler(request):
        return httpx.Response(404)

    with pytest.raises(ProbeError):
        PROBES["http_file"].run({"url": URL}, client_with(handler))


def test_retry_once_on_5xx_then_succeed():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, headers={"ETag": '"ok"'})

    resp = request_with_retry(client_with(handler), "HEAD", URL)
    assert resp.status_code == 200
    assert calls["n"] == 2


def test_retry_once_on_5xx_then_fail():
    def handler(request):
        return httpx.Response(503)

    with pytest.raises(ProbeError, match="503"):
        request_with_retry(client_with(handler), "GET", URL)


def test_retry_on_transport_error():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200)

    assert request_with_retry(client_with(handler), "GET", URL).status_code == 200


def test_4xx_fails_immediately():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(403)

    with pytest.raises(ProbeError, match="403"):
        request_with_retry(client_with(handler), "GET", URL)
    assert calls["n"] == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/sources_checks/test_probe_manual.py tests/sources_checks/test_probe_http_file.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'sdc_core.sources.checks.probes'`

- [ ] **Step 3: Implement**

```python
# packages/sdc-core/src/sdc_core/sources/checks/probes/_spec.py
"""Descriptor each probe module exposes as ``SPEC``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import httpx

from sdc_core.sources.checks.compare import Kind, Observation

RunFn = Callable[[dict, httpx.Client], Observation]
ValidateFn = Callable[[dict], None]


@dataclass(frozen=True)
class ProbeSpec:
    name: str
    kind: Kind
    required: frozenset[str]  # registry keys this probe needs
    optional: frozenset[str]  # registry keys it accepts
    run: RunFn
    validate: ValidateFn | None = None  # extra param checks; raise ValueError
```

```python
# packages/sdc-core/src/sdc_core/sources/checks/probes/_http.py
"""Shared HTTP client and retry policy for probes."""

from __future__ import annotations

import httpx

DEFAULT_TIMEOUT = 30.0
USER_AGENT = "sdc-sources-check/1.0 (+https://github.com/dads2busy/Social-Data-Commons)"


class ProbeError(Exception):
    """A probe could not produce an observation. Becomes an `error` row."""


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
        transport=transport,
    )


def request_with_retry(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    """One retry on transport error or 5xx. 4xx raises immediately."""
    last: Exception | None = None
    for _attempt in range(2):
        try:
            resp = client.request(method, url, **kwargs)
        except httpx.TransportError as exc:
            last = exc
            continue
        if resp.status_code >= 500:
            last = ProbeError(f"HTTP {resp.status_code} from {url}")
            continue
        if resp.status_code >= 400:
            raise ProbeError(f"HTTP {resp.status_code} from {url}")
        return resp
    raise ProbeError(f"{last} after retry")
```

```python
# packages/sdc-core/src/sdc_core/sources/checks/probes/manual.py
"""No-network probe: tells a human where to look."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from sdc_core.sources.checks.compare import Observation
from sdc_core.sources.checks.probes._spec import ProbeSpec


def run(params: dict, client: httpx.Client) -> Observation:
    detail = params["url"]
    if params.get("note"):
        detail = f"{detail} | {params['note']}"
    return Observation(kind="manual", value=None, fetched_at=datetime.now(timezone.utc), detail=detail)


SPEC = ProbeSpec(
    name="manual",
    kind="manual",
    required=frozenset({"url"}),
    optional=frozenset({"note"}),
    run=run,
)
```

```python
# packages/sdc-core/src/sdc_core/sources/checks/probes/http_file.py
"""Content fingerprint of a single URL: ETag, else Last-Modified, else SHA-256."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import httpx

from sdc_core.sources.checks.compare import Observation
from sdc_core.sources.checks.probes._http import ProbeError, request_with_retry
from sdc_core.sources.checks.probes._spec import ProbeSpec


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run(params: dict, client: httpx.Client) -> Observation:
    url = params["url"]
    try:
        head = request_with_retry(client, "HEAD", url)
    except ProbeError:
        head = None  # e.g. 405 Method Not Allowed; fall through to GET
    if head is not None:
        etag = head.headers.get("ETag")
        if etag:
            return Observation("content", etag, _now(), "ETag")
        last_modified = head.headers.get("Last-Modified")
        if last_modified:
            return Observation("content", last_modified, _now(), "Last-Modified")

    digest = hashlib.sha256()
    try:
        with client.stream("GET", url) as resp:
            if resp.status_code >= 400:
                raise ProbeError(f"HTTP {resp.status_code} from {url}")
            for chunk in resp.iter_bytes():
                digest.update(chunk)
    except httpx.TransportError as exc:
        raise ProbeError(f"{exc!r} fetching {url}") from exc
    return Observation("content", digest.hexdigest(), _now(), "SHA-256")


SPEC = ProbeSpec(
    name="http_file",
    kind="content",
    required=frozenset({"url"}),
    optional=frozenset(),
    run=run,
)
```

```python
# packages/sdc-core/src/sdc_core/sources/checks/probes/__init__.py
"""Registry of probe kinds. Add a module and list it here to add a probe."""

from __future__ import annotations

from sdc_core.sources.checks.probes import http_file, manual
from sdc_core.sources.checks.probes._spec import ProbeSpec

PROBES: dict[str, ProbeSpec] = {m.SPEC.name: m.SPEC for m in (manual, http_file)}

__all__ = ["PROBES", "ProbeSpec"]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/sources_checks -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-core/src/sdc_core/sources/checks/probes tests/sources_checks
git commit -m "feat(sources): probe spec, retrying HTTP helper, manual and http_file probes

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: `html_years` and `lodes_vintage` probes

**Files:**
- Create: `packages/sdc-core/src/sdc_core/sources/checks/probes/html_years.py`
- Create: `packages/sdc-core/src/sdc_core/sources/checks/probes/lodes_vintage.py`
- Modify: `packages/sdc-core/src/sdc_core/sources/checks/probes/__init__.py` (add both to the tuple)
- Test: `tests/sources_checks/test_probe_html_years.py`

**Interfaces:**
- Consumes: `ProbeSpec`, `ProbeError`, `request_with_retry`, `Observation`.
- Produces: `html_years.extract_max_year(text: str, pattern: str) -> int | None`; `html_years.validate(params)`; `lodes_vintage.DEFAULT_PATTERN`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/sources_checks/test_probe_html_years.py
import httpx
import pytest

from sdc_core.sources.checks.probes import PROBES
from sdc_core.sources.checks.probes._http import ProbeError, make_client
from sdc_core.sources.checks.probes.html_years import extract_max_year

PAGE = """
<a href="/doc/2023%20County%20Health%20Rankings%20Virginia%20Data%20-%20v3.xlsx">2023</a>
<a href="/doc/2025 County Health Rankings Virginia Data - v4.xlsx">2025</a>
<img width="3000" height="1024px">
"""
CHR_PATTERN = r"(\d{4})(?: |%20)County(?: |%20)Health(?: |%20)Rankings(?: |%20)Virginia(?: |%20)Data"


def client_with(text, status=200):
    return make_client(transport=httpx.MockTransport(lambda r: httpx.Response(status, text=text)))


def test_spec():
    spec = PROBES["html_years"]
    assert spec.kind == "vintage"
    assert spec.required == {"url", "pattern"}
    assert spec.validate is not None


def test_extract_max_year_filters_implausible():
    assert extract_max_year(PAGE, CHR_PATTERN) == 2025
    assert extract_max_year("width=3000 1024px 0999", r"(\d{4})") is None


def test_run_returns_vintage_observation():
    obs = PROBES["html_years"].run({"url": "https://x.example/p", "pattern": CHR_PATTERN}, client_with(PAGE))
    assert (obs.kind, obs.value, obs.detail) == ("vintage", 2025, "https://x.example/p")


def test_run_no_match_is_probe_error():
    with pytest.raises(ProbeError, match="no year matched"):
        PROBES["html_years"].run({"url": "https://x.example/p", "pattern": r"nothing(\d{4})"}, client_with(PAGE))


@pytest.mark.parametrize("pattern", [r"(\d{4})-(\d{4})", r"\d{4}", r"(\d{4"])
def test_validate_requires_exactly_one_group(pattern):
    with pytest.raises(ValueError):
        PROBES["html_years"].validate({"url": "u", "pattern": pattern})


def test_validate_accepts_one_group():
    PROBES["html_years"].validate({"url": "u", "pattern": r"fmr(20\d{2})/"})


LODES_LISTING = """
<a href="va_wac_S000_JT00_2002.csv.gz">va_wac_S000_JT00_2002.csv.gz</a>
<a href="va_wac_S000_JT00_2022.csv.gz">va_wac_S000_JT00_2022.csv.gz</a>
<a href="va_wac_S000_JT00_2023.csv.gz">va_wac_S000_JT00_2023.csv.gz</a>
"""


def test_lodes_default_pattern():
    spec = PROBES["lodes_vintage"]
    assert spec.kind == "vintage"
    assert spec.required == {"url"}
    assert spec.optional == {"pattern"}
    obs = spec.run({"url": "https://lehd.example/va/wac/"}, client_with(LODES_LISTING))
    assert obs.value == 2023


def test_lodes_custom_pattern_validated():
    with pytest.raises(ValueError):
        PROBES["lodes_vintage"].validate({"url": "u", "pattern": r"(\d{4})(\d{2})"})
    PROBES["lodes_vintage"].validate({"url": "u"})  # no pattern is fine
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/sources_checks/test_probe_html_years.py -q`
Expected: FAIL with `ModuleNotFoundError` for `html_years`.

- [ ] **Step 3: Implement**

```python
# packages/sdc-core/src/sdc_core/sources/checks/probes/html_years.py
"""Vintage from a web page: the largest plausible year a one-group regex captures."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from sdc_core.sources.checks.compare import Observation
from sdc_core.sources.checks.probes._http import ProbeError, request_with_retry
from sdc_core.sources.checks.probes._spec import ProbeSpec

YEAR_MIN, YEAR_MAX = 1900, 2100


def extract_max_year(text: str, pattern: str) -> int | None:
    years: list[int] = []
    for match in re.findall(pattern, text):
        try:
            year = int(match)
        except (TypeError, ValueError):
            continue
        if YEAR_MIN <= year <= YEAR_MAX:
            years.append(year)
    return max(years) if years else None


def validate(params: dict) -> None:
    try:
        compiled = re.compile(params["pattern"])
    except re.error as exc:
        raise ValueError(f"pattern is not a valid regex: {exc}") from exc
    if compiled.groups != 1:
        raise ValueError("pattern must contain exactly one capture group (the year)")


def run(params: dict, client: httpx.Client) -> Observation:
    url, pattern = params["url"], params["pattern"]
    resp = request_with_retry(client, "GET", url)
    year = extract_max_year(resp.text, pattern)
    if year is None:
        raise ProbeError(f"no year matched {pattern!r} at {url}")
    return Observation("vintage", year, datetime.now(timezone.utc), url)


SPEC = ProbeSpec(
    name="html_years",
    kind="vintage",
    required=frozenset({"url", "pattern"}),
    optional=frozenset(),
    run=run,
    validate=validate,
)
```

```python
# packages/sdc-core/src/sdc_core/sources/checks/probes/lodes_vintage.py
"""Vintage from a LEHD LODES directory listing (html_years with a LODES default pattern)."""

from __future__ import annotations

import httpx

from sdc_core.sources.checks.compare import Observation
from sdc_core.sources.checks.probes import html_years
from sdc_core.sources.checks.probes._spec import ProbeSpec

DEFAULT_PATTERN = r"_(\d{4})\.csv\.gz"


def run(params: dict, client: httpx.Client) -> Observation:
    return html_years.run(
        {"url": params["url"], "pattern": params.get("pattern", DEFAULT_PATTERN)}, client
    )


def validate(params: dict) -> None:
    if "pattern" in params:
        html_years.validate(params)


SPEC = ProbeSpec(
    name="lodes_vintage",
    kind="vintage",
    required=frozenset({"url"}),
    optional=frozenset({"pattern"}),
    run=run,
    validate=validate,
)
```

Update `probes/__init__.py`:

```python
from sdc_core.sources.checks.probes import html_years, http_file, lodes_vintage, manual
from sdc_core.sources.checks.probes._spec import ProbeSpec

PROBES: dict[str, ProbeSpec] = {
    m.SPEC.name: m.SPEC for m in (manual, http_file, html_years, lodes_vintage)
}
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/sources_checks -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-core/src/sdc_core/sources/checks/probes tests/sources_checks
git commit -m "feat(sources): html_years and lodes_vintage probes

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `census_vintage` and `bea_vintage` probes

**Files:**
- Create: `packages/sdc-core/src/sdc_core/sources/checks/probes/census_vintage.py`
- Create: `packages/sdc-core/src/sdc_core/sources/checks/probes/bea_vintage.py`
- Modify: `packages/sdc-core/src/sdc_core/sources/checks/probes/__init__.py`
- Test: `tests/sources_checks/test_probe_census_vintage.py`, `tests/sources_checks/test_probe_bea_vintage.py`

**Interfaces:**
- Produces: `census_vintage.max_vintage(catalog: dict, dataset: str) -> int | None`; `census_vintage.DATA_JSON_URL`; `bea_vintage.max_year_from_params(payload: dict) -> int | None`; `bea_vintage.BEA_URL`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/sources_checks/test_probe_census_vintage.py
import json

import httpx
import pytest

from sdc_core.sources.checks.probes import PROBES
from sdc_core.sources.checks.probes._http import ProbeError, make_client
from sdc_core.sources.checks.probes.census_vintage import DATA_JSON_URL, max_vintage

CATALOG = {
    "dataset": [
        {"c_dataset": ["acs", "acs5"], "c_vintage": 2022, "title": "ACS 5-Year 2022"},
        {"c_dataset": ["acs", "acs5"], "c_vintage": 2024, "title": "ACS 5-Year 2024"},
        {"c_dataset": ["acs", "acs5", "profile"], "c_vintage": 2025, "title": "profile, must not match"},
        {"c_dataset": ["acs", "acs1"], "c_vintage": 2026, "title": "acs1, must not match"},
        {"c_dataset": ["timeseries", "eits"], "title": "no c_vintage, must be ignored"},
        {"c_dataset": ["acs", "acs5"], "c_vintage": "not-an-int"},
    ]
}


def test_max_vintage_exact_dataset_match():
    assert max_vintage(CATALOG, "acs/acs5") == 2024
    assert max_vintage(CATALOG, "acs/acs5/profile") == 2025
    assert max_vintage(CATALOG, "dec/pl") is None
    assert max_vintage({}, "acs/acs5") is None


def test_run_hits_data_json_and_returns_vintage():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, content=json.dumps(CATALOG).encode())

    spec = PROBES["census_vintage"]
    assert spec.kind == "vintage" and spec.required == {"dataset"}
    obs = spec.run({"dataset": "acs/acs5"}, make_client(transport=httpx.MockTransport(handler)))
    assert seen["url"] == DATA_JSON_URL
    assert (obs.value, obs.detail) == (2024, "api.census.gov/data.json")


def test_run_unknown_dataset_is_probe_error():
    client = make_client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=CATALOG)))
    with pytest.raises(ProbeError, match="dec/pl"):
        PROBES["census_vintage"].run({"dataset": "dec/pl"}, client)
```

```python
# tests/sources_checks/test_probe_bea_vintage.py
import httpx
import pytest

from sdc_core.sources.checks.probes import PROBES
from sdc_core.sources.checks.probes._http import ProbeError, make_client
from sdc_core.sources.checks.probes.bea_vintage import max_year_from_params

PARAMS = {"dataset": "Regional", "table": "CAINC4"}


def test_spec():
    spec = PROBES["bea_vintage"]
    assert spec.kind == "vintage"
    assert spec.required == {"dataset", "table"}


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"BEAAPI": {"Results": {"ParamValue": [{"Key": "2022", "Desc": "2022"}, {"Key": "2024", "Desc": "2024"}]}}}, 2024),
        ({"BEAAPI": {"Results": {"ParamValue": {"TableName": "CAINC4", "FirstYear": "1969", "LastYear": "2023"}}}}, 2023),
        ({"BEAAPI": {"Results": {"ParamValue": []}}}, None),
        ({}, None),
    ],
)
def test_max_year_from_params(payload, expected):
    assert max_year_from_params(payload) == expected


def test_missing_api_key_is_probe_error(monkeypatch):
    monkeypatch.delenv("BEA_API_KEY", raising=False)
    client = make_client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    with pytest.raises(ProbeError, match="BEA_API_KEY"):
        PROBES["bea_vintage"].run(PARAMS, client)


def test_run_sends_expected_query(monkeypatch):
    monkeypatch.setenv("BEA_API_KEY", "k123")
    seen = {}

    def handler(request):
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"BEAAPI": {"Results": {"ParamValue": [{"Key": "2024"}]}}})

    obs = PROBES["bea_vintage"].run(PARAMS, make_client(transport=httpx.MockTransport(handler)))
    assert obs.value == 2024
    assert seen["UserID"] == "k123"
    assert seen["method"] == "GetParameterValuesFiltered"
    assert seen["datasetname"] == "Regional"
    assert seen["TargetParameter"] == "Year"
    assert seen["TableName"] == "CAINC4"
    assert obs.detail == "apps.bea.gov Regional/CAINC4 Year values"


def test_bea_error_payload_is_probe_error(monkeypatch):
    monkeypatch.setenv("BEA_API_KEY", "k123")
    payload = {"BEAAPI": {"Results": {"Error": {"APIErrorCode": "3", "APIErrorDescription": "Invalid API UserId"}}}}
    client = make_client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    with pytest.raises(ProbeError, match="Invalid API UserId"):
        PROBES["bea_vintage"].run(PARAMS, client)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/sources_checks/test_probe_census_vintage.py tests/sources_checks/test_probe_bea_vintage.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# packages/sdc-core/src/sdc_core/sources/checks/probes/census_vintage.py
"""Newest vintage of a Census API dataset, from the api.census.gov/data.json catalog."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from sdc_core.sources.checks.compare import Observation
from sdc_core.sources.checks.probes._http import ProbeError, request_with_retry
from sdc_core.sources.checks.probes._spec import ProbeSpec

DATA_JSON_URL = "https://api.census.gov/data.json"
CATALOG_TIMEOUT = 120.0  # the catalog is tens of MB


def max_vintage(catalog: dict, dataset: str) -> int | None:
    want = dataset.strip("/").split("/")
    vintages = [
        entry["c_vintage"]
        for entry in catalog.get("dataset", [])
        if entry.get("c_dataset") == want and isinstance(entry.get("c_vintage"), int)
    ]
    return max(vintages) if vintages else None


def run(params: dict, client: httpx.Client) -> Observation:
    resp = request_with_retry(client, "GET", DATA_JSON_URL, timeout=CATALOG_TIMEOUT)
    year = max_vintage(resp.json(), params["dataset"])
    if year is None:
        raise ProbeError(f"dataset {params['dataset']!r} not found in {DATA_JSON_URL}")
    return Observation("vintage", year, datetime.now(timezone.utc), "api.census.gov/data.json")


SPEC = ProbeSpec(
    name="census_vintage",
    kind="vintage",
    required=frozenset({"dataset"}),
    optional=frozenset(),
    run=run,
)
```

```python
# packages/sdc-core/src/sdc_core/sources/checks/probes/bea_vintage.py
"""Newest year a BEA Regional table offers, via GetParameterValuesFiltered."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone

import httpx

from sdc_core.sources.checks.compare import Observation
from sdc_core.sources.checks.probes._http import ProbeError, request_with_retry
from sdc_core.sources.checks.probes._spec import ProbeSpec

BEA_URL = "https://apps.bea.gov/api/data/"
_YEAR = re.compile(r"\b(19\d{2}|20\d{2})\b")


def max_year_from_params(payload: dict) -> int | None:
    values = payload.get("BEAAPI", {}).get("Results", {}).get("ParamValue", [])
    if isinstance(values, dict):
        values = [values]
    years: list[int] = []
    for item in values:
        for v in item.values():
            years.extend(int(y) for y in _YEAR.findall(str(v)))
    return max(years) if years else None


def run(params: dict, client: httpx.Client) -> Observation:
    key = os.environ.get("BEA_API_KEY", "")
    if not key:
        raise ProbeError("BEA_API_KEY environment variable is not set")
    query = {
        "UserID": key,
        "method": "GetParameterValuesFiltered",
        "datasetname": params["dataset"],
        "TargetParameter": "Year",
        "TableName": params["table"],
        "ResultFormat": "json",
    }
    resp = request_with_retry(client, "GET", BEA_URL, params=query)
    payload = resp.json()
    error = payload.get("BEAAPI", {}).get("Results", {}).get("Error")
    if error:
        raise ProbeError(f"BEA API error: {error.get('APIErrorDescription', error)}")
    year = max_year_from_params(payload)
    if year is None:
        raise ProbeError(f"no Year values returned for {params['dataset']}/{params['table']}")
    detail = f"apps.bea.gov {params['dataset']}/{params['table']} Year values"
    return Observation("vintage", year, datetime.now(timezone.utc), detail)


SPEC = ProbeSpec(
    name="bea_vintage",
    kind="vintage",
    required=frozenset({"dataset", "table"}),
    optional=frozenset(),
    run=run,
)
```

Update `probes/__init__.py` to the final form:

```python
"""Registry of probe kinds. Add a module and list it here to add a probe."""

from __future__ import annotations

from sdc_core.sources.checks.probes import (
    bea_vintage,
    census_vintage,
    html_years,
    http_file,
    lodes_vintage,
    manual,
)
from sdc_core.sources.checks.probes._spec import ProbeSpec

PROBES: dict[str, ProbeSpec] = {
    m.SPEC.name: m.SPEC
    for m in (manual, http_file, html_years, lodes_vintage, census_vintage, bea_vintage)
}

__all__ = ["PROBES", "ProbeSpec"]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/sources_checks -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-core/src/sdc_core/sources/checks/probes tests/sources_checks
git commit -m "feat(sources): census_vintage and bea_vintage probes

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: State store and repo paths

**Files:**
- Create: `packages/sdc-core/src/sdc_core/sources/checks/state.py`
- Create: `packages/sdc-core/src/sdc_core/sources/checks/paths.py`
- Test: `tests/sources_checks/test_state.py`, `tests/sources_checks/conftest.py`

**Interfaces:**
- Produces:
  - `load_state(path: Path) -> dict[str, Observation]` (missing file → `{}`)
  - `save_state(path: Path, state: dict[str, Observation]) -> None` (sorted keys, 2-space indent, trailing newline)
  - `find_repo_root(start: Path | None = None) -> Path` (walk up to the dir containing `sync.yaml`; `FileNotFoundError` otherwise)
  - `registry_path(root) -> Path` = `root/meta/source_checks.yaml`; `state_path(root) -> Path` = `root/meta/source_checks_state.json`
  - pytest fixture `repo` (temp repo root) used by Tasks 6–8.

- [ ] **Step 1: Write the fixture and failing tests**

```python
# tests/sources_checks/conftest.py
"""A throwaway repo root: sync.yaml marker, meta/, and three pipelines."""

from pathlib import Path

import pytest


def add_pipeline(root: Path, rel: str, sources_yaml: str) -> Path:
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / "pipeline.yaml").write_text(f"name: {d.name.lower()}\nsources:\n{sources_yaml}")
    return d


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "sync.yaml").write_text("dashboards: {}\n")
    (tmp_path / "meta").mkdir()
    add_pipeline(tmp_path, "demographics/Age", "  va:\n    type: census_acs\n    years: [2022, 2023]\n")
    add_pipeline(
        tmp_path,
        "demographics/Geographic Mobility (HOI)",
        "  va:\n    type: census_acs\n    years: [2023, 2024]\n  chr:\n    type: county_health_rankings\n    urls:\n      2024: https://chr.example/2024.xlsx\n      2025: https://chr.example/2025.xlsx\n",
    )
    add_pipeline(tmp_path, "energy/Thing", "  va:\n    type: computed\n")
    # a hidden dir and a worktree must never be discovered as pipelines
    add_pipeline(tmp_path, ".claude/worktrees/x/demographics/Age", "  va:\n    type: census_acs\n")
    add_pipeline(tmp_path, "worktree-feature/demographics/Age", "  va:\n    type: census_acs\n")
    return tmp_path
```

```python
# tests/sources_checks/test_state.py
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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/sources_checks/test_state.py -q`
Expected: FAIL with `ModuleNotFoundError` for `paths` / `state`.

- [ ] **Step 3: Implement**

```python
# packages/sdc-core/src/sdc_core/sources/checks/paths.py
"""Where the registry and state live, relative to the monorepo root."""

from __future__ import annotations

from pathlib import Path

ROOT_MARKER = "sync.yaml"


def find_repo_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    for candidate in [start, *start.parents]:
        if (candidate / ROOT_MARKER).exists():
            return candidate
    raise FileNotFoundError(f"could not find repo root: no {ROOT_MARKER} in {start} or its parents")


def registry_path(root: Path) -> Path:
    return root / "meta" / "source_checks.yaml"


def state_path(root: Path) -> Path:
    return root / "meta" / "source_checks_state.json"
```

```python
# packages/sdc-core/src/sdc_core/sources/checks/state.py
"""Last accepted observation per source id, persisted as committed JSON."""

from __future__ import annotations

import json
from pathlib import Path

from sdc_core.sources.checks.compare import Observation


def load_state(path: Path) -> dict[str, Observation]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {sid: Observation.from_dict(d) for sid, d in raw.items()}


def save_state(path: Path, state: dict[str, Observation]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {sid: state[sid].to_dict() for sid in sorted(state)}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/sources_checks -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-core/src/sdc_core/sources/checks tests/sources_checks
git commit -m "feat(sources): state store and repo path helpers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Registry: load, validate, discover, audit, sync-latest

**Files:**
- Create: `packages/sdc-core/src/sdc_core/sources/checks/registry.py`
- Modify: `docs/specs/2026-10-13-source-freshness-check-design.md` (Section 1: add `untracked:`; Background: 73 pipelines)
- Test: `tests/sources_checks/test_registry.py`

**Interfaces:**
- Consumes: `PROBES` (Task 4 final), `yaml`.
- Produces:
  - `class RegistryError(ValueError)`
  - `PipelineRef(path: str, latest: int | None = None, source: str | None = None, key: str | None = None)`
  - `SourceEntry(id: str, probe: str, params: dict, pipelines: tuple[PipelineRef, ...])`
  - `Registry(sources: tuple[SourceEntry, ...], untracked: dict[str, str])` with `.tracked_paths() -> set[str]`
  - `load_registry(path: Path) -> Registry`
  - `discover_pipelines(repo_root: Path) -> list[str]` (posix relative dirs, sorted; skips any path component starting with `.`, containing `worktree`, or equal to `node_modules`)
  - `audit(registry, repo_root) -> tuple[list[str], list[str]]` → `(unregistered_on_disk, registered_but_missing)`
  - `max_year(obj) -> int | None` (recursive: `years:` list items and `urls:` dict keys)
  - `compute_latest(repo_root, ref: PipelineRef) -> int | None`
  - `sync_latest(registry_path, repo_root, *, dry_run: bool) -> list[tuple[str, str, int | None, int | None]]` → `(source_id, pipeline_path, old, new)`; `new is None` means unresolvable and untouched
  - `REGISTRY_HEADER: str`

- [ ] **Step 1: Write the failing tests**

```python
# tests/sources_checks/test_registry.py
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
    assert compute_latest(repo, PipelineRef(path=gm, source="chr", key="urls")) is None  # urls is a dict, not walkable past key
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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/sources_checks/test_registry.py -q`
Expected: FAIL with `ModuleNotFoundError` for `registry`.

- [ ] **Step 3: Implement**

```python
# packages/sdc-core/src/sdc_core/sources/checks/registry.py
"""meta/source_checks.yaml: which upstream sources feed which pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from sdc_core.sources.checks.probes import PROBES

REGISTRY_HEADER = (
    "# Machine-maintained by `sdc sources sync-latest`; comments outside this header are lost\n"
    "# on rewrite. Use a source's `note` key for remarks that must survive.\n"
)
ENTRY_KEYS = {"probe", "pipelines"}
PIPELINE_KEYS = {"path", "latest", "source", "key"}
SKIP_DIR_PARTS = {"node_modules"}


class RegistryError(ValueError):
    """The registry file is malformed."""


@dataclass(frozen=True)
class PipelineRef:
    path: str  # pipeline dir relative to repo root, as on disk
    latest: int | None = None  # max year we have ingested (vintage probes only)
    source: str | None = None  # name under the pipeline's `sources:`; None = all
    key: str | None = None  # sub-key within that source to restrict the year walk


@dataclass(frozen=True)
class SourceEntry:
    id: str
    probe: str
    params: dict
    pipelines: tuple[PipelineRef, ...]


@dataclass(frozen=True)
class Registry:
    sources: tuple[SourceEntry, ...]
    untracked: dict[str, str]  # pipeline path -> reason

    def tracked_paths(self) -> set[str]:
        return {ref.path for entry in self.sources for ref in entry.pipelines}


def _parse_pipeline(sid: str, spec_kind: str, raw: object) -> PipelineRef:
    if not isinstance(raw, dict) or "path" not in raw:
        raise RegistryError(f"{sid}: each pipeline entry needs a `path`")
    unknown = raw.keys() - PIPELINE_KEYS
    if unknown:
        raise RegistryError(f"{sid}/{raw['path']}: unknown pipeline keys {sorted(unknown)}")
    latest = raw.get("latest")
    if spec_kind == "vintage" and not isinstance(latest, int):
        raise RegistryError(f"{sid}/{raw['path']}: vintage probe requires integer latest")
    if spec_kind != "vintage" and latest is not None:
        raise RegistryError(f"{sid}/{raw['path']}: latest is only allowed on vintage probes")
    return PipelineRef(
        path=str(raw["path"]), latest=latest, source=raw.get("source"), key=raw.get("key")
    )


def _parse_entry(sid: str, body: object) -> SourceEntry:
    if not isinstance(body, dict):
        raise RegistryError(f"{sid}: entry must be a mapping")
    probe_name = body.get("probe")
    spec = PROBES.get(probe_name)
    if spec is None:
        raise RegistryError(f"{sid}: unknown probe {probe_name!r}; known: {sorted(PROBES)}")
    params = {k: v for k, v in body.items() if k not in ENTRY_KEYS}
    missing = spec.required - params.keys()
    if missing:
        raise RegistryError(f"{sid}: missing keys {sorted(missing)} for probe {probe_name}")
    unknown = params.keys() - spec.required - spec.optional
    if unknown:
        raise RegistryError(f"{sid}: unknown keys {sorted(unknown)} for probe {probe_name}")
    if spec.validate is not None:
        try:
            spec.validate(params)
        except ValueError as exc:
            raise RegistryError(f"{sid}: {exc}") from exc
    refs = tuple(_parse_pipeline(sid, spec.kind, p) for p in body.get("pipelines") or [])
    if not refs:
        raise RegistryError(f"{sid}: no pipelines listed")
    return SourceEntry(id=sid, probe=probe_name, params=params, pipelines=refs)


def load_registry(path: Path) -> Registry:
    raw = yaml.safe_load(path.read_text()) or {}
    entries = tuple(_parse_entry(sid, body) for sid, body in (raw.get("sources") or {}).items())
    untracked: dict[str, str] = {}
    for item in raw.get("untracked") or []:
        if not isinstance(item, dict) or "path" not in item or "reason" not in item:
            raise RegistryError("untracked entries need path and reason")
        untracked[str(item["path"])] = str(item["reason"])
    return Registry(sources=entries, untracked=untracked)


def discover_pipelines(repo_root: Path) -> list[str]:
    """Every dir under the repo containing pipeline.yaml, excluding hidden dirs and worktrees."""
    found: list[str] = []
    for p in repo_root.rglob("pipeline.yaml"):
        rel = p.parent.relative_to(repo_root)
        parts = rel.parts
        if any(part.startswith(".") or "worktree" in part or part in SKIP_DIR_PARTS for part in parts):
            continue
        found.append(rel.as_posix())
    return sorted(found)


def audit(registry: Registry, repo_root: Path) -> tuple[list[str], list[str]]:
    on_disk = set(discover_pipelines(repo_root))
    known = registry.tracked_paths() | set(registry.untracked)
    return sorted(on_disk - known), sorted(known - on_disk)


def max_year(obj: object) -> int | None:
    """Largest year in any `years:` list or `urls:` dict key, at any depth."""
    found: set[int] = set()

    def walk(x: object) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "years" and isinstance(v, list):
                    found.update(int(y) for y in v if str(y).isdigit())
                elif k == "urls" and isinstance(v, dict):
                    found.update(int(y) for y in v if str(y).isdigit())
                else:
                    walk(v)
        elif isinstance(x, list):
            for item in x:
                walk(item)

    walk(obj)
    return max(found) if found else None


def compute_latest(repo_root: Path, ref: PipelineRef) -> int | None:
    cfg_path = repo_root / ref.path / "pipeline.yaml"
    if not cfg_path.exists():
        return None
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    target: object = cfg.get("sources") or {}
    if not isinstance(target, dict):
        return None
    if ref.source is not None:
        if ref.source not in target:
            return None
        target = target[ref.source]
    if ref.key is not None:
        if not isinstance(target, dict) or ref.key not in target:
            return None
        target = target[ref.key]
    return max_year(target)


def sync_latest(
    registry_path: Path, repo_root: Path, *, dry_run: bool
) -> list[tuple[str, str, int | None, int | None]]:
    """Rewrite each vintage pipeline's `latest` from its pipeline.yaml.

    Returns (source_id, pipeline_path, old, new) for every vintage pipeline ref.
    `new is None` means the source/key could not be resolved; that ref is left untouched.
    """
    raw = yaml.safe_load(registry_path.read_text()) or {}
    registry = load_registry(registry_path)
    changes: list[tuple[str, str, int | None, int | None]] = []
    dirty = False
    for entry in registry.sources:
        if PROBES[entry.probe].kind != "vintage":
            continue
        for i, ref in enumerate(entry.pipelines):
            new = compute_latest(repo_root, ref)
            changes.append((entry.id, ref.path, ref.latest, new))
            if new is not None and new != ref.latest:
                raw["sources"][entry.id]["pipelines"][i]["latest"] = new
                dirty = True
    if dirty and not dry_run:
        body = yaml.safe_dump(raw, sort_keys=False, allow_unicode=True, width=120)
        registry_path.write_text(REGISTRY_HEADER + body)
    return changes
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/sources_checks -q`
Expected: all pass.

- [ ] **Step 5: Amend the spec**

In `docs/specs/2026-10-13-source-freshness-check-design.md`:

1. In **Background**, replace "39 pipelines declare their inputs" with "73 pipelines (39 at depth two, 33 nested three to five levels deep under food, housing, business_climate and health, plus the depth-one `demographics/pipeline.yaml` umbrella) declare their inputs". Add a row to the table: `| licensed / live snapshots (Mergent Intellect, OSM, SAMHSA, HIFLD, Feeding America) | 20 | none |`.
2. In **Section 1**, after the registry example, add this paragraph and YAML block:

~~~markdown
A top-level `untracked:` list acknowledges pipelines that intentionally have no probe:

```yaml
untracked:
  - {path: energy/DataCenters, reason: exploratory energy category; no upstream release}
  - {path: transportation/Walkability, reason: computed from other SDC datasets}
```

`audit` treats these as registered; `check` still lists them as `not_tracked` and shows the
reason in DETAIL. A pipeline in neither list is an `audit` failure.
~~~

3. In **Section 4**, change the `audit` sentence to: "`audit` prints two lists and exits 1 if either is non-empty: pipelines on disk that are in neither `sources:` nor `untracked:`; and registry paths (either list) that do not exist on disk."
4. In **Section 1** rules, change "seeded by hand for all 33 non-energy pipelines" to "seeded by hand for all 73 pipelines: every pipeline appears under `sources:` or `untracked:`".

- [ ] **Step 6: Commit**

```bash
git add packages/sdc-core/src/sdc_core/sources/checks/registry.py tests/sources_checks docs/specs/2026-10-13-source-freshness-check-design.md
git commit -m "feat(sources): registry load/validate, pipeline discovery, audit, sync-latest; spec: untracked list, 73 pipelines

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: `run_checks` orchestration and report rendering

**Files:**
- Create: `packages/sdc-core/src/sdc_core/sources/checks/report.py`
- Modify: `packages/sdc-core/src/sdc_core/sources/checks/__init__.py` (was empty)
- Test: `tests/sources_checks/test_report.py`, `tests/sources_checks/test_run_checks.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `report.sort_rows(rows: list[Row]) -> list[Row]`
  - `report.render_table(rows) -> str`, `report.render_json(rows) -> str`, `report.exit_code(rows) -> int`
  - `run_checks(registry: Registry, state: dict[str, Observation], repo_root: Path, *, source_filter: set[str] = frozenset(), pipeline_filter: set[str] = frozenset(), client: httpx.Client | None = None) -> tuple[list[Row], dict[str, Observation]]` — rows sorted; second item holds only successful, non-manual observations (what `--update-state` should merge).
  - `make_client` is re-exported from `sdc_core.sources.checks` so the CLI test can monkeypatch it.

- [ ] **Step 1: Write the failing tests**

```python
# tests/sources_checks/test_report.py
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
```

```python
# tests/sources_checks/test_run_checks.py
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
    assert [(r.source, r.pipeline) for r in rows] == [("chr_va", "demographics/Geographic Mobility (HOI)")]
    assert all(r.status != "not_tracked" for r in rows)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/sources_checks/test_report.py tests/sources_checks/test_run_checks.py -q`
Expected: FAIL with `ImportError` (`run_checks`, `report`).

- [ ] **Step 3: Implement**

```python
# packages/sdc-core/src/sdc_core/sources/checks/report.py
"""Render rows as a fixed-width table or JSON; derive the exit code."""

from __future__ import annotations

import json

from sdc_core.sources.checks.compare import ACTION_STATUSES, STATUS_ORDER, Row

COLUMNS = ["STATUS", "SOURCE", "PIPELINE", "OURS", "UPSTREAM", "DETAIL"]


def sort_rows(rows: list[Row]) -> list[Row]:
    return sorted(rows, key=lambda r: (STATUS_ORDER[r.status], r.source or "~", r.pipeline))


def _cell(value: object) -> str:
    return "-" if value is None else str(value)


def render_table(rows: list[Row]) -> str:
    data = [
        [r.status, _cell(r.source), r.pipeline, _cell(r.ours), _cell(r.upstream), r.detail]
        for r in rows
    ]
    widths = [max(len(line[i]) for line in [COLUMNS, *data]) for i in range(len(COLUMNS) - 1)]

    def fmt(cells: list[str]) -> str:
        fixed = "  ".join(c.ljust(w) for c, w in zip(cells[:-1], widths))
        return f"{fixed}  {cells[-1]}".rstrip()

    return "\n".join([fmt(COLUMNS), *(fmt(d) for d in data)])


def render_json(rows: list[Row]) -> str:
    return json.dumps([r.to_dict() for r in rows], indent=2) + "\n"


def exit_code(rows: list[Row]) -> int:
    return 1 if any(r.status in ACTION_STATUSES for r in rows) else 0
```

```python
# packages/sdc-core/src/sdc_core/sources/checks/__init__.py
"""Upstream source freshness checks: probes -> compare -> rows.

Entry point is ``run_checks``. See docs/specs/2026-10-13-source-freshness-check-design.md.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from sdc_core.log import get_logger
from sdc_core.sources.checks.compare import Observation, Row, compare, describe
from sdc_core.sources.checks.probes import PROBES
from sdc_core.sources.checks.probes._http import ProbeError, make_client
from sdc_core.sources.checks.registry import Registry, discover_pipelines
from sdc_core.sources.checks.report import sort_rows

log = get_logger("sdc.sources.checks")

__all__ = ["run_checks", "make_client"]


def run_checks(
    registry: Registry,
    state: dict[str, Observation],
    repo_root: Path,
    *,
    source_filter: set[str] = frozenset(),
    pipeline_filter: set[str] = frozenset(),
    client: httpx.Client | None = None,
) -> tuple[list[Row], dict[str, Observation]]:
    """Probe every (filtered) source once and emit one row per consuming pipeline.

    Returns sorted rows and the observations worth persisting (successful, non-manual).
    """
    own_client = client is None
    client = client or make_client()
    rows: list[Row] = []
    observed: dict[str, Observation] = {}
    try:
        for entry in registry.sources:
            if source_filter and entry.id not in source_filter:
                continue
            refs = [r for r in entry.pipelines if not pipeline_filter or r.path in pipeline_filter]
            if not refs:
                continue
            spec = PROBES[entry.probe]
            try:
                obs = spec.run(entry.params, client)
            except ProbeError as exc:
                message = str(exc)
            except Exception as exc:  # noqa: BLE001 - any probe failure is an error row, never a crash
                message = f"{type(exc).__name__}: {exc}"
            else:
                message = None
            if message is not None:
                log.warning("%s: %s", entry.id, message)
                rows.extend(
                    Row("error", entry.id, r.path, r.latest, None, message, None) for r in refs
                )
                continue
            if obs.kind != "manual":
                observed[entry.id] = obs
            prior = state.get(entry.id)
            for r in refs:
                status = compare(obs, r.latest, prior)
                upstream = obs.value if obs.kind == "vintage" else None
                rows.append(
                    Row(status, entry.id, r.path, r.latest, upstream, describe(status, obs, prior), obs.fetched_at)
                )
    finally:
        if own_client:
            client.close()

    if not source_filter and not pipeline_filter:
        tracked = registry.tracked_paths()
        for path in discover_pipelines(repo_root):
            if path not in tracked:
                reason = registry.untracked.get(path, "no registry entry")
                rows.append(Row("not_tracked", None, path, None, None, reason, None))
    return sort_rows(rows), observed
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/sources_checks -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-core/src/sdc_core/sources/checks tests/sources_checks
git commit -m "feat(sources): run_checks orchestration and table/JSON report

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: CLI wiring (`sdc sources check | audit | sync-latest`)

**Files:**
- Modify: `packages/sdc-core/src/sdc_core/cli.py` (append a new group after the `zenodo` group; also add three lines to the module docstring)
- Test: `tests/sources_checks/test_cli.py`

**Interfaces:**
- Consumes: `run_checks`, `make_client` (from `sdc_core.sources.checks`), `load_registry`, `audit`, `sync_latest`, `load_state`, `save_state`, `find_repo_root`, `registry_path`, `state_path`, `render_table`, `render_json`, `exit_code`.
- Produces: click commands `sources check`, `sources audit`, `sources sync-latest`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/sources_checks/test_cli.py
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
    monkeypatch.setattr(checks_pkg, "make_client", lambda: make_client(transport=httpx.MockTransport(handler)))
    return CliRunner()


def test_check_table_exit_code_and_no_state_write(repo, monkeypatch):
    runner = prepare(repo, monkeypatch)
    result = runner.invoke(main, ["sources", "check"])
    assert result.exit_code == 1, result.output
    lines = result.output.splitlines()
    assert lines[0].startswith("STATUS")
    assert lines[1].startswith("new_vintage") and "demographics/Age" in lines[1]
    assert any(l.startswith("baseline") for l in lines)
    assert any(l.startswith("current") and "Geographic Mobility (HOI)" in l for l in lines)
    assert any(l.startswith("not_tracked") and "energy/Thing" in l and "exploratory" in l for l in lines)
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
        ["sources", "check", "--pipeline", "demographics/Geographic Mobility (HOI)", "--json", str(out)],
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
    dirty_registry = REGISTRY.replace("untracked:\n  - {path: energy/Thing, reason: exploratory}\n", "untracked:\n  - {path: ghost/P, reason: gone}\n")
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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/sources_checks/test_cli.py -q`
Expected: FAIL with `Error: No such command 'sources'` in result output (exit_code 2).

- [ ] **Step 3: Implement**

Append to `packages/sdc-core/src/sdc_core/cli.py` (after the `zenodo_status` command, end of file):

```python
# ---------------------------------------------------------------------------
# sdc sources
# ---------------------------------------------------------------------------


@main.group()
def sources():
    """Upstream source freshness checks (registry: meta/source_checks.yaml)."""
    pass


@sources.command("check")
@click.option("--source", "source_ids", multiple=True, help="Only this source id (repeatable)")
@click.option("--pipeline", "pipelines", multiple=True, help="Only this pipeline path (repeatable)")
@click.option("--json", "json_path", type=click.Path(dir_okay=False), default=None,
              help="Also write the rows to this JSON file")
@click.option("--update-state", is_flag=True,
              help="Record successful observations as the new baseline in meta/source_checks_state.json")
def sources_check(source_ids: tuple[str, ...], pipelines: tuple[str, ...], json_path: str | None,
                  update_state: bool):
    """Compare upstream vintages/fingerprints against what each pipeline has ingested.

    Exit 0 when every row is current, baseline, or not_tracked; 1 otherwise.
    """
    from sdc_core.sources.checks import run_checks
    from sdc_core.sources.checks.paths import find_repo_root, registry_path, state_path
    from sdc_core.sources.checks.registry import load_registry
    from sdc_core.sources.checks.report import exit_code, render_json, render_table
    from sdc_core.sources.checks.state import load_state, save_state

    root = find_repo_root()
    registry = load_registry(registry_path(root))
    state = load_state(state_path(root))
    rows, observed = run_checks(
        registry, state, root, source_filter=set(source_ids), pipeline_filter=set(pipelines)
    )
    click.echo(render_table(rows))
    if json_path:
        pathlib.Path(json_path).write_text(render_json(rows))
    if update_state:
        state.update(observed)
        save_state(state_path(root), state)
        click.echo(f"state updated: {state_path(root)}")
    sys.exit(exit_code(rows))


@sources.command("audit")
def sources_audit():
    """List pipelines missing from the registry and registry paths missing on disk."""
    from sdc_core.sources.checks.paths import find_repo_root, registry_path
    from sdc_core.sources.checks.registry import audit, load_registry

    root = find_repo_root()
    registry = load_registry(registry_path(root))
    unregistered, missing = audit(registry, root)
    if unregistered:
        click.echo("Pipelines on disk with no registry entry (add under sources: or untracked:):")
        for path in unregistered:
            click.echo(f"  {path}")
    if missing:
        click.echo("Registry paths not found on disk:")
        for path in missing:
            click.echo(f"  {path}")
    if not unregistered and not missing:
        click.echo("registry and pipelines on disk agree")
    sys.exit(1 if unregistered or missing else 0)


@sources.command("sync-latest")
@click.option("--dry-run", is_flag=True, help="Report what would change without writing")
def sources_sync_latest(dry_run: bool):
    """Rewrite each vintage pipeline's `latest` from its pipeline.yaml years."""
    from sdc_core.sources.checks.paths import find_repo_root, registry_path
    from sdc_core.sources.checks.registry import sync_latest

    root = find_repo_root()
    changes = sync_latest(registry_path(root), root, dry_run=dry_run)
    verb = "WOULD SET" if dry_run else "SET"
    n_changed = 0
    for sid, path, old, new in changes:
        if new is None:
            click.echo(f"UNRESOLVED  {sid:<24s} {path}  (latest stays {old})")
        elif new != old:
            n_changed += 1
            click.echo(f"{verb:<11s} {sid:<24s} {path}  {old} -> {new}")
    click.echo(f"{len(changes)} vintage pipeline refs checked, {n_changed} {'would change' if dry_run else 'changed'}")
```

Also extend the module docstring at the top of `cli.py`:

```python
    sdc sources check        # upstream freshness report (exit 1 when action is needed)
    sdc sources audit        # pipelines missing from meta/source_checks.yaml
    sdc sources sync-latest  # refresh `latest` years from pipeline.yaml
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/sources_checks -q && uv run sdc sources --help`
Expected: all tests pass; help lists `audit`, `check`, `sync-latest`.

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-core/src/sdc_core/cli.py tests/sources_checks/test_cli.py
git commit -m "feat(cli): sdc sources check/audit/sync-latest

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Seed the registry, calibrate against live sources, record the baseline

This task touches the network on purpose. It is the acceptance test from spec Section 6.

**Files:**
- Create: `meta/source_checks.yaml`
- Create: `meta/source_checks_state.json` (via `--update-state`)
- Modify (only if calibration requires): `meta/source_checks.yaml` patterns/URLs
- Modify: `docs/specs/2026-10-13-source-freshness-check-design.md` (record final registry counts in Background)

**Interfaces:** none new.

- [ ] **Step 1: Write the registry**

Create `meta/source_checks.yaml` with exactly this content. `latest` values were read from each `pipeline.yaml` on 2026-10-13; Step 3 verifies them with `sync-latest --dry-run`.

```yaml
# Machine-maintained by `sdc sources sync-latest`; comments outside this header are lost
# on rewrite. Use a source's `note` key for remarks that must survive.
sources:
  acs5:
    probe: census_vintage
    dataset: acs/acs5
    pipelines:
      - {path: broadband/Household Broadband, latest: 2024}
      - {path: demographics/Age, latest: 2024}
      - {path: demographics/Gender, latest: 2024}
      - {path: "demographics/Geographic Mobility (HOI)", latest: 2024}
      - {path: demographics/Language, latest: 2024}
      - {path: demographics/Population Density, latest: 2024}
      - {path: demographics/Race, latest: 2024}
      - {path: "demographics/Segregation Index (HOI)", latest: 2024}
      - {path: demographics/Veteran, latest: 2024}
      - {path: demographics/Cooperative extension, source: va, key: perc_male, latest: 2024}
      - {path: education/Postsecondary, latest: 2024}
      - {path: education/Years of Schooling, latest: 2024}
      - {path: financial_well_being/Employment Rates, latest: 2024}
      - {path: financial_well_being/Household Income, latest: 2024}
      - {path: financial_well_being/Income Inequality, latest: 2024}
      - {path: financial_well_being/Material_Deprivation, latest: 2024}
      - {path: financial_well_being/Poverty, latest: 2024}
      - {path: "food/Food and Nutrition Assistance/Supplemental Nutrition Assistance Program (SNAP)", latest: 2024}
      - {path: health/Social Vulnerability Index, latest: 2024}
      - {path: health/System Usage and Insurance/Without Health Insurance, latest: 2024}
      - {path: transportation/Population Characteristics, latest: 2024}

  chr_va:
    probe: html_years
    url: https://www.countyhealthrankings.org/health-data/virginia/data-and-resources
    pattern: "(\\d{4})(?: |%20)County(?: |%20)Health(?: |%20)Rankings(?: |%20)Virginia(?: |%20)Data"
    pipelines:
      - {path: education/Funding, latest: 2025}
      - {path: demographics/Cooperative extension, source: va, key: county_health_rankings, latest: 2025}
      - {path: health/System Usage and Insurance/Preventable Hospitalizations, latest: 2025}

  ookla_fixed_tiles:
    probe: html_years
    url: "https://ookla-open-data.s3-us-west-2.amazonaws.com/?list-type=2&prefix=shapefiles/performance/type=fixed/&delimiter=/"
    pattern: "year=(\\d{4})/"
    pipelines:
      - {path: broadband/Ookla Speed, latest: 2025}

  lodes8_va_wac:
    probe: lodes_vintage
    url: https://lehd.ces.census.gov/data/lodes/LODES8/va/wac/
    pattern: "va_wac_S000_JT00_(\\d{4})\\.csv\\.gz"
    pipelines:
      - {path: financial_well_being/Employment Access Index, latest: 2023}
      - {path: business_climate/Employment/Worker_diversity, latest: 2019}

  bea_cainc4:
    probe: bea_vintage
    dataset: Regional
    table: CAINC4
    pipelines:
      - {path: financial_well_being/Personal Income, latest: 2024}

  cms_marketplace_puf:
    probe: html_years
    url: https://www.cms.gov/marketplace/resources/data/public-use-files
    pattern: "marketplace-puf/(\\d{4})/"
    pipelines:
      - {path: health/Health care cost, latest: 2026}

  vdoe_sol_pass_rates:
    probe: html_years
    url: https://www.doe.virginia.gov/data-policy-funding/data-reports/statistics-reports/sol-test-pass-rates-other-results
    pattern: "(20\\d{2})-20\\d{2}"
    pipelines:
      - {path: education/Reading, latest: 2024}

  hud_fmr:
    probe: html_years
    url: https://www.huduser.gov/portal/datasets/fmr.html
    pattern: "fmr/fmr(20\\d{2})/"
    pipelines:
      - {path: housing/Cost/Rent, latest: 2025}

  ejscreen_archive:
    probe: html_years
    url: https://web.archive.org/web/2024/https://gaftp.epa.gov/EJSCREEN/
    pattern: "EJSCREEN/(20\\d{2})/"
    note: EPA removed EJScreen in 2025; this is a Wayback snapshot and will not advance
    pipelines:
      - {path: "environment/Environmental Hazard Index (HOI)", latest: 2024}

  vera_incarceration_trends:
    probe: http_file
    url: https://raw.githubusercontent.com/vera-institute/incarceration-trends/main/incarceration_trends_county.csv
    pipelines:
      - {path: "public_safety/Incarceration (HOI)"}

  ppi_va_tract_2020:
    probe: http_file
    url: https://www.prisonpolicy.org/origin/va/2020/tract.html
    pipelines:
      - {path: "public_safety/Incarceration (HOI)"}

  alice_va:
    probe: http_file
    url: https://www.unitedforalice.org/Attachments/StateDataSheet/DataSheet_VA.xlsx
    pipelines:
      - {path: "financial_well_being/Asset Limited Income Constrained Employed (ALICE)"}

  cms_hospital_general_information:
    probe: http_file
    url: https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/xubh-q36u
    note: dataset metadata JSON; its `modified` field changes on each CMS refresh
    pipelines:
      - {path: health/Health Care Services/Hospitals and Emergency Rooms/Service Access Scores}

  cms_physician_national_downloadable:
    probe: http_file
    url: https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/mj5m-pzi6
    note: dataset metadata JSON; its `modified` field changes on each CMS refresh
    pipelines:
      - {path: health/Health Care Services/Physicians/OB-GYN/Service Access Scores}
      - {path: health/Health Care Services/Physicians/Pediatric/Service Access Scores}
      - {path: health/Health Care Services/Physicians/Primary Care/Service Access Scores}

  nppes_npi_files:
    probe: http_file
    url: https://download.cms.gov/nppes/NPI_Files.html
    note: page lists the current monthly dissemination file; changes monthly by design
    pipelines:
      - {path: health/Health Care Services/Urgent Care Centers/Service Access Scores}

  vdh_hoi:
    probe: manual
    url: https://apps.vdh.virginia.gov/omhhe/hoi/
    note: no machine-readable release list; indicator Excel files are downloaded by hand
    pipelines:
      - {path: health/Health Opportunity Index}

  cdc_wonder_natality:
    probe: manual
    url: https://wonder.cdc.gov/natality-expanded-current.html
    note: WONDER D149 is a query form; check the "current" year range on the landing page
    pipelines:
      - {path: health/Prenatal Care Adequacy}

  vdss_daycare_locations:
    probe: manual
    url: https://www.dss.virginia.gov/facility/search/cc.cgi
    note: locations_{year}.csv is exported by hand into data/working
    pipelines:
      - {path: education/Daycare Accessibility}

  usda_fara:
    probe: manual
    url: https://www.ers.usda.gov/data-products/food-access-research-atlas/download-the-data
    note: 2019 is the latest atlas; ERS announces new editions on this page
    pipelines:
      - {path: "food/Food Access/Food Accessibility Indicator (HOI)"}

  feeding_america_mmg:
    probe: manual
    url: https://www.feedingamerica.org/research/map-the-meal-gap/by-county
    note: Map the Meal Gap Excel is requested from Feeding America and placed in data/working
    pipelines:
      - {path: food/Food Security/Feeding America/Overall Food Insecurity}

  usda_nass_census_of_agriculture:
    probe: manual
    url: https://quickstats.nass.usda.gov/
    note: Census of Agriculture is quinquennial (2022 current; next 2027)
    pipelines:
      - {path: business_climate/Industry specific/Agriculture}

  cdc_places:
    probe: manual
    url: https://www.cdc.gov/places/
    note: release year is two ahead of data year (2025 release = 2023 data); compare by hand
    pipelines:
      - {path: health/Mental Health/Mental and Physical Healthy Days}

  vdh_overdose_surveillance:
    probe: manual
    url: https://www.vdh.virginia.gov/surveillance-and-investigation/syndromic-surveillance/drug-overdose-surveillance/
    note: quarterly PDF/dashboard releases; no stable file URL
    pipelines:
      - {path: health/Substance Abuse/Drug Overdose ED Visits}

  hifld_ems:
    probe: manual
    url: https://hifld-geoplatform.opendata.arcgis.com/
    note: ArcGIS REST layer; check editingInfo.lastEditDate on the layer metadata by hand
    pipelines:
      - {path: health/Health Care Services/EMS/Service Catchment Scores}

  samhsa_findtreatment:
    probe: manual
    url: https://findtreatment.gov/locator
    note: live locator API; there is no release event, re-run on a cadence
    pipelines:
      - {path: health/Health Care Services/Drug and Rehab/Service Catchment Scores}
      - {path: health/Health Care Services/Mental Health/Service Access Scores}

untracked:
  - {path: demographics, reason: umbrella config listing demographic topics; data comes from the topic pipelines}
  - {path: "health/Access to Care Index (HOI)", reason: computed from other SDC datasets}
  - {path: transportation/Walkability, reason: computed from other SDC datasets}
  - {path: housing/Cost/Affordability_HT, reason: reproduced from a CNT H+T Index snapshot; no upstream feed}
  - {path: food/Food Access/Healthy Food Availability, reason: live OpenStreetMap extract; no vintage}
  - {path: "food/Food Security/Feeding America/Children's Food Insecurity", reason: derived from Overall Food Insecurity working data}
  - {path: food/Food Security/Feeding America/Food Budget Shortfall, reason: derived from Overall Food Insecurity working data}
  - {path: food/Food Security/Feeding America/Food Secure Average Meal Cost, reason: derived from Overall Food Insecurity working data}
  - {path: health/Health Care Services/Dentists/Service Catchment Scores, reason: static provider GeoJSON; no upstream feed}
  - {path: business_climate/Business_characteristics/Industry, reason: Mergent Intellect licensed 2020 snapshot}
  - {path: business_climate/Business_characteristics/Industry_Minority_owned, reason: Mergent Intellect licensed 2020 snapshot}
  - {path: business_climate/Business_characteristics/Minority_owned, reason: Mergent Intellect licensed 2020 snapshot}
  - {path: business_climate/Business_characteristics/Total, reason: Mergent Intellect licensed 2020 snapshot}
  - {path: business_climate/Employment/Industry, reason: Mergent Intellect licensed 2020 snapshot}
  - {path: business_climate/Employment/Industry_Minority_owned, reason: Mergent Intellect licensed 2020 snapshot}
  - {path: business_climate/Employment/Minority_owned, reason: Mergent Intellect licensed 2020 snapshot}
  - {path: business_climate/Employment/Total, reason: Mergent Intellect licensed 2020 snapshot}
  - {path: energy/DataCenters, reason: exploratory energy category; no upstream release}
  - {path: energy/DataCentersProjected, reason: exploratory energy category; no upstream release}
  - {path: energy/EVChargingDemand, reason: exploratory energy category; no upstream release}
  - {path: energy/EVChargingStations, reason: exploratory energy category; no upstream release}
  - {path: energy/PowerInfrastructure, reason: exploratory energy category; no upstream release}
  - {path: energy/ResidentialEnergyScenario, reason: exploratory energy category; no upstream release}
```

- [ ] **Step 2: Audit must be clean**

Run: `uv run sdc sources audit`
Expected: `registry and pipelines on disk agree`, exit 0. If it lists a pipeline, the seed above missed one: add it under `sources:` (if it has a probe-able upstream) or `untracked:` (with a reason), never silently.

- [ ] **Step 3: Verify `latest` values**

Run: `uv run sdc sources sync-latest --dry-run`
Expected: `… 0 would change` and no `UNRESOLVED` lines. If any `WOULD SET` appears, the hand-typed `latest` was wrong: run without `--dry-run` to fix it. If `UNRESOLVED` appears, the `source:`/`key:` on that ref is wrong: fix it so the walk finds a `years:` list or `urls:` map.

- [ ] **Step 4: Live calibration**

Run: `uv run sdc sources check` (network; set `BEA_API_KEY` and `CENSUS_API_KEY` in the environment as the pipelines do).
Expected: a table with `baseline` for every `http_file` source, `unverified` for every `manual`, numbers for every vintage source. Exit 1 is expected on first run (manual rows).

For each `error` row, decide:
- an `html_years` miss (`no year matched …`): open the URL, find how years appear, fix the `pattern` (keep exactly one capture group). Re-run with `--source ID` until it yields a plausible year.
- a URL 404 or a changed CMS dataset id: fix the URL in the registry.
- an upstream outage (5xx/timeout): leave as is; not a code failure.

Anything that cannot be made to probe cleanly becomes a `manual` entry with a `note`. Do not leave a permanently erroring source in the registry.

- [ ] **Step 5: Record the baseline**

Run: `uv run sdc sources check --update-state`
Expected: `meta/source_checks_state.json` is created with one entry per non-manual source that probed successfully. Re-run `uv run sdc sources check`; every `http_file` row should now be `current`.

- [ ] **Step 6: Record final counts in the spec**

In `docs/specs/2026-10-13-source-freshness-check-design.md` Background, after the table, add one line: "Seeded registry (2026-10-13): N sources under `sources:`, M pipelines tracked, K pipelines acknowledged under `untracked:`." using the actual counts from `grep -c "probe:" meta/source_checks.yaml`, the number of distinct tracked paths, and `grep -c "reason:" meta/source_checks.yaml`.

- [ ] **Step 7: Full test run and commit**

Run: `uv run pytest -q`
Expected: all tests pass (71 pre-existing + new).

```bash
git add meta/source_checks.yaml meta/source_checks_state.json docs/specs/2026-10-13-source-freshness-check-design.md
git commit -m "feat(sources): seed source_checks registry for all 73 pipelines and record baseline state

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review notes

- **Spec coverage.** Section 1 → Task 6 + Task 9. Section 2 (six probes, retry policy, timeouts, env keys) → Tasks 2–4. Section 3 (state file, comparison matrix, `--update-state` semantics, error rows don't overwrite) → Tasks 1, 5, 7, 8. Section 4 (three subcommands, sort order, exit code, `--json`, filters hide `not_tracked`) → Tasks 7–8. Section 5 (layout) → file structure above. Section 6 (network-free tests, acceptance) → every task's tests + Task 9.
- **Type consistency.** `Observation(kind, value, fetched_at, detail)` positional order is used identically in Tasks 1–7. `run_checks` returns `(list[Row], dict[str, Observation])` in Task 7 and is consumed that way in Task 8. `PipelineRef` field order `(path, latest, source, key)` matches the test in Task 6.
- **Review Focus coverage.** (1) special-character paths: Task 6 `test_sync_latest_writes_and_preserves_special_paths`, Task 8 `test_check_json_output_and_pipeline_filter_with_special_chars`. (2) data.json oddities: Task 4 `CATALOG`. (3) HEAD 405 / redirect / 404: Task 2. (4) implausible years: Task 3 `test_extract_max_year_filters_implausible`. (5) non-ProbeError exceptions: Task 7 `broken_json` source.
