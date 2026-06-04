# Phase 2c-1 — Replicate Indices, Simple (Segregation, Affordability, Material Deprivation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mark the three composite-index datasets that already use `census_standardize=True` (or have it wired) to **replicate** their index to 2020 children instead of area-interpolating it — Segregation (entropy), Affordability (CNT regression, 6 measures), and Material Deprivation (flip its 1B-1 `interpolate:false` placeholder to `replicate`).

**Architecture:** Pure metadata + wiring, reusing the existing `replicate` measure_type. No pipeline restructuring (these already standardize via `standardize_all`). Per the Phase-2 decision, genuine composite indices are replicated (carried from the area-dominant parent), like median/gini — recompute-from-inputs is impractical for PCA/entropy/regression and is a possible future refinement.

**Tech Stack:** Python 3.12, pandas, pytest, uv workspace. Builds on Phases 0/1/2a/2b.

**Scope:** Phase 2c-1 — the three simple replicate cases. Phase 2c-2 (restructure): Environmental Hazard (manual `convert` on PCA index), Walkability (manual `convert` on rank-sum index), Food Accessibility (local area-weighted crosswalk on a %) — each needs its standardization path redirected through `standardize_all` and is deferred.

**Spec:** `docs/specs/2026-06-03-census10to20-intensive-measure-fix-design.md` (§4.3 replicate; §4.5 composite indices). Branch: `fix/census10to20-data-remediation`.

---

## Facts (from investigation)

- **`demographics/Segregation Index (HOI)`** — measure `segregation_indicator` (key `segregation_indicator_geo20`, descriptive `measure_type:"index"`, no geo_standardize). Shannon-entropy index. Standardizes ingest.py:98-102: `write_data(result, out_dir / filename, census_standardize=out.get("standardize", False))` (resolves True). TOPIC_DIR at ingest.py:20. No measure_info passed currently → entropy index area-interpolated (wrong).
- **`housing/Cost/Affordability_HT`** — 6 measures, keys `affordability_index_geo20`, `housing_cost_pct_geo20`, `transport_cost_pct_geo20`, `autos_per_hh_geo20`, `vmt_per_hh_geo20`, `transit_frac_geo20` (all no measure_type/geo_standardize). CNT regression outputs (no recoverable counts → all replicate). Standardizes ingest.py:117: `write_data(output, WORKING_DIR / filename, census_standardize=True)`; prepare reads working → distribution unchanged. TOPIC_DIR at ingest.py:26. (Note: with no measure_info, `affordability_index` heuristic-classifies as `ratio` and would currently *raise* on regeneration — adding metadata both fixes correctness and prevents the crash.)
- **`financial_well_being/Material_Deprivation`** — measure `material_deprivation_indicator` (key `material_deprivation_indicator_geo20`), currently `geo_standardize: {"measure_type": "index", "interpolate": false}` (1B-1 placeholder). Townsend z-score composite. Standardizes in **prepare.py** at lines 190 and 232, both already wired with `measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None` (1B-1). Only the metadata block needs to flip.

---

## File Structure
- **Modify** `tests/test_geo_standardize_metadata.py` — move Material Deprivation from `INDEX_SKIP_DATASETS` to `REPLICATE_DATASETS`; add Segregation + Affordability to `REPLICATE_DATASETS`.
- **Modify** `financial_well_being/Material_Deprivation/data/distribution/measure_info.json` — flip the block to `replicate`.
- **Modify** `demographics/Segregation Index (HOI)/data/distribution/measure_info.json` + `ingest.py` — replicate metadata + wiring.
- **Modify** `housing/Cost/Affordability_HT/data/distribution/measure_info.json` + `ingest.py` — 6 replicate blocks + wiring.

---

## Task 1: Harness — regroup Material Deprivation + add Segregation & Affordability to replicate

**Files:**
- Modify: `tests/test_geo_standardize_metadata.py`

