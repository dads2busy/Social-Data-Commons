# Urgent Care Centers — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

## Qualification checklist failures

### Section 0.1 — Data source is automatable
- **FAIL:** Requires Google Places API for location ingestion (`googleway` R package with GOOGLE_API_KEY)

### Section 0.5 — Spatial complexity
- **FAIL:** Floating catchment area (FCA) analysis via R `catchment` package
- **FAIL:** Requires travel time matrices + block group geometries

## What exists
- R scripts: `01_ingest_gmap_urgent_care_centers.R`, catchment score Rmds
- Data source: Google Places API (grid search over ~224 points)

## To unblock
1. Implement Python FCA, port travel time matrices
2. Implement Google Places API ingestion (or use cached location data)
