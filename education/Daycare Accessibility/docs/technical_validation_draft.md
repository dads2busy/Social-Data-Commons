# Technical Validation

## Source data completeness

The dataset depends on a complete enumeration of licensed child day care facilities from the Virginia Department of Social Services (VDSS) search portal. We assessed the completeness of the scraped facility records by examining coverage, field completeness, and consistency with an independent source.

In 2021 the scrape returned 5,138 facilities; in 2025 it returned 4,827, a decline of 311 facilities (6.1%). As an independent cross-check, the Administration for Children and Families reported that 4,975 child care programs in Virginia received American Rescue Plan stabilization grants as of December 2022^1^. Because stabilization grants were distributed broadly to active programs regardless of CCDF participation, this figure approximates the count of operational programs in the state during the period between our two scrape years. Our 2021 count of 5,138 and 2025 count of 4,827 bracket this figure, consistent with a gradual contraction of the licensed child care supply.

All scraped records contain non-null values for capacity and age range fields. However, where the VDSS detail page did not report a capacity value, the pipeline assigns a default of 4 seats; where no age range was listed, it assigns a default of 0 to 12 years. In 2021, 618 of 5,138 facilities (12.0%) received the default capacity, and 2,287 (44.5%) received the default age range. In 2025, 481 of 4,827 (10.0%) received the default capacity, and 2,064 (42.8%) received the default age range. The high rate of default age ranges reflects the fact that many VDSS listings omit this field. Users who require precise age-group filtering should be aware that nearly half of providers carry imputed age ranges, which may introduce noise into the age-stratified 3SFCA ratios.

Among facilities with reported (non-default) capacity, the distribution is right-skewed (Fig. 1). The median licensed capacity is 60 seats in 2021 and 56 in 2025, with means of 75 in both years. The maximum observed capacity is 564 seats in both years. These distributions are stable across the two time points, suggesting no systematic change in the types of facilities captured.

## Geocoding accuracy

All facility addresses were geocoded using the U.S. Census Bureau geocoding service. In both 2021 and 2025, every facility record was successfully matched to geographic coordinates (100% match rate). The pipeline includes an automatic retry step that simplifies addresses and resubmits them if the initial match fails; the final 100% rate reflects the combined success of both attempts.

To assess the spatial accuracy of geocoded coordinates, we checked whether all points fall within the bounding box of the Commonwealth of Virginia (latitude 36.5 to 39.5 degrees north, longitude 75.2 to 83.7 degrees west). Zero facilities in either year fall outside this bounding box, indicating no gross geocoding errors that placed facilities in the wrong state.

Geocoding to street addresses followed by assignment to the nearest block group centroid introduces positional uncertainty. The magnitude of this uncertainty depends on the size of block groups. In urban areas of Virginia, block groups are small (often less than 1 km across), and the assignment error is negligible relative to the travel time resolution of the dataset. In rural areas, block groups can span tens of kilometers. A facility assigned to the centroid of a large rural block group may be several kilometers from its true location. This positional error propagates into the travel time calculations, where it is bounded by the difference in travel time between the true facility location and the assigned centroid. For the OSRM-based block-group-to-block-group travel time matrix, this error is absorbed into the centroid-to-centroid approximation and does not introduce a systematic bias in the accessibility ratios.

## Population denominator verification

Child population denominators at the block group level were drawn from the American Community Survey (ACS) 5-year estimates (Table B01001, Sex by Age). To verify these values, we compared the state-level totals obtained by summing our block-group-level population figures against published Census Bureau estimates. The Census Bureau Population Estimates Program reported approximately 481,000 children under age 5 in Virginia in 2021^2^. The sum of male and female under-5 population across all Virginia block groups in our dataset is consistent with this figure, with differences attributable to the use of ACS 5-year estimates (centered on the 2017-2021 period) versus single-year population estimates.

The dataset uses three age-stratified population denominators: children under 15, children ages 5 to 14, and children under 10. These are constructed by summing the ACS variables for under-5, 5-to-9, and 10-to-14 age groups (male and female). Because these variables are drawn directly from the Census API with no additional transformation, the population values inherit the sampling error characteristics of the ACS. Margins of error are largest at the block group level and decrease at higher aggregation levels. The dataset does not propagate ACS margins of error into the accessibility ratios.

