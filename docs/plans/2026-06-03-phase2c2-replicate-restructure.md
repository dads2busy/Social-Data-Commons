# Phase 2c-2 — Replicate Indices, Restructure (Environmental Hazard, Walkability, Food Accessibility) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the three composite/percent datasets that **manually** redistribute their index to 2020 boundaries by area-weighting (which dilutes the index) — switch them to **replicate** (carry the area-dominant parent's value). They must keep their manual vintage handling because their data is on 2010 boundaries for years ≥ 2020 (so `standardize_all`'s `year<2020` rule cannot drive them).

**Architecture:** Add a public `replicate_2010_to_2020_bounds` primitive (dominant-parent replicate, the sibling of `convert_2010_to_2020_bounds`). Environmental Hazard and Walkability swap their `convert_2010_to_2020_bounds(index)` calls for it; Food Accessibility's local area-weighting crosswalk is rewritten to dominant-parent and its spurious `census_standardize=True` is turned off (it now manually emits `_geo20`). These three are manually-standardized (not via `standardize_all`); their measures are marked `external` for harness completeness, and correctness rests on the primitive's unit test + per-dataset review.

**Tech Stack:** Python 3.12, pandas, pytest, uv workspace. Builds on Phases 0/1/2a/2b/2c-1.

**Scope:** Phase 2c-2 — the final three affected datasets. After this, all 24 are configured and Phase 3 (combined regeneration) can run. `external` is already in `VALID_TYPES` (added in 2a).

**Why not `standardize_all`:** Investigation confirmed each has 2010-boundary data in years ≥ 2020 — Environmental Hazard 2016-2021 (incl. 2020/2021), Walkability all of 2017-2023 (D4C is `bg2010`), Food Accessibility all years (extrapolated from 2010-vintage FARA). `standardize_all` keys vintage on `year<2020`, so it would mishandle their post-2020 rows. Their existing manual conversion already encodes the correct vintage; only the redistribution math is wrong.

**Spec:** `docs/specs/2026-06-03-census10to20-intensive-measure-fix-design.md` (§4.3 replicate; §4.5 composite indices). Branch: `fix/census10to20-data-remediation`.

---

## Facts (from investigation)

- **Environmental Hazard** (`environment/Environmental Hazard Index (HOI)/code/distribution/ingest.py`): imports `from sdc_core.geo import convert_2010_to_2020_bounds` (line 26). `GEO_2010_YEARS = list(range(2016, 2022))`; for those years it keeps `_geo10` and calls `convert_2010_to_2020_bounds(year_data[["geoid", "value"]], geoid_col="geoid", val_col="value")` (ingest.py:327-331) to build `_geo20`; 2022-2024 are already `_geo20`. `write_data` (ingest.py:394, 417) does NOT pass `census_standardize`. Measure `environmental_hazard_index`, tract-level. measure_info key `environmental_hazard_index_geo20`, no geo_standardize.
- **Walkability** (`transportation/Walkability/code/distribution/ingest.py`): imports `from sdc_core.geo import convert_2010_to_2020_bounds` (line 18). `add_geo_suffixes` calls `convert_2010_to_2020_bounds(year_df[["geoid","value"]])` (national, ~line 157) and `convert_2010_to_2020_bounds(st_tracts[["geoid","value"]], state_fips=st_fips)` (regional, ~line 171) for ALL years' tract index; `_geo10` is the original, counties/BG handled separately. `write_data` `census_standardize=False` (ingest.py:224-227); prepare.py `census_standardize=False`. Measure `walkability_index`. measure_info key `walkability_index_geo20`, no geo_standardize.
- **Food Accessibility** (`food/Food Access/Food Accessibility Indicator (HOI)/code/distribution/ingest.py`): local `convert_tracts_2010_to_2020(df, xwalk)` (ingest.py:111-134) area-weights the percent via `weight = arealand_part / arealand_2020` then groupby-sum; called at ingest.py:183-184 BEFORE `interpolate_extrapolate`. `write_data(long, ..., census_standardize=True)` (ingest.py:227) — with no measure_info this heuristic-classifies `food_access_percentage` as `ratio` and would RAISE on regeneration. Measure `food_access_percentage`, tract-level, only `_geo20` published. measure_info key `food_access_percentage_geo20`, no geo_standardize.

---

