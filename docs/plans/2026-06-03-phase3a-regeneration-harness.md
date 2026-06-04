# Phase 3a — Regeneration Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and dry-run-validate the tooling that Phase 3b will use to regenerate the 24 corrupted datasets — an acceptance test (count conservation + ratio consistency), a publish kill-switch, a per-dataset entrypoint manifest, and a driver that re-runs a pipeline's `run()` while bypassing auto-publish. **No distribution data is regenerated in this plan.**

**Architecture:** A `tools/census10to20_remediation/` package: `acceptance_test.py` (reusable checks), `datasets.py` (entrypoint manifest), `driver.py` (per-dataset orchestration with a `--dry-run` that runs BEFORE-acceptance only). Plus a `SDC_NO_PUBLISH` env kill-switch in `sdc_core.versioning.update_version`. The driver imports each pipeline module by path and calls its `run()` directly — never `__main__` — so `update_version` (and its auto-tag/release) never fires during regeneration; versioning is a separate, controlled, local-only `force_level="patch"` step.

**Tech Stack:** Python 3.12, pandas, pytest, uv workspace. Builds on Phases 0-2c (all 24 datasets configured; harness green).

**Scope:** Phase 3a — harness only, validated by dry-run. **Phase 3b** (separate, explicitly-initiated) executes the regeneration: runs the driver for real across 24 pipelines (live Census API + cached external inputs), writes `data/distribution/` + `dashboard_data/`, commits per dataset — Age first as checkpoint, then base-ACS, then composites. The composite entrypoint-manifest entries (which vary per pipeline) are confirmed at the start of 3b's composite phase; 3a populates the uniform base-ACS entries.

**Specs:** `docs/specs/2026-06-03-census10to20-remediation-design.md` (driver, versioning policy, acceptance test, phased order) and `docs/specs/2026-06-03-census10to20-intensive-measure-fix-design.md` §9 (extended gate). Branch: `fix/census10to20-data-remediation`.

---

## Design recap (from the remediation spec)
- **Publish safety:** driver calls `run()` directly (no `__main__` → no `update_version`); PLUS `SDC_NO_PUBLISH` env kill-switch as defense-in-depth.
- **Versioning:** per dataset `update_version(topic, force_level="patch", auto_tag=False, auto_release=False)` — refreshes the (stale) manifest, patch-bumps `pipeline.yaml`, NO push/release. `force_level="patch"` also defeats the phantom MAJOR bump from stale manifests. A local annotated tag is created without pushing.
- **Acceptance:** count measures' county `geo20/geo10` ≈ 1.0 (the original-bug gate) + ratio `_geo20` consistent with published constituent counts (the intensive-fix gate). Require AFTER pass AND BEFORE>AFTER (proof the inflation was removed).
- **Commit:** one per dataset (regenerated `data/distribution/*.csv.xz` + refreshed `manifest.json` + bumped `pipeline.yaml` + refreshed `dashboard_data/`).

---

## File Structure
- **Modify** `packages/sdc-core/src/sdc_core/versioning.py` — `SDC_NO_PUBLISH` kill-switch.
- **Create** `tools/census10to20_remediation/__init__.py`
- **Create** `tools/census10to20_remediation/acceptance_test.py` — `check_conservation`, `check_ratio_consistency`.
- **Create** `tools/census10to20_remediation/datasets.py` — entrypoint manifest (base-ACS).
- **Create** `tools/census10to20_remediation/driver.py` — per-dataset orchestration + dry-run.
- **Create** `tools/census10to20_remediation/test_acceptance.py`, `test_driver.py` — unit tests.

---

## Task 1: `SDC_NO_PUBLISH` kill-switch

**Files:**
- Modify: `packages/sdc-core/src/sdc_core/versioning.py`
- Test: `packages/sdc-core/tests/test_versioning.py` (create if absent)

- [ ] **Step 1: Write the failing test:**

