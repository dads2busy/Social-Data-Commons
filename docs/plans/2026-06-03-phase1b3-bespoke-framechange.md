# Phase 1B-3 — Bespoke Frame Changes (Population Density, Without Health Insurance, Employment Rates) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the base-ACS frame-change datasets whose ingests need bespoke surgery: Population Density (density unit conversion + melt population count), Without Health Insurance (numerator/denominator are local variables → assign + melt helper counts), and Employment Rates (`compute_emp_rate` emits employed/civilian-labor-force helper counts for exact `emp_rate`; `labor_participate_rate` replicates).

**Architecture:** One mechanism fix — the density branch divides the standardized count by the crosswalk's `area20` (square meters), so add an optional `area_divisor` to the density spec to convert to the published area unit (persons/mi²). Everything else reuses the Phase 1B-2 melt-then-drop machinery (`input_only_measures` auto-derive): each pipeline melts its previously-dropped counts as helper measures, authors ratio/density metadata, and wires `measure_info=`. No distribution data regenerated.

**Tech Stack:** Python 3.12, pandas, pytest, uv workspace. Builds on Phase 0/1A/1B-1/1B-2.

**Scope:** Phase 1B-3 — the last three base-ACS datasets. Composites/HOIs (incl. Material Deprivation's real recompute) → Phase 2. Combined regeneration → Phase 3. After 1B-3, all 16 base-ACS datasets have correct `geo_standardize` metadata + wiring.

**Spec:** `docs/specs/2026-06-03-census10to20-intensive-measure-fix-design.md` (§4.2 ratio, §4.4 density). Branch: `fix/census10to20-data-remediation`.

---

## Per-dataset facts (from investigation)

- **`demographics/Population Density`** — `population_density` = `total_pop / land_area_sqmi` (ingest.py:171), `total_pop` dropped before write; `SQ_METERS_PER_SQ_MILE = 2_589_988.11` (ingest.py:30). measure_info key: `population_density_geo20`. Standardizes ingest.py:187-191 (`census_standardize=standardize`). The crosswalk `area20` is land area in **m²**; the published unit is **persons/mi²** → needs `area_divisor = 2589988.11`.
- **`health/System Usage and Insurance/Without Health Insurance`** — `compute_measures` (ingest.py:28-47): `total = total_19_34 + total_35_64`, `uninsured = uninsured_19_34 + uninsured_35_64` (LOCAL vars); `no_hlth_ins_pct = 100*uninsured/total`; `hlth_ins_pct = 100 - no_hlth_ins_pct`; melt `measure_cols = ["no_hlth_ins_pct", "hlth_ins_pct"]`. measure_info keys are PLAIN: `no_hlth_ins_pct`, `hlth_ins_pct`. Standardizes ingest.py:77-81 (`census_standardize=standardize`).
- **`financial_well_being/Employment Rates`** — two sources. `compute_emp_rate` (ingest.py): `emp_rate = employed/civilian_lf*100` (both columns). `compute_labor_rate`: passes through precomputed `labor_participate_rate` (S2301). measure_info keys: `emp_rate_geo20`, `labor_participate_rate_geo20`. Both sources write via the shared `run_source` → `write_data(..., census_standardize=True)` (ingest.py:100-105).

Helper counts (melted in, auto-dropped): `population_count`; `no_hlth_ins_count`, `hlth_ins_count`, `hlth_ins_total_count`; `emp_employed_count`, `emp_civilian_lf_count`.

---

## File Structure

- **Modify** `packages/sdc-census10to20/src/sdc_census10to20/convert.py` — `_redistribute_density` + density dispatch gain `area_divisor` (default 1.0).
- **Modify** `tests/test_geo_standardize_metadata.py` — add `DENSITY_DATASETS` group + density test; add WHI + Employment Rates to `EXACT_RATIO_FRAMECHANGE_DATASETS`; add Employment Rates to `REPLICATE_DATASETS`; dedupe `ALL_DATASETS`.
- **Modify** 3× `measure_info.json` + 3× `ingest.py`.
- **Test** `packages/sdc-census10to20/tests/test_convert.py`.

---

## Task 1: Density `area_divisor` (unit conversion)

**Files:**
- Modify: `packages/sdc-census10to20/src/sdc_census10to20/convert.py`
- Test: `packages/sdc-census10to20/tests/test_convert.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_convert.py`):

