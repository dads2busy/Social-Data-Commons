# Nursing Homes — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

Applies to all three Nursing Homes sub-topics: Provider Info, Inspection Deficiencies, Staffing/Nurses.

## Qualification checklist failures

### Section 0.2 — R code is complete, production pipeline
- **FAIL:** No active R or Python code exists in any of the three sub-topic directories
- **FAIL:** No output files exist in data/distribution/
- **FAIL:** Only documentation files present (data dictionary, PDF manual)

## What exists
- Directory structure with placeholder "temp" folders
- Reference documentation: `hrs_ltcfocus_data_manual_042016_v2.pdf`, `ltcfocus_data_dictionary_2020.xlsx`
- Potential data sources: CMS HCQIS, LTCfocus database

## To unblock
1. Identify and document specific data source (CMS Nursing Home Compare API or LTCfocus)
2. Write initial R or Python pipeline from scratch
3. Define target measures and output schema
