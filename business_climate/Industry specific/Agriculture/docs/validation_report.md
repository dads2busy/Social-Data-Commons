# Agriculture — Conversion Validation Report

**Date:** 2026-03-03
**Converted from:** `code/distribution/Prepare.R` (using `quickerstats` R package)
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py`

## Data source

- **Source:** USDA NASS Census of Agriculture (QuickStats API)
- **Type:** nass
- **Coverage:** Virginia (state FIPS 51)
- **Years:** 2022 (primary), 2017 (fallback)

## Output files

| File | Rows | Year | Measures | Region types |
|---|---|---|---|---|
| `va_ct_2022_industry_agriculture.csv.xz` | 848 | 2022 | 9 (of 12 configured) | county |

## Validation against old R output

Reference file: `va_ct_2022_industry_agriculture.csv.xz` (1,158 rows; years 2017 + 2022; 12 measures)

### 2022 shared measures (7 measures)

| Comparison | Value |
|---|---|
| Old 2022 rows | 970 |
| New 2022 rows | 848 |
| Shared measures | 7 |
| Merged rows | 671 |

| Measure | Old rows | New rows | Matched | Max diff | Result |
|---|---|---|---|---|---|
| operation_farmValue | 98 | 98 | 98 | 0 | **PASS** |
| total_animal_expense | 98 | 95 | 95 | 0 | **PASS** |
| total_commodity_sales | 98 | 98 | 98 | 0 | **PASS** |
| total_cropland_acres | 97 | 97 | 97 | 0 | **PASS** |
| total_cropland_operations | 97 | 97 | 97 | 0 | **PASS** |
| total_farmValue | 98 | 98 | 98 | 0 | **PASS** |
| total_irrigatedCropland_acre | 96 | 88 | 88 | 0 | **PASS** |

All matched rows are exact (0 difference). Minor row count differences (95 vs 98, 88 vs 96) are due to counties with suppressed `(D)` values that the new pipeline drops while the old R code may have handled differently.

### Measures available in new but year-shifted

| Measure | Old year | New year | Note |
|---|---|---|---|
| total_acres | 2017 | 2022 | Old R fell back to 2017 because `quickerstats::get_county_data` filters to `domain_desc=TOTAL`, which returns 0 for this measure in 2022. New pipeline correctly retrieves 2022 data from `IRRIGATION STATUS` domain (one row per county). |
| total_operations | 2017 | 2022 | Same as above. |

### Measures unavailable from NASS API

| Measure | Search term | Note |
|---|---|---|
| fruit_treeNut_total_sales | FRUIT & TREE NUT TOTALS - SALES, MEASURED IN $ | API returns 0 rows for 2022 and 2017. Old data likely from an earlier API version or manual extract. |
| total_animalProducts_sales | ANIMAL TOTALS, INCL PRODUCTS - SALES, MEASURED IN $ | Same — no longer available via QuickStats API. |
| total_calves_sales | CATTLE, INCL CALVES - SALES, MEASURED IN $ | Same — no longer available via QuickStats API. |

These 3 measures exist in the old R output (2022 year) but the NASS QuickStats API no longer returns them for Virginia with the `source_desc=CENSUS` + `sector_desc=ECONOMICS` filters.

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, year, measure, value, measure_type | geoid, year, measure, value, moe, region_type |
| Extra column | `measure_type` (always "count") | `region_type` (always "county"), `moe` (always NA) |

## Implementation notes

- Old R pipeline used the `quickerstats` R package which wraps the NASS QuickStats API. New Python pipeline calls the API directly via `httpx`.
- Domain filtering: the API returns multiple domain categories per county for some measures (e.g., FARM SALES breakdowns). The new pipeline filters to `domain_desc=TOTAL` rows when available, falling back to the full result when only one domain exists per county.
- Rate limiting: 3-second sleep between API calls per NASS guidelines.
- Suppressed values marked `(D)` in the API are dropped (not parseable as float).
