# Phase 1B-2 — Frame-Change Exact Ratios (Veteran, Language, Postsecondary) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable exact `_geo20` percent recompute for datasets whose denominator count is computed in-ingest but dropped before the melt, by (a) melting the denominator back into the standardization frame as a helper count, (b) recomputing the ratio from numerator/denominator counts, and (c) dropping those helper counts from the published output — for Veteran, Language, and Postsecondary.

**Architecture:** Add a small `input_only_measures` capability to `standardize_all`: measures listed there (or auto-derived from `measure_info` as referenced-but-unpublished counts) are kept in the frame for ratio/density recompute but excluded from the standardized output (and skip the heuristic warning). A `referenced_helper_measures(measure_info)` helper derives that set. `write_data` forwards the param. Then each pipeline melts its denominator as a prefixed helper count and authors a ratio spec; the existing `measure_info=` wiring (same as Phase 1A) triggers auto-derive, so the helper count is used and dropped automatically.

**Tech Stack:** Python 3.12, pandas, pytest, uv workspace. Builds on Phase 0/1A/1B-1.

**Scope:** Phase 1B-2 — the three clean single-column-melt ratio datasets. Deferred to Phase 1B-3: Population Density (density-unit conversion: crosswalk `area20` is m², published unit is persons/mi²), Without Health Insurance (numerator/denominator are local variables, not columns), Employment Rates (per-source `compute_emp_rate` restructure + `labor_participate_rate` replicate). Composites → Phase 2. Regeneration → Phase 3.

**Decision banked (user):** melt-for-standardization, drop-before-publish (preserve the published measure set). Implemented via the `input_only_measures`/auto-derive mechanism.

**Spec:** `docs/specs/2026-06-03-census10to20-intensive-measure-fix-design.md` (§4.2 exact ratio). Branch: `fix/census10to20-data-remediation`.

---

## Per-dataset facts (from investigation)

| Dataset | measure_info keys | percent → numerator / denominator (denominator dropped before melt) | melt pattern | standardize call |
|---|---|---|---|---|
| `demographics/Veteran` | `veteran_count_geo20`, `veteran_percent_geo20` | `veteran` / `vet_denom` (B21001_001 civilian 18+) | `[c for c in df.columns if c.startswith("veteran_")]` | ingest.py:72-76 `census_standardize=standardize` |
| `demographics/Language` | `language_hh_limited_english_count_geo20`, `language_hh_limited_english_percent_geo20` | `hh_limited_english` / `total_hh` (C16002_001 households) | `startswith("language_")` | ingest.py:82-86 `census_standardize=standardize` |
| `education/Postsecondary` | `acs_postsecondary_count_geo20`, `acs_postsecondary_percent_geo20` | `count` / `df["total"]` (population) | explicit row-loop | ingest.py:114-118 `census_standardize=True` |

Helper count names (melted in, dropped from output): `veteran_denom_count`, `language_total_hh_count`, `acs_postsecondary_denom_count`.

---

## File Structure

- **Modify** `packages/sdc-census10to20/src/sdc_census10to20/convert.py` — add `referenced_helper_measures()`; add `input_only_measures` param + auto-derive to `standardize_all`.
- **Modify** `packages/sdc-census10to20/src/sdc_census10to20/__init__.py` — export `referenced_helper_measures`.
- **Modify** `packages/sdc-core/src/sdc_core/io.py` — `write_data` gains `input_only_measures` (forwarded).
- **Modify** `tests/test_geo_standardize_metadata.py` — add `EXACT_RATIO_FRAMECHANGE_DATASETS` group + a recompute-and-drop test.
- **Modify** 3× `measure_info.json` (Veteran, Language, Postsecondary) — count + ratio blocks.
- **Modify** 3× `ingest.py` — melt the helper denominator count + wire `measure_info=`.
- **Test** `packages/sdc-census10to20/tests/test_convert.py`, `packages/sdc-core/tests/test_io.py`.

---

## Task 1: `referenced_helper_measures` helper

