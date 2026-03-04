# Hospitals and Emergency Rooms — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

## Qualification checklist failures

### Section 0.5 — Spatial complexity
- **FAIL:** Pipeline uses floating catchment area (FCA) analysis via R `catchment` package
- **FAIL:** Requires pre-computed travel time matrices between population zones and hospital locations
- **FAIL:** Uses 2-step and enhanced 2-step FCA calculations at block group level

## What exists
- R scripts: `01_ingest_cms_hospitals.R`, `02_prepare_cms_hospitals.R`, catchment score Rmds (2015-2022)
- Data source: CMS Medicare hospital datasets (automatable downloads)
- Output: `ncr_cttrbg_hosp_*.csv.xz` (block group level service access scores)

## To unblock
1. Implement FCA algorithm in Python (2-step and enhanced 2-step)
2. Port or pre-compute travel time matrices (requires OSRM or similar routing service)
3. Block group geometry processing via `geopandas`
