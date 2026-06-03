# Intensive-Measure Standardization Mechanism — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `sdc_census10to20.standardize_all` interpolate each measure according to its type (count / ratio / rate / median / mean / density / index) driven by `measure_info.json` metadata, so intensive `_geo20` values are correct instead of area-diluted.

**Architecture:** All per-type logic lives in `sdc_census10to20/convert.py` as small helpers that reuse the existing `convert_2010_to_2020_bounds` primitive and `create_crosswalk`. `standardize_all` gains a `measure_info` parameter and dispatches per (year, measure, geoid-length) slice. `sdc_core.io.write_data` threads a `measure_info` argument through. No data is regenerated in this plan — it delivers and tests the mechanism only.

**Tech Stack:** Python 3.12, pandas, pytest, uv workspace. Packages: `packages/sdc-census10to20` (core logic + tests), `packages/sdc-core` (`write_data` threading).

**Scope:** Phase 0 of `docs/specs/2026-06-03-census10to20-intensive-measure-fix-design.md`. Per-dataset `measure_info` authoring, composite-index recompute verification, and the combined regeneration are follow-on plans.

---

## File Structure

- **Modify** `packages/sdc-census10to20/src/sdc_census10to20/convert.py`
  - Add `parse_geo_standardize_info()`, `_classify_by_name()`, and per-type redistribution helpers.
  - Rewrite `standardize_all`'s standardized-parts loop to dispatch by measure type.
  - `convert_2010_to_2020_bounds` is unchanged.
- **Modify** `packages/sdc-core/src/sdc_core/io.py`
  - `write_data` gains `measure_info=None`, passed to `standardize_all`.
- **Modify** `packages/sdc-census10to20/tests/test_convert.py`
  - Add tests for parsing, each measure type, fallback, errors, and a mixed-frame integration test.

The existing `fake_crosswalk` fixture (test_convert.py:11–35) is reused throughout. Its shape:

| geoid20 | geoid10 | area20 | area10 | area_part | type_change |
|---|---|---|---|---|---|
| 51001000001 | 51001000010 | 1000 | 1000 | 1000 | same |
| 51001000002 | 51001000020 | 600 | 1000 | 600 | split |
| 51001000003 | 51001000020 | 400 | 1000 | 400 | split |
| 51001000004 | 51001000030 | 600 | 1000 | 400 | moved |
| 51001000005 | 51001000030 | 600 | 1000 | 400 | moved |

So parent `51001000020` splits into children `…002` (area 600/1000) and `…003` (area 400/1000).

---

## Task 1: `parse_geo_standardize_info` — normalize metadata to base measure names

**Files:**
- Modify: `packages/sdc-census10to20/src/sdc_census10to20/convert.py`
- Test: `packages/sdc-census10to20/tests/test_convert.py`

`measure_info.json` keys are suffixed (`age_under_20_percent_geo20`); the frame carries base names (`age_under_20_percent`). This helper strips the suffix and extracts each measure's `geo_standardize` block, accepting either a dict or a path.

- [ ] **Step 1: Write the failing test**

```python
def test_parse_geo_standardize_info_strips_suffix_and_extracts_block():
    from sdc_census10to20 import convert
    mi = {
        "_references": {"ignored": True},
        "age_under_20_percent_geo20": {
            "label": "Under 20",
            "geo_standardize": {
                "measure_type": "ratio",
                "numerator": "age_under_20_count",
                "denominator": "age_total_count",
                "scale": 100,
            },
        },
        "age_total_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "no_block_geo20": {"label": "no geo_standardize here"},
    }
    specs = convert.parse_geo_standardize_info(mi)
    assert specs["age_under_20_percent"]["measure_type"] == "ratio"
    assert specs["age_under_20_percent"]["numerator"] == "age_under_20_count"
    assert specs["age_total_count"]["measure_type"] == "count"
    assert "no_block" not in specs          # no geo_standardize block
    assert "_references" not in specs        # underscore keys skipped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_parse_geo_standardize_info_strips_suffix_and_extracts_block -v`
Expected: FAIL with `AttributeError: module 'sdc_census10to20.convert' has no attribute 'parse_geo_standardize_info'`

- [ ] **Step 3: Write minimal implementation**

Add near the top of `convert.py` (after the existing imports add `import json`, `import re`, `from pathlib import Path`):

