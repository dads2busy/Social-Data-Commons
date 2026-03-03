# Mergent Intellect Pipeline Validation Report

Validated: 2026-03-03

## Overview

Converted 8 Mergent Intellect sub-pipelines from R to Python, plus a shared
computation module (`mi_metrics.py`). All pipelines read pre-computed
block-group-level feature files and aggregate business/employment metrics at
block_group, tract, and county levels.

## Shared module

`business_climate/Microdata/Mergent_intellect/mi_metrics.py` replaces
`business_climate/utils/distribution/functions.R` (625 lines of R).

## Validation results

Every file with existing R output was compared row-by-row.  Maximum numeric
difference across all files is ~1.42e-14 (IEEE 754 floating-point only).

### Business_characteristics

| Topic | Prefix | Rows | Max diff |
|---|---|---|---|
| Total | va059 | 49,100 | 0.00e+00 |
| Total | ncr | 247,250 | 1.78e-15 |
| Total | rva | 26,330 | 0.00e+00 |
| Minority_owned | va059 | 92,250 | 8.88e-16 |
| Minority_owned | ncr | 456,425 | 7.11e-15 |
| Minority_owned | rva | 47,655 | 0.00e+00 |
| Industry | va059 | 629,035 | 0.00e+00 |
| Industry | ncr | 3,702,555 | 3.55e-15 |
| Industry | rva | 400,530 | 0.00e+00 |
| Industry_Minority_owned | va059 | 761,160 | — (no prior R output) |
| Industry_Minority_owned | ncr | 4,418,640 | — (no prior R output) |
| Industry_Minority_owned | rva | 470,215 | — (no prior R output) |

### Employment

| Topic | Prefix | Rows | Max diff |
|---|---|---|---|
| Total | va059 | 103,140 | 0.00e+00 |
| Total | ncr | 598,430 | 1.42e-14 |
| Total | rva | 62,924 | 0.00e+00 |
| Minority_owned | va059 | 145,432 | 0.00e+00 |
| Minority_owned | ncr | 814,741 | 1.42e-14 |
| Minority_owned | rva | 81,973 | 0.00e+00 |
| Industry | va059 | 578,323 | 1.42e-14 |
| Industry | ncr | 5,214,637 | 1.42e-14 |
| Industry | rva | 539,060 | 0.00e+00 |
| Industry_Minority_owned | va059 | 645,576 | — (no prior R output) |
| Industry_Minority_owned | ncr | 5,608,642 | — (no prior R output) |
| Industry_Minority_owned | rva | 572,439 | — (no prior R output) |

### HHI (Herfindahl-Hirschman Index) — county level only

| Prefix | Rows | Max diff |
|---|---|---|
| va059 | 231 | 0.00e+00 |
| ncr | 3,154 | 0.00e+00 |
| rva | 461 | 0.00e+00 |

### Location Quotient — all geo levels

| Prefix | Rows | Max diff |
|---|---|---|
| va059 | 125,325 | 0.00e+00 |
| ncr | 740,431 | 0.00e+00 |
| rva | 80,106 | 0.00e+00 |

## Dashboard files

28 NCR dashboard files generated via `prepare.py` (8 topics × 3 geo levels,
plus HHI county-only + LQ 3 levels):

```
ncr_{bg,tr,ct}_mi_2010_2020_business_metrics_by_{total,minority_owned,industry,industry_minority_owned}.csv.xz
ncr_{bg,tr,ct}_mi_2010_2020_employment_metrics_by_{total,minority_owned,industry,industry_minority_owned}.csv.xz
ncr_ct_mi_2010_2020_herfindalh_index_by_industry.csv.xz
ncr_{bg,tr,ct}_mi_2010_2020_location_quotient_by_industry.csv.xz
```

## Notes

- Industry_Minority_owned pipelines had no prior R output in the repository.
  The Python output was validated structurally (correct columns, geoid formats,
  year ranges) and the shared `mi_metrics.py` module was validated against all
  other topics that do have R output.
- R `size()` function computed small_business/sole_proprietor metrics but these
  were never included in the R output (dead code). Python matches the actual
  R output (no size metrics).