**Files:**
- Modify: `packages/sdc-census10to20/src/sdc_census10to20/convert.py`, `.../__init__.py`
- Test: `packages/sdc-census10to20/tests/test_convert.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_convert.py`):

```python
def test_referenced_helper_measures_derives_unpublished_referenced_counts():
    from sdc_census10to20 import referenced_helper_measures
    mi = {
        "sub_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "sub_pct_geo20": {"geo_standardize": {
            "measure_type": "ratio", "numerator": "sub_count",
            "denominator": "denom_count", "scale": 100,
        }},
    }
    # sub_count is published (its own measure); denom_count is referenced but not published.
    assert referenced_helper_measures(mi) == {"denom_count"}
    # No ratios / all-published -> empty set.
    assert referenced_helper_measures({"x_geo20": {"geo_standardize": {"measure_type": "count"}}}) == set()
```

- [ ] **Step 2: Run, verify FAIL** with `ImportError: cannot import name 'referenced_helper_measures'`:

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_referenced_helper_measures_derives_unpublished_referenced_counts -v`

- [ ] **Step 3: Implement.** In `convert.py`, add after `parse_geo_standardize_info`:

```python
def referenced_helper_measures(measure_info) -> set[str]:
    """Base measure names referenced as numerator/denominator/count/weight by some
    geo_standardize spec but NOT themselves published measures.

    These are melted into the standardization frame only to recompute ratios or
    density; they are excluded from the standardized output (see
    ``standardize_all``'s ``input_only_measures``).
    """
    specs = parse_geo_standardize_info(measure_info)
    published = set(specs)
    referenced: set[str] = set()
    for spec in specs.values():
        for field in ("numerator", "denominator", "count", "weight"):
            ref = spec.get(field)
            if ref:
                referenced.add(ref)
    return referenced - published
```

In `packages/sdc-census10to20/src/sdc_census10to20/__init__.py`, add `referenced_helper_measures` to the import from `.convert` and to `__all__` (alongside `parse_geo_standardize_info`).

- [ ] **Step 4: Run, verify PASS:**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_referenced_helper_measures_derives_unpublished_referenced_counts -v`
Run: `cd packages/sdc-census10to20 && uv run python -c "from sdc_census10to20 import referenced_helper_measures; print('ok')"`

- [ ] **Step 5: Commit:**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/src/sdc_census10to20/__init__.py packages/sdc-census10to20/tests/test_convert.py
git commit -m "feat(census10to20): referenced_helper_measures (referenced-but-unpublished counts)"
```

---

## Task 2: `input_only_measures` + auto-derive in `standardize_all`

**Files:**
- Modify: `packages/sdc-census10to20/src/sdc_census10to20/convert.py`
- Test: `packages/sdc-census10to20/tests/test_convert.py`

Measures in `input_only_measures` are kept in the input frame (so the ratio/density branch can fetch their slices) but their own `_geo10`/`_geo20` rows are NOT emitted, and they skip the heuristic warning. When `input_only_measures is None` and `measure_info` is given, the set auto-derives via `referenced_helper_measures`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_convert.py`):

