## Overview
Access to care composite index for Virginia census tracts, counties, and health districts. Combines physician availability (primary care physicians within 30 driving miles, derived from CMS Medicare Physician & Other Practitioners PUF and OSRM-based block-group travel times) with insurance coverage (ACS 5-year uninsured rate for ages 19-64) into a z-score composite where higher values indicate better access to care. This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Access To Care** data pipeline.

## Provenance
Based on the Access to Care methodology originally developed by the Virginia Department of Health (VDH), Office of Minority Health and Health Equity (OMHHE) as part of their Health Opportunity Index (HOI). This pipeline reproduces and extends the VDH indicator using open data sources: CMS Medicare Physician PUF (primary care providers in VA, assigned to census tracts via HUD ZIP-to-tract crosswalk with residential ratio weighting) and ACS 5-year uninsured estimates. Physician accessibility uses OSRM-based driving distances between block group centroids, aggregated to tract level, with a 30-mile threshold. The composite index is the negated z-score of the sum of z-scored population-per-physician ratio and z-scored uninsured percentage.

Percentile rank of the access_care_indicator_geo20 z-score, following the Virginia Department of Health (VDH) Health Opportunity Index (HOI) methodology of converting z-score indicators to percentile ranks. Computed per year across all Virginia census tracts using pandas rank(pct=True). County and health district values are the mean of their constituent tract percentile ranks.

## Coverage
- **Temporal coverage:** 2017–2023 (annual, CMS PUF + ACS 5-year)
- **Geographic levels:** County, Health District, Tract
- **Coverage areas:** Virginia (statewide)

## Methodology
Composite z-score index measuring access to primary care. Combines two components: (1) population-to-physician ratio, using CMS Medicare Physician PUF data to count primary care physicians (Internal Medicine, Family Practice, Pediatric Medicine, OB/GYN) within 30 miles of each census tract via OSRM driving distances and HUD ZIP-to-tract crosswalk allocation; and (2) percentage of uninsured residents aged 19-64 from ACS 5-year estimates (B27010). The index is computed as -1 × z(z(pop_per_physician) + z(pct_uninsured)), so higher values indicate better access to care.

Percentile rank (0–1) of the access to care composite z-score index, computed per year across all Virginia census tracts. A value of 0.80 means the tract has better access to care than 80% of Virginia tracts in that year. Derived from the access_care_indicator_geo20 z-score by ranking tract values within each year and dividing by the number of tracts. County and health district values are the mean of their constituent tract percentile ranks.

## Source Tables
- [Medicare Physician & Other Practitioners - by Provider, 2017-2023](https://data.cms.gov/provider-summary-by-type-of-service/medicare-physician-other-practitioners/medicare-physician-other-practitioners-by-provider)
- [ACS 5-Year Estimates, Tables B01001 (Total Population) and B27010 (Health Insurance Coverage)](https://www.census.gov/data/developers/data-sets/acs-5year.html)
- [USPS ZIP Code-Census Tract Crosswalk, December 2021](https://www.huduser.gov/portal/datasets/usps_crosswalk.html)
- [Block-group-to-block-group driving distances, 8-state region (VA, MD, DC, DE, NC, TN, KY, WV)](https://project-osrm.org/)

## Variables
- **B01001_001**: Tot Pop
- **B27010_033**: Uninsured 19 34
- **B27010_050**: Uninsured 35 64

## Measures (2)
*Note on naming conventions: Measures containing `_geo20` are computed using 2020 Census geographic boundaries.*

- **access_care_indicator_geo20**: Access to care indicator (2020 geographies) (mean)
  Composite z-score of physician availability within 30 miles and insurance coverage rate.
- **access_care_pctile_geo20**: Access to care percentile (2020 geographies) (mean)
  Percentile rank of access to care z-score, where higher values indicate better access.

## Data Sources
- [CMS Medicare Physician & Other Practitioners PUF (accessed 2025)](https://data.cms.gov/provider-summary-by-type-of-service/medicare-physician-other-practitioners)
- [U.S. Census Bureau (accessed 2025)](https://www.census.gov/programs-surveys/acs.html)
- [HUD Office of Policy Development and Research (accessed 2025)](https://www.huduser.gov/portal/datasets/usps_crosswalk.html)
- [OSRM (Open Source Routing Machine) (accessed 2025)](https://project-osrm.org/)

## File Format
Data files are provided as xz-compressed CSV (`.csv.xz`) with the following columns: `geoid`, `region_type`, `region_name`, `year`, `measure`, `value`, `moe` (margin of error, where available).
