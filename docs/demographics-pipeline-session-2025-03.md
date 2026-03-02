# Demographics Pipeline Session Summary — March 2025

## Goal

Convert all `sdc-monorepo/demographics/` pipelines to produce dashboard-ready wide CSV files
via `data_reformat_for_site()`, matching the completed `Gender` reference implementation.
Output goes to:
- `dashboard_data/virginia_public_health_data/` — VA dashboard (va_ct_*, va_hd_*, va_tr_*)
- `dashboard_data/national_capital_region_data/` — NCR dashboard (ncr_ct_*, ncr_tr_*, ncr_bg_*)

Population Density, Geographic Mobility, Segregation, and Cooperative Extension are **VA only**.

---

## Reference Implementation

`demographics/Gender/code/prepare.py` is the canonical pattern:
1. `find_va_source()` / `find_ncr_source()` — globs for the ingest output in `data/distribution/`
2. `build_va_with_health_districts()` — reads VA long file, aggregates counties→HDs via crosswalk,
   writes combined VA distribution file
3. `data_reformat_for_site()` — pivots long→wide, splits by level, writes per-level csv.xz

---

## Status at End of Session

### Pipelines producing dashboard files (all complete)

| Topic | VA files | NCR files | Notes |
|---|---|---|---|
| Gender | va_ct/hd/tr | ncr_ct/tr/bg | Reference implementation |
| Age | va_ct/hd/tr | ncr_ct/tr/bg | ✅ |
| Race | va_ct/hd/tr | ncr_ct/tr/bg | ✅ |
| Language | va_ct/hd/tr | ncr_ct/tr/bg | ✅ |
| Veteran | va_ct/hd/tr | ncr_ct/tr/bg | ✅ |
| Population Density | va_ct/hd/tr | — | ✅ fixed this session |
| Geographic Mobility (HOI) | va_ct/hd/tr | — | ✅ fixed this session |
| Segregation (HOI) | va_ct/hd/tr | — | ✅ fixed this session |
| Cooperative Extension | va_ct/hd/tr | — | ✅ partial — see known issues |

### Current dashboard_data output files

```
dashboard_data/virginia_public_health_data/
  va_ct_census_acs_2009_2024_gender_demographics.csv.xz
  va_ct_census_acs_2009_2024_race_demographics.csv.xz
  va_ct_census_acs_2009_2021_age_demographics.csv.xz
  va_ct_census_acs_2009_2021_veteran_demographics.csv.xz
  va_ct_census_acs_2016_2021_language_demographics.csv.xz
  va_ct_census_acs_2015_2024_population_density.csv.xz
  va_ct_census_acs_2015_2024_geographic_mobility_hoi.csv.xz
  va_ct_census_acs_2015_2024_segregation.csv.xz
  va_ct_mixed_2010_2024_cooperative_extension.csv.xz
  (plus matching va_hd_* and va_tr_* for each)
```

---

## Bugs Fixed This Session

### 1. `output.filename` KeyError (Population Density, Geographic Mobility, Segregation)
`pipeline.yaml` has no `output.filename` key but old `prepare.py` used `out["filename"]`.
Fixed by replacing with `find_va_source()` glob functions.

### 2. Segregation ingest: DP05 variables on wrong Census endpoint
DP05 variables are Data Profile tables requiring `acs/acs5/profile`, not `acs/acs5`.
Fixed in `packages/sdc-core/src/sdc_core/census.py`:
- Added `table_type: str = "detail"` parameter to `get_acs_wide()` and `get_acs_multi()`
- URL suffix logic: `{"profile": "/profile", "subject": "/subject"}.get(table_type, "")`

Fixed in `demographics/Segregation (HOI)/code/ingest.py`:
- Both `get_acs_multi()` calls now pass `table_type="profile"`

Same fix applies to any S-prefix (subject) tables — see cooperative extension below.

### 3. Double `_geo20` suffix (Population Density, Geographic Mobility)
`ingest.py` wrote with `census_standardize=True` → measure names get `_geo20`/`_geo10` suffix.
`prepare.py` then read that file and applied `census_standardize=True` again → `_geo20_geo20`.

Two-part fix in each `prepare.py`:
- Changed `find_va_source()` glob from `va_*` to `va_cttr_*` — ingest writes `cttr` (county+tract),
  prepare writes `hdcttr`. The specific glob prevents prepare from reading its own previous output.
- Changed `write_data(..., census_standardize=False)` — data is already standardized.

The same pattern applies to Segregation: ingest writes `va_tr_*`, prepare glob is `va_tr_*census_acs*`.

### 4. Incorrect measure name overwrite in Segregation prepare.py
`aggregate_up()` preserves the `measure` column in groupby when present. After aggregation,
county rows already had `segregation_indicator_geo10` and `segregation_indicator_geo20`.
The line `county["measure"] = "segregation_indicator"` overwrote these, causing duplicates
and losing geo-vintage information. Line removed.

### 5. `perc_male` missing from Cooperative Extension (S0101 is a subject table)
`ingest_perc_male()` called `get_acs_wide()` without `table_type`, defaulting to detail endpoint.
S0101 is a subject table — fixed by adding `table_type="subject"` to that call.

---

## Known Issues

### County Health Rankings URLs are all 404
`disconnectedYouth` and `voterTurnout` measures in Cooperative Extension come from CHR Excel files.
The URL template in `pipeline.yaml` is outdated:
```
https://www.countyhealthrankings.org/sites/default/files/{year}%20County%20Health%20Rankings%20Virginia%20Data%20-%20v1_0.xlsx
```
All years 2017–2023 return 404. Need to find current CHR download URL format.

---

## Key Architecture Notes

### census_standardize pattern
- Applied in `ingest.py` via `write_data(..., census_standardize=True)` in pipeline.yaml `standardize: true` pipelines
- Renames tract measures: pre-2020 tracts → `_geo10`, 2020+ tracts and all counties → `_geo20`
- **Never apply again in `prepare.py`** — always use `census_standardize=False` there
- Gender/Age/Language/Veteran do NOT use census_standardize (no geo suffix on measures)
- Race, Population Density, Geographic Mobility, Segregation DO use it (measures have `_geo20`/`_geo10`)

### find_va_source() glob specificity
Always glob for the INGEST output pattern (before health district aggregation), not the PREPARE output:
- `va_cttr_*` = ingest output (county+tract) ← use this in glob
- `va_hdcttr_*` = prepare output (hd+county+tract) ← do NOT match

For segregation (tract-only ingest): `va_tr_*census_acs*segregation.csv.xz`
For population density: `va_cttr_*population_density.csv.xz`
For geographic mobility: `va_cttr_*geographic_mobility_hoi.csv.xz`

### Census API table types
- Detail tables (B/C prefix): default `table_type="detail"` → `acs/acs5`
- Profile tables (DP prefix): `table_type="profile"` → `acs/acs5/profile`
- Subject tables (S prefix): `table_type="subject"` → `acs/acs5/subject`

### Running pipelines
```bash
cd /Users/ads7fg/git/sdc-monorepo
.venv/bin/python "demographics/<Topic>/code/ingest.py"   # fetch raw data
.venv/bin/python "demographics/<Topic>/code/prepare.py"  # aggregate + write dashboard files
```

### Value accuracy
Gender county values vs old `virginia_public_health_data/data/county.csv.xz`:
max_diff=0.0000, mean_diff=0.0000 across 2000 rows (years 2009–2023). ✅

Old county.csv.xz used `_direct` suffix (R pipeline artifact). New pipeline uses `_geo20`/`_geo10`
where census_standardize=True, or no suffix otherwise. This naming change is intentional.
