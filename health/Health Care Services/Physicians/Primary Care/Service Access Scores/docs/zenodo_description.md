## Overview
Floating catchment area analysis measuring primary care physician accessibility at block group level. Computes 2SFCA, E2SFCA, and 3SFCA variants with physician counts from CMS Doctors and Clinicians data. Covers 2018-2025 with automated CMS download and Census geocoding. This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Primcare Access Scores** data pipeline.

## Provenance
Provider locations from CMS Doctors and Clinicians dataset (2022), filtered to Family Practice, Family Medicine, and General Practice specialties in VA, DC, and MD. Addresses geocoded to latitude/longitude. Provider capacity estimated as 1.0 per unique NPI. Counts reflect the number of providers within the floating catchment area of each block group, aggregated to higher geographies by population-weighted mean.

Spatial access scores computed using the two-step floating catchment area (2SFCA) method (Luo, 2004). Provider locations from CMS Doctors and Clinicians (2022), filtered to Family Practice/Family Medicine/General Practice in VA/DC/MD. Demand from ACS 2020 block group population. Travel times from OSRM block-group-to-block-group matrices. Catchment threshold: 30 minutes driving.

Spatial access scores computed using the enhanced two-step floating catchment area (E2SFCA) method (Luo & Qi, 2009). Provider locations from CMS Doctors and Clinicians (2022), filtered to Family Practice/Family Medicine/General Practice in VA/DC/MD. Demand from ACS 2020 block group population. Travel times from OSRM block-group-to-block-group matrices. Catchment threshold: 30 minutes driving with three distance-decay zones.

Spatial access scores computed using the three-step floating catchment area (3SFCA) method (Wan et al., 2012). Provider locations from CMS Doctors and Clinicians (2022), filtered to Family Practice/Family Medicine/General Practice in VA/DC/MD. Demand from ACS 2020 block group population. Travel times from OSRM block-group-to-block-group matrices. Catchment threshold: 30 minutes driving with distance-decay and provider-competition weights.

Drive times computed using OSRM block-group-to-block-group travel time matrices. For each block group, the ten closest primary care physician locations (CMS Doctors and Clinicians, 2022) are identified and the mean travel time is reported. Aggregated to higher geographies by population-weighted mean.

Drive times computed using OSRM block-group-to-block-group travel time matrices. For each block group, the ten closest primary care physician locations (CMS Doctors and Clinicians, 2022) are identified and the median travel time is reported. Aggregated to higher geographies by population-weighted mean.

## Coverage
- **Coverage areas:** CMS

## Methodology
Count of primary care physicians accessible within each geography's floating catchment area. Primary care physicians include family practice, family medicine, and general practice specialties enrolled in Medicare. Areas with low provider counts may face longer wait times and reduced access to preventive care, contributing to worse health outcomes over time.

Primary care accessibility measured using the two-step floating catchment area (2SFCA) method, which computes physician-to-population ratios weighted by travel time within catchment areas. Higher values indicate greater spatial access to primary care. Areas with low scores may face physician shortages, leading to delayed preventive care and higher emergency department utilization.

Primary care accessibility measured using the enhanced two-step floating catchment area (E2SFCA) method, which improves on 2SFCA by applying distance-decay weights within catchment zones. This produces a more realistic accessibility measure since patients are more likely to visit closer providers. Low scores indicate areas where residents face significant barriers to reaching primary care.

Primary care accessibility measured using the three-step floating catchment area (3SFCA) method, which extends E2SFCA by adding a selection-weight step that accounts for competition among providers. This method better captures how patients choose among multiple nearby providers. Low scores indicate areas with both fewer providers and higher competition for available appointments.

Mean drive time in minutes to the ten closest primary care physician locations. This measure captures the average effort required to reach nearby primary care options. Areas with high mean drive times have fewer geographically proximate providers, which can reduce the likelihood of regular preventive care visits.

Median drive time in minutes to the ten closest primary care physician locations. The median is less sensitive to outlier distances than the mean, providing a robust measure of typical travel burden. High median drive times indicate areas where even the most accessible providers require substantial travel, a barrier to routine primary care utilization.

## Measures (6)
- **primcare_cnt**: Primary care availability by count (count)
  Number of Medicare-enrolled primary care physicians accessible within a geography's catchment area.
- **primcare_2sfca**: Primary care geographic availability (2-step floating catchment areas) (index)
  Spatial access index for primary care physicians based on the 2SFCA method using travel-time-weighted supply-to-demand ratios.
- **primcare_e2sfca**: Primary care geographic availability (enhanced 2-step floating catchment areas) (index)
  Spatial access index for primary care physicians based on the E2SFCA method with distance-decay weighting within catchment zones.
- **primcare_3sfca**: Primary care geographic availability (3-step floating catchment areas) (index)
  Spatial access index for primary care physicians based on the 3SFCA method with provider competition weighting.
- **primcare_near_10_mean**: Primary care availability by mean drive time to the ten closest facilities in minutes (drive time, unit: minutes)
  Average drive time in minutes from a block group centroid to the ten nearest primary care physician locations.
- **primcare_near_10_median**: Primary care availability by median drive time to the ten closest facilities in minutes (drive time, unit: minutes)
  Median drive time in minutes from a block group centroid to the ten nearest primary care physician locations.

## Data Sources
- [CMS Doctors and Clinicians (accessed 2024)](https://data.cms.gov/provider-data/topics/doctors-clinicians)

## File Format
Data files are provided as CSVs (`.csv`) with the following columns: `geoid`, `region_type`, `region_name`, `year`, `measure`, `value`, `moe` (margin of error, where available). Larger files are provided as xz-compressed CSVs (`.csv.xz`).