- [ ] **Step 1: Edit the harness.**

Append the three datasets to `REPLICATE_DATASETS`:
```python
REPLICATE_DATASETS = [
    "financial_well_being/Household Income",
    "education/Years of Schooling",
    "financial_well_being/Income Inequality",
    "transportation/Population Characteristics",
    "demographics/Cooperative extension",
    "financial_well_being/Employment Rates",
    "financial_well_being/Material_Deprivation",
    "demographics/Segregation Index (HOI)",
    "housing/Cost/Affordability_HT",
]
```

Empty `INDEX_SKIP_DATASETS` (Material Deprivation moved out; no dataset uses `interpolate:false` anymore):
```python
INDEX_SKIP_DATASETS = []  # Material Deprivation moved to REPLICATE in Phase 2c-1
```

(`ALL_DATASETS`'s de-dup union already includes both lists. `STANDARDIZE_FILE`: Material Deprivation's prepare.py override from 1B-1 stays; Segregation and Affordability standardize in ingest, so the comprehension default of ingest.py is correct.)

- [ ] **Step 2: Run, verify the three fail (assertion) and nothing else regressed:**

Run: `uv run pytest tests/test_geo_standardize_metadata.py -q`
Expected new failures (assertion-based):
- `test_replicate_measures_take_parent_value[financial_well_being/Material_Deprivation]` — "no replicate/median/mean measures" (still typed `index` until Task 2).
- `test_every_measure_has_valid_geo_standardize` + `test_replicate_measures_take_parent_value` + `test_standardize_call_wires_measure_info` for Segregation and Affordability ("missing geo_standardize block" / "no replicate measures" / "not passing measure_info=").
The `test_index_measures_not_interpolated` group now has 0 parametrizations (empty list) — no instances, fine. All other params stay green.

- [ ] **Step 3: Commit:**

```bash
git add tests/test_geo_standardize_metadata.py
git commit -m "test(phase2c1): move Material Deprivation to replicate; add Segregation & Affordability"
```

---

## Task 2: Material Deprivation — flip index/skip → replicate

**Files:**
- Modify: `financial_well_being/Material_Deprivation/data/distribution/measure_info.json`

The wiring (both prepare.py `write_data` calls passing `measure_info`) already exists from Phase 1B-1; only the metadata block changes.

- [ ] **Step 1: Flip the block.** In `measure_info.json`, change the `material_deprivation_indicator_geo20` object's `geo_standardize` from:
```json
    "geo_standardize": {"measure_type": "index", "interpolate": false},
```
to:
```json
    "geo_standardize": {"measure_type": "replicate"},
```

- [ ] **Step 2: Verify:**

Run: `uv run python -c "import json; json.load(open('financial_well_being/Material_Deprivation/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k Deprivation`
Expected: `valid`; Material Deprivation params PASS — completeness, `test_replicate_measures_take_parent_value` (the indicator now replicates to children), wiring (already present from 1B-1).

- [ ] **Step 3: Commit:**

```bash
git add "financial_well_being/Material_Deprivation/data/distribution/measure_info.json"
git commit -m "feat(material-deprivation): replicate the composite index (flip 1B-1 interpolate:false)"
```

---

## Task 3: Segregation — replicate metadata + ingest wiring

**Files:**
- Modify: `demographics/Segregation Index (HOI)/data/distribution/measure_info.json`
- Modify: `demographics/Segregation Index (HOI)/code/distribution/ingest.py`

- [ ] **Step 1: Metadata.** In `measure_info.json`, add to the `segregation_indicator_geo20` object:
```json
    "geo_standardize": {"measure_type": "replicate"},
```
(Leave the descriptive `"measure_type": "index"` field unchanged. Keep valid JSON.)

