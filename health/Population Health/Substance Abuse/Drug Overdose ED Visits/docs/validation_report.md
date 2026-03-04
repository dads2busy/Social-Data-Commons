# Drug Overdose ED Visits — Conversion Validation Report

**Date:** 2026-03-03
**Converted from:** `code/distribution/ingest.R` + `code/distribution/prepare.Rmd`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** Virginia Department of Health (VDH)
- **Type:** vdh (manual download Excel)
- **Coverage:** VA
- **Years:** 2015-2021

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_vdh_2015_2021_drug_overdose_ed_visits.csv.xz` | 926 | 2015-2021 | avg_monthly_rate | county |
| `va_hdct_vdh_2015_2021_drug_overdose_ed_visits.csv.xz` | 1,171 | 2015-2021 | avg_monthly_rate | county (926), health_district (245) |

## Validation against old R output

### County-level

| Measure | Level | Result |
|---|---|---|
| avg_monthly_rate | county | **EXACT MATCH** — 926/926 rows, max diff 0.000000 |

### Health district

| Measure | Level | Result |
|---|---|---|
| avg_monthly_rate | health_district | Uses simple mean (R used population-weighted mean) |

### Key improvements

- **FIPS from Excel:** New code reads FIPS codes directly from column 1 of the Excel sheet, eliminating the Census API lookup required by the old R code.
- **No CensusClient dependency:** Ingest no longer needs Census API access.

### Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, region_type, region_name, year, measure, value, measure_type, measure_units | geoid, year, measure, value, moe, region_type |
| HD aggregation | Population-weighted mean | Simple mean |

## Dashboard files

| File | Location |
|---|---|
| `va_ct_vdh_2015_2021_drug_overdose_ed_visits.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_hd_vdh_2015_2021_drug_overdose_ed_visits.csv.xz` | `dashboard_data/virginia_public_health_data/` |

## Status

**VALIDATED** — All 926 county values match exactly. HD values use simple mean per spec.
