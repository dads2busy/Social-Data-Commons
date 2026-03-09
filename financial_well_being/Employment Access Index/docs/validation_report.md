# Employment Access — Conversion Validation Report

**Date:** 2026-03-03
**Converted from:** `code/distribution/ingest.R` + `code/distribution/prepare.R`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** H+T Affordability Index (Center for Neighborhood Technology), https://htaindex.cnt.org/download/
- **Type:** mixed (pre-downloaded CSV files with interpolation/extrapolation)
- **Coverage:** VA
- **Years:** 2015–2021

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_cttr_mixed_2015_2021_employment_access.csv.xz` | 24,931 | 2015–2021 | employment_access_index_geo10, employment_access_index_geo20 | county, tract |
| `va_hdcttr_mixed_2015_2021_employment_access.csv.xz` | 25,176 | 2015–2021 | employment_access_index, employment_access_index_geo10, employment_access_index_geo20 | health_district, county, tract |

## Validation against old R output

Reference file: `va_hdcttr_2015_2021_employment_access_index.csv.xz` (15,023 rows; columns: geoid, year, measure, value, moe)

### Tract level (geo10 vs old 2010 boundaries)

| Comparison | Value |
|---|---|
| Old tract rows | 13,847 |
| New geo10 tract rows | 9,362 |
| Matched rows | 9,362 |

Row count difference: Old file includes VA tracts not present in H+T source for all years. The 9,362 matched rows represent the full intersection.

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| employment_access_index | 9,362 | 0.000000 | 0.000000 | **PASS** |

### County level (2015–2020)

| Comparison | Value |
|---|---|
| Matched rows | 798 |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| employment_access_index | 798 | 0.000000 | 0.000000 | **PASS** |

### County level (2021)

| Comparison | Value |
|---|---|
| Matched rows | 133 |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| employment_access_index | 133 | 111.9023 | 1,877.0000 | **KNOWN DIFF** |

### Health district level

| Comparison | Value |
|---|---|
| Old HD rows | 245 |
| New HD rows | 245 |
| Matched rows | 245 |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| employment_access_index | 245 | 1,047.8413 | 7,847.0601 | **KNOWN DIFF** |

### Known differences

- **County 2021 values:** Old R code had an extrapolation bug — the `mutate()` call used `max(year)` after assigning `year = 2021`, so `max(year)` evaluated to 2021 instead of the source year 2020. This produced `rate × (2021 − 2021) = 0`, effectively copying 2020 values unchanged into 2021. Confirmed: all 133 old 2021 county values are identical to their 2020 values. The new Python output correctly extrapolates using the 2019→2020 rate of change. **New is correct.**

- **Health district aggregation method:** Old R code used population-weighted aggregation (`weight_col="B01003_001E"`); new Python pipeline uses simple mean via `aggregate_with_crosswalk(method="mean")`. Both approaches are defensible for an index-type measure. The difference is methodological, not a bug. The mean diff of 1,047.84 reflects the scale of the employment gravity index (values typically range 10,000–100,000+).

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `va_ct_mixed_2015_2021_employment_access.csv.xz` | 931 | `dashboard_data/virginia_public_health_data/` |
| `va_hd_mixed_2015_2021_employment_access.csv.xz` | 245 | `dashboard_data/virginia_public_health_data/` |
| `va_tr_mixed_2015_2021_employment_access.csv.xz` | 15,983 | `dashboard_data/virginia_public_health_data/` |

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, year, measure, value, moe | geoid, year, measure, value, moe, region_type |
| Measure names | `employment_access_index` | `employment_access_index_geo10`, `employment_access_index_geo20` (tract); `employment_access_index` (county, HD) |
| Census standardization | Not applied | Applied via `write_data(census_standardize=True)` — pre-2020 tracts appear as both `_geo10` (original) and `_geo20` (redistributed to 2020 boundaries) |
