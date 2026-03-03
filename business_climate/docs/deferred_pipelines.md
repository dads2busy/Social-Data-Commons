# Business Climate — Deferred Pipeline Report

**Date:** 2026-03-03

## Overview

The following business_climate pipelines were evaluated for Python conversion and **deferred** because they fail the qualification checklist (spec section 0). All depend on Mergent Intellect, a commercial microdata source with no API or automated refresh strategy.

## Deferred pipelines

### Business_characteristics (4 subtopics)

| Subtopic | Output file | Rows |
|---|---|---|
| Total | `{prefix}_cttrbg_mi_2010_2020_business_metrics_by_Total.csv.xz` | varies |
| Minority_owned | `{prefix}_cttrbg_mi_2010_2020_business_metrics_by_Minority_owned.csv.xz` | varies |
| Industry | `{prefix}_cttrbg_mi_2010_2020_business_metrics_by_Industry.csv.xz` | varies |
| Industry_Minority_owned | `{prefix}_cttrbg_mi_2010_2020_business_metrics_by_Industry_Minority_owned.csv.xz` | varies |

**Measures:** new_business, entry_rate, exit_business, exit_rate, number_business, small_business, soloproprio_business, perc_small, perc_soloproprio

### Employment (4 subtopics, excluding Worker_diversity)

| Subtopic | Output file | Rows |
|---|---|---|
| Total | `{prefix}_cttrbg_mi_2010_2020_employment_metrics_by_Total.csv.xz` | varies |
| Minority_owned | `{prefix}_cttrbg_mi_2010_2020_employment_metrics_by_Minority_owned.csv.xz` | varies |
| Industry | `{prefix}_cttrbg_mi_2010_2020_employment_metrics_by_Industry.csv.xz` | varies |
| Industry_Minority_owned | `{prefix}_cttrbg_mi_2010_2020_employment_metrics_by_Industry_Minority_owned.csv.xz` | varies |

**Measures:** job_creation_new, job_creation_active, total_job_creation, perc_job_creation_new, perc_job_creation_active, job_destruction_exit, job_destruction_active, total_job_destruction, perc_job_destruction_exit, perc_job_destruction_active, total_employment

**Coverage areas (all subtopics):** va059 (Fairfax), ncr (14 counties), rva (Richmond area)

## Qualification checklist failures

| Checklist item | Status | Detail |
|---|---|---|
| 0.1 Data source is automatable | **FAIL** | Mergent Intellect is a commercial database requiring manual data extracts. No API, no download URL, no refresh strategy documented. |
| 0.2 R code is complete | Pass | R scripts (`prepare.R`) are production-quality, calling `business_dynamics()` / `employment_dynamics()` wrappers from `utils/distribution/functions.R`. |
| 0.3 Output can be validated | Pass | Distribution files exist for all 3 coverage areas. |
| 0.4 Data fits long-format schema | Pass | Output follows `(geoid, year, measure, value, moe)` format. |
| 0.5 No spatial complexity | Pass | No spatial joins or routing. |

## Data dependency chain

```
Mergent Intellect Excel files (commercial, manual download)
    ↓ [Microdata/Mergent_intellect/prepare01-03_*.R]
Microdata/Mergent_intellect/data/working/mi_*_features_bg.csv.xz
    ↓ [Business_characteristics/*/code/distribution/prepare.R]
    ↓ [Employment/*/code/distribution/prepare.R]
    ↓ calls utils/distribution/functions.R
*/data/distribution/*.csv.xz
```

The upstream Microdata processing (prepare01-03_*.R) involves:
1. Concatenating raw Excel files from Mergent Intellect
2. Feature engineering (NAICS recoding, entry/exit classification, minority ownership)
3. Geocoding and aggregation to block group level

The feature files (`mi_*_features_bg.csv.xz`) are dated June 2023 and appear to be one-time extracts.

## Recommendation

These pipelines should be converted only when:
1. A documented Mergent Intellect API or automated download process is established, OR
2. The existing feature files are confirmed as permanent reference data (no refresh needed), in which case the downstream `prepare.R` → `functions.R` logic could be ported to Python reading from the committed working files.

The downstream aggregation logic (625 lines in `functions.R`) is straightforward pandas and could be ported quickly once the data source question is resolved.
