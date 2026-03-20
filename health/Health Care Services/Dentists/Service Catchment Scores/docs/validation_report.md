# Dentists Service Catchment Scores — Conversion Validation Report

**Date:** 2026-03-20
**Converted from:** R code in `code/distribution/*.Rmd` + partial Python `ingest.py`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** WebMD Physician Directory (geocoded GeoJSON)
- **Type:** GeoJSON provider locations + FCA spatial access model
- **Coverage:** NCR only
- **Years:** 2022

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `ncr_cttrbg_webmd_2022_access_scores_dent.csv.xz` | 29,826 | 2022 | dent_cnt, dent_2sfca, dent_e2sfca, dent_3sfca, dent_near_10_mean, dent_near_10_median | block_group, tract, county |

## Validation against old output

### NCR

| Comparison | Old file | New file |
|---|---|---|
| File | `ncr_cttrbg_webmd_2021_access_scores_dentists.csv.xz` | `ncr_cttrbg_webmd_2022_access_scores_dent.csv.xz` |
| Rows | 31,269 | 29,826 |
| Year | 2021 | 2022 |
| BG count | 3,235 | 3,626 |
| Counties | 14 (NCR) | 14 (NCR) |

**Note:** Old and new files use different data years (2021 vs 2022), so exact value matching is not possible.

### Structural comparison

| Level | Old rows (per measure) | New rows (per measure) |
|---|---|---|
| block_group | 3,235 | 3,626 |
| tract | 1,218 | 1,331 |
| county | 14 | 14 |

### Known differences

- **Year change:** Old file is year=2021 (ACS 2020 population), new is year=2022 (ACS 2021 population). Value comparison not meaningful across years.
- **BG count increase (3,235 -> 3,626):** Old pipeline only fetched VA BGs (state=51) and missed MD and DC block groups within NCR counties. New pipeline fetches VA+MD+DC (states 51, 24, 11) and correctly includes all NCR BGs.
- **`dent_pop_cnt` dropped:** Old file included a population count measure (`dent_pop_cnt`) that is not a provider access measure. The new pipeline uses `aggregate_bg_to_levels` from the shared module which does not produce this measure. This is intentional — population counts are not a dental access metric.
- **VA output removed:** Old pipeline produced both VA (`va_hdcttrbgca_webmd_2021_access_scores_dentists.csv.xz`) and NCR output. The provider GeoJSON only covers the NCR region, so the VA output was invalid (it only had NCR-area providers projected across all VA BGs). New pipeline correctly produces NCR output only.

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `ncr_bg_webmd_2022_access_scores_dent.csv.xz` | — | `dashboard_data/national_capital_region_data/` |
| `ncr_ct_webmd_2022_access_scores_dent.csv.xz` | — | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_webmd_2022_access_scores_dent.csv.xz` | — | `dashboard_data/national_capital_region_data/` |

## Schema changes

| Aspect | Old | New |
|---|---|---|
| Columns | geoid, region_type, region_name, measure, value, year, measure_type, data_method | geoid, year, measure, value, moe, region_type, data_method |
| Region type format | "block group" | "block_group" |
| Measures | 7 (including dent_pop_cnt) | 6 |
| Consumer BGs | VA only (3,235) | VA+MD+DC (3,626) |
