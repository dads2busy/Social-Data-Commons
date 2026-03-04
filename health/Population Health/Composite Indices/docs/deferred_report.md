# Composite Indices — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

## Qualification checklist failures

### Section 0.3 — Pipeline depends on other pipelines' outputs
- **FAIL:** Composite indices aggregate outputs from HOI, SVI, and other health indicator pipelines
- Requires all upstream pipelines to be converted and running first

### Section 0.2 — R code is complete, production pipeline
- **PARTIAL:** `Prepare_Composite_Indices_Files.Rmd` exists but produces static pre-computed quintile files (2015-2019), not a continuously updated pipeline

## What exists
- `Prepare_Composite_Indices_Files.Rmd` — aggregates multiple health indices into composite scores
- `data/` — year-organized subdirectories with quintile CSVs (2015-2019)

## To unblock
1. Convert all upstream indicator pipelines first
2. Define composite index methodology in Python
3. Determine if composite indices are still actively used or archived
