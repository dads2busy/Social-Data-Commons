# census10to20 Intensive-Measure Fix — Design Spec

**Date:** 2026-06-03
**Status:** approved design, pending implementation plan
**Prerequisite for:** `docs/specs/2026-06-03-census10to20-remediation-design.md`
(the count-corruption remediation is BLOCKED on this fix)
**Related:** `reference_census10to20_convert_semantics` (memory),
`docs/specs/2026-06-03-census10to20-count-conservation-fix-design.md`

## 1. Problem

`sdc_census10to20.standardize_all` area-weights **every** measure it is handed,
calling `convert_2010_to_2020_bounds` per (year, measure). Area-weighting is correct
only for **extensive** quantities (counts): a 2010 source distributes its count to
overlapping 2020 tracts by `area_part/area10`, and the weights tile the source, so
the total is conserved.

For **intensive** quantities (percent, rate, median, mean, density, composite
index), area-weighting is wrong — it distributes the *value* by area as if it were a
count. Demonstrated on real split tract `51121020300` (fixed code):

| input on parent | child 020301 | child 020302 | child 021201 | sum |
|---|---|---|---|---|
| count = 1000 | 65.4 | 934.5 | 0.1 | **1000 ✓** |
| percent = 30.0 | **1.96** | **28.0** | 0.003 | 30.0 (wrong invariant) |

The correct per-child percent is ~30% on every child (the under-20 *share* doesn't
change when you draw a boundary), recoverable as
`under20_count_geo20 / total_count_geo20`. Area-weighting instead dilutes by area
(child 020301 off by ~15×).

### Why this is urgent and coupled

These intensive `_geo20` measures are **displayed**: declared in `measure_info.json`,
pivoted into the wide dashboard files by `data_reformat_for_site` (no recompute), and
referenced in both dashboard repos. They share the **same `standardize_all` pass** as
the counts, so the count-corruption remediation cannot regenerate counts without
simultaneously shipping this percent regression — which is *worse* than the current
(pre-v0.1.2) pass-through behavior. Hence this fix is a hard prerequisite.

## 2. Measure inventory across the 24 affected datasets

Non-count `_geo20` measures, by class (drives the per-type logic in §4):

- **ratio / percent** (most demographics + Without Health Insurance, Postsecondary,
  Food Access %, Geo Mobility `perc_*`, Affordability cost %s, Broadband `perc_*`,
  Pop Characteristics `perc_*`)
- **rate** (Employment Rates: `labor_participate_rate`, `emp_rate`; Incarceration:
  `incarceration_rate_per_100000`)
- **mean** (Years of Schooling: `average_years_schooling`; Pop Characteristics:
  `commute_time`; Affordability: `autos_per_hh`, `vmt_per_hh`)
- **median** (Household Income: `median_household_income`)
- **density** (Population Density: `population_density`)
- **composite index** (Income Inequality `gini_index`; EnvHazard; Employment Access;
  Walkability; Segregation; Material Deprivation; Affordability `affordability_index`)

Some datasets publish **only** the intensive measure, not its constituent counts.

## 3. Metadata: `measure_info.json` extension

Each measure gains an optional `geo_standardize` block. Absent → name-heuristic
fallback + warning (§4.6).

```jsonc
"age_under_20_percent_geo20": {
  ...existing dashboard fields...,
  "geo_standardize": {
    "measure_type": "ratio",          // count|ratio|rate|median|mean|density|index
    "numerator":   "age_under_20_count",
    "denominator": "age_total_count"   // exact denominator when published
  }
},
"no_hlth_ins_pct_geo20": {
  "geo_standardize": {
    "measure_type": "ratio",
    "weight": "total_population"        // population-weight fallback (see §4.2, Fork 1)
  }
},
"median_household_income_geo20": {
  "geo_standardize": { "measure_type": "median", "replicate": true }
},
"population_density_geo20": {
  "geo_standardize": { "measure_type": "density", "count": "population_count" }
},
"gini_index_geo20": {
  "geo_standardize": { "measure_type": "index", "interpolate": false }
}
```

Field rules:
- `count`: no extra fields. Area-weighted sum.
- `ratio`/`rate`: either `numerator`+`denominator` (both must be present in the frame
  at standardization time) **or** `weight` (a count to population-weight by).
- `median`/`mean`: `weight` (population-weight) **or** `replicate: true`.
- `density`: `count` (the extensive count) — recomputed as count ÷ 2020 land area.
- `index`: `interpolate: false` — never interpolated; recomputed from standardized
  inputs by the composite pipeline (§4.5).

## 4. `standardize_all` new behavior (sdc-core / sdc-census10to20)

`standardize_all` gains a `measure_info` parameter (dict or path). For each pre-2020
sub-county (year, measure) it dispatches on `measure_type`:

### 4.1 count (extensive)
Area-weighted sum via `convert_2010_to_2020_bounds`. Unchanged from the v0.1.2 fix.

### 4.2 ratio / rate (intensive)
- If `numerator` + `denominator` are declared and present: area-weight each as counts,
  then `value_geo20 = scale · numerator_geo20 / denominator_geo20`
  (`scale` = 100 for percent, 100000 for per-100k, etc.). **Exact** — equals the
  parent ratio for splits and the count-weighted average for merges.
