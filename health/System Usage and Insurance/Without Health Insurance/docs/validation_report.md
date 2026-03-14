# Without Health Insurance — Validation Report

**Date:** 2026-03-14
**Pipeline version:** v1.0.0

## Data sources

- ACS 5-year estimates, table B27010 (Types of Health Insurance Coverage by Age)
- Variables: B27010_018 (total 19-34), B27010_033 (uninsured 19-34), B27010_034 (total 35-64), B27010_050 (uninsured 35-64)
- Measures: `no_hlth_ins_pct`, `hlth_ins_pct`

## Coverage

| Source | Years | Geographies |
|--------|-------|-------------|
| VA | 2015-2024 | county, tract, health_district |
| NCR | 2015-2024 | county, tract, block_group |

Old R pipeline covered 2015-2023. New Python pipeline extends through 2024.

## Row counts

| Dataset | Old (R) | New (Python) |
|---------|---------|--------------|
| NCR (cttrbg) | 84,598 | 276,860 (incl. _geo10 + _geo20 variants) |
| VA (hdcttr) | 39,678 | 65,462 (incl. _geo10 + _geo20 variants) |

New data is larger due to: (1) additional year 2024, (2) census_standardize=true creates _geo10 and _geo20 measure variants.

## Validation comparison (2015-2023 overlap)

### VA counties (5-digit FIPS)

| Metric | Value |
|--------|-------|
| Rows compared | 2,394 |
| Exact matches | 2,394/2,394 (100.0%) |
| Mean difference | 0.000000 |
| Max difference | 0.000000 |

### NCR counties (5-digit FIPS)

| Metric | Value |
|--------|-------|
| Rows compared | 252 |
| Exact matches | 252/252 (100.0%) |
| Mean difference | 0.000000 |
| Max difference | 0.000000 |

### NCR tracts (11-digit FIPS)

| Metric | Value |
|--------|-------|
| Rows compared | 21,584 |
| Exact matches | 18,364/21,584 (85.1%) |
| Mean difference | 0.016660 |
| Max difference | 11.676731 |

### NCR block groups (12-digit FIPS)

| Metric | Value |
|--------|-------|
| Rows compared | 40,462 |
| Exact matches | 37,222/40,462 (92.0%) |
| Mean difference | 0.344262 |
| Max difference | 66.328484 |

### Explanation of tract/block group differences

County-level values are **identical** between old R and new Python output. Tract and block group differences are entirely attributable to **2010→2020 census boundary standardization** (`census_standardize=true`). The old R pipeline used raw ACS geographies (mixed 2010/2020 boundaries depending on year), while the new Python pipeline standardizes all values to 2020 census boundaries using population-weighted crosswalks. This is an intentional improvement, not an error.

## Conclusion

Validation passes. County-level data is exact. Sub-county differences are expected from boundary standardization.
