# Phase 1B-1 — Replicate/Index Metadata (no frame change) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Author `geo_standardize` metadata for the six Phase-1B datasets that need NO standardization-frame change — those whose intensive `_geo20` measures are replicated from the area-dominant parent (median/mean/replicate) or are composite indices skipped pending Phase 2 — plus a small `replicate` measure_type in the mechanism and a generalized metadata harness.

**Architecture:** Add a `replicate` measure_type to `standardize_all` (routes to the existing dominant-parent replicate helper). Generalize the repo-root harness to cover three dataset groups (exact-ratio, replicate, index-skip) and plain-keyed measure_info files. Then per dataset: add `geo_standardize` blocks and wire `measure_info` into the existing `write_data(..., census_standardize=...)` call (in ingest for five datasets, in prepare for Material Deprivation). No distribution data regenerated; no exact-ratio frame changes (those are Phase 1B-2).

**Tech Stack:** Python 3.12, pandas, pytest, uv workspace. Builds on Phase 0 (`standardize_all`) and Phase 1A (the harness).

**Scope:** Phase 1B-1 only. The frame-change exact-ratio/density datasets (Veteran, Language, Postsecondary, Without Health Insurance, Employment Rates, Population Density) are Phase 1B-2. Composites/HOIs are Phase 2. Regeneration is Phase 3.

**Spec:** `docs/specs/2026-06-03-census10to20-intensive-measure-fix-design.md` (§4.3 median/mean replicate, §4.5 index skip). Branch: `fix/census10to20-data-remediation`.

---

## Type decisions (rationale)

- **median / mean** → replicate the area-dominant parent (§4.3). `median_household_income` (median), `average_years_schooling` (mean), `commute_time` (mean).
- **replicate** → a new generic type for intensive values that must be carried (parent → children) but are neither median nor mean: `gini_index` (a directly-published Census statistic, B19083 — not a composite, cannot be reaggregated), and ACS-precomputed percents with no numerator/denominator/total-pop available in the frame: `perc_carpool`, `perc_no_vehicle`, `perc_male`, `perc_children_raised_by_GPs`, `disconnectedYouth`, `voterTurnout`.
- **index + interpolate:false** → `material_deprivation_indicator` is a genuine composite z-score index; correct handling is recompute-from-standardized-inputs in **Phase 2**. For now mark it skipped (no interpolated `_geo20`); Phase 2 produces the correct `_geo20`. (No data is regenerated before Phase 2 + Phase 3.)

## Metadata to author (base name = measure_info key minus `_geo20`; some files key by plain base name)

| Dataset | measure_info.json key | geo_standardize block |
|---|---|---|
| `financial_well_being/Household Income` | `median_household_income_geo20` | `{"measure_type": "median"}` |
| `education/Years of Schooling` | `average_years_schooling_geo20` | `{"measure_type": "mean"}` |
| `financial_well_being/Income Inequality` | `gini_index_geo20` | `{"measure_type": "replicate"}` |
| `transportation/Population Characteristics` | `commute_time_geo20` | `{"measure_type": "mean"}` |
| `transportation/Population Characteristics` | `perc_carpool_geo20` | `{"measure_type": "replicate"}` |
| `transportation/Population Characteristics` | `perc_no_vehicle_geo20` | `{"measure_type": "replicate"}` |
| `demographics/Cooperative extension` | `perc_male` *(plain key)* | `{"measure_type": "replicate"}` |
| `demographics/Cooperative extension` | `perc_children_raised_by_GPs` *(plain key)* | `{"measure_type": "replicate"}` |
| `demographics/Cooperative extension` | `disconnectedYouth` *(plain key)* | `{"measure_type": "replicate"}` |
| `demographics/Cooperative extension` | `voterTurnout` *(plain key)* | `{"measure_type": "replicate"}` |
| `financial_well_being/Material_Deprivation` | `material_deprivation_indicator_geo20` | `{"measure_type": "index", "interpolate": false}` |

## Standardization call sites (where to wire `measure_info`)

