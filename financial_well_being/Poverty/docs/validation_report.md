# Poverty — Conversion Validation Report

**Date:** 2026-03-03
**Converted from:** `code/distribution/prepare_adult_poverty_by_race.R` + `code/distribution/prepare_child_poverty_by_race.R` + `code/distribution/prepare_poverty_by_race.R`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** Census ACS 5-Year, tables B17001A–B17001I (poverty status by age, sex, and race)
- **Type:** census_acs
- **Coverage:** NCR (adults and children by race/sex) + Fairfax County VA (demographics)
- **Years:** 2021

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `ncr_tr_census_acs_2021_poverty_adults.csv.xz` | 31,377 | 2021 | 24 | tract |
| `ncr_tr_census_acs_2021_poverty_children.csv.xz` | 28,892 | 2021 | 24 | tract |
| `va059_tr_census_acs_2021_2021_poverty_demographics.csv.xz` | 6,521 | 2021 | 24 | tract |

## Validation against old R output

### NCR Adults

| Comparison | Old file | New file |
|---|---|---|
| File | `ncr_tr_acs_2021_poverty_adults.csv.xz` | `ncr_tr_census_acs_2021_poverty_adults.csv.xz` |
| Rows | 47,916 | 31,377 |
| Measures | 36 | 24 |
| Common measures | 24 | — |
| Matched rows | 31,377 | — |

Row count difference: Old file contained 12 additional `*_cnt` measures (e.g. `asian_men_cnt`, `blk_women_cnt`) that are gender-split population counts. These are not included in the new pipeline as they are intermediate values, not final poverty measures. The 24 common measures match exactly.

| Measure group | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| All 24 common measures | 31,377 | 0.000000 | 0.000000 | **PASS** |

### NCR Children

| Comparison | Old file | New file |
|---|---|---|
| File | `ncr_tr_acs_2021_poverty_children.csv.xz` | `ncr_tr_census_acs_2021_poverty_children.csv.xz` |
| Rows | 47,916 | 28,892 |
| Measures | 36 | 24 |
| Common measures | 24 | — |
| Matched rows | 28,892 | — |

| Measure group | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| Non-`othr_*` measures (20) | 23,912 | 0.000000 | 0.000000 | **PASS** |
| `othr_*` measures (4) | 4,980 | 0.479164 | 388.000000 | **KNOWN DIFF** |

### FFX Demographics

| Comparison | Old file | New file |
|---|---|---|
| File | `va059_tr_acs_2021_poverty_demographics.csv.xz` | `va059_tr_census_acs_2021_2021_poverty_demographics.csv.xz` |
| Rows | 6,576 | 6,521 |
| Matched rows | 6,521 | — |

Row count difference: Old file contained 55 extra rows for tracts that no longer exist in ACS 2021 vintage. These rows had null/zero values.

| Measure group | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| All 24 measures | 6,521 | 0.000000 | 0.000000 | **PASS** |

### Known differences

- **Children `othr_*` measures (othr_boys_pov_cnt, othr_boys_pov_pct, othr_girls_pov_cnt, othr_girls_pov_pct):** Old R code had a vector recycling bug. The "other" race tables were computed by pairing `c(rep("C",7), rep("E",7), rep("F",7), rep("G",7))` (28 elements) with `str_pad(4:9)` (6 elements). R silently recycles the shorter vector, causing the table-letter/variable-number pairings to shift after the first 6 iterations. This double-counts some variables (e.g. B17001C_004, B17001E_005) and skips others. The adult pipeline was unaffected because it used `10:16` (7 elements), matching the `rep(...,7)` groups. The Python pipeline correctly iterates each race table and variable independently. **New is correct.**

- **Old-only measures (12 `*_cnt` measures in adults and children):** The old R files included 12 additional gender-split population count measures (e.g. `asian_men_cnt`, `blk_boys_cnt`). These are intermediate denominators, not final poverty measures. The new pipeline does not produce them. This is intentional — the poverty rate/count measures already capture the same information.

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `ncr_tr_census_acs_2021_poverty_adults.csv.xz` | 1,331 | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_census_acs_2021_poverty_children.csv.xz` | 1,331 | `dashboard_data/national_capital_region_data/` |

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, year, measure, value, moe | geoid, year, measure, value, moe, region_type |
| Measure count (adults/children) | 36 (incl. 12 intermediate counts) | 24 (poverty measures only) |
| `region_type` column | Not present | `tract` |
