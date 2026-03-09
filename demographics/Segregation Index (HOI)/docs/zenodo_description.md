## Overview
Residential segregation indicator computed as the Entropy Index (Theil's H) from ACS table B03002 (Hispanic or Latino Origin by Race) race/ethnicity data, measuring how sub-area racial/ethnic composition differs from the overall state composition. The index uses eight race/ethnicity categories: Hispanic/Latino, White, Black, American Indian, Asian, Native Hawaiian/Pacific Islander, Some Other Race, and Two or More Races. Builds on methodology used in the Virginia Department of Health's Health Opportunity Index (HOI). This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Segregation** data pipeline.

## Provenance
The segregation indicator uses the Entropy Index (Theil's H), a method for measuring multigroup residential segregation that quantifies how sub-area racial/ethnic composition differs from the overall composition (Theil, 1972; Reardon & Firebaugh, 2002). This pipeline builds on methodology developed by the Virginia Department of Health, Office of Minority Health and Health Equity (VDH-OMHHE) for the Health Opportunity Index (HOI), which includes a segregation indicator as one of its 13 community health profiles.

## Coverage
- **Temporal coverage:** 2015–2024 (ACS 5-year estimates)
- **Geographic levels:** Block Group, County, Tract
- **Coverage areas:** National Capital Region (DC metro), Virginia (statewide)

## Methodology
Residential segregation indicator computed as the Entropy Index (Theil's H) from ACS 5-year estimates, table B03002 (Hispanic or Latino Origin by Race). The index measures how the racial/ethnic composition of a sub-area compares to that of the state as a whole, using eight categories: Hispanic/Latino, White, Black/African American, American Indian/Alaska Native, Asian, Native Hawaiian/Other Pacific Islander, Some Other Race, and Two or More Races. Higher values indicate greater deviation from the statewide racial/ethnic composition. County and Health District values are aggregated from tract-level scores. Computed using 2020 Census geographic boundaries.

Residential segregation indicator computed as the Entropy Index (Theil's H) from ACS 5-year estimates, table B03002 (Hispanic or Latino Origin by Race). The index measures how the racial/ethnic composition of a sub-area compares to that of the state as a whole, using eight categories: Hispanic/Latino, White, Black/African American, American Indian/Alaska Native, Asian, Native Hawaiian/Other Pacific Islander, Some Other Race, and Two or More Races. Higher values indicate greater deviation from the statewide racial/ethnic composition. County and Health District values are aggregated from tract-level scores. Computed using 2010 Census geographic boundaries.

## Source Tables
- [ACS 5-Year Estimates, Table B03002 (Hispanic or Latino Origin by Race)](https://www.census.gov/data/developers/data-sets/acs-5year.html)

## Variables
- **B03002_001**: Total Pop
- **B03002_012**: Hisp Latin
- **B03002_003**: White
- **B03002_004**: Black
- **B03002_005**: American Indian
- **B03002_006**: Asian
- **B03002_007**: Nhopi
- **B03002_008**: Sor
- **B03002_009**: Two

## Measures (2)
*Note on naming conventions: Measures containing `_geo20` are computed using 2020 Census geographic boundaries, while those containing `_geo10` use 2010 Census geographic boundaries.*

- **segregation_indicator_geo20**: Segregation indicator (2020 geographies) (mean)
  Entropy Index (Theil's H) measuring how sub-area racial/ethnic composition differs from the overall state composition.
- **segregation_indicator_geo10**: Segregation indicator (2010 geographies) (mean)
  Entropy Index (Theil's H) measuring how sub-area racial/ethnic composition differs from the overall state composition.

## Data Sources
- [U.S. Census Bureau (accessed 2025)](https://www.census.gov/programs-surveys/acs.html)

## File Format
Data files are provided as xz-compressed CSV (`.csv.xz`) with the following columns: `geoid`, `region_type`, `region_name`, `year`, `measure`, `value`, `moe` (margin of error, where available).
