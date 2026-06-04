# census10to20 Coverage-Gap Standardization — Design

**Date:** 2026-06-04
**Status:** Approved (design); pending spec review → implementation plan

## Goal

Standardize the 7 monorepo datasets that carry pre-2020 census-tract/block-group data on
2010-vintage boundaries but currently emit **no** `_geo20` measures, bringing them onto 2020
geographies consistent with the 24 already-remediated datasets and the dashboards.

## Background

After the 24-dataset census10to20 remediation, an audit of all ~72 datasets (see
`docs/census10to20-coverage-gap-candidates.md`) plus a vintage probe identified datasets with
pre-2020 tract/BG data that are not standardized. A dataset truly needs standardization only if
its pre-2020 data exists **at the tract/BG level** and sits on 2010-vintage boundaries.

The probe (unique tract count per year, and tract-set overlap vs known 2010/2020 sets) resolved
the vintage of each candidate. Critically, several sources switched to 2020 geographies at a
year **other than 2020**, which the current `standardize_all` (hardcoded `year < 2020`)
mishandles — the same failure mode that forced the manual workaround on EnvHazard in the prior
remediation.

## Scope

### In scope (7 datasets)

| Dataset | Source | Vintage pattern | `vintage_cutoff_year` |
|---|---|---|---|
| business_climate/Employment/Worker_diversity | LODES | all 2010-vintage (2010–2019) | 2020 (default) |
| food/Food and Nutrition Assistance/Supplemental Nutrition Assistance Program (SNAP) | census_acs | clean switch at 2020 (2013–2019 = 2010 set) | 2020 (default) |
| health/Health Care Services/Physicians/OB-GYN/Service Access Scores | CMS | switch at 2021 (2020 is 2010-vintage) | 2021 |
| health/Health Care Services/Physicians/Pediatric/Service Access Scores | CMS | switch at 2021 | 2021 |
| health/Health Care Services/Physicians/Primary Care/Service Access Scores | CMS | switch at 2021 | 2021 |
| health/Mental Health/Mental and Physical Healthy Days | CDC PLACES | switch at 2022/23 (2020+2021 are 2010-vintage) | 2022 |
| housing/Cost/Rent | HUD FMR | **all years** 2010-vintage (fixed 2010 tract set) | sentinel = "all years" |

Evidence for the cutoffs: per-year unique tract counts — Worker_diversity constant ~1766
(2010–2019); SNAP 8530 (2013–2019) → 9606 (2020–2023); OB-GYN/Pediatric/PrimaryCare 3131
(≤2020) → 3529 (2021+); PLACES 4967 (2018–2021) → 5654 (2023); Rent constant 3124 (2018–2025),
with VA tracts overlapping the 2010 set 1895/1898 but the 2020 set only 1626/1898.

### Out of scope

- **Hospitals and Emergency Rooms/Service Access Scores** — erratic per-year tract counts
  (5181→5357→7941→5755→3529) indicate inconsistent geography across years, not a clean
  2010→2020 switch. Investigate (and likely fix the underlying geography handling) **separately**
  before standardizing. Tracked as a follow-up, not part of this effort.
- **Overall Food Insecurity (Feeding America)** — its tract-level data exists **only at 2020**
  (pre-2020 years are county-only). No pre-2020 tract data to convert → not a gap. Excluded.
- The 9 verified 2020-native datasets and the 8 county-only business_climate datasets from the
  audit doc remain out of scope (unchanged).

## Design

### 1. Shared change: configurable vintage cutoff in `standardize_all`

`packages/sdc-census10to20/src/sdc_census10to20/convert.py` hardcodes the 2010/2020 boundary as
`year < 2020` in two places:
- line ~366: the `_geo10` vs `_geo20` suffix decision for the "original" rows.
- line ~376: `if yr < 2020:` — the gate on which years get converted to 2020 boundaries.

Add a keyword parameter `vintage_cutoff_year: int = 2020` to `standardize_all`. Replace both
literals with the parameter: a sub-county row is treated as 2010-vintage (gets `_geo10` for the
original copy, and is converted to a `_geo20` copy) when `year < vintage_cutoff_year`; otherwise
it is native-2020 (`_geo20`, no conversion). Default `2020` preserves current behavior exactly
(backward-compatible; the 24 standardized datasets are unaffected).

Thread the parameter through `sdc_core.io.write_data` so a pipeline can pass
`write_data(df, path, census_standardize=True, measure_info=mi, vintage_cutoff_year=2021)`.
`write_data` forwards it to `standardize_all`. Default `2020` so existing callers are unchanged.

**"All years 2010-vintage" (Rent):** pass a cutoff above the dataset's max year (e.g. the
pipeline computes `max(years) + 1`), so every year is `< cutoff` and converted. This needs no
new sentinel type — a sufficiently high integer expresses "convert all years." The Rent ingest
will compute and pass `vintage_cutoff_year = max(years) + 1`.

### 2. Per-dataset measure types (`geo_standardize` blocks)

Each in-scope dataset's `measure_info.json` currently has **zero** `geo_standardize` blocks.
Add a block per published measure. Measure-type rules:

- **count** (area-weighted, count-conserving): integer population/establishment/provider counts.
  - Worker_diversity: all `wac_*_count`, `*_count`, `Minority_employment`, `Nonminority_employment`.
  - SNAP: `hh_received_snap_cnt`, `population`.
  - Service Access Scores: `*_cnt` (provider counts).
