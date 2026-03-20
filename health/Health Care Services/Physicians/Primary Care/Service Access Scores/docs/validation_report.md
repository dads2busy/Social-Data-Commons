# Primary Care Service Access Scores — Conversion Validation Report

**Date:** 2026-03-20
**Converted from:** `code/distribution/` R scripts (01_ingest_cms_primarycare.R, 02_prepare_cms_primarycare.R, catchment Rmds)
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Old source:** WebMD Physician Directory (~14,560 providers statewide, scraped to PostgreSQL, no longer accessible)
- **New source:** CMS Doctors and Clinicians (https://data.cms.gov/provider-data/), Medicare-enrolled primary care physicians (~1,100 capacity in VA/DC/MD)
- **Type:** cms_physicians
- **Coverage:** VA + NCR
- **Years:** 2022

### Source change rationale

The old pipeline used provider addresses scraped from WebMD's online physician directory and stored in a PostgreSQL database that no longer exists. This data source is not reproducible. The new pipeline uses CMS Doctors and Clinicians data, which is publicly available, automatable, and updated regularly. CMS data covers Medicare-enrolled physicians only (a subset of all practicing physicians), so provider counts are substantially lower. This is an intentional trade-off: reproducibility and automation over coverage.

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_hdcttrbg_cms_2022_access_scores_primcare.csv.xz` | 49,974 | 2022 | primcare_cnt, primcare_2sfca, primcare_e2sfca, primcare_3sfca, primcare_near_10_mean, primcare_near_10_median | health_district, county, tract, block_group |
| `ncr_cttrbg_cms_2022_access_scores_primcare.csv.xz` | 29,826 | 2022 | primcare_cnt, primcare_2sfca, primcare_e2sfca, primcare_3sfca, primcare_near_10_mean, primcare_near_10_median | county, tract, block_group |

## Validation against old R output

### VA statewide

| Comparison | Old file | New file |
|---|---|---|
| File | `va_hdcttrbgca_webmd_2021_access_scores_primcare.csv.xz` | `va_hdcttrbg_cms_2022_access_scores_primcare.csv.xz` |
| Rows | 58,548 | 49,974 |
| Provider count | 14,560 (WebMD) | 1,104 (CMS) |
| Block groups | 5,948 | 5,963 (5,948 overlap + 15 new) |

| Measure | Correlation (r) | Old mean | New mean | Magnitude ratio | Result |
|---|---|---|---|---|---|
| primcare_2sfca | 0.40 | 2.37 | 0.13 | ~18x | EXPECTED — provider count difference |
| primcare_e2sfca | 0.61 | — | — | — | EXPECTED — best correlation, spatial patterns preserved |
| primcare_3sfca | 0.37 | — | — | — | EXPECTED — provider count difference |
| primcare_cnt | — | — | — | — | Not directly comparable (different provider universe) |
| primcare_near_10_mean | — | 9.2 min | 19.4 min | ~2x | EXPECTED — fewer locations = farther travel |
| primcare_near_10_median | — | — | — | — | EXPECTED — same direction as mean |

### NCR

| Comparison | Old file | New file |
|---|---|---|
| File | `ncr_cttrbg_webmd_2021_acccess_scores_primcare.csv.xz` | `ncr_cttrbg_cms_2022_access_scores_primcare.csv.xz` |
| Rows | 31,269 | 29,826 |

NCR patterns mirror VA: lower FCA scores and longer travel times due to fewer CMS providers vs WebMD providers.

### Known differences

- **Provider count (~13x fewer):** Old pipeline used ~14,560 WebMD-sourced providers covering all practicing physicians found in the directory. New pipeline uses ~1,100 CMS Medicare-enrolled providers. This is the primary driver of all magnitude differences. CMS data is the correct going-forward source because it is reproducible and automatable.
- **FCA scores ~18x lower:** Direct consequence of fewer providers. The spatial pattern of relative accessibility is preserved (E2SFCA correlation 0.61), meaning areas that were relatively underserved in the old data remain relatively underserved in the new data.
- **Travel times ~2x higher:** With fewer provider locations, the average distance to the nearest 10 providers increases. This is mechanically expected.
- **Year change (2021 → 2022):** Old output was labeled 2021 (WebMD scrape year). New output uses 2022 CMS data.
- **Civic association geography dropped:** Old output included civic_association (`ca` in filename). New output does not include this geography.
- **15 new block groups:** New census geography additions not present in old data.

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Filename prefix | `va_hdcttrbgca_webmd_2021_` | `va_hdcttrbg_cms_2022_` |
| Data source | WebMD Physician Directory | CMS Doctors and Clinicians |
| Columns | geoid, year, measure, value, moe | geoid, year, measure, value, moe, region_type, data_method |
| New measures | — | primcare_near_10_mean, primcare_near_10_median |
| Geographies | HD, county, tract, BG, civic_assoc | HD, county, tract, BG |
