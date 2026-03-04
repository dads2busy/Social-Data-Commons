# MSI Institutions — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

## Qualification checklist failures

### Section 0.1 — Source data requires external service
- **FAIL:** R code (`ingest01.R`) uses hardcoded desktop paths and PostgreSQL database queries
- **FAIL:** No automated data source — relies on manual data transfers

### Section 0.2 — R code is complete, production pipeline
- **FAIL:** Code is exploratory with hardcoded local paths (e.g. `/Users/avagutshall/Desktop/`)
- **FAIL:** No output files in `data/distribution/`

## What exists
- `ingest01.R` — reads from local files with hardcoded paths
- `old/` directory with earlier attempts

## To unblock
1. Identify reproducible data source (CMS API, HRSA, or shared database)
2. Write pipeline with automated download
3. Define target measures and output schema
