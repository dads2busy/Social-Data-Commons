# ALICE — Conversion Validation Report

**Date:** 2026-03-03
**Converted from:** `code/distribution/prepare.R`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** United for ALICE Virginia State Data Sheet (Excel download)
- **Type:** alice (pre-computed Excel)
- **Coverage:** VA
- **Years:** 2010, 2012, 2014, 2016, 2018, 2019, 2021

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_ct_alice_2010_2021_alice.csv.xz` | 1,866 | 2010–2021 | alice_pct, poverty_pct | county |

## Validation against old R output

### County level

| Comparison | Old file | New file |
|---|---|---|
| File | `va_ct_2010_2021_alice.csv.xz` | `va_ct_alice_2010_2021_alice.csv.xz` |
| Rows | 1,866 | 1,866 |
| Overlap years | 2010–2021 | — |
| Matched rows | 1,866 | — |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| alice_pct | 933 | 0.002511 | 0.005000 | **PASS** |
| poverty_pct | 933 | 0.002511 | 0.005000 | **PASS** |

### Known differences

- **Rounding:** Max diff of 0.005 across all rows is consistent with rounding to one fewer decimal place. No rows exceed 0.01 tolerance. This is acceptable.

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `va_ct_alice_2010_2021_alice.csv.xz` | 933 | `dashboard_data/virginia_public_health_data/` |

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, year, measure, value, moe, measure_type | geoid, year, measure, value, moe, region_type |
| `measure_type` column | Present | Removed (not part of standard schema) |
| `region_type` column | Not present | `county` |
