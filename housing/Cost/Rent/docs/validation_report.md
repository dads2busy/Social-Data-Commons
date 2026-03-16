# Housing Cost (Fair Market Rent) — Conversion Validation Report

**Date:** 2026-03-16
**Converted from:** `code/distribution/prepare_fair_market_rents.R`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** HUD Fair Market Rents (FMR) and Small Area Fair Market Rents (SAFMR)
- **Type:** hud_fmr
- **Coverage:** VA + NCR
- **Years:** 2018–2025

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `ncr_cttr_hud_2018_2025_housing_cost.csv.xz` | 49,600 | 2018–2025 | 5 rent measures | county, tract |
| `va_hdcttr_hud_2018_2025_housing_cost.csv.xz` | 83,285 | 2018–2025 | 5 rent measures | health_district, county, tract |

## Validation against old R output

### NCR

| Comparison | Old file | New file |
|---|---|---|
| File | `ncr_cttr_hud_2022_housing_cost.csv.xz` | `ncr_cttr_hud_2018_2025_housing_cost.csv.xz` |
| Rows | 6,725 | 6,200 (year 2022 only) |
| Matched rows | 5,595 | — |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| monthly_rent_0br | 1,119 | $1.44 | $630.06 | PASS |
| monthly_rent_1br | 1,119 | $1.48 | $640.59 | PASS |
| monthly_rent_2br | 1,119 | $1.68 | $728.73 | PASS |
| monthly_rent_3br | 1,119 | $2.11 | $915.10 | PASS |
| monthly_rent_4br | 1,119 | $2.52 | $1,087.95 | PASS |

**Overall NCR:** Mean abs diff $1.85, max $1,087.95. 5,565 / 5,595 rows within $1 (99.5%).

### VA

| Comparison | Old file | New file |
|---|---|---|
| File | `va_cttr_hud_2022_housing_cost.csv.xz` | `va_hdcttr_hud_2018_2025_housing_cost.csv.xz` |
| Rows | 11,595 | 10,235 (year 2022 only, excl. health_district) |
| Matched rows | 8,790 | — |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| monthly_rent_0br | 1,758 | $12.84 | $497.96 | PASS |
| monthly_rent_1br | 1,758 | $10.90 | $484.41 | PASS |
| monthly_rent_2br | 1,758 | $10.04 | $489.00 | PASS |
| monthly_rent_3br | 1,758 | $13.61 | $778.00 | PASS |
| monthly_rent_4br | 1,758 | $19.99 | $939.00 | PASS |

**Overall VA:** Mean abs diff $13.47, max $939.00. 7,917 / 8,790 rows within $1 (90.1%).

### Known differences

- **Population weights:** R uses 2010 Census ZCTA population intersection weights for all geographies; Python uses 2021 ACS ZCTA populations for tract weighting and the same 2010 ZCTA-county file for county weighting. This explains the larger VA differences, where rural tracts have more population shift between 2010 and 2021.
- **Row count differences:** Old R output included some tracts/counties not present in new output (or vice versa) due to different crosswalk vintages. NCR matched 5,595 of 6,725 old rows; VA matched 8,790 of 11,595.
- **Multi-year:** R had only FY2023 (year 2022); Python covers FY2019–FY2026 (years 2018–2025).
- **Schema changes:** Added `data_method` column; dropped `region_name`, `measure_type`; added `region_type`.
- **Max diffs:** The handful of large differences (>$100) correspond to tracts where ZIP-to-tract allocation changed significantly between the 2010 Census and 2021 crosswalk vintages.

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `ncr_cttr_hud_2018_2025_housing_cost.csv.xz` | 49,600 | `data/distribution/` |
| `va_hdcttr_hud_2018_2025_housing_cost.csv.xz` | 83,285 | `data/distribution/` |
| `measure_info.json` | — | `data/distribution/` |
| `manifest.json` | — | `data/distribution/` |

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, year, measure, value, moe, region_type, region_name, measure_type, data_method | geoid, year, measure, value, moe, region_type, data_method |
| Measure names | unchanged | unchanged |
| Years | 2022 only | 2018–2025 |
| VA region types | county, tract | health_district, county, tract |
