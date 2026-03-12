# Mental and Physical Healthy Days — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

## Qualification checklist failures

### Section 0.4 — Pipeline uses SDC dataset framework
- **FAIL:** Uses `dataset_create.Rmd` + `dataset_add_*.Rmd` pattern with `dataset-metadata.json`
- This is a different pipeline architecture (SDC dataset framework) that requires separate conversion tooling

### Section 0.3 — Pipeline depends on external model outputs
- **FAIL:** Uses BRFSS small-area estimates (SAE) which are model-based estimates, not direct data downloads

## What exists
- `dataset_create.Rmd` — creates base dataset structure
- `dataset_add_ncr_brfss_sae.Rmd` — adds NCR BRFSS small-area estimates
- `dataset_add_va_brfss_sae.Rmd` — adds VA BRFSS small-area estimates
- `dataset-metadata.json` — SDC dataset metadata
- `distribution/` — organized output files by year

## To unblock
1. Define conversion pattern for SDC dataset framework pipelines
2. Identify BRFSS SAE data source and download method
3. Convert using dataset framework conversion spec (not yet written)