```python
def test_standardize_all_auto_drops_helper_counts_but_recomputes_ratio(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    # parent .020 splits .002/.003. numerator sub_count=300, denominator denom_count=1000.
    data = pd.DataFrame({
        "geoid":       ["51001000020", "51001000020", "51001000020"],
        "year":        [2018, 2018, 2018],
        "measure":     ["sub_count", "denom_count", "sub_pct"],
        "value":       [300.0, 1000.0, 30.0],
        "moe":         [pd.NA, pd.NA, pd.NA],
        "region_type": ["tract", "tract", "tract"],
    })
    mi = {
        "sub_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "sub_pct_geo20": {"geo_standardize": {
            "measure_type": "ratio", "numerator": "sub_count",
            "denominator": "denom_count", "scale": 100,
        }},
    }
    # denom_count is referenced but unpublished -> auto-derived as input-only.
    out = convert.standardize_all(data, measure_info=mi)
    m = set(out["measure"])
    pct = out[out["measure"] == "sub_pct_geo20"].set_index("geoid")["value"]
    assert pct["51001000002"] == pytest.approx(30.0)
    assert pct["51001000003"] == pytest.approx(30.0)
    assert "sub_count_geo20" in m            # published count still emitted
    assert "denom_count_geo20" not in m      # helper not emitted
    assert "denom_count_geo10" not in m      # helper not emitted (original suppressed)


def test_standardize_all_explicit_input_only_overrides(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)
    data = pd.DataFrame({
        "geoid": ["51001000020"], "year": [2018], "measure": ["pop"],
        "value": [500.0], "moe": [pd.NA], "region_type": ["tract"],
    })
    mi = {"pop_geo20": {"geo_standardize": {"measure_type": "count"}}}
    # Explicitly mark pop input-only -> its _geo20 must NOT be emitted.
    out = convert.standardize_all(data, measure_info=mi, input_only_measures={"pop"})
    assert "pop_geo20" not in set(out["measure"])
    assert "pop_geo10" not in set(out["measure"])
```

- [ ] **Step 2: Run, verify FAIL** (helper currently emitted; `input_only_measures` kwarg unknown):

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py -k "auto_drops_helper or explicit_input_only" -v`

- [ ] **Step 3: Implement.** Change the `standardize_all` signature to add `input_only_measures=None` immediately after `measure_info=None`:

```python
def standardize_all(
    data: pd.DataFrame,
    *,
    measure_info=None,
    input_only_measures=None,
    filter_geo: str = "state",
    geoid_col: str = "geoid",
    measure_col: str = "measure",
    year_col: str = "year",
    value_col: str = "value",
    moe_col: str = "moe",
    region_type_col: str = "region_type",
    state_fips: str = "51",
) -> pd.DataFrame:
```

After the existing `specs = parse_geo_standardize_info(...)` line, add the input-only resolution:

```python
    if input_only_measures is not None:
        input_only = set(input_only_measures)
    elif measure_info is not None:
        input_only = referenced_helper_measures(measure_info)
    else:
        input_only = set()
```

Change the `original` construction to exclude input-only measures. Find the line `original = data.copy()` and replace with:

```python
    original = data[~data[measure_col].isin(input_only)].copy()
```

In the standardized-parts loop, skip input-only measures. Find `for meas in measures:` and add immediately inside it (before the `for geoid_len` loop):

```python
                if meas in input_only:
                    continue
```

(The ratio/density branches still fetch their numerator/denominator/count slices from the unfiltered `data`, so recompute is unaffected; only the helper's own emission and heuristic warning are suppressed.)

- [ ] **Step 4: Run the two new tests + full file, verify all pass:**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py -v`
(All prior tests must remain green — for Age/Race/Gender-style frames every measure is published, so `referenced_helper_measures` returns an empty set and nothing is dropped.)

- [ ] **Step 5: Commit:**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/tests/test_convert.py
git commit -m "feat(census10to20): input_only_measures (auto-derived) drop helper counts from output"
```

---

## Task 3: `write_data` forwards `input_only_measures`

**Files:**
- Modify: `packages/sdc-core/src/sdc_core/io.py`
- Test: `packages/sdc-core/tests/test_io.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_io.py`):

```python
def test_write_data_forwards_input_only_measures(monkeypatch, tmp_path):
    captured = {}

    def fake_standardize_all(df, *, measure_info=None, input_only_measures=None, **kw):
        captured["input_only_measures"] = input_only_measures
        return df

    import sdc_core.io as io
    monkeypatch.setattr(io, "standardize_all", fake_standardize_all)

    df = pd.DataFrame({
        "geoid": ["51001000020"], "year": [2018], "measure": ["pop"],
        "value": [1.0], "moe": [pd.NA], "region_type": ["tract"],
    })
    write_data(df, tmp_path / "out.csv", census_standardize=True,
               measure_info={"pop_geo20": {}}, input_only_measures={"denom"})
    assert captured["input_only_measures"] == {"denom"}
