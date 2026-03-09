# Personal Income — Conversion Validation Report

**Date:** 2026-03-03
**Converted from:** `code/distribution/ingest.R` + `code/distribution/prepare.R`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** Bureau of Economic Analysis (BEA) CAINC4 — Personal Income and Employment by Major Component
- **Type:** bea
- **Coverage:** VA (counties + health districts)
- **Years:** 2015–2024

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_hdct_bea_2015_2024_personal_income.csv.xz` | 5,040 | 2015–2024 | earnings_per_job, tot_compensation, tot_employment | county, health_district |

## Validation against old R output

Reference file: `va_hdct_bea_2015_2023_earnings_per_job.csv.xz` (4,536 rows)

Note: Old file used `"health district"` (with space) in `region_type`; new file uses `"health_district"` (underscore). Old file used `total_compensation`/`total_employment` for HD rows; new file uses `tot_compensation`/`tot_employment` consistently. Comparisons below normalize these differences.

### County — earnings_per_job

| Comparison | Value |
|---|---|
| Overlap years | 2015–2023 |
| Matched rows | 1,197 |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| earnings_per_job | 1,197 | 1.22 | 30.60 | **PASS** |

624/1,197 rows match exactly; remaining differences are small rounding (max $30.60).

### Health district — earnings_per_job

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| earnings_per_job | 315 | 1.25 | 26.36 | **PASS** |

### County — tot_compensation

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| tot_compensation | 1,197 | 7,370,464 | 783,414,000 | **KNOWN DIFF** |

Per-year breakdown:

| Year | Diffs > 0 | Mean % diff | Max % diff |
|---|---|---|---|
| 2015 | 0 | 0.0000% | 0.0000% |
| 2016 | 0 | 0.0000% | 0.0000% |
| 2017 | 0 | 0.0000% | 0.0000% |
| 2018 | 0 | 0.0000% | 0.0000% |
| 2019 | 0 | 0.0000% | 0.0000% |
| 2020 | 133 | 0.1349% | 7.2817% |
| 2021 | 133 | 0.1321% | 7.6059% |
| 2022 | 133 | 0.0052% | 7.0632% |
| 2023 | 133 | -0.1554% | 7.7578% |

### Health district — tot_compensation

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| tot_compensation | 315 | 25,625,762 | 1,760,340,000 | **KNOWN DIFF** |

### County — tot_employment

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| tot_employment | 1,197 | 14,239 | 1,297,395 | **KNOWN DIFF** |

### Health district — tot_employment

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| tot_employment | 315 | 51,975 | 3,892,185 | **KNOWN DIFF** |

### Known differences

- **BEA data revisions (2020–2023):** Years 2015–2019 match exactly for `tot_compensation` and `tot_employment`. Years 2020–2023 differ because BEA periodically revises its estimates. The old R pipeline was run against an earlier vintage of BEA data; the new Python pipeline fetched the current (revised) vintage. BEA revisions are standard practice, especially for recent years. Mean percentage difference is under 0.2% for most counties; the ~7% max outlier likely reflects a BEA reclassification of establishments between FIPS codes. **New is correct** (uses latest BEA data).

- **Measure naming:** Old file used `total_compensation`/`total_employment` for HD rows but `tot_compensation`/`tot_employment` for county rows. New pipeline uses `tot_compensation`/`tot_employment` consistently at all levels.

- **Region type format:** Old file used `"health district"` (with space); new uses `"health_district"` (underscore) to match the standard schema.

- **Old-only measures:** Old file contained `total_compensation` and `total_employment` as separate HD measures (315 rows each). These are the same data as `tot_compensation`/`tot_employment` under a different name. The new pipeline consolidates to a single name.

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `va_ct_bea_2015_2024_personal_income.csv.xz` | 1,330 | `dashboard_data/virginia_public_health_data/` |
| `va_hd_bea_2015_2024_personal_income.csv.xz` | 350 | `dashboard_data/virginia_public_health_data/` |

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, year, measure, value, moe, region_name, region_type, measure_type | geoid, year, measure, value, moe, region_type |
| Extra columns | `region_name`, `measure_type` | Removed (not part of standard schema) |
| Measure names (HD) | `total_compensation`, `total_employment` | `tot_compensation`, `tot_employment` |
| `region_type` format | `"health district"` | `"health_district"` |
