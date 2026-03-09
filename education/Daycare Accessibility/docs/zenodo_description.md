## Overview
Daycare accessibility measures for Virginia, including minimum drive time to nearest provider, total capacity, and floating catchment area ratios (seats per 1,000 children) for three age groups. Uses VDSS facility data, ACS child population estimates, and OSRM-based travel times. This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Daycare Access** data pipeline.

## Provenance
Total licensed day care capacity reported by the Virginia Department of Social Services, summed within each geographic region.

Minimum drive time from block group centroids to day care providers, calculated using the Open Source Routing Machine with pre-computed BG-to-BG travel times.

Day care availability ratios are calculated using the 3-step floating catchment area (3SFCA) method (Wan et al., 2012), with distance-weighted Gaussian decay.

## Coverage
- **Temporal coverage:** 2021–2025 (VDSS facility data + ACS 5-year estimates)
- **Geographic levels:** Block Group
- **Coverage areas:** Virginia (statewide)

## Methodology
Summed capacity (seats) of all day care providers within the region, according to the Virginia Department of Social Services.

Time (minutes) to drive to the nearest day care provider of any type. Times are calculated using the Open Source Routing Machine, from block group centroids to each provider. Times for higher geographic levels are averaged across block groups.

Number of day care seats per 1,000 children under 15 years of age, which accept at least ages 4 to 10, as calculated within floating catchment areas. Catchment area ratios are based on the population of children under 15 within block groups (as estimated in the American Community Survey), capacity of eligible day care providers (as reported by the Virginia Department of Social Services), and travel times between block group centroids and day care locations (as calculated with the Open Source Routing Machine). Catchment areas are weighted by travel time with a Gaussian function with scale of 18, which are normalized for each consumer (for a 3-step floating catchment area).

Number of day care seats per 1,000 children between 5 and 14 years of age, which accept at least some ages over 4, as calculated within floating catchment areas. Catchment area ratios are based on the population of children over 4 within block groups (as estimated in the American Community Survey), capacity of eligible day care providers (as reported by the Virginia Department of Social Services), and travel times between block group centroids and day care locations (as calculated with the Open Source Routing Machine). Catchment areas are weighted by travel time with a Gaussian function with scale of 18, which are normalized for each consumer (for a 3-step floating catchment area).

Number of day care seats per 1,000 children under 10 years of age, which accept at least some ages under 10, as calculated within floating catchment areas. Catchment area ratios are based on the population of children under 10 within block groups (as estimated in the American Community Survey), capacity of eligible day care providers (as reported by the Virginia Department of Social Services), and travel times between block group centroids and day care locations (as calculated with the Open Source Routing Machine). Catchment areas are weighted by travel time with a Gaussian function with scale of 18, which are normalized for each consumer (for a 3-step floating catchment area).

## Source Tables
- [Child Day Care Search](https://www.dss.virginia.gov/facility/search/cc2.cgi)
- [Pre-computed BG-to-BG travel time matrices](http://project-osrm.org)
- [ACS 5-Year, Table B01001 (Sex by Age)](https://data.census.gov/table/ACSDT5Y2024.B01001)

## Variables
- **B01001_003**: Male Under 5
- **B01001_027**: Female Under 5
- **B01001_004**: Male 5 9
- **B01001_028**: Female 5 9
- **B01001_005**: Male 10 14
- **B01001_029**: Female 10 14

## Measures (5)
- **daycare_capacity**: Day Care Capacity (seats) (count, unit: day care seat)
  Total number of licensed day care seats in the region, from VDSS facility records.
- **daycare_min_drivetime**: Minutes to Nearest Day Care (minimum, unit: minute)
  Drive time in minutes to the nearest day care provider, based on OSRM routing from block group centroids.
- **daycare_ratio**: Day Care Seats Per 1k Children Under 15, Accepting at Least Ages 4-10 (ratio, unit: day care seat per 1k children)
  Day care seats per 1,000 children under 15, using a 3-step floating catchment area method with Gaussian distance-decay weighting.
- **daycare_ratio_over_4**: Day Care Seats Per 1k Children Between 5 and 14, With Minimal Accepted Age Over 4 (ratio, unit: day care seat per 1k children)
  Day care seats per 1,000 children ages 5-14, using 3SFCA method. Only providers accepting ages over 4.
- **daycare_ratio_under_10**: Day Care Seats Per 1k Children Under 10, With Maximal Accepted Age Under 10 (ratio, unit: day care seat per 1k children)
  Day care seats per 1,000 children under 10, using 3SFCA method. Only providers accepting ages under 10.

## Data Sources
- [Virginia Department of Social Services (accessed 2025)](https://www.dss.virginia.gov)
- [Open Source Routing Machine (accessed 2025)](http://project-osrm.org)
- [American Community Survey (accessed 2025)](https://www.census.gov/programs-surveys/acs.html)

## File Format
Data files are provided as xz-compressed CSV (`.csv.xz`) with the following columns: `geoid`, `region_type`, `region_name`, `year`, `measure`, `value`, `moe` (margin of error, where available).
