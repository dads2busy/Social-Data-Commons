# Mental Health Services — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

## Qualification checklist failures

### Section 0.5 — Spatial complexity
- **FAIL:** Floating catchment area (FCA) analysis via R `catchment` package
- **FAIL:** Requires travel time matrices + block group geometries

## What exists
- R scripts: prepare Rmds for DMV and VA, catchment score Rmds
- Data source: SAMHSA mental health facilities (originally via PostgreSQL)
- Output: `ncr_cttrbg_samhsa_2021_access_scores_mental.csv.xz`

## To unblock
Same as Hospitals: implement Python FCA, port travel time matrices.
Also need alternative to PostgreSQL data source.
