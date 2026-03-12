# Environmental Hazard Index (HOI) — Conversion Validation Report

**Date:** 2026-03-12
**Converted from:** No prior R pipeline in this topic directory (new Python implementation)
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** EPA EJScreen (archived via Internet Archive)
- **Type:** EPA environmental justice screening data
- **Coverage:** VA
- **Years:** 2016-2024

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `va_tr_epa_2016_2024_environmental_hazard.csv.xz` | 31,284 | 2016-2024 | environmental_hazard_index_geo10, environmental_hazard_index_geo20 | tract |
| `va_hdcttr_epa_2016_2024_environmental_hazard.csv.xz` | ~38,000 | 2016-2024 | environmental_hazard_index_geo10, environmental_hazard_index_geo20 | health_district, county, tract |

## Validation against old R output

No prior R output exists for this pipeline in the repository. The legacy R pipeline was located in `meta/all/data/sdc.environment/environmental_justice/` (outside this topic directory) and its output was not committed.

### Internal consistency checks

- 2016-2021: 1,907 tracts on 2010 boundaries (geo10), crosswalked to ~2,208 tracts on 2020 boundaries (geo20)
- 2022-2024: 2,198 tracts on native 2020 boundaries (geo20 only)
- PCA explained variance ratio: ~0.25-0.30 across years (consistent with 12-variable extraction)
- Z-scores: mean ≈ 0, std ≈ 1 per year (by construction)

### Known differences from legacy R approach

- Legacy R used `psych::principal()` with oblimin rotation; Python uses `sklearn.decomposition.PCA` (no rotation). Both extract the first principal component from the correlation matrix. Sign and magnitude of PC1 are equivalent since oblimin rotation with 1 component is a no-op.
- Legacy R aggregated BGs to tracts via simple mean; Python uses population-weighted mean when population data is available, falling back to simple mean.
- 2024 data uses 10 PCA variables (EPA dropped CANCER and RESP columns).

## Dashboard files

| File | Location |
|---|---|
| `va_tr_epa_2016_2024_environmental_hazard.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_ct_epa_2016_2024_environmental_hazard.csv.xz` | `dashboard_data/virginia_public_health_data/` |
| `va_hd_epa_2016_2024_environmental_hazard.csv.xz` | `dashboard_data/virginia_public_health_data/` |

## Schema

| Aspect | New (Python) |
|---|---|
| Columns | geoid, year, measure, value, moe, region_type, data_method |
| Measure names | `environmental_hazard_index_geo10`, `environmental_hazard_index_geo20` |
| Geography handling | Manual crosswalk via `convert_2010_to_2020_bounds()` for 2016-2021 (EJScreen switched BG vintage in 2022, not 2020) |
