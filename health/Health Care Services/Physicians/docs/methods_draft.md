## Methods

### Input Data Sources

The datasets described in this paper were produced from four primary input sources. Table 1 summarizes each source, its provider, spatial resolution, and temporal coverage.

**Table 1.** Input data sources.

| Source | Provider | Resolution | Temporal Coverage |
|--------|----------|------------|-------------------|
| Doctors and Clinicians National Downloadable File | Centers for Medicare & Medicaid Services (CMS) | Provider address | 2017--2025 (annual) |
| American Community Survey 5-Year Estimates, Table B01001 | U.S. Census Bureau | Census block group | 2016--2023 |
| Pre-computed block-group-to-block-group travel time matrices | OpenStreetMap / OSRM v5.27.1 | Census block group centroid | 2020 road network |
| County-to-Health-District Crosswalk | Virginia Department of Health (VDH) | County | 2020 |

The study area encompasses two overlapping regions: the Commonwealth of Virginia (FIPS 51, all counties and independent cities) and the National Capital Region (NCR). The NCR includes nine Virginia jurisdictions (Fairfax County, Fairfax City, Falls Church, Loudoun County, Arlington County, Alexandria, Manassas, Manassas Park, and Prince William County), four Maryland counties (Frederick, Montgomery, Prince George's, and Charles), and the District of Columbia.

### Data Acquisition

#### CMS Provider Data

Provider records were obtained from the CMS Doctors and Clinicians National Downloadable File, a publicly available registry of clinicians enrolled in Medicare. Annual ZIP archives were downloaded programmatically from the CMS Provider Data website (https://data.cms.gov/provider-data/dataset/mj5m-pzi6) for each year in the study period. Each archive contains a single CSV file listing all enrolled clinicians nationwide.

The pipeline extracted the CSV from each archive, filtered records to providers with practice addresses in Virginia, Maryland, or the District of Columbia, and retained only those holding MD or DO credentials. Column names were standardized across years because CMS changed its schema multiple times during the study period (e.g., `lst_nm` in early files, `Last Name` in intermediate files, and `Provider Last Name` in later files). After standardization, providers were filtered by specialty. Three specialty-specific datasets were constructed:

- **Primary care**: providers listing Family Practice, Family Medicine, or General Practice as a primary or secondary specialty (2018--2025).
- **OB-GYN**: providers listing Obstetrics/Gynecology as a primary or secondary specialty (2017--2025).
- **Pediatric**: providers listing Pediatric Medicine as a primary or secondary specialty (2018--2025).

Each provider was identified by a unique National Provider Identifier (NPI). Per-year filtered CSVs were saved to enable incremental updates without re-downloading the full national file.

#### Population Denominator Data

Block-group-level population denominators were drawn from the American Community Survey (ACS) 5-Year Estimates, Table B01001 (Sex by Age), retrieved through the Census Bureau API. Each specialty used a denominator appropriate to its target population:

- **Primary care**: total population (variable B01001_001).
- **OB-GYN**: female population aged 15 and older, constructed by summing 20 age-sex bins (variables B01001_030 through B01001_049).
- **Pediatric**: population aged 0 to 17, constructed by summing 8 age-sex bins covering males and females under 5, 5 to 9, 10 to 14, and 15 to 17 (variables B01001_003 through B01001_006 and B01001_027 through B01001_030).

Population data were retrieved for all block groups in Virginia (FIPS 51), Maryland (FIPS 24), and the District of Columbia (FIPS 11). Because ACS 5-Year Estimates are released with a two-year lag, each CMS data year *t* was paired with the ACS vintage *t* - 1, capped at 2023 (the latest available vintage at the time of processing). For example, CMS year 2025 used ACS year 2023.

#### Travel Time Matrices

Travel times between block group centroids were drawn from pre-computed matrices generated using the Open Source Routing Machine (OSRM) v5.27.1. OSRM was configured with the OpenStreetMap road network as of 2020, using automobile routing under free-flow conditions (no real-time traffic adjustment). Block group centroids were derived from 2020 TIGER/Line shapefiles published by the Census Bureau. Travel time matrices were stored as Apache Parquet files, one per state FIPS code, covering Virginia and all neighboring states (FIPS codes 10, 11, 21, 24, 37, 47, 51, 54) to ensure border-crossing routes were available. Each file contains origin block group, destination block group, and travel time in minutes. Pairs without a viable road route were absent from the file and treated as unreachable (assigned a cost of 1,000,000 minutes) during matrix construction.

### Geocoding and Spatial Assignment

Provider addresses were geocoded using the U.S. Census Bureau Geocoder API (Public_AR_Current benchmark, Current_Current vintage). Each unique address was submitted as a single-line query. The geocoding results were cached so that addresses appearing in multiple years or across specialty datasets were geocoded only once. Successfully geocoded addresses received latitude and longitude coordinates.

Each geocoded provider address was then assigned to the nearest 2020 census block group centroid using the haversine distance formula. Provider capacity at each block group was defined as the count of unique NPIs at addresses assigned to that block group. This aggregation step collapsed multiple providers at the same physical location (e.g., a multi-physician practice) into a single supply point with capacity equal to the number of distinct clinicians.

### Floating Catchment Area Computation

All three datasets were processed through a shared computational module that implements three variants of the floating catchment area (FCA) method. The FCA family of methods measures spatial accessibility by computing a ratio of supply (provider capacity) to demand (population) within a travel-time-defined catchment area [14]. Each variant differs in how it handles distance decay within the catchment.

For all variants, let *i* index consumer block groups with population *P_i*, and let *j* index provider locations with capacity *S_j*. Let *d_{ij}* denote the travel time in minutes from consumer *i* to provider *j*. All accessibility scores are reported per 1,000 population.

#### Two-Step Floating Catchment Area (2SFCA)

The 2SFCA method, introduced by Luo and Wang [14], uses a binary threshold to define the catchment. A provider is considered accessible if and only if the travel time falls below the threshold *d_0* = 30 minutes.

In the first step, the provider-to-population ratio for each provider *j* is computed as:

$$R_j = \frac{S_j}{\sum_{i \mid d_{ij} < d_0} P_i} \quad (1)$$

where the denominator sums the population of all block groups within the 30-minute threshold.

In the second step, the accessibility score for each consumer block group *i* is:

$$A_i^{\text{2SFCA}} = \sum_{j \mid d_{ij} < d_0} R_j \quad (2)$$

where the summation runs over all providers reachable within 30 minutes.

#### Enhanced Two-Step Floating Catchment Area (E2SFCA)

The E2SFCA method, proposed by Luo and Qi [15], replaces the binary threshold with stepped distance decay weights that decrease with travel time. The weight function *w_{ij}* takes the following values:

| Travel time range | Weight |
|-------------------|--------|
| 0--10 minutes     | 0.962  |
| 10--20 minutes    | 0.704  |
| 20--30 minutes    | 0.377  |
| 30--60 minutes    | 0.042  |

These weights were derived from a Gaussian function evaluated at the midpoint of each zone, following the calibration described in Luo and Qi [15].

The provider-to-population ratio becomes:

$$R_j = \frac{S_j}{\sum_i w_{ij} P_i} \quad (3)$$

and the accessibility score is:

$$A_i^{\text{E2SFCA}} = \sum_j w_{ij} R_j \quad (4)$$

where *w_{ij}* = 0 for travel times exceeding 60 minutes.

#### Three-Step Floating Catchment Area (3SFCA)

The 3SFCA method, introduced by Wan, Zou, and Sternberg [16], adds a selection probability step that accounts for competition among providers for the same demand population. It uses a continuous Gaussian decay kernel:

$$w_{ij} = \exp\left(-\frac{d_{ij}^2}{2\sigma^2}\right) \quad (5)$$

where *sigma* = 20 minutes is the bandwidth parameter controlling the rate of distance decay.

**Step 1 (Selection weights):** The probability that population at block group *i* selects provider *j* is:

$$G_{ij} = \frac{w_{ij}}{\sum_{k} w_{ik}} \quad (6)$$

This normalization ensures that the selection weights for each consumer sum to 1 across all providers, representing a probabilistic allocation of demand.

**Step 2 (Provider-to-population ratio):** Using the selection-weighted demand:

$$R_j = \frac{S_j}{\sum_i G_{ij} P_i} \quad (7)$$

**Step 3 (Accessibility score):**

$$A_i^{\text{3SFCA}} = \sum_j G_{ij} R_j \quad (8)$$

The selection weight normalization (*normalize_weight* = True in the implementation) distinguishes the 3SFCA from the E2SFCA by ensuring that demand is allocated probabilistically across competing providers rather than counted fully within each provider's catchment. This addresses the demand overcount problem identified by Wan et al. [16].

The Gaussian bandwidth of 20 minutes was selected to be consistent with prior physician accessibility studies in the region and reflects the typical willingness-to-travel range for routine medical appointments [19].

#### Supplementary Measures

In addition to the three FCA scores, the pipeline computed three supplementary measures for each block group:

- **Provider count**: the sum of unique NPI capacity assigned to the block group. This measure reflects the physical presence of providers but does not account for population demand or distance.
- **Nearest-10 mean travel time**: the arithmetic mean of travel times from the block group to its 10 nearest provider locations.
- **Nearest-10 median travel time**: the median of travel times from the block group to its 10 nearest provider locations.

These supplementary measures provide interpretable baselines for comparison with the FCA scores.

### Geographic Aggregation

Block-group-level measures were aggregated to three higher geographic levels: census tract (first 11 digits of the 12-digit block group GEOID), county (first 5 digits), and, for Virginia only, health district (via the VDH county-to-health-district crosswalk).

The aggregation method depended on the measure type:

- **Provider counts** were aggregated by summation.
- **Travel time measures** (nearest-10 mean, nearest-10 median) were aggregated by arithmetic mean across constituent block groups.
- **FCA scores** (2SFCA, E2SFCA, 3SFCA) were aggregated by population-weighted mean, where the weight for each block group was its specialty-specific denominator population. This approach ensures that the aggregated score reflects per-capita accessibility rather than being biased by low-population block groups.

### Output Format

Each specialty produced two output files: one covering all Virginia block groups, tracts, and counties, and one covering the NCR subset. Files are compressed long-format CSV archives (.csv.xz) with the schema: `geoid`, `year`, `measure`, `value`, `moe`, `region_type`, `data_method`. Provider counts carry `data_method` = "observed"; all FCA and travel time measures carry `data_method` = "modeled". The `moe` column is reserved for margin-of-error propagation from ACS inputs but is not populated in the current release.

### Software and Computational Environment

The pipeline was implemented in Python 3.12 using pandas for tabular operations, NumPy for array computation, GeoPandas for spatial data handling, and SciPy for sparse matrix operations and the Gaussian kernel. Travel time routing was performed offline by OSRM v5.27.1. Geocoding was performed via the U.S. Census Bureau Geocoder REST API (Public_AR_Current benchmark). The FCA computation was implemented in the `sdc-core` library (catchment module), which provides a unified `catchment_ratio()` function supporting all three FCA variants through parameterization of the weight specification, kernel function, and normalization options.