```python
# packages/sdc-core/tests/test_versioning.py
import os
import sdc_core.versioning as versioning


def test_sdc_no_publish_forces_no_tag_no_release(monkeypatch, tmp_path):
    calls = {"tag": 0, "release": 0}
    monkeypatch.setattr(versioning, "create_git_tag", lambda *a, **k: calls.__setitem__("tag", calls["tag"] + 1))
    monkeypatch.setattr(versioning, "create_github_release", lambda *a, **k: calls.__setitem__("release", calls["release"] + 1))
    monkeypatch.setenv("SDC_NO_PUBLISH", "1")

    # Minimal topic dir with a pipeline.yaml + a distribution file.
    topic = tmp_path / "demo"
    dist = topic / "data" / "distribution"
    dist.mkdir(parents=True)
    (topic / "pipeline.yaml").write_text('name: demo\nversion: "1.0.0"\noutput:\n  path: data/distribution\n')
    import pandas as pd
    pd.DataFrame({"geoid": ["51001000020"], "year": [2018], "measure": ["x_geo20"],
                  "value": [1.0], "moe": [pd.NA], "region_type": ["tract"]}).to_csv(dist / "d.csv.xz", index=False)

    # Even with auto_tag/auto_release defaulting True, SDC_NO_PUBLISH suppresses both.
    versioning.update_version(topic, force_level="patch")
    assert calls["tag"] == 0
    assert calls["release"] == 0
```

- [ ] **Step 2: Run, verify FAIL** (without the kill-switch, `create_git_tag` is called):

Run: `cd packages/sdc-core && uv run pytest tests/test_versioning.py::test_sdc_no_publish_forces_no_tag_no_release -v`

- [ ] **Step 3: Implement.** In `versioning.py`, ensure `import os` is present at the top (add if missing). Inside `update_version`, immediately after the signature/docstring (before any tagging logic — earliest point in the body), add:

```python
    if os.environ.get("SDC_NO_PUBLISH"):
        auto_tag = False
        auto_release = False
```

- [ ] **Step 4: Run, verify PASS + full sdc-core suite:**

Run: `cd packages/sdc-core && uv run pytest tests/ -v`

- [ ] **Step 5: Commit:**

```bash
git add packages/sdc-core/src/sdc_core/versioning.py packages/sdc-core/tests/test_versioning.py
git commit -m "feat(sdc-core): SDC_NO_PUBLISH env kill-switch suppresses auto-tag/release"
```

---

## Task 2: Acceptance — count conservation check

**Files:**
- Create: `tools/census10to20_remediation/__init__.py` (empty)
- Create: `tools/census10to20_remediation/acceptance_test.py`
- Test: `tools/census10to20_remediation/test_acceptance.py`

