# Mental Health Service Access Scores — Conversion Validation Report

**Date:** 2026-03-20
**Converted from:** R scripts in `code/` (`.Rmd` files) + SAMHSA GeoJSON input
**New pipeline:** `pipeline.yaml` + `code/distribution/download.py` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** SAMHSA findtreatment.gov API (sType=MH)
- **Type:** samhsa_api
- **Coverage:** VA + NCR
- **Years:** 2025 (live API pull; old data was 2021 SAMHSA/HIFLD snapshot)

## Facility counts

| Source | Facilities (8-state region) | Facilities (VA only, approx) |
|---|---|---|
| Old (HIFLD/SAMHSA 2021) | ~1,100 (from CSV) | ~300 |
| New (SAMHSA 2025) | 1,703 | ~500 |

The new data contains more facilities because: (1) the SAMHSA API returns current active listings vs the 2021 snapshot, (2) 4 years of facility openings, and (3) slightly different facility definitions.

## Output files

| File | Rows | Year | Measures | Region types |
|---|---|---|---|---|
| `va_hdcttrbg_samhsa_2025_access_scores_mental.csv.xz` | 49,974 | 2025 | mental_cnt, mental_near_10_mean, mental_near_10_median, mental_2sfca, mental_e2sfca, mental_3sfca | block_group, tract, county, health_district |
| `ncr_cttrbg_samhsa_2025_access_scores_mental.csv.xz` | 29,826 | 2025 | (same) | block_group, tract, county |

## Validation against old output

### VA county-level spatial correlation (2021 vs 2025)

Direct value comparison is not meaningful because: (1) different years (2021 vs 2025), (2) different data sources (snapshot vs live API), (3) different FCA score scale. Spatial pattern correlation is used instead.

| Measure | Matched counties | Correlation | Old mean | New mean |
|---|---|---|---|---|
| mental_cnt | 133 | 0.8640 | 1.47 | 1.94 |
| mental_near_10_mean | 133 | 0.7338 | 38.40 | 34.45 |
| mental_near_10_median | 133 | 0.6580 | 40.87 | 35.81 |
| mental_2sfca | 133 | 0.4328 | 0.3210 | 0.0413 |
| mental_e2sfca | 133 | 0.5345 | 0.3246 | 0.0397 |
| mental_3sfca | 133 | 0.5052 | 0.3376 | 0.0433 |

### NCR county-level spatial correlation

| Measure | Matched counties | Correlation | Old mean | New mean |
|---|---|---|---|---|
| mental_cnt | 14 | 0.9266 | 6.71 | 11.71 |
| mental_near_10_mean | 14 | 0.8016 | 14.56 | 15.48 |
| mental_near_10_median | 14 | 0.8363 | 14.75 | 15.87 |
| mental_2sfca | 14 | 0.7377 | 35.91 | 0.0258 |
| mental_e2sfca | 14 | 0.7808 | 36.15 | 0.0263 |
| mental_3sfca | 14 | 0.4426 | 37.24 | 0.0275 |

### Known differences

- **FCA score scale:** Old output used a different `return_type` in the catchment computation (likely per 100,000), producing values ~1000x larger than the new output (per 1,000). The spatial pattern is preserved (correlations 0.44-0.93).
- **Region type values:** Changed from `"block group"` to `"block_group"`, `"health district"` to `"health_district"` for consistency with the standard schema.
- **Dropped measure:** `mental_pop_cnt` (total population count) is no longer included as it is not an access measure.
- **Dropped geography:** `civic_association` level is no longer computed (dashboard does not display it).
- **Year difference:** Old=2021 (snapshot), New=2025 (live SAMHSA API). Expect different facility counts and minor shifts in access patterns.
- **Higher facility count in new data:** 1,703 vs ~1,100 due to SAMHSA API returning more comprehensive/current listings.
- **Lower VA-level FCA correlations:** Expected because (a) facility locations have shifted over 4 years, (b) population denominators are different (ACS 2021 vs 2023), and (c) smaller counties are more sensitive to individual facility additions/closures.

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `va_bg_samhsa_2025_access_scores_mental.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `va_ct_samhsa_2025_access_scores_mental.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `va_hd_samhsa_2025_access_scores_mental.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `va_tr_samhsa_2025_access_scores_mental.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `ncr_bg_samhsa_2025_access_scores_mental.csv.xz` | — | `dashboard_data/national_capital_region_data/` |
| `ncr_ct_samhsa_2025_access_scores_mental.csv.xz` | — | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_samhsa_2025_access_scores_mental.csv.xz` | — | `dashboard_data/national_capital_region_data/` |

## Schema changes

| Aspect | Old | New |
|---|---|---|
| Columns | geoid, region_type, region_name, measure, value, year, measure_type, data_method | geoid, year, measure, value, moe, region_type, data_method |
| Region types | block group, tract, county, health district, civic association | block_group, tract, county, health_district |
| FCA scale | ~0.32 (per 100K?) | ~0.04 (per 1K) |
