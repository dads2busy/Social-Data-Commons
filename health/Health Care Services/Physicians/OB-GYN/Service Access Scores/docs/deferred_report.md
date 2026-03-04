# Physicians — OB-GYN — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

## Qualification checklist failures

### Section 0.5 — Spatial complexity
- **FAIL:** Floating catchment area (FCA) analysis via R `catchment` package
- **FAIL:** Requires travel time matrices + block group geometries
- **FAIL:** Includes Fairfax-specific population-weighted catchment variant with age/sex population pyramids

## What exists
- R scripts: `01_ingest_cms_obgyn.R`, prepare + catchment score Rmds
- Data source: CMS dataset + WebMD (2021-2022)
- Output: `ncr_cttrbg_webmd_2021_access_scores_obgyn.csv.xz`

## To unblock
Same as Hospitals: implement Python FCA, port travel time matrices.
