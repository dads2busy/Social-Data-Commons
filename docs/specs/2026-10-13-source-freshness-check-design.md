# Source Freshness Check — Design

**Date:** 2026-10-13
**Status:** Approved (design); pending spec review → implementation plan

## Goal

Give the maintainer one command that answers: *which pipelines have a newer upstream
vintage, or a silently revised upstream file, than what we last ingested?* Today that
question is answered by visiting a dozen release pages by hand. Nothing in the monorepo,
the two dashboard repos, or CI tracks upstream state.

## Background

73 pipelines (39 at depth two, 33 nested three to five levels deep under food, housing,
business_climate and health, plus the depth-one `demographics/pipeline.yaml` umbrella) declare
their inputs under `sources:` in `pipeline.yaml`. The declarations fall into roughly twelve
source families:

| Family | Pipelines | Where "latest year" lives today |
|---|---|---|
| `census_acs` | 16 | `years:` list |
| `computed` / `mixed` (derived from other pipelines or ad hoc) | 6 | `years:` list or none |
| energy (`source:` string, exploratory) | 6 | none |
| URL-backed files (EJScreen, Vera, PPI, ALICE) | 4 | `url:` + `years:` |
| one-offs: ookla, county_health_rankings, vdoe, lodes_gravity, bea, cms_puf, vdh_hoi, nchs | 8 | `years:` or none |
| licensed / live snapshots (Mergent Intellect, OSM, SAMHSA, HIFLD, Feeding America) | 20 | none |

Existing repo-wide operations (`sdc version status`, `sdc zenodo status`, `sdc sync`) all
report on *our* state. None probe upstream. The existing `sdc_core/sources/` subpackage
holds only the shared CHR downloader.

## Decisions already made

These were settled during brainstorming and are not reopened here.

1. **Scope of this pass: CLI only.** A scheduled GitHub Action and a docs-site status
   page are explicit later wrappers. The CLI's exit code and `--json` output are designed
   so those wrappers need no new logic.
2. **Two signals, selectively applied.** *New vintage* (a year newer than our max) for
   sources with a year concept. *Content changed* (fingerprint differs from last
   snapshot) only for URL-backed sources that have no vintage concept. Content checks are
   not applied to vintage-bearing sources, to avoid timestamp noise.
3. **Central registry**, not per-`pipeline.yaml` annotations. One file,
   `meta/source_checks.yaml`, maps upstream sources to the pipelines that consume them.
   No `pipeline.yaml` is modified.
4. **Lives in sdc-core** as `sdc sources …`, matching how `version`, `zenodo`, and `sync`
   already work. The addition is purely additive and imports nothing from pipelines, so
   downstream impact on existing pipelines is nil.

## Section 1: Registry (`meta/source_checks.yaml`)

Source-centric, because many pipelines share one upstream (16 share ACS 5-year). One entry
per upstream source, keyed by a stable id.

```yaml
sources:
  acs5:
    probe: census_vintage
    dataset: acs/acs5
    pipelines:
      - {path: demographics/Age, latest: 2024}
      - {path: demographics/Race, latest: 2024}
      # ... one line per consuming pipeline

  alice_va:
    probe: http_file
    url: https://www.unitedforalice.org/Attachments/StateDataSheet/DataSheet_VA.xlsx
    pipelines:
      - {path: "financial_well_being/Asset Limited Income Constrained Employed (ALICE)"}

  vdh_hoi:
    probe: manual
    url: https://www.vdh.virginia.gov/omhhe/hoi/
    note: no machine-readable release list; checker prints the URL for a human to look
    pipelines:
      - {path: health/Health Opportunity Index}
```

Rules:

- `path` is the pipeline directory relative to the repo root, exactly as on disk (quoted
  when it contains spaces or parentheses).
- `latest` is required for vintage probes and forbidden for content and manual probes.
  It is the max of `years:` in that pipeline's `pipeline.yaml` for that source. The
  `sync-latest` subcommand fills and refreshes it; the maintainer does not edit it by hand.
- Probe-specific keys (`dataset`, `url`, `pattern`, …) are validated per probe kind at
  load time. Unknown keys are an error.
- Pipelines with no registry entry (computed, mixed, energy) are not silently omitted.
  They appear in `check` output as `not_tracked`, and `audit` lists them explicitly.
- The registry is seeded by hand for all 73 pipelines: every pipeline appears under
  `sources:` or `untracked:`. `sync-latest` can fill `latest` but cannot choose a probe.

A top-level `untracked:` list acknowledges pipelines that intentionally have no probe:

```yaml
untracked:
  - {path: energy/DataCenters, reason: exploratory energy category; no upstream release}
  - {path: transportation/Walkability, reason: computed from other SDC datasets}
```

