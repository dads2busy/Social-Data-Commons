## Overview
Race and ethnicity distribution from ACS tables B02001 (Race) and B03003 (Hispanic or Latino Origin), providing counts and percentages for seven race/ethnicity categories including White, Black/African American, American Indian/Alaska Native, Asian American/Pacific Islander, Other, Two or More Races, and Hispanic/Latino. This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Race Demographics** data pipeline.

## Provenance
Directly tabulated from ACS 5-year estimates, tables B02001 (Race) and B03003 (Hispanic or Latino Origin). Asian American/Pacific Islander is a combined category from B02001_005 (Asian alone) and B02001_006 (Native Hawaiian/Other Pacific Islander alone). Percentages are calculated relative to total population (B02001_001 for race, B03003_001 for ethnicity).

Directly tabulated from ACS 5-year estimates, tables B02001 (Race) and B03003 (Hispanic or Latino Origin). Black or African American alone is B02001_003. Percentages are calculated relative to total population (B02001_001 for race, B03003_001 for ethnicity).

Directly tabulated from ACS 5-year estimates, table B02001 (Race). Total population is B02001_001.

Directly tabulated from ACS 5-year estimates, table B03003 (Hispanic or Latino Origin). Hispanic or Latino is B03003_003. Percentages are calculated relative to total population (B03003_001 for ethnicity).

Directly tabulated from ACS 5-year estimates, tables B02001 (Race) and B03003 (Hispanic or Latino Origin). American Indian or Alaska Native alone is B02001_004. Percentages are calculated relative to total population (B02001_001 for race, B03003_001 for ethnicity).

Directly tabulated from ACS 5-year estimates, tables B02001 (Race) and B03003 (Hispanic or Latino Origin). Some Other Race alone is B02001_007. Percentages are calculated relative to total population (B02001_001 for race, B03003_001 for ethnicity).

Directly tabulated from ACS 5-year estimates, tables B02001 (Race) and B03003 (Hispanic or Latino Origin). Two or More Races is B02001_008. Percentages are calculated relative to total population (B02001_001 for race, B03003_001 for ethnicity).

Directly tabulated from ACS 5-year estimates, tables B02001 (Race) and B03003 (Hispanic or Latino Origin). White alone is B02001_002. Percentages are calculated relative to total population (B02001_001 for race, B03003_001 for ethnicity).

## Coverage
- **Temporal coverage:** 2009–2024 (ACS 5-year estimates)
- **Geographic levels:** Block Group, County, Tract
- **Coverage areas:** National Capital Region (DC metro), Virginia (statewide)

## Methodology
Count of Asian American/Pacific Islander residents in a community. Racial and ethnic composition data tracks the Asian American/Pacific Islander population in a community. Understanding demographic diversity is essential for equitable resource allocation, culturally competent service delivery, and monitoring disparities across groups.

Racial and ethnic composition data tracks the Asian American/Pacific Islander population in a community. Understanding demographic diversity is essential for equitable resource allocation, culturally competent service delivery, and monitoring disparities across groups.

Count of Black or African American residents in a community. Racial and ethnic composition data tracks the Black or African American population in a community. Understanding demographic diversity is essential for equitable resource allocation, culturally competent service delivery, and monitoring disparities across groups.

Total population from the race/ethnicity table. This count serves as the denominator for calculating racial and ethnic composition percentages and provides the baseline population figure for a community.

Count of Hispanic or Latino residents in a community. Racial and ethnic composition data tracks the Hispanic or Latino population in a community. Understanding demographic diversity is essential for equitable resource allocation, culturally competent service delivery, and monitoring disparities across groups.

Count of American Indian or Alaska Native residents in a community. Racial and ethnic composition data tracks the American Indian or Alaska Native population in a community. Understanding demographic diversity is essential for equitable resource allocation, culturally competent service delivery, and monitoring disparities across groups.

Count of residents identifying as Some Other Race alone in a community. Racial and ethnic composition data tracks the Some Other Race population in a community. Understanding demographic diversity is essential for equitable resource allocation, culturally competent service delivery, and monitoring disparities across groups.

Count of residents identifying as Two or More Races in a community. Racial and ethnic composition data tracks the Two or More Races population in a community. Understanding demographic diversity is essential for equitable resource allocation, culturally competent service delivery, and monitoring disparities across groups.

Count of White residents in a community. Racial and ethnic composition data tracks the White population in a community. Understanding demographic diversity is essential for equitable resource allocation, culturally competent service delivery, and monitoring disparities across groups.

## Source Tables
- [5-Year estimates, tables B02001 and B03003, via the API](https://www.census.gov/data/developers/data-sets/acs-5year.html)

## Variables
- **B02001_001**: Total Race
- **B02001_002**: Wht Alone
- **B02001_003**: Afr Amer Alone
- **B02001_004**: Native Alone
- **B02001_005**: Asian Alone
- **B02001_006**: Pacific Islander Alone
- **B02001_007**: Other
- **B02001_008**: Two Or More
- **B03003_001**: Eth Total
- **B03003_003**: Hispanic Or Latino

## Measures (15)
*Note on naming conventions: Measures containing `_geo20` are computed using 2020 Census geographic boundaries.*

- **race_AAPI_count_geo20**: The Asian American/Pacific Islander population. (arithmetic mean, unit: individual)
  Count of the Asian American/Pacific Islander population.
- **race_AAPI_percent_geo20**: The Asian American/Pacific Islander population percent. (percent, unit: individual)
  The Asian American/Pacific Islander population percent.
- **race_afr_amer_alone_count_geo20**: The Black population. (arithmetic mean, unit: individual)
  Count of the Black or African American population.
- **race_afr_amer_alone_percent_geo20**: The Black population percent. (percent, unit: individual)
  The Black or African American population percent.
- **race_total_count_geo20**: Total count of the population. (arithmetic mean, unit: individual)
  Total count of the population.
- **race_hispanic_or_latino_count_geo20**: The Hispanic/Latino population. (arithmetic mean, unit: individual)
  Count of the Hispanic/Latino population.
- **race_hispanic_or_latino_percent_geo20**: The Hispanic/Latino population percent. (percent, unit: individual)
  The Hispanic/Latino population percent.
- **race_native_alone_count_geo20**: The Native population. (arithmetic mean, unit: individual)
  Count of the American Indian or Alaska Native population.
- **race_native_alone_percent_geo20**: The Native population percent. (percent, unit: individual)
  The American Indian or Alaska Native population percent.
- **race_other_count_geo20**: The Other racial population. (arithmetic mean, unit: individual)
  Count of the Other racial population.
- **race_other_percent_geo20**: The Other racial population percent. (percent, unit: individual)
  The Other racial population percent.
- **race_two_or_more_count_geo20**: The two or more races population. (arithmetic mean, unit: individual)
  Count of the Two or More Races population.
- **race_two_or_more_percent_geo20**: The two or more races population percent. (percent, unit: individual)
  The Two or More Races population percent.
- **race_wht_alone_count_geo20**: The White population. (arithmetic mean, unit: individual)
  Count of the White population.
- **race_wht_alone_percent_geo20**: The White population percent. (percent, unit: individual)
  The White population percent.

## Data Sources
- [American Community Survey (accessed 2025)](https://www.census.gov/programs-surveys/acs.html)

## File Format
Data files are provided as xz-compressed CSVs (`.csv.xz`) with the following columns: `geoid`, `year`, `measure`, `value`, `moe` (margin of error, where available), `region_type`, `data_method` (observed, modeled, scaled, interpolated, or extrapolated). A `measure_info.json` file provides per-measure metadata.