| Dataset | File | Call |
|---|---|---|
| `financial_well_being/Household Income` | `code/distribution/ingest.py` (~74-78) | `write_data(result, out_dir / f"{auto_name}.csv.xz", census_standardize=True)` |
| `education/Years of Schooling` | `code/distribution/ingest.py` (~116-120) | `write_data(result, out_dir / f"{auto_name}.csv.xz", census_standardize=True)` |
| `financial_well_being/Income Inequality` | `code/distribution/ingest.py` (~65-69) | `write_data(result, out_dir / f"{auto_name}.csv.xz", census_standardize=True)` |
| `transportation/Population Characteristics` | `code/distribution/ingest.py` (~79-82) | `write_data(result, out_dir / f"{auto_name}.csv.xz", census_standardize=True)` |
| `demographics/Cooperative extension` | `code/distribution/ingest.py` (~140-144) | `write_data(result, out_dir / filename, census_standardize=out_cfg.get("standardize", False))` |
| `financial_well_being/Material_Deprivation` | `code/distribution/prepare.py` (189 & 228) | `write_data(va_townsend, DIST_DIR / filename, census_standardize=True)` and `write_data(ncr_townsend, ...)` |

---

## Task 1: Add `replicate` measure_type to `standardize_all`

**Files:**
- Modify: `packages/sdc-census10to20/src/sdc_census10to20/convert.py`
- Test: `packages/sdc-census10to20/tests/test_convert.py`

The existing dispatch has `elif mtype in ("median", "mean"):` routing to `_redistribute_replicate`. Add `"replicate"` to that tuple so a generic replicate type works.

- [ ] **Step 1: Write the failing test** (append to `tests/test_convert.py`):

```python
def test_standardize_all_replicate_type_replicates_dominant_parent(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({
        "geoid": ["51001000020"], "year": [2018], "measure": ["some_score"],
        "value": [0.42], "moe": [pd.NA], "region_type": ["tract"],
    })
    mi = {"some_score_geo20": {"geo_standardize": {"measure_type": "replicate"}}}
    out = convert.standardize_all(data, measure_info=mi)
    s = out[out["measure"] == "some_score_geo20"].set_index("geoid")["value"]
    assert s["51001000002"] == pytest.approx(0.42)
    assert s["51001000003"] == pytest.approx(0.42)
```

- [ ] **Step 2: Run, verify it FAILS** with `ValueError: unknown measure_type 'replicate'`:

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_standardize_all_replicate_type_replicates_dominant_parent -v`

- [ ] **Step 3: Implement.** In `convert.py`, find the dispatch branch `elif mtype in ("median", "mean"):` and change it to:

```python
                    elif mtype in ("median", "mean", "replicate"):
```

(The branch body — calling `_redistribute_replicate` — is unchanged.)

- [ ] **Step 4: Run the new test + full file, verify all pass:**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py -v`

