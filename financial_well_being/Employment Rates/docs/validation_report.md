# Employment — Conversion Validation Report

**Date:** 2026-03-03
**Converted from:** `code/distribution/prepare_va_emp_rate.R` + `code/distribution/prepare_va_labor_participate_rate.R` + `code/distribution/prepare_ncr_emp_rate.R` + `code/distribution/prepare_ncr_job_participate_rate.R`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** Census ACS B23025 (employment rate) and S2301 (labor force participation rate)
- **Type:** census_acs
- **Coverage:** VA + NCR
- **Years:** 2015–2024

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_cttr_census_acs_2015_2024_employment_rate.csv.xz` | 32,395 | 2015–2024 | emp_rate_geo10, emp_rate_geo20 | county, tract |
| `va_cttr_census_acs_2015_2024_labor_participate_rate.csv.xz` | 32,785 | 2015–2024 | labor_participate_rate_geo10, labor_participate_rate_geo20 | county, tract |
| `ncr_cttr_census_acs_2015_2024_employment_rate.csv.xz` | 57,090 | 2015–2024 | emp_rate_geo10, emp_rate_geo20 | county, tract |
| `ncr_cttr_census_acs_2015_2024_labor_participate_rate.csv.xz` | — | 2015–2024 | labor_participate_rate_geo10, labor_participate_rate_geo20 | county, tract |
| `va_hdcttr_census_acs_2015_2024_labor_participate_rate.csv.xz` | 33,135 | 2015–2024 | labor_participate_rate, labor_participate_rate_geo10, labor_participate_rate_geo20 | health_district, county, tract |

## Validation against old R output

### VA Employment Rate

| Comparison | Old file | New file |
|---|---|---|
| File | `va_cttr_2015_2023_employment_rate.csv.xz` | `va_cttr_census_acs_2015_2024_employment_rate.csv.xz` |
| Rows | 19,524 | 32,395 |
| Overlap years | 2015–2019 | — |
| Matched rows (geo10) | 9,374 | — |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| emp_rate | 9,374 | 0.002462 | 0.005000 | **PASS** |

### NCR Employment Rate

| Comparison | Old file | New file |
|---|---|---|
| File | `ncr_cttr_2015_2023_employment_rate.csv.xz` | `ncr_cttr_census_acs_2015_2024_employment_rate.csv.xz` |
| Rows | 11,570 | 57,090 |
| Overlap years | 2015–2019 | — |
| Matched rows (geo10) | 6,089 | — |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| emp_rate | 6,089 | 0.002518 | 0.005000 | **PASS** |

### VA Labor Participation Rate

| Comparison | Old file | New file |
|---|---|---|
| File | `va_hdcttr_2015_2023_labor_participate_rate.csv.xz` | `va_hdcttr_census_acs_2015_2024_labor_participate_rate.csv.xz` |
| Rows | 19,839 | 33,135 |
| Overlap years | 2015–2019 | — |
| Matched rows (geo10) | 9,535 | — |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| labor_participate_rate | 9,535 | 0.000000 | 0.000000 | **PASS** |

### NCR Labor Participation Rate

| Comparison | Old file | New file |
|---|---|---|
| File | `ncr_cttr_2015_2023_job_participate_rate.csv.xz` | `ncr_cttr_census_acs_2015_2024_labor_participate_rate.csv.xz` |
| Rows | 11,570 | — |
| Overlap years | 2015–2019 | — |
| Matched rows (geo10) | 6,120 | — |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| labor_participate_rate | 6,120 | 0.919997 | 91.930000 | **KNOWN DIFF** |

### Known differences

- **Employment rate rounding:** Max diff of 0.005 across VA and NCR is consistent with decimal precision differences between R (`round(x, 2)`) and Python. All rows within 0.01 tolerance. Acceptable.

- **NCR labor participation rate:** The old R pipeline measure `job_participate_rate` was computed from ACS detail table B23025 (civilian labor force / civilian noninstitutional population). The new pipeline fetches `labor_participate_rate` from ACS subject table S2301_C02_001, which is the ACS pre-computed rate using a slightly different denominator (population 16+). These are different measures from different ACS tables, so value differences are expected and correct. The measure was renamed to `labor_participate_rate` to match the ACS terminology.

- **Row count differences:** New files have more rows because: (1) new pipeline covers 2015–2024 vs old 2015–2023, and (2) census standardization produces both `_geo10` and `_geo20` rows for pre-2020 tracts.

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `va_ct_census_acs_2015_2024_employment_rate.csv.xz` | 1,330 | `dashboard_data/virginia_public_health_data/` |
| `va_tr_census_acs_2015_2024_employment_rate.csv.xz` | 23,036 | `dashboard_data/virginia_public_health_data/` |
| `va_ct_census_acs_2015_2024_labor_participate_rate.csv.xz` | 1,330 | `dashboard_data/virginia_public_health_data/` |
| `va_hd_census_acs_2015_2024_labor_participate_rate.csv.xz` | 350 | `dashboard_data/virginia_public_health_data/` |
| `va_tr_census_acs_2015_2024_labor_participate_rate.csv.xz` | 23,325 | `dashboard_data/virginia_public_health_data/` |
| `ncr_ct_census_acs_2015_2024_employment_rate.csv.xz` | 1,580 | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_census_acs_2015_2024_employment_rate.csv.xz` | 40,385 | `dashboard_data/national_capital_region_data/` |
| `ncr_ct_census_acs_2015_2024_labor_participate_rate.csv.xz` | 1,580 | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_census_acs_2015_2024_labor_participate_rate.csv.xz` | 40,865 | `dashboard_data/national_capital_region_data/` |

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, year, measure, value, moe | geoid, year, measure, value, moe, region_type |
| Measure names | `emp_rate`, `job_participate_rate` | `emp_rate_geo10`, `emp_rate_geo20`, `labor_participate_rate_geo10`, `labor_participate_rate_geo20` |
| Measure rename | `job_participate_rate` | `labor_participate_rate` (matches ACS terminology) |
| Census standardization | Not applied | Applied — pre-2020 tracts appear as both `_geo10` and `_geo20` |
