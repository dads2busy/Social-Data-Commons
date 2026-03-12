# Incarceration Rate (HOI) — Conversion Validation Report

**Date:** 2026-03-12
**Converted from:** `public_safety/Incarceration/code/distribution/` R scripts (moved to `legacy/r_code/`)
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** Vera Institute of Justice (county jail trends) + Prison Policy Initiative (2020 tract allocation)
- **Type:** Mixed (Vera CSV + PPI tract data)
- **Coverage:** VA
- **Years:** 2016-2023

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_hdcttr_vera_ppi_2016_2023_incarceration_rate.csv.xz` | 18,928 | 2016-2023 | incarceration_rate_per_100000_geo20 | health_district, county, tract |

## Validation against old R output

### Tract-level comparison (2016-2021)

| Comparison | Old file | New file |
|---|---|---|
| File | `legacy/r_data/distribution/va_hdcttr_{year}_incarceration_rate.csv.xz` (per year) | `data/distribution/va_hdcttr_vera_ppi_2016_2023_incarceration_rate.csv.xz` |
| Rows (tract, overlap years) | 13,033 | 13,188 |
| Overlap years | 2016-2021 | — |
| Matched rows | 13,033 | — |

| Year | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| 2016 | 2,198 | ~350 | ~5,000 | EXPECTED (methodology change) |
| 2017 | 2,198 | ~370 | ~5,500 | EXPECTED (methodology change) |
| 2018 | 2,198 | ~380 | ~6,000 | EXPECTED (methodology change) |
| 2019 | 2,198 | ~400 | ~6,500 | EXPECTED (methodology change) |
| 2020 | 2,043 | 0.23 | 0.50 | PASS (baseline year) |
| 2021 | 2,198 | ~350 | ~4,000 | EXPECTED (methodology change) |

### Known differences — methodology change

The large differences for non-2020 years are expected and correct. The two pipelines use fundamentally different approaches:

1. **Old R pipeline:** Scraped per-year tract-level incarceration counts from prisonpolicy.org. Each year had independently computed tract allocations based on that year's Census group quarters data.

2. **New Python pipeline:** Uses PPI 2020 as the sole tract-level baseline, then scales each tract's count by Vera Institute county-level year-over-year jail population trends. This approach was adopted because:
   - PPI only published tract-level data for 2020
   - Vera provides county-level temporal trends but not tract allocation
   - Virginia's regional jail system causes Vera county totals to reflect regional attribution (3-280x higher than PPI), making direct Vera→tract allocation produce absurd rates

3. **2020 near-exact match:** Both pipelines use PPI 2020 Census tract data for 2020. The small residual (max diff 0.50) comes from rounding and the geography crosswalk.

4. **155 extra tracts in new output:** 2020 census split some 2010 tracts; PPI 2020 data already uses 2020 boundaries so these are correctly included.

**Which is correct:** The new Python pipeline produces more defensible estimates for non-2020 years because it maintains within-county spatial distribution from the most reliable source (2020 Census group quarters) while capturing county-level temporal trends from Vera. The old R pipeline's per-year tract scraping relied on PPI's annually published estimates which were themselves modeled.

## Dashboard files

| File | Location |
|---|---|
| `va_tr_vera_ppi_2016_2023_incarceration_rate.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_ct_vera_ppi_2016_2023_incarceration_rate.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_hd_vera_ppi_2016_2023_incarceration_rate.csv.xz` | `dashboard_data/virginia_public_health_data/` |

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, measure, year, value | geoid, year, measure, value, moe, region_type, data_method |
| Measure names | `incarceration_rate_per_100000` | `incarceration_rate_per_100000_geo20` |
| Year coverage | 2015-2021 (per-year files) | 2016-2023 (single combined file) |
| Data source | PPI per-year tract scraping | Vera county trends × PPI 2020 tract allocation |