```

- [ ] **Step 2: Run, verify FAIL** with `TypeError: write_data() got an unexpected keyword argument 'input_only_measures'`:

Run: `cd packages/sdc-core && uv run pytest tests/test_io.py::test_write_data_forwards_input_only_measures -v`

- [ ] **Step 3: Implement.** In `io.py`, add `input_only_measures=None` to `write_data`'s signature (after `measure_info=None`), and update the standardize call:

```python
    if census_standardize:
        df = standardize_all(df, measure_info=measure_info, input_only_measures=input_only_measures)
```

- [ ] **Step 4: Run, verify PASS + full sdc-core suite:**

Run: `cd packages/sdc-core && uv run pytest tests/ -v`

- [ ] **Step 5: Commit:**

```bash
git add packages/sdc-core/src/sdc_core/io.py packages/sdc-core/tests/test_io.py
git commit -m "feat(sdc-core): write_data forwards input_only_measures to standardize_all"
```

---

## Task 4: Harness — frame-change ratio group (recompute + drop helpers)

**Files:**
- Modify: `tests/test_geo_standardize_metadata.py`

- [ ] **Step 1: Edit the harness.** Add the new group constant after `INDEX_SKIP_DATASETS`:

```python
# Percents recompute exactly from a denominator melted into the frame as a helper
# count (dropped from output via input_only auto-derive).
EXACT_RATIO_FRAMECHANGE_DATASETS = [
    "demographics/Veteran",
    "demographics/Language",
    "education/Postsecondary",
]
```

Update `ALL_DATASETS`:

```python
ALL_DATASETS = (
    EXACT_RATIO_DATASETS
    + REPLICATE_DATASETS
    + INDEX_SKIP_DATASETS
    + EXACT_RATIO_FRAMECHANGE_DATASETS
)
```

(The `STANDARDIZE_FILE` dict comprehension over `ALL_DATASETS` already maps the new datasets to `code/distribution/ingest.py`; no edit needed there beyond ALL_DATASETS now including them.)

Add this test (after `test_index_measures_not_interpolated`):

```python
@pytest.mark.parametrize("dataset", EXACT_RATIO_FRAMECHANGE_DATASETS)
def test_framechange_ratios_recompute_and_drop_helpers(dataset, monkeypatch, split_crosswalk):
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: split_crosswalk)
    mi = _measure_info(dataset)
    specs = parse_geo_standardize_info(mi)
    helpers = convert.referenced_helper_measures(mi)
    assert helpers, f"{dataset}: expected helper (input-only) counts referenced by ratios"
    ratios = {b: s for b, s in specs.items() if s.get("measure_type") in ("ratio", "rate")}
    assert ratios, f"{dataset}: no ratio measures"

    counts = set()
    for s in ratios.values():
        counts.add(s["numerator"])
        counts.add(s["denominator"])
    values = {c: 100.0 * (i + 1) for i, c in enumerate(sorted(counts))}
    measure_values = dict(values)
    measure_values.update({b: 0.0 for b in ratios})  # ratio input recomputed
    data = _synthetic_frame("51001000020", measure_values)

    out = convert.standardize_all(data, measure_info=mi)  # auto-derives input_only
    out_measures = set(out["measure"])
    for base, spec in ratios.items():
        expected = spec["scale"] * values[spec["numerator"]] / values[spec["denominator"]]
        got = out[out["measure"] == f"{base}_geo20"].set_index("geoid")["value"]
        assert got["51001000002"] == pytest.approx(expected), f"{dataset}:{base} A"
        assert got["51001000003"] == pytest.approx(expected), f"{dataset}:{base} B"
    for h in helpers:
        assert f"{h}_geo20" not in out_measures, f"{dataset}: helper {h} leaked _geo20"
        assert f"{h}_geo10" not in out_measures, f"{dataset}: helper {h} leaked _geo10"
