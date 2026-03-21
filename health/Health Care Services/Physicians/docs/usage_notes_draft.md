## Usage Notes

### File Access and Software

All dataset files are distributed as LZMA-compressed CSV files (.csv.xz). Users can decompress these with standard command-line tools (e.g., `xz -d` on Linux/macOS) or read them directly in Python using `pandas.read_csv()`, which handles .csv.xz files without manual decompression. R users can read the files with `readr::read_csv()` or `data.table::fread()` after decompression. Each file follows a long-format schema with columns for `geoid`, `year`, `measure`, `value`, `moe`, and `data_method`. Files are organized by geographic coverage area (Virginia or NCR) and geographic resolution (block group, tract, county, or health district).

### Interpreting the Measures

Each specialty produces six measures. The `cnt` measure reports the raw count of providers within a catchment area. The `2sfca`, `e2sfca`, and `3sfca` measures are floating catchment area (FCA) ratios expressed as physicians per 1,000 population, where higher values indicate better spatial access. The three FCA variants differ in how they model distance decay: 2SFCA applies a binary 30-minute threshold, E2SFCA applies stepped distance weights across zones from 0 to 60 minutes, and 3SFCA applies a Gaussian decay function with a scale parameter of 20 minutes. The `near_10_mean` and `near_10_median` measures report the mean and median drive time (in minutes) to the 10 nearest providers, where lower values indicate better access.

Population denominators differ by specialty. Primary care measures use total population, OB-GYN measures use the female population aged 15 and older, and pediatric measures use the population aged 0 to 17. These denominators should be considered when comparing FCA scores across specialties, as the same provider-to-population ratio carries different implications depending on the size and distribution of the relevant demand population.

### Scope Limitations

The provider data are drawn from the CMS Doctors and Clinicians public use file, which includes only physicians enrolled in the Medicare program. Non-Medicare providers, including those in exclusively private or cash-pay practices, are not captured. This exclusion is most consequential for OB-GYN and pediatric specialties, where a larger share of physicians may serve primarily non-Medicare populations. The geographic scope covers Virginia at block group through health district levels and the National Capital Region at block group through county levels. Areas outside these regions are not included, and border effects may reduce accuracy for census tracts near coverage area boundaries, where residents may access providers located outside the study area.

### Temporal Comparability

The dataset spans 2018 to 2025 for primary care and pediatric physicians and 2017 to 2025 for OB-GYN physicians. Each CMS data year *t* is paired with American Community Survey population estimates from year *t*-1, capped at the 2023 ACS vintage for the most recent CMS years. Users should note a structural break in 2024 and 2025: CMS expanded the scope of its public use files in those years, resulting in a sharp increase in provider counts that reflects data coverage changes rather than actual workforce growth. Trend analyses that include 2024 or 2025 should account for this discontinuity, and users should avoid interpreting the increase as evidence of improved provider supply.

### Current Policy Use

These datasets are integrated into two operational public health dashboards: the Virginia Public Health Data dashboard, maintained in partnership with the Virginia Department of Health, and the National Capital Region dashboard. Both platforms present the FCA and distance-based measures alongside other health and demographic indicators for use by public health planners, local governments, and community organizations.

### Appropriate and Inappropriate Uses

The data are well suited for identifying geographic disparities in physician accessibility, comparing access across sub-state regions, and tracking relative changes in provider spatial coverage over time (with attention to the 2024 break). They are also appropriate for use as covariates in regression models examining associations between healthcare access and health outcomes.

The data are not suitable for estimating actual physician utilization, patient volumes, or appointment availability. FCA scores reflect spatial potential for access based on provider locations and population, not realized access. The data should not be used to assess individual physician quality or to compare access across states, as the geographic scope is limited to Virginia and the NCR.
