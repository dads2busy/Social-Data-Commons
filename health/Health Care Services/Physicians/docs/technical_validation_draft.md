# Technical Validation

This section describes the checks and analyses we performed to assess the quality, consistency, and plausibility of the three physician accessibility datasets: primary care, obstetrics and gynecology (OB-GYN), and pediatric. Each dataset contains block-group-level floating catchment area (FCA) scores derived from CMS Doctors and Clinicians enrollment records, ACS total population estimates, and OSRM-based travel times between block group centroids. The validation analyses address five potential error sources: incompleteness in the source provider data, distributional properties of the computed measures, internal arithmetic consistency, temporal stability, and convergent validity against simpler measures.

## Source data completeness

The datasets draw physician locations from the CMS Doctors and Clinicians public use file, which records providers enrolled in Medicare. Block group counts changed between the 2010 Census geography (used for 2018 through 2020) and the 2020 Census geography (2021 onward): 5,332 block groups in the earlier period and 5,963 in the later period. This transition reflects the Census Bureau's redrawing of block group boundaries and does not indicate data loss.

Provider counts for Virginia block groups across the time series are as follows. For primary care: 898, 813, 851, 1,153, 1,104, 1,127, 3,851, and 3,805 (2018 through 2025). For OB-GYN: 229, 212, 193, 188, 275, 280, 250, 925, and 1,112 (2017 through 2025). For pediatrics: 104, 103, 94, 143, 127, 126, 315, and 385 (2018 through 2025). All three specialties show a pronounced increase in 2024, with primary care provider counts roughly tripling and OB-GYN and pediatric counts more than doubling. This increase does not reflect actual workforce growth; rather, it coincides with CMS expanding the Doctors and Clinicians file to include additional enrollment types beginning in 2024 (CMS, 2024). Users analyzing temporal trends should treat 2024 as a structural break in the source data rather than evidence of a supply increase.

The vast majority of block groups contain zero providers in any given year: 87% to 99% depending on the specialty and year. This pattern is expected. Physicians concentrate at practice addresses in commercial and institutional areas, which fall within a small fraction of residential block groups. The FCA methodology is designed for precisely this spatial configuration, as it redistributes provider capacity across the surrounding catchment area using a travel-time-weighted function.

We did not independently verify the CMS provider counts against an external source such as state licensure boards. The CMS file captures only Medicare-enrolled physicians, which excludes an estimated 15 to 20 percent of the active physician workforce (AAMC, 2022). This undercounting is systematic rather than random, meaning that the FCA scores reflect relative spatial accessibility among the CMS-enrolled portion of the workforce, not the total supply. The bias is most likely to affect specialties with lower Medicare participation rates.

## Distribution of measures

Table 1 reports summary statistics for the six primary output measures across all three specialties at the block group level in 2025 (N = 5,963 block groups for Virginia). The three FCA variant measures (2SFCA, E2SFCA, and 3SFCA) and the mean travel time to the nearest 10 providers (near_10_mean) characterize different aspects of spatial accessibility.

The E2SFCA scores show a gradient across specialties that mirrors provider density. Primary care, with the most providers, has the highest mean E2SFCA score (0.438, SD = 0.212) and no block groups with zero values. OB-GYN (mean = 0.300, SD = 0.218) and pediatrics (mean = 0.216, SD = 0.263) have progressively lower means, with 2.7% and 3.6% of block groups at zero, respectively. The zero-value block groups for OB-GYN and pediatrics are located in remote western Virginia, where no providers of those specialties practice within the 30-minute catchment threshold.

The 2SFCA scores, which apply a binary rather than distance-weighted catchment, show a higher proportion of zero-value block groups: 3.1% for primary care, 15.4% for OB-GYN, and 17.0% for pediatrics. The 3SFCA scores, by contrast, have near-zero percentages of zero values across all specialties, consistent with the Gaussian decay function assigning nonzero (though small) weights even at long travel times.

Mean travel time to the nearest 10 providers (near_10_mean) follows the expected pattern. Primary care has the shortest mean travel time (16.5 minutes, median 11.1 minutes), followed by OB-GYN (23.6 minutes, median 18.9 minutes) and pediatrics (24.5 minutes, median 19.3 minutes). For OB-GYN, 162 block groups (2.7%) and for pediatrics, 213 block groups (3.6%) lack a near_10_mean value because fewer than 10 providers of that specialty exist within the maximum travel time threshold. These missing values correspond to the most isolated block groups in western Virginia.