```

- [ ] **Step 2: Run, verify Phase 1A/1B-1 stay green and the 3 frame-change datasets fail:**

Run: `uv run pytest tests/test_geo_standardize_metadata.py -v`
Expected: all previously-green params still pass; the new `EXACT_RATIO_FRAMECHANGE` datasets fail — `test_every_measure_has_valid_geo_standardize` ("missing geo_standardize block"), `test_framechange_ratios_recompute_and_drop_helpers` ("expected helper ... counts" — `referenced_helper_measures` is empty until ratio specs are authored), and `test_standardize_call_wires_measure_info` ("not passing measure_info="). Assertion failures, not import errors.

- [ ] **Step 3: Commit:**

```bash
git add tests/test_geo_standardize_metadata.py
git commit -m "test(phase1b2): frame-change exact-ratio harness group (recompute + drop helpers)"
```

---

## Task 5: Veteran — melt denom count + ratio metadata + wiring

**Files:**
- Modify: `demographics/Veteran/code/distribution/ingest.py`
- Modify: `demographics/Veteran/data/distribution/measure_info.json`

- [ ] **Step 1: Melt the helper denominator.** In `ingest.py` `compute_measures`, after the line `df["veteran_count"] = df["veteran"]`, add:

```python
    df["veteran_denom_count"] = df["vet_denom"]
```

(This is captured by the existing `measure_cols = [c for c in df.columns if c.startswith("veteran_")]`, so it melts as the measure `veteran_denom_count`.)

- [ ] **Step 2: Metadata.** In `measure_info.json` add `geo_standardize` blocks:
- `veteran_count_geo20` → `"geo_standardize": {"measure_type": "count"},`
- `veteran_percent_geo20` → `"geo_standardize": {"measure_type": "ratio", "numerator": "veteran_count", "denominator": "veteran_denom_count", "scale": 100},`

(Do not add a `veteran_denom_count` entry — it stays unpublished, so it auto-derives as input-only and is dropped.)

- [ ] **Step 3: Wiring.** In `ingest.py`, add `MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"` after the `TOPIC_DIR = ...` line, and change the write_data call (lines 72-76):

```python
        out_path = write_data(
            result,
            out_dir / filename,
            census_standardize=standardize,
            measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,
        )
```

(Read the file to match the exact existing call text/indentation. `input_only` is auto-derived inside `standardize_all` from `measure_info`, so no extra kwarg is needed.)

- [ ] **Step 4: Verify:**

Run: `uv run python -c "import json; json.load(open('demographics/Veteran/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k Veteran`
Expected: `valid`; Veteran params PASS — `test_every_measure_has_valid_geo_standardize`, `test_framechange_ratios_recompute_and_drop_helpers` (veteran_percent → parent ratio; `veteran_denom_count` dropped), `test_standardize_call_wires_measure_info`.

- [ ] **Step 5: Commit:**

```bash
git add "demographics/Veteran/data/distribution/measure_info.json" "demographics/Veteran/code/distribution/ingest.py"
git commit -m "feat(veteran): exact-ratio metadata + melt denom helper count + wiring"
```

---

## Task 6: Language — melt total_hh count + ratio metadata + wiring

**Files:**
- Modify: `demographics/Language/code/distribution/ingest.py`
- Modify: `demographics/Language/data/distribution/measure_info.json`

- [ ] **Step 1: Melt the helper denominator.** In `ingest.py` `compute_measures`, after the line `df["language_hh_limited_english_count"] = df["hh_limited_english"]`, add:

```python
    df["language_total_hh_count"] = df["total_hh"]
```

(Captured by the existing `measure_cols = [c for c in df.columns if c.startswith("language_")]`.)

- [ ] **Step 2: Metadata.** In `measure_info.json`:
- `language_hh_limited_english_count_geo20` → `"geo_standardize": {"measure_type": "count"},`
- `language_hh_limited_english_percent_geo20` → `"geo_standardize": {"measure_type": "ratio", "numerator": "language_hh_limited_english_count", "denominator": "language_total_hh_count", "scale": 100},`