`audit` treats these as registered; `check` still lists them as `not_tracked` and shows the
reason in DETAIL. A pipeline in neither list is an `audit` failure.

## Section 2: Probes

A probe is a function `(entry: dict, client: httpx.Client) -> Observation`.

```python
@dataclass(frozen=True)
class Observation:
    kind: Literal["vintage", "content", "manual"]
    value: int | str | None      # year for vintage, fingerprint for content, None for manual
    fetched_at: datetime         # UTC
    detail: str                  # one human-readable line (URL inspected, header used, …)
```

Probe kinds for this pass, covering every source family in the repo:

| Probe | Mechanism | Registry keys | Covers |
|---|---|---|---|
| `census_vintage` | GET `https://api.census.gov/data.json`; filter `dataset` entries whose `c_dataset` path equals the configured dataset; max `c_vintage` | `dataset` | acs5 (16 pipelines) |
| `bea_vintage` | BEA API `GetParameterValues` with `ParameterName=Year` for the configured dataset/table; max year | `dataset`, `table` | Personal Income |
| `lodes_vintage` | GET the LODES directory listing (e.g. `https://lehd.ces.census.gov/data/lodes/LODES8/va/od/`); regex `_(\d{4})\.csv\.gz`; max | `url`, `pattern` (default supplied) | Employment Access Index |
| `http_file` | HEAD the URL; fingerprint = `ETag`, else `Last-Modified`, else streamed SHA-256 of a GET body. `detail` names which was used. | `url` | ALICE, Vera CSV, PPI, CMS PUF, EJScreen |
| `html_years` | GET a page; apply configured regex with one capture group; max 4-digit year captured | `url`, `pattern` | NCHS, Ookla, CHR, VDOE (VDH HOI stays `manual` unless seeding finds a page that lists years) |
| `manual` | No network; returns `kind="manual"` with the URL in `detail` | `url`, optional `note` | anything the above cannot handle |

Policy common to every network probe:

- One retry on connection error or 5xx, then fail.
- A failed probe produces an `error` row for every consuming pipeline. It never aborts the
  run.
- Timeout 30 s per request. `httpx` is already an sdc-core dependency; no new dependency.
- `CENSUS_API_KEY` is read from the environment as elsewhere in sdc-core, but `data.json`
  does not require it. `BEA_API_KEY` is read from the environment; if absent, the
  `bea_vintage` probe reports `error` with a message saying which variable to set.
- Probes never write to disk and never cache. The state file (Section 3) is the only
  persistence.

## Section 3: State and comparison

`meta/source_checks_state.json` is committed. It holds the last accepted observation per
source id:

```json
{
  "alice_va": {"kind": "content", "value": "W/\"5f3a…\"", "fetched_at": "2026-10-13T14:02:11Z", "detail": "ETag"},
  "acs5":     {"kind": "vintage", "value": 2024,          "fetched_at": "2026-10-13T14:02:09Z", "detail": "api.census.gov/data.json"}
}
```

Comparison is a pure function `compare(observation, pipeline_latest, prior_state) -> Status`.

| Probe kind | Rule | Resulting status |
|---|---|---|
| vintage | observed year > pipeline `latest` | `new_vintage` |
| vintage | observed year ≤ pipeline `latest` | `current` |
| content | no prior state | `baseline` |
| content | fingerprint ≠ prior | `changed` |
| content | fingerprint = prior | `current` |
| manual | always | `unverified` |
| any | probe raised | `error` |
| (no registry entry) | — | `not_tracked` |

Vintage comparisons are per pipeline: two pipelines on acs5 can sit at different `latest`
values and get different statuses from one observation.

State is written only when `--update-state` is passed. A plain `check` never moves the
baseline, so an exploratory run cannot hide a change. With `--update-state`, the state for a
source is replaced by the new observation regardless of status (including `changed`), on the
grounds that the maintainer passed the flag to acknowledge what they saw. Rows with status
`error` do not overwrite prior state.

After the maintainer re-runs a pipeline for a new year, they run `sdc sources sync-latest`,
which rewrites each `latest` from the current `years:` lists. Nothing else needs editing.

## Section 4: CLI

```
sdc sources check [--source ID]... [--pipeline PATH]... [--json FILE] [--update-state]
sdc sources audit
sdc sources sync-latest [--dry-run]
```

`check` prints one table, sorted so action items come first (`new_vintage`, `changed`,
`unverified`, `error`, then `baseline`, `current`, `not_tracked`), then by source id, then
by pipeline path:

