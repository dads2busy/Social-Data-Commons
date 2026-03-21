# Methods

## Data sources

The dataset was produced from three primary input data sources and one geographic crosswalk (Table 1).

**Table 1.** Input data sources.

| Source | Provider | Description | Scope | Temporal coverage | Resolution | Access date | Reference |
|---|---|---|---|---|---|---|---|
| Child Day Care Facility Search | Virginia Department of Social Services (VDSS) | Licensed child day care facility records including name, address, licensed capacity, and accepted age range | Virginia | 2021, 2025 | Facility (point) | Jan 2021, Jan 2025 | ^1^ |
| American Community Survey, Table B01001 | U.S. Census Bureau | Sex by Age population estimates | VA, MD, DC, DE, KY, NC, TN, WV | 2019 (5-yr), 2024 (5-yr) | Census block group | Feb 2025 | ^2^ |
| Pre-computed travel time matrices | Open Source Routing Machine (OSRM) | Driving time between census block group centroids | VA, MD, DC, DE, KY, NC, TN, WV | 2020 road network | Block group pair | 2021 | ^3^ |
| County-to-health-district crosswalk | Virginia Department of Health | Mapping of Virginia counties and independent cities to health districts | Virginia | 2020 | County | 2021 | ^4^ |

## Facility data collection

Licensed child day care facility records were obtained by scraping the VDSS Child Day Care Search portal^1^. The scraping procedure consisted of four steps: (1) a POST request to the search endpoint with empty search parameters to retrieve all licensed facilities; (2) parallel GET requests to individual facility detail pages to extract capacity, accepted age range, license type, and administrator information; (3) geocoding of each facility address; and (4) parsing of age range text into numeric bounds.

The search results page returns an HTML table containing facility identifiers, names, and addresses. We parsed this table using regular expressions to extract facility IDs and mailing addresses. For each facility, we fetched the detail page and extracted the licensed capacity (an integer) and the accepted age range (a text string such as "2 months - 6 years 11 months"). Age range strings were parsed by extracting year values from each side of a hyphen delimiter; month-only values were converted to fractional years and rounded down.

Where the VDSS detail page did not report a capacity value, the pipeline assigned a default of 4 licensed seats. Where no age range was listed or the text could not be parsed, the pipeline assigned a default range of 0 to 12 years. These conservative defaults ensure that facilities with incomplete records contribute minimally to capacity totals (default = 4 is near the lower end of the observed distribution) while remaining eligible for all age-group calculations (default range = 0 to 12 spans all three age strata).

Detail pages were cached locally to support resumable scraping. The scraping procedure used up to 8 parallel HTTP connections with a 30-second timeout per request. The scrape was run once in January 2021, yielding 5,138 facility records, and once in January 2025, yielding 4,827 records.

## Geocoding

Facility addresses were geocoded using the U.S. Census Bureau geocoding service (Public_AR_Current benchmark)^5^. Each address was submitted as a single-line query. If the initial geocoding attempt returned no match, the address was simplified by retaining only the street address, city, and state components, and resubmitted. The final coordinates (latitude and longitude in WGS 84) were stored alongside each facility record.

Each geocoded facility was then assigned to the nearest census block group centroid. Block group centroids for the 2020 Census geography were pre-computed from the TIGER/Line shapefiles. The assignment was based on great-circle (haversine) distance between the geocoded facility coordinates and all block group centroids, selecting the centroid with the minimum distance. This approach ensures that every facility maps to exactly one block group, even when the geocoded address falls near a block group boundary.

## Population data

Child population counts at the block group level were obtained from the American Community Survey (ACS) 5-year estimates, Table B01001 (Sex by Age)^2^. Six variables were extracted: males and females in the under-5, 5-to-9, and 10-to-14 age groups (variables B01001_003, B01001_027, B01001_004, B01001_028, B01001_005, and B01001_029, respectively). Three age-stratified population denominators were constructed by summation:

- Children under 15: sum of all six variables.
- Children ages 5 to 14: sum of the 5-to-9 and 10-to-14 variables (male and female).
- Children under 10: sum of the under-5 and 5-to-9 variables (male and female).

For the 2021 facility data, population estimates from the 2019 ACS 5-year period (2015-2019) were used. For the 2025 facility data, population estimates from the 2024 ACS 5-year period (2020-2024) were used. Population data were fetched for Virginia and all bordering states (Maryland, the District of Columbia, Delaware, Kentucky, North Carolina, Tennessee, and West Virginia) to support the cross-border travel time calculations described below.

## Travel time computation

Driving times between census block group centroids were derived from the Open Source Routing Machine (OSRM)^3^, an open-source routing engine that computes shortest-path travel times on the OpenStreetMap road network. Pre-computed block-group-to-block-group travel time matrices were stored as Apache Parquet files, one per state FIPS code (Virginia, Maryland, Delaware, Kentucky, North Carolina, Tennessee, West Virginia, and the District of Columbia). Each record contains an origin block group, a destination block group, and the estimated driving time in minutes.

The matrices were computed from the 2020 road network and represent free-flow driving conditions without traffic modeling. Travel times between block groups within the same state and between bordering states were included to account for cross-border access to child care providers. After loading and deduplicating, the combined travel time matrix contains approximately 45 million origin-destination pairs. For block group pairs where a facility is located in the same block group as the consumer, a travel time of zero minutes was assigned.

## Accessibility measure computation

Five measures were computed for each census block group in each year.

### Capacity and minimum drive time

Total licensed child care capacity for each block group was computed as the sum of licensed seat counts across all facilities assigned to that block group. The minimum drive time for each block group was defined as the shortest OSRM-based travel time from that block group's centroid to any block group containing at least one licensed facility. For block groups that contain at least one facility, the minimum drive time is zero.

