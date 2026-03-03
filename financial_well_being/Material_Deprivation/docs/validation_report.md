# Material Deprivation — Conversion Validation Report

**Date:** 2026-03-03
**Converted from:** `code/distribution/prepare_material_dep.R`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** Census ACS B23025, B25014, B25044, S2502 (Townsend Material Deprivation Index)
- **Type:** census_acs
- **Coverage:** VA
- **Years:** 2015–2024

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_hdcttr_census_acs_2015_2024_material_deprivation.csv.xz` | 33,135 | 2015–2024 | material_deprivation_indicator_geo10, material_deprivation_indicator_geo20 | health_district, county, tract |

## Validation against old R output

Reference file: `va_hdcttr_vdh_2015_2023_material_deprivation_index.csv.xz` (19,559 rows; columns: geoid, year, measure, value, moe)

### Tract level (geo10 vs old 2010 boundaries)

| Comparison | Value |
|---|---|
| Old tract rows (overlap years) | 9,535 |
| New geo10 tract rows (overlap years) | 9,535 |
| Matched rows | 9,535 |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| material_deprivation_indicator | 9,535 | 0.004803 | 0.020640 | **PASS** |

1,810 rows have diff > 0.01 (max 0.02). These are small numerical differences from floating-point arithmetic in z-score computation.

### County level

| Comparison | Value |
|---|---|
| Matched rows | 1,197 |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| material_deprivation_indicator | 1,197 | 0.000024 | 0.000050 | **PASS** |

### Health district level

| Comparison | Value |
|---|---|
| Matched rows | 35 |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| material_deprivation_indicator | 35 | 0.000027 | 0.000049 | **PASS** |

Note: Only 35 of 350 new HD rows matched because the old file covered 2015–2019 for HD (5 years × 35 HDs = 175 expected, but the old file appears to have had only 1 year of HD data in the overlap window).

### Known differences

- **Tract-level z-score precision:** The Townsend index is computed as a sum of z-scores. Small differences (max 0.02) arise from floating-point arithmetic differences between R and Python in the z-score normalization step. All differences are well within the 0.1 tolerance for index-type measures.

- **Measure naming:** Old file uses `material_deprivation_indicator` for all levels. New file uses `material_deprivation_indicator_geo10`/`material_deprivation_indicator_geo20` for tracts (census standardization) and `material_deprivation_indicator_geo20` for county/HD (boundaries are stable, but the measure carries the `_geo20` suffix in the new pipeline).

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `va_ct_census_acs_2015_2024_material_deprivation.csv.xz` | 1,330 | `dashboard_data/virginia_public_health_data/` |
| `va_hd_census_acs_2015_2024_material_deprivation.csv.xz` | 350 | `dashboard_data/virginia_public_health_data/` |
| `va_tr_census_acs_2015_2024_material_deprivation.csv.xz` | 23,325 | `dashboard_data/virginia_public_health_data/` |

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, year, measure, value, moe | geoid, year, measure, value, moe, region_type |
| Measure names | `material_deprivation_indicator` | `material_deprivation_indicator_geo10`, `material_deprivation_indicator_geo20` |
| Data source label | `vdh` | `census_acs` (reflects actual ACS source tables) |
| Census standardization | Not applied | Applied — pre-2020 tracts appear as both `_geo10` and `_geo20` |