```
STATUS        SOURCE     PIPELINE                                  OURS   UPSTREAM  DETAIL
new_vintage   acs5       demographics/Age                          2023   2024      api.census.gov/data.json
changed       alice_va   financial_well_being/…(ALICE)             -      -         ETag changed (was W/"5f3a…")
unverified    vdh_hoi    health/Health Opportunity Index           -      -         https://www.vdh.virginia.gov/omhhe/hoi/
error         ookla      broadband/Ookla Speed                     2025   -         HTTP 503 after retry
baseline      vera       public_safety/Incarceration (HOI)         -      -         Last-Modified recorded
current       acs5       demographics/Race                         2024   2024
not_tracked   -          energy/DataCenters                        -      -
```

- `--source` and `--pipeline` filter rows; both repeatable; `not_tracked` rows are shown
  only when no filter is given.
- `--json FILE` writes the same rows as a JSON array of objects with keys `status`,
  `source`, `pipeline`, `ours`, `upstream`, `detail`, `fetched_at`.
- **Exit code** 0 when every row is `current`, `baseline`, or `not_tracked`; 1 when any row
  is `new_vintage`, `changed`, `unverified`, or `error`. This is what the deferred GitHub
  Action will key on.

`audit` prints two lists and exits 1 if either is non-empty: pipelines on disk (any
directory containing `pipeline.yaml`, excluding hidden dirs and worktrees, matching how
`sdc version status` discovers them) that are in neither `sources:` nor `untracked:`; and
registry paths (either list) that do not exist on disk.

`sync-latest` reads each registered pipeline's `pipeline.yaml`, computes max `years:` for
the matching source, and rewrites `latest` in the registry. It preserves comments and key
order where PyYAML allows: regenerate from the loaded dict with `yaml.safe_dump(sort_keys=False)`.
Comments are lost on rewrite; the file header says so, and the `note` key exists for
per-source remarks that must survive. With `--dry-run` it prints the diff and
writes nothing. If a registered source name does not appear under the pipeline's
`sources:`, it reports that pipeline as unresolvable and leaves `latest` untouched.

## Section 5: Code layout

```
packages/sdc-core/src/sdc_core/sources/checks/
  __init__.py       # run_checks(registry, state, source_filter, pipeline_filter) -> list[Row]
  registry.py       # load + validate meta/source_checks.yaml; discover pipelines; audit; sync_latest
  state.py          # load/save meta/source_checks_state.json
  compare.py        # Observation, Status, Row dataclasses; compare()
  report.py         # render_table(rows) -> str; render_json(rows) -> str; exit_code(rows) -> int
  probes/
    __init__.py     # PROBES: dict[str, Callable]; per-kind key validation
    census_vintage.py
    bea_vintage.py
    lodes_vintage.py
    http_file.py
    html_years.py
    manual.py
```

`cli.py` gains a `sources` click group with the three subcommands, resolving the registry
and state paths relative to the repo root (the directory containing `sync.yaml`, found by
walking up from the cwd, consistent with `sdc sync`).

Every unit has one job and a typed interface. Probes know nothing about pipelines; `compare`
knows nothing about HTTP; `report` knows nothing about either.

## Section 6: Testing

Tests live in `tests/sources_checks/` and never touch the network.

- **compare**: table-driven tests over every row of the Section 3 matrix, including the
  per-pipeline split on a shared vintage source.
- **probes**: one test module per probe using `httpx.MockTransport` with recorded response
  fixtures under `tests/sources_checks/fixtures/` (a trimmed `data.json`, a BEA parameter
  response, a LODES directory listing, an HTML page with years, HEAD responses with and
  without `ETag`). Each probe also has a test for the retry-then-error path and, for
  `http_file`, the fallback chain ETag → Last-Modified → SHA-256.
- **registry**: valid file loads; unknown probe kind rejected; unknown key rejected;
  `latest` present on a content probe rejected; `path` not on disk flagged by `audit`;
  `sync-latest` rewrites `latest` and reports unresolvable sources.
- **report**: sort order; exit code for each status mix; JSON shape.
- **cli**: `click.testing.CliRunner` smoke test for each subcommand against a temp repo
  root containing a two-pipeline fixture registry.

Acceptance: `uv run pytest tests/sources_checks` passes; `uv run sdc sources audit` exits 0
against the seeded registry; `uv run sdc sources check` runs end to end against the live
network and produces a table with no `error` rows caused by code (upstream outages are not
a failure of this work).

## Out of scope

No scheduling, no issue creation, no docs-site page, no automatic re-ingest, no change to
any `pipeline.yaml`, no notification. The energy pipelines are left `not_tracked` by design
(see memory: energy category is exploratory).
