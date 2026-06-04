# Phase 2a — Geographic Mobility (reclassified exact ratio) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `demographics/Geographic Mobility (HOI)` — investigation reclassified it as an exact-ratio dataset, not a composite: `perc_moving` is `moving_count / total_count` with both counts published in the standardization frame, so it gets the same exact-ratio treatment as Age/Race/Gender. Its fourth measure `perc_moving_direct` is a block-group dasymetric redistribution produced outside `standardize_all` and is marked `external`.

**Architecture:** Author `geo_standardize` metadata (count + exact-ratio) and wire `measure_info` into the ingest standardization call — reuses the existing mechanism with no changes. Add an `external` measure_type to the harness's valid set for measures produced outside `standardize_all` (here, `perc_moving_direct`, built by `sdc_core.redistribute` in prepare with `census_standardize=False`). No `standardize_all` change is needed: an `external` measure never reaches it (prepare writes `census_standardize=False`), and if one ever did, the existing unknown-type `ValueError` is the correct loud failure.

**Tech Stack:** Python 3.12, pandas, pytest, uv workspace. Builds on Phases 0/1.

**Scope:** Phase 2a — Geographic Mobility only. The census10to20 fix here is for `perc_moving` (the `standardize_all`-managed measure). `perc_moving_direct`'s redistribution correctness is governed by `sdc_core.redistribute` (a separate engine, not the `convert_2010_to_2020_bounds` bug) — out of scope for this remediation; marked `external`. Other Phase-2 sub-plans: 2b (2020-native passthrough: Incarceration, Employment Access), 2c (replicate indices: Environmental Hazard, Segregation, Walkability, Affordability, Material Deprivation, Food Accessibility).

**Spec:** `docs/specs/2026-06-03-census10to20-intensive-measure-fix-design.md` (§4.2 exact ratio). Branch: `fix/census10to20-data-remediation`.

---

## Facts (from investigation)

`demographics/Geographic Mobility (HOI)` measure_info `_geo20` keys: `perc_moving_geo20`, `perc_moving_direct_geo20`, `geo_mobility_total_count_geo20`, `geo_mobility_moving_count_geo20`.

`compute_measures` (ingest.py:27-42):
```python
    df["geo_mobility_total_count"] = df["total_pop"]    # B07204_001
    df["geo_mobility_moving_count"] = df["pop_moving"]  # B07204_003
    df["perc_moving"] = 100 * df["pop_moving"] / df["total_pop"]
    ...
    measure_cols = ["geo_mobility_total_count", "geo_mobility_moving_count", "perc_moving"]
```
All three are melted into the ingest frame. Standardizes at ingest.py:72-76: `write_data(result, out_dir / filename, census_standardize=standardize)` (no `measure_info` currently → `perc_moving` heuristic-classifies as `count` and is area-weighted, the bug).

`perc_moving_direct` is produced in **prepare.py** via `run_redistribution` (`sdc_core.redistribute`, prepare.py:88-99) and written with `census_standardize=False` (prepare.py:111-114) — it never passes through `standardize_all`.

No `geo_standardize` blocks exist yet.

---

## File Structure
- **Modify** `tests/test_geo_standardize_metadata.py` — add `external` to `VALID_TYPES`; add Geographic Mobility to `EXACT_RATIO_DATASETS`.
- **Modify** `demographics/Geographic Mobility (HOI)/data/distribution/measure_info.json` — count + ratio + external blocks.
- **Modify** `demographics/Geographic Mobility (HOI)/code/distribution/ingest.py` — wire `measure_info`.

---

## Task 1: Harness — `external` type + add Geographic Mobility to exact-ratio group

**Files:**
- Modify: `tests/test_geo_standardize_metadata.py`

- [ ] **Step 1: Edit the harness.**

Add `"external"` to `VALID_TYPES` (measures produced outside `standardize_all`, e.g. dasymetric redistribution):
```python
VALID_TYPES = {"count", "ratio", "rate", "median", "mean", "replicate", "density", "index", "external"}
```

Append Geographic Mobility to `EXACT_RATIO_DATASETS`:
```python
EXACT_RATIO_DATASETS = [
    "demographics/Age",
    "demographics/Race",
    "demographics/Gender",
    "demographics/Geographic Mobility (HOI)",
]
```

(No other harness edits. `ALL_DATASETS` already includes `EXACT_RATIO_DATASETS`; `STANDARDIZE_FILE`'s comprehension maps Geographic Mobility to `code/distribution/ingest.py` — correct, that's where it standardizes. The `external` measure `perc_moving_direct` is not a `count` or `ratio`, so `test_ratio_specs_reference_published_counts` and `test_ratios_recompute_to_parent_value` skip it; `test_every_measure_has_valid_geo_standardize` accepts it via `VALID_TYPES`.)