```python
def test_standardize_all_density_applies_area_divisor(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    # In fake_crosswalk, area_part == area20 and area10 == 1000, so for pop == 1000
    # count_geo20 / area20 == 1.0 per child; with area_divisor=10 the density is 10.0.
    data = pd.DataFrame({
        "geoid":       ["51001000020", "51001000020"],
        "year":        [2018, 2018],
        "measure":     ["pop_count", "pop_density"],
        "value":       [1000.0, 1.0],
        "moe":         [pd.NA, pd.NA],
        "region_type": ["tract", "tract"],
    })
    mi = {
        "pop_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "pop_density_geo20": {"geo_standardize": {
            "measure_type": "density", "count": "pop_count", "area_divisor": 10.0,
        }},
    }
    out = convert.standardize_all(data, measure_info=mi)
    dens = out[out["measure"] == "pop_density_geo20"].set_index("geoid")["value"]
    assert dens["51001000002"] == pytest.approx(10.0)
    assert dens["51001000003"] == pytest.approx(10.0)
```

- [ ] **Step 2: Run, verify FAIL** (area_divisor not applied → density is 1.0, not 10.0):

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_standardize_all_density_applies_area_divisor -v`

- [ ] **Step 3: Implement.** In `convert.py`, change `_redistribute_density`'s signature and the division:

```python
def _redistribute_density(count_slice, *, geoid_col, value_col, state_fips, area_divisor=1.0):
    """density_geo20 = count_geo20 / (area20 / area_divisor).

    ``area20`` from the crosswalk is land area in the relationship file's units
    (square meters). ``area_divisor`` converts to the published area unit
    (e.g. 2_589_988.11 m²/mi² → persons per square mile). Default 1.0 leaves
    ``area20`` units unchanged.
    """
    count20 = convert_2010_to_2020_bounds(
        count_slice, geoid_col=geoid_col, val_col=value_col, state_fips=state_fips,
    )
    geoids = list(count_slice[geoid_col].astype(str).unique())
    xwalk = create_crosswalk(geoids, state_fips=state_fips)
    area20 = (
        xwalk.drop_duplicates("geoid20")[["geoid20", "area20"]]
        .rename(columns={"geoid20": "geoid"})
    )
    m = count20.merge(area20, on="geoid")
    m[value_col] = m[value_col] / (m["area20"] / area_divisor)
    return m[["geoid", value_col]]
```

And in the density dispatch branch, pass `area_divisor` from the spec (default 1.0). Change the `_redistribute_density(...)` call to:

```python
                        converted = _redistribute_density(
                            c_slice, geoid_col=geoid_col, value_col=value_col,
                            state_fips=state_fips,
                            area_divisor=spec.get("area_divisor", 1.0),
                        )
```

- [ ] **Step 4: Run the new test + full file, verify all pass:**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py -v`
(The Phase-0 density test `test_standardize_all_density_recomputed_from_count_and_area20` must still pass — it has no `area_divisor`, so the default 1.0 leaves `count/area20` unchanged.)