## File Structure
- **Modify** `packages/sdc-census10to20/src/sdc_census10to20/convert.py` + `__init__.py` — public `replicate_2010_to_2020_bounds`; `_redistribute_replicate` delegates to it.
- **Modify** `packages/sdc-core/src/sdc_core/geo.py` — re-export `replicate_2010_to_2020_bounds`.
- **Modify** `tests/test_geo_standardize_metadata.py` — `EXTERNAL_STANDARDIZE_DATASETS` group; add to `ALL_DATASETS`; exclude from the wiring test.
- **Modify** 3× `measure_info.json` (external blocks) + 3× `ingest.py`.
- **Test** `packages/sdc-census10to20/tests/test_convert.py`.

---

## Task 1: Public `replicate_2010_to_2020_bounds` primitive

**Files:**
- Modify: `packages/sdc-census10to20/src/sdc_census10to20/convert.py`, `.../__init__.py`
- Modify: `packages/sdc-core/src/sdc_core/geo.py`
- Test: `packages/sdc-census10to20/tests/test_convert.py`

Expose the dominant-parent replicate (currently internal in `_redistribute_replicate`) as a public sibling of `convert_2010_to_2020_bounds`, so pipelines that manually convert can swap to it.

- [ ] **Step 1: Write the failing test** (append to `tests/test_convert.py`):

```python
def test_replicate_2010_to_2020_bounds_takes_dominant_parent(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import replicate_2010_to_2020_bounds
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    # Parent .020 (value 0.7) splits into .002/.003 -> both take 0.7 (dominant parent).
    data = pd.DataFrame({"geoid": ["51001000020"], "value": [0.7]})
    out = replicate_2010_to_2020_bounds(data, geoid_col="geoid", val_col="value")
    vals = out.set_index("geoid")["value"]
    assert vals["51001000002"] == pytest.approx(0.7)
    assert vals["51001000003"] == pytest.approx(0.7)
```

- [ ] **Step 2: Run, verify FAIL** with `ImportError: cannot import name 'replicate_2010_to_2020_bounds'`:

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_replicate_2010_to_2020_bounds_takes_dominant_parent -v`

- [ ] **Step 3: Implement.** In `convert.py`, add the public function (place near `convert_2010_to_2020_bounds`), and refactor the existing `_redistribute_replicate` to delegate to it. Read the current `_redistribute_replicate` (it does the dominant-parent logic + a NaN `warnings.warn`); move that body into the public function:

```python
def replicate_2010_to_2020_bounds(data, *, geoid_col="geoid", val_col="value", state_fips="51"):
    """Replicate a single year/measure of 2010-vintage values onto 2020 boundaries.

    Each 2020 tract takes the value of its area-dominant 2010 parent (largest
    land-area overlap). Use for non-additive per-tract statistics/indices that
    cannot be areal-interpolated (median, gini, entropy, PCA z-score, rank-sum,
    regression index) — the parent's value is the best estimate for each child
    absent sub-tract detail. Sibling of ``convert_2010_to_2020_bounds`` (which is
    for extensive count measures).

    Returns a frame with columns ``["geoid", val_col]`` on 2020 boundaries.
    """
    data = data.copy()
    data[geoid_col] = data[geoid_col].astype(str)
    geoids = list(data[geoid_col].unique())
    xwalk = create_crosswalk(geoids, state_fips=state_fips)
    dom_idx = xwalk.groupby("geoid20")["area_part"].idxmax()
    dom = xwalk.loc[dom_idx, ["geoid20", "geoid10"]]
    parent_vals = data.rename(columns={geoid_col: "geoid10"})[["geoid10", val_col]]
    out = dom.merge(parent_vals, on="geoid10", how="left")
    out = out.rename(columns={"geoid20": "geoid"})[["geoid", val_col]]
    if out[val_col].isna().any():
        warnings.warn(
            "some 2020 tracts had no dominant 2010 parent in the input data; "
            "their replicated value is NaN",
            stacklevel=2,
        )
    return out
```

Then replace the body of `_redistribute_replicate` (keep its signature so `standardize_all`'s replicate branch is unchanged) with a delegation:

```python
def _redistribute_replicate(meas_slice, *, geoid_col, value_col, state_fips):
    """Each 2020 child takes its area-dominant 2010 parent's value."""
    return replicate_2010_to_2020_bounds(
        meas_slice, geoid_col=geoid_col, val_col=value_col, state_fips=state_fips,
    )
