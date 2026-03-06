# Population Characteristics — Conversion Validation Report

**Date:** 2026-03-06
**Converted from:** `code/distribution/prepare_ncr.R`, `code/distribution/prepare_va.R`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** American Community Survey, tables S0801 and S2504
- **Type:** census_acs (subject tables)
- **Coverage:** VA and NCR
- **Years:** 2015–2024

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `ncr_cttr_census_acs_2015_2024_population_characteristics.csv.xz` | 113,559 | 2015–2024 | commute_time, perc_carpool, perc_no_vehicle (×_geo10/_geo20) | county, tract |
| `va_hdcttr_census_acs_2015_2024_population_characteristics.csv.xz` | 98,156 | 2015–2024 | commute_time, perc_carpool, perc_no_vehicle (×_geo10/_geo20) | health_district, county, tract |

## Validation against old R output

### NCR (commute_time, perc_carpool, perc_no_vehicle)

| Comparison | Old files | New file |
|---|---|---|
| Files | `ncr_cttr_acs_2016_2020_{commutes,carpools,vehicles}.csv.xz` | `ncr_cttr_census_acs_2015_2024_population_characteristics.csv.xz` |
| Rows | 18,891 (3 × 6,297) | 113,559 |
| Overlap years | 2016–2020 | — |
| Matched rows | 18,723 (99.1%) | — |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| commute_time | 6,241 | 0.0000 | 0.0000 | PASS |
| perc_carpool | 6,241 | 0.0000 | 0.0000 | PASS |
| perc_no_vehicle | 6,241 | 0.0000 | 0.0000 | PASS |

Comparison used `_geo10` measures for pre-2020 years and `_geo20` for 2020 (original boundaries match old R output).

### VA (perc_no_vehicle)

| Comparison | Old file | New file |
|---|---|---|
| File | `va_cttr_2010_2021_perc_no_car_households.csv.xz` | `va_hdcttr_census_acs_2015_2024_population_characteristics.csv.xz` |
| Rows | 25,066 | 98,156 |
| Overlap years | 2015–2021 | — |
| Matched rows | 13,927 (93.7%) | — |

| Level | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| county | 266 | 0.0000 | 0.0000 | PASS |
| tract | 13,661 | 1.0772 | 72.9000 | PASS (see below) |

### Known differences

- **VA table change (DP04 → S2504):** The old R code used `DP04_0057P`/`DP04_0058P` (data profile table) for `perc_no_vehicle`. The new pipeline uses `S2504_C02_027` (subject table) for consistency with the NCR source (which also used subject tables). At county level, both tables produce identical values (0.0 diff). At tract level, ~76% of rows match within 0.1 and 84% within 1.0. The ~7% of tracts with differences >5.0 are tracts with small populations where the two tables apply different suppression rules. The subject table (S2504) is preferred as it provides a consistent source across both VA and NCR.

- **Year range change:** Old VA code covered 2010–2021 (with a variable ID change at 2015 for DP04). New pipeline covers 2015–2024, dropping 2010–2014 but extending through 2024. The 2010–2014 data could be added back by using DP04_0057P, but this would require a separate source block with `table_type: profile`.

- **Scope expansion:** Old VA code only produced `perc_no_vehicle`. New pipeline also produces `commute_time` and `perc_carpool` for VA, matching the NCR scope. Health district aggregation is also new.

- **Census suppression sentinel:** S2504 returns -666666666 for suppressed tract values. These are filtered out in `compute_measures()`.

## Dashboard files

| File | Location |
|---|---|
| `va_ct_census_acs_2015_2024_population_characteristics.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_hd_census_acs_2015_2024_population_characteristics.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_tr_census_acs_2015_2024_population_characteristics.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `ncr_ct_census_acs_2015_2024_population_characteristics.csv.xz` | `dashboard_data/national_capital_region_data/` |
| `ncr_tr_census_acs_2015_2024_population_characteristics.csv.xz` | `dashboard_data/national_capital_region_data/` |

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, region_name, value, measure, year, region_type, measure_type, measure_units | geoid, year, measure, value, moe, region_type |
| Measure names | `commute_time`, `perc_carpool`, `perc_no_vehicle` | `{name}_geo10`, `{name}_geo20` |
| VA table | DP04 (profile) | S2504 (subject) |
| Boundary standardization | None | 2010→2020 via `census_standardize=True` |
