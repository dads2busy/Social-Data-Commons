# Access to Care (HOI) — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

## Qualification checklist failures

### Section 0.1 — Data source is automatable
- **FAIL:** Requires geocoding cascade (Census API → OpenStreetMap → Google Maps) to convert physician addresses to coordinates
- **FAIL:** Requires pre-computed tract-to-tract distance matrix from an external repository

### Section 0.5 — Spatial complexity
- **FAIL:** Pipeline uses `sf` package for spatial joins (`st_intersects`) to assign geocoded physicians to census tracts
- **FAIL:** Computes physician-within-30-miles counts using a tract distance matrix
- **FAIL:** Requires `tidygeocoder` R package for multi-provider geocoding cascade

## What exists
- R scripts: `ingest_pop_insur.R`, `ingest_primcare.R`, `prepare_primcare_tracts.R`, `prepare_phys_pop_ratio_insur_pct.R`
- Output: `va_tr_2017_2021_care_access_indicator_std.csv.xz`
- Methodology: Composite index from physician-to-population ratio + uninsured percentage (z-score based)

## To unblock
1. Implement Python geocoding pipeline (e.g., `geopy` with Census/Nominatim providers)
2. Port or pre-compute tract distance matrix in Python
3. Replace `sf::st_intersects` spatial join with `geopandas.sjoin`
4. Ensure geocoding API keys are available in CI environment
