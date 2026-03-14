# Without Health Insurance — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

## Qualification checklist failures

### Section 0.4 — Pipeline uses SDC dataset framework
- **FAIL:** Uses `dataset_create.Rmd` + `dataset_add_*.Rmd` pattern with `dataset-metadata.json`
- This is a different pipeline architecture (SDC dataset framework) that requires separate conversion tooling

## What exists
- `dataset_create.Rmd` — creates base dataset structure
- `dataset_add_ncr_pct_ins.Rmd` — adds NCR percent insured data
- `dataset_add_va_pct_ins.Rmd` — adds VA percent insured data
- `dataset-metadata.json` — SDC dataset metadata
- `distribution/` — organized output files
- `old files/` — previous versions

## To unblock
1. Define conversion pattern for SDC dataset framework pipelines
2. Convert using dataset framework conversion spec (not yet written)
