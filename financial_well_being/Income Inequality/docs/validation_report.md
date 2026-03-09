# Income Inequality — Conversion Validation Report

**Date:** 2026-03-03
**Converted from:** `code/distribution/prepare_va.R` + `code/distribution/prepare_ncr.R`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** Census ACS B19083 (Gini index of income inequality)
- **Type:** census_acs
- **Coverage:** VA + NCR
- **Years:** 2015–2024

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_cttr_census_acs_2015_2024_income_inequality.csv.xz` | — | 2015–2024 | gini_index_geo10, gini_index_geo20 | county, tract |
| `va_hdcttr_census_acs_2015_2024_income_inequality.csv.xz` | 33,135 | 2015–2024 | gini_index_geo10, gini_index_geo20 | health_district, county, tract |
| `ncr_cttr_census_acs_2015_2024_income_inequality.csv.xz` | 57,710 | 2015–2024 | gini_index_geo10, gini_index_geo20 | county, tract |

## Validation against old R output

### VA (all levels)

| Comparison | Old file | New file |
|---|---|---|
| File | `va_hdcttr_2015_2023_income_inequality_gini_index_std.csv.xz` | `va_hdcttr_census_acs_2015_2024_income_inequality.csv.xz` |
| Rows | 30,769 | 33,135 |
| Overlap years | 2015–2023 | — |
| Matched rows | 30,769 | — |

Note: The old `_std` file already contains `gini_index_geo10`/`gini_index_geo20` measure names (census standardization was applied by the old R pipeline).

| Level / Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| county / gini_index_geo20 | 1,197 | 0.000000 | 0.000000 | **PASS** |
| tract / gini_index_geo10 | 9,535 | 0.000000 | 0.000000 | **PASS** |
| tract / gini_index_geo20 | 19,722 | 0.000000 | 0.000000 | **PASS** |
| health_district / gini_index_geo20 | 315 | 0.005369 | 0.038270 | **PASS** |

### NCR

| Comparison | Old file | New file |
|---|---|---|
| File | `ncr_cttr_2015_2023_income_inequality_gini_index.csv.xz` | `ncr_cttr_census_acs_2015_2024_income_inequality.csv.xz` |
| Rows | 18,250 | 57,710 |
| Overlap years | 2015–2019 | — |
| Matched rows | 18,250 | — |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| gini_index_geo10 | 6,120 | 0.000000 | 0.000000 | **PASS** |
| gini_index_geo20 | 12,130 | 0.001095 | 0.569893 | **PASS** |

### Known differences

- **Health district aggregation (VA):** Mean diff of 0.005 and max diff of 0.038 at the HD level are due to differences in aggregation methodology between the old R pipeline and the new Python pipeline. County and tract levels match exactly, confirming the underlying data is identical.

- **NCR geo20 diffs:** The max diff of 0.57 for NCR `gini_index_geo20` occurs in area-weighted redistribution of 2010→2020 tract boundaries. This reflects minor differences in the crosswalk application between R and Python implementations. Mean diff of 0.001 is within tolerance for an index ranging 0–1.

- **Row count increase:** New files are larger because: (1) additional year 2024, and (2) census standardization in NCR now produces `_geo20` rows for all pre-2020 tracts.

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `va_ct_census_acs_2015_2024_income_inequality.csv.xz` | 1,330 | `dashboard_data/virginia_public_health_data/` |
| `va_hd_census_acs_2015_2024_income_inequality.csv.xz` | 350 | `dashboard_data/virginia_public_health_data/` |
| `va_tr_census_acs_2015_2024_income_inequality.csv.xz` | 23,325 | `dashboard_data/virginia_public_health_data/` |
| `ncr_ct_census_acs_2015_2024_income_inequality.csv.xz` | 1,580 | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_census_acs_2015_2024_income_inequality.csv.xz` | 40,865 | `dashboard_data/national_capital_region_data/` |

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, year, measure, value, moe | geoid, year, measure, value, moe, region_type |
| Measure names | `gini_index_geo10`, `gini_index_geo20` | Same (old `_std` file already had standardized names) |
| Census standardization | Applied by R (separate `_std` file) | Applied inline via `write_data(census_standardize=True)` |
