# Phase 1A — Exact-Ratio Metadata (Age, Race, Gender) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Author `geo_standardize` metadata for the three clean exact-ratio base-ACS datasets (Age, Race, Gender) and wire their `measure_info.json` into the ingest standardization call, with a reusable metadata test harness — so a future regeneration produces correct intensive `_geo20` values instead of area-diluted ones.

**Architecture:** No source-logic changes. Per dataset: (1) add a `geo_standardize` block to each `_geo20` measure in `measure_info.json` (counts → `{measure_type: count}`; percents → `{measure_type: ratio, numerator, denominator, scale: 100}`), and (2) pass the dataset's `measure_info.json` path into the existing `write_data(..., census_standardize=...)` call in `ingest.py`. A repo-root pytest harness verifies metadata completeness, referential integrity, and that each ratio recomputes to the parent ratio through the real `standardize_all`.

**Tech Stack:** Python 3.12, pandas, pytest, uv workspace. The `standardize_all` mechanism + `parse_geo_standardize_info` already shipped in Phase 0 (`packages/sdc-census10to20`).

**Scope:** Phase 1A only — the three datasets whose percent denominators are **published counts already in the standardization frame** (verified: Age→`age_total_count`, Race→`race_total_count`, Gender→`gender_total_count`). Language/Veteran/Postsecondary publish only the numerator (denominator dropped before melt) and need a frame change → deferred to Phase 1B. Composites → Phase 2. No distribution data is regenerated here (that is Phase 3).

**Prerequisite spec:** `docs/specs/2026-06-03-census10to20-intensive-measure-fix-design.md` (§3 metadata schema, §4.2 exact ratio). Branch: `fix/census10to20-data-remediation`.

---

## File Structure

- **Create** `tests/test_geo_standardize_metadata.py` — repo-root harness: structural + referential-integrity + functional tests, parametrized over the Phase-1A datasets. One responsibility: verify `geo_standardize` metadata is complete, consistent, and produces correct intensive `_geo20` through the real `standardize_all`.
- **Modify** `demographics/Age/data/distribution/measure_info.json` — add `geo_standardize` to its 7 `_geo20` measures.
- **Modify** `demographics/Race/data/distribution/measure_info.json` — add `geo_standardize` to its 15 `_geo20` measures.
- **Modify** `demographics/Gender/data/distribution/measure_info.json` — add `geo_standardize` to its 5 `_geo20` measures.
- **Modify** `demographics/{Age,Race,Gender}/code/distribution/ingest.py` — define `MEASURE_INFO` and pass it to the existing `write_data` call.

Authoritative metadata to author (base name = measure_info key minus `_geo20`):

**Age** (`demographics/Age/data/distribution/measure_info.json`)
| `_geo20` key | geo_standardize block |
|---|---|
| `age_total_count_geo20` | `{"measure_type": "count"}` |
| `age_under_20_count_geo20` | `{"measure_type": "count"}` |
| `age_20_64_count_geo20` | `{"measure_type": "count"}` |
| `age_65_plus_count_geo20` | `{"measure_type": "count"}` |
| `age_under_20_percent_geo20` | `{"measure_type": "ratio", "numerator": "age_under_20_count", "denominator": "age_total_count", "scale": 100}` |
| `age_20_64_percent_geo20` | `{"measure_type": "ratio", "numerator": "age_20_64_count", "denominator": "age_total_count", "scale": 100}` |
| `age_65_plus_percent_geo20` | `{"measure_type": "ratio", "numerator": "age_65_plus_count", "denominator": "age_total_count", "scale": 100}` |

**Race** (`demographics/Race/data/distribution/measure_info.json`) — all percent denominators are `race_total_count`. Note: `race_hispanic_or_latino_percent` is computed in ingest against `eth_total` (ACS B03003 total), which is not a published measure; `eth_total == race_total_count` (both total population) so exact recompute against `race_total_count` is correct to rounding. Document this in the commit.
| `_geo20` key | geo_standardize block |
|---|---|
| `race_total_count_geo20` | `{"measure_type": "count"}` |
| `race_AAPI_count_geo20` | `{"measure_type": "count"}` |
| `race_afr_amer_alone_count_geo20` | `{"measure_type": "count"}` |
| `race_hispanic_or_latino_count_geo20` | `{"measure_type": "count"}` |
| `race_native_alone_count_geo20` | `{"measure_type": "count"}` |
| `race_other_count_geo20` | `{"measure_type": "count"}` |
| `race_two_or_more_count_geo20` | `{"measure_type": "count"}` |
| `race_wht_alone_count_geo20` | `{"measure_type": "count"}` |
| `race_AAPI_percent_geo20` | `{"measure_type": "ratio", "numerator": "race_AAPI_count", "denominator": "race_total_count", "scale": 100}` |
| `race_afr_amer_alone_percent_geo20` | `{"measure_type": "ratio", "numerator": "race_afr_amer_alone_count", "denominator": "race_total_count", "scale": 100}` |
| `race_hispanic_or_latino_percent_geo20` | `{"measure_type": "ratio", "numerator": "race_hispanic_or_latino_count", "denominator": "race_total_count", "scale": 100}` |
| `race_native_alone_percent_geo20` | `{"measure_type": "ratio", "numerator": "race_native_alone_count", "denominator": "race_total_count", "scale": 100}` |
| `race_other_percent_geo20` | `{"measure_type": "ratio", "numerator": "race_other_count", "denominator": "race_total_count", "scale": 100}` |
| `race_two_or_more_percent_geo20` | `{"measure_type": "ratio", "numerator": "race_two_or_more_count", "denominator": "race_total_count", "scale": 100}` |
| `race_wht_alone_percent_geo20` | `{"measure_type": "ratio", "numerator": "race_wht_alone_count", "denominator": "race_total_count", "scale": 100}` |

