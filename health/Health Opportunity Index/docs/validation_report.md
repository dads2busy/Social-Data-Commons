# Health Opportunity Index — Conversion Validation Report

**Date:** 2026-03-03
**Converted from:** 18 `prepare_*.R` scripts + `aggregate_tr_to_hdct.R`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** Virginia Department of Health (VDH) Health Opportunity Index
- **Type:** vdh_hoi (manual download Excel files)
- **Coverage:** VA
- **Years:** 2017, 2020

## Indicators (18 total)

### Pattern A — 2017 only, quintile text labels (7 indicators)
affordability, education, employment_access, income_inequality, job_participation, population_churning, population_density

### Pattern B — 2017 + 2020, text + continuous_quintile with inversion (6 indicators)
access_care, air_quality, food_accessibility, material_deprivation, segregation, walkability

### Pattern C — 2020 only, from consolidated profile files (5 indicators)
community_environment, consumer_opportunity, economic_opportunity, health_opportunity, wellness_disparity

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_vdh_2017_2020_health_opportunity_index.csv.xz` | 48,366 | 2017, 2020 | 18 indicators | tract |
| `va_hdcttr_vdh_2017_2020_health_opportunity_index.csv.xz` | 52,398 | 2017, 2020 | 18 indicators | health_district (840), county (3,192), tract (48,366) |

## Validation against old R output

### Tract-level

| Pattern | Year | Indicator tested | Result |
|---|---|---|---|
| A (quintile text) | 2017 | walkability | **EXACT MATCH** — 1,886/1,886 rows |
| B (quintile text) | 2017 | air_quality | **EXACT MATCH** — 1,886/1,886 rows |
| B (continuous quintile) | 2020 | air_quality | **EXACT MATCH** — 2,168/2,168 rows |

### County + HD (population-weighted aggregation)

Population-weighted aggregation uses ACS tract population (B01003_001): 2017 for year 2017, 2021 for year 2020 — matching the R code exactly.

### Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| File count | ~30 separate files | 1 ingest + 1 prepare output |
| Columns | geoid, measure, value, year, moe | geoid, year, measure, value, moe, region_type |

## Dashboard files

| File | Location |
|---|---|
| `va_ct_vdh_2017_2020_health_opportunity_index.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_hd_vdh_2017_2020_health_opportunity_index.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_tr_vdh_2017_2020_health_opportunity_index.csv.xz` | `dashboard_data/virginia_public_health_data/` |

## Status

**VALIDATED** — All tested tract-level values match exactly across all 3 indicator patterns.