`check_conservation` reimplements the impact doc's gate: for pre-2020 tract rows, each COUNT measure's per-county `geo20/geo10` sum ratio must be ≈ 1.0 (counties don't move, so a correct count is conserved). The currently-committed (corrupt) Age data should FAIL this with max ratio ≈ 2.0 — that's the real-data validation.

- [ ] **Step 1: Write the failing test:**

```python
# tools/census10to20_remediation/test_acceptance.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from acceptance_test import check_conservation

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(tmp_path, rows):
    df = pd.DataFrame(rows, columns=["geoid", "year", "measure", "value", "region_type"])
    df["moe"] = pd.NA
    p = tmp_path / "d.csv.xz"
    df.to_csv(p, index=False)
    return p


def test_check_conservation_passes_when_county_totals_match(tmp_path):
    # county 51001: geo10 sum == geo20 sum (conserved) -> ratio 1.0 -> pass
    rows = [
        ("51001000001", 2018, "pop_count_geo10", 1000, "tract"),
        ("51001000002", 2018, "pop_count_geo20", 600, "tract"),
        ("51001000003", 2018, "pop_count_geo20", 400, "tract"),
    ]
    rep = check_conservation(_write(tmp_path, rows))
    assert rep["status"] == "pass"
    assert rep["max_ratio"] == pytest.approx(1.0)


def test_check_conservation_fails_on_inflation(tmp_path):
    # geo20 sum (1200) > geo10 sum (1000) -> ratio 1.2 -> fail
    rows = [
        ("51001000001", 2018, "pop_count_geo10", 1000, "tract"),
        ("51001000002", 2018, "pop_count_geo20", 600, "tract"),
        ("51001000003", 2018, "pop_count_geo20", 600, "tract"),
    ]
    rep = check_conservation(_write(tmp_path, rows))
    assert rep["status"] == "fail"
    assert rep["max_ratio"] == pytest.approx(1.2)


def test_check_conservation_detects_committed_age_inflation():
    # The currently-committed (corrupt) Age NCR data must show the known inflation.
    age = REPO_ROOT / "demographics/Age/data/distribution/ncr_cttrbg_census_acs_2009_2024_age_demographics.csv.xz"
    rep = check_conservation(age)
    assert rep["status"] == "fail"
    assert rep["max_ratio"] > 1.1  # impact doc: up to ~2.0
```

(Add `import pytest` at the top of the test file.)

- [ ] **Step 2: Run, verify FAIL** with `ModuleNotFoundError: acceptance_test`:

Run: `uv run pytest tools/census10to20_remediation/test_acceptance.py -v`

- [ ] **Step 3: Implement.** Create `tools/census10to20_remediation/__init__.py` (empty) and `tools/census10to20_remediation/acceptance_test.py`:

```python
"""Acceptance checks for the census10to20 data remediation (Phase 3)."""
from __future__ import annotations

import numpy as np
import pandas as pd

_GEO20 = "_geo20"
_GEO10 = "_geo10"


def _is_count(base: str) -> bool:
    """Heuristic: a measure is a conserved count if its name marks it so."""
    b = base.lower()
    if any(h in b for h in ("percent", "_pct", "rate", "median", "mean", "index",
                            "score", "gini", "density", "indicator", "ratio", "frac")):
        return False
    return b.endswith("_count") or "count" in b or b.endswith("_pop") or "population" in b


def check_conservation(dist_path, *, tol: float = 1.01) -> dict:
    """County geo20/geo10 sum ratio for pre-2020 tract COUNT measures must be ~1.0.

    Returns {"status": "pass"|"fail"|"n/a", "max_ratio": float|None,
             "per_measure": {base: max_county_ratio}}.
    """
    df = pd.read_csv(dist_path, dtype={"geoid": str})
    tr = df[(df["year"] < 2020) & (df["region_type"] == "tract")].copy()
    if tr.empty:
        return {"status": "n/a", "max_ratio": None, "per_measure": {}}
    tr["county"] = tr["geoid"].str[:5]
    bases = sorted({
        m[: -len(_GEO20)] for m in tr["measure"].unique() if m.endswith(_GEO20)
    })
    per_measure: dict[str, float] = {}
    for base in bases:
        if not _is_count(base):
            continue
        g10 = tr[tr["measure"] == base + _GEO10].groupby("county")["value"].sum()
        g20 = tr[tr["measure"] == base + _GEO20].groupby("county")["value"].sum()
        ratio = (g20 / g10).replace([np.inf, -np.inf], np.nan).dropna()
        if not ratio.empty:
            per_measure[base] = float(ratio.max())
    if not per_measure:
        return {"status": "n/a", "max_ratio": None, "per_measure": {}}
    max_ratio = max(per_measure.values())
    return {
        "status": "pass" if max_ratio <= tol else "fail",
        "max_ratio": max_ratio,
        "per_measure": per_measure,
    }
```

- [ ] **Step 4: Run, verify PASS** (incl. the real-data Age check showing inflation):

Run: `uv run pytest tools/census10to20_remediation/test_acceptance.py -v`

- [ ] **Step 5: Commit:**

```bash
git add tools/census10to20_remediation/__init__.py tools/census10to20_remediation/acceptance_test.py tools/census10to20_remediation/test_acceptance.py
git commit -m "feat(remediation): acceptance check_conservation (count county-ratio gate)"
```

---

## Task 3: Acceptance — ratio consistency check

**Files:**
- Modify: `tools/census10to20_remediation/acceptance_test.py`
- Modify: `tools/census10to20_remediation/test_acceptance.py`

For exact-ratio datasets whose constituent counts are published, verify each `percent_geo20` equals `scale · numerator_geo20 / denominator_geo20` per geoid (within tolerance) — catching any residual percent dilution. Driven by a dataset's `measure_info` `geo_standardize` ratio specs.

- [ ] **Step 1: Write the failing test** (append to `test_acceptance.py`):

```python
def test_check_ratio_consistency_passes_when_percent_matches_counts(tmp_path):
    rows = [
        ("51001000002", 2018, "u20_count_geo20", 30, "tract"),
        ("51001000002", 2018, "tot_count_geo20", 100, "tract"),
        ("51001000002", 2018, "u20_pct_geo20", 30.0, "tract"),  # 100*30/100
    ]
    measure_info = {
        "u20_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "tot_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "u20_pct_geo20": {"geo_standardize": {"measure_type": "ratio",
            "numerator": "u20_count", "denominator": "tot_count", "scale": 100}},
    }
    from acceptance_test import check_ratio_consistency
    rep = check_ratio_consistency(_write(tmp_path, rows), measure_info)
    assert rep["status"] == "pass"


def test_check_ratio_consistency_fails_on_diluted_percent(tmp_path):
    rows = [
        ("51001000002", 2018, "u20_count_geo20", 30, "tract"),
        ("51001000002", 2018, "tot_count_geo20", 100, "tract"),
        ("51001000002", 2018, "u20_pct_geo20", 18.0, "tract"),  # diluted (should be 30)
    ]
    measure_info = {
        "u20_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "tot_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "u20_pct_geo20": {"geo_standardize": {"measure_type": "ratio",
            "numerator": "u20_count", "denominator": "tot_count", "scale": 100}},
    }
    from acceptance_test import check_ratio_consistency
    rep = check_ratio_consistency(_write(tmp_path, rows), measure_info)
    assert rep["status"] == "fail"
```

- [ ] **Step 2: Run, verify FAIL** with `ImportError: cannot import name 'check_ratio_consistency'`:

Run: `uv run pytest tools/census10to20_remediation/test_acceptance.py -k ratio_consistency -v`

- [ ] **Step 3: Implement.** Add to `acceptance_test.py` (reuse the package's metadata parser):

```python
from sdc_census10to20 import parse_geo_standardize_info


def check_ratio_consistency(dist_path, measure_info, *, tol: float = 0.5) -> dict:
    """Each ratio _geo20 must equal scale * numerator_geo20 / denominator_geo20.

    Only ratio specs whose numerator AND denominator are present in the file are
    checked (frame-change datasets drop their helper counts, so they are skipped).
    Returns {"status": "pass"|"fail"|"n/a", "max_abs_diff": float|None,
             "checked": [base, ...]}.
    """
    df = pd.read_csv(dist_path, dtype={"geoid": str})
    specs = parse_geo_standardize_info(measure_info)
    present = set(df["measure"].unique())

    def series(base):
        return df[df["measure"] == base + _GEO20].set_index(["geoid", "year"])["value"]

    checked, max_diff = [], 0.0
    for base, spec in specs.items():
        if spec.get("measure_type") not in ("ratio", "rate"):
            continue
        num, den = spec.get("numerator"), spec.get("denominator")
        if not (num and den):
            continue
        if not ({num + _GEO20, den + _GEO20, base + _GEO20} <= present):
            continue
        scale = spec.get("scale", 100)
        recomputed = scale * series(num) / series(den)
        published = series(base)
        diff = (recomputed - published).abs().replace([np.inf, -np.inf], np.nan).dropna()
        if not diff.empty:
            checked.append(base)
            max_diff = max(max_diff, float(diff.max()))
    if not checked:
        return {"status": "n/a", "max_abs_diff": None, "checked": []}
    return {
        "status": "pass" if max_diff <= tol else "fail",
        "max_abs_diff": max_diff,
        "checked": checked,
    }
```

- [ ] **Step 4: Run, verify PASS + full acceptance file:**

Run: `uv run pytest tools/census10to20_remediation/test_acceptance.py -v`

- [ ] **Step 5: Commit:**

```bash
git add tools/census10to20_remediation/acceptance_test.py tools/census10to20_remediation/test_acceptance.py
git commit -m "feat(remediation): acceptance check_ratio_consistency (intensive-fix gate)"
```

---

## Task 4: Entrypoint manifest (base-ACS) + driver import-run mechanism

**Files:**
- Create: `tools/census10to20_remediation/datasets.py`
- Create: `tools/census10to20_remediation/driver.py`
- Test: `tools/census10to20_remediation/test_driver.py`

The manifest lists each dataset's topic dir, ordered entrypoints (`module_path:function`), and the distribution-file glob the acceptance test reads. The driver's `run_entrypoint` loads a module by path and calls a function — executing module top-level (imports) but NOT `if __name__ == "__main__"` (so `update_version` never fires).

- [ ] **Step 1: Write the failing test:**

```python
# tools/census10to20_remediation/test_driver.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from driver import run_entrypoint
from datasets import BASE_ACS


def test_base_acs_manifest_paths_resolve():
    repo = Path(__file__).resolve().parents[2]
    assert BASE_ACS, "manifest is empty"
    for entry in BASE_ACS:
        topic = repo / entry["topic"]
        assert topic.is_dir(), f"missing topic dir: {entry['topic']}"
        for ep in entry["entrypoints"]:
            mod_rel, _, func = ep.partition(":")
            assert (topic / mod_rel).is_file(), f"missing module: {entry['topic']}/{mod_rel}"
            assert func, f"entrypoint missing function: {ep}"


def test_run_entrypoint_calls_module_function_not_main(tmp_path):
    mod = tmp_path / "stub.py"
    mod.write_text(
        "ran = []\n"
        "def run():\n    ran.append('run')\n    return 'ok'\n"
        "if __name__ == '__main__':\n    raise SystemExit('main should not run')\n"
    )
    result = run_entrypoint(mod, "run")
    assert result == "ok"
```

- [ ] **Step 2: Run, verify FAIL** (modules don't exist yet):

Run: `uv run pytest tools/census10to20_remediation/test_driver.py -v`

- [ ] **Step 3: Implement.** Create `datasets.py` with the base-ACS entries (all uniform `ingest.run` → `prepare.run`):

```python
"""Per-dataset regeneration manifest for the census10to20 remediation.

Each entry: topic dir, ordered entrypoints (module-relative path : function),
and the distribution-file glob(s) the acceptance test reads.

Phase 3b adds the composite entries (their entrypoint sequences vary and are
confirmed when that phase runs). 3a covers the uniform base-ACS group.
"""

INGEST = "code/distribution/ingest.py:run"
PREPARE = "code/distribution/prepare.py:run"


def _base(topic, glob):
    return {"topic": topic, "entrypoints": [INGEST, PREPARE], "dist_glob": glob}


BASE_ACS = [
    _base("demographics/Age", "data/distribution/*age_demographics.csv.xz"),
    _base("demographics/Race", "data/distribution/*race*.csv.xz"),
    _base("demographics/Gender", "data/distribution/*gender*.csv.xz"),
    _base("demographics/Language", "data/distribution/*language*.csv.xz"),
    _base("demographics/Veteran", "data/distribution/*veteran*.csv.xz"),
    _base("demographics/Population Density", "data/distribution/*population_density*.csv.xz"),
    _base("demographics/Cooperative extension", "data/distribution/*.csv.xz"),
    _base("demographics/Geographic Mobility (HOI)", "data/distribution/*mobility*.csv.xz"),
    _base("financial_well_being/Household Income", "data/distribution/*income*.csv.xz"),
    _base("financial_well_being/Income Inequality", "data/distribution/*inequality*.csv.xz"),
    _base("financial_well_being/Employment Rates", "data/distribution/*employment*.csv.xz"),
    _base("financial_well_being/Material_Deprivation", "data/distribution/*material*.csv.xz"),
    _base("health/System Usage and Insurance/Without Health Insurance", "data/distribution/*insurance*.csv.xz"),
    _base("education/Years of Schooling", "data/distribution/*schooling*.csv.xz"),
    _base("education/Postsecondary", "data/distribution/*postsecondary*.csv.xz"),
    _base("broadband/Household Broadband", "data/distribution/*broadband*.csv.xz"),
    _base("transportation/Population Characteristics", "data/distribution/*population_characteristics*.csv.xz"),
]
```

Create `driver.py` with the import-run mechanism (orchestration is added in Task 5):

```python
"""Driver for the census10to20 data regeneration (Phase 3b runs this)."""
from __future__ import annotations

import importlib.util
from pathlib import Path


def run_entrypoint(module_path, func_name: str):
    """Import a module by file path and call one of its functions.

    Executes module top-level code (imports, constants) but NOT the
    ``if __name__ == "__main__"`` block — so a pipeline's ``run()`` is invoked
    without triggering the ``update_version`` auto-publish in its ``__main__``.
    """
    module_path = Path(module_path)
    spec = importlib.util.spec_from_file_location(f"_regen_{module_path.stem}", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, func_name)
    return fn()
```

- [ ] **Step 4: Run, verify PASS** (manifest paths resolve; stub run() called, `__main__` not):

Run: `uv run pytest tools/census10to20_remediation/test_driver.py -v`
(If a `dist_glob` matches nothing for a dataset, fix the glob to match its actual committed file — the `test_base_acs_manifest_paths_resolve` test only checks topic/module existence; a follow-up assertion can check globs during 3b. The globs above are starting patterns; adjust any that don't match committed files.)

- [ ] **Step 5: Commit:**

```bash
git add tools/census10to20_remediation/datasets.py tools/census10to20_remediation/driver.py tools/census10to20_remediation/test_driver.py
git commit -m "feat(remediation): base-ACS entrypoint manifest + driver import-run mechanism"
```

---

## Task 5: Driver orchestration + dry-run validation on Age

**Files:**
- Modify: `tools/census10to20_remediation/driver.py`
- Modify: `tools/census10to20_remediation/test_driver.py`

Add `regenerate_dataset(entry, *, repo_root, dry_run)`: in dry-run it runs BEFORE-acceptance on the committed distribution file and reports (NO regen, NO version, NO commit). In real mode (Phase 3b) it additionally runs the entrypoints, re-runs acceptance (AFTER), gates on pass + BEFORE>AFTER, version-bumps local-patch, and commits. 3a validates the dry-run path on Age.

- [ ] **Step 1: Write the failing test** (append to `test_driver.py`):

```python
def test_dry_run_reports_before_acceptance_on_age():
    from driver import regenerate_dataset
    from datasets import BASE_ACS
    repo = Path(__file__).resolve().parents[2]
    age = next(e for e in BASE_ACS if e["topic"] == "demographics/Age")
    report = regenerate_dataset(age, repo_root=repo, dry_run=True)
    assert report["dry_run"] is True
    assert report["regenerated"] is False
    assert report["committed"] is False
    # The committed Age data is still corrupt -> BEFORE acceptance fails (inflation).
    assert report["before"]["status"] == "fail"
    assert report["before"]["max_ratio"] > 1.1
```

- [ ] **Step 2: Run, verify FAIL** with `ImportError: cannot import name 'regenerate_dataset'`:

Run: `uv run pytest tools/census10to20_remediation/test_driver.py::test_dry_run_reports_before_acceptance_on_age -v`

- [ ] **Step 3: Implement.** Add to `driver.py`:

```python
import glob as _glob

from acceptance_test import check_conservation


def _dist_file(entry, repo_root):
    matches = sorted(_glob.glob(str(Path(repo_root) / entry["topic"] / entry["dist_glob"])))
    if not matches:
        raise FileNotFoundError(f"{entry['topic']}: no file matches {entry['dist_glob']}")
    return matches[-1]


def regenerate_dataset(entry, *, repo_root, dry_run: bool):
    """Regenerate one dataset (or, in dry_run, only report BEFORE acceptance).

    Real-mode (dry_run=False) is exercised by Phase 3b. It must run with
    SDC_NO_PUBLISH set and is responsible for: running each entrypoint via
    run_entrypoint, re-running acceptance (AFTER), gating on AFTER pass AND
    AFTER.max_ratio < BEFORE.max_ratio, version-bumping local-patch
    (update_version(topic, force_level="patch", auto_tag=False, auto_release=False)),
    and committing. 3a only validates the dry-run path.
    """
    repo_root = Path(repo_root)
    before = check_conservation(_dist_file(entry, repo_root))
    report = {
        "topic": entry["topic"], "dry_run": dry_run,
        "before": before, "regenerated": False, "committed": False,
    }
    if dry_run:
        return report
    raise NotImplementedError(
        "real-mode regeneration is executed in Phase 3b (run with SDC_NO_PUBLISH=1)"
    )
```

(The real-mode body is intentionally left for Phase 3b, where it is implemented + run against live pipelines. 3a delivers and validates the dry-run path and the gating contract is documented in the docstring.)

- [ ] **Step 4: Run, verify PASS:**

Run: `uv run pytest tools/census10to20_remediation/test_driver.py -v`
Also run the whole harness + suites to confirm no regressions:
Run: `uv run pytest tools/census10to20_remediation tests/test_geo_standardize_metadata.py packages/sdc-census10to20 packages/sdc-core -q`

- [ ] **Step 5: Commit:**

```bash
git add tools/census10to20_remediation/driver.py tools/census10to20_remediation/test_driver.py
git commit -m "feat(remediation): driver dry-run (BEFORE acceptance); real-mode stub for Phase 3b"
```

---

## Done criteria
- `SDC_NO_PUBLISH` kill-switch suppresses auto-tag/release; tested.
- `acceptance_test.check_conservation` detects the known committed-Age inflation (max ratio > 1.1) and passes on conserved data; `check_ratio_consistency` catches diluted percents; both unit-tested.
- Base-ACS entrypoint manifest resolves; driver `run_entrypoint` invokes `run()` without `__main__`; `regenerate_dataset` dry-run reports BEFORE acceptance on Age (status fail).
- NO distribution data regenerated. All prior suites green.

## Follow-on
**Phase 3b — execute the regeneration (consequential; explicitly initiated):**
1. Implement `regenerate_dataset` real-mode (entrypoints → AFTER acceptance gate → local-patch version → commit).
2. Add composite entrypoint-manifest entries (confirm each composite's run sequence: EnvHazard, Walkability, Food, Incarceration, Employment Access, Affordability, Food Accessibility — some have compute steps / working-dir flows).
3. Confirm prerequisites: `CENSUS_API_KEY` (in `.env`), cached external inputs (EJSCREEN, transit, GTFS), `SDC_NO_PUBLISH=1` exported.
4. Run **Age first** as the checkpoint (regen → acceptance pass + BEFORE>AFTER → local patch + commit), then batch base-ACS, then composites. Halt the batch on any acceptance failure.
5. Validate the EnvHazard-NCR `state_fips` watch-item (MD/DC tracts) recorded in memory.
6. Refresh `dashboard_data/` outputs; commit per dataset.