```

Add `replicate_2010_to_2020_bounds` to `convert.py`'s `__all__`, and to `packages/sdc-census10to20/src/sdc_census10to20/__init__.py` (import from `.convert` + add to `__all__`).

In `packages/sdc-core/src/sdc_core/geo.py`, re-export it alongside `convert_2010_to_2020_bounds` (add to the import from `sdc_census10to20` and to `geo.py`'s `__all__` if it has one).

- [ ] **Step 4: Run the new test + full census10to20 + sdc-core suites, verify all pass:**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py -v`
Run: `cd packages/sdc-core && uv run pytest tests/ -v`
Run: `uv run python -c "from sdc_core.geo import replicate_2010_to_2020_bounds; print('ok')"`
(The existing replicate tests still pass since `_redistribute_replicate` now delegates to the same logic.)

- [ ] **Step 5: Commit:**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/src/sdc_census10to20/__init__.py packages/sdc-core/src/sdc_core/geo.py packages/sdc-census10to20/tests/test_convert.py
git commit -m "feat(census10to20): public replicate_2010_to_2020_bounds (dominant-parent sibling of convert)"
```

---

## Task 2: Harness — external-standardize group

**Files:**
- Modify: `tests/test_geo_standardize_metadata.py`

These three standardize manually (not via `standardize_all`), so they get `external` metadata and are excluded from the `measure_info=` wiring test. (`external` is already in `VALID_TYPES` from Phase 2a.)

- [ ] **Step 1: Edit the harness.** Add a group (after `GEO2020_DATASETS`):

```python
# Manually standardized via replicate_2010_to_2020_bounds in their own ingest
# (their 2010-vintage data extends past 2020, so standardize_all's year<2020 rule
# can't drive them). Measures are marked `external`; correctness is covered by the
# replicate primitive's unit test + per-dataset review.
EXTERNAL_STANDARDIZE_DATASETS = [
    "environment/Environmental Hazard Index (HOI)",
    "transportation/Walkability",
    "food/Food Access/Food Accessibility Indicator (HOI)",
]
```

Add to the `ALL_DATASETS` de-dup union:
```python
ALL_DATASETS = list(dict.fromkeys(
    EXACT_RATIO_DATASETS
    + REPLICATE_DATASETS
    + INDEX_SKIP_DATASETS
    + EXACT_RATIO_FRAMECHANGE_DATASETS
    + DENSITY_DATASETS
    + GEO2020_DATASETS
    + EXTERNAL_STANDARDIZE_DATASETS
))
```

Exclude external datasets from the wiring test (they don't pass `measure_info`). Change the `test_standardize_call_wires_measure_info` parametrization from `ALL_DATASETS` to:
```python
@pytest.mark.parametrize(
    "dataset", [d for d in ALL_DATASETS if d not in EXTERNAL_STANDARDIZE_DATASETS]
)
def test_standardize_call_wires_measure_info(dataset):
    ...
```

(Completeness `test_every_measure_has_valid_geo_standardize` still runs over `ALL_DATASETS` — external measures need a `geo_standardize: {measure_type: external}` block, added in Tasks 3-5. The functional groups (ratio/replicate/density/geo2020) don't include these datasets, so they aren't functionally tested via `standardize_all` — by design.)

- [ ] **Step 2: Run, verify the three fail completeness (assertion) and nothing else regressed:**

Run: `uv run pytest tests/test_geo_standardize_metadata.py -q`
Expected: `test_every_measure_has_valid_geo_standardize` fails for the three new datasets ("missing geo_standardize block"). The wiring test does NOT run for them (excluded). All else green.

- [ ] **Step 3: Commit:**

```bash
git add tests/test_geo_standardize_metadata.py
git commit -m "test(phase2c2): external-standardize group (manually replicated datasets)"
```

---

## Task 3: Environmental Hazard — swap convert → replicate

**Files:**
- Modify: `environment/Environmental Hazard Index (HOI)/code/distribution/ingest.py`
- Modify: `environment/Environmental Hazard Index (HOI)/data/distribution/measure_info.json`

- [ ] **Step 1: Swap the import + call.** In `ingest.py`, change the import (line 26) from:
```python
from sdc_core.geo import convert_2010_to_2020_bounds
```
to:
```python
from sdc_core.geo import replicate_2010_to_2020_bounds
```
And in the `GEO_2010_YEARS` block (ingest.py:327-331), change the call from `convert_2010_to_2020_bounds(...)` to `replicate_2010_to_2020_bounds(...)` (same args):
```python
        converted = replicate_2010_to_2020_bounds(
            year_data[["geoid", "value"]],
            geoid_col="geoid",
            val_col="value",
        )
