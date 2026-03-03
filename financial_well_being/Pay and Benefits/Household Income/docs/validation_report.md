# Household Income — Conversion Validation Report

**Date:** 2026-03-03
**Converted from:** `code/distribution/ingest.R` + `code/distribution/prepare_va.R` + `code/distribution/prepare_ncr.R`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** Census ACS B19013 (median household income in past 12 months)
- **Type:** census_acs
- **Coverage:** VA + NCR
- **Years:** 2015–2024

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_cttrbg_census_acs_2015_2024_household_income.csv.xz` | 89,178 | 2015–2024 | median_household_income_geo10, median_household_income_geo20 | block_group, county, tract |
| `ncr_cttrbg_census_acs_2015_2024_household_income.csv.xz` | 159,143 | 2015–2024 | median_household_income_geo10, median_household_income_geo20 | block_group, county, tract |

## Validation against old R output

### VA

| Comparison | Old file | New file |
|---|---|---|
| File | `va_cttrbg_2015_2023_median_household_income.csv.xz` | `va_cttrbg_census_acs_2015_2024_household_income.csv.xz` |
| Rows | 19,524 | 89,178 |
| Overlap years | 2015–2019 | — |
| Matched rows (geo10) | 9,532 | — |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| median_household_income | 9,532 | 0.00 | 0.00 | **PASS** |

### NCR

| Comparison | Old file | New file |
|---|---|---|
| File | `ncr_cttrbg_2015_2023_median_household_income.csv.xz` | `ncr_cttrbg_census_acs_2015_2024_household_income.csv.xz` |
| Rows | 42,299 | 159,143 |
| Overlap years | 2015–2019 | — |
| Matched rows (geo10) | 6,120 | — |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| median_household_income | 6,120 | 0.00 | 0.00 | **PASS** |

### Known differences

- **Negative values (suppression codes):** The new output contains 3,050 rows with negative values, including the Census Bureau suppression sentinel `-666666666`. These represent tracts/block groups where ACS suppresses median income due to insufficient sample size. The old R pipeline appears to have filtered these out. The new pipeline retains them for transparency; downstream consumers should filter `value < 0` if needed.

- **Row count increase:** New files are substantially larger because: (1) additional year 2024, (2) census standardization produces both `_geo10` and `_geo20` rows for pre-2020 tracts and block groups, and (3) suppression-coded rows are retained.

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `va_ct_census_acs_2015_2024_household_income.csv.xz` | 1,330 | `dashboard_data/virginia_public_health_data/` |
| `va_tr_census_acs_2015_2024_household_income.csv.xz` | 23,322 | `dashboard_data/virginia_public_health_data/` |
| `va_bg_census_acs_2015_2024_household_income.csv.xz` | 56,399 | `dashboard_data/virginia_public_health_data/` |
| `ncr_ct_census_acs_2015_2024_household_income.csv.xz` | 1,580 | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_census_acs_2015_2024_household_income.csv.xz` | 40,860 | `dashboard_data/national_capital_region_data/` |
| `ncr_bg_census_acs_2015_2024_household_income.csv.xz` | 101,442 | `dashboard_data/national_capital_region_data/` |

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, year, measure, value, moe | geoid, year, measure, value, moe, region_type |
| Measure names | `median_household_income` | `median_household_income_geo10`, `median_household_income_geo20` |
| Suppression codes | Filtered out | Retained as `-666666666` |
| Census standardization | Not applied | Applied — pre-2020 tracts/block groups appear as both `_geo10` and `_geo20` |
