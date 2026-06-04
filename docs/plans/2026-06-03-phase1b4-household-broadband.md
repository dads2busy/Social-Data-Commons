# Phase 1B-4 — Household Broadband (frame-change ratios in prepare) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cover the last uncovered base-ACS dataset — `broadband/Household Broadband` — whose three `perc_hh_*` measures are computed in `prepare.py` from counts dropped before the melt (and which currently mis-classify as `count` and get area-weighted as extensive). Melt the numerator/denominator counts as helpers, author exact-ratio metadata, and wire `measure_info` into the two `prepare.py` standardization calls.

**Architecture:** Reuses the Phase 1B-2/1B-3 melt-then-drop mechanism unchanged (`input_only_measures` auto-derive). `compute_measures` (shared by VA and NCR) keeps the raw count columns in the melt; the three ratio specs reference them; `referenced_helper_measures` auto-derives them as input-only and `standardize_all` drops them from output. No mechanism change. No data regenerated.

**Tech Stack:** Python 3.12, pandas, pytest, uv workspace. Builds on Phase 0/1A/1B-1/1B-2/1B-3.

**Scope:** Phase 1B-4 — one dataset. This is the **16th and final base-ACS dataset**; completing it means every base-ACS dataset has correct `geo_standardize` metadata + wiring. Composites/HOIs (incl. Material Deprivation recompute) → Phase 2. Combined regeneration → Phase 3.

**Spec:** `docs/specs/2026-06-03-census10to20-intensive-measure-fix-design.md` (§4.2 exact ratio). Branch: `fix/census10to20-data-remediation`.

---

## Facts (from investigation)

- measure_info keys (suffixed): `perc_hh_with_broadband_geo20`, `perc_hh_with_cable_fiber_dsl_geo20`, `perc_hh_without_internet_geo20`. Currently **no** `geo_standardize` blocks.
- `compute_measures` (prepare.py:61-82, shared by VA+NCR) computes the three percents from raw count columns, then melts only `[c for c in df.columns if c.startswith("perc_hh_")]` — so the numerator counts (`hh_with_broadband`, `hh_with_cable_fiber_dsl`, `hh_without_internet`) and denominator (`total_hh`) are dropped.
- Standardizes in **prepare.py** with two calls: `va_dist_path = write_data(va_long, DIST_DIR / filename, census_standardize=True)` (line 120) and `ncr_dist_path = write_data(ncr_long, DIST_DIR / filename, census_standardize=True)` (line 158). A `measure_info` local is already defined (line 88: `measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None`) but only passed to `data_reformat_for_site`, not `write_data`.
- Helper counts (melted in, auto-dropped): `hh_with_broadband`, `hh_with_cable_fiber_dsl`, `hh_without_internet`, `total_hh`.

---

## File Structure

- **Modify** `tests/test_geo_standardize_metadata.py` — add Household Broadband to `EXACT_RATIO_FRAMECHANGE_DATASETS` + `STANDARDIZE_FILE` override (prepare.py).
- **Modify** `broadband/Household Broadband/code/distribution/prepare.py` — include the count columns in the melt; pass `measure_info` to both `write_data` calls.
- **Modify** `broadband/Household Broadband/data/distribution/measure_info.json` — three ratio `geo_standardize` blocks.

---

## Task 1: Harness — add Household Broadband (prepare-standardized frame-change)

**Files:**
- Modify: `tests/test_geo_standardize_metadata.py`

- [ ] **Step 1: Edit the harness.** Append `broadband/Household Broadband` to `EXACT_RATIO_FRAMECHANGE_DATASETS`:

```python
EXACT_RATIO_FRAMECHANGE_DATASETS = [
    "demographics/Veteran",
    "demographics/Language",
    "education/Postsecondary",
    "health/System Usage and Insurance/Without Health Insurance",
    "financial_well_being/Employment Rates",
    "broadband/Household Broadband",
]
```

Add a `STANDARDIZE_FILE` override for it (it standardizes in prepare.py, like Material Deprivation). Find the existing override line `STANDARDIZE_FILE["financial_well_being/Material_Deprivation"] = "code/distribution/prepare.py"` and add immediately after it:

```python
STANDARDIZE_FILE["broadband/Household Broadband"] = "code/distribution/prepare.py"
```

(No other harness edits — `ALL_DATASETS` already includes `EXACT_RATIO_FRAMECHANGE_DATASETS`, and the `test_framechange_ratios_recompute_and_drop_helpers` test already covers the group.)

- [ ] **Step 2: Run, verify prior-green stay green and Household Broadband fails:**

Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k "Broadband or broadband"`
Expected: Household Broadband params FAIL with assertion errors — `test_every_measure_has_valid_geo_standardize` ("missing geo_standardize block"), `test_framechange_ratios_recompute_and_drop_helpers` ("expected helper ... counts" — empty until ratio specs authored), `test_standardize_call_wires_measure_info` ("not passing measure_info=" — reads prepare.py). Then run the full file to confirm nothing else regressed:
Run: `uv run pytest tests/test_geo_standardize_metadata.py -q` (only the 3 new Broadband failures).

- [ ] **Step 3: Commit:**

```bash
git add tests/test_geo_standardize_metadata.py
git commit -m "test(phase1b4): add Household Broadband to frame-change group (prepare-standardized)"
```

---

## Task 2: Household Broadband — melt count helpers + ratio metadata + wire both prepare calls

**Files:**
- Modify: `broadband/Household Broadband/code/distribution/prepare.py`
- Modify: `broadband/Household Broadband/data/distribution/measure_info.json`

- [ ] **Step 1: Keep the count columns in the melt.** In `compute_measures` (prepare.py), the melt currently is:

```python
    id_cols = ["geoid", "year", "region_type"]
    measure_cols = [c for c in df.columns if c.startswith("perc_hh_")]
