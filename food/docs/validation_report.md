# food/ Pipeline Validation Report

Validated: 2026-03-03

## SNAP (Supplemental Nutrition Assistance Program)

Source: ACS B22010, VA/MD/DC, 2013–2023, county/tract/block_group

### Ingest validation (vs old R output)

| File | Rows compared | Max diff |
|---|---|---|
| NCR county/tract/BG (overall measures) | 153,795 | 6.39e-14 |
| VA county/tract/BG (no HD) | 254,343 | 6.39e-14 |
| VA health districts | 1,155 | 0.00e+00 |

### Dashboard files generated

- NCR: 3 files (county, tract, block_group)
- VA: 4 files (health_district, county, tract, block_group)

## Feeding America — Map the Meal Gap

Source: 6 MMG Excel files (2014–2019) + US_tract_2020.xlsx

### Overall Food Insecurity

| File | Rows compared | Max diff |
|---|---|---|
| NCR county (2 measures) | 168 | 1.78e-15 |
| VA county + HD (2 measures) | 2,016 | 3.55e-15 |
| NCR tract 2020 | 2,662 | 3.55e-15 |

Note: 3 extra Fairfax County tracts in Python output (new 2020 Census tracts
not in the original R analysis).  6 additional rows; all values correct.

### Children's Food Insecurity

| File | Rows compared | Max diff |
|---|---|---|
| NCR county | 168 | 3.55e-15 |
| VA county + HD | 2,016 | 3.55e-15 |

### Food Secure Average Meal Cost

| File | Rows compared | Max diff |
|---|---|---|
| NCR county | 84 | 0.00e+00 |
| VA county + HD | 1,008 | 8.88e-16 |

### Food Budget Shortfall

| File | Rows compared | Max diff |
|---|---|---|
| NCR county | 84 | 0.00e+00 |
| VA county + HD | 1,008 | 0.00e+00 |

### Dashboard files generated

- Overall: NCR (county, tract), VA (health_district, county, tract)
- Children's: NCR (county), VA (health_district, county)
- Meal Cost: NCR (county), VA (health_district, county)
- Budget Shortfall: NCR (county), VA (health_district, county)

## Notes

- All numeric differences are IEEE 754 floating-point only (max ~6.39e-14)
- SNAP NCR ingest file contains all VA/MD/DC data (profile: NCR fetches full states);
  dashboard generation via data_reformat_for_site filters to the 14 NCR counties
- Feeding America HD aggregation uses ACS population-weighted averages matching
  the R code exactly (sum for counts, recompute rates from summed counts/population,
  population-weighted average for Cost_Per_Meal)
