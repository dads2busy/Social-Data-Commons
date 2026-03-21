## Overview
Floating catchment area analysis measuring OB-GYN service accessibility at block group level using female population age 15+ as consumer demand. Computes 2SFCA, E2SFCA, and 3SFCA variants with physician counts from CMS Doctors and Clinicians data (2017-2025). This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Obgyn Access Scores** data pipeline.

## Provenance
Provider counts from CMS Doctors and Clinicians national downloadable file, filtered to Obstetrics/Gynecology specialty (primary or secondary) with MD/DO credentials in VA, DC, and MD. Addresses geocoded via Census Geocoder and snapped to nearest 2020 block group centroid. Counts represent unique NPIs per block group.

Travel times from pre-computed OSRM block-group-to-block-group driving time matrix. For each consumer block group, the 10 nearest provider block groups (by travel time) are identified and the mean travel time is computed. Provider locations from CMS Doctors and Clinicians, filtered to Obstetrics/Gynecology specialty.

Travel times from pre-computed OSRM block-group-to-block-group driving time matrix. For each consumer block group, the 10 nearest provider block groups (by travel time) are identified and the median travel time is computed. Provider locations from CMS Doctors and Clinicians, filtered to Obstetrics/Gynecology specialty.

Spatial access scores computed using the 2SFCA methodology (Luo, 2004) with a 30-minute travel time threshold. Provider capacity = unique NPI count per location from CMS Doctors and Clinicians (Obstetrics/Gynecology). Consumer demand = female population age 15+ from ACS table B01001 (variables B01001_030 through B01001_049). Travel times from pre-computed OSRM BG-to-BG matrix. Scores expressed per 1,000 population.

Spatial access scores computed using the E2SFCA methodology (Luo & Qi, 2009) with stepped weights: 10 min (0.962), 20 min (0.704), 30 min (0.377), 60 min (0.042). Provider capacity = unique NPI count per location from CMS Doctors and Clinicians (Obstetrics/Gynecology). Consumer demand = female population age 15+ from ACS table B01001 (variables B01001_030 through B01001_049). Travel times from pre-computed OSRM BG-to-BG matrix. Scores expressed per 1,000 population.

Spatial access scores computed using the 3SFCA methodology (Wan et al., 2012) with Gaussian distance decay (scale=20). Provider capacity = unique NPI count per location from CMS Doctors and Clinicians (Obstetrics/Gynecology). Consumer demand = female population age 15+ from ACS table B01001 (variables B01001_030 through B01001_049). Travel times from pre-computed OSRM BG-to-BG matrix. Scores normalized by selection weights.

## Coverage
- **Coverage areas:** CMS

## Methodology
Count of OB-GYN physicians per block group, derived from CMS Doctors and Clinicians enrollment data. Areas with few or no OB-GYN providers face potential gaps in reproductive and maternal health care, which can lead to delayed prenatal visits and worse birth outcomes.

Average travel time in minutes to the nearest 10 OB-GYN provider locations from each block group. This measure captures geographic barriers to reproductive health care: longer travel times are associated with fewer prenatal visits, delayed emergency obstetric care, and higher rates of adverse maternal outcomes.

Median travel time in minutes to the nearest 10 OB-GYN provider locations from each block group. The median is less sensitive to outlier locations than the mean, providing a robust indicator of typical geographic access to reproductive health services.

OB-GYN care accessibility measured using the two-step floating catchment area (2SFCA) method with a 30-minute travel threshold. This index quantifies geographic access to reproductive health services by computing provider-to-population ratios within overlapping service areas. Lower scores indicate areas where the female population age 15+ faces greater competition for limited OB-GYN capacity.

OB-GYN care accessibility measured using the enhanced two-step floating catchment area (E2SFCA) method with stepped distance-decay weights. Unlike the basic 2SFCA, E2SFCA applies decreasing weights at 10, 20, 30, and 60-minute travel bands, reflecting the reality that patients are less likely to use providers farther away. This produces a more realistic picture of effective access to reproductive health care.

OB-GYN care accessibility measured using the three-step floating catchment area (3SFCA) method with Gaussian distance decay. The 3SFCA adds a selection-weight step that accounts for the competitive effect among nearby providers, yielding an accessibility score that reflects both spatial proximity and choice behavior in reproductive health service utilization.

## Measures (6)
- **obgyn_cnt**: OB-GYN physician count (count)
  Number of OB-GYN physicians located in each geographic area.
- **obgyn_near_10_mean**: Mean travel time to nearest 10 OB-GYN locations (time, unit: minutes)
  Mean driving time in minutes to the 10 closest OB-GYN provider locations.
- **obgyn_near_10_median**: Median travel time to nearest 10 OB-GYN locations (time, unit: minutes)
  Median driving time in minutes to the 10 closest OB-GYN provider locations.
- **obgyn_2sfca**: OB-GYN care geographic availability (2SFCA) (index)
  Spatial accessibility index for OB-GYN services using the two-step floating catchment area method.
- **obgyn_e2sfca**: OB-GYN care geographic availability (E2SFCA) (index)
  Spatial accessibility index for OB-GYN services using the enhanced two-step floating catchment area method with distance-decay weights.
- **obgyn_3sfca**: OB-GYN care geographic availability (3SFCA) (index)
  Spatial accessibility index for OB-GYN services using the three-step floating catchment area method with Gaussian decay.

## Data Sources
- [CMS Doctors and Clinicians (accessed 2025)](https://data.cms.gov/provider-data/topics/doctors-clinicians)

## File Format
Data files are provided as CSVs (`.csv`) with the following columns: `geoid`, `region_type`, `region_name`, `year`, `measure`, `value`, `moe` (margin of error, where available). Larger files are provided as xz-compressed CSVs (`.csv.xz`).