```python
_GEO_SUFFIX_RE = re.compile(r"_(geo10|geo20)$")


def _strip_geo_suffix(name: str) -> str:
    return _GEO_SUFFIX_RE.sub("", name)


def parse_geo_standardize_info(measure_info) -> dict[str, dict]:
    """Map base measure name -> its geo_standardize spec.

    ``measure_info`` may be a dict (already-loaded measure_info.json) or a path
    to a measure_info.json file. Keys are suffixed (``..._geo20``); we strip the
    suffix so lookups match the base measure names carried in the data frame.
    Entries without a ``geo_standardize`` block, and underscore-prefixed keys
    (e.g. ``_references``), are skipped.
    """
    if isinstance(measure_info, (str, Path)):
        with open(measure_info) as f:
            measure_info = json.load(f)
    specs: dict[str, dict] = {}
    for key, val in measure_info.items():
        if key.startswith("_") or not isinstance(val, dict):
            continue
        block = val.get("geo_standardize")
        if block:
            specs[_strip_geo_suffix(key)] = block
    return specs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_parse_geo_standardize_info_strips_suffix_and_extracts_block -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/tests/test_convert.py
git commit -m "feat(census10to20): parse geo_standardize metadata from measure_info"
```

---

## Task 2: Add `measure_info` param to `standardize_all`, routing all measures through count behavior by default

**Files:**
- Modify: `packages/sdc-census10to20/src/sdc_census10to20/convert.py:90-171`
- Test: `packages/sdc-census10to20/tests/test_convert.py`

This task adds the parameter and a per-slice dispatch shell that, for now, only knows the `count` path (area-weighted via `convert_2010_to_2020_bounds`). Default `measure_info=None` and the heuristic must classify the existing `"pop"` test measure as a count so all existing tests still pass.

- [ ] **Step 1: Write the failing test**

```python
def test_standardize_all_accepts_measure_info_and_keeps_count_behavior(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({
        "geoid": ["51001000020"],
        "year": [2018],
        "measure": ["pop"],
        "value": [500.0],
        "moe": [pd.NA],
        "region_type": ["tract"],
    })
    mi = {"pop_geo20": {"geo_standardize": {"measure_type": "count"}}}
    out = convert.standardize_all(data, measure_info=mi)

    geo20 = out[out["measure"] == "pop_geo20"].set_index("geoid")["value"]
    # split by area_part/area10: child .002 = 300, child .003 = 200
    assert geo20["51001000002"] == pytest.approx(300.0)
    assert geo20["51001000003"] == pytest.approx(200.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_standardize_all_accepts_measure_info_and_keeps_count_behavior -v`
Expected: FAIL with `TypeError: standardize_all() got an unexpected keyword argument 'measure_info'`

- [ ] **Step 3: Write minimal implementation**

Add a name heuristic helper and a dispatcher; modify `standardize_all`'s signature and its inner loop. First add helpers (place after `parse_geo_standardize_info`):

```python
_COUNT_HINTS = ("count", "_pop", "population", "households", "total")
_INTENSIVE_HINTS = (
    "percent", "_pct", "rate", "median", "mean", "average", "avg",
    "index", "score", "gini", "density", "ratio", "frac",
)


def _classify_by_name(measure: str) -> str:
    """Fallback classification when no geo_standardize metadata is provided."""
    m = measure.lower()
    if "density" in m:
        return "density"
    if "median" in m:
        return "median"
    if any(h in m for h in ("mean", "average", "avg")):
        return "mean"
    if any(h in m for h in _INTENSIVE_HINTS):
        return "ratio"
    if any(h in m for h in _COUNT_HINTS):
        return "count"
    return "count"  # safest default: behaves as today (area-weighted)
```

Then change the signature (line 90) to add `measure_info=None` as the first keyword-only arg:

```python
def standardize_all(
    data: pd.DataFrame,
    *,
    measure_info=None,
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

Inside `standardize_all`, before the `for yr in years` loop, build the spec map:

```python
    specs = parse_geo_standardize_info(measure_info) if measure_info is not None else {}
```

Replace the inner body that currently calls `convert_2010_to_2020_bounds` directly (lines ~143-154) with a dispatch that, for this task, handles only `count`:

```python
                    spec = specs.get(meas)
                    mtype = spec["measure_type"] if spec else _classify_by_name(meas)

                    if mtype == "count":
                        converted = convert_2010_to_2020_bounds(
                            temp, geoid_col=geoid_col, val_col=value_col,
                            state_fips=state_fips,
                        )
                    else:
                        raise NotImplementedError(
                            f"measure_type {mtype!r} not yet handled (measure {meas!r})"
                        )

                    converted[year_col] = yr
                    converted[measure_col] = f"{meas}_geo20"
                    converted[moe_col] = pd.NA
                    if region_type_col in data.columns:
                        converted[region_type_col] = _GEOID_LEN_TO_REGION_TYPE[geoid_len]
                    standardized_parts.append(converted)