### Three-step floating catchment area ratios

Three age-stratified accessibility ratios were computed using the three-step floating catchment area (3SFCA) method^6^. The 3SFCA extends the two-step floating catchment area approach^7,8^ by adding a selection-weight normalization step that accounts for competition among consumers for nearby providers. The method proceeds in three steps.

**Step 1: Selection weights.** For each consumer block group *i*, a selection weight is computed for each provider *j* using a Gaussian distance-decay kernel:

w_ij = exp(-d_ij^2 / (2s^2))        (1)

where d_ij is the driving time in minutes from block group *i* to provider *j*, and s is the Gaussian scale parameter. The selection weight is then normalized using a quadratic scheme:

W_ij = w_ij * (w_ij / R_i)        (2)

where R_i = sum_j(w_ij) is the sum of raw weights across all providers accessible to consumer *i*. This quadratic normalization, following the 3SFCA formulation of Wan, Zou, and Sternberg^6^, ensures that consumers who can reach many providers distribute their demand more heavily toward nearer providers, while consumers with few options concentrate demand on those few providers.

**Step 2: Provider-to-demand ratios.** For each provider *j*, a weighted demand D_j is computed as:

D_j = sum_i(W_ij * P_i)        (3)

where P_i is the child population of consumer block group *i* in the relevant age group. The provider-to-demand ratio is then:

R_j = S_j / D_j        (4)

where S_j is the licensed capacity (number of seats) of provider *j*.

**Step 3: Accessibility scores.** The accessibility score for consumer block group *i* is the sum of provider-to-demand ratios, weighted by the selection weights:

A_i = sum_j(W_ij * R_j)        (5)

The final score A_i is multiplied by 1,000 to express the ratio as licensed seats per 1,000 children.

**Parameter values.** The Gaussian scale parameter was set to s = 18 / sqrt(2) ≈ 12.73 minutes in the kernel function, which produces weights equivalent to a scale of 18 minutes in the alternative parameterization exp(-(d/18)^2) used in earlier implementations. At a travel time of 18 minutes, the weight drops to exp(-1) ≈ 0.37, meaning a provider 18 minutes away contributes approximately 37% of the weight of a provider at the same location. This scale was chosen to reflect a reasonable maximum willingness to travel for child care, informed by the original 3SFCA application to primary care access^6^.

**Age-group filtering.** Before computing each ratio, the set of eligible providers was filtered by their reported or imputed accepted age range:

- daycare_ratio (children under 15): providers whose minimum accepted age is below 5 and whose maximum accepted age exceeds 9, i.e., those accepting at least ages 4 to 10.
- daycare_ratio_over_4 (children 5 to 14): providers whose minimum accepted age exceeds 4.
- daycare_ratio_under_10 (children under 10): providers whose maximum accepted age is below 10.

The corresponding child population denominator was used for each ratio (under-15, 5-to-14, or under-10, respectively).

## Geographic aggregation

Block-group-level measures were aggregated to three higher geographic levels: census tract (first 11 digits of the block group FIPS code), county (first 5 digits), and Virginia health district (via a county-to-health-district crosswalk from the Virginia Department of Health^4^). The aggregation method varied by measure type:

- **Capacity:** summed across constituent block groups.
- **Minimum drive time:** arithmetic mean across constituent block groups.
- **3SFCA ratios:** population-weighted mean, where the weight for each block group is the relevant age-group population (under-15, 5-to-14, or under-10). This ensures that the aggregated ratio reflects the average accessibility experienced by children in the area, rather than the unweighted average across block groups of varying population size.

## Software and computational environment

All data processing was performed in Python 3.12.9 using the following libraries: pandas 3.0.1, NumPy 2.4.2, GeoPandas 1.1.2, httpx 0.28.1, and PyYAML 6.0.3. The 3SFCA computation was performed using the catchment module of the sdc-core library (version 0.1.0), developed by the Social Data Commons at the University of Virginia^9^. Geocoding used the U.S. Census Bureau geocoding API^5^. Travel time matrices were generated using OSRM version 5.27.1^3^.

## References

1. Virginia Department of Social Services. Child Day Care Search. https://www.dss.virginia.gov/facility/search/cc2.cgi (accessed January 2021 and January 2025).
2. U.S. Census Bureau. American Community Survey 5-Year Estimates, Table B01001 (Sex by Age). https://data.census.gov/table/ACSDT5Y2024.B01001 (accessed February 2025).
3. Luxen, D. & Vetter, C. Real-time routing with OpenStreetMap data. in *Proc. 19th ACM SIGSPATIAL Int. Conf. on Advances in Geographic Information Systems* 513-516 (ACM, 2011).
4. Virginia Department of Health. Virginia health districts, regions, and localities crosswalk. https://www.vdh.virginia.gov/content/uploads/sites/182/2020/08/VA-regions_districts_localities.pdf (2020).
5. U.S. Census Bureau. Geocoding Services API. https://geocoding.geo.census.gov (accessed January 2021 and January 2025).
6. Wan, N., Zou, B. & Sternberg, T. A three-step floating catchment area method for analyzing spatial access to health services. *Int. J. Geogr. Inf. Sci.* **26**, 1073-1089 (2012).
7. Luo, W. & Wang, F. Measures of spatial accessibility to health care in a GIS environment: Synthesis and a case study in the Chicago region. *Environ. Plan. B* **30**, 865-884 (2003).
8. Luo, W. & Qi, Y. An enhanced two-step floating catchment area (E2SFCA) method for measuring spatial accessibility to primary care physicians. *Health Place* **15**, 1100-1107 (2009).
9. Social Data Commons, Biocomplexity Institute and Initiative. sdc-core: Social Data Commons core utilities, version 0.1.0. University of Virginia (2025).
