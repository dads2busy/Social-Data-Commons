## Overview
Townsend Material Deprivation Index for Virginia census tracts, counties, and health districts. Combines four ACS-derived indicators — unemployment rate, overcrowding, non-car ownership, and non-home ownership — into a z-score composite rescaled to 0–1, where higher values indicate greater material deprivation. This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Material Deprivation** data pipeline.

## Provenance
Based on the Townsend Material Deprivation Index (Townsend, Phillimore & Beattie, 1988), originally developed for the UK Census to measure area-level material deprivation. This pipeline adapts the methodology for U.S. Census ACS variables. The four component indicators (unemployment, overcrowding, non-car ownership, non-home ownership) are computed from ACS 5-year estimates, z-scored within year and geography level, summed, z-scored again, and min-max rescaled to [0, 1]. The VDH Health Opportunity Index includes a similar adaptation of the Townsend index as one of its 13 indicators.

## Coverage
- **Temporal coverage:** 2015–2024 (ACS 5-year estimates)
- **Geographic levels:** County, Tract
- **Coverage areas:** Virginia (statewide)

## Methodology
Townsend Material Deprivation Index adapted for U.S. Census data. Combines four ACS-derived indicators: (1) unemployment rate (B23025, log-transformed), (2) overcrowding — proportion of occupied housing units with more than 1 person per room (B25014, log-transformed), (3) non-car ownership — proportion of households with no vehicle (B25044), and (4) non-home ownership — proportion of renter-occupied units (S2502). Each indicator is z-scored within year and geography level, summed, the sum is z-scored again, then min-max rescaled to [0, 1]. Higher values indicate greater material deprivation. Computed using 2020 Census geographic boundaries.

Townsend Material Deprivation Index adapted for U.S. Census data. Combines four ACS-derived indicators: (1) unemployment rate (B23025, log-transformed), (2) overcrowding — proportion of occupied housing units with more than 1 person per room (B25014, log-transformed), (3) non-car ownership — proportion of households with no vehicle (B25044), and (4) non-home ownership — proportion of renter-occupied units (S2502). Each indicator is z-scored within year and geography level, summed, the sum is z-scored again, then min-max rescaled to [0, 1]. Higher values indicate greater material deprivation. Computed using 2010 Census geographic boundaries.

## Source Tables
- [ACS 5-Year Estimates, Tables B23025 (Employment Status), B25014 (Tenure by Occupants per Room), B25044 (Tenure by Vehicles Available), and S2502 (Demographic Characteristics for Occupied Housing Units)](https://www.census.gov/data/developers/data-sets/acs-5year.html)

## Variables
- **B23025_002**: Adult Pop
- **B23025_005**: Unemployed
- **B25014_001**: Occupancy All
- **B25014_005**: Occupant 1 Plus Per Room Owner
- **B25014_006**: Occupant 1 5 Per Room Owner
- **B25014_007**: Occupant 2 Plus Per Room Owner
- **B25014_011**: Occupant 1 Plus Per Room Renter
- **B25014_012**: Occupant 1 5 Per Room Renter
- **B25014_013**: Occupant 2 Plus Per Room Renter
- **B25044_001**: Households Total
- **B25044_003**: Hh Owner No Vehicle
- **B25044_010**: Hh Renter No Vehicle
- **S2502_C01_001**: All Occupied Units
- **S2502_C05_001**: Renter Occupied Units

## Measures (2)
*Note on naming conventions: Measures containing `_geo20` are computed using 2020 Census geographic boundaries, while those containing `_geo10` use 2010 Census geographic boundaries.*

- **material_deprivation_indicator_geo20**: Material deprivation indicator (2020 geographies) (mean)
  Townsend Material Deprivation Index (0-1) combining unemployment, overcrowding, non-car ownership, and non-home ownership.
- **material_deprivation_indicator_geo10**: Material deprivation indicator (2010 geographies) (mean)
  Townsend Material Deprivation Index (0-1) combining unemployment, overcrowding, non-car ownership, and non-home ownership.

## Data Sources
- [U.S. Census Bureau (accessed 2025)](https://www.census.gov/programs-surveys/acs.html)

## File Format
Data files are provided as xz-compressed CSV (`.csv.xz`) with the following columns: `geoid`, `region_type`, `region_name`, `year`, `measure`, `value`, `moe` (margin of error, where available).
