# Walkability Index — Conversion Validation Report

**Date:** 2026-03-06
**Converted from:** `code/distribution/ingest.R`, `code/distribution/prepare01.R`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** EPA National Walkability Index (Smart Location Database V3, January 2021)
- **Type:** static_download (CSV from EPA Data Commons)
- **Coverage:** VA and NCR (VA, MD, DC)
- **Geography:** Census block groups (2010 vintage) → aggregated to tracts and counties
- **Year label:** 2019 (based on ACS 2015-2019 inputs to SLD)

## Output files

| File | Rows | Measures | Region types |
|---|---|---|---|
| `va_hdcttr_epa_sld_2019_walkability_index.csv.xz` | 4,248 | walkability_index_geo10, walkability_index_geo20 | health_district, county, tract |
| `ncr_cttr_epa_sld_2019_walkability_index.csv.xz` | 2,566 | walkability_index_geo10, walkability_index_geo20 | county, tract |

## Validation against old R output

### VA (walkability_index_raw)

| Comparison | Old file | New file |
|---|---|---|
| File | `va_hdcttr_2021_walkability_index.csv.xz` | `va_hdcttr_epa_sld_2019_walkability_index.csv.xz` |
| Old rows | 4,096 (2 measures × 2,048) | 4,248 |

| Level | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| tract | 1,880 | 0.0000 | 0.0000 | PASS |
| county | 133 | 0.0000 | 0.0000 | PASS |

Comparison used `walkability_index_geo10` tracts (same 2010 boundaries as old R output) and `walkability_index_geo20` counties (county boundaries unchanged between censuses).

## Known differences

- **Year label change:** Old R code used `year=2021` (publication date). New pipeline uses `year=2019` (ACS data vintage) since the SLD uses 2010-vintage block groups from ACS 2015-2019.

- **Measure name change:** Old R output had `walkability_index_raw` and `walkability_index_zscore`. New pipeline produces `walkability_index_geo10` (original 2010 boundaries) and `walkability_index_geo20` (converted to 2020 boundaries). Z-scores were dropped as they are derivable and not used by the dashboards.

- **Scope expansion:** Old pipeline was VA-only. New pipeline also produces NCR coverage (14 counties, 1,219 tracts on 2010 boundaries).

- **GEOID precision issue:** The SLD CSV stores GEOID10/GEOID20 columns as scientific notation floats (e.g., `4.8113E+11`), losing precision. GEOIDs are instead reconstructed from component columns (STATEFP, COUNTYFP, TRACTCE, BLKGRPCE) with proper zero-padding.

- **2010→2020 tract conversion:** `walkability_index_geo20` tract data uses `convert_2010_to_2020_bounds()` per state, resulting in 2,200 VA tracts (vs 1,880 on 2010 boundaries) and 1,333 NCR tracts (vs 1,219).

## Dashboard files

| File | Location |
|---|---|
| `va_ct_epa_sld_2019_walkability_index.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_hd_epa_sld_2019_walkability_index.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_tr_epa_sld_2019_walkability_index.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `ncr_ct_epa_sld_2019_walkability_index.csv.xz` | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_epa_sld_2019_walkability_index.csv.xz` | `dashboard_data/national_capital_region_data/` |

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, year, measure, value, moe | geoid, year, measure, value, moe, region_type |
| Measure names | `walkability_index_raw`, `walkability_index_zscore` | `walkability_index_geo10`, `walkability_index_geo20` |
| Year | 2021 | 2019 |
| Data source | Geodatabase (Natl_WI.gdb from WalkabilityIndex.zip) | CSV (EPA_SmartLocationDatabase_V3_Jan_2021_Final.csv) |
| Boundary standardization | None (2010 only) | 2010→2020 via `convert_2010_to_2020_bounds()` |
