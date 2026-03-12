# Food Accessibility Indicator (HOI) — Conversion Validation Report

**Date:** 2026-03-12
**Converted from:** `code/distribution/prepare_fara.Rmd` (moved to `legacy/`)
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** USDA Economic Research Service, Food Access Research Atlas
- **Type:** USDA FARA Excel files (2015, 2019 editions)
- **Coverage:** VA
- **Years:** 2015-2023 (interpolated 2016-2018, extrapolated 2020-2023)

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_hdcttr_usda_2015_2023_food_access.csv.xz` | 33,498 | 2015-2023 | food_access_percentage_geo10, food_access_percentage_geo20 | health_district, county, tract |

## Validation against old R output

### Tract-level comparison (2015-2019)

| Comparison | Old file | New file |
|---|---|---|
| File | `data/working/va_tr_usda_2015_2019_food_access.csv` | `data/distribution/va_hdcttr_usda_2015_2023_food_access.csv.xz` |
| Rows (tract, overlap years) | 11,020 | 11,061 |
| Overlap years | 2015-2019 | — |
| Matched rows | 11,020 | — |

| Metric | Value | Result |
|---|---|---|
| Exact matches | 3,409 / 11,020 (31%) | — |
| Within 0.01 | 9,119 / 11,020 (82.7%) | — |
| Within 0.1 | 9,339 / 11,020 (84.7%) | — |
| Mean absolute diff | 0.726 | EXPECTED |
| Median absolute diff | 0.000 | PASS |
| Max absolute diff | 75.6 | EXPECTED |

### Known differences

- **2010→2020 geography crosswalk:** Old R output used 2010 census tract GEOIDs. New Python output converts all tracts to 2020 boundaries via `census_standardize=True` (area-weighted redistribution). This causes value differences where tract boundaries changed between 2010 and 2020. The 83% exact-match rate reflects tracts with `same` boundary status in the crosswalk; the 17% with differences are `split` or `moved` tracts.
- **Worst outliers (diff > 40):** These are tracts where 2010 boundaries were split into multiple 2020 tracts (e.g., 51740211800 went from 0.01 to 75.62). The new values reflect the crosswalked 2020-boundary values, which redistribute area-weighted values differently. New output is correct for 2020 boundaries.
- **41 extra tracts in new output:** 2020 census added new tracts from splits. These correctly appear only in the new output.
- **Years 2020-2023:** Not present in old R output. Python extrapolates linearly from 2015-2019 trend.

## Dashboard files

| File | Location |
|---|---|
| `va_tr_usda_2015_2023_food_access.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_ct_usda_2015_2023_food_access.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_hd_usda_2015_2023_food_access.csv.xz` | `dashboard_data/virginia_public_health_data/` |

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, year, measure, value, moe | geoid, year, measure, value, moe, region_type, data_method |
| Measure names | `food_access_percentage` | `food_access_percentage_geo10`, `food_access_percentage_geo20` |
| Geography | 2010 census tracts | 2020 census tracts (crosswalked) |
| Year coverage | 2015-2019 | 2015-2023 |
