# Worker Diversity — Conversion Validation Report

**Date:** 2026-03-03
**Converted from:** R `lehdr` package + `utils/distribution/functions.R`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py`

## Data source

- **Source:** Census LODES WAC (Workplace Area Characteristics)
- **Type:** lodes
- **Coverage:** NCR (14 counties, VA+MD+DC), VA059 (Fairfax County), RVA (Richmond area)
- **Years:** 2010–2019

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `ncr_cttrbg_lodes_2010_2019_employment_by_minority_workers.csv.xz` | 98,774 | 2010–2019 | Minority_employment, Nonminority_employment | block_group, tract, county |
| `va059_cttrbg_lodes_2010_2019_employment_by_minority_workers.csv.xz` | 19,028 | 2010–2019 | Minority_employment, Nonminority_employment | block_group, tract, county |
| `rva_cttrbg_lodes_2010_2019_employment_by_minority_workers.csv.xz` | 12,304 | 2010–2019 | Minority_employment, Nonminority_employment | block_group, tract, county |

## Validation against old R output

### NCR (98,774 rows)

| Comparison | Value |
|---|---|
| Old rows | 98,774 |
| New rows | 98,774 |
| Matched on (geoid, year, measure) | 98,774 |

| Level | Matched | Max diff | Mean diff | Result |
|---|---|---|---|---|
| block_group | 71,898 | 0 | 0 | **PASS** |
| tract | 26,596 | 0 | 0 | **PASS** |
| county | 280 | 0 | 0 | **PASS** |

| Measure | Matched | Max diff | Mean diff | Result |
|---|---|---|---|---|
| Minority_employment | 49,387 | 0 | 0 | **PASS** |
| Nonminority_employment | 49,387 | 0 | 0 | **PASS** |

### VA059 (19,028 rows)

| Comparison | Value |
|---|---|
| Old rows | 19,028 |
| New rows | 19,028 |
| Matched on (geoid, year, measure) | 19,028 |

| Level | Matched | Max diff | Mean diff | Result |
|---|---|---|---|---|
| block_group | 13,528 | 0 | 0 | **PASS** |
| tract | 5,480 | 0 | 0 | **PASS** |
| county | 20 | 0 | 0 | **PASS** |

### RVA

No old R output available for RVA coverage area (new addition). Output verified structurally: 12,304 rows with correct geoid prefixes (51159, 51087, 51041), 2 measures, 10 years, 3 region types.

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, year, measure, value, moe, measure_type | geoid, year, measure, value, moe, region_type |
| Extra column | `measure_type` (always "count") | `region_type` (block_group, tract, county) |

## Implementation notes

- Old R pipeline used the `lehdr` package to download LODES WAC data. New Python pipeline downloads raw LODES WAC CSV.gz files directly from Census Bureau.
- Both LODES8 and LODES7 URLs are tried with automatic fallback.
- Race columns CR01 (White alone) = Nonminority; CR02–CR05, CR07 = Minority.
- Block-level data aggregated to block groups (first 12 digits of w_geocode), then further aggregated to tracts (first 11) and counties (first 5).

## Data refresh — 2026-10-13 (v1.0.0 → v1.1.0)

Extended `years` in `pipeline.yaml` from 2010–2019 to 2010–2023 after `sdc sources check`
reported LODES8 WAC 2023 available. All years are fetched from LODES8 (2020 Census blocks), so no
boundary standardization applies.

| File | Rows | Years |
|---|---|---|
| `ncr_cttrbg_lodes_2010_2023_employment_by_minority_workers.csv.xz` | 138,394 | 2010–2023 |
| `va059_cttrbg_lodes_2010_2023_employment_by_minority_workers.csv.xz` | 26,650 | 2010–2023 |
| `rva_cttrbg_lodes_2010_2023_employment_by_minority_workers.csv.xz` | 17,234 | 2010–2023 |

Overlap check (2010–2019) against the previous `*_2010_2019_*` files: every row matched with
zero difference (ncr 98,774 / va059 19,028 / rva 12,304 rows). The previous files were removed.

Code changes in the same refresh: `ingest.py` now sets `data_method = "observed"` (the committed
files had this column populated by a one-off repo-wide patch, so a plain re-run had dropped it);
`prepare.py` moved `update_version()` from `run()` into `__main__` per the spec template. The
stale `manifest.json` (schema without `data_method`) was regenerated at v1.0.0 before the run so
the bump reflects only the added years.
