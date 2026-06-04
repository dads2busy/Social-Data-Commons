# Phase 2b — 2020-Native Passthrough (Incarceration, Employment Access) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the spurious redistribution of two datasets whose data is already on 2020 boundaries for all years — `public_safety/Incarceration (HOI)` (PPI 2020 tracts) and `financial_well_being/Employment Access Index` (TIGER2020 geometry). Their pre-2020-year sub-county rows are currently mis-treated by `standardize_all` as 2010-vintage and area-converted; they must instead pass through as `_geo20` unchanged (no `_geo10`, no conversion).

**Architecture:** Add a `geo2020` measure_type to `standardize_all`: a measure declared `geo2020` is emitted as `_geo20` for **all** rows (its data is already 2020-vintage), with no `_geo10` and no `convert_2010_to_2020_bounds` call. Both pipelines keep `census_standardize=True` and just gain `measure_info` wiring + a `geo2020` block — staying on the standard metadata-driven pattern. No per-pipeline measure-relabeling.

**Tech Stack:** Python 3.12, pandas, pytest, uv workspace. Builds on Phases 0/1/2a.

**Scope:** Phase 2b — the two 2020-native datasets. Other Phase-2 sub-plans: 2a (Geographic Mobility ratio) done; 2c (replicate indices: Environmental Hazard, Segregation, Walkability, Affordability, Material Deprivation, Food Accessibility).

**Spec:** `docs/specs/2026-06-03-census10to20-intensive-measure-fix-design.md`. Branch: `fix/census10to20-data-remediation`.

---

## Facts (from investigation)

- **`public_safety/Incarceration (HOI)`** — measure `incarceration_rate_per_100000` (key `incarceration_rate_per_100000_geo20`, `measure_type:"rate"`, no geo_standardize). Geographies tract/county/health_district; years **2016-2023** (pre-2020 present). PPI data uses **2020 census tracts natively**. Standardizes ingest.py:192: `write_data(combined, DIST_DIR / f"{out_name}.csv.xz", census_standardize=True)`.
- **`financial_well_being/Employment Access Index`** — measure `employment_access_index` (key `employment_access_index_geo20`, `measure_type:"index"`, no geo_standardize). Geographies tract/county; years **2015-2023** (pre-2020 present). Built on **TIGER2020** geometry (2020 geoids). Standardizes ingest.py:434: `write_data(combined, WORKING_DIR / filename, census_standardize=True)`; prepare reads working → distribution with no further `census_standardize`.

Both have pre-2020-year sub-county rows carrying **2020 geoids**, which `standardize_all` (with no metadata) currently mis-classifies and tries to area-convert. The fix makes them pass through as `_geo20`.

---

## File Structure
- **Modify** `packages/sdc-census10to20/src/sdc_census10to20/convert.py` — add `geo2020` handling to `standardize_all`.
- **Modify** `tests/test_geo_standardize_metadata.py` — `geo2020` in `VALID_TYPES`; `GEO2020_DATASETS` group + test; add the two datasets.
- **Modify** 2× `measure_info.json` + 2× `ingest.py`.
- **Test** `packages/sdc-census10to20/tests/test_convert.py`.

---

## Task 1: `geo2020` measure_type in `standardize_all`

**Files:**
- Modify: `packages/sdc-census10to20/src/sdc_census10to20/convert.py`
- Test: `packages/sdc-census10to20/tests/test_convert.py`

A `geo2020` measure is already 2020-vintage: emit it as `_geo20` for every row (no `_geo10`), and skip it in the conversion loop. Current relevant code: the input_only block ends at convert.py:333; the `original` suffix block is convert.py:335-343; the per-measure loop skip is convert.py:351-352.

- [ ] **Step 1: Write the failing test** (append to `tests/test_convert.py`):

```python
def test_standardize_all_geo2020_passes_through_without_conversion(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    # A pre-2020 sub-county row of a 2020-native measure must emit _geo20 unchanged
    # (no _geo10, no split into children).
    data = pd.DataFrame({
        "geoid": ["51001000020"], "year": [2018], "measure": ["my_rate"],
        "value": [42.0], "moe": [pd.NA], "region_type": ["tract"],
    })
    mi = {"my_rate_geo20": {"geo_standardize": {"measure_type": "geo2020"}}}
    out = convert.standardize_all(data, measure_info=mi)
    measures = set(out["measure"])
    assert "my_rate_geo20" in measures
    assert "my_rate_geo10" not in measures
    g20 = out[out["measure"] == "my_rate_geo20"]
    assert set(g20["geoid"]) == {"51001000020"}          # unchanged, NOT split into children
    assert g20["value"].iloc[0] == pytest.approx(42.0)
```

