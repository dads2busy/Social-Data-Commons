# Urgent Care Centers Service Access Scores — NPPES Conversion Validation Report

**Date:** 2026-03-22
**Version:** 4.0.0 (NPPES) replacing 2.0.0 (Google Maps)

## Data Source Change

| Attribute | Old (v2.0.0) | New (v4.0.0) |
|-----------|-------------|-------------|
| Source | Google Maps manual scrape | NPPES NPI Registry (taxonomy 261QU0200X) |
| Coverage | NCR only | VA + NCR |
| Years | 2022 only | 2020-2025 |
| Provider count (NCR) | 77 facilities | 252 facilities (3.3x) |
| Provider count (VA) | N/A | 663 facilities |
| Geocoding | Pre-geocoded | Census Geocoder API (91% match rate) |
| Reproducibility | Not reproducible (manual scrape) | Fully reproducible (automated download) |
| Capacity | 1 per facility | 1 per facility (unchanged) |

## Rationale for Change

The Google Maps data source had three limitations:
1. **Not reproducible** — required manual scraping with no stable API
2. **NCR-only** — no statewide Virginia coverage
3. **Single year** — no multi-year time series capability

NPPES provides a public, downloadable registry of all NPI-enrolled healthcare organizations, filterable by taxonomy code. This enables automated, reproducible, statewide, multi-year pipelines.

## Output Files

| File | Rows | Years | Coverage |
|---|---|---|---|
| `va_hdcttrbg_nppes_2020_2025_access_scores_urgent.csv.xz` | 294,312 | 2020-2025 | Virginia (BG+tract+county+HD) |
| `ncr_cttrbg_nppes_2020_2025_access_scores_urgent.csv.xz` | 176,028 | 2020-2025 | NCR (BG+tract+county) |

## Provider Count Comparison (NCR, 2022)

NPPES identifies 252 urgent care facilities in the NCR compared to 77 from Google Maps. The 3.3x increase reflects:
- NPPES captures all NPI-enrolled urgent care centers, including those not listed on Google Maps
- Google Maps may have included only a subset of search results
- Some NPPES entries may be administrative registrations rather than patient-facing locations

## Spatial Correlation (NCR block groups, 2022)

| Measure | Spearman r | Pearson r | Old mean | New mean |
|---------|-----------|----------|----------|----------|
| urgent_cnt | 0.241 | 0.281 | 0.021 | 0.070 |
| urgent_e2sfca | 0.421 | 0.293 | 0.013 | 0.044 |
| urgent_3sfca | 0.132 | 0.285 | 0.013 | 0.044 |

Low correlations are expected given the 3.3x provider count difference. The E2SFCA measure shows the strongest rank agreement (Spearman r = 0.421), indicating that the relative spatial pattern of accessibility is partially preserved despite the absolute magnitude change. FCA scores are approximately 3.4x higher in the NPPES version, proportional to the provider count increase.

## New Coverage

The NPPES pipeline adds statewide Virginia coverage that did not exist in the Google Maps version:
- 5,963 block groups (2021-2025 Census geography)
- 2,198 census tracts
- 133 counties/independent cities
- 35 health districts
- 6 years of data (2020-2025)

## Schema Changes

| Aspect | Old (v2.0.0) | New (v4.0.0) |
|---|---|---|
| data_source | gmap | nppes |
| Region types | block_group, tract, county | block_group, tract, county, health_district |
| Removed measures | — | urgent_pop_cnt (consumer population, not access) |
| Removed columns | — | region_name, measure_type (schema cleanup) |
| Removed regions | — | PA (42), WV (54) edge-case BGs |

## Dashboard Files

| File | Location |
|---|---|
| `va_bg_nppes_2020_2025_access_scores_urgent.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_tr_nppes_2020_2025_access_scores_urgent.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_ct_nppes_2020_2025_access_scores_urgent.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_hd_nppes_2020_2025_access_scores_urgent.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `ncr_bg_nppes_2020_2025_access_scores_urgent.csv.xz` | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_nppes_2020_2025_access_scores_urgent.csv.xz` | `dashboard_data/national_capital_region_data/` |
| `ncr_ct_nppes_2020_2025_access_scores_urgent.csv.xz` | `dashboard_data/national_capital_region_data/` |

## Known Limitations

1. **NPPES is a point-in-time snapshot.** The same facility set is used for all years (2020-2025). Year-over-year changes in the time series reflect only ACS population denominator changes, not facility openings/closures.
2. **Geocoding gap.** 56 of 651 unique addresses (8.6%) failed Census Geocoder matching. These facilities are excluded from the FCA computation.
3. **Administrative registrations.** Some NPPES entries may be administrative rather than patient-facing locations, inflating facility counts.
4. **Taxonomy code coverage.** Facilities registered under different codes (e.g., hospital-based urgent care) would be missed by the 261QU0200X filter.