## Accessibility measure validation

### Internal consistency

The dataset contains 5,963 block groups for each year, aggregated to 2,198 census tracts, 133 counties, and 35 health districts. We verified that the aggregation procedure produces internally consistent results. For the capacity measure, the sum of block group values within each county exactly matches the county-level value for all 133 counties in both years (zero discrepancies). For the minimum drive time measure, county-level values equal the arithmetic mean of their constituent block group values to within floating-point precision (maximum discrepancy less than 0.0001 minutes). These checks confirm that the aggregation code operates correctly.

### Distribution of accessibility ratios

The three 3SFCA accessibility ratios are expressed as licensed child care seats per 1,000 children. Summary statistics for all five measures at the block group level are presented in Table 1. At the block group level in 2021, the primary ratio (daycare_ratio, for children under 15 at providers accepting ages 4 to 10) has a median of 136.7 and a mean of 134.8 seats per 1,000 children, with a standard deviation of 70.8. Only 0.2% of block groups have a ratio of exactly zero, indicating that the 3SFCA method, with its Gaussian distance-decay weighting, assigns nonzero accessibility to nearly all populated block groups, even those without a facility within their own boundaries. The spatial distribution of this ratio at the county level is shown in Fig. 3.

The age-stratified ratios show more variation. The over-4 ratio (daycare_ratio_over_4) has 153 zero-value block groups (2.57%) in 2021, increasing to 381 (6.39%) in 2025. This increase reflects a reduction in the number of providers that exclusively serve school-age children. The under-10 ratio (daycare_ratio_under_10) has fewer zeros (3 in 2021, 28 in 2025).

All three ratios exhibit right-skewed distributions with outliers. In 2021, 20 to 37 block groups (0.3 to 0.6%) have values exceeding three standard deviations above the mean. These extreme values occur in block groups with very low child populations (small denominators) adjacent to large-capacity facilities. While arithmetically valid, these outliers may not represent meaningful accessibility levels and should be interpreted with caution.

### Convergent validity

To assess whether the 3SFCA ratios measure what they claim to measure, we compared them against a simpler, more transparent alternative: a containment-based provider-to-child ratio computed as total licensed capacity within each county divided by total children under 15 in that county, multiplied by 1,000. Unlike the 3SFCA ratio, which accounts for cross-boundary travel and applies distance-decay weighting, the simple containment ratio treats each county as a closed system and counts only facilities physically located within its borders.

Across 132 Virginia counties in 2021, the Spearman rank correlation between the 3SFCA ratio and the simple containment ratio is 0.74 (p < 0.001), and the Pearson correlation is 0.44 (p < 0.001) (Fig. 4). The strong rank-order agreement indicates that the two measures largely agree on which counties have better or worse child care accessibility. The weaker linear correlation reflects a systematic and expected divergence: the 3SFCA method compresses extreme values that arise in geographically small jurisdictions with regionally serving facilities. For example, Virginia's independent cities (Lexington, Bristol, Salem, Charlottesville, Alexandria) host child care facilities that serve surrounding counties, producing simple containment ratios exceeding 400 seats per 1,000 children, while the 3SFCA correctly redistributes this capacity to the broader catchment area. The simple ratio has a standard deviation of 134, compared to 56 for the 3SFCA ratio, confirming that the distance-decay and competition adjustments in the 3SFCA reduce the influence of administrative boundary artifacts.

### Geographic disaggregation by urbanicity

We classified Virginia's 133 counties into three groups by child population density (children under 15 per square kilometer): rural (bottom quartile, n = 34), suburban (middle two quartiles, n = 66), and urban (top quartile, n = 33). All four non-capacity measures show statistically significant differences across these groups (Kruskal-Wallis p < 0.001 for each), confirming that the dataset captures the expected urban-rural gradient in child care accessibility (Fig. 5).

Rural counties have a mean 3SFCA ratio of 64.5 seats per 1,000 children (SD = 50.2), compared to 113.0 (SD = 50.3) in suburban counties and 152.5 (SD = 34.1) in urban counties. The mean minimum drive time follows the inverse pattern: 16.6 minutes in rural counties, 8.2 in suburban, and 1.7 in urban. The age-stratified ratios show the same gradient, with the over-4 ratio exhibiting the widest relative gap between rural (mean = 8.4) and urban (mean = 50.5) counties. These patterns are consistent with known disparities in child care provision, where rural areas have fewer licensed providers relative to the child population and greater travel distances to the nearest facility.

