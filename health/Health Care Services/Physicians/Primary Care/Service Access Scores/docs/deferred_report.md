# Physicians — Primary Care — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

## Qualification checklist failures

### Section 0.5 — Spatial complexity
- **FAIL:** Floating catchment area (FCA) analysis via R `catchment` package
- **FAIL:** Requires travel time matrices + block group geometries

## What exists
- R scripts: `01_ingest_cms_primarycare.R`, `02_prepare_cms_primarycare.R`, catchment score Rmds
- Data source: CMS Doctors/Clinicians dataset (2018-2022, automatable)
- Output: `ncr_cttrbg_webmd_2021_acccess_scores_primcare.csv.xz`

## To unblock
Same as Hospitals: implement Python FCA, port travel time matrices.