The maximum E2SFCA value for pediatrics (4.230) is notably higher than for primary care (1.679) or OB-GYN (1.013). This outlier occurs in a block group with a very small total population adjacent to a pediatric practice, producing a high per-capita ratio. While arithmetically correct, such extreme values should be interpreted with caution. Figure 1 shows the distribution of E2SFCA scores across all three specialties.

## Internal consistency

We verified the arithmetic consistency of the aggregation procedure by comparing county-level provider counts against the sum of block-group-level provider counts within each county. For all three specialties across all 133 Virginia counties in 2022, the discrepancy is zero: the county total exactly equals the sum of its constituent block groups. This check confirms that the spatial join assigning providers to block groups and the subsequent county aggregation introduce no record loss, duplication, or misattribution.

This verification does not test the accuracy of the FCA scores themselves, which depend on the travel time matrix and the Gaussian decay parameters. It confirms only that the input provider data are correctly partitioned across geographic units.

## Cross-specialty correlation

If the three datasets measure related aspects of physician accessibility, we would expect moderate positive correlations across specialties. Table 2 reports Spearman rank correlations among the E2SFCA scores at the Virginia block group level in 2022. The strongest correlation is between primary care and OB-GYN (rho = 0.694), followed by primary care and pediatrics (rho = 0.515) and OB-GYN and pediatrics (rho = 0.504). These moderate correlations indicate that areas with better primary care access tend to have better specialist access as well, but with substantial independent variation, consistent with the fact that specialist practices cluster in different locations than primary care offices (Ricketts, 2005).

The near_10_mean travel time measure shows stronger cross-specialty correlations (primary care to OB-GYN: rho = 0.806; primary care to pediatrics: rho = 0.701; OB-GYN to pediatrics: rho = 0.776). Travel time is driven primarily by the road network and block group remoteness, both of which are shared across specialties, so the higher correlations for this measure are expected.

## Temporal consistency

Multi-year datasets should exhibit high autocorrelation across consecutive years if the underlying spatial distribution of providers changes gradually. We assessed temporal consistency by computing Pearson correlations of E2SFCA scores between consecutive years at the Virginia block group level (Figure 2).

For primary care, consecutive-year correlations range from 0.919 to 0.956, with one exception: the 2023 to 2024 transition has r = 0.827. For pediatrics, consecutive correlations range from 0.914 to 0.982. For OB-GYN, the range is 0.615 to 0.961, with two notably lower values: 2017 to 2018 (r = 0.615) and 2023 to 2024 (r = 0.768).

Two patterns warrant explanation. First, the 2023 to 2024 dip appears across all three specialties (primary care r = 0.827, OB-GYN r = 0.768, pediatrics r = 0.939) and coincides with the CMS data expansion described in the Source Data Completeness section. The addition of new enrollment types in 2024 altered the spatial distribution of counted providers, producing a one-time shift in the accessibility surface. Second, the OB-GYN correlation for 2017 to 2018 (r = 0.615) is the lowest in the entire series and may reflect early-vintage data quality issues in the CMS file for that specialty.

First-to-last-year correlations provide a measure of long-term structural stability. Primary care has r = 0.635 (2018 to 2025), OB-GYN r = 0.549 (2017 to 2025), and pediatrics r = 0.827 (2018 to 2025). The substantially lower first-to-last correlations for primary care and OB-GYN, relative to pediatrics, reflect the compounding of year-to-year shifts (including the 2024 break). Pediatric access patterns are more spatially stable, likely because pediatric practices are fewer in number and more spatially concentrated in established medical centers.

The 2024 structural break does not invalidate the time series. The pre-2024 years (2018 through 2023) form an internally consistent series, as do the post-expansion years (2024 through 2025). Pooling across the break, however, conflates a data scope change with actual access change. We recommend that users conducting trend analyses either restrict to the pre-2024 period or include the 2024 break as a fixed effect.

## Convergent validity

To assess whether the E2SFCA scores capture meaningful variation in physician accessibility, we compared them against a simpler measure: the raw count of providers within each county. Unlike the FCA scores, provider counts do not account for population demand, cross-boundary travel, or distance decay; they simply reflect how many physicians have practice addresses in a county.

