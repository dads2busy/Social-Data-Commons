## Overview
Floating catchment area analysis measuring pediatric service accessibility at block group level using population ages 0-17 as consumer demand. Computes 2SFCA, E2SFCA, and 3SFCA variants with physician counts from CMS Doctors and Clinicians data (PEDIATRIC MEDICINE specialty). Covers 2018-2025 with automated CMS download and Census geocoding. This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Pediatric Access Scores** data pipeline.

## Provenance
Provider counts derived from CMS Doctors and Clinicians dataset (2018-2025), filtered to PEDIATRIC MEDICINE specialty with MD/DO credentials in VA/DC/MD. Addresses geocoded via Census Geocoder API and snapped to nearest 2020 block group centroid. Counts summed from block group to tract, county, and health district.

Travel times from pre-computed OSRM block-group-to-block-group driving time matrices (2020 boundaries). For each block group, the 10 nearest pediatrician locations (by travel time) are identified and their mean travel time computed. Aggregated to tract/county/HD via simple mean across constituent block groups.

Travel times from pre-computed OSRM block-group-to-block-group driving time matrices (2020 boundaries). For each block group, the 10 nearest pediatrician locations (by travel time) are identified and their median travel time computed. Aggregated to tract/county/HD via simple mean of block group medians.

Two-step floating catchment area (2SFCA) with 30-minute travel time threshold. Supply: CMS Doctors and Clinicians PEDIATRIC MEDICINE providers (MD/DO) in VA/DC/MD, geocoded and snapped to 2020 block group centroids. Demand: ACS B01001 population ages 0-17 (variables B01001_003-006, B01001_027-030) at block group level. Travel costs from OSRM driving time matrices. Values expressed per 1,000 population. Aggregated to tract/county via population-weighted mean.

Enhanced two-step floating catchment area (E2SFCA) with stepped distance decay weights: 10 min=0.962, 20 min=0.704, 30 min=0.377, 60 min=0.042. Supply: CMS Doctors and Clinicians PEDIATRIC MEDICINE providers. Demand: ACS B01001 population ages 0-17. Travel costs from OSRM driving time matrices. Values per 1,000 population. Aggregated to tract/county via population-weighted mean.

Three-step floating catchment area (3SFCA) with Gaussian distance decay (scale=20) and normalized competition weights. Supply: CMS Doctors and Clinicians PEDIATRIC MEDICINE providers. Demand: ACS B01001 population ages 0-17. Travel costs from OSRM driving time matrices. Values per 1,000 population. Aggregated to tract/county via population-weighted mean.

## Coverage
- **Coverage areas:** CMS

## Methodology
Count of pediatric medicine physicians located within each geographic area. Pediatricians are identified from the CMS Doctors and Clinicians dataset by filtering to providers with a PEDIATRIC MEDICINE specialty designation and MD/DO credentials. Higher counts indicate greater local availability of pediatric care providers, though counts alone do not account for population demand or geographic accessibility barriers.

Average travel time in minutes to the nearest 10 pediatric medicine physicians from each block group centroid. This measure captures geographic proximity to pediatric care, with higher values indicating communities where families must travel farther to access multiple pediatric providers. Areas with long travel times to pediatricians may face barriers to routine well-child visits, vaccinations, and acute care for children.

Median travel time in minutes to the nearest 10 pediatric medicine physicians from each block group centroid. The median is more robust to outliers than the mean, providing a better sense of typical accessibility. Communities with high median travel times face systematic barriers to pediatric care access that may result in delayed treatment and lower utilization of preventive services for children.

Pediatric care accessibility measured using the two-step floating catchment area (2SFCA) method. This index accounts for both the supply of pediatricians and the demand from the population aged 0-17, weighted by travel time within a 30-minute catchment. Higher values indicate better spatial access to pediatric care relative to the child population, while lower values suggest potential shortages that could affect timely access to well-child visits and acute care.

Pediatric care accessibility measured using the enhanced two-step floating catchment area (E2SFCA) method. Unlike the basic 2SFCA, this variant applies stepped distance decay weights (10 min: 0.962, 20 min: 0.704, 30 min: 0.377, 60 min: 0.042), better reflecting how families' willingness to travel for pediatric care decreases with distance. Higher values indicate greater spatial accessibility to pediatric physicians relative to child population demand.

Pediatric care accessibility measured using the three-step floating catchment area (3SFCA) method with Gaussian distance decay. This is the most sophisticated FCA variant, normalizing competition weights so that each consumer's demand is distributed proportionally across reachable providers. It provides the most realistic estimate of pediatric care accessibility by accounting for provider competition and distance sensitivity simultaneously.

## Measures (6)
- **peds_cnt**: Pediatric care availability by count (count)
  Number of pediatric medicine physicians (MD/DO) from CMS Doctors and Clinicians data within each area.
- **peds_near_10_mean**: Mean travel time to nearest 10 pediatricians (count, unit: minutes)
  Mean driving time in minutes from block group centroid to the 10 nearest pediatric medicine physicians.
- **peds_near_10_median**: Median travel time to nearest 10 pediatricians (count, unit: minutes)
  Median driving time in minutes from block group centroid to the 10 nearest pediatric medicine physicians.
- **peds_2sfca**: Pediatric care geographic availability (2-step floating catchment areas) (index)
  Spatial accessibility index for pediatric physicians per 1,000 children aged 0-17, using 2-step floating catchment area method.
- **peds_e2sfca**: Pediatric care geographic availability (enhanced 2-step floating catchment areas) (index)
  Spatial accessibility index for pediatric physicians per 1,000 children aged 0-17, using enhanced 2-step floating catchment area method with distance decay.
- **peds_3sfca**: Pediatric care geographic availability (3-step floating catchment areas) (index)
  Spatial accessibility index for pediatric physicians per 1,000 children aged 0-17, using 3-step floating catchment area method with Gaussian decay.

## Data Sources
- [CMS Doctors and Clinicians (accessed 2025)](https://data.cms.gov/provider-data/dataset/mj5m-pzi6)

## File Format
Data files are provided as CSVs (`.csv`) with the following columns: `geoid`, `region_type`, `region_name`, `year`, `measure`, `value`, `moe` (margin of error, where available). Larger files are provided as xz-compressed CSVs (`.csv.xz`).