- [ ] **Step 5: Commit:**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/tests/test_convert.py
git commit -m "feat(census10to20): density area_divisor for published area-unit conversion"
```

---

## Task 2: Harness — density group + frame-change/replicate additions

**Files:**
- Modify: `tests/test_geo_standardize_metadata.py`

- [ ] **Step 1: Edit group constants.**

Append to `EXACT_RATIO_FRAMECHANGE_DATASETS` (Without Health Insurance and Employment Rates have ratio measures recomputed from melted helper counts):

```python
EXACT_RATIO_FRAMECHANGE_DATASETS = [
    "demographics/Veteran",
    "demographics/Language",
    "education/Postsecondary",
    "health/System Usage and Insurance/Without Health Insurance",
    "financial_well_being/Employment Rates",
]
```

Append to `REPLICATE_DATASETS` (Employment Rates' `labor_participate_rate` replicates):

```python
REPLICATE_DATASETS = [
    "financial_well_being/Household Income",
    "education/Years of Schooling",
    "financial_well_being/Income Inequality",
    "transportation/Population Characteristics",
    "demographics/Cooperative extension",
    "financial_well_being/Employment Rates",
]
```

Add a density group after `EXACT_RATIO_FRAMECHANGE_DATASETS`:

```python
# Density measures recomputed as count_geo20 / (area20 / area_divisor); the count
# is melted into the frame as a helper and dropped from output.
DENSITY_DATASETS = ["demographics/Population Density"]
```

Change `ALL_DATASETS` to a de-duplicated union (Employment Rates appears in two groups):

```python
ALL_DATASETS = list(dict.fromkeys(
    EXACT_RATIO_DATASETS
    + REPLICATE_DATASETS
    + INDEX_SKIP_DATASETS
    + EXACT_RATIO_FRAMECHANGE_DATASETS
    + DENSITY_DATASETS
))
```

(`STANDARDIZE_FILE`'s comprehension over `ALL_DATASETS` then maps the three new datasets to `code/distribution/ingest.py` automatically — they all standardize in ingest.)

- [ ] **Step 2: Add the density test** (after `test_framechange_ratios_recompute_and_drop_helpers`):

```python
@pytest.mark.parametrize("dataset", DENSITY_DATASETS)
def test_density_recompute_and_drop_helper(dataset, monkeypatch, split_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: split_crosswalk)
    mi = _measure_info(dataset)
    specs = parse_geo_standardize_info(mi)
    helpers = convert.referenced_helper_measures(mi)
    assert helpers, f"{dataset}: expected a helper (input-only) count for density"
    dens = {b: s for b, s in specs.items() if s.get("measure_type") == "density"}
    assert dens, f"{dataset}: no density measures"

    counts = {s["count"] for s in dens.values()}
    # pop == area10 (1000 in the fixture) so count_geo20/area20 == 1.0 per child;
    # then density == area_divisor.
    measure_values = {c: 1000.0 for c in counts}
    measure_values.update({b: 0.0 for b in dens})
    data = _synthetic_frame("51001000020", measure_values)

    out = convert.standardize_all(data, measure_info=mi)  # auto-derives input_only
    out_measures = set(out["measure"])
    for base, spec in dens.items():
        ad = spec.get("area_divisor", 1.0)
        got = out[out["measure"] == f"{base}_geo20"].set_index("geoid")["value"]
        assert got["51001000002"] == pytest.approx(ad), f"{dataset}:{base} A"
        assert got["51001000003"] == pytest.approx(ad), f"{dataset}:{base} B"
    for h in helpers:
        assert f"{h}_geo20" not in out_measures, f"{dataset}: helper {h} leaked _geo20"
        assert f"{h}_geo10" not in out_measures, f"{dataset}: helper {h} leaked _geo10"
```

- [ ] **Step 3: Run, verify prior-green stay green and the 3 new datasets fail:**

Run: `uv run pytest tests/test_geo_standardize_metadata.py -v`
Expected: all previously-green params still pass. The new datasets fail with assertion errors — completeness ("missing geo_standardize block"), the frame-change test for WHI & Employment Rates ("expected helper ... counts"), the density test for Population Density ("expected a helper ... count"), the replicate test for Employment Rates ("no replicate/median/mean measures"), and wiring ("not passing measure_info="). Assertion failures, not import errors.

- [ ] **Step 4: Commit:**

```bash
git add tests/test_geo_standardize_metadata.py
git commit -m "test(phase1b3): density group + add WHI/Employment Rates to frame-change & replicate"
```

---

## Task 3: Population Density — melt population count + density metadata + wiring

**Files:**
- Modify: `demographics/Population Density/code/distribution/ingest.py`
- Modify: `demographics/Population Density/data/distribution/measure_info.json`

- [ ] **Step 1: Emit the helper population count.** In `ingest.py` `run_source`, replace the block that builds `result` from `pop` (the lines computing `pop["value"]`, `pop["measure"]`, `pop["moe"]`, then `result = pop[[...]]` and the dropna) with one that emits both the density and a `population_count` helper:

```python
        density = pop[["geoid", "year", "region_type"]].copy()
        density["measure"] = "population_density"
        density["value"] = pop["total_pop"] / pop["land_area_sqmi"]
        density["moe"] = pd.NA

        popcount = pop[["geoid", "year", "region_type"]].copy()
        popcount["measure"] = "population_count"
        popcount["value"] = pop["total_pop"]
        popcount["moe"] = pd.NA

        result = pd.concat([density, popcount], ignore_index=True)
        result = result[["geoid", "year", "measure", "value", "moe", "region_type"]]
        result = result.dropna(subset=["value"])