At the county level in 2022 (n = 133 Virginia counties), Spearman rank correlations between the mean E2SFCA score and provider count are: primary care rho = 0.608, OB-GYN rho = 0.730, and pediatrics rho = 0.651 (Figure 3). The strong rank-order agreement indicates that both measures largely agree on which counties have better or worse access. Pearson linear correlations are weaker: primary care r = 0.286, OB-GYN r = 0.551, pediatrics r = 0.533. The gap between Spearman and Pearson correlations is largest for primary care and reflects a known feature of the FCA methodology: it adjusts for population demand, compressing the distribution relative to raw counts. Counties with large populations (such as Fairfax County) have high provider counts but only moderate FCA scores because those providers serve a correspondingly large population. The weaker linear correlation for primary care, specifically, is consistent with primary care providers being more evenly distributed relative to population than specialists, reducing the variance that the FCA adjustment can explain (Guagliardo, 2004).

The divergence between rank and linear correlation is itself a validation finding. If the FCA scores correlated linearly with raw counts, they would add little information beyond a simple provider census. The FCA's value lies precisely in adjusting for the factors that create divergences: population size, cross-boundary travel, and distance decay.

## Urban-rural disaggregation

We classified Virginia block groups into quartiles by county-level provider count and examined mean E2SFCA scores and travel times across these quartiles (2022). For primary care, mean E2SFCA scores increase across quartiles: Q1 = 0.114, Q2 = 0.104, Q3 = 0.134, Q4 = 0.162. Mean travel time to the nearest 10 primary care providers follows the inverse pattern: Q1 = 18.5 minutes, Q2 = 24.6 minutes, Q3 = 21.3 minutes, Q4 = 13.5 minutes (Figure 4). Block groups in the highest provider-count quartile have E2SFCA scores 42% higher and travel times 27% shorter than block groups in the lowest quartile.

The non-monotonic pattern in Q2 (which has the lowest FCA score and highest travel time) likely reflects suburban block groups at the fringe of metro areas, where population is high but nearby providers are concentrated in adjacent urban cores. The FCA method captures this pattern, assigning lower scores to high-demand areas whose providers are shared with surrounding block groups. This is precisely the scenario for which FCA methods were developed (Luo and Qi, 2009), and its appearance in the data supports the face validity of the computed scores.

## Known limitations

1. **CMS enrollment coverage.** The datasets include only physicians enrolled in Medicare, which excludes an estimated 15 to 20 percent of the physician workforce (AAMC, 2022). Physicians who do not participate in Medicare tend to be younger and more concentrated in urban, affluent areas. This omission likely causes a modest underestimation of accessibility in urban block groups relative to rural ones.

2. **Practice address accuracy.** The CMS file records the address associated with a provider's enrollment record, which may be a billing address, administrative office, or hospital campus rather than the location where patients are seen. This issue is most pronounced for hospital-employed physicians, whose enrollment address may be a central administrative building rather than an outpatient clinic.

3. **Specialty classification.** Provider specialty is based on CMS enrollment designation, not board certification. Some providers may have changed specialties or hold dual designations. The primary care category (Family Practice, Family Medicine, General Practice) is relatively well-defined, but the OB-GYN and pediatric categories may miss subspecialists whose primary enrollment is in a different category.

4. **Static road network.** Travel times are computed using OSRM with a free-flow road network from 2020. The calculations do not account for traffic congestion, road closures, seasonal variation, or time-of-day effects. Actual travel times during peak hours in congested urban corridors may be 50 to 100 percent longer than the free-flow estimates (Weiss et al., 2020).

5. **Centroid approximation.** Both provider locations and population are assigned to block group centroids, introducing positional uncertainty that is proportional to block group size. In rural western Virginia, block groups can span tens of kilometers, and the centroid may be far from any road or inhabited area. This uncertainty propagates into the FCA scores but does not introduce systematic directional bias.

6. **ACS margin of error.** The total population denominators carry sampling uncertainty from the ACS 5-year estimates, which is largest at the block group level. This uncertainty is not propagated into the FCA scores. Block groups with very small populations and large margins of error may have FCA scores that are highly sensitive to the population estimate used.

