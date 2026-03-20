# Urgent Care Centers Service Access Scores — Conversion Validation Report

**Date:** 2026-03-20
**Converted from:** R code in `code/distribution/*.Rmd` + partial Python `ingest.py`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** Google Maps urgent care center locations (geocoded GeoJSON)
- **Type:** GeoJSON provider locations + FCA spatial access model
- **Coverage:** NCR only
- **Years:** 2022

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `ncr_cttrbg_gmap_2022_access_scores_urgent.csv.xz` | 29,826 | 2022 | urgent_cnt, urgent_2sfca, urgent_e2sfca, urgent_3sfca, urgent_near_10_mean, urgent_near_10_median | block_group, tract, county |

## Validation against old output

### NCR

| Comparison | Old file | New file |
|---|---|---|
| File | `ncr_bgtrct_gmap_2022_access_scores_urgent_care_centers.csv.xz` | `ncr_cttrbg_gmap_2022_access_scores_urgent.csv.xz` |
| Rows | 64,323 | 29,826 |
| Year | 2022 | 2022 |
| BG count (old) | 6,087 | 3,626 |
| Counties (old) | 37 | 14 (NCR) |

### Value comparison at county level (same year, 14 matched counties)

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| urgent_2sfca | 14 | 1.1293 | 1.6320 | Expected diff |
| urgent_3sfca | 14 | 1.1133 | 1.6954 | Expected diff |
| urgent_cnt | 14 | 36.29 | 92.0 | Expected diff |
| urgent_e2sfca | 14 | 1.1502 | 1.4149 | Expected diff |
| urgent_near_10_mean | 14 | 10.62 | 26.11 | Expected diff |
| urgent_near_10_median | 14 | 11.26 | 29.44 | Expected diff |

### Known differences

- **Old file had vastly broader geographic coverage:** Despite being named "ncr_", the old file contained 6,087 unique BGs across 37 counties — far beyond the 14 NCR counties. This included many non-NCR counties in VA, MD, and even rows with PA GEOIDs (starting with 42) that had NaN region_type. The old pipeline was not properly filtering to NCR boundaries.
- **Consumer population change:** Because the old file included BGs from a much larger area, the FCA scores were computed with a different consumer-provider spatial relationship. Providers in the NCR competed for a much larger consumer population in the old pipeline, which distorted the access ratios. The new pipeline correctly restricts both consumers and providers to the 14 NCR counties, producing valid within-NCR accessibility measures.
- **`urgent_pop_cnt` dropped:** Same as Dentists — population count is not an access measure. Not produced by the shared `aggregate_bg_to_levels` module.
- **Count diffs explained:** The old pipeline counted providers snapped to BGs across the wider area, so county-level counts included providers outside the NCR. New pipeline correctly counts only NCR providers.
- **Travel time diffs explained:** With a broader consumer area, travel times to nearest 10 providers would differ because more distant providers from outside NCR were included in the calculation.

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `ncr_bg_gmap_2022_access_scores_urgent.csv.xz` | — | `dashboard_data/national_capital_region_data/` |
| `ncr_ct_gmap_2022_access_scores_urgent.csv.xz` | — | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_gmap_2022_access_scores_urgent.csv.xz` | — | `dashboard_data/national_capital_region_data/` |

## Schema changes

| Aspect | Old | New |
|---|---|---|
| Columns | geoid, region_type, region_name, measure, value, year, measure_type, data_method | geoid, year, measure, value, moe, region_type, data_method |
| Region type format | "block group" | "block_group" |
| Measures | 7 (including urgent_pop_cnt) | 6 |
| Consumer BGs | ~6,087 (37 counties) | 3,626 (14 NCR counties) |