**Gender** (`demographics/Gender/data/distribution/measure_info.json`)
| `_geo20` key | geo_standardize block |
|---|---|
| `gender_total_count_geo20` | `{"measure_type": "count"}` |
| `gender_male_count_geo20` | `{"measure_type": "count"}` |
| `gender_female_count_geo20` | `{"measure_type": "count"}` |
| `gender_male_percent_geo20` | `{"measure_type": "ratio", "numerator": "gender_male_count", "denominator": "gender_total_count", "scale": 100}` |
| `gender_female_percent_geo20` | `{"measure_type": "ratio", "numerator": "gender_female_count", "denominator": "gender_total_count", "scale": 100}` |

---

## Task 1: Metadata test harness (fails until metadata authored)

**Files:**
- Create: `tests/test_geo_standardize_metadata.py`

- [ ] **Step 1: Write the harness** (the whole file):

```python
"""Phase 1 harness: verify geo_standardize metadata is complete, consistent,
and produces correct intensive _geo20 values through the real standardize_all.

Scope: Phase 1A datasets (exact-ratio: percent denominators are published counts).
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from sdc_census10to20 import convert, parse_geo_standardize_info

REPO_ROOT = Path(__file__).resolve().parents[1]

# Phase 1A: datasets whose percent denominators are published counts in-frame.
PHASE_1A = ["demographics/Age", "demographics/Race", "demographics/Gender"]

VALID_TYPES = {"count", "ratio", "rate", "median", "mean", "density", "index"}


def _measure_info(dataset: str) -> dict:
    path = REPO_ROOT / dataset / "data/distribution/measure_info.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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


@pytest.mark.parametrize("dataset", PHASE_1A)
def test_every_geo20_measure_has_valid_geo_standardize(dataset):
    mi = _measure_info(dataset)
    geo20_keys = [k for k in mi if k.endswith("_geo20")]
    assert geo20_keys, f"{dataset}: no _geo20 measures found"
    specs = parse_geo_standardize_info(mi)
    for key in geo20_keys:
        base = key[: -len("_geo20")]
        assert base in specs, f"{dataset}: {key} missing geo_standardize block"
        mtype = specs[base].get("measure_type")
        assert mtype in VALID_TYPES, f"{dataset}: {key} bad measure_type {mtype!r}"


@pytest.mark.parametrize("dataset", PHASE_1A)
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
        assert num in count_bases, f"{dataset}: {base} numerator {num!r} not a published count"
        assert den in count_bases, f"{dataset}: {base} denominator {den!r} not a published count"


@pytest.mark.parametrize("dataset", PHASE_1A)
def test_ratios_recompute_to_parent_value(dataset, monkeypatch, split_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: split_crosswalk)
    mi = _measure_info(dataset)
    specs = parse_geo_standardize_info(mi)
    counts = sorted(b for b, s in specs.items() if s.get("measure_type") == "count")
    ratios = {b: s for b, s in specs.items() if s.get("measure_type") in ("ratio", "rate")}
    assert ratios, f"{dataset}: no ratio measures in metadata"

    # Distinct positive values per count so a numerator/denominator swap would fail.
    values = {c: 100.0 * (i + 1) for i, c in enumerate(counts)}
    parent = "51001000020"
    rows = [(parent, c, values[c]) for c in counts]
    rows += [(parent, b, 0.0) for b in ratios]  # ratio input value is recomputed, irrelevant
    data = pd.DataFrame({
        "geoid":       [r[0] for r in rows],
        "year":        [2018] * len(rows),
        "measure":     [r[1] for r in rows],
        "value":       [r[2] for r in rows],
        "moe":         [pd.NA] * len(rows),
        "region_type": ["tract"] * len(rows),
    })
    out = convert.standardize_all(data, measure_info=mi)

    for base, spec in ratios.items():
        expected = spec["scale"] * values[spec["numerator"]] / values[spec["denominator"]]
        got = out[out["measure"] == f"{base}_geo20"].set_index("geoid")["value"]
        assert got["51001000002"] == pytest.approx(expected), f"{dataset}:{base} child A"
        assert got["51001000003"] == pytest.approx(expected), f"{dataset}:{base} child B"
```

