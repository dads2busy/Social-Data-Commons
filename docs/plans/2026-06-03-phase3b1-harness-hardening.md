# Phase 3b-1 — Regeneration Harness Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the Phase-3a regeneration harness so its AFTER gate can be trusted before the consequential 24-pipeline run: check **all** of a dataset's distribution files (not just one), wire the ratio-consistency check into the gate, implement `regenerate_dataset` real-mode (run → AFTER gate → local-patch version → commit), and add the 7 composite manifest entries (all 24 now covered). **No distribution data is regenerated in this plan** — real-mode is unit-tested with a stub pipeline; the actual run is Phase 3b-2.

**Architecture:** Extend `tools/census10to20_remediation/` from 3a. The driver gains `_dist_files` (all matches), `_acceptance` (count conservation + ratio consistency aggregated over all files), and real-mode `regenerate_dataset` (mockable `update_version`/commit so it's testable without a real pipeline or git write). The manifest gains a `measure_info` field per entry and the 7 composite entries. All 24 datasets use uniform `[ingest.run, prepare.run]` entrypoints (verified).

**Tech Stack:** Python 3.12, pandas, pytest, uv workspace. Builds on Phase 3a.

**Scope:** Phase 3b-1 — harness hardening only (code/TDD, no data regenerated). **Phase 3b-2** (separate, explicitly initiated) executes: `SDC_NO_PUBLISH=1`, run the driver real-mode for `demographics/Age` first as a checkpoint (regen → acceptance pass + BEFORE>AFTER → local patch + commit), confirm, then batch base-ACS, then composites; halt on any acceptance failure. Census API reachable + `CENSUS_API_KEY` in `.env` + external inputs cached (confirmed).

**Specs:** `docs/specs/2026-06-03-census10to20-remediation-design.md`, `...intensive-measure-fix-design.md` §9. Branch: `fix/census10to20-data-remediation`.

---

## Facts
- 3a built `acceptance_test.py` (`check_conservation`, `check_ratio_consistency`), `datasets.py` (`BASE_ACS`, 17 entries), `driver.py` (`run_entrypoint`, `regenerate_dataset` dry-run + real-mode `NotImplementedError` stub), and the `SDC_NO_PUBLISH` kill-switch.
- 3a review found: `_dist_file` returns one file but 16/17 datasets have two (NCR `cttrbg` + VA `hdcttr`); the ratio check is unwired; real-mode is a stub.
- All 24 datasets expose `run()` in both ingest and prepare → uniform `[ingest.run, prepare.run]` entrypoints. The 7 not yet in the manifest: Segregation, Incarceration, Employment Access, Environmental Hazard, Walkability, Food Accessibility, Affordability_HT.
- Versioning policy (remediation spec): `update_version(topic, force_level="patch", auto_tag=False, auto_release=False)` (refresh manifest, patch bump, no publish; `force_level="patch"` also defeats the phantom MAJOR bump) + a LOCAL annotated tag (no push).

---

## File Structure
- **Modify** `tools/census10to20_remediation/driver.py` — `_dist_files`, `_acceptance`, real-mode `regenerate_dataset`, `_local_tag`/`_commit_dataset` helpers.
- **Modify** `tools/census10to20_remediation/datasets.py` — `measure_info` per entry; 7 composite entries; an `ALL_DATASETS` list.
- **Modify** `tools/census10to20_remediation/test_driver.py`, `test_acceptance.py` — tests.

---

## Task 1: Multi-file acceptance aggregation

**Files:**
- Modify: `tools/census10to20_remediation/driver.py`
- Modify: `tools/census10to20_remediation/test_driver.py`

Replace single-file `_dist_file` with `_dist_files` (all matches) and aggregate `check_conservation` over them so the gate sees every file (NCR + VA).

- [ ] **Step 1: Write the failing test** (append to `test_driver.py`):

```python
def test_dist_files_returns_all_matches_and_acceptance_aggregates(tmp_path):
    import pandas as pd
    from driver import _dist_files, _acceptance_conservation

    topic = tmp_path / "demo"
    dist = topic / "data" / "distribution"
    dist.mkdir(parents=True)
    # file A: conserved (ratio 1.0); file B: inflated (ratio 1.5)
    def w(name, g20a, g20b):
        pd.DataFrame({
            "geoid": ["51001000001", "51001000002", "51001000003"],
            "year": [2018, 2018, 2018],
            "measure": ["c_geo10", "c_geo20", "c_geo20"],
            "value": [1000, g20a, g20b],
            "moe": [pd.NA, pd.NA, pd.NA],
            "region_type": ["tract", "tract", "tract"],
        }).to_csv(dist / name, index=False)
    w("a.csv.xz", 600, 400)   # sum 1000 -> 1.0
    w("b.csv.xz", 900, 600)   # sum 1500 -> 1.5
    entry = {"topic": "demo", "dist_glob": "data/distribution/*.csv.xz"}
    files = _dist_files(entry, tmp_path)
    assert len(files) == 2
    rep = _acceptance_conservation(entry, tmp_path)
    assert rep["status"] == "fail"            # worst file fails
    assert rep["max_ratio"] == pytest.approx(1.5)
```

(Add `import pytest` to test_driver.py if not present.)

- [ ] **Step 2: Run, verify FAIL** (`_dist_files`/`_acceptance_conservation` don't exist):

Run: `uv run pytest tools/census10to20_remediation/test_driver.py::test_dist_files_returns_all_matches_and_acceptance_aggregates -v`

- [ ] **Step 3: Implement.** In `driver.py`, replace `_dist_file` with `_dist_files` and add the aggregator:

```python
def _dist_files(entry, repo_root):
    matches = sorted(_glob.glob(str(Path(repo_root) / entry["topic"] / entry["dist_glob"])))
    if not matches:
        raise FileNotFoundError(f"{entry['topic']}: no file matches {entry['dist_glob']}")
    return matches


def _acceptance_conservation(entry, repo_root):
    """Run check_conservation over ALL of a dataset's distribution files; aggregate.

    status = fail if any file fails; n/a only if every file is n/a; else pass.
    max_ratio = worst (largest) across files.
    """
    from acceptance_test import check_conservation
    reps = [check_conservation(f) for f in _dist_files(entry, repo_root)]
    ratios = [r["max_ratio"] for r in reps if r["max_ratio"] is not None]
    if any(r["status"] == "fail" for r in reps):
        status = "fail"
    elif all(r["status"] == "n/a" for r in reps):
        status = "n/a"
    else:
        status = "pass"
    return {"status": status, "max_ratio": max(ratios) if ratios else None,
            "per_file": {Path(f).name: r for f, r in zip(_dist_files(entry, repo_root), reps)}}
```

Update `regenerate_dataset`'s BEFORE line from `check_conservation(_dist_file(...))` to `_acceptance_conservation(entry, repo_root)`.

- [ ] **Step 4: Run, verify PASS + full driver/acceptance suites:**

Run: `uv run pytest tools/census10to20_remediation -v`
(The Age dry-run test still passes — Age's two files both show ratio 2.0, aggregated max_ratio 2.0, status fail.)

- [ ] **Step 5: Commit:**

```bash
git add tools/census10to20_remediation/driver.py tools/census10to20_remediation/test_driver.py
git commit -m "feat(remediation): acceptance over ALL of a dataset's distribution files"
```

---

## Task 2: Wire ratio consistency into the gate + `measure_info` per entry

**Files:**
- Modify: `tools/census10to20_remediation/datasets.py`
- Modify: `tools/census10to20_remediation/driver.py`
- Modify: `tools/census10to20_remediation/test_driver.py`

Add a `measure_info` field to each manifest entry and an `_acceptance` that combines conservation + ratio consistency.

- [ ] **Step 1: Write the failing test** (append to `test_driver.py`):

```python
def test_acceptance_combines_conservation_and_ratio(tmp_path):
    import json, pandas as pd
    from driver import _acceptance

    topic = tmp_path / "demo"
    dist = topic / "data" / "distribution"
    dist.mkdir(parents=True)
    # conserved counts but a DILUTED percent -> ratio check must fail the dataset
    pd.DataFrame({
        "geoid": ["51001000001", "51001000002", "51001000003"],
        "year": [2018, 2018, 2018],
        "measure": ["tot_count_geo10", "tot_count_geo20", "tot_count_geo20"],
        "value": [1000, 600, 400],
        "moe": [pd.NA, pd.NA, pd.NA], "region_type": ["tract", "tract", "tract"],
    }).to_csv(dist / "d.csv.xz", index=False)
    # append a percent that's wrong vs counts (no counts in file for it -> use a self-consistent case):
    extra = pd.DataFrame({
        "geoid": ["51001000002"], "year": [2018],
        "measure": ["sub_count_geo20"], "value": [30], "moe": [pd.NA], "region_type": ["tract"],
    })
    extra2 = pd.DataFrame({
        "geoid": ["51001000002"], "year": [2018],
        "measure": ["sub_pct_geo20"], "value": [18.0], "moe": [pd.NA], "region_type": ["tract"],
    })
    base = pd.read_csv(dist / "d.csv.xz", dtype={"geoid": str})
    pd.concat([base, extra, extra2], ignore_index=True).to_csv(dist / "d.csv.xz", index=False)

    mi = {
        "tot_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "sub_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "sub_pct_geo20": {"geo_standardize": {"measure_type": "ratio",
            "numerator": "sub_count", "denominator": "tot_count", "scale": 100}},
    }
    (dist / "measure_info.json").write_text(json.dumps(mi))
    entry = {"topic": "demo", "dist_glob": "data/distribution/*d.csv.xz",
             "measure_info": "data/distribution/measure_info.json"}
    rep = _acceptance(entry, tmp_path)
    # conservation passes (1.0) but ratio is diluted (18 vs 100*30/600=5? -> mismatch) -> overall fail
    assert rep["status"] == "fail"
    assert rep["ratio"]["status"] == "fail"
```

- [ ] **Step 2: Run, verify FAIL** (`_acceptance` doesn't exist):

Run: `uv run pytest tools/census10to20_remediation/test_driver.py::test_acceptance_combines_conservation_and_ratio -v`

- [ ] **Step 3: Implement.** In `driver.py` add `_acceptance` (conservation + ratio over all files, using the entry's `measure_info`):

```python
def _acceptance(entry, repo_root):
    """Combined gate: count conservation (all files) + ratio consistency (all files)."""
    from acceptance_test import check_ratio_consistency
    import json as _json

    cons = _acceptance_conservation(entry, repo_root)
    mi_path = Path(repo_root) / entry["topic"] / entry["measure_info"]
    measure_info = _json.loads(mi_path.read_text()) if mi_path.exists() else {}
    ratio_reps = [check_ratio_consistency(f, measure_info) for f in _dist_files(entry, repo_root)]
    ratio_status = (
        "fail" if any(r["status"] == "fail" for r in ratio_reps)
        else ("n/a" if all(r["status"] == "n/a" for r in ratio_reps) else "pass")
    )
    overall = "fail" if cons["status"] == "fail" or ratio_status == "fail" else (
        "n/a" if cons["status"] == "n/a" and ratio_status == "n/a" else "pass"
    )
    return {"status": overall, "conservation": cons,
            "ratio": {"status": ratio_status, "reps": ratio_reps}}
```

Update `regenerate_dataset` to use `_acceptance(entry, repo_root)` for BEFORE (instead of `_acceptance_conservation`), and adjust the dry-run report key accordingly (`report["before"]` is now the combined report; its conservation sub-report has `max_ratio`). Update the existing Age dry-run test's assertions to read `report["before"]["conservation"]["status"] == "fail"` and `report["before"]["conservation"]["max_ratio"] > 1.1`.

Add a `MEASURE_INFO = "data/distribution/measure_info.json"` constant in `datasets.py` and include `"measure_info": MEASURE_INFO` in the `_base(...)` helper's returned dict.

- [ ] **Step 4: Run, verify PASS + full suite:**

Run: `uv run pytest tools/census10to20_remediation -v`

- [ ] **Step 5: Commit:**

```bash
git add tools/census10to20_remediation/driver.py tools/census10to20_remediation/datasets.py tools/census10to20_remediation/test_driver.py
git commit -m "feat(remediation): combined acceptance gate (conservation + ratio) + measure_info per entry"
```

---

## Task 3: Real-mode `regenerate_dataset`

**Files:**
- Modify: `tools/census10to20_remediation/driver.py`
- Modify: `tools/census10to20_remediation/test_driver.py`

Implement real-mode: run each entrypoint, re-run `_acceptance` (AFTER), gate on AFTER pass AND inflation reduced, then local-patch version + local tag + commit. `update_version` and the commit are module-level so the test can monkeypatch them and exercise the orchestration with a stub pipeline (no real git/data).

- [ ] **Step 1: Write the failing test** (append to `test_driver.py`):

```python
def test_real_mode_runs_gates_versions_commits(tmp_path, monkeypatch):
    import json, pandas as pd
    import driver as drv

    topic = tmp_path / "demo"
    dist = topic / "data" / "distribution"
    code = topic / "code" / "distribution"
    dist.mkdir(parents=True); code.mkdir(parents=True)
    # committed BEFORE = inflated (county ratio 1.5)
    pd.DataFrame({
        "geoid": ["51001000001", "51001000002", "51001000003"], "year": [2018]*3,
        "measure": ["c_geo10", "c_geo20", "c_geo20"], "value": [1000, 900, 600],
        "moe": [pd.NA]*3, "region_type": ["tract"]*3,
    }).to_csv(dist / "d.csv.xz", index=False)
    (dist / "measure_info.json").write_text(json.dumps(
        {"c_geo20": {"geo_standardize": {"measure_type": "count"}}}))
    # stub ingest.run rewrites the file CONSERVED (ratio 1.0)
    (code / "ingest.py").write_text(
        "import pandas as pd\nfrom pathlib import Path\n"
        "def run():\n"
        "    p = Path(__file__).resolve().parents[2] / 'data/distribution/d.csv.xz'\n"
        "    pd.DataFrame({'geoid':['51001000001','51001000002','51001000003'],'year':[2018]*3,"
        "'measure':['c_geo10','c_geo20','c_geo20'],'value':[1000,600,400],'moe':[pd.NA]*3,"
        "'region_type':['tract']*3}).to_csv(p, index=False)\n")
    (code / "prepare.py").write_text("def run():\n    pass\n")

    calls = {"version": 0, "tag": 0, "commit": 0}
    monkeypatch.setattr(drv, "update_version",
                        lambda *a, **k: calls.__setitem__("version", calls["version"] + 1) or type("R", (), {"tag": "demo/v1.0.1", "new_version": "1.0.1"})())
    monkeypatch.setattr(drv, "_local_tag", lambda *a, **k: calls.__setitem__("tag", calls["tag"] + 1))
    monkeypatch.setattr(drv, "_commit_dataset", lambda *a, **k: calls.__setitem__("commit", calls["commit"] + 1))

    entry = {"topic": "demo", "dist_glob": "data/distribution/*d.csv.xz",
             "measure_info": "data/distribution/measure_info.json",
             "entrypoints": ["code/distribution/ingest.py:run", "code/distribution/prepare.py:run"]}
    report = drv.regenerate_dataset(entry, repo_root=tmp_path, dry_run=False)
    assert report["regenerated"] is True
    assert report["after"]["status"] == "pass"
    assert report["before"]["conservation"]["max_ratio"] == pytest.approx(1.5)
    assert report["after"]["conservation"]["max_ratio"] == pytest.approx(1.0)
    assert calls == {"version": 1, "tag": 1, "commit": 1}
    assert report["committed"] is True
```

- [ ] **Step 2: Run, verify FAIL** (real-mode raises `NotImplementedError`):

Run: `uv run pytest tools/census10to20_remediation/test_driver.py::test_real_mode_runs_gates_versions_commits -v`

- [ ] **Step 3: Implement.** In `driver.py`, add imports + helpers + real-mode body. Add at the top:

```python
import subprocess
from sdc_core.versioning import update_version
```

Add helpers:

```python
def _local_tag(tag: str, repo_root) -> None:
    """Create an annotated tag locally WITHOUT pushing."""
    subprocess.run(["git", "tag", "-a", tag, "-m", f"remediation {tag}"],
                   cwd=str(repo_root), check=True, capture_output=True, text=True)


def _commit_dataset(entry, repo_root, message) -> None:
    """Stage the dataset's regenerated outputs + metadata and commit."""
    topic = entry["topic"]
    subprocess.run(["git", "add", f"{topic}/data/distribution", f"{topic}/pipeline.yaml"],
                   cwd=str(repo_root), check=True, capture_output=True, text=True)
    # dashboard_data outputs (refreshed by prepare) live at repo root
    subprocess.run(["git", "add", "dashboard_data"], cwd=str(repo_root),
                   check=False, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", message], cwd=str(repo_root),
                   check=True, capture_output=True, text=True)


def _inflation_reduced(before, after) -> bool:
    """True if the count-inflation signature dropped (or there was none to begin with)."""
    b = before["conservation"]["max_ratio"]
    a = after["conservation"]["max_ratio"]
    if b is None or a is None:
        return True  # no count measures to inflate (e.g. replicate/index/geo2020 datasets)
    return a < b
```

Replace the `regenerate_dataset` real-mode branch (the `raise NotImplementedError`) with:

```python
    topic_dir = Path(repo_root) / entry["topic"]
    for ep in entry["entrypoints"]:
        mod_rel, _, func = ep.partition(":")
        run_entrypoint(topic_dir / mod_rel, func)
    after = _acceptance(entry, repo_root)
    report["after"] = after
    report["regenerated"] = True
    if after["status"] == "fail" or not _inflation_reduced(before, after):
        report["gate"] = "failed"
        return report  # caller halts the batch; nothing committed
    result = update_version(topic_dir, force_level="patch", auto_tag=False, auto_release=False)
    if result is not None and getattr(result, "tag", None):
        _local_tag(result.tag, repo_root)
    _commit_dataset(entry, repo_root,
                    f"fix({entry['topic']}): regenerate census10to20 _geo20 (remediation)")
    report["committed"] = True
    return report
```

(The `regenerate_dataset` signature/dry-run path from 3a is unchanged; only the real-mode branch is implemented. `before` is the combined `_acceptance` report from Task 2.)

- [ ] **Step 4: Run, verify PASS + full suite:**

Run: `uv run pytest tools/census10to20_remediation -v`

- [ ] **Step 5: Commit:**

```bash
git add tools/census10to20_remediation/driver.py tools/census10to20_remediation/test_driver.py
git commit -m "feat(remediation): regenerate_dataset real-mode (run -> AFTER gate -> local patch + tag + commit)"
```

---

## Task 4: Composite manifest entries (all 24)

**Files:**
- Modify: `tools/census10to20_remediation/datasets.py`
- Modify: `tools/census10to20_remediation/test_driver.py`

Add the 7 remaining datasets (uniform `[INGEST, PREPARE]` entrypoints) and an `ALL_DATASETS` list; extend the manifest test to verify every entry's glob resolves to ≥1 committed file.

- [ ] **Step 1: Add the entries.** In `datasets.py`, after `BASE_ACS`, add:

```python
COMPOSITES = [
    _base("demographics/Segregation Index (HOI)", "data/distribution/*segregation*.csv.xz"),
    _base("public_safety/Incarceration (HOI)", "data/distribution/*incarceration*.csv.xz"),
    _base("financial_well_being/Employment Access Index", "data/distribution/*employment_access*.csv.xz"),
    _base("environment/Environmental Hazard Index (HOI)", "data/distribution/*environmental*.csv.xz"),
    _base("transportation/Walkability", "data/distribution/*walkability*.csv.xz"),
    _base("food/Food Access/Food Accessibility Indicator (HOI)", "data/distribution/*food_access*.csv.xz"),
    _base("housing/Cost/Affordability_HT", "data/distribution/*affordability*.csv.xz"),
]

ALL_DATASETS = BASE_ACS + COMPOSITES
```

- [ ] **Step 2: Strengthen the manifest test** (replace `test_base_acs_manifest_paths_resolve` in `test_driver.py`, or add a new one over `ALL_DATASETS`):

```python
def test_all_manifest_entries_resolve():
    import glob
    from datasets import ALL_DATASETS
    repo = Path(__file__).resolve().parents[2]
    assert len(ALL_DATASETS) == 24, f"expected 24 datasets, got {len(ALL_DATASETS)}"
    for entry in ALL_DATASETS:
        topic = repo / entry["topic"]
        assert topic.is_dir(), f"missing topic dir: {entry['topic']}"
        for ep in entry["entrypoints"]:
            mod_rel, _, func = ep.partition(":")
            assert (topic / mod_rel).is_file(), f"missing module: {entry['topic']}/{mod_rel}"
        mi = topic / entry["measure_info"]
        assert mi.is_file(), f"missing measure_info: {entry['topic']}/{entry['measure_info']}"
        matches = glob.glob(str(topic / entry["dist_glob"]))
        assert matches, f"dist_glob matches nothing: {entry['topic']} :: {entry['dist_glob']}"
```

- [ ] **Step 3: Run, verify PASS.** Fix any glob that matches nothing (inspect the dataset's actual committed `data/distribution/*.csv.xz` filenames and adjust the pattern to match all of its data files):

Run: `uv run pytest tools/census10to20_remediation/test_driver.py::test_all_manifest_entries_resolve -v`
Report any glob corrections made.

- [ ] **Step 4: Full suite green:**

Run: `uv run pytest tools/census10to20_remediation tests/test_geo_standardize_metadata.py packages/sdc-census10to20 packages/sdc-core -q`

- [ ] **Step 5: Commit:**

```bash
git add tools/census10to20_remediation/datasets.py tools/census10to20_remediation/test_driver.py
git commit -m "feat(remediation): composite manifest entries (all 24); glob-resolution test"
```

---

## Done criteria
- Acceptance runs over ALL of a dataset's distribution files (NCR + VA), aggregating worst-case.
- The gate combines count conservation + ratio consistency (per the dataset's `measure_info`).
- `regenerate_dataset` real-mode runs entrypoints → AFTER gate (pass + inflation reduced) → local-patch `update_version` (no publish) + local tag (no push) + per-dataset commit; unit-tested with a stub pipeline + mocked version/commit.
- Manifest covers all 24 datasets with resolving globs + measure_info.
- NO distribution data regenerated; all suites green.

## Follow-on
**Phase 3b-2 — execute the regeneration (consequential; explicitly initiated):**
1. `export SDC_NO_PUBLISH=1`; confirm `CENSUS_API_KEY` (in `.env`), Census API reachable, external inputs cached.
2. **Age checkpoint:** `regenerate_dataset(age, dry_run=False)` → assert `after.status == pass` AND BEFORE>AFTER → review the commit (data + manifest + pipeline.yaml + dashboard_data). STOP and inspect.
3. **Base-ACS batch:** loop the remaining 16 base-ACS; halt on any gate failure.
4. **Composites:** the 7 (watch EnvHazard NCR `state_fips` MD/DC drop — recorded in memory; some composites re-fetch external/cached inputs).
5. Each commit is local-only (no push, no GitHub release). Expect trivial source-refresh diffs alongside the fix (stable ACS vintages); the acceptance gate isolates the fix.
6. After all 24: run the full harness + acceptance summary; then a final review before deciding to merge/publish (a separate, later decision).