- [ ] **Step 3: Wiring.** Add `MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"` after `TOPIC_DIR = ...`, and add `measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,` to the write_data call (lines 82-86). Read the file to match exact text.

- [ ] **Step 4: Verify:**

Run: `uv run python -c "import json; json.load(open('demographics/Language/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v -k Language`
Expected: `valid`; Language params PASS.

- [ ] **Step 5: Commit:**

```bash
git add "demographics/Language/data/distribution/measure_info.json" "demographics/Language/code/distribution/ingest.py"
git commit -m "feat(language): exact-ratio metadata + melt total_hh helper count + wiring"
```

---

## Task 7: Postsecondary — emit denom count + ratio metadata + wiring

**Files:**
- Modify: `education/Postsecondary/code/distribution/ingest.py`
- Modify: `education/Postsecondary/data/distribution/measure_info.json`

- [ ] **Step 1: Emit the helper denominator.** In `ingest.py` `compute_measures`, the long frame is built by a row-loop over a list of `(measure, val, moe)` tuples. Add a third entry for the denominator (total population) so it melts as a measure:

```python
    for measure, val, moe in [
        ("acs_postsecondary_count", count, moe_count),
        ("acs_postsecondary_percent", pct, moe_pct),
        ("acs_postsecondary_denom_count", df["total"],
         df.get("total_moe", pd.Series(0, index=df.index))),
    ]:
```

(`val.round(4)` / `moe.round(4)` already applied in the loop body work on these Series.)

- [ ] **Step 2: Metadata.** In `measure_info.json`:
- `acs_postsecondary_count_geo20` → `"geo_standardize": {"measure_type": "count"},`
- `acs_postsecondary_percent_geo20` → `"geo_standardize": {"measure_type": "ratio", "numerator": "acs_postsecondary_count", "denominator": "acs_postsecondary_denom_count", "scale": 100},`

- [ ] **Step 3: Wiring.** Add `MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"` after `TOPIC_DIR = ...` (note: `DIST_DIR` already exists; place `MEASURE_INFO` near it), and change the write_data call (lines 114-118, `census_standardize=True`) to add `measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,`. Read the file to match exact text.

- [ ] **Step 4: Verify:**

Run: `uv run python -c "import json; json.load(open('education/Postsecondary/data/distribution/measure_info.json')); print('valid')"`
Run: `uv run pytest tests/test_geo_standardize_metadata.py -v`
Expected: `valid`; the FULL harness is green — Age/Race/Gender + the 1B-1 datasets + Veteran/Language/Postsecondary (completeness, frame-change recompute+drop, wiring).

- [ ] **Step 5: Commit:**

```bash
git add "education/Postsecondary/data/distribution/measure_info.json" "education/Postsecondary/code/distribution/ingest.py"
git commit -m "feat(postsecondary): exact-ratio metadata + emit denom helper count + wiring"
```

---

## Done criteria
- `referenced_helper_measures` + `input_only_measures` (auto-derived) implemented and tested; `write_data` forwards.
- Full harness green incl. the 3 frame-change datasets: each percent recomputes to the parent ratio AND the helper denominator count does not appear (no `_geo10`/`_geo20`) in output.
- No data regenerated; published measure set unchanged (helpers dropped). Phase-0/1A/1B-1 suites still green: `uv run pytest tests/test_geo_standardize_metadata.py packages/sdc-census10to20 packages/sdc-core -q`.

## Follow-on (separate plans)
1. **Phase 1B-3** — bespoke frame changes: Population Density (add density area-unit handling: convert crosswalk `area20` m² to the published unit, or carry a divisor), Without Health Insurance (assign the local `uninsured`/`total` vars to melted helper counts), Employment Rates (`compute_emp_rate` emits `employed`/`civilian_lf` helper counts for exact `emp_rate`; `labor_participate_rate` → replicate).
2. **Phase 2** — composite-index recompute-from-standardized-inputs (Material Deprivation + 8 HOI/index datasets).
3. **Phase 3** — combined regeneration with the extended acceptance gate.