```

Change `measure_cols` to also include the four raw count columns (the three numerators + the denominator), so they melt as helper measures:

```python
    id_cols = ["geoid", "year", "region_type"]
    count_cols = [
        "hh_with_broadband", "hh_with_cable_fiber_dsl",
        "hh_without_internet", "total_hh",
    ]
    measure_cols = [c for c in df.columns if c.startswith("perc_hh_")] + count_cols
```

(These raw count columns already exist on `df` at this point — they are the inputs to the percent computation just above. The rest of `compute_measures` — the `melt`, `long["moe"] = pd.NA`, `return long` — is unchanged. Read the file to confirm the exact surrounding lines.)

- [ ] **Step 2: Metadata.** In `measure_info.json`, add a `geo_standardize` block to each of the three percent objects (all share denominator `total_hh`, scale 100):
- `perc_hh_with_broadband_geo20` → `"geo_standardize": {"measure_type": "ratio", "numerator": "hh_with_broadband", "denominator": "total_hh", "scale": 100},`
- `perc_hh_with_cable_fiber_dsl_geo20` → `"geo_standardize": {"measure_type": "ratio", "numerator": "hh_with_cable_fiber_dsl", "denominator": "total_hh", "scale": 100},`
- `perc_hh_without_internet_geo20` → `"geo_standardize": {"measure_type": "ratio", "numerator": "hh_without_internet", "denominator": "total_hh", "scale": 100},`

(Do NOT add entries for the four helper counts — they stay unpublished, auto-derived as input-only, dropped from output. Don't modify `_references`/other fields. Keep valid JSON.)

- [ ] **Step 3: Wiring.** In `prepare.py`, the `run()` function already defines `measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None` (line 88), before both `write_data(..., census_standardize=True)` calls. Pass it to BOTH:
- line 120: change `va_dist_path = write_data(va_long, DIST_DIR / filename, census_standardize=True)` to
  ```python
          va_dist_path = write_data(
              va_long, DIST_DIR / filename, census_standardize=True,
              measure_info=measure_info,
          )
  ```
- line 158: change `ncr_dist_path = write_data(ncr_long, DIST_DIR / filename, census_standardize=True)` to
  ```python
          ncr_dist_path = write_data(
              ncr_long, DIST_DIR / filename, census_standardize=True,
              measure_info=measure_info,
          )
  ```

(Read the file to match exact indentation. Reuse the existing `measure_info` local — no new constant needed. `input_only` is auto-derived inside `standardize_all` from `measure_info`, so no extra kwarg.)

- [ ] **Step 4: Verify (full harness — final task):**

Run: `uv run python -c "import json; json.load(open('broadband/Household Broadband/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v`
Expected: `valid`; the FULL harness is GREEN, now covering all 16 base-ACS datasets. For Household Broadband: completeness (3 measures), `test_framechange_ratios_recompute_and_drop_helpers` (all 3 percents → parent ratio; the 4 helper counts dropped — no `_geo10`/`_geo20`), wiring (reads prepare.py).

- [ ] **Step 5: Commit:**

```bash
git add "broadband/Household Broadband/data/distribution/measure_info.json" "broadband/Household Broadband/code/distribution/prepare.py"
git commit -m "feat(household-broadband): exact-ratio metadata + melt count helpers + prepare wiring"
```

---

## Done criteria
- Full harness green incl. Household Broadband: all 3 `perc_hh_*` measures recompute to the parent ratio, and the 4 helper counts (`hh_with_broadband`, `hh_with_cable_fiber_dsl`, `hh_without_internet`, `total_hh`) are dropped from output.
- No data regenerated; published measure set unchanged. Phase-0/1A/1B-1/1B-2/1B-3 suites still green: `uv run pytest tests/test_geo_standardize_metadata.py packages/sdc-census10to20 packages/sdc-core -q`.
- **Milestone:** all **16** base-ACS datasets now carry correct `geo_standardize` metadata + wiring (verify: `len(ALL_DATASETS) == 16`).

## Follow-on (separate plans)
1. **Phase 2** — composite-index recompute-from-standardized-inputs: Material Deprivation (recompute the Townsend z-score index on 2020 boundaries from standardized inputs, replacing the `interpolate:false` placeholder) + the 8 HOI/index datasets (Environmental Hazard, Food Accessibility, Incarceration, Geographic Mobility, Segregation, Employment Access, Walkability, Affordability). Verify each computes its index from standardized inputs, not by interpolating the index. Start with EnvHazard `ingest.py:327`.
2. **Phase 3** — combined regeneration (now-unblocked remediation spec) with the extended acceptance gate.
