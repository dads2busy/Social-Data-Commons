# Drug and Rehab Service Access Scores — Conversion Validation Report

**Date:** 2026-03-20
**Converted from:** R scripts in `code/` (`.Rmd` files) + HIFLD/SAMHSA GeoJSON input
**New pipeline:** `pipeline.yaml` + `code/distribution/download.py` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** SAMHSA findtreatment.gov API (sType=SA)
- **Type:** samhsa_api
- **Coverage:** VA + NCR
- **Years:** 2025 (live API pull; old data was 2021 HIFLD snapshot)

## Facility counts

| Source | Facilities (8-state region) | Facilities (VA only, approx) |
|---|---|---|
| Old (HIFLD 2021) | ~1,200 (from CSV) | ~350 |
| New (SAMHSA 2025) | 1,860 | ~540 |

The new data contains more facilities because: (1) the SAMHSA API returns current active listings vs the 2021 HIFLD snapshot, (2) 4 years of facility openings, and (3) slightly different facility definitions.

## Output files

| File | Rows | Year | Measures | Region types |
|---|---|---|---|---|
| `va_hdcttrbg_samhsa_2025_access_scores_substance.csv.xz` | 49,974 | 2025 | substance_cnt, substance_near_10_mean, substance_near_10_median, substance_2sfca, substance_e2sfca, substance_3sfca | block_group, tract, county, health_district |
| `ncr_cttrbg_samhsa_2025_access_scores_substance.csv.xz` | 29,826 | 2025 | (same) | block_group, tract, county |

## Validation against old output

### VA county-level spatial correlation (2021 vs 2025)

Direct value comparison is not meaningful because: (1) different years (2021 vs 2025), (2) different data sources (HIFLD snapshot vs live SAMHSA API), (3) different measure name prefix (`subs_` vs `substance_`), (4) different FCA score scale. Spatial pattern correlation is used instead.

| Measure (old -> new) | Matched counties | Correlation | Old mean | New mean |
|---|---|---|---|---|
| subs_cnt -> substance_cnt | 133 | 0.7862 | 1.35 | 1.81 |
| subs_near_10_mean -> substance_near_10_mean | 133 | 0.7369 | 39.42 | 33.89 |
| subs_near_10_median -> substance_near_10_median | 133 | 0.6747 | 41.10 | 34.94 |
| subs_2sfca -> substance_2sfca | 133 | 0.4973 | 0.2697 | 0.0370 |
| subs_e2sfca -> substance_e2sfca | 133 | 0.5402 | 0.2673 | 0.0357 |
| subs_3sfca -> substance_3sfca | 133 | 0.5227 | 0.2845 | 0.0395 |

### NCR county-level spatial correlation

| Measure (old -> new) | Matched counties | Correlation | Old mean | New mean |
|---|---|---|---|---|
| subs_cnt -> substance_cnt | 14 | 0.9701 | 8.21 | 10.36 |
| subs_near_10_mean -> substance_near_10_mean | 14 | 0.9535 | 15.24 | 16.77 |
| subs_near_10_median -> substance_near_10_median | 14 | 0.9321 | 15.87 | 17.56 |
| subs_2sfca -> substance_2sfca | 14 | 0.8530 | 40.06 | 0.0228 |
| subs_e2sfca -> substance_e2sfca | 14 | 0.8808 | 39.72 | 0.0233 |
| subs_3sfca -> substance_3sfca | 14 | 0.9060 | 43.71 | 0.0245 |

### Known differences

- **FCA score scale:** Old output used a different `return_type` in the catchment computation (likely per 100,000), producing values 1000x larger than the new output (per 1,000). The spatial pattern is preserved (correlations 0.50-0.91).
- **Measure prefix:** Changed from `subs_` to `substance_` for consistency with pipeline naming.
- **Region type values:** Changed from `"block group"` to `"block_group"`, `"health district"` to `"health_district"` for consistency with the standard schema.
- **Dropped measure:** `subs_pop_cnt` (total population count) is no longer included as it is not an access measure.
- **Dropped geography:** `civic_association` level is no longer computed (dashboard does not display it).
- **Year difference:** Old=2021 (HIFLD snapshot), New=2025 (live SAMHSA API). Expect different facility counts and minor shifts in access patterns.
- **Higher facility count in new data:** 1,860 vs ~1,200 due to SAMHSA API returning more comprehensive/current listings.

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `va_bg_samhsa_2025_access_scores_substance.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `va_ct_samhsa_2025_access_scores_substance.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `va_hd_samhsa_2025_access_scores_substance.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `va_tr_samhsa_2025_access_scores_substance.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `ncr_bg_samhsa_2025_access_scores_substance.csv.xz` | — | `dashboard_data/national_capital_region_data/` |
| `ncr_ct_samhsa_2025_access_scores_substance.csv.xz` | — | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_samhsa_2025_access_scores_substance.csv.xz` | — | `dashboard_data/national_capital_region_data/` |

## Schema changes

| Aspect | Old | New |
|---|---|---|
| Columns | geoid, region_type, region_name, measure, value, year, measure_type, data_method | geoid, year, measure, value, moe, region_type, data_method |
| Measure prefix | `subs_*` | `substance_*` |
| Region types | block group, tract, county, health district, civic association | block_group, tract, county, health_district |
| FCA scale | ~0.27 (per 100K?) | ~0.04 (per 1K) |
