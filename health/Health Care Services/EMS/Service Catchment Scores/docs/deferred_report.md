# EMS Stations — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

## Qualification checklist failures

### Section 0.5 — Spatial complexity
- **FAIL:** Floating catchment area (FCA) analysis via R `catchment` package
- **FAIL:** Requires travel time matrices + block group geometries

## What exists
- R scripts: prepare Rmds for DMV and VA, catchment score Rmds
- Data source: HIFLD 2021 (originally via PostgreSQL)
- Output: `ncr_cttrbg_hifld_2021_access_scores_ems.csv.xz`

## To unblock
Same as Hospitals: implement Python FCA, port travel time matrices.
Also need alternative to PostgreSQL data source (direct HIFLD download or cached CSV).
