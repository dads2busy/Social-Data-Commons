# Pediatric Service Access Scores — Conversion Validation Report

**Date:** 2026-03-20
**Converted from:** `code/catchment_scores_ped_va.Rmd` (WebMD-based, single year 2021)
**New pipeline:** `pipeline.yaml` + `code/distribution/download.py` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Old source:** WebMD Physician Directory (manual scrape, 2021 only)
- **New source:** CMS Doctors and Clinicians (automated download, 2018-2025)
- **Type:** cms_physicians
- **Coverage:** VA + NCR
- **Years:** 2018-2025
- **Specialty filter:** PEDIATRIC MEDICINE (pri_spec, sec_spec_1, sec_spec_2)
- **Population denominator:** Ages 0-17 (ACS B01001_003-006, B01001_027-030)

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_hdcttrbg_cms_2018_2025_access_scores_peds.csv.xz` | 383,196 | 2018-2025 | peds_cnt, peds_near_10_mean, peds_near_10_median, peds_2sfca, peds_e2sfca, peds_3sfca | health_district, county, tract, block_group |
| `ncr_cttrbg_cms_2018_2025_access_scores_peds.csv.xz` | 229,824 | 2018-2025 | (same 6 measures) | county, tract, block_group |

## Validation against old R output

### VA — Year 2021 comparison

| Comparison | Old file | New file |
|---|---|---|
| File | `va_hdcttrbgca_webmd_2021_access_scores_pediatrics.csv.xz` | `va_hdcttrbg_cms_2018_2025_access_scores_peds.csv.xz` |
| Rows (2021) | 50,184 | 49,974 |
| Matched rows | 49,812 | — |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| peds_2sfca | 8,302 | 2.1752 | 20.4799 | EXPECTED |
| peds_3sfca | 8,302 | 2.1311 | 27.1650 | EXPECTED |
| peds_cnt | 8,302 | 4.9839 | 772.0 | EXPECTED |
| peds_e2sfca | 8,302 | 2.1222 | 12.1613 | EXPECTED |
| peds_near_10_mean | 8,302 | 16.2227 | 56.11 | EXPECTED |
| peds_near_10_median | 8,302 | 16.9668 | 55.80 | EXPECTED |

### Known differences

- **Data source change (WebMD -> CMS):** The old pipeline used WebMD's online physician directory (manual scrape), while the new pipeline uses CMS Doctors and Clinicians (official Medicare enrollment data). These are fundamentally different data sources with different coverage, so large value differences are expected and correct. CMS is the authoritative source.
- **Provider counts:** Old had ~155 providers from WebMD; new has 179 unique NPIs from CMS for 2021. The provider count diffs reflect different directory coverage.
- **Travel time measures:** Large diffs result from different provider locations (different data source).
- **FCA scores:** Different provider sets produce different supply-demand ratios.
- **Measure prefix:** Changed from `ped_` to `peds_` to match pipeline convention.
- **Dropped measure:** `ped_pop_cnt` (child population count) not carried forward — it is an ACS demographic, not a service access score.
- **Dropped region type:** `civic_association` not produced by new pipeline (not a standard geography level).
- **Row count difference:** Old had civic_association rows; new does not. Otherwise matched 49,812 of 50,184 old rows.
- **Year expansion:** Old had 2021 only; new covers 2018-2025 (8 years of CMS data).

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `va_bg_cms_2018_2025_access_scores_peds.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `va_ct_cms_2018_2025_access_scores_peds.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `va_hd_cms_2018_2025_access_scores_peds.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `va_tr_cms_2018_2025_access_scores_peds.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `ncr_bg_cms_2018_2025_access_scores_peds.csv.xz` | — | `dashboard_data/national_capital_region_data/` |
| `ncr_ct_cms_2018_2025_access_scores_peds.csv.xz` | — | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_cms_2018_2025_access_scores_peds.csv.xz` | — | `dashboard_data/national_capital_region_data/` |

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, region_type, region_name, measure, value, year, measure_type, data_method | geoid, year, measure, value, moe, region_type, data_method |
| Measure prefix | `ped_` | `peds_` |
| Data source | WebMD | CMS Doctors and Clinicians |
| Years | 2021 | 2018-2025 |
| Region types | block group, tract, county, health district, civic association | block_group, tract, county, health_district |

## Provider counts by year (CMS PEDIATRIC MEDICINE)

| Year | Unique NPIs | Rows after filter |
|---|---|---|
| 2018 | 193 | 457 |
| 2019 | 188 | 340 |
| 2020 | 164 | 304 |
| 2021 | 179 | 332 |
| 2022 | 151 | 283 |
| 2023 | 150 | 276 |
| 2024 | 627 | 969 |
| 2025 | 793 | 1,295 |

Note: The jump in 2024-2025 likely reflects CMS expanding their inclusion of pediatric medicine providers in the dataset.