```
(Everything else — keeping `_geo10`, the 2022-2024 already-`_geo20` path, the two `write_data` calls without `census_standardize` — is unchanged. Confirm `convert_2010_to_2020_bounds` is not referenced anywhere else in the file before removing the import.)

- [ ] **Step 2: Metadata.** In `measure_info.json`, add to the `environmental_hazard_index_geo20` object:
```json
    "geo_standardize": {"measure_type": "external"},
```
(Documents that it's standardized manually via replicate, not `standardize_all`. Keep valid JSON.)

- [ ] **Step 3: Verify:**

Run: `uv run python -c "import json; json.load(open('environment/Environmental Hazard Index (HOI)/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k "Environmental or Hazard"`
Expected: `valid`; the Environmental Hazard completeness param PASSES (external block present); it's excluded from the wiring test.
Also confirm the ingest module imports cleanly:
Run: `uv run python -c "import importlib.util; s=importlib.util.spec_from_file_location('eh','environment/Environmental Hazard Index (HOI)/code/distribution/ingest.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print('import ok')"`
Expected: `import ok` (confirms the import swap is valid).

- [ ] **Step 4: Commit:**

```bash
git add "environment/Environmental Hazard Index (HOI)/data/distribution/measure_info.json" "environment/Environmental Hazard Index (HOI)/code/distribution/ingest.py"
git commit -m "feat(environmental-hazard): replicate the PCA index to 2020 (swap convert->replicate)"
```

---

## Task 4: Walkability — swap convert → replicate (both calls)

**Files:**
- Modify: `transportation/Walkability/code/distribution/ingest.py`
- Modify: `transportation/Walkability/data/distribution/measure_info.json`

- [ ] **Step 1: Swap the import + both calls.** In `ingest.py`, change the import (line 18) from `from sdc_core.geo import convert_2010_to_2020_bounds` to `from sdc_core.geo import replicate_2010_to_2020_bounds`. In `add_geo_suffixes`, change BOTH calls (national ~line 157 and regional ~line 171) from `convert_2010_to_2020_bounds(...)` to `replicate_2010_to_2020_bounds(...)` (same args each):
```python
            converted = replicate_2010_to_2020_bounds(
                year_df[["geoid", "value"]],
            )
```
and
```python
                converted = replicate_2010_to_2020_bounds(
                    st_tracts[["geoid", "value"]],
                    state_fips=st_fips,
                )
```
(Everything else — `_geo10` original, county `_geo20`-only, block-group `_geo10`-only, `census_standardize=False` — unchanged. Confirm no other `convert_2010_to_2020_bounds` reference remains before removing the import.)

- [ ] **Step 2: Metadata.** In `measure_info.json`, add to the `walkability_index_geo20` object:
```json
    "geo_standardize": {"measure_type": "external"},
```

- [ ] **Step 3: Verify:**

Run: `uv run python -c "import json; json.load(open('transportation/Walkability/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k Walkability`
Expected: `valid`; Walkability completeness param PASSES.
Run: `uv run python -c "import importlib.util; s=importlib.util.spec_from_file_location('wk','transportation/Walkability/code/distribution/ingest.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print('import ok')"`
Expected: `import ok`.

- [ ] **Step 4: Commit:**

```bash
git add "transportation/Walkability/data/distribution/measure_info.json" "transportation/Walkability/code/distribution/ingest.py"
git commit -m "feat(walkability): replicate the rank-sum index to 2020 (swap convert->replicate)"
```

---

## Task 5: Food Accessibility — dominant-parent crosswalk + turn off spurious standardize

**Files:**
- Modify: `food/Food Access/Food Accessibility Indicator (HOI)/code/distribution/ingest.py`
- Modify: `food/Food Access/Food Accessibility Indicator (HOI)/data/distribution/measure_info.json`

Food uses its own crosswalk (`data/original/crosswalk_tracts.csv`, columns `geoid_2010`/`geoid_2020`/`arealand_part`/`arealand_2020` — the same Census relationship-file fields). Rewrite its local `convert_tracts_2010_to_2020` from area-weighting to dominant-parent replicate (keeping its crosswalk), and turn off the spurious `census_standardize=True` (the data is already 2020-vintage after the local replicate; manually emit `_geo20`).