- [ ] **Step 2: Run, verify it FAILS** (no `geo_standardize` blocks authored yet):

Run: `uv run pytest tests/test_geo_standardize_metadata.py -v`
Expected: all parametrizations FAIL — `test_every_geo20_measure_has_valid_geo_standardize` fails with "missing geo_standardize block"; the ratio/functional tests fail with "no ratio measures in metadata".

- [ ] **Step 3: Commit the harness:**

```bash
git add tests/test_geo_standardize_metadata.py
git commit -m "test(phase1): geo_standardize metadata harness for Age/Race/Gender"
```

---

## Task 2: Author Age `geo_standardize` metadata

**Files:**
- Modify: `demographics/Age/data/distribution/measure_info.json`

- [ ] **Step 1: Add a `geo_standardize` key to each of the 7 `_geo20` measure objects**, using the exact blocks from the Age table in the File Structure section. JSON key order within each measure object does not matter; insert `"geo_standardize": {...}` as a new top-level key inside each measure's object (e.g. alongside `"aggregation_method"`). Do not modify `_references` or any other field. Concretely, for example, the `age_under_20_percent_geo20` object gains:

```json
    "geo_standardize": {
      "measure_type": "ratio",
      "numerator": "age_under_20_count",
      "denominator": "age_total_count",
      "scale": 100
    },
```

and `age_total_count_geo20` gains `"geo_standardize": {"measure_type": "count"},`. Apply the corresponding block to all 7 measures per the Age table.

- [ ] **Step 2: Verify the JSON still parses and the Age params now pass:**

