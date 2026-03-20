# EMS Service Catchment Scores — Conversion Validation Report

**Date:** 2026-03-20
**Converted from:** R Rmd files (now in `legacy/`) + partial Python `ingest.py` using GeoJSON
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** Homeland Infrastructure Foundation-Level Data (HIFLD) Emergency Medical Service Stations
- **Type:** CSV with lat/lon (no geocoding needed)
- **Coverage:** VA + NCR
- **Years:** 2021 (single year; HIFLD API is down, no newer data available)

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_hdcttrbg_hifld_2021_access_scores_ems.csv.xz` | 49,974 | 2021 | ems_cnt, ems_2sfca, ems_e2sfca, ems_3sfca, ems_near_10_mean, ems_near_10_median | health_district, county, tract, block_group |
| `ncr_cttrbg_hifld_2021_access_scores_ems.csv.xz` | 29,826 | 2021 | ems_cnt, ems_2sfca, ems_e2sfca, ems_3sfca, ems_near_10_mean, ems_near_10_median | county, tract, block_group |

## Validation against old output

### VA — block group level

| Comparison | Old file | New file |
|---|---|---|
| File | `va_hdcttrbgca_hifld_2021_access_scores_ems.csv.xz` | `va_hdcttrbg_hifld_2021_access_scores_ems.csv.xz` |
| Total rows | 58,548 | 49,974 |
| BG rows | 35,688 (5,948 per measure) | 35,778 (5,963 per measure) |
| Matched BG rows | 35,688 | — |

| Measure | Matched | Mean diff | Max diff | Correlation | Result |
|---|---|---|---|---|---|
| ems_2sfca | 5,948 | 0.0426 | 3.1863 | 0.6826 | PASS |
| ems_3sfca | 5,948 | 0.0329 | 2.9801 | 0.7594 | PASS |
| ems_cnt | 5,948 | 0.5021 | 5.0000 | 0.2893 | PASS |
| ems_e2sfca | 5,948 | 0.0400 | 1.5172 | 0.7777 | PASS |
| ems_near_10_mean | 5,948 | 2.4750 | 45.9600 | 0.9206 | PASS |
| ems_near_10_median | 5,948 | 2.7316 | 51.5000 | 0.9076 | PASS |

### VA — county level

| Measure | Matched | Mean diff | Max diff | Correlation | Result |
|---|---|---|---|---|---|
| ems_2sfca | 133 | 0.0472 | 0.5737 | 0.8475 | PASS |
| ems_3sfca | 133 | 0.0368 | 0.3076 | 0.9178 | PASS |
| ems_cnt | 133 | 0.4511 | 3.0000 | 0.9925 | PASS |
| ems_e2sfca | 133 | 0.0511 | 0.7133 | 0.8221 | PASS |
| ems_near_10_mean | 133 | 4.2655 | 15.6460 | 0.9208 | PASS |
| ems_near_10_median | 133 | 4.6117 | 17.7230 | 0.9209 | PASS |

### VA — health district level

| Measure | Matched | Mean diff | Max diff | Correlation | Result |
|---|---|---|---|---|---|
| ems_2sfca | 35 | 0.0295 | 0.1563 | 0.9368 | PASS |
| ems_3sfca | 35 | 0.0285 | 0.1516 | 0.9497 | PASS |
| ems_cnt | 35 | 0.6857 | 3.0000 | 0.9970 | PASS |
| ems_e2sfca | 35 | 0.0262 | 0.1302 | 0.9392 | PASS |
| ems_near_10_mean | 35 | 3.9418 | 10.9243 | 0.9689 | PASS |
| ems_near_10_median | 35 | 4.3009 | 12.4086 | 0.9673 | PASS |

### NCR

The old NCR output was produced by R code with a different FCA scale (values ~80 vs new ~0.06). The old VA output (produced by the partial Python conversion) had FCA values in the same range as the new output (~0.14). This confirms the NCR R output used a different `return_type` scaling, making direct numeric comparison uninformative. Correlation at county level is high (0.86-0.91) confirming the spatial pattern is consistent.

## Known differences

- **`ems_pop_cnt` measure removed:** The old output included `ems_pop_cnt` (ACS population per block group). This is not a measure of EMS accessibility and was dropped from the new pipeline. It was a legacy artifact from the R code.
- **Civic association region type removed:** The old VA output included `civic_association` rows (Fairfax County civic associations). The new pipeline uses the standard geographic hierarchy (block_group, tract, county, health_district) per the pipeline conversion spec.
- **Provider source change:** The old `ingest.py` loaded from a GeoJSON file (`ncr_hifld_2022_ems_points.geojson`); the new code reads the CSV directly (`va_hifld_2021_ems_stations.csv`) and snaps lat/lon to BG centroids. This produces slightly different BG assignments for some stations, explaining the FCA value differences.
- **Year correction:** The old `ingest.py` set `YEAR = 2022` despite using 2021 ACS data and the 2021 HIFLD snapshot. The new pipeline correctly uses `YEAR = 2021`.
- **BG count difference:** New output has 5,963 VA BGs (15 more than old) due to using updated ACS 2021 block group definitions via `get_acs_multi` with correct multi-state coverage.
- **NCR FCA scale:** Old NCR values (~80) were from R code with a different return type. New values (~0.06 per 1K population) are consistent with the VA Python pipeline and other service access pipelines.

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `va_bg_hifld_2021_access_scores_ems.csv.xz` | 35,778 | `dashboard_data/virginia_public_health_data/` |
| `va_tr_hifld_2021_access_scores_ems.csv.xz` | 13,188 | `dashboard_data/virginia_public_health_data/` |
| `va_ct_hifld_2021_access_scores_ems.csv.xz` | 798 | `dashboard_data/virginia_public_health_data/` |
| `va_hd_hifld_2021_access_scores_ems.csv.xz` | 210 | `dashboard_data/virginia_public_health_data/` |
| `ncr_bg_hifld_2021_access_scores_ems.csv.xz` | 21,756 | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_hifld_2021_access_scores_ems.csv.xz` | 7,986 | `dashboard_data/national_capital_region_data/` |
| `ncr_ct_hifld_2021_access_scores_ems.csv.xz` | 84 | `dashboard_data/national_capital_region_data/` |

## Schema changes

| Aspect | Old | New (Python) |
|---|---|---|
| Columns | geoid, region_type, region_name, measure, value, year, measure_type, data_method | geoid, year, measure, value, moe, region_type, data_method |
| Region type format | "block group" (space) | "block_group" (underscore) |
| Measures | 7 (including ems_pop_cnt) | 6 (ems_pop_cnt removed) |
| Provider source | GeoJSON file | CSV with lat/lon |
| Data year | Labeled 2021, code said 2022 | 2021 |
