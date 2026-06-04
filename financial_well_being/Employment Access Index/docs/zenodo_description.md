## Overview
Employment Intensity (gravity model) from LEHD-LODES WAC job counts and TIGER/Line centroids. E = sum(jobs_i / dist_i^2) with hierarchical distance approximation and 200-mile radius cutoff. This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Employment Access** data pipeline.

## Provenance
Computed using a gravity model from LEHD-LODES Workplace Area Characteristics (WAC) job counts and TIGER/Line Census block centroids. Employment intensity is calculated as the sum of jobs divided by the square of the distance (in miles) from each Census block group to all nearby employment locations, using a hierarchical distance approximation: individual block-level job counts within 34 miles, tract-level aggregates from 34 to 165 miles, and county-level aggregates from 165 to 200 miles. Inspired by the Center for Neighborhood Technology (CNT) H+T Affordability Index gravity model approach.

## Coverage
- **Temporal coverage:** 2015–2023 (ACS 5-year estimates)
- **Geographic levels:** County, Tract
- **Coverage areas:** Virginia (statewide)

## Methodology
The Employment Access Index quantifies how easily residents of a community can reach jobs, using a gravity model that accounts for both the number of nearby jobs and the distance to them. Communities with low employment access face longer commutes, higher transportation costs, and fewer economic opportunities, all of which contribute to financial instability and reduced quality of life. This measure is a key input to the VDH Health Opportunity Index, where it contributes to the Economic Opportunity profile.

## Source Tables
- [LODES WAC S000 JT00, column C000 (total jobs per Census block)](https://lehd.ces.census.gov/data/lodes/LODES8/)
- [TABBLOCK20, BG, TRACT, COUNTY shapefiles (INTPTLAT, INTPTLON fields)](https://www2.census.gov/geo/tiger/TIGER2020/)

## Measures (1)
*Note on naming conventions: Measures containing `_geo20` are reported on 2020 Census tract boundaries.*

- **employment_access_index_geo20**: Employment Access Index (mean, unit: index score)
  Gravity-based index of employment accessibility measuring proximity to jobs, weighted by distance decay.

## Data Sources
- [LEHD-LODES Workplace Area Characteristics (accessed 2026)](https://lehd.ces.census.gov/data/lodes/)
- [TIGER/Line Shapefiles (2020 Census Geography) (accessed 2026)](https://www2.census.gov/geo/tiger/TIGER2020/)

## File Format
Data files are provided as CSVs (`.csv`) with the following columns: `geoid`, `year`, `measure`, `value`, `moe` (margin of error, where available), `region_type`, `data_method` (observed, modeled, scaled, interpolated, or extrapolated). Per-measure metadata (descriptions, units, and sources) is documented in the dataset's `measure_info.json` in the Social Data Commons repository.