```

- [ ] **Step 4: Run the full existing suite + new test to verify all pass**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py -v`
Expected: PASS for all (existing `pop`-based tests classify as count via heuristic; new test passes)

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/tests/test_convert.py
git commit -m "feat(census10to20): standardize_all measure_info param + count dispatch"
```

---

## Task 3: Ratio (exact) — recompute from standardized numerator/denominator counts

**Files:**
- Modify: `packages/sdc-census10to20/src/sdc_census10to20/convert.py`
- Test: `packages/sdc-census10to20/tests/test_convert.py`

A `ratio`/`rate` with declared `numerator`+`denominator` present in the frame is recomputed as `scale · num_geo20 / denom_geo20`. This yields the parent ratio on every split child (the `30% → 30%` property).

- [ ] **Step 1: Write the failing test**

```python
def test_standardize_all_ratio_exact_recomputes_from_counts(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    # Parent .020 splits into .002/.003. Under-20=300, total=1000 -> 30% everywhere.
    data = pd.DataFrame({
        "geoid":       ["51001000020", "51001000020", "51001000020"],
        "year":        [2018, 2018, 2018],
        "measure":     ["under20_count", "total_count", "under20_percent"],
        "value":       [300.0, 1000.0, 30.0],
        "moe":         [pd.NA, pd.NA, pd.NA],
        "region_type": ["tract", "tract", "tract"],
    })
    mi = {
        "under20_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "total_count_geo20":   {"geo_standardize": {"measure_type": "count"}},
        "under20_percent_geo20": {"geo_standardize": {
            "measure_type": "ratio",
            "numerator": "under20_count",
            "denominator": "total_count",
            "scale": 100,
        }},
    }
    out = convert.standardize_all(data, measure_info=mi)
    pct = out[out["measure"] == "under20_percent_geo20"].set_index("geoid")["value"]
    assert pct["51001000002"] == pytest.approx(30.0)
    assert pct["51001000003"] == pytest.approx(30.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_standardize_all_ratio_exact_recomputes_from_counts -v`
Expected: FAIL with `NotImplementedError: measure_type 'ratio' not yet handled`

- [ ] **Step 3: Write minimal implementation**

Add the helper:

```python
def _redistribute_ratio_exact(
    num_slice, denom_slice, scale, *, geoid_col, value_col, state_fips,
):
    """ratio_geo20 = scale * numerator_geo20 / denominator_geo20."""
    num = convert_2010_to_2020_bounds(
        num_slice, geoid_col=geoid_col, val_col=value_col, state_fips=state_fips,
    )
    den = convert_2010_to_2020_bounds(
        denom_slice, geoid_col=geoid_col, val_col=value_col, state_fips=state_fips,
    )
    m = num.merge(den, on="geoid", suffixes=("_num", "_den"))
    m[value_col] = scale * m[f"{value_col}_num"] / m[f"{value_col}_den"]
    return m[["geoid", value_col]]
```

Add a small slice helper (used by the ratio/density tasks). The frame inside
`standardize_all` has already been reduced to columns
`[geoid, measure, year, value, moe(, region_type)]` (convert.py:113-116), so
`value_col` is present:

```python
def _measure_slice(data, yr, geoid_len, meas, *, year_col, geoid_col, measure_col, value_col):
    s = data[
        (data[year_col] == yr)
        & (data[measure_col] == meas)
        & (data[geoid_col].str.len() == geoid_len)
    ]
    return s[[geoid_col, value_col]].copy()
```

In the dispatch, add the `ratio`/`rate` branch before the `else: raise`:

```python
                    elif mtype in ("ratio", "rate"):
                        if spec and spec.get("numerator") and spec.get("denominator"):
                            num_slice = _measure_slice(
                                data, yr, geoid_len, spec["numerator"],
                                year_col=year_col, geoid_col=geoid_col,
                                measure_col=measure_col, value_col=value_col,
                            )
                            den_slice = _measure_slice(
                                data, yr, geoid_len, spec["denominator"],
                                year_col=year_col, geoid_col=geoid_col,
                                measure_col=measure_col, value_col=value_col,
                            )
                            if num_slice.empty or den_slice.empty:
                                raise ValueError(
                                    f"ratio {meas!r}: numerator/denominator "
                                    f"counts missing from frame for year {yr}"
                                )
                            converted = _redistribute_ratio_exact(
                                num_slice, den_slice, spec.get("scale", 100),
                                geoid_col=geoid_col, value_col=value_col,
                                state_fips=state_fips,
                            )
                        else:
                            raise NotImplementedError(
                                "population-weighted ratio handled in Task 4"
                            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_standardize_all_ratio_exact_recomputes_from_counts -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/tests/test_convert.py
git commit -m "feat(census10to20): ratio _geo20 recomputed exactly from standardized counts"
```

---

## Task 4: Ratio (population-weighted) — for measures whose counts aren't in the frame

**Files:**
- Modify: `packages/sdc-census10to20/src/sdc_census10to20/convert.py`
- Test: `packages/sdc-census10to20/tests/test_convert.py`

When only a `weight` count is declared, compute the population-weighted average of parent values: `Σ(value·weight·areafrac) / Σ(weight·areafrac)`, implemented as `convert(value*weight) / convert(weight)`. Exact for pure splits; count-weighted average for merges.

- [ ] **Step 1: Write the failing test**

```python
def test_standardize_all_ratio_population_weighted_split_is_exact(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    # Pure split parent .020 at 42% with weight (pop) 1000 -> each child 42%.
    data = pd.DataFrame({
        "geoid":       ["51001000020", "51001000020"],
        "year":        [2018, 2018],
        "measure":     ["uninsured_pct", "total_population"],
        "value":       [42.0, 1000.0],
        "moe":         [pd.NA, pd.NA],
        "region_type": ["tract", "tract"],
    })
    mi = {
        "total_population_geo20": {"geo_standardize": {"measure_type": "count"}},
        "uninsured_pct_geo20": {"geo_standardize": {
            "measure_type": "ratio", "weight": "total_population",
        }},
    }
    out = convert.standardize_all(data, measure_info=mi)
    pct = out[out["measure"] == "uninsured_pct_geo20"].set_index("geoid")["value"]
    assert pct["51001000002"] == pytest.approx(42.0)
    assert pct["51001000003"] == pytest.approx(42.0)


def test_standardize_all_ratio_population_weighted_merge_is_count_weighted(monkeypatch):
    from sdc_census10to20 import convert
    # Merge: 2020 tract M fed by two 2010 parents with different pcts + pops.
    crosswalk = pd.DataFrame({
        "geoid20":     ["51999000M", "51999000M"],
        "geoid10":     ["51999000S1", "51999000S2"],
        "area10":      [1000, 1000],
        "area20":      [2000, 2000],
        "area_part":   [1000, 1000],   # each parent fully into M
        "type_change": ["moved", "moved"],
    })
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: crosswalk)

    data = pd.DataFrame({
        "geoid":       ["51999000S1", "51999000S2", "51999000S1", "51999000S2"],
        "year":        [2018, 2018, 2018, 2018],
        "measure":     ["pct", "pct", "pop", "pop"],
        "value":       [10.0, 50.0, 300.0, 100.0],   # weighted avg = (10*300+50*100)/400 = 20
        "moe":         [pd.NA, pd.NA, pd.NA, pd.NA],
        "region_type": ["tract", "tract", "tract", "tract"],
    })
    mi = {
        "pop_geo20": {"geo_standardize": {"measure_type": "count"}},
        "pct_geo20": {"geo_standardize": {"measure_type": "ratio", "weight": "pop"}},
    }
    out = convert.standardize_all(data, measure_info=mi)
    pct = out[out["measure"] == "pct_geo20"].set_index("geoid")["value"]
    assert pct["51999000M"] == pytest.approx(20.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py -k population_weighted -v`
Expected: FAIL with `NotImplementedError: population-weighted ratio handled in Task 4`

- [ ] **Step 3: Write minimal implementation**

Add the helper:

```python
def _redistribute_ratio_weighted(
    meas_slice, weight_slice, *, geoid_col, value_col, state_fips,
):
    """Population-weighted average: convert(value*weight) / convert(weight).

    Values are already in display units (e.g. 42.0), so no scale factor.
    """
    merged = meas_slice.merge(weight_slice, on=geoid_col, suffixes=("_v", "_w"))
    merged["_vw"] = merged[f"{value_col}_v"] * merged[f"{value_col}_w"]
    vw = merged[[geoid_col, "_vw"]].rename(columns={"_vw": value_col})
    num = convert_2010_to_2020_bounds(
        vw, geoid_col=geoid_col, val_col=value_col, state_fips=state_fips,
    )
    den = convert_2010_to_2020_bounds(
        weight_slice, geoid_col=geoid_col, val_col=value_col, state_fips=state_fips,
    )
    m = num.merge(den, on="geoid", suffixes=("_num", "_den"))
    m[value_col] = m[f"{value_col}_num"] / m[f"{value_col}_den"]
    return m[["geoid", value_col]]
```

Replace the `else: raise NotImplementedError("population-weighted ratio handled in Task 4")` branch with:

```python
                        else:
                            weight = spec.get("weight") if spec else None
                            if not weight:
                                raise ValueError(
                                    f"ratio {meas!r}: declare numerator+denominator "
                                    f"or a weight in geo_standardize"
                                )
                            w_slice = _measure_slice(
                                data, yr, geoid_len, weight,
                                year_col=year_col, geoid_col=geoid_col,
                                measure_col=measure_col, value_col=value_col,
                            )
                            if w_slice.empty:
                                raise ValueError(
                                    f"ratio {meas!r}: weight {weight!r} missing "
                                    f"from frame for year {yr}"
                                )
                            converted = _redistribute_ratio_weighted(
                                temp[[geoid_col, value_col]], w_slice,
                                geoid_col=geoid_col, value_col=value_col,
                                state_fips=state_fips,
                            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py -k population_weighted -v`
Expected: PASS (both)

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/tests/test_convert.py
git commit -m "feat(census10to20): population-weighted ratio _geo20 fallback"
```

---

## Task 5: Median / mean — replicate the area-dominant parent value

**Files:**
- Modify: `packages/sdc-census10to20/src/sdc_census10to20/convert.py`
- Test: `packages/sdc-census10to20/tests/test_convert.py`

Each 2020 child takes the value of its largest-`area_part` 2010 parent.

- [ ] **Step 1: Write the failing test**

```python
def test_standardize_all_median_replicates_dominant_parent(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    # Parent .020 (median income 70000) splits into .002/.003 -> both 70000.
    data = pd.DataFrame({
        "geoid":       ["51001000020"],
        "year":        [2018],
        "measure":     ["median_income"],
        "value":       [70000.0],
        "moe":         [pd.NA],
        "region_type": ["tract"],
    })
    mi = {"median_income_geo20": {"geo_standardize": {
        "measure_type": "median", "replicate": True,
    }}}
    out = convert.standardize_all(data, measure_info=mi)
    med = out[out["measure"] == "median_income_geo20"].set_index("geoid")["value"]
    assert med["51001000002"] == pytest.approx(70000.0)
    assert med["51001000003"] == pytest.approx(70000.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_standardize_all_median_replicates_dominant_parent -v`
Expected: FAIL with `NotImplementedError: measure_type 'median' not yet handled` (from the `else: raise`)

- [ ] **Step 3: Write minimal implementation**

Add the helper:

```python
def _redistribute_replicate(meas_slice, *, geoid_col, value_col, state_fips):
    """Each 2020 child takes its area-dominant 2010 parent's value."""
    geoids = list(meas_slice[geoid_col].astype(str).unique())
    xwalk = create_crosswalk(geoids, state_fips=state_fips)
    dom_idx = xwalk.groupby("geoid20")["area_part"].idxmax()
    dom = xwalk.loc[dom_idx, ["geoid20", "geoid10"]]
    parent_vals = meas_slice.rename(columns={geoid_col: "geoid10"})[["geoid10", value_col]]
    out = dom.merge(parent_vals, on="geoid10", how="left")
    return out.rename(columns={"geoid20": "geoid"})[["geoid", value_col]]
```

Add the dispatch branch before `else: raise`:

```python
                    elif mtype in ("median", "mean"):
                        converted = _redistribute_replicate(
                            temp[[geoid_col, value_col]],
                            geoid_col=geoid_col, value_col=value_col,
                            state_fips=state_fips,
                        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_standardize_all_median_replicates_dominant_parent -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/tests/test_convert.py
git commit -m "feat(census10to20): median/mean _geo20 replicate dominant parent"
```

---

## Task 6: Density — standardized count divided by 2020 land area

**Files:**
- Modify: `packages/sdc-census10to20/src/sdc_census10to20/convert.py`
- Test: `packages/sdc-census10to20/tests/test_convert.py`

`density_geo20 = count_geo20 / area20`, where `count` is the declared extensive count and `area20` comes from the crosswalk.

- [ ] **Step 1: Write the failing test**

```python
def test_standardize_all_density_recomputed_from_count_and_area20(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    # Parent .020: population 1000 splits 600/400 into children with area20 600/400.
    # child .002: pop 600 / area20 600 = 1.0 ; child .003: pop 400 / area20 400 = 1.0
    data = pd.DataFrame({
        "geoid":       ["51001000020", "51001000020"],
        "year":        [2018, 2018],
        "measure":     ["pop_count", "pop_density"],
        "value":       [1000.0, 1.0],
        "moe":         [pd.NA, pd.NA],
        "region_type": ["tract", "tract"],
    })
    mi = {
        "pop_count_geo20":   {"geo_standardize": {"measure_type": "count"}},
        "pop_density_geo20": {"geo_standardize": {
            "measure_type": "density", "count": "pop_count",
        }},
    }
    out = convert.standardize_all(data, measure_info=mi)
    dens = out[out["measure"] == "pop_density_geo20"].set_index("geoid")["value"]
    assert dens["51001000002"] == pytest.approx(1.0)
    assert dens["51001000003"] == pytest.approx(1.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_standardize_all_density_recomputed_from_count_and_area20 -v`
Expected: FAIL with `NotImplementedError: measure_type 'density' not yet handled`

- [ ] **Step 3: Write minimal implementation**

Add the helper:

```python
def _redistribute_density(count_slice, *, geoid_col, value_col, state_fips):
    """density_geo20 = count_geo20 / area20 (2020 land area)."""
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
    m[value_col] = m[value_col] / m["area20"]
    return m[["geoid", value_col]]
```

Add the dispatch branch before `else: raise`:

```python
                    elif mtype == "density":
                        if not (spec and spec.get("count")):
                            raise ValueError(
                                f"density {meas!r}: declare 'count' in geo_standardize"
                            )
                        c_slice = _measure_slice(
                            data, yr, geoid_len, spec["count"],
                            year_col=year_col, geoid_col=geoid_col,
                            measure_col=measure_col, value_col=value_col,
                        )
                        if c_slice.empty:
                            raise ValueError(
                                f"density {meas!r}: count {spec['count']!r} missing "
                                f"from frame for year {yr}"
                            )
                        converted = _redistribute_density(
                            c_slice, geoid_col=geoid_col, value_col=value_col,
                            state_fips=state_fips,
                        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_standardize_all_density_recomputed_from_count_and_area20 -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/tests/test_convert.py
git commit -m "feat(census10to20): density _geo20 recomputed from count and area20"
```

---

## Task 7: Index — skip interpolation (recomputed downstream)

**Files:**
- Modify: `packages/sdc-census10to20/src/sdc_census10to20/convert.py`
- Test: `packages/sdc-census10to20/tests/test_convert.py`

A measure with `measure_type: index` (or `interpolate: false`) produces **no** interpolated `_geo20`; the composite pipeline computes it from standardized inputs. The original pre-2020 row still becomes `_geo10` (existing "original" passthrough).

- [ ] **Step 1: Write the failing test**

```python
def test_standardize_all_index_is_not_interpolated(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({
        "geoid":       ["51001000020"],
        "year":        [2018],
        "measure":     ["hazard_index"],
        "value":       [0.7],
        "moe":         [pd.NA],
        "region_type": ["tract"],
    })
    mi = {"hazard_index_geo20": {"geo_standardize": {
        "measure_type": "index", "interpolate": False,
    }}}
    out = convert.standardize_all(data, measure_info=mi)
    measures = set(out["measure"])
    # original pre-2020 row is suffixed _geo10; NO interpolated _geo20 emitted
    assert "hazard_index_geo10" in measures
    assert "hazard_index_geo20" not in measures
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_standardize_all_index_is_not_interpolated -v`
Expected: FAIL with `NotImplementedError: measure_type 'index' not yet handled`

- [ ] **Step 3: Write minimal implementation**

Add the dispatch branch before `else: raise`, and `continue` so nothing is appended:

```python
                    elif mtype == "index" or (spec and spec.get("interpolate") is False):
                        continue  # indices recomputed from standardized inputs downstream
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_standardize_all_index_is_not_interpolated -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/tests/test_convert.py
git commit -m "feat(census10to20): index measures skipped (recomputed downstream)"
```

---

## Task 8: Unclassified fallback warning + replace the hard `else: raise`

**Files:**
- Modify: `packages/sdc-census10to20/src/sdc_census10to20/convert.py`
- Test: `packages/sdc-census10to20/tests/test_convert.py`

Once all known types are handled, the only `else` left is an unknown `measure_type` string. A measure with **no** metadata is classified by `_classify_by_name`; emit a warning **only when `measure_info` was provided** (i.e. the caller intended coverage but missed this measure). Legacy callers passing no `measure_info` (`None`) stay silent, so existing tests are unaffected.

- [ ] **Step 1: Write the failing test**

```python
def test_standardize_all_warns_when_no_metadata_uses_heuristic(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({
        "geoid": ["51001000020"], "year": [2018], "measure": ["mystery_count"],
        "value": [500.0], "moe": [pd.NA], "region_type": ["tract"],
    })
    with pytest.warns(UserWarning, match="no geo_standardize metadata"):
        out = convert.standardize_all(data, measure_info={})  # empty -> heuristic
    # 'mystery_count' heuristically a count -> still produces a _geo20
    assert "mystery_count_geo20" in set(out["measure"])


def test_standardize_all_raises_on_unknown_measure_type(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({
        "geoid": ["51001000020"], "year": [2018], "measure": ["weird"],
        "value": [1.0], "moe": [pd.NA], "region_type": ["tract"],
    })
    mi = {"weird_geo20": {"geo_standardize": {"measure_type": "bogus"}}}
    with pytest.raises(ValueError, match="unknown measure_type"):
        convert.standardize_all(data, measure_info=mi)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py -k "warns_when_no_metadata or raises_on_unknown" -v`
Expected: FAIL (no warning emitted / `NotImplementedError` instead of `ValueError`)

- [ ] **Step 3: Write minimal implementation**

In the dispatch, after computing `spec`/`mtype`, add the heuristic warning (only when `measure_info` was provided but this measure was missing from it):

```python
                    spec = specs.get(meas)
                    if spec:
                        mtype = spec["measure_type"]
                    else:
                        mtype = _classify_by_name(meas)
                        if measure_info is not None:
                            warnings.warn(
                                f"measure {meas!r} has no geo_standardize metadata; "
                                f"falling back to name heuristic -> {mtype!r}",
                                UserWarning,
                                stacklevel=2,
                            )
```

Replace the final `else: raise NotImplementedError(...)` with:

```python
                    else:
                        raise ValueError(
                            f"unknown measure_type {mtype!r} for measure {meas!r}"
                        )
```

(`warnings` is already imported at the top of convert.py.)

- [ ] **Step 4: Run the full suite to verify all pass**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py -v`
Expected: PASS (all tasks' tests green together)

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/tests/test_convert.py
git commit -m "feat(census10to20): heuristic-fallback warning + unknown-type error"
```

---

## Task 9: Thread `measure_info` through `sdc_core.io.write_data`

**Files:**
- Modify: `packages/sdc-core/src/sdc_core/io.py:77-125`
- Test: `packages/sdc-core/tests/test_io.py` (create if absent)

`write_data` gains `measure_info=None`, passed to `standardize_all` only when `census_standardize=True`.

- [ ] **Step 1: Write the failing test**

```python
# packages/sdc-core/tests/test_io.py
import pandas as pd
from sdc_core.io import write_data


def test_write_data_passes_measure_info_to_standardize(monkeypatch, tmp_path):
    captured = {}

    def fake_standardize_all(df, *, measure_info=None, **kw):
        captured["measure_info"] = measure_info
        return df

    import sdc_core.io as io
    monkeypatch.setattr(io, "standardize_all", fake_standardize_all)

    df = pd.DataFrame({
        "geoid": ["51001000020"], "year": [2018], "measure": ["pop"],
        "value": [1.0], "moe": [pd.NA], "region_type": ["tract"],
    })
    mi = {"pop_geo20": {"geo_standardize": {"measure_type": "count"}}}
    write_data(df, tmp_path / "out.csv", census_standardize=True, measure_info=mi)
    assert captured["measure_info"] == mi
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/sdc-core && uv run pytest tests/test_io.py::test_write_data_passes_measure_info_to_standardize -v`
Expected: FAIL with `TypeError: write_data() got an unexpected keyword argument 'measure_info'`

- [ ] **Step 3: Write minimal implementation**

Edit `write_data` signature (io.py:77-84) to add `measure_info=None`:

```python
def write_data(
    df: pd.DataFrame,
    path: str | pathlib.Path,
    *,
    standardize: bool = True,
    census_standardize: bool = False,
    compress: bool = True,
    measure_info=None,
) -> pathlib.Path:
```

And change the standardize call (io.py:115-116):

```python
    if census_standardize:
        df = standardize_all(df, measure_info=measure_info)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/sdc-core && uv run pytest tests/test_io.py::test_write_data_passes_measure_info_to_standardize -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/sdc-core/src/sdc_core/io.py packages/sdc-core/tests/test_io.py
git commit -m "feat(sdc-core): write_data threads measure_info to standardize_all"
```

---

## Task 10: Integration test — mixed-type frame end-to-end

**Files:**
- Test: `packages/sdc-census10to20/tests/test_convert.py`

One frame containing a count, an exact ratio, a population-weighted ratio, a median, a density, and an index — verifying the full dispatch produces correct `_geo20` for each in a single pass.

- [ ] **Step 1: Write the failing test**

```python
def test_standardize_all_mixed_measure_types_integration(monkeypatch, fake_crosswalk):
    from sdc_census10to20 import convert
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    g = "51001000020"  # splits 600/400 into .002/.003
    rows = [
        (g, "under20_count", 300.0),
        (g, "total_count",   1000.0),
        (g, "under20_pct",   30.0),    # exact ratio -> 30 / 30
        (g, "uninsured_pct", 42.0),    # weighted ratio -> 42 / 42
        (g, "median_income", 70000.0), # replicate -> 70000 / 70000
        (g, "pop_density",   1.0),     # 600/600, 400/400 -> 1.0 / 1.0
        (g, "hazard_index",  0.7),     # skipped
    ]
    data = pd.DataFrame({
        "geoid":       [r[0] for r in rows],
        "year":        [2018] * len(rows),
        "measure":     [r[1] for r in rows],
        "value":       [r[2] for r in rows],
        "moe":         [pd.NA] * len(rows),
        "region_type": ["tract"] * len(rows),
    })
    mi = {
        "under20_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "total_count_geo20":   {"geo_standardize": {"measure_type": "count"}},
        "under20_pct_geo20":   {"geo_standardize": {"measure_type": "ratio",
            "numerator": "under20_count", "denominator": "total_count", "scale": 100}},
        "uninsured_pct_geo20": {"geo_standardize": {"measure_type": "ratio",
            "weight": "total_count"}},
        "median_income_geo20": {"geo_standardize": {"measure_type": "median"}},
        "pop_density_geo20":   {"geo_standardize": {"measure_type": "density",
            "count": "under20_count"}},  # using under20_count as the extensive count for the test
        "hazard_index_geo20":  {"geo_standardize": {"measure_type": "index",
            "interpolate": False}},
    }
    out = convert.standardize_all(data, measure_info=mi)
    g20 = out[out["measure"].str.endswith("_geo20")]
    by = lambda m: g20[g20["measure"] == m].set_index("geoid")["value"]

    assert by("under20_pct_geo20")["51001000002"] == pytest.approx(30.0)
    assert by("uninsured_pct_geo20")["51001000003"] == pytest.approx(42.0)
    assert by("median_income_geo20")["51001000002"] == pytest.approx(70000.0)
    # density uses under20_count(300) split 180/120 over area20 600/400 = 0.3/0.3
    assert by("pop_density_geo20")["51001000002"] == pytest.approx(0.3)
    assert "hazard_index_geo20" not in set(g20["measure"])
```

- [ ] **Step 2: Run test to verify it passes (all mechanism already implemented)**

Run: `cd packages/sdc-census10to20 && uv run pytest tests/test_convert.py::test_standardize_all_mixed_measure_types_integration -v`
Expected: PASS

- [ ] **Step 3: Run the entire workspace test suite**

Run: `uv run pytest packages/sdc-census10to20 packages/sdc-core -v`
Expected: PASS (no regressions in either package)

- [ ] **Step 4: Commit**

```bash
git add packages/sdc-census10to20/tests/test_convert.py
git commit -m "test(census10to20): mixed measure-type standardization integration"
```

---

## Done criteria
- `standardize_all` dispatches by measure type from `measure_info`; counts area-weighted, ratios recomputed (exact or population-weighted), medians/means replicated, density recomputed from count/area20, indices skipped.
- `write_data` threads `measure_info`.
- All existing `test_convert.py` tests still pass (count behavior unchanged when measures classify as counts).
- New tests cover every type, the heuristic-fallback warning, and the unknown-type error.

## Follow-on (separate plans)
1. **Per-dataset metadata + frames:** author `geo_standardize` blocks in each of the 24 `measure_info.json`; ensure weight/count inputs are present in each standardization frame; pass `measure_info` into `write_data`/`standardize_all`.
2. **Composite-index recompute:** verify/fix each HOI pipeline to recompute its index from standardized inputs (start with `environment/Environmental Hazard Index (HOI)` ingest.py:327).
3. **Combined regeneration:** execute `docs/specs/2026-06-03-census10to20-remediation-design.md` (now unblocked) with the extended acceptance gate.
