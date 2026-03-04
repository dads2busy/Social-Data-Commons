# Prenatal Care Adequacy — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

## Qualification checklist failures

### Section 0.1 — Data source is automatable
- **FAIL:** Source data (NCHS Natality) must be manually downloaded from CDC WONDER (https://wonder.cdc.gov/)
- **FAIL:** CDC WONDER requires interactive parameter configuration — no stable download URL
- **FAIL:** Raw data files are not committed to the repository (only `raw_data_note.txt` in data/original/)

### Section 0.3 — Output can be validated
- **PARTIAL:** Output file exists (`va_ct_nchs_2014_2020_kotelchuck.csv.xz`) but source data is not available for re-running

## What exists
- Files: `ingest.txt` (download instructions), `prepare.Rmd` (56 KB, includes analysis + output)
- Methodology: Kotelchuck Index (prenatal care adequacy metric)
- Output: `va_ct_nchs_2014_2020_kotelchuck.csv.xz` (county-level, 2014-2020)

## To unblock
1. Download NCHS Natality data from CDC WONDER and commit to data/original/
2. Document exact CDC WONDER query parameters in pipeline.yaml
3. Separate the prepare.Rmd into distinct ingest and prepare steps
