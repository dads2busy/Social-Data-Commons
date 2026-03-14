## Overview
Population gender distribution from ACS table B01001 (Sex by Age), providing counts and percentages for male and female populations. This dataset is produced by the Social Data Commons at the University of Virginia. This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Gender Demographics** data pipeline.

## Provenance
Directly tabulated from ACS 5-year estimates, table B01001 (Sex by Age). Female counts are from variable B01001_026. Values are available at Census tract, county, and block group levels on Census 2020 geography boundaries. Pre-2020 values have been standardized to 2020 boundaries using area-weighted crosswalks.

Calculated from ACS 5-year estimates, table B01001 (Sex by Age). Female counts (B01001_026) divided by total population (B01001_001). Values are available at Census tract, county, and block group levels on Census 2020 geography boundaries. Pre-2020 values have been standardized to 2020 boundaries using area-weighted crosswalks.

Directly tabulated from ACS 5-year estimates, table B01001 (Sex by Age). Male counts are from variable B01001_002. Values are available at Census tract, county, and block group levels on Census 2020 geography boundaries. Pre-2020 values have been standardized to 2020 boundaries using area-weighted crosswalks.

Calculated from ACS 5-year estimates, table B01001 (Sex by Age). Male counts (B01001_002) divided by total population (B01001_001). Values are available at Census tract, county, and block group levels on Census 2020 geography boundaries. Pre-2020 values have been standardized to 2020 boundaries using area-weighted crosswalks.

Directly tabulated from ACS 5-year estimates, table B01001 (Sex by Age), variable B01001_001 (total population). Values are available at Census tract, county, and block group levels on Census 2020 geography boundaries. Pre-2020 values have been standardized to 2020 boundaries using area-weighted crosswalks.

## Coverage
- **Temporal coverage:** 2009–2024 (ACS 5-year estimates)
- **Geographic levels:** Block Group, County, Tract
- **Coverage areas:** National Capital Region (DC metro), Virginia (statewide)

## Methodology
The count of female residents captures the size of the female population in a community. Gender-disaggregated population data is essential for planning services, allocating resources, and understanding demographic composition.

The female population share measures the proportion of residents who are female. Significant departures from the statewide average can reflect local labor markets (e.g., military bases, college towns), age structure, or migration patterns.

Total population count representing all residents regardless of gender. This baseline figure serves as the denominator for computing gender composition percentages and is essential for contextualizing a community's demographic profile. Changes in total population over time reflect broader trends in migration, development, and economic opportunity.

## Source Tables
- [5-Year estimates, table B01001, via the API](https://www.census.gov/data/developers/data-sets/acs-5year.html)

## Variables
- **B01001_001**: Total Pop
- **B01001_002**: Male
- **B01001_026**: Female

## Measures (5)
*Note on naming conventions: Measures containing `_geo20` are computed using 2020 Census geographic boundaries.*

- **gender_female_count_geo20**: The count of females in population. (arithmetic mean, unit: individual)
  Count of the female population.
- **gender_female_percent_geo20**: The percent of females in the total population. (percent, unit: individual)
  The percent of females in the total population.
- **gender_male_count_geo20**: The count of males in population. (arithmetic mean, unit: individual)
  Count of the male population.
- **gender_male_percent_geo20**: The percent of males in the total population. (percent, unit: individual)
  The percent of males in the total population.
- **gender_total_count_geo20**: Total count of the population. (arithmetic mean, unit: individual)
  Total count of the population.

## Data Sources
- [American Community Survey (accessed 2025)](https://www.census.gov/programs-surveys/acs.html)

## File Format
Data files are provided as CSVs (`.csv`) with the following columns: `geoid`, `region_type`, `region_name`, `year`, `measure`, `value`, `moe` (margin of error, where available). Larger files are provided as xz-compressed CSVs (`.csv.xz`).