```

(Read the file to match exact surrounding code/indentation. `pd` is already imported.)

- [ ] **Step 2: Metadata.** In `measure_info.json`, add to `population_density_geo20`:

```json
    "geo_standardize": {"measure_type": "density", "count": "population_count", "area_divisor": 2589988.11},
```

(Do NOT add a `population_count` entry — it stays unpublished, auto-derived as input-only and dropped. `area_divisor` matches the ingest's `SQ_METERS_PER_SQ_MILE = 2_589_988.11`.)

- [ ] **Step 3: Wiring.** In `ingest.py`, add `MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"` after the `TOPIC_DIR = ...` line, and add `measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,` to the write_data call (ingest.py:187-191). Read the file to match exact text.

- [ ] **Step 4: Verify:**

Run: `uv run python -c "import json; json.load(open('demographics/Population Density/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k Density`
Expected: `valid`; Population Density params PASS — completeness, `test_density_recompute_and_drop_helper` (density == area_divisor; `population_count` dropped), wiring.

- [ ] **Step 5: Commit:**

```bash
git add "demographics/Population Density/data/distribution/measure_info.json" "demographics/Population Density/code/distribution/ingest.py"
git commit -m "feat(population-density): density metadata (area_divisor) + melt population_count + wiring"
```

---

## Task 4: Without Health Insurance — assign+melt helper counts + ratio metadata + wiring

**Files:**
- Modify: `health/System Usage and Insurance/Without Health Insurance/code/distribution/ingest.py`
- Modify: `health/System Usage and Insurance/Without Health Insurance/data/distribution/measure_info.json`

- [ ] **Step 1: Assign + melt helper counts.** In `ingest.py` `compute_measures`, after the line `df["hlth_ins_pct"] = 100 - df["no_hlth_ins_pct"]`, add the three helper count columns, and extend `measure_cols`:

```python
    df["no_hlth_ins_count"] = uninsured
    df["hlth_ins_count"] = total - uninsured
    df["hlth_ins_total_count"] = total

    id_cols = ["geoid", "year", "region_type"]
    measure_cols = [
        "no_hlth_ins_pct", "hlth_ins_pct",
        "no_hlth_ins_count", "hlth_ins_count", "hlth_ins_total_count",
    ]
```

(`total` and `uninsured` are the existing local variables. The rest of `compute_measures` — the `melt`, `long["moe"] = pd.NA`, `dropna` — is unchanged.)

- [ ] **Step 2: Metadata.** In `measure_info.json` (keys are PLAIN, no `_geo20` suffix), add to each percent object:
- `no_hlth_ins_pct` → `"geo_standardize": {"measure_type": "ratio", "numerator": "no_hlth_ins_count", "denominator": "hlth_ins_total_count", "scale": 100},`
- `hlth_ins_pct` → `"geo_standardize": {"measure_type": "ratio", "numerator": "hlth_ins_count", "denominator": "hlth_ins_total_count", "scale": 100},`

(Do NOT add entries for the three helper counts — they stay unpublished, auto-derived as input-only, dropped.)

- [ ] **Step 3: Wiring.** In `ingest.py`, add `MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"` after the `TOPIC_DIR = ...` line, and add `measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,` to the write_data call (ingest.py:77-81). Read the file to match exact text.

- [ ] **Step 4: Verify:**

Run: `uv run python -c "import json; json.load(open('health/System Usage and Insurance/Without Health Insurance/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k "Insurance"`
Expected: `valid`; Without Health Insurance params PASS — completeness (both plain keys), `test_framechange_ratios_recompute_and_drop_helpers` (both percents → parent ratio; all 3 helper counts dropped), wiring.

- [ ] **Step 5: Commit:**

```bash
git add "health/System Usage and Insurance/Without Health Insurance/data/distribution/measure_info.json" "health/System Usage and Insurance/Without Health Insurance/code/distribution/ingest.py"
git commit -m "feat(without-health-insurance): exact-ratio metadata + assign/melt helper counts + wiring"
```

---

## Task 5: Employment Rates — emit emp_rate helper counts + ratio/replicate metadata + wiring

