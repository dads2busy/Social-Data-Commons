# Usage Notes

## File access and software

The primary dataset is distributed as an xz-compressed CSV file (.csv.xz). Most statistical software can read this format directly: in Python, pandas.read_csv() decompresses xz files automatically; in R, read.csv() handles xz decompression natively since R 4.0. Users of spreadsheet software should first decompress the file using a utility such as 7-Zip (Windows), The Unarchiver (macOS), or the xz command-line tool (Linux/macOS). The decompressed CSV is approximately 5 MB. The GeoJSON point files can be opened in any GIS software (QGIS, ArcGIS) or read programmatically using libraries such as GeoPandas (Python) or sf (R).

## Interpreting the accessibility ratios

The three 3SFCA accessibility ratios express the number of licensed child care seats available per 1,000 children in the relevant age group, weighted by travel time and adjusted for competition among nearby consumers. Higher values indicate greater accessibility. A ratio of 100 means that, within the distance-weighted catchment area, there is approximately one licensed seat for every 10 children. A ratio of zero indicates that no licensed providers are reachable within a practical driving distance for the given age group.

There is no established threshold in the literature for "adequate" child care accessibility as measured by a floating catchment area ratio. However, the "child care desert" definition of Malik and Hamm^1^, which identifies areas with more than three children under five per licensed slot (equivalent to fewer than 333 seats per 1,000 children), provides a rough reference point. In this dataset, the median block-group-level primary ratio (daycare_ratio) is approximately 137 seats per 1,000 children under 15, suggesting that most Virginia block groups fall below the 333-per-1,000 threshold when the denominator includes the full under-15 population. Direct comparison with the Malik and Hamm threshold requires caution, as their definition uses a narrower age group (under 5) and a simple containment ratio rather than a distance-weighted catchment.

## Scope limitations

The dataset covers only facilities listed in the VDSS licensed child day care search portal. It excludes unlicensed arrangements, informal care by relatives or neighbors, license-exempt religious programs, and facilities licensed by the Virginia Department of Education (including public school pre-kindergarten programs). Users should interpret the accessibility measures as reflecting the licensed, regulated child care market rather than the full spectrum of care available to families.

The geographic scope is limited to Virginia. Block groups in bordering states were included in the travel time and 3SFCA calculations to avoid boundary effects, but the final dataset contains measures only for Virginia block groups, tracts, counties, and health districts.

## Temporal comparability

The two time points (2021 and 2025) use different ACS population vintages as denominators: the 2019 ACS 5-year estimates (2015-2019 period) for 2021, and the 2024 ACS 5-year estimates (2020-2024 period) for 2025. Changes in the accessibility ratios between years therefore reflect both changes in provider supply (the numerator) and changes in child population estimates (the denominator). Users who wish to isolate the supply-side effect should compare the daycare_capacity measure, which does not depend on population estimates.

The VDSS portal may have changed its data entry practices between the two scrape dates. In particular, the 25% decline in the over-4 ratio (daycare_ratio_over_4) between 2021 and 2025 may partly reflect changes in how facilities report their accepted age ranges, rather than actual closures of school-age programs. The primary ratio (daycare_ratio) and the under-10 ratio (daycare_ratio_under_10) are less sensitive to this issue because their age filters are broader.

## Appropriate and inappropriate uses

The dataset is suitable for: identifying neighborhoods with low child care accessibility relative to the child population; comparing accessibility across geographic levels (block group, tract, county, health district); analyzing temporal changes in child care supply between 2021 and 2025; and serving as a spatially resolved covariate in studies of maternal employment, child development, or economic mobility.

The dataset is not suitable for: determining whether a specific family can find a child care placement (individual-level accessibility depends on factors such as cost, quality, and scheduling that are not captured); evaluating the quality of child care providers (the dataset contains only capacity and age range, not quality ratings or inspection outcomes); or making claims about unlicensed or informal care markets.

## References

1. Malik, R. & Hamm, K. Mapping America's child care deserts (Center for American Progress, 2017).