- [ ] **Step 2: Wiring.** In `ingest.py`, add `MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"` after the `TOPIC_DIR = ...` line (line 20), and add `measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,` to the write_data call (ingest.py:98-102):
```python
        out_path = write_data(
            result,
            out_dir / filename,
            census_standardize=out.get("standardize", False),
            measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,
        )
```
(Read the file to match exact existing text/indentation.)

- [ ] **Step 3: Verify:**

Run: `uv run python -c "import json; json.load(open('demographics/Segregation Index (HOI)/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k Segregation`
Expected: `valid`; Segregation params PASS — completeness, replicate-to-parent, wiring.

- [ ] **Step 4: Commit:**

```bash
git add "demographics/Segregation Index (HOI)/data/distribution/measure_info.json" "demographics/Segregation Index (HOI)/code/distribution/ingest.py"
git commit -m "feat(segregation): replicate the entropy index + ingest wiring"
```

---

## Task 4: Affordability_HT — 6 replicate blocks + ingest wiring

**Files:**
- Modify: `housing/Cost/Affordability_HT/data/distribution/measure_info.json`
- Modify: `housing/Cost/Affordability_HT/code/distribution/ingest.py`

- [ ] **Step 1: Metadata.** In `measure_info.json`, add `"geo_standardize": {"measure_type": "replicate"},` to EACH of the six measure objects:
- `affordability_index_geo20`
- `housing_cost_pct_geo20`
- `transport_cost_pct_geo20`
- `autos_per_hh_geo20`
- `vmt_per_hh_geo20`
- `transit_frac_geo20`

(All six are CNT-regression outputs with no recoverable constituent counts → replicate. Don't modify `_references`/other fields. Keep valid JSON.)

- [ ] **Step 2: Wiring.** In `ingest.py`, add `MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"` after the `TOPIC_DIR = ...` line (line 26), and change the write_data call (ingest.py:117) to pass measure_info:
```python
        out_path = write_data(
            output,
            WORKING_DIR / filename,
            census_standardize=True,
            measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,
        )
```
(Read the file to match exact text/indentation — it is currently a single-line call; expand it. The measure_info.json is in `data/distribution/` even though this writes to WORKING_DIR — correct; prepare.py carries the standardized `_geo20` measures to distribution unchanged.)

- [ ] **Step 3: Verify (full harness — final task):**

Run: `uv run python -c "import json; json.load(open('housing/Cost/Affordability_HT/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v`
Expected: `valid`; the FULL harness is GREEN — all prior phases + the three 2c-1 datasets. For Affordability: completeness (6 measures), `test_replicate_measures_take_parent_value` (all 6 replicate to children), wiring.

- [ ] **Step 4: Commit:**

```bash
git add "housing/Cost/Affordability_HT/data/distribution/measure_info.json" "housing/Cost/Affordability_HT/code/distribution/ingest.py"
git commit -m "feat(affordability-ht): replicate index + 5 intensive measures + ingest wiring"
```

---

## Done criteria
- Full harness green incl. Segregation, Affordability (6 measures), and Material Deprivation — each composite/intensive measure replicates the area-dominant parent instead of being area-interpolated.
- No data regenerated. Phase-0/1/2a/2b suites still green: `uv run pytest tests/test_geo_standardize_metadata.py packages/sdc-census10to20 packages/sdc-core -q`.

## Follow-on (separate plans)
1. **Phase 2c-2** — restructure replicate: Environmental Hazard (remove the manual `convert_2010_to_2020_bounds(year_data[["geoid","value"]])` on the PCA index at ingest.py:327; route through `standardize_all` with `replicate`), Walkability (remove the manual `convert` on the rank-sum index at ingest.py:157/171), Food Accessibility (remove the local `convert_tracts_2010_to_2020` area-weighting of the percent; let `standardize_all` replicate). Each keeps its index computation on 2010 geoids, then lets `standardize_all` replicate to 2020 — removing the current incorrect index-interpolation.
2. **Phase 3** — combined regeneration with the extended acceptance gate.
