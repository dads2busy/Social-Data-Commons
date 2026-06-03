# Memoize census10to20 Relationship-File Fetch + Age Proof — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Download the Census relationship file once per process (behavior-neutral), release `sdc-census10to20 v0.1.3`, and prove the regeneration loop on `demographics/Age`.

**Architecture:** Extract the URL read into a memoized `_load_relationship(res, state_fips)` keyed cache; `get_2010_2020_bound_changes` filters/classifies on a per-call copy (output unchanged). TDD with a `pd.read_csv` call-counter. Then re-run Age ingest (now fast), verify county-conservation, refresh dashboards.

**Tech Stack:** pandas, pytest, sdc-census10to20, hatch-vcs release, ACS pipeline.

**Spec:** `docs/specs/2026-06-03-census10to20-crosswalk-cache-design.md`

**Branch:** `perf/census10to20-crosswalk-cache` (already created).

**Verified:** `crosswalk.py:get_2010_2020_bound_changes` does the `pd.read_csv(URL, sep="|")` then keep_cols / `AREALAND_PART != 0` / rename, then geoid filter + `count_20`/`count_10`/`match_area`/`type_change`. Existing tests monkeypatch `pd.read_csv` to return `synthetic_tract_relationship_csv` (raw `GEOID_TRACT_20/10`, `AREALAND_TRACT_20/10`, `AREALAND_PART`). Convert tests monkeypatch `create_crosswalk` (bypass the cache).

---

## File Structure

**Modify:**
- `packages/sdc-census10to20/src/sdc_census10to20/crosswalk.py` — add cache + `_load_relationship`
- `packages/sdc-census10to20/tests/conftest.py` — autouse cache-clearing fixture
- `packages/sdc-census10to20/tests/test_crosswalk.py` — 2 new tests
- `packages/sdc-census10to20/CHANGELOG.md` — `[0.1.3]`
- `demographics/Age/data/distribution/*.csv.xz` + `dashboard_data/` — regenerated (Age proof)

---

## Task 1: TDD — cache tests (failing) + isolation fixture

- [ ] **Step 1: Add an autouse cache-clearing fixture to `conftest.py`**

Append to `packages/sdc-census10to20/tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def _clear_relationship_cache():
    """Reset the in-process relationship-file cache so tests are isolated."""
    from sdc_census10to20 import crosswalk as _cw
    getattr(_cw, "_RELATIONSHIP_CACHE", {}).clear()
    yield
    getattr(_cw, "_RELATIONSHIP_CACHE", {}).clear()
```

(`getattr(..., {})` makes it a no-op before the cache exists, so the suite stays
green during red.)

- [ ] **Step 2: Add the two cache tests to `test_crosswalk.py`**

Append:

```python
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
```

- [ ] **Step 3: Run the crosswalk tests; confirm the 2 new ones fail**