- [ ] **Step 2: Run, verify FAIL** (currently the pre-2020 sub-county row becomes `my_rate_geo10` + area-converted children):

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_standardize_all_geo2020_passes_through_without_conversion -v`

- [ ] **Step 3: Implement.**

(a) After the `input_only` resolution block (convert.py:333, the line `input_only = set()`), add a `native_2020` set:

```python
    native_2020 = {
        b for b, s in specs.items() if s.get("measure_type") == "geo2020"
    }
```

(b) Replace the `original` suffix block (convert.py:335-343) so `geo2020` measures are always suffixed `_geo20`:

```python
    original = data[~data[measure_col].isin(input_only)].copy()
    original[measure_col] = original.apply(
        lambda row: (
            f"{row[measure_col]}_geo20"
            if row[measure_col] in native_2020
            else (
                f"{row[measure_col]}_geo10"
                if row[year_col] < 2020 and len(row[geoid_col]) in _SUB_COUNTY_LENGTHS
                else f"{row[measure_col]}_geo20"
            )
        ),
        axis=1,
    )
```

(c) In the per-measure loop, skip `geo2020` measures (they emit no converted rows — the original block already produced their `_geo20`). Change the existing skip (convert.py:350-352):

```python
                # Helper (input-only) and geo2020-native measures emit no converted rows.
                if meas in input_only or meas in native_2020:
                    continue
```

- [ ] **Step 4: Run the new test + full file, verify all pass:**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py -v`
(All prior tests stay green — `geo2020` is opt-in via metadata; no existing measure declares it.)

- [ ] **Step 5: Commit:**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/tests/test_convert.py
git commit -m "feat(census10to20): geo2020 measure_type (already-2020 passthrough, no conversion)"
```

---

## Task 2: Harness — `geo2020` group + valid type + add the two datasets

**Files:**
- Modify: `tests/test_geo_standardize_metadata.py`

- [ ] **Step 1: Edit the harness.**

Add `"geo2020"` to `VALID_TYPES`:
```python
VALID_TYPES = {"count", "ratio", "rate", "median", "mean", "replicate", "density", "index", "external", "geo2020"}
```

Add a group after `EXACT_RATIO_FRAMECHANGE_DATASETS` (or near the other group lists):
```python
# Data already on 2020 boundaries for all years (PPI 2020 tracts, TIGER2020) —
# pass through as _geo20, no conversion.
GEO2020_DATASETS = [
    "public_safety/Incarceration (HOI)",
    "financial_well_being/Employment Access Index",
]
```

Add `GEO2020_DATASETS` to the `ALL_DATASETS` de-duplicated union:
```python
ALL_DATASETS = list(dict.fromkeys(
    EXACT_RATIO_DATASETS
    + REPLICATE_DATASETS
    + INDEX_SKIP_DATASETS
    + EXACT_RATIO_FRAMECHANGE_DATASETS
    + DENSITY_DATASETS
    + GEO2020_DATASETS
))
```

(`STANDARDIZE_FILE`'s comprehension maps both to `code/distribution/ingest.py` — correct: both standardize in ingest, even though Employment Access writes to WORKING_DIR.)

- [ ] **Step 2: Add the geo2020 test** (after the density test):

```python
@pytest.mark.parametrize("dataset", GEO2020_DATASETS)
def test_geo2020_measures_pass_through_as_geo20(dataset, monkeypatch, split_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: split_crosswalk)
    mi = _measure_info(dataset)
    specs = parse_geo_standardize_info(mi)
    native = sorted(b for b, s in specs.items() if s.get("measure_type") == "geo2020")
    assert native, f"{dataset}: no geo2020 measures"
    values = {b: 10.0 * (i + 1) for i, b in enumerate(native)}
    data = _synthetic_frame("51001000020", values)  # pre-2020 sub-county row
    out = convert.standardize_all(data, measure_info=mi)
    out_measures = set(out["measure"])
    for base in native:
        assert f"{base}_geo20" in out_measures, f"{dataset}: {base}_geo20 missing"
        assert f"{base}_geo10" not in out_measures, f"{dataset}: {base} should not emit _geo10"
        g20 = out[out["measure"] == f"{base}_geo20"]
        assert set(g20["geoid"]) == {"51001000020"}, f"{dataset}: {base} geoid changed (was converted)"
        assert g20["value"].iloc[0] == pytest.approx(values[base])
```

- [ ] **Step 3: Run, verify prior-green stay green and the two new datasets fail (assertion):**

Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k "Incarceration or Employment Access"`
Expected: both datasets FAIL — `test_every_measure_has_valid_geo_standardize` ("missing geo_standardize block"), `test_geo2020_measures_pass_through_as_geo20` ("no geo2020 measures"), `test_standardize_call_wires_measure_info` ("not passing measure_info=").
Then: `uv run pytest tests/test_geo_standardize_metadata.py -q` — only the new failures.

