# Physicians — Pediatric — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

## Qualification checklist failures

### Section 0.5 — Spatial complexity
- **FAIL:** Floating catchment area (FCA) analysis via R `catchment` package
- **FAIL:** Requires travel time matrices + block group geometries
- **FAIL:** Includes Fairfax-specific population-weighted FCA variant

## What exists
- R scripts: prepare + catchment score Rmds for DMV and VA
- Data source: WebMD physician directory (geocoded)
- Output: Block group level access scores for pediatricians

## To unblock
Same as Hospitals: implement Python FCA, port travel time matrices.