- **ratio** (recompute percentage from standardized numerator/denominator counts): percentages
  whose constituent counts are published in the same dataset.
  - SNAP: `hh_received_snap_pct` (= `hh_received_snap_cnt` / households; confirm denominator
    measure name during implementation — may require declaring a denominator count as an
    `input_only` helper).
  - Worker_diversity: `*_perc` measures **if** the matching `*_count` and total are published;
    otherwise fall back to **replicate** (decide per measure during implementation — see Open
    Items).
- **replicate** (dominant-parent copy): intensive measures with no published count basis —
  indices, distances, medians, and standalone percents.
  - Service Access Scores: `*_2sfca`, `*_3sfca`, `*_e2sfca`, `*_near_10_mean`, `*_near_10_median`.
  - PLACES: `perc_freq_mental_distress`, `perc_freq_physical_distress`.
  - Rent: `monthly_rent_0br` … `monthly_rent_4br`.

`_geo10` variant descriptions follow the project rule: same text as `_geo20` plus "Values on
original 2010 census tract boundaries." (per CLAUDE.md / conversion spec).

### 3. Wiring point

Standardization must happen where the **canonical `data/distribution/` output** is written —
the ingest `write_data` call that produces the long-format distribution file. Per the survey,
each in-scope pipeline writes its distribution file in `ingest.py` (Worker_diversity:148,
Rent:476/488, PLACES:285, Service Access Scores ingest:~272; SNAP writes in ingest:84 and
re-writes in prepare:121). For each, change the **ingest** distribution `write_data` to
`census_standardize=True, measure_info=<loaded measure_info>, vintage_cutoff_year=<cutoff>`.
During implementation, confirm per pipeline which `write_data` produces the published
distribution file (vs a working/intermediate file) and standardize at that point only. The
three `census_standardize=False` flags (Worker_diversity, PLACES, Rent) are flipped to `True`;
the PLACES comment is updated to reflect the project-wide standardization decision.

## Components / files changed

- `packages/sdc-census10to20/src/sdc_census10to20/convert.py` — add `vintage_cutoff_year` param.
- `packages/sdc-core/src/sdc_core/io.py` — thread `vintage_cutoff_year` through `write_data`.
- Per dataset (7): `measure_info.json` (+ `geo_standardize` blocks), `code/distribution/ingest.py`
  (flip `census_standardize`, pass `measure_info` + `vintage_cutoff_year`).
- `tools/census10to20_remediation/datasets.py` — add the 7 to the driver dataset list.
- Harness tests (`packages/sdc-census10to20` + `tools/census10to20_remediation`) — metadata test
  coverage for the 7; a unit test for `vintage_cutoff_year` (e.g. a 2021-cutoff frame converts
  its 2020 rows but not its 2021 rows).

## Execution flow (per dataset)

1. Confirm measure types against `measure_info.json` and the data; resolve any `ratio`-vs-
   `replicate` percentage questions (Open Items).
2. Add `geo_standardize` blocks to `measure_info.json`.
3. Flip ingest `write_data` to `census_standardize=True, measure_info=…, vintage_cutoff_year=…`.
4. Add to the harness metadata test + driver dataset list.
5. Regenerate via the `tools/census10to20_remediation/` driver with `SDC_NO_PUBLISH=1` and the
   region-wide conservation gate (tol 0.02, per-county worst-N reporting).
6. Validate: `_geo10`/`_geo20` measures present for pre-cutoff years; native `_geo20` for
   post-cutoff years; region-wide conservation for count measures; sane row counts; spot-check
   that a known 2010 tract that split is replicated (intensive) or area-weighted (count) correctly.
7. Commit per dataset.

After all 7: run the full test suite, then `finishing-a-development-branch` (merge to main +
push), create git tags, and create GitHub releases (data files attached). **No Zenodo** — none
of the 7 has a `zenodo_deposit_id`.

## Testing & validation

- **Unit:** `vintage_cutoff_year` behavior in `standardize_all` (default 2020 unchanged; a
  cutoff of 2021 converts 2020 rows and leaves 2021 native; a high cutoff converts all years).
- **Metadata harness:** every published measure of the 7 has a valid `geo_standardize` block.
- **Conservation gate:** region-wide summed-2020 / summed-2010 ≈ 1.0 for count measures
  (Worker_diversity, SNAP counts, provider counts); intensive measures exempt (replicate).
- **Regression:** the 24 already-standardized datasets must be byte-stable (default cutoff
  unchanged) — verified by the existing harness still passing.

## Open items (resolved during implementation, not blocking the plan)

1. **Worker_diversity percents** — determine per measure whether each `*_perc` has a published
   count basis (→ `ratio`) or not (→ `replicate`). Also reconcile the 78 `measure_info` keys vs
   ~40 data measures (stale/unused metadata vs emitted measures).
2. **SNAP `pct` denominator** — confirm the households denominator measure name; declare it
   `input_only` if it is a helper count not published as its own measure.
3. **Block-group standardization** — Worker_diversity, SNAP, and the Service Access Scores carry
   block-group rows; confirm the per-state BG relationship file resolves for the coverage
   (state_fips) and that BG conversion behaves (the tract relationship file is national; BG is
   per-state).
4. **Service Access Scores re-write in prepare** — confirm prepare does not re-emit a
   non-standardized distribution file over the standardized one.

## Risks

- **Wrong cutoff** → pre-2020-vintage years treated as native (no conversion) or vice-versa.
  Mitigated by the per-year tract-count evidence above and the validation step.
- **sdc-core change regressing the 24** → mitigated by the `2020` default and the existing
  harness.
- **Hospitals-style hidden inconsistency** in another dataset → the per-year tract-count check is
  part of validation; if a supposedly-clean dataset shows erratic counts, pause and treat like
  Hospitals.
