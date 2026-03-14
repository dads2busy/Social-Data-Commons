## Overview
Multi-year Walkability Index derived from LEHD-LODES employment entropy, GTFS transit proximity, and EPA Smart Location Database street connectivity. Each block group is scored using the formula NatWalkInd = D2A_Ranked/6 + D2B_Ranked/6 + D3B_Ranked/3 + D4C_Ranked/3, where D2A and D2B are employment/household land use entropy from LODES WAC job counts and ACS household data, D3B is street intersection density from the EPA SLD, and D4C is distance to the nearest transit stop from GTFS feeds. Components are ranked into 20 quantile bins before combining. Block group scores are aggregated to Census tracts and counties using population-weighted means. This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Walkability Index** data pipeline.

## Provenance
Derived from the EPA National Walkability Index methodology. Employment entropy (D2A/D2B) computed annually from LEHD LODES + ACS data. Street connectivity (D3B) from EPA SLD V3. Transit proximity (D4C) computed annually from national GTFS feeds. Formula: NatWalkInd = D2A_Ranked/6 + D2B_Ranked/6 + D3B_Ranked/3 + D4C_Ranked/3.

## Coverage
- **Temporal coverage:** 2017–2023 (annual, LODES + GTFS)
- **Geographic levels:** County, Health District, Tract
- **Coverage areas:** National Capital Region (DC metro), United States (national), Virginia (statewide)

## Methodology
The Walkability Index is a composite measure that ranks block groups according to their relative walkability, computed annually for 2017-2023. It combines four components: (1) D2A_Ranked — employment and household land use entropy from LEHD LODES WAC job counts by NAICS sector and ACS B11001 household counts, measuring the diversity of nearby land uses; (2) D2B_Ranked — employment-only entropy across five tiers (retail, office, industrial, service, entertainment); (3) D3B_Ranked — street intersection density from the EPA Smart Location Database V3, measuring pedestrian-friendly street connectivity; and (4) D4C_Ranked — distance to the nearest transit stop computed from national GTFS feeds via the Mobility Database, measuring transit accessibility. Each component is ranked into 20 quantile bins across all block groups in the coverage area. The final index is calculated as NatWalkInd = D2A_Ranked/6 + D2B_Ranked/6 + D3B_Ranked/3 + D4C_Ranked/3, producing scores from 1 (least walkable) to 20 (most walkable). Block group scores are aggregated to Census tracts and counties using population-weighted means.

## Source Tables
- [Smart Location Database V3, January 2021](https://www.epa.gov/smartgrowth/smart-location-mapping#walkability)
- [LODES 8 Workplace Area Characteristics](https://lehd.ces.census.gov/data/lodes/LODES8/)
- [ACS 5-Year Estimates, Table B11001 (Household Type)](https://data.census.gov/table/ACSDT5Y2023.B11001)
- [Mobility Database and Transitland GTFS feeds](https://mobilitydatabase.org)
- [Census 2010 Centers of Population (block group centroids)](https://www.census.gov/geographies/reference-files/time-series/geo/centers-population.html)

## Variables
- **Custom NatWalkInd = D2A_Ranked/6 + D2B_Ranked/6 + D3B_Ranked/3 + D4C_Ranked/3**: Walkability Index

## Measures (1)
*Note on naming conventions: Measures containing `_geo20` are computed using 2020 Census geographic boundaries.*

- **walkability_index_geo20**: Walkability Index (population-weighted mean, unit: index score)
  Composite walkability score (1-20) combining employment entropy, street connectivity, and transit proximity, updated annually from LODES, EPA SLD, and GTFS data.

## Data Sources
- [Environmental Protection Agency (accessed 2025)](https://www.epa.gov/smartgrowth/smart-location-mapping)
- [Census Bureau LEHD (accessed 2025)](https://lehd.ces.census.gov/)
- [Census Bureau ACS (accessed 2025)](https://data.census.gov)
- [GTFS Transit Feeds (accessed 2025)](https://mobilitydatabase.org)
- [Census Bureau (accessed 2025)](https://www.census.gov)

## File Format
Data files are provided as CSVs (`.csv`) with the following columns: `geoid`, `region_type`, `region_name`, `year`, `measure`, `value`, `moe` (margin of error, where available). Larger files are provided as xz-compressed CSVs (`.csv.xz`).
