## Overview
Residential segregation indicator computed as the Entropy Index (Theil's H) from ACS table B03002 (Hispanic or Latino Origin by Race) race/ethnicity data, measuring how sub-area racial/ethnic composition differs from the overall state composition. The index uses eight race/ethnicity categories: Hispanic/Latino, White, Black, American Indian, Asian, Native Hawaiian/Pacific Islander, Some Other Race, and Two or More Races. Builds on methodology used in the Virginia Department of Health's Health Opportunity Index (HOI). This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Segregation** data pipeline.

## Provenance
The segregation indicator uses the Entropy Index (Theil's H), a method for measuring multigroup residential segregation that quantifies how sub-area racial/ethnic composition differs from the overall composition (Theil, 1972; Reardon & Firebaugh, 2002). This pipeline builds on methodology developed by the Virginia Department of Health, Office of Minority Health and Health Equity (VDH-OMHHE) for the Health Opportunity Index (HOI), which includes a segregation indicator as one of its 13 community health profiles.

## Coverage
- **Temporal coverage:** 2015–2024 (ACS 5-year estimates)
- **Geographic levels:** Block Group, County, Tract
- **Coverage areas:** National Capital Region (DC metro), Virginia (statewide)

## Methodology
The Segregation Index measures how much a community's racial and ethnic composition differs from the state as a whole, using the Entropy Index (Theil's H) across eight racial/ethnic categories. Communities with high segregation values tend to have more concentrated poverty, unequal access to services, and wider disparities in educational and economic outcomes. As a component of the VDH Health Opportunity Index Social Impact profile, this measure helps identify areas where residential sorting by race may reinforce structural inequities.

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

## Measures (1)
*Note on naming conventions: Measures containing `_geo20` are reported on 2020 Census tract boundaries. Pre-2020 estimates are standardized from 2010 to 2020 census tract boundaries using an area-based crosswalk: intensive measures (rates, percentages, medians, per-household quantities, densities, and composite indices) are assigned the value of the area-dominant 2010 tract rather than area-averaged, so the measure's scale is preserved.*

- **segregation_indicator_geo20**: Segregation Indicator (mean, unit: index score)
  Entropy Index (Theil's H) measuring how sub-area racial/ethnic composition differs from the overall state composition.

## Data Sources
- [U.S. Census Bureau (accessed 2025)](https://www.census.gov/programs-surveys/acs.html)

## File Format
Data files are provided as xz-compressed CSVs (`.csv.xz`) with the following columns: `geoid`, `year`, `measure`, `value`, `moe` (margin of error, where available), `region_type`, `data_method` (observed, modeled, scaled, interpolated, or extrapolated). A `measure_info.json` file provides per-measure metadata.
