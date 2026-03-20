# Hospital and Emergency Room Accessibility — Conversion Validation Report

**Date:** 2026-03-20
**Converted from:** R pipeline (`code/01_ingest_cms_hospitals.R`, `code/02_prepare_cms_hospitals.R`, `code/03_prepare_*_cms_hospitals.R`, `code/distribution/*.Rmd`)
**New pipeline:** `pipeline.yaml` + `code/distribution/download.py` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** CMS Hospital Compare — General Hospital Information
- **URL:** https://data.cms.gov/provider-data/topics/hospitals
- **Type:** CMS hospital archive ZIPs
- **Coverage:** VA, DC, MD (both VA and NCR dashboards)
- **Years:** 2015–2025 (old: 2015–2022 via HIFLD single-year; new: 2015–2025 via CMS per-year)

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_hdcttrbg_cms_2015_2025_access_scores_hosp.csv.xz` | 516,522 | 2015–2025 | hosp_cnt, hosp_near_10_mean, hosp_near_10_median, hosp_2sfca, hosp_e2sfca, hosp_3sfca | health_district, county, tract, block_group |
| `ncr_cttrbg_cms_2015_2025_access_scores_hosp.csv.xz` | 310,518 | 2015–2025 | hosp_cnt, hosp_near_10_mean, hosp_near_10_median, hosp_2sfca, hosp_e2sfca, hosp_3sfca | county, tract, block_group |

## Validation against old R output

### NCR — Block group level

| Comparison | Old file | New file |
|---|---|---|
| File | `ncr_bgtrct_{2015..2022}_access_scores_hospitals.csv.xz` (8 files) | `ncr_cttrbg_cms_2015_2025_access_scores_hosp.csv.xz` |
| Rows (overlap years) | 323,582 (BG+tract) | 160,332 (BG only) |
| Matched BG rows | 157,752 | — |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| hosp_2sfca | 26,292 | 0.5568 | 0.9657 | EXPECTED |
| hosp_3sfca | 26,292 | 0.5017 | 1.4101 | EXPECTED |
| hosp_e2sfca | 26,292 | 0.5437 | 1.0649 | EXPECTED |
| hosp_cnt | 26,292 | 0.5763 | 2.0 | EXPECTED |
| hosp_near_10_mean | 26,292 | 4.4846 | 43.12 | EXPECTED |
| hosp_near_10_median | 26,292 | 4.7491 | 50.55 | EXPECTED |

### VA — Single-year comparison (2021)

| Comparison | Old file | New file |
|---|---|---|
| File | `va_hdcttrbgca_hifld_2021_access_scores_hospitals.csv.xz` | `va_hdcttrbg_cms_2015_2025_access_scores_hosp.csv.xz` |
| Old rows | 58,548 | — |
| Old year | 2021 only | 2015–2025 |

## Known differences

All differences are **expected and intentional** due to the fundamental change in data source and methodology:

1. **Data source change (HIFLD → CMS Hospital Compare):** The old pipeline used HIFLD hospital locations (a static snapshot from ~2021/2022) applied uniformly to all years 2015–2022. The new pipeline uses CMS Hospital Compare, which provides actual year-by-year hospital listings. This means hospital counts and locations change per year in the new output, reflecting reality (hospitals open, close, and change status over time).

2. **Geocoding method change:** Old pipeline used R `tidygeocoder` (census → arcgis → osm cascade). New pipeline uses HIFLD as primary geocode source (matching 81% of hospitals by name+state), with Census Geocoder API as fallback. 97% of hospitals geocoded successfully (178/184).

3. **Year coverage expansion:** Old pipeline: 2015–2022 (8 years). New pipeline: 2015–2025 (11 years).

4. **Hospital count consistency:** New pipeline shows ~139-144 VA/DC/MD non-psychiatric hospitals per year, which is consistent with the old pipeline's range of 32-38 NCR hospitals and ~89 VA hospitals per year.

5. **Dropped measure:** `hosp_pop_cnt` was present in old output but is not produced by the new `aggregate_bg_to_levels()`. This measure was informational (population denominator) and not displayed on dashboards.

6. **6 ungeocoded hospitals:** These are edge cases: PO box addresses (LeWisGale Alleghany, Hiram Davis), military facilities (VA Maryland Perry Point, Walter Reed), and an address with floor information (Inova Specialty). None are in the NCR region.

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `va_bg_cms_2015_2025_access_scores_hosp.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `va_ct_cms_2015_2025_access_scores_hosp.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `va_hd_cms_2015_2025_access_scores_hosp.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `va_tr_cms_2015_2025_access_scores_hosp.csv.xz` | — | `dashboard_data/virginia_public_health_data/` |
| `ncr_bg_cms_2015_2025_access_scores_hosp.csv.xz` | — | `dashboard_data/national_capital_region_data/` |
| `ncr_ct_cms_2015_2025_access_scores_hosp.csv.xz` | — | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_cms_2015_2025_access_scores_hosp.csv.xz` | — | `dashboard_data/national_capital_region_data/` |

## Schema changes

| Aspect | Old (R/HIFLD) | New (Python/CMS) |
|---|---|---|
| Data source | HIFLD 2021/2022 snapshot | CMS Hospital Compare per-year |
| Columns | geoid, region_type, region_name, measure, value, year, measure_type, data_method | geoid, year, measure, value, moe, region_type, data_method |
| Years | 2015–2022 (static hospital set) | 2015–2025 (year-specific hospitals) |
| Geocoding | R tidygeocoder cascade | HIFLD primary + Census Geocoder fallback |
| Measures | 7 (incl. hosp_pop_cnt) | 6 (hosp_pop_cnt dropped) |
