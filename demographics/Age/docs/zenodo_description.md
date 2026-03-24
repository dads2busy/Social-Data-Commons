## Overview
Population age distribution from ACS table B01001 (Sex by Age), providing counts and percentages for three age groups (under 20, 20-64, and 65+). Age groups are computed by summing sex-specific single-year age variables from 5-year ACS estimates. This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Age Demographics** data pipeline.

## Provenance
Directly tabulated from ACS 5-year estimates, table B01001 (Sex by Age). Age groups computed by summing sex-specific single-year age variables. Percentages calculated relative to total population (B01001_001).

## Coverage
- **Temporal coverage:** 2009–2024 (ACS 5-year estimates)
- **Geographic levels:** Block Group, County, Tract
- **Coverage areas:** National Capital Region (DC metro), Virginia (statewide)

## Methodology
The count of working-age residents (20-64) represents the primary labor force and tax base of a community. Changes in this group affect economic productivity, housing demand, and the ratio of dependents to workers.

The count of older adult residents (65+) captures the number of residents who are seniors. Communities with large senior populations face growing demand for geriatric health services, accessible transportation, affordable housing, and age-friendly infrastructure.

Total population count representing all residents across all age groups. This baseline figure serves as the denominator for computing age-group percentages and is essential for understanding the scale of a community's population. Changes in total population over time reflect broader trends in migration, development, and economic opportunity.

The count of youth residents (under 20) captures the number of residents who are children and adolescents. Communities with large youth populations have greater demand for schools, childcare, pediatric health services, and family support programs.

## Source Tables
- [5-Year estimates, table B01001, via the API](https://www.census.gov/data/developers/data-sets/acs-5year.html)

## Variables
- **B01001_001**: Total Pop
- **B01001_003**: M Under 5
- **B01001_004**: M 5 9
- **B01001_005**: M 10 14
- **B01001_006**: M 15 17
- **B01001_007**: M 18 19
- **B01001_008**: M 20
- **B01001_009**: M 21
- **B01001_010**: M 22 24
- **B01001_011**: M 25 29
- **B01001_012**: M 30 34
- **B01001_013**: M 35 39
- **B01001_014**: M 40 44
- **B01001_015**: M 45 49
- **B01001_016**: M 50 54
- **B01001_017**: M 55 59
- **B01001_018**: M 60 61
- **B01001_019**: M 62 64
- **B01001_020**: M 65 66
- **B01001_021**: M 67 69
- **B01001_022**: M 70 74
- **B01001_023**: M 75 79
- **B01001_024**: M 80 84
- **B01001_025**: M 85 Plus
- **B01001_027**: F Under 5
- **B01001_028**: F 5 9
- **B01001_029**: F 10 14
- **B01001_030**: F 15 17
- **B01001_031**: F 18 19
- **B01001_032**: F 20
- **B01001_033**: F 21
- **B01001_034**: F 22 24
- **B01001_035**: F 25 29
- **B01001_036**: F 30 34
- **B01001_037**: F 35 39
- **B01001_038**: F 40 44
- **B01001_039**: F 45 49
- **B01001_040**: F 50 54
- **B01001_041**: F 55 59
- **B01001_042**: F 60 61
- **B01001_043**: F 62 64
- **B01001_044**: F 65 66
- **B01001_045**: F 67 69
- **B01001_046**: F 70 74
- **B01001_047**: F 75 79
- **B01001_048**: F 80 84
- **B01001_049**: F 85 Plus

## Measures (7)
*Note on naming conventions: Measures containing `_geo20` are computed using 2020 Census geographic boundaries.*

- **age_20_64_count_geo20**: The population estimates between age 20 and 64. (arithmetic mean, unit: individual)
  Count of the population between age 20 and 64.
- **age_20_64_percent_geo20**: The population estimates between age 20 and 64. (percent, unit: individual)
  The percent of the population between age 20 and 64.
- **age_65_plus_count_geo20**: The population over age 64. (arithmetic mean, unit: individual)
  Count of the population over age 64.
- **age_65_plus_percent_geo20**: The percent of the population over age 64. (percent, unit: individual)
  The percent of the population over age 64.
- **age_total_count_geo20**: Total count of the population. (arithmetic mean, unit: individual)
  Total count of the population.
- **age_under_20_count_geo20**: The population estimates under age 20. (arithmetic mean, unit: individual)
  Count of the population under age 20.
- **age_under_20_percent_geo20**: The percent of the population under age 20. (percent, unit: individual)
  The percent of the population under age 20.

## Data Sources
- [American Community Survey (accessed 2025)](https://www.census.gov/programs-surveys/acs.html)

## File Format
Data files are provided as xz-compressed CSVs (`.csv.xz`) with the following columns: `geoid`, `year`, `measure`, `value`, `moe` (margin of error, where available), `region_type`, `data_method` (observed, modeled, scaled, interpolated, or extrapolated). A `measure_info.json` file provides per-measure metadata.