- [ ] **Step 2: Run, verify Geographic Mobility fails (assertion) and nothing else regressed:**

Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k Mobility`
Expected: Geographic Mobility params FAIL — `test_every_measure_has_valid_geo_standardize` ("missing geo_standardize block"), `test_ratio_specs_reference_published_counts` ("no ratio measures in metadata"), `test_ratios_recompute_to_parent_value` ("no ratio measures in metadata"), `test_standardize_call_wires_measure_info` ("not passing measure_info=").
Then: `uv run pytest tests/test_geo_standardize_metadata.py -q` — confirm ONLY the new Geographic Mobility failures (everything else green).

- [ ] **Step 3: Commit:**

```bash
git add tests/test_geo_standardize_metadata.py
git commit -m "test(phase2a): external measure_type + add Geographic Mobility to exact-ratio group"
```

---

## Task 2: Geographic Mobility — ratio/count/external metadata + ingest wiring

**Files:**
- Modify: `demographics/Geographic Mobility (HOI)/data/distribution/measure_info.json`
- Modify: `demographics/Geographic Mobility (HOI)/code/distribution/ingest.py`

- [ ] **Step 1: Metadata.** Add a `geo_standardize` block to each of the four `_geo20` measure objects:
- `geo_mobility_total_count_geo20` → `"geo_standardize": {"measure_type": "count"},`
- `geo_mobility_moving_count_geo20` → `"geo_standardize": {"measure_type": "count"},`
- `perc_moving_geo20` → `"geo_standardize": {"measure_type": "ratio", "numerator": "geo_mobility_moving_count", "denominator": "geo_mobility_total_count", "scale": 100},`
- `perc_moving_direct_geo20` → `"geo_standardize": {"measure_type": "external"},`

(`perc_moving_direct` is produced by `run_redistribution` in prepare, not `standardize_all`; the `external` marker documents that and satisfies completeness. Don't modify `_references`/other fields. Keep valid JSON.)

- [ ] **Step 2: Wiring.** In `ingest.py`, add `MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"` after the `TOPIC_DIR = ...` line, and change the write_data call (ingest.py:72-76) to add the measure_info kwarg:

```python
        out_path = write_data(
            result,
            out_dir / filename,
            census_standardize=standardize,
            measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,
        )
```

(Read the file to match exact existing call text/indentation. The two counts are published and correctly area-weighted; `perc_moving` now recomputes exactly from them. `perc_moving_direct` is created later in prepare — not affected by this call.)

- [ ] **Step 3: Verify:**

Run: `uv run python -c "import json; json.load(open('demographics/Geographic Mobility (HOI)/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k Mobility`
Expected: `valid`; Geographic Mobility params PASS — completeness (4 keys incl. external), `test_ratio_specs_reference_published_counts` (perc_moving references published counts), `test_ratios_recompute_to_parent_value` (perc_moving → parent ratio), wiring.
Then run the full harness to confirm no regressions:
Run: `uv run pytest tests/test_geo_standardize_metadata.py packages/sdc-census10to20 packages/sdc-core -q`

- [ ] **Step 4: Commit:**

```bash
git add "demographics/Geographic Mobility (HOI)/data/distribution/measure_info.json" "demographics/Geographic Mobility (HOI)/code/distribution/ingest.py"
git commit -m "feat(geographic-mobility): exact-ratio metadata (perc_moving) + external perc_moving_direct + wiring"
```

---

## Done criteria
- Full harness green incl. Geographic Mobility: `perc_moving` recomputes to the parent ratio from its published counts; `perc_moving_direct` marked `external` (out of `standardize_all` scope); counts area-weighted.
- No data regenerated. Phase-0/1 suites still green.

## Note (out of scope, flag for later)
`perc_moving_direct` is a block-group dasymetric redistribution via `sdc_core.redistribute` — NOT the `convert_2010_to_2020_bounds` bug this remediation targets. Whether `run_redistribution` itself correctly handles the percentage (vs. diluting it) is a separate `sdc-redistribute` correctness question, independent of census10to20. Not addressed here.

## Follow-on (separate plans)
1. **Phase 2b** — 2020-native passthrough: `public_safety/Incarceration (HOI)` (PPI 2020 tracts) and `financial_well_being/Employment Access Index` (TIGER2020). These compute on 2020 boundaries natively and must NOT be redistributed — turn off the spurious standardization and emit `_geo20` as-is (no `_geo10`). Likely needs a small mechanism concept for "already-2020 passthrough" or `census_standardize=False` + direct `_geo20` labeling.
2. **Phase 2c** — replicate indices: Environmental Hazard (PCA), Segregation (entropy), Walkability (rank-sum), Affordability (regression), Material Deprivation (change its 1B-1 `interpolate:false` to `replicate`), Food Accessibility (currently a local area-weighted crosswalk on a percent). Route each index through `standardize_all` with a `replicate` spec instead of the current index-interpolation / direct-`convert` / local-crosswalk paths.
3. **Phase 3** — combined regeneration with the extended acceptance gate.