- [ ] **Step 5: Commit:**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/tests/test_convert.py
git commit -m "feat(census10to20): add replicate measure_type (routes to dominant-parent replicate)"
```

---

## Task 2: Generalize the metadata harness for replicate/index/plain-keyed datasets

**Files:**
- Modify: `tests/test_geo_standardize_metadata.py` (rewrite)

Replace the file with the version below. It keeps the exact-ratio coverage, generalizes completeness to all non-underscore keys (handles plain-keyed files), and adds replicate + index-skip functional tests and a per-dataset standardize-file map for the wiring test. After this task, the three Phase-1A datasets stay green and the six Phase-1B-1 datasets fail (no metadata/wiring yet).

- [ ] **Step 1: Overwrite `tests/test_geo_standardize_metadata.py`** with:

```python
"""Phase 1 harness: verify geo_standardize metadata is complete, consistent,
and produces correct intensive _geo20 values through the real standardize_all.
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from sdc_census10to20 import convert, parse_geo_standardize_info

REPO_ROOT = Path(__file__).resolve().parents[1]

# Percents recompute exactly from published in-frame counts.
EXACT_RATIO_DATASETS = ["demographics/Age", "demographics/Race", "demographics/Gender"]

# Intensive measures replicate the area-dominant parent (median/mean/replicate).
REPLICATE_DATASETS = [
    "financial_well_being/Household Income",
    "education/Years of Schooling",
    "financial_well_being/Income Inequality",
    "transportation/Population Characteristics",
    "demographics/Cooperative extension",
]

# Composite index skipped here; recomputed from standardized inputs in Phase 2.
INDEX_SKIP_DATASETS = ["financial_well_being/Material_Deprivation"]

ALL_DATASETS = EXACT_RATIO_DATASETS + REPLICATE_DATASETS + INDEX_SKIP_DATASETS

# Where each dataset's census_standardize=True write_data call lives.
STANDARDIZE_FILE = {d: "code/distribution/ingest.py" for d in ALL_DATASETS}
STANDARDIZE_FILE["financial_well_being/Material_Deprivation"] = "code/distribution/prepare.py"

VALID_TYPES = {"count", "ratio", "rate", "median", "mean", "replicate", "density", "index"}
REPLICATE_TYPES = {"median", "mean", "replicate"}


def _measure_info(dataset: str) -> dict:
    path = REPO_ROOT / dataset / "data/distribution/measure_info.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _measure_keys(mi: dict) -> list:
    """Top-level measure keys, excluding underscore-prefixed metadata (_references)."""
    return [k for k in mi if not k.startswith("_")]


def _base(key: str) -> str:
    return key[: -len("_geo20")] if key.endswith("_geo20") else key


@pytest.fixture
def split_crosswalk() -> pd.DataFrame:
    # Parent 51001000020 splits into .002 (area 600) and .003 (area 400).
    return pd.DataFrame({
        "geoid20":     ["51001000002", "51001000003"],
        "geoid10":     ["51001000020", "51001000020"],
        "area20":      [600, 400],
        "area10":      [1000, 1000],
        "area_part":   [600, 400],
        "type_change": ["split", "split"],
    })


def _synthetic_frame(parent, measure_values):
    rows = [(parent, m, v) for m, v in measure_values.items()]
    return pd.DataFrame({
        "geoid":       [r[0] for r in rows],
        "year":        [2018] * len(rows),
        "measure":     [r[1] for r in rows],
        "value":       [r[2] for r in rows],
        "moe":         [pd.NA] * len(rows),
        "region_type": ["tract"] * len(rows),
    })


@pytest.mark.parametrize("dataset", ALL_DATASETS)
def test_every_measure_has_valid_geo_standardize(dataset):
    mi = _measure_info(dataset)
    keys = _measure_keys(mi)
    assert keys, f"{dataset}: no measures found"
    specs = parse_geo_standardize_info(mi)
    for key in keys:
        base = _base(key)
        assert base in specs, f"{dataset}: {key} missing geo_standardize block"
        mtype = specs[base].get("measure_type")
        assert mtype in VALID_TYPES, f"{dataset}: {key} bad measure_type {mtype!r}"


@pytest.mark.parametrize("dataset", EXACT_RATIO_DATASETS)
def test_ratio_specs_reference_published_counts(dataset):
    mi = _measure_info(dataset)
    specs = parse_geo_standardize_info(mi)
    count_bases = {b for b, s in specs.items() if s.get("measure_type") == "count"}
    ratios = {b: s for b, s in specs.items() if s.get("measure_type") in ("ratio", "rate")}
    assert ratios, f"{dataset}: no ratio measures in metadata"
    for base, spec in ratios.items():
        num, den = spec.get("numerator"), spec.get("denominator")
        assert num and den, f"{dataset}: {base} ratio missing numerator/denominator"
        assert "scale" in spec, f"{dataset}: {base} ratio missing scale"
        assert spec["scale"] > 0, f"{dataset}: {base} scale must be positive, got {spec['scale']!r}"
        assert num in count_bases, f"{dataset}: {base} numerator {num!r} not a published count"
        assert den in count_bases, f"{dataset}: {base} denominator {den!r} not a published count"


@pytest.mark.parametrize("dataset", EXACT_RATIO_DATASETS)
def test_ratios_recompute_to_parent_value(dataset, monkeypatch, split_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: split_crosswalk)
    mi = _measure_info(dataset)
    specs = parse_geo_standardize_info(mi)
    counts = sorted(b for b, s in specs.items() if s.get("measure_type") == "count")
    ratios = {b: s for b, s in specs.items() if s.get("measure_type") in ("ratio", "rate")}
    assert ratios, f"{dataset}: no ratio measures in metadata"
    values = {c: 100.0 * (i + 1) for i, c in enumerate(counts)}
    measure_values = {c: values[c] for c in counts}
    measure_values.update({b: 0.0 for b in ratios})  # ratio input recomputed
    data = _synthetic_frame("51001000020", measure_values)
    out = convert.standardize_all(data, measure_info=mi)
    for base, spec in ratios.items():
        expected = spec["scale"] * values[spec["numerator"]] / values[spec["denominator"]]
        got = out[out["measure"] == f"{base}_geo20"].set_index("geoid")["value"]
        assert got["51001000002"] == pytest.approx(expected), f"{dataset}:{base} A"
        assert got["51001000003"] == pytest.approx(expected), f"{dataset}:{base} B"


@pytest.mark.parametrize("dataset", REPLICATE_DATASETS)
def test_replicate_measures_take_parent_value(dataset, monkeypatch, split_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: split_crosswalk)
    mi = _measure_info(dataset)
    specs = parse_geo_standardize_info(mi)
    repl = sorted(b for b, s in specs.items() if s.get("measure_type") in REPLICATE_TYPES)
    assert repl, f"{dataset}: no replicate/median/mean measures in metadata"
    values = {b: 10.0 * (i + 1) for i, b in enumerate(repl)}
    data = _synthetic_frame("51001000020", values)
    out = convert.standardize_all(data, measure_info=mi)
    for base in repl:
        got = out[out["measure"] == f"{base}_geo20"].set_index("geoid")["value"]
        assert got["51001000002"] == pytest.approx(values[base]), f"{dataset}:{base} A"
        assert got["51001000003"] == pytest.approx(values[base]), f"{dataset}:{base} B"


@pytest.mark.parametrize("dataset", INDEX_SKIP_DATASETS)
def test_index_measures_not_interpolated(dataset, monkeypatch, split_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: split_crosswalk)
    mi = _measure_info(dataset)
    specs = parse_geo_standardize_info(mi)
    idx = sorted(b for b, s in specs.items() if s.get("measure_type") == "index")
    assert idx, f"{dataset}: no index measures in metadata"
    data = _synthetic_frame("51001000020", {b: 0.5 for b in idx})
    out = convert.standardize_all(data, measure_info=mi)
    measures = set(out["measure"])
    for base in idx:
        assert f"{base}_geo10" in measures, f"{dataset}:{base} _geo10 should exist"
        assert f"{base}_geo20" not in measures, f"{dataset}:{base} _geo20 should be skipped"


@pytest.mark.parametrize("dataset", ALL_DATASETS)
def test_standardize_call_wires_measure_info(dataset):
    rel = STANDARDIZE_FILE[dataset]
    src = (REPO_ROOT / dataset / rel).read_text(encoding="utf-8")
    assert "measure_info=" in src, f"{dataset}: {rel} write_data not passing measure_info="
```

- [ ] **Step 2: Run, verify Phase-1A green and Phase-1B-1 red:**

Run: `uv run pytest tests/test_geo_standardize_metadata.py -v`
Expected: the `EXACT_RATIO_DATASETS` (Age/Race/Gender) parametrizations PASS (completeness, ratio, recompute, wiring). The `REPLICATE_DATASETS` and `INDEX_SKIP_DATASETS` parametrizations FAIL — completeness fails "missing geo_standardize block"; replicate/index tests fail "no ... measures in metadata"; wiring fails "not passing measure_info=". These failures are expected (metadata/wiring authored in Tasks 3-8).

- [ ] **Step 3: Commit:**

```bash
git add tests/test_geo_standardize_metadata.py
git commit -m "test(phase1b): generalize metadata harness (replicate/index groups, plain keys, standardize-file map)"
```

---

## Task 3: Household Income — median metadata + ingest wiring

**Files:**
- Modify: `financial_well_being/Household Income/data/distribution/measure_info.json`
- Modify: `financial_well_being/Household Income/code/distribution/ingest.py`

- [ ] **Step 1: Metadata.** Add to the `median_household_income_geo20` object in measure_info.json:

```json
    "geo_standardize": {"measure_type": "median"},
```

- [ ] **Step 2: Wiring.** In `ingest.py`, add after the `TOPIC_DIR = ...` line:

```python
MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"
```

and change the `write_data(result, out_dir / f"{auto_name}.csv.xz", census_standardize=True)` call to:

```python
        out_path = write_data(
            result,
            out_dir / f"{auto_name}.csv.xz",
            census_standardize=True,
            measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,
        )
```

(Read the file first; match the exact existing call text and indentation.)

- [ ] **Step 3: Verify:**

Run: `uv run python -c "import json; json.load(open('financial_well_being/Household Income/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k "Household_Income or Household Income"`
Expected: `valid`; the Household Income parametrizations (completeness, replicate, wiring) PASS.

- [ ] **Step 4: Commit:**

```bash
git add "financial_well_being/Household Income/data/distribution/measure_info.json" "financial_well_being/Household Income/code/distribution/ingest.py"
git commit -m "feat(household-income): median geo_standardize metadata + ingest wiring"
```

---

## Task 4: Years of Schooling — mean metadata + ingest wiring

**Files:**
- Modify: `education/Years of Schooling/data/distribution/measure_info.json`
- Modify: `education/Years of Schooling/code/distribution/ingest.py`

- [ ] **Step 1: Metadata.** Add to the `average_years_schooling_geo20` object:

```json
    "geo_standardize": {"measure_type": "mean"},
```

- [ ] **Step 2: Wiring.** In `ingest.py`, add `MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"` after the `TOPIC_DIR = ...` line, and change the `write_data(result, out_dir / f"{auto_name}.csv.xz", census_standardize=True)` call to add `measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,` (multi-line form as in Task 3). Read the file to match exact text.

- [ ] **Step 3: Verify:**

Run: `uv run python -c "import json; json.load(open('education/Years of Schooling/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k "Years of Schooling"`
Expected: `valid`; Years of Schooling parametrizations PASS.

- [ ] **Step 4: Commit:**

```bash
git add "education/Years of Schooling/data/distribution/measure_info.json" "education/Years of Schooling/code/distribution/ingest.py"
git commit -m "feat(years-of-schooling): mean geo_standardize metadata + ingest wiring"
```

---

## Task 5: Income Inequality — gini replicate metadata + ingest wiring

**Files:**
- Modify: `financial_well_being/Income Inequality/data/distribution/measure_info.json`
- Modify: `financial_well_being/Income Inequality/code/distribution/ingest.py`

- [ ] **Step 1: Metadata.** Add to the `gini_index_geo20` object:

```json
    "geo_standardize": {"measure_type": "replicate"},
```

- [ ] **Step 2: Wiring.** In `ingest.py`, add `MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"` after `TOPIC_DIR = ...`, and add `measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,` to the `write_data(result, out_dir / f"{auto_name}.csv.xz", census_standardize=True)` call. Read the file to match exact text.

- [ ] **Step 3: Verify:**

Run: `uv run python -c "import json; json.load(open('financial_well_being/Income Inequality/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k "Income Inequality"`
Expected: `valid`; Income Inequality parametrizations PASS.

- [ ] **Step 4: Commit:**

```bash
git add "financial_well_being/Income Inequality/data/distribution/measure_info.json" "financial_well_being/Income Inequality/code/distribution/ingest.py"
git commit -m "feat(income-inequality): gini replicate geo_standardize metadata + ingest wiring"
```

---

## Task 6: Population Characteristics — mean + replicate metadata + ingest wiring

**Files:**
- Modify: `transportation/Population Characteristics/data/distribution/measure_info.json`
- Modify: `transportation/Population Characteristics/code/distribution/ingest.py`

- [ ] **Step 1: Metadata.** Add blocks to the three measure objects:
- `commute_time_geo20` → `"geo_standardize": {"measure_type": "mean"},`
- `perc_carpool_geo20` → `"geo_standardize": {"measure_type": "replicate"},`
- `perc_no_vehicle_geo20` → `"geo_standardize": {"measure_type": "replicate"},`

- [ ] **Step 2: Wiring.** In `ingest.py`, add `MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"` after `TOPIC_DIR = ...`, and add `measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,` to the `write_data(result, out_dir / f"{auto_name}.csv.xz", census_standardize=True,)` call. Read the file to match exact text.

- [ ] **Step 3: Verify:**

Run: `uv run python -c "import json; json.load(open('transportation/Population Characteristics/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k "Population Characteristics"`
Expected: `valid`; Population Characteristics parametrizations PASS (completeness, replicate for all 3 measures, wiring).

- [ ] **Step 4: Commit:**

```bash
git add "transportation/Population Characteristics/data/distribution/measure_info.json" "transportation/Population Characteristics/code/distribution/ingest.py"
git commit -m "feat(population-characteristics): mean/replicate geo_standardize metadata + ingest wiring"
```

---

## Task 7: Cooperative extension — replicate metadata (plain keys) + ingest wiring

**Files:**
- Modify: `demographics/Cooperative extension/data/distribution/measure_info.json`
- Modify: `demographics/Cooperative extension/code/distribution/ingest.py`

This file keys measures by PLAIN base name (no `_geo20` suffix). Add a block to each of the four measure objects:
- `perc_male` → `"geo_standardize": {"measure_type": "replicate"},`
- `perc_children_raised_by_GPs` → `"geo_standardize": {"measure_type": "replicate"},`
- `disconnectedYouth` → `"geo_standardize": {"measure_type": "replicate"},`
- `voterTurnout` → `"geo_standardize": {"measure_type": "replicate"},`

- [ ] **Step 1: Metadata.** Add the four blocks.

- [ ] **Step 2: Wiring.** In `ingest.py`, add `MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"` after `TOPIC_DIR = ...`, and change the `write_data(result, out_dir / filename, census_standardize=out_cfg.get("standardize", False))` call to add `measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,`. Read the file to match exact text.

- [ ] **Step 3: Verify:**

Run: `uv run python -c "import json; json.load(open('demographics/Cooperative extension/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k "Cooperative extension"`
Expected: `valid`; Cooperative extension parametrizations PASS (completeness over the 4 plain keys, replicate for all 4, wiring).

- [ ] **Step 4: Commit:**

```bash
git add "demographics/Cooperative extension/data/distribution/measure_info.json" "demographics/Cooperative extension/code/distribution/ingest.py"
git commit -m "feat(cooperative-extension): replicate geo_standardize metadata + ingest wiring"
```

---

## Task 8: Material Deprivation — index/skip metadata + prepare wiring (two calls)

**Files:**
- Modify: `financial_well_being/Material_Deprivation/data/distribution/measure_info.json`
- Modify: `financial_well_being/Material_Deprivation/code/distribution/prepare.py`

This dataset standardizes in **prepare.py** with TWO `write_data(..., census_standardize=True)` calls (VA at ~189, NCR at ~228). It marks the composite index skipped for now (Phase 2 recomputes it from standardized inputs).

- [ ] **Step 1: Metadata.** Add to the `material_deprivation_indicator_geo20` object:

```json
    "geo_standardize": {"measure_type": "index", "interpolate": false},
```

- [ ] **Step 2: Wiring.** Read `prepare.py`. It already loads a `measure_info` value (around line 168, e.g. `measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None`) and defines `DIST_DIR`. Ensure a `MEASURE_INFO = DIST_DIR / "measure_info.json"` constant exists (it likely does; if not, add it near `DIST_DIR`). Add `measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None` to BOTH `write_data(..., census_standardize=True)` calls:

```python
        va_dist_path = write_data(
            va_townsend, DIST_DIR / filename, census_standardize=True,
            measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,
        )
```
and the analogous `ncr_townsend` call. Match exact existing variable names/indentation from the file.

- [ ] **Step 3: Verify:**

Run: `uv run python -c "import json; json.load(open('financial_well_being/Material_Deprivation/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v`
Expected: `valid`; the FULL harness is green (all of Age/Race/Gender + the six Phase-1B-1 datasets) — including `test_index_measures_not_interpolated[financial_well_being/Material_Deprivation]` and the wiring test reading prepare.py.

- [ ] **Step 4: Commit:**

```bash
git add "financial_well_being/Material_Deprivation/data/distribution/measure_info.json" "financial_well_being/Material_Deprivation/code/distribution/prepare.py"
git commit -m "feat(material-deprivation): index/skip geo_standardize metadata + prepare wiring"
```

---

## Done criteria
- `tests/test_geo_standardize_metadata.py` fully green: completeness for all 9 datasets (3 exact-ratio + 5 replicate + 1 index-skip); exact-ratio recompute (Age/Race/Gender); replicate-to-parent (the 5 replicate datasets); index-not-interpolated (Material Deprivation); and `measure_info=` wired in the correct standardize file for every dataset.
- `replicate` measure_type works in `standardize_all`; Phase-0 suites still green: `uv run pytest packages/sdc-census10to20 packages/sdc-core -q`.
- No distribution data regenerated; no frame changes (those are Phase 1B-2).

## Follow-on (separate plans)
1. **Phase 1B-2** — frame-change exact ratios + density: Veteran, Language, Postsecondary, Without Health Insurance, Employment Rates, Population Density. Melt the existing numerator/denominator counts into the standardization frame, exact-recompute the ratio (density = count/area20), then **drop the helper counts before publish** (per the chosen policy). Extend the harness with an EXACT_RATIO_FRAMECHANGE group.
2. **Phase 2** — composite-index recompute-from-standardized-inputs (Material Deprivation + the 8 HOI/index datasets).
3. **Phase 3** — combined regeneration (now-unblocked remediation spec) with the extended acceptance gate.
