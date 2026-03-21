# Data Records

The dataset is deposited on Zenodo (deposit ID 18917730)^1^ and is freely available under an open license. The deposit contains the files described in Table 2.

**Table 2.** Output files included in the dataset deposit.

| Filename | Format | Size | Description |
|---|---|---|---|
| va_hdcttrbg_vdss_2021_2025_daycare_access.csv.xz | xz-compressed CSV | 570 KB | Primary dataset: all five measures at all four geographic levels for 2021 and 2025 |
| points_2021.geojson | GeoJSON | 2.1 MB | Licensed child day care facility locations for 2021, with capacity and age range attributes |
| points_2025.geojson | GeoJSON | 1.1 MB | Licensed child day care facility locations for 2025, with capacity and age range attributes |
| measure_info.json | JSON | 13 KB | Machine-readable metadata for each measure, including long descriptions, units, provenance, and source citations |
| manifest.json | JSON | 1 KB | Version, generation timestamp, and SHA-256 checksums for all output files |

The primary dataset (va_hdcttrbg_vdss_2021_2025_daycare_access.csv.xz) is provided in long format with 83,290 rows. Each row represents one measure for one geographic unit in one year. The file contains the following columns:

**Table 3.** Column definitions for the primary dataset.

| Column | Data type | Description |
|---|---|---|
| geoid | string | FIPS code identifying the geographic unit (12 digits for block groups, 11 for tracts, 5 for counties, or a health district identifier) |
| year | integer | Year of the facility data (2021 or 2025) |
| measure | string | Name of the accessibility measure (see Table 4) |
| value | float | Numeric value of the measure |
| moe | float | Margin of error (NA for all records in this dataset; reserved for measures derived from survey estimates) |
| region_type | string | Geographic level: block_group, tract, county, or health_district |
| data_method | float | Data production method code (reserved for future use) |

The dataset contains five measures, defined in Table 4.

**Table 4.** Accessibility measures included in the dataset.

| Measure name | Description | Unit | Type |
|---|---|---|---|
| daycare_capacity | Total number of licensed child day care seats within the geographic unit | Seats | Count |
| daycare_min_drivetime | Driving time from the block group centroid to the nearest licensed child day care provider | Minutes | Index |
| daycare_ratio | Licensed child day care seats per 1,000 children under 15, at providers accepting at least ages 4 to 10, computed using the 3SFCA method | Seats per 1,000 children | Ratio |
| daycare_ratio_over_4 | Licensed child day care seats per 1,000 children ages 5 to 14, at providers with minimum accepted age over 4, computed using the 3SFCA method | Seats per 1,000 children | Ratio |
| daycare_ratio_under_10 | Licensed child day care seats per 1,000 children under 10, at providers with maximum accepted age under 10, computed using the 3SFCA method | Seats per 1,000 children | Ratio |

The GeoJSON point files (points_2021.geojson and points_2025.geojson) contain one Feature per licensed facility with Point geometry (WGS 84 coordinates) and the following properties: name (facility name), capacity (licensed seats), age_min (minimum accepted age in years), age_max (maximum accepted age in years), and type (facility type as reported by VDSS).

The dataset covers the Commonwealth of Virginia at four nested geographic levels: 5,963 census block groups, 2,198 census tracts, 133 counties and independent cities, and 35 health districts. Data are provided for two years (2021 and 2025). All geographic identifiers use 2020 Census FIPS codes.

## References

1. Social Data Commons. Daycare Accessibility dataset for Virginia. Zenodo https://doi.org/10.5281/zenodo.18917730 (2025).