- [ ] **Step 4: Commit:**

```bash
git add tests/test_geo_standardize_metadata.py
git commit -m "test(phase2b): geo2020 group + add Incarceration & Employment Access"
```

---

## Task 3: Incarceration — geo2020 metadata + ingest wiring

**Files:**
- Modify: `public_safety/Incarceration (HOI)/data/distribution/measure_info.json`
- Modify: `public_safety/Incarceration (HOI)/code/distribution/ingest.py`

- [ ] **Step 1: Metadata.** In `measure_info.json`, add to the `incarceration_rate_per_100000_geo20` object:

```json
    "geo_standardize": {"measure_type": "geo2020"},
```

(Leave the existing `"measure_type": "rate"` descriptive field unchanged — `geo_standardize.measure_type` is what drives `standardize_all`. Don't modify other fields. Keep valid JSON.)

- [ ] **Step 2: Wiring.** In `ingest.py`, add `MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"` after the `TOPIC_DIR = ...` line (convert.py:27 region), and change the write_data call (ingest.py:192) to pass measure_info:

```python
        out_path = write_data(
            combined,
            DIST_DIR / f"{out_name}.csv.xz",
            census_standardize=True,
            measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,
        )
```

(Read the file to match exact existing call text/indentation — it is currently a single-line call; expand it.)

- [ ] **Step 3: Verify:**

Run: `uv run python -c "import json; json.load(open('public_safety/Incarceration (HOI)/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k Incarceration`
Expected: `valid`; Incarceration params PASS — completeness, `test_geo2020_measures_pass_through_as_geo20` (rate passes through as `_geo20`, no `_geo10`, no conversion), wiring.

- [ ] **Step 4: Commit:**

```bash
git add "public_safety/Incarceration (HOI)/data/distribution/measure_info.json" "public_safety/Incarceration (HOI)/code/distribution/ingest.py"
git commit -m "feat(incarceration): geo2020 passthrough metadata + ingest wiring"
```

---

## Task 4: Employment Access — geo2020 metadata + ingest wiring

**Files:**
- Modify: `financial_well_being/Employment Access Index/data/distribution/measure_info.json`
- Modify: `financial_well_being/Employment Access Index/code/distribution/ingest.py`

- [ ] **Step 1: Metadata.** In `measure_info.json`, add to the `employment_access_index_geo20` object:

```json
    "geo_standardize": {"measure_type": "geo2020"},
```

(Leave the existing `"measure_type": "index"` descriptive field unchanged. Keep valid JSON.)

- [ ] **Step 2: Wiring.** In `ingest.py`, add `MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"` after the `TOPIC_DIR = ...` line, and change the write_data call (ingest.py:434-435) to pass measure_info:

```python
            out_path = write_data(
                combined,
                WORKING_DIR / filename,
                census_standardize=True,
                measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,
            )
```

(Read the file to match exact text/indentation. The measure_info.json lives in `data/distribution/` even though this call writes to `WORKING_DIR` — that's correct, the metadata is the published one. prepare.py later reads the working file and carries `employment_access_index_geo20` to distribution unchanged.)

- [ ] **Step 3: Verify (full harness — final task):**

Run: `uv run python -c "import json; json.load(open('financial_well_being/Employment Access Index/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v`
Expected: `valid`; the FULL harness is GREEN — Phase 1 + 2a + both 2b datasets. For Employment Access: completeness, `test_geo2020_measures_pass_through_as_geo20`, wiring.

- [ ] **Step 4: Commit:**

```bash
git add "financial_well_being/Employment Access Index/data/distribution/measure_info.json" "financial_well_being/Employment Access Index/code/distribution/ingest.py"
git commit -m "feat(employment-access): geo2020 passthrough metadata + ingest wiring"
```

---

## Done criteria
- `geo2020` measure_type implemented + tested: a 2020-native measure emits `_geo20` for all rows (value unchanged at the original geoid), no `_geo10`, no conversion.
- Full harness green incl. Incarceration and Employment Access passing through as `_geo20`.
- No data regenerated. Phase-0/1/2a suites still green: `uv run pytest tests/test_geo_standardize_metadata.py packages/sdc-census10to20 packages/sdc-core -q`.

## Follow-on (separate plans)
1. **Phase 2c** — replicate indices: Environmental Hazard (PCA), Segregation (entropy), Walkability (rank-sum), Affordability (regression), Material Deprivation (flip 1B-1 `interpolate:false` → `replicate`), Food Accessibility (currently a local area-weighted crosswalk on a %). Route each index through `standardize_all` with a `replicate` spec, removing the current index-interpolation / direct-`convert` / local-crosswalk paths.
2. **Phase 3** — combined regeneration with the extended acceptance gate.
