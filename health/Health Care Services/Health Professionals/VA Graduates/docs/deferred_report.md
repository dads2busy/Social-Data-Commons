# Health Professionals — VA Graduates — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

## Qualification checklist failures

### Section 0.1 — Data source is automatable
- **FAIL:** Requires PostgreSQL database connection (host `postgis1`, credentials via env vars)
- **FAIL:** SCHEV data requires manual download from https://research.schev.edu/
- **FAIL:** Geography joins use database tables (`dc_geographies.*`)

## What exists
- R scripts: `prepare02.R`, `prepare_ahec.R`, `prepare_hd.R`
- Data source: SCHEV (health profession degrees awarded by locality, 2016-2021)
- Output: `va_hd_schev_2016_2019_health_degrees_awarded.csv.xz`

## To unblock
1. Replace PostgreSQL queries with local crosswalk files
2. Document SCHEV manual download process
3. Port fuzzy county name matching logic to Python
