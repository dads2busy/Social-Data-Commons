## Overview
Housing and transportation affordability index independently reproduced using the Center for Neighborhood Technology (CNT) H+T Index methodology. Combines housing costs with modeled transportation costs (auto ownership, vehicle miles traveled, and transit use) as a percentage of household income for a Regional Typical Household. Transportation costs are derived from three regression models with 17 independent variables computed from ACS demographics, LEHD employment data, TIGER geographic boundaries, and GTFS transit schedules at block group resolution. This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Affordability Index** data pipeline.

## Provenance
Independently reproduced using the methodology published by the Center for Neighborhood Technology (CNT). Regression coefficients from CNT Tables 3-6 are applied to 17 independent variables computed from American Community Survey data, LEHD Origin-Destination Employment Statistics, TIGER geographic data, and GTFS transit feeds. Block group estimates are aggregated to tract and county via unweighted means.

## Coverage
- **Temporal coverage:** 2023–2023 (annual, ACS 5-year + GTFS + LEHD)
- **Geographic levels:** Block Group, County, Tract
- **Coverage areas:** National Capital Region (DC metro), Virginia (statewide)

## Methodology
The Housing + Transportation (H+T) Affordability Index measures the true cost of housing by combining housing and transportation costs as a percentage of household income. A neighborhood is considered affordable when H+T costs consume no more than 45% of household income. This measure uses the Regional Typical Household variant, which reflects a household earning the regional median income. Reproduced independently using CNT's published regression coefficients (Tables 3-6) applied to ACS demographic data, LEHD employment data, and GTFS transit schedule data at block group resolution.

Annual housing cost (weighted average of median owner costs and gross rent by tenure ratio) as a percentage of the regional median household income. Part of the H+T Affordability Index decomposition.

Annual transportation cost (auto ownership + vehicle miles traveled + transit use) as a percentage of the regional median household income. Derived from CNT regression models for auto ownership, VMT, and transit ridership applied to neighborhood-level variables.

Predicted automobile ownership per household from the CNT auto ownership regression model. Uses household income, density, transit access, employment gravity, and housing stock characteristics as predictors.

Predicted annual vehicle miles traveled per household from the CNT VMT regression model. Reflects how neighborhood density, transit access, employment access, and housing patterns influence driving behavior.

Predicted fraction of commuters using public transit from the CNT transit use regression model (quasibinomial). Reflects how transit connectivity, employment access, density, and household characteristics influence transit ridership. Block groups with no transit service are assigned 0%.

## Source Tables
- [H+T Affordability Index Methods](https://htaindex.cnt.org/about/HTMethods_2016.pdf)
- U.S. Census Bureau, 2023
- Mobility Database, 2023 feeds
- H+T Affordability Index Methods, Table 4
- H+T Affordability Index Methods, Table 5
- H+T Affordability Index Methods, Table 6

## Variables
- **B19013_001**: Median Hh Income
- **B11001_001**: Total Hh
- **B25003_002**: Owner Occupied
- **B25003_003**: Renter Occupied
- **B25003_001**: Total Occupied
- **B25024_002**: Units 1 Detached
- **B25024_001**: Total Units
- **B08301_001**: Workers 16Plus
- **B08301_003**: Workers Drove Alone
- **B08301_004**: Workers Carpool
- **B08301_010**: Workers Transit
- **B08301_019**: Workers Walked
- **B08301_020**: Workers Other
- **B08301_021**: Workers Wfh
- **B25008_001**: Pop In Occ Hu
- **B01003_001**: Total Pop
- **B25088_002**: Median Owner Cost
- **B25064_001**: Median Gross Rent
- **B25009_002**: Hh Size Owner
- **B25009_010**: Hh Size Renter

## Measures (6)
- **affordability_index**: Housing + Transportation Affordability Index (mean, unit: percent)
  Proportion of income spent on combined housing and transportation costs for a Regional Typical Household.
- **housing_cost_pct**: Housing Cost as Percent of Income (mean, unit: percent)
  Housing cost as a percentage of income for a Regional Typical Household.
- **transport_cost_pct**: Transportation Cost as Percent of Income (mean, unit: percent)
  Transportation cost as a percentage of income for a Regional Typical Household.
- **autos_per_hh**: Predicted Autos per Household (mean, unit: vehicles)
  Predicted number of automobiles per household based on neighborhood characteristics.
- **vmt_per_hh**: Predicted Annual Vehicle Miles Traveled per Household (mean, unit: miles)
  Predicted annual vehicle miles traveled per household based on neighborhood characteristics.
- **transit_frac**: Predicted Transit Commuter Fraction (mean, unit: percent)
  Predicted fraction of commuters using public transit based on neighborhood characteristics.

## Data Sources
- [Center for Neighborhood Technology](https://htaindex.cnt.org/)
- [American Community Survey 5-Year Estimates](https://www.census.gov/programs-surveys/acs)
- [LEHD Origin-Destination Employment Statistics](https://lehd.ces.census.gov/data/)
- [General Transit Feed Specification (GTFS)](https://mobilitydatabase.org/)

## File Format
Data files are provided as xz-compressed CSV (`.csv.xz`) with the following columns: `geoid`, `region_type`, `region_name`, `year`, `measure`, `value`, `moe` (margin of error, where available).