Run: `uv run python -c "import json; json.load(open('demographics/Age/data/distribution/measure_info.json')); print('valid json')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k Age`
Expected: `valid json`; all three Age-parametrized tests PASS. (Race/Gender still fail — that's expected until their tasks.)

- [ ] **Step 3: Commit:**

```bash
git add demographics/Age/data/distribution/measure_info.json
git commit -m "feat(age): geo_standardize metadata (counts + exact-ratio percents)"
```

---

## Task 3: Author Race `geo_standardize` metadata

**Files:**
- Modify: `demographics/Race/data/distribution/measure_info.json`

- [ ] **Step 1: Add a `geo_standardize` key to each of the 15 `_geo20` measure objects**, using the exact blocks from the Race table in the File Structure section (8 counts → `{"measure_type": "count"}`; 7 percents → ratio with the listed numerator, `denominator: "race_total_count"`, `scale: 100`). Note in particular that `race_hispanic_or_latino_percent_geo20` uses `denominator: "race_total_count"` even though ingest divides by `eth_total` — they are equal (both total population). Do not modify `_references`.

- [ ] **Step 2: Verify JSON parses and Race params pass:**

Run: `uv run python -c "import json; json.load(open('demographics/Race/data/distribution/measure_info.json')); print('valid json')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k Race`
Expected: `valid json`; all three Race-parametrized tests PASS.

- [ ] **Step 3: Commit:**

```bash
git add demographics/Race/data/distribution/measure_info.json
git commit -m "feat(race): geo_standardize metadata (counts + exact-ratio percents; hispanic denom=race_total_count)"
```

---

## Task 4: Author Gender `geo_standardize` metadata

**Files:**
- Modify: `demographics/Gender/data/distribution/measure_info.json`

- [ ] **Step 1: Add a `geo_standardize` key to each of the 5 `_geo20` measure objects**, using the exact blocks from the Gender table (3 counts → count; 2 percents → ratio with the listed numerator, `denominator: "gender_total_count"`, `scale: 100`). Do not modify `_references`.

- [ ] **Step 2: Verify JSON parses and the full harness is green:**

Run: `uv run python -c "import json; json.load(open('demographics/Gender/data/distribution/measure_info.json')); print('valid json')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v`
Expected: `valid json`; ALL parametrizations (Age, Race, Gender) PASS now.

- [ ] **Step 3: Commit:**

```bash
git add demographics/Gender/data/distribution/measure_info.json
git commit -m "feat(gender): geo_standardize metadata (counts + exact-ratio percents)"
```

---

## Task 5: Wire `measure_info` into the three ingest standardization calls

**Files:**
- Modify: `demographics/Age/code/distribution/ingest.py`
- Modify: `demographics/Race/code/distribution/ingest.py`
- Modify: `demographics/Gender/code/distribution/ingest.py`
- Modify: `tests/test_geo_standardize_metadata.py` (add a wiring test)

Each ingest standardizes via `write_data(result, out_dir / filename, census_standardize=standardize)` (Age `ingest.py:135-139`, Race `ingest.py:100-104`, Gender `ingest.py:76`). Each has `TOPIC_DIR = Path(__file__).resolve().parents[2]`. We add a `MEASURE_INFO` constant and pass it.

- [ ] **Step 1: Add the wiring test** (append to `tests/test_geo_standardize_metadata.py`):

```python
@pytest.mark.parametrize("dataset", PHASE_1A)
def test_ingest_wires_measure_info(dataset):
    src = (REPO_ROOT / dataset / "code/distribution/ingest.py").read_text(encoding="utf-8")
    assert "MEASURE_INFO" in src, f"{dataset}: ingest.py missing MEASURE_INFO constant"
    assert "measure_info=" in src, f"{dataset}: ingest.py write_data not passing measure_info"
```

- [ ] **Step 2: Run it, verify it FAILS** (ingests don't wire measure_info yet):

Run: `uv run pytest tests/test_geo_standardize_metadata.py::test_ingest_wires_measure_info -v`
Expected: all three FAIL with "missing MEASURE_INFO constant".

- [ ] **Step 3: Edit each ingest.py.** In each file, add the constant immediately after the `TOPIC_DIR = ...` line:

```python
MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"
```

Then change the `write_data` call to pass it. For **Age** (`ingest.py:135-139`) and **Race** (`ingest.py:100-104`), the call spans multiple lines — change:

```python
        out_path = write_data(
            result,
            out_dir / filename,
            census_standardize=standardize,
        )
```
to:
```python
        out_path = write_data(
            result,
            out_dir / filename,
            census_standardize=standardize,
            measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,
        )
```

For **Gender** (`ingest.py:76`), the call is a single line:
```python
        out_path = write_data(result, out_dir / filename, census_standardize=standardize)
```
change to:
```python
        out_path = write_data(
            result, out_dir / filename, census_standardize=standardize,
            measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,
        )
```

- [ ] **Step 4: Run the wiring test + full harness, verify all pass:**

Run: `uv run pytest tests/test_geo_standardize_metadata.py -v`
Expected: all tests PASS (structural, integrity, functional, and wiring for all 3 datasets).

Also confirm the ingest modules still import cleanly (no syntax error), e.g. for Age:
Run: `uv run python -c "import importlib.util,pathlib; p='demographics/Age/code/distribution/ingest.py'; s=importlib.util.spec_from_file_location('age_ingest',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print('MEASURE_INFO:', m.MEASURE_INFO.name)"`
Expected: prints `MEASURE_INFO: measure_info.json`.
(Repeat the import check for Race and Gender, adjusting the path and module name.)

- [ ] **Step 5: Commit:**

```bash
git add demographics/Age/code/distribution/ingest.py demographics/Race/code/distribution/ingest.py demographics/Gender/code/distribution/ingest.py tests/test_geo_standardize_metadata.py
git commit -m "feat(demographics): wire measure_info into Age/Race/Gender ingest standardization"
```

---

## Done criteria
- `tests/test_geo_standardize_metadata.py` passes for Age, Race, Gender: every `_geo20` measure has a valid `geo_standardize` block; every ratio references published counts with a scale; each ratio recomputes to the parent ratio through the real `standardize_all`; each ingest wires `measure_info`.
- No distribution data regenerated; no `standardize_all`/`write_data` source changes (mechanism shipped in Phase 0).
- Existing Phase-0 suites remain green: `uv run pytest packages/sdc-census10to20 packages/sdc-core -q`.

## Follow-on (separate plans)
1. **Phase 1B** — datasets needing a weight/count added to the standardization frame: Language (`total_hh`), Veteran (`vet_denom` civilian-18+), Postsecondary (`total`), plus population-weight/replicate/density cases (Without Health Insurance, Broadband, Population Characteristics, Cooperative extension, Employment Rates, Population Density, Household Income, Years of Schooling, Material Deprivation, Income Inequality). Extend the harness's `PHASE_1A` list and add weight-referential-integrity checks.
2. **Phase 2** — composite-index recompute-from-standardized-inputs (8 HOI/index datasets), authoring their `index → interpolate:false` metadata alongside the recompute fix.
3. **Phase 3** — the combined regeneration (now-unblocked remediation spec) with the extended acceptance gate.