7. **Fixed Gaussian decay parameter.** The 3SFCA and E2SFCA scores use a single Gaussian scale parameter (18 minutes) applied uniformly across all block groups. Willingness to travel for physician care likely varies with urbanicity, socioeconomic status, and specialty. A spatially varying or specialty-specific decay function may produce different accessibility surfaces, particularly in the transition zones between urban and rural areas (McGrail and Humphreys, 2009).

8. **CMS data expansion in 2024.** The addition of new enrollment types to the CMS Doctors and Clinicians file in 2024 roughly tripled primary care provider counts and more than doubled OB-GYN and pediatric counts. This scope change creates a structural break in the time series. Pre-2024 and post-2024 values are not directly comparable without adjustment.

9. **No provider hours or capacity.** The datasets treat all providers as equal, regardless of whether they practice full-time or part-time. A physician who sees patients one day per week contributes the same to the FCA score as one who practices five days per week. This limitation overstates accessibility in areas served primarily by part-time or locum tenens providers.

## References

1. American Association of Medical Colleges (AAMC). *2022 Physician Specialty Data Report* (AAMC, 2022).
2. Centers for Medicare and Medicaid Services (CMS). Medicare Fee-for-Service Public Provider Enrollment data release notes (CMS, 2024).
3. Guagliardo, M. F. Spatial accessibility of primary care: concepts, methods, and challenges. *Int. J. Health Geogr.* **3**, 3 (2004).
4. Luo, W. & Qi, Y. An enhanced two-step floating catchment area (E2SFCA) method for measuring spatial accessibility to primary care physicians. *Health Place* **15**, 1100--1107 (2009).
5. Luo, W. & Wang, F. Measures of spatial accessibility to health care in a GIS environment: synthesis and a case study in the Chicago region. *Environ. Plann. B* **30**, 865--884 (2003).
6. McGrail, M. R. & Humphreys, J. S. Measuring spatial accessibility to primary care in rural areas: improving the effectiveness of the two-step floating catchment area method. *Appl. Geogr.* **29**, 533--541 (2009).
7. Ricketts, T. C. Workforce issues in rural areas: a focus on policy equity. *Am. J. Public Health* **95**, 42--48 (2005).
8. Wan, N., Zou, B. & Sternberg, T. A three-step floating catchment area method for analyzing spatial access to health services. *Int. J. Geogr. Inf. Sci.* **26**, 1073--1089 (2012).
9. Weiss, D. J. et al. Global maps of travel time to healthcare facilities. *Nat. Med.* **26**, 1835--1838 (2020).

## Figure and Table Legends

**Table 1.** Summary statistics for E2SFCA, 2SFCA, 3SFCA, and near-10-mean measures at the census block group level (Virginia, 2025). N, number of block groups with non-null values; SD, standard deviation; % Zero, percentage of block groups with a value of exactly zero. E2SFCA, 2SFCA, and 3SFCA are dimensionless ratios; near_10_mean is in minutes.

**Table 2.** Spearman rank correlation matrix of E2SFCA scores and near-10-mean travel times across the three physician specialties (Virginia block groups, 2022). All correlations are statistically significant (p < 0.001).

**Figure 1.** Distribution of E2SFCA scores at the block group level for primary care (left), OB-GYN (center), and pediatrics (right), Virginia, 2025. Dashed vertical lines indicate the median; solid vertical lines indicate the mean. The x-axis is truncated at two standard deviations above the mean; values exceeding this threshold are included in the rightmost bin.

**Figure 2.** Temporal consistency of E2SFCA scores: Pearson correlation between consecutive years for each specialty (Virginia block groups). The dashed horizontal line at r = 0.9 indicates a reference threshold for high temporal stability. The 2023-2024 dip reflects the CMS data expansion rather than a change in the underlying accessibility surface.

**Figure 3.** Convergent validity: county-level mean E2SFCA score (y-axis) versus raw provider count (x-axis) for each specialty (Virginia, 2022, n = 133). Spearman (rho) and Pearson (r) correlations are annotated. The divergence between rank and linear correlation reflects the FCA adjustment for population demand.

**Figure 4.** Urban-rural disaggregation: mean E2SFCA score (left) and mean travel time to the nearest 10 providers (right) by county-level provider count quartile for primary care (Virginia block groups, 2022). Error bars show one standard error of the mean.