### Sensitivity to Gaussian decay parameter

The 3SFCA ratios depend on a Gaussian distance-decay function with a scale parameter of 18 minutes. This parameter controls how rapidly the influence of a provider diminishes with travel time: at 18 minutes of travel, the weight drops to approximately 37% of its maximum. The choice of 18 minutes reflects a judgment about how far parents are willing to travel for child care, informed by the original 3SFCA application to health services^3^.

We assessed sensitivity by examining the correlation structure of the ratios across time (Fig. 2). The primary ratio (daycare_ratio) shows a Pearson correlation of 0.876 between 2021 and 2025, indicating that the spatial pattern of accessibility is stable across years despite changes in facility counts. The minimum drive time measure shows the highest stability (r = 0.894), while the over-4 ratio shows the lowest correlation (r = 0.648), consistent with greater volatility in the subset of providers serving only older children. These correlations provide indirect evidence that the ratios capture persistent spatial structure rather than noise, though a direct sensitivity analysis varying the scale parameter would strengthen this assessment and is planned for a future release.

## Temporal consistency

The 6.1% decline in facility count between 2021 and 2025 (from 5,138 to 4,827) is consistent with documented national and state-level trends. Lee and Parolin reported that two-thirds of U.S. child care centers closed in April 2020, with one-third remaining closed a year later^4^. The National Association for the Education of Young Children found in its July 2021 survey that four in five centers reported staffing shortages and one in three respondents were considering leaving the field^5^. The Bureau of Labor Statistics documented that over 40% of child care workers employed in February 2020 were unemployed by April 2020, with the sector's employment remaining 20% below pre-pandemic levels through January 2021^6^. Virginia was not exempt from these trends; the state's receipt of ARP stabilization grants for 4,975 programs^1^ indicates the scale of the sector requiring emergency support.

Against this backdrop, the 6.1% net decline observed between our 2021 and 2025 scrapes is plausible, representing a modest contraction after the acute pandemic-era disruption. The decline in total licensed capacity is smaller (3.7%), consistent with a pattern in which smaller providers were more likely to close while larger facilities persisted.

At the block group level, the mean drive time to the nearest provider increased by 3.9% from 2021 to 2025, consistent with a reduced number of provider locations. The correlation between 2021 and 2025 drive time values across block groups is 0.894, indicating high spatial stability: areas with long drive times in 2021 generally had long drive times in 2025 as well. The primary 3SFCA ratio (daycare_ratio) changed by only 1.2%, with a cross-year correlation of 0.876.

The most notable temporal shift occurs in the over-4 ratio, which declined 25.3% between 2021 and 2025. This ratio depends on the subset of providers whose minimum accepted age exceeds 4. The large decline and relatively low cross-year correlation (0.648) suggest that the supply of providers serving exclusively school-age children contracted more sharply than the supply of providers serving younger children. This pattern is consistent with the closure of after-school programs during and after the pandemic, but may also reflect changes in how age ranges are reported on the VDSS portal. Users analyzing trends in the age-stratified ratios should consider both explanations.

## Known limitations

The dataset has several limitations that users should consider:

1. **Licensed facilities only.** The dataset covers facilities listed in the VDSS licensed child day care search portal. It excludes unlicensed care arrangements, informal care by relatives or neighbors, license-exempt religious programs, and facilities licensed by the Virginia Department of Education (such as public school pre-K programs). The true supply of child care available to families is therefore larger than what this dataset captures.

2. **Default imputation for missing fields.** Approximately 12% of facilities lack a reported capacity value and receive a default of 4 seats. Approximately 44% lack a parseable age range and receive a default of 0 to 12 years. These defaults were chosen to be conservative (small capacity, broad age range), but they introduce noise. The age-stratified ratios are particularly affected, as the default age range causes imputed facilities to be included in all three age-group calculations.

3. **Centroid-based spatial assignment.** Facilities are assigned to block groups based on haversine distance to the nearest block group centroid, and travel times are computed between centroids. This approximation is adequate for the sub-kilometer block groups typical of urban Virginia but introduces greater uncertainty in large rural block groups.

