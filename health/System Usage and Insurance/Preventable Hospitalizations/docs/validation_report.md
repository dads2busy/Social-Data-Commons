# Preventable Hospitalizations — Conversion Validation Report

**Date:** 2026-03-03
**Converted from:** `code/distribution/ingest.R` + `code/distribution/prepare.R`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** County Health Rankings (CHR), "Ranked Measure Data" sheet
- **Type:** county_health_rankings
- **Coverage:** VA
- **Years:** 2015-2021

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_county_health_rankings_2015_2021_preventable_hospitalizations.csv.xz` | 1148 | 2015-2021 | prevent_hosp_rate | county (903), health_district (245) |

## Validation against old R output

### VA county + health district

| Comparison | Old file | New file |
|---|---|---|
| File | `va_hdct_2015_2021_preventable_hospitalizations.csv.xz` | `va_county_health_rankings_2015_2021_preventable_hospitalizations.csv.xz` |
| Rows | 1180 (933 county + 245 HD + 2 state) | 1148 (903 county + 245 HD) |

| Measure | Level | Result |
|---|---|---|
| prevent_hosp_rate | county | **EXACT MATCH** — 903/903 rows, max diff 0.000000 |
| prevent_hosp_rate | health_district | **EXACT MATCH** — 245/245 rows, max diff 0.000000 |

### Row count difference

Old R output has 933 county rows (including 30 with NA values). New Python output has 903 county rows (NAs dropped). The 30-row difference is due to `dropna(subset=["value"])` in the CHR ingestion — the old R code retained NA rows.

### Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, year, measure, value, measure_type | geoid, year, measure, value, moe, region_type |
| NA handling | Kept as rows | Dropped |
| State row (51000) | Not included | Excluded by filter |

## Dashboard files

| File | Location |
|---|---|
| `va_ct_county_health_rankings_2015_2021_preventable_hospitalizations.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_hd_county_health_rankings_2015_2021_preventable_hospitalizations.csv.xz` | `dashboard_data/virginia_public_health_data/` |

## Status

**VALIDATED** — All county and health district values match exactly.