- Else (count-less; **Fork 1 = population-weight by total population**): population-
  weighted average of parent values, weight = the declared `weight` count (default
  `total_population`), which the pipeline must include in the standardization frame.
  Mechanically: `Σ(value_parent · weight_parent · area_frac) / Σ(weight_parent ·
  area_frac)`. **Exact for pure splits** (one parent → weighted avg of one value = that
  value); a **close approximation for the rarer merge cases** where the true
  denominator ≠ total population. This approximation is documented per affected
  measure (Without Health Insurance, Broadband, Pop Characteristics, Coop Extension,
  Geo Mobility, Affordability cost %s).

### 4.3 median / mean (Fork 2 = replicate)
Each 2020 child takes the value of its **area-dominant** 2010 parent (the parent with
the largest `area_part` overlap). This is the uniform-within-tract estimate the areal
method already assumes; for medians it is as defensible as weighted averaging (a median
cannot be truly reaggregated). `weight`-based population-weighting is supported in the
schema for future opt-in but is **not** the default.

### 4.4 density
Standardize the declared `count` (area-weighted sum), then divide by the **2020** tract
land area (`area20`, from the Census relationship file the crosswalk already loads).
`density_geo20 = count_geo20 / area20`. Not area-weighted as a value.

### 4.5 index (composite)
**Never interpolated.** The composite pipeline standardizes its *input* measures (each
by its own type) and **recomputes the index on 2020 boundaries** from the standardized
inputs. Implementation must verify each HOI pipeline does convert-inputs-then-compute,
not compute-then-convert. **`environment/Environmental Hazard Index (HOI)` calls
`convert_2010_to_2020_bounds` directly (ingest.py:327) — confirm what it converts and
fix to input-then-compute if it interpolates the index.**

### 4.6 unclassified / error handling
- Measure with no `geo_standardize`: fall back to a name heuristic (count vs intensive)
  **and log a warning** naming the measure, so gaps are visible rather than silent.
- A `ratio` declaring `numerator`/`denominator` that are absent from the frame, or a
  `density` whose `count` is absent: **raise** rather than silently area-weight.

## 5. sdc-core API surface
- `standardize_all(df, *, measure_info=None, ...)` — accepts a measure→metadata map or
  a `measure_info.json` path.
- `write_data(..., census_standardize=True, measure_info=None)` — threads
  `measure_info` to `standardize_all`. Pipelines pass their topic's
  `measure_info.json`. When `measure_info` is None, behavior is the heuristic fallback
  (backward compatible for non-migrated callers, with warnings).
- `convert_2010_to_2020_bounds` itself is unchanged (the extensive primitive); the new
  intensive logic lives in `standardize_all` and small helpers.

## 6. Tests
Extend `packages/sdc-census10to20/tests/test_convert.py`:
- ratio (exact num/denom): split parent 30% → all children 30%.
- ratio (population-weight): pure split exact; merge = count-weighted average.
- median/mean: child = area-dominant parent value.
- density: count conserved, value = count/area20.
- index: `interpolate:false` measures pass through untouched by `standardize_all`.
- regression guard: a percent measure is **not** area-diluted (no `1.96`-type result).

## 7. Per-dataset work (the 24)
For each affected dataset:
1. Author `geo_standardize` blocks in `measure_info.json` for every `_geo20` measure.
2. Ensure the required inputs are present in the standardization frame: constituent
   counts for exact ratios, or `total_population` for population-weighted ratios, or the
   `count` for density. ACS pipelines generally already fetch total population; add it
   to the standardized frame where missing (publish or drop per existing contract).
3. Pass `measure_info` to `write_data`/`standardize_all`.
4. HOI/composite pipelines: confirm index recompute-from-standardized-inputs (§4.5).

## 8. Phasing
- **Phase 0 — sdc-core:** `standardize_all` + `write_data` changes + tests. No data
  regenerated yet.
- **Phase 1 — metadata + frames:** author `measure_info` `geo_standardize` and ensure
  weight/count inputs across the 24 (base ACS first, then composites).
- **Phase 2 — composite indices:** verify/fix each HOI to recompute from standardized
  inputs.
- **Phase 3 — combined regeneration:** hand off to the (now unblocked) remediation
  spec, whose acceptance gate is extended (§9) to verify intensive measures too.

## 9. Acceptance (extends the remediation gate)
Per dataset, in addition to the count conservation check (county geo20/geo10 ≈ 1.0):
- Every `ratio`/`rate` `_geo20`: for split-only counties, child value ≈ parent ratio /
  constituent-count-recomputed value within tolerance.
- No intensive measure exhibits the area-dilution signature (e.g. a percent whose
  per-child value collapses far below the county mean while siblings inflate).
- `index` `_geo20` equals the value recomputed from standardized inputs (not an
  interpolation of the old index).

## 10. Non-goals
- No change to `convert_2010_to_2020_bounds`' extensive math (already correct).
- No new external data sourcing for medians/means (replicate; weighting is opt-in).
- No dashboard-side recompute; correctness is produced upstream in the distribution
  files. Published measure sets are preserved unless a dataset opts to publish
  constituent counts.

## 11. Known approximations (documented, accepted)
- Population-weighted ratios for count-less measures use **total population** as the
  weight; exact for splits, approximate for merges where the true denominator differs
  (households, labor force, civilian noninstitutionalized population).
- Medians/means are **replicated** from the area-dominant parent — a uniform-within-
  tract estimate, not a true reaggregation.
- Both are strictly better than area-weighting and are the standard areal-interpolation
  treatments for intensive measures absent sub-tract microdata.