4. **No traffic or time-of-day variation.** Travel times are derived from OSRM using static road network data without traffic modeling. Actual travel times during morning and evening commutes, when parents are most likely to access child care, may be substantially longer in congested urban and suburban areas.

5. **Web scraping fragility.** The VDSS portal data are obtained by scraping HTML pages. Changes to the portal's structure, URL scheme, or data formatting could cause partial or complete failure of the scrape without warning. The 2021 and 2025 scrapes used the same parsing logic, but the portal may have changed its data entry practices between those years.

6. **ACS margin of error not propagated.** The child population denominators carry sampling uncertainty from the ACS, which is largest at the block group level. This uncertainty is not propagated into the accessibility ratios. As a result, ratios for block groups with small child populations (and correspondingly large ACS margins of error) are less reliable.

7. **Single Gaussian scale parameter.** The 3SFCA method uses a fixed Gaussian decay scale of 18 minutes for all locations. Willingness to travel for child care likely varies between urban and rural settings and across socioeconomic groups. A spatially varying distance-decay function may be more appropriate but was not implemented.

## References

1. Administration for Children and Families, Office of Child Care. ARP Child Care Stabilization Fact Sheet: Virginia (U.S. Department of Health and Human Services, 2023).
2. U.S. Census Bureau. Population Estimates Program, Annual Estimates of the Resident Population by Single Year of Age and Sex for Virginia: April 1, 2020 to July 1, 2021 (2022).
3. Wan, N., Zou, B. & Sternberg, T. A three-step floating catchment area method for analyzing spatial access to health services. *Int. J. Geogr. Inf. Sci.* **26**, 1073-1089 (2012).
4. Lee, E. K. & Parolin, Z. The care burden during COVID-19: A national database of child care closures in the United States. *Socius* **7**, 23780231211032028 (2021).
5. National Association for the Education of Young Children. Pandemic surveys (2020-2021).
6. Cooksey, K. & Thomas, E. Childcare employment before, during, and after the COVID-19 pandemic. *Mon. Labor Rev.* (2024).

## Figure and Table Legends

**Table 1.** Summary statistics for all five daycare accessibility measures at the census block group level, by year. N, number of block groups with non-null values; SD, standard deviation; % Zero, percentage of block groups with a value of exactly zero. Capacity is expressed in licensed seats; minimum drive time in minutes; ratios in licensed seats per 1,000 children.

**Figure 1.** Distribution of licensed capacity among Virginia child day care facilities with reported (non-default) capacity values, for 2021 (left, N = 4,520) and 2025 (right, N = 4,346). Facilities assigned the default capacity of 4 seats are excluded. Dashed vertical lines indicate the median; solid vertical lines indicate the mean. The x-axis is truncated at 300 seats; facilities with capacity exceeding 300 are included in the rightmost bin.

**Figure 2.** Block-group-level values in 2021 (x-axis) versus 2025 (y-axis) for four measures: minimum drive time (upper left), primary 3SFCA ratio (upper right), over-4 ratio (lower left), and under-10 ratio (lower right). Each point represents one census block group (N = 5,963). The dashed diagonal line indicates perfect agreement (1:1). Pearson correlation coefficients (r) are shown in each panel.

**Figure 3.** County-level daycare accessibility ratio (licensed child care seats per 1,000 children under 15, at providers accepting ages 4 to 10) for 2021 (left) and 2025 (right). Both panels share the same color scale. County boundaries are shown in gray.

**Figure 4.** Convergent validity: county-level 3SFCA accessibility ratio (y-axis) versus simple containment ratio (x-axis) for 132 Virginia counties in 2021. The simple containment ratio is computed as total licensed capacity within each county divided by total children under 15, multiplied by 1,000. The dashed diagonal line indicates perfect agreement (1:1). The red line shows the ordinary least squares fit. Pearson (r) and Spearman (rho) correlation coefficients are annotated.

**Figure 5.** Distribution of four daycare accessibility measures across Virginia counties classified by urbanicity (child population density quartiles), 2021. Rural: bottom quartile (n = 34); suburban: middle two quartiles (n = 66); urban: top quartile (n = 33). Box plots show the median (horizontal line), interquartile range (box), 1.5x IQR whiskers, and outliers (circles).
