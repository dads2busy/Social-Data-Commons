# Memoize the census10to20 Relationship-File Fetch + Age Proof — Design

## Overview

`sdc-census10to20`'s `get_2010_2020_bound_changes` re-downloads the Census
2010↔2020 relationship file on **every** call. `standardize_all` calls
`convert_2010_to_2020_bounds` once per (year × measure × geoid-length), so a
single pipeline run re-fetches the same (national tract / per-state block-group)
file ~100+ times — making each affected dataset's regeneration take minutes.
Memoize the fetch so it happens once per process; behavior-neutral. Then prove
the whole loop on `demographics/Age` (now fast): regenerate → acceptance test →
refresh dashboard outputs → commit.

## Decisions settled in brainstorming

- **Cache the download only**, keyed by `(res, state_fips)`. The geoid filter and
  `type_change` classification stay per-call (cheap, unchanged) → output is
  byte-identical to today.
- **Patch release `sdc-census10to20 v0.1.3`** (performance only).
- **Scope = cache + release + the Age proof.** The full 24-dataset regeneration
  batch is the separate follow-on (per `docs/census10to20-conversion-data-impact.md`).

## The change (`packages/sdc-census10to20/src/sdc_census10to20/crosswalk.py`)

Extract the URL read + column prep into a memoized helper:

```python
_RELATIONSHIP_CACHE: dict[tuple[str, str], pd.DataFrame] = {}

def _load_relationship(res: str, state_fips: str) -> pd.DataFrame:
    """Download + prep the Census relationship file once per (res, state_fips)."""
    key = (res, state_fips)
    if key not in _RELATIONSHIP_CACHE:
        # existing: pick URL by res, pd.read_csv(sep="|"), keep_cols,
        # drop AREALAND_PART==0, rename to geoid20/geoid10/area20/area10/area_part
        _RELATIONSHIP_CACHE[key] = frame
    return _RELATIONSHIP_CACHE[key].copy()
```

`get_2010_2020_bound_changes(res, geoids, *, state_fips)` becomes:
`df = _load_relationship(res, state_fips)`, then the **unchanged** geoid filter +
`count_20`/`count_10`/`match_area`/`type_change` classification on `df`. The
invalid-resolution `ValueError` moves into `_load_relationship` (raised before any
caching). Returning `.copy()` keeps the cached frame immutable across callers.

No change to `create_crosswalk`, `convert_2010_to_2020_bounds`, or any output.

## Tests (TDD) — `packages/sdc-census10to20/tests/test_crosswalk.py`

- **Add** `test_relationship_file_fetched_once`: monkeypatch `pd.read_csv` with a
  counter returning the canned `synthetic_tract_relationship_csv`; call
  `get_2010_2020_bound_changes(res="tract")` twice (and/or with different
  `geoids`) → assert `pd.read_csv` called exactly **once**.
- **Add** `test_cache_returns_independent_copies`: mutating one result does not
  affect a subsequent call's result.
- Existing crosswalk + convert tests still pass (output unchanged). Cache must be
  reset between tests (a fixture clearing `_RELATIONSHIP_CACHE`, or monkeypatch
  reassigns the module dict) so the call-count test is deterministic.

## Release

- Bump via tag `census10to20-v0.1.3`; CHANGELOG `[0.1.3]`:
  "Performance — the Census relationship file is now downloaded once per process
  (memoized) instead of on every `get_2010_2020_bound_changes` call, so
  `convert_2010_to_2020_bounds` / `standardize_all` runs drop from minutes to
  seconds. No change to outputs."
- Merge to `main`, push, tag, verify `0.1.3` on PyPI.

## Age proof (after the cache ships in the workspace)

1. Re-run `demographics/Age/code/distribution/ingest.py` (ACS from cache; convert
   now fast). Confirm it completes in ~seconds and rewrites
   `data/distribution/*.csv.xz`.
2. **Acceptance test** (from the impact doc): pre-2020 tract-level, per-county
   `_geo20`/`_geo10` totals — worst ratio must drop from **2.0 → ≈1.0** for both
   the NCR and VA files.
3. Re-run `demographics/Age/code/distribution/prepare.py` to refresh the
   `dashboard_data/` aggregates (`update_version` is local-only — confirmed) and
   any HD/county rollups.
4. Spot-check that **unchanged** geographies are identical pre/post (only
   split/moved geoids changed), and commit the regenerated Age data.

## Verification / success criteria

- New cache tests pass; full `sdc-census10to20` suite green; outputs unchanged.
- `v0.1.3` live on PyPI.
- Age ingest completes in seconds (not minutes); acceptance test ≈1.0 for NCR + VA.
- Age `prepare.py` refreshes dashboard outputs; regenerated data committed.

## Out of scope

- The full 24-dataset regeneration batch (separate follow-on).
- Any change to the conversion math (already fixed in v0.1.2), `redistribute`,
  or `sdc-core`.
- On-disk/persistent caching of the relationship file (in-process memo only).