**Files:**
- Modify: `financial_well_being/Employment Rates/code/distribution/ingest.py`
- Modify: `financial_well_being/Employment Rates/data/distribution/measure_info.json`

- [ ] **Step 1: Emit helper counts from `compute_emp_rate`.** Replace `compute_emp_rate` with a version that emits `emp_rate` plus the two count measures:

```python
def compute_emp_rate(df: pd.DataFrame) -> pd.DataFrame:
    mask = df["civilian_lf"].gt(0) & df["civilian_lf"].notna()
    df = df[mask].copy()
    id_cols = ["geoid", "year", "region_type"]
    parts = []
    for measure, val in [
        ("emp_rate", (df["employed"] / df["civilian_lf"] * 100).round(4)),
        ("emp_employed_count", df["employed"]),
        ("emp_civilian_lf_count", df["civilian_lf"]),
    ]:
        part = df[id_cols].copy()
        part["measure"] = measure
        part["value"] = val
        part["moe"] = pd.NA
        parts.append(part)
    return pd.concat(parts, ignore_index=True)
```

(`compute_labor_rate` is unchanged — `labor_participate_rate` replicates.)

- [ ] **Step 2: Metadata.** In `measure_info.json`:
- `emp_rate_geo20` → `"geo_standardize": {"measure_type": "ratio", "numerator": "emp_employed_count", "denominator": "emp_civilian_lf_count", "scale": 100},`
- `labor_participate_rate_geo20` → `"geo_standardize": {"measure_type": "replicate"},`

(Do NOT add entries for the two helper counts — they auto-derive as input-only and drop.)

- [ ] **Step 3: Wiring.** In `ingest.py`, add `MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"` after the `TOPIC_DIR = ...` line, and add `measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,` to the shared `run_source` write_data call (ingest.py:100-105). Read the file to match exact text. (One change covers both the emp and labor sources, which share `run_source`.)

- [ ] **Step 4: Verify:**

Run: `uv run python -c "import json; json.load(open('financial_well_being/Employment Rates/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v`
Expected: `valid`; the FULL harness is GREEN — Phase 1A + 1B-1 + 1B-2 + the three 1B-3 datasets. For Employment Rates: completeness (both measures), `test_framechange_ratios_recompute_and_drop_helpers` (`emp_rate` → parent ratio; the 2 helper counts dropped), AND `test_replicate_measures_take_parent_value` (`labor_participate_rate` → parent value).

- [ ] **Step 5: Commit:**

```bash
git add "financial_well_being/Employment Rates/data/distribution/measure_info.json" "financial_well_being/Employment Rates/code/distribution/ingest.py"
git commit -m "feat(employment-rates): emp_rate exact-ratio (emit helper counts) + labor replicate + wiring"
```

---

## Done criteria
- Density `area_divisor` implemented + tested (Phase-0 density default-1.0 behavior preserved).
- Full harness green incl. the 3 new datasets: Population Density (density == area_divisor, `population_count` dropped); Without Health Insurance (both percents → parent ratio, 3 helpers dropped); Employment Rates (`emp_rate` → parent ratio + 2 helpers dropped, `labor_participate_rate` → parent value).
- No data regenerated; published measure sets unchanged. Phase-0/1A/1B-1/1B-2 suites still green: `uv run pytest tests/test_geo_standardize_metadata.py packages/sdc-census10to20 packages/sdc-core -q`.
- **Milestone:** all 16 base-ACS datasets now carry correct `geo_standardize` metadata + wiring.

## Follow-on (separate plans)
1. **Phase 2** — composite-index recompute-from-standardized-inputs: Material Deprivation (its prepare computes a Townsend z-score index; recompute on 2020 boundaries from standardized inputs instead of `interpolate:false` placeholder) + the 8 HOI/index datasets (Environmental Hazard, Food Accessibility, Incarceration, Geographic Mobility, Segregation, Employment Access, Walkability, Affordability) — verify each computes its index from standardized inputs, not by interpolating the index. Start with EnvHazard `ingest.py:327`.
2. **Phase 3** — combined regeneration (now-unblocked remediation spec) with the extended acceptance gate (county geo20/geo10 ≈ 1.0 for counts; ratio/replicate/density correctness; index recomputed).