Run: `uv run --group dev pytest packages/sdc-census10to20/tests/test_crosswalk.py -q`
Expected: `test_relationship_file_fetched_once` FAILS (`calls["n"] == 2`),
`test_load_relationship_returns_independent_copies` FAILS (`_load_relationship`
doesn't exist). The existing 6 crosswalk tests still pass.

---

## Task 2: Implement the cache

- [ ] **Step 1: Refactor `crosswalk.py` — add cache + `_load_relationship`**

Replace the body of `get_2010_2020_bound_changes` from the URL selection through
the rename (the lines that pick `file_path`/`res_code`, do `pd.read_csv`,
`keep_cols`, the `AREALAND_PART != 0` filter, and the column rename) so that work
lives in a memoized helper. Concretely, insert this helper above
`get_2010_2020_bound_changes`:

```python
_RELATIONSHIP_CACHE: dict[tuple[str, str], pd.DataFrame] = {}


def _load_relationship(res: str, state_fips: str) -> pd.DataFrame:
    """Download + prep the Census relationship file, once per (res, state_fips)."""
    if res == "tract":
        file_path = (
            "https://www2.census.gov/geo/docs/maps-data/data/rel2020/"
            "tract/tab20_tract20_tract10_natl.txt"
        )
        res_code = "TRACT"
    elif res == "block group":
        file_path = (
            "https://www2.census.gov/geo/docs/maps-data/data/rel2020/blkgrp/"
            f"tab20_blkgrp20_blkgrp10_st{state_fips}.txt"
        )
        res_code = "BLKGRP"
    else:
        raise ValueError('Invalid resolution. Use "tract" or "block group".')

    key = (res, state_fips)
    if key not in _RELATIONSHIP_CACHE:
        crosswalk = pd.read_csv(
            file_path,
            sep="|",
            dtype={f"GEOID_{res_code}_10": str, f"GEOID_{res_code}_20": str},
        )
        keep_cols = [
            f"GEOID_{res_code}_20",
            f"GEOID_{res_code}_10",
            f"AREALAND_{res_code}_20",
            f"AREALAND_{res_code}_10",
            "AREALAND_PART",
        ]
        crosswalk = crosswalk[keep_cols]
        crosswalk = crosswalk[crosswalk["AREALAND_PART"] != 0]
        crosswalk.columns = ["geoid20", "geoid10", "area20", "area10", "area_part"]
        _RELATIONSHIP_CACHE[key] = crosswalk

    return _RELATIONSHIP_CACHE[key].copy()
```

Then rewrite `get_2010_2020_bound_changes` to start from the helper and keep the
unchanged filter + classification:

```python
def get_2010_2020_bound_changes(
    res: str = "tract",
    geoids: list[str] | None = None,
    *,
    state_fips: str = "51",
) -> pd.DataFrame:
    """<docstring unchanged>"""
    crosswalk = _load_relationship(res, state_fips)

    if geoids is not None:
        crosswalk = crosswalk[crosswalk["geoid10"].isin(geoids)]

    crosswalk["count_20"] = crosswalk.groupby("geoid20")["geoid20"].transform("size")
    crosswalk["count_10"] = crosswalk.groupby("geoid10")["geoid10"].transform("size")

    geoid_10_20 = (
        crosswalk[["geoid10", "area20"]]
        .groupby("geoid10", as_index=False)
        .sum()
        .rename(columns={"area20": "match_area"})
    )
    crosswalk = crosswalk.merge(geoid_10_20, on="geoid10", how="left")

    crosswalk["type_change"] = "moved"
    split_mask = crosswalk["area10"] == crosswalk["match_area"]
    crosswalk.loc[split_mask, "type_change"] = "split"
    same_mask = (crosswalk["count_10"] == 1) & (crosswalk["count_20"] == 1)
    crosswalk.loc[same_mask, "type_change"] = "same"

    crosswalk = crosswalk.drop(columns=["count_10", "count_20", "match_area"])
    return crosswalk
```

(Keep the existing module docstring/imports and `__all__` unchanged. Leave the
`get_2010_2020_bound_changes` docstring body as it was.)

- [ ] **Step 2: Run the full census10to20 suite; all pass**

Run: `uv run --group dev pytest packages/sdc-census10to20/tests/ -q`
Expected: all pass (the 2 new cache tests + the unchanged crosswalk/convert tests;
output is identical, only the fetch is cached).

- [ ] **Step 3: Commit**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/crosswalk.py packages/sdc-census10to20/tests/
git commit -m "perf(census10to20): memoize the Census relationship-file download"
```

---

## Task 3: Changelog

- [ ] **Step 1: Add the 0.1.3 entry**

Insert above `## [0.1.2] - 2026-06-03` in `packages/sdc-census10to20/CHANGELOG.md`:

```markdown
## [0.1.3] - 2026-06-03

### Performance
- The Census 2010↔2020 relationship file is now downloaded once per process
  (memoized by resolution + state) instead of on every
  `get_2010_2020_bound_changes` call. `convert_2010_to_2020_bounds` /
  `standardize_all` runs that previously took minutes now take seconds. No change
  to outputs.

```

- [ ] **Step 2: Commit**

```bash
git add packages/sdc-census10to20/CHANGELOG.md
git commit -m "docs(census10to20): changelog 0.1.3 (relationship-file caching)"
```

---

## Task 4: Age proof — regenerate on the fast convert

The workspace `sdc-census10to20` is the editable branch source, so the cache is
already active. `CENSUS_API_KEY` is in `.env` (auto-loaded) and the ACS is cached
under `demographics/Age/data/working/acs_cache/`, so ingest does no live API calls.

- [ ] **Step 1: Capture the baseline (corrupt) acceptance ratios**

```bash
uv run --group dev python - <<'PY'
import pandas as pd
def worst(path):
    df = pd.read_csv(path, dtype={"geoid": str})
    tr = df[(df.year < 2020) & (df.region_type == "tract")].copy(); tr["c"] = tr.geoid.str[:5]
    w = 1.0
    for b in sorted({m[:-6] for m in tr.measure.unique() if m.endswith("_geo20")}):
        r = (tr[tr.measure==b+"_geo20"].groupby("c").value.sum()
             / tr[tr.measure==b+"_geo10"].groupby("c").value.sum()).replace([float("inf")], float("nan")).dropna()
        if len(r): w = max(w, float(r.max()))
    return round(w, 3)
for f in ["ncr_cttrbg_census_acs_2009_2024_age_demographics.csv.xz",
          "va_hdcttr_census_acs_2009_2024_age_demographics.csv.xz"]:
    p = "demographics/Age/data/distribution/" + f
    print("BASELINE", f.split('_')[0], "worst ratio:", worst(p))
PY
```

Expected: both ≈ `2.0` (corrupt).

- [ ] **Step 2: Re-run Age ingest (now fast)**

```bash
time uv run --group dev python "demographics/Age/code/distribution/ingest.py" > /tmp/age_ingest.log 2>&1; echo "exit=$?"
grep -viE "python-dotenv|it/s\]|resource_tracker|warnings.warn" /tmp/age_ingest.log | tail -8
```

Expected: exit 0, completes in **seconds** (not minutes), distribution files
rewritten (`git status --short demographics/Age/data/distribution/` shows them
modified). If it still hangs > ~60s, STOP — the cache isn't taking effect; do not
proceed.

- [ ] **Step 3: Acceptance test on the regenerated files**

Re-run the Step-1 script. Expected: both worst ratios drop to **≈ 1.0** (allowing
tiny edge leakage to neighboring counties; should be < 1.01).

- [ ] **Step 4: Spot-check an unchanged county is byte-identical pre/post**

```bash
uv run --group dev python - <<'PY'
import pandas as pd, subprocess, io
p = "demographics/Age/data/distribution/ncr_cttrbg_census_acs_2009_2024_age_demographics.csv.xz"
new = pd.read_csv(p, dtype={"geoid": str})
old = pd.read_csv(io.BytesIO(subprocess.run(["git","show",f"HEAD:{p}"],capture_output=True).stdout),
                  compression="xz", dtype={"geoid": str})
# County 51027 had no tract changes (ratio 1.0): its pre-2020 _geo20 rows should be unchanged.
def slice_(d): 
    m = (d.geoid.str[:5]=="51027") & (d.year<2020) & (d.measure.str.endswith("_geo20"))
    return d[m].sort_values(["geoid","year","measure"]).reset_index(drop=True)[["geoid","year","measure","value"]]
o, n = slice_(old), slice_(new)
print("unchanged-county rows match:", o.equals(n), "| rows:", len(n))
PY
```

Expected: `unchanged-county rows match: True` — confirms only changed geographies moved.

- [ ] **Step 5: Re-run Age prepare.py (refresh dashboard outputs)**

```bash
uv run --group dev python "demographics/Age/code/distribution/prepare.py" > /tmp/age_prepare.log 2>&1; echo "exit=$?"
grep -viE "python-dotenv|warnings.warn" /tmp/age_prepare.log | tail -8
git status --short "demographics/Age/" | head
```

Expected: exit 0; `dashboard_data/` (and `manifest.json` version bump from the
local `update_version`) updated. (`update_version` is local-only — confirmed in
`sdc_core/versioning.py`, no Zenodo/HTTP.)

- [ ] **Step 6: Commit the regenerated Age data**

```bash
git add "demographics/Age/"
git commit -m "data(Age): regenerate with count-conserving convert (fixes inflated pre-2020 _geo20)"
```

---

## Task 5: Finish, release v0.1.3, verify

- [ ] **Step 1: Full suite green**

Run: `uv run --group dev pytest packages/sdc-census10to20/tests/ -q`
Expected: all pass.

- [ ] **Step 2: Finish the development branch**

Use **superpowers:finishing-a-development-branch** to merge
`perf/census10to20-crosswalk-cache` to `main` (verify tests on the merged result)
and push.

- [ ] **Step 3: Cut the release**

```bash
git checkout main && git pull
git tag census10to20-v0.1.3
git push origin census10to20-v0.1.3
gh run watch "$(gh run list --workflow=publish-census10to20.yml --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status --interval 15
```

Expected: green publish run.

- [ ] **Step 4: Verify the release**

```bash
curl -s -o /dev/null -w "pypi 0.1.3 -> HTTP %{http_code}\n" https://pypi.org/pypi/sdc-census10to20/0.1.3/json
```

Expected: `HTTP 200`.

---

## Self-Review

- **Spec coverage:** memoized `_load_relationship` keyed by `(res, state_fips)`,
  return `.copy()` → Task 2. ValueError before caching → in `_load_relationship`
  (Task 2). cache-clear fixture + fetched-once + independent-copies tests → Task 1.
  output-unchanged → existing tests still pass (Task 2 §2). CHANGELOG + v0.1.3
  release → Tasks 3, 5. Age proof (ingest fast, ratio 2.0→1.0, prepare, unchanged
  spot-check, commit) → Task 4. scope excludes the 24-dataset batch → no such task.
  All covered.
- **Placeholder scan:** none — full helper + rewritten function shown; tests
  complete; Age verification scripts concrete with expected output.
- **Consistency:** `_RELATIONSHIP_CACHE` / `_load_relationship(res, state_fips)`
  names match across crosswalk.py, the conftest fixture, and the tests. Tag
  `census10to20-v0.1.3` matches the publish workflow trigger. The acceptance-test
  ratio (2.0 baseline → ~1.0) matches the verified corruption signature and the
  fix from v0.1.2 (already on main).