- [ ] **Step 1: Rewrite the local crosswalk to dominant-parent.** Replace the body of `convert_tracts_2010_to_2020` (ingest.py:111-134) with a dominant-parent replicate:
```python
def convert_tracts_2010_to_2020(df: pd.DataFrame, xwalk: pd.DataFrame) -> pd.DataFrame:
    """Replicate 2010-tract values onto 2020 tracts via the area-dominant parent.

    Each 2020 tract takes the value of the 2010 tract contributing the most land
    area to it. The food-access percentage is a per-tract statistic, not an
    additive count, so it is replicated (not area-weighted) to avoid dilution.
    """
    xwalk = xwalk.copy()
    dom_idx = xwalk.groupby("geoid_2020")["arealand_part"].idxmax()
    dom = xwalk.loc[dom_idx, ["geoid_2020", "geoid_2010"]]
    result = dom.merge(df, on="geoid_2010", how="inner")
    result = result.rename(columns={"geoid_2020": "geoid"})[["geoid", "value"]]
    log.info("  Replicated %d 2010-tracts -> %d 2020-tracts", len(df), len(result))
    return result
```
(Read the file to confirm `df` has columns `geoid_2010` and `value` at the call site, matching the existing function.)

- [ ] **Step 2: Turn off spurious standardize + manually emit `_geo20`.** The final `write_data` (ingest.py:227) currently passes `census_standardize=True`, which would re-run `standardize_all` on already-2020 data (mishandling pre-2020 years and raising on the `food_access_percentage` ratio heuristic). Change it so the measure is suffixed `_geo20` directly and standardization is off. Just before the `write_data` call, set the measure name, and change the call:
```python
    long["measure"] = "food_access_percentage_geo20"
    out_path = write_data(long, DIST_DIR / f"{out_name}.csv.xz", census_standardize=False)
```
(Read the file to confirm the long frame's measure column is currently `"food_access_percentage"` and the variable is named `long`; adapt names to match. Food publishes only `_geo20` — no `_geo10` — consistent with its current measure_info.)

- [ ] **Step 3: Metadata.** In `measure_info.json`, add to the `food_access_percentage_geo20` object:
```json
    "geo_standardize": {"measure_type": "external"},
```

- [ ] **Step 4: Verify (full harness — final task):**

Run: `uv run python -c "import json; json.load(open('food/Food Access/Food Accessibility Indicator (HOI)/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v`
Expected: `valid`; the FULL harness GREEN — all prior phases + the three 2c-2 datasets (completeness via external blocks; wiring test excludes them).
Run: `uv run python -c "import importlib.util; s=importlib.util.spec_from_file_location('fa','food/Food Access/Food Accessibility Indicator (HOI)/code/distribution/ingest.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print('import ok')"`
Expected: `import ok`.
Run: `uv run pytest tests/test_geo_standardize_metadata.py packages/sdc-census10to20 packages/sdc-core -q` — all green.

- [ ] **Step 5: Commit:**

```bash
git add "food/Food Access/Food Accessibility Indicator (HOI)/data/distribution/measure_info.json" "food/Food Access/Food Accessibility Indicator (HOI)/code/distribution/ingest.py"
git commit -m "feat(food-accessibility): dominant-parent replicate + drop spurious census_standardize"
```

---

## Done criteria
- `replicate_2010_to_2020_bounds` public primitive implemented + unit-tested; `_redistribute_replicate` delegates to it (existing replicate behavior unchanged).
- Environmental Hazard and Walkability replicate their index (no area-weighting); Food Accessibility replicates (dominant parent) and no longer spuriously re-standardizes.
- Full harness green incl. the three `external`-marked datasets; primitive unit test covers the replicate logic they call.
- No data regenerated. Phase-0..2c-1 suites still green.
- **Milestone: all 24 affected datasets configured** — Phase 3 (combined regeneration) can run.

## Verification note
These three are manually standardized, so the harness can't functionally test their `_geo20` via `standardize_all`. Their correctness rests on: (1) the `replicate_2010_to_2020_bounds` unit test (the shared logic EnvHazard/Walkability call), (2) per-dataset code review of the swap (subagent-driven spec+quality review), (3) completeness confirming the `external` metadata. Food's local dominant-parent rewrite + `census_standardize=False` change is the most involved and warrants careful review.

## Follow-on
- **Phase 3** — combined regeneration (the now-unblocked remediation spec `docs/specs/2026-06-03-census10to20-remediation-design.md`) with the extended acceptance gate: counts conserve (county geo20/geo10 ≈ 1.0); ratios equal their constituent-count recompute; replicate/density/geo2020/external measures correct.
