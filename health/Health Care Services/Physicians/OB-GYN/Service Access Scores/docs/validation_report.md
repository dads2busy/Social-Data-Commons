# OB-GYN Service Access Scores — Conversion Validation Report

**Date:** 2026-03-20
**Converted from:** `code/01_ingest_cms_obgyn.R` + `code/distribution/2.catchment_scores_obgyn_*.Rmd`
**New pipeline:** `pipeline.yaml` + `code/distribution/download.py` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** CMS Doctors and Clinicians (previously WebMD Physician Directory)
- **Type:** cms_physicians
- **Coverage:** VA + NCR
- **Years:** 2017-2025 (previously single year 2021 from WebMD)

## Data source change

The pipeline was converted from WebMD physician directory scraping (single snapshot, 2021) to CMS Doctors and Clinicians enrollment data (2017-2025 annual). This is a **data source change**, not a simple code port, so values are expected to differ substantially.

Key differences:
- **WebMD** listed all physicians with an online profile (broader coverage, includes non-Medicare providers)
- **CMS** includes only Medicare-enrolled physicians with MD/DO credentials (narrower, but authoritative and annually updated)
- WebMD captured ~1,500+ unique OB-GYN locations in the NCR; CMS captures ~400-700 per year

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_hdcttrbg_cms_2017_2025_access_scores_obgyn.csv.xz` | 427,638 | 2017-2025 | 6 | health_district, county, tract, block_group |
| `ncr_cttrbg_cms_2017_2025_access_scores_obgyn.csv.xz` | 256,722 | 2017-2025 | 6 | county, tract, block_group |

## Measures produced

| Measure | Type | Data method |
|---|---|---|
| `obgyn_cnt` | count | observed |
| `obgyn_near_10_mean` | time (minutes) | observed |
| `obgyn_near_10_median` | time (minutes) | observed |
| `obgyn_2sfca` | index (per 1,000) | modeled |
| `obgyn_e2sfca` | index (per 1,000) | modeled |
| `obgyn_3sfca` | index (per 1,000) | modeled |

## Comparison against old output

### NCR (year 2021 overlap)

| Comparison | Old file | New file |
|---|---|---|
| File | `ncr_cttrbg_webmd_2021_access_scores_obgyn.csv.xz` | `ncr_cttrbg_cms_2017_2025_access_scores_obgyn.csv.xz` |
| Rows | 31,269 (1 year) | 256,722 (9 years) |
| Source | WebMD | CMS |

| Measure | Old mean (2021) | New mean (2021) | Ratio | Explanation |
|---|---|---|---|---|
| obgyn_2sfca | 1.0111 | 0.0981 | 0.10x | Fewer CMS providers = lower access ratio |
| obgyn_e2sfca | 1.0164 | 0.0980 | 0.10x | Same |
| obgyn_3sfca | 1.0043 | 0.0970 | 0.10x | Same |
| obgyn_cnt | 3.14 | 0.14 | 0.04x | CMS has fewer enrolled OB-GYNs |
| obgyn_near_10_mean | 4.74 min | 17.91 min | 3.8x | Fewer providers = longer travel |
| obgyn_near_10_median | 4.83 min | 18.71 min | 3.9x | Same |

### VA (year 2021 overlap)

| Comparison | Old file | New file |
|---|---|---|
| File | `va_hdcttrbgca_webmd_2021_access_scores_obgyn.csv.xz` | `va_hdcttrbg_cms_2017_2025_access_scores_obgyn.csv.xz` |
| Rows | 58,548 (1 year) | 427,638 (9 years) |
| Source | WebMD | CMS |

### Known differences

- **Data source change (WebMD to CMS):** All measures differ by approximately 10x (FCA scores) or 4x (travel times) due to the fundamental difference in provider coverage between WebMD (broad physician directory) and CMS (Medicare enrollment). CMS is the authoritative source and provides annual updates.
- **`obgyn_pop_cnt` removed:** The old pipeline included a consumer population count measure. The new pipeline does not produce this as it is not an access measure; population data is used internally as the FCA denominator.
- **Civic association aggregation removed:** The old VA output included `civic_association` region type. The new pipeline follows the standard pattern (BG, tract, county, health district).
- **`region_type` format:** Changed from "block group" to "block_group" (underscore-separated, matching standard schema).

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `va_bg_cms_2017_2025_access_scores_obgyn.csv.xz` | N/A | `dashboard_data/virginia_public_health_data/` |
| `va_ct_cms_2017_2025_access_scores_obgyn.csv.xz` | N/A | `dashboard_data/virginia_public_health_data/` |
| `va_hd_cms_2017_2025_access_scores_obgyn.csv.xz` | N/A | `dashboard_data/virginia_public_health_data/` |
| `va_tr_cms_2017_2025_access_scores_obgyn.csv.xz` | N/A | `dashboard_data/virginia_public_health_data/` |
| `ncr_bg_cms_2017_2025_access_scores_obgyn.csv.xz` | N/A | `dashboard_data/national_capital_region_data/` |
| `ncr_ct_cms_2017_2025_access_scores_obgyn.csv.xz` | N/A | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_cms_2017_2025_access_scores_obgyn.csv.xz` | N/A | `dashboard_data/national_capital_region_data/` |

## Schema changes

| Aspect | Old (R/WebMD) | New (Python/CMS) |
|---|---|---|
| Data source | WebMD physician directory | CMS Doctors and Clinicians |
| Years | 2021 (single) | 2017-2025 (9 years, annual) |
| Measures | 7 (incl. pop_cnt) | 6 |
| Region types (VA) | block group, civic association, county, health district, tract | block_group, county, health_district, tract |
| Region types (NCR) | block group, county, tract | block_group, county, tract |
| Population denominator | Female age 15+ (ACS B01001_030-049) | Female age 15+ (ACS B01001_030-049) — unchanged |

## Geocoding statistics

- Total unique addresses across 2017-2025: 1,250
- Successfully geocoded: 1,091 (87%)
- Failed: 159 (13%) — dropped from analysis
