## Data Records

The complete dataset is archived on Zenodo (DOI: TBD) and comprises six compressed CSV files organized by physician specialty and geographic coverage area. All files follow a shared long-format schema and can be read with any tool that supports CSV and LZMA decompression.

### Repository and Access

The dataset is published under a Creative Commons Attribution 4.0 International license. Each specialty is versioned independently: Primary Care v4.0.1, OB-GYN v2.0.0, and Pediatric v2.0.0. Files use LZMA compression (`.csv.xz`) and range from approximately 50 to 120 MB uncompressed. The repository includes a `manifest.json` file listing each output with row counts and checksums. Source code for the full pipeline is available in the associated GitHub repository.

### File Inventory

**Table 2.** Output files.

| File | Specialty | Coverage | Years | Rows |
|------|-----------|----------|-------|------|
| `va_hdcttrbg_cms_2018_2025_access_scores_primcare.csv.xz` | Primary Care | Virginia | 2018--2025 | -- |
| `ncr_cttrbg_cms_2018_2025_access_scores_primcare.csv.xz` | Primary Care | NCR | 2018--2025 | -- |
| `va_hdcttrbg_cms_2017_2025_access_scores_obgyn.csv.xz` | OB-GYN | Virginia | 2017--2025 | -- |
| `ncr_cttrbg_cms_2017_2025_access_scores_obgyn.csv.xz` | OB-GYN | NCR | 2017--2025 | -- |
| `va_hdcttrbg_cms_2018_2025_access_scores_peds.csv.xz` | Pediatric | Virginia | 2018--2025 | -- |
| `ncr_cttrbg_cms_2018_2025_access_scores_peds.csv.xz` | Pediatric | NCR | 2018--2025 | -- |

Combined row counts across coverage areas: Primary Care 613,020; OB-GYN 774,469; Pediatric 703,111. The total across all six files is 2,090,600 records.

### Schema Description

Every file contains seven columns in a shared long-format schema. Each row represents one measure for one geographic unit in one year. The `geoid` column stores the FIPS code as a string, preserving leading zeros: 12 digits for block groups, 11 for tracts, 5 for counties and independent cities, or a text name for Virginia health districts. The `year` column records the calendar year of the underlying CMS Doctors and Clinicians data. The `measure` column identifies which of the six specialty-specific indicators the row contains. The `value` column holds the numeric result. The `moe` column is reserved for margin of error in survey-derived measures and is NA throughout this dataset because all values are either direct counts or model outputs. The `region_type` column identifies the geographic level as one of `block_group`, `tract`, `county`, or `health_district`. The `data_method` column is set to `observed` for provider count measures and `modeled` for all FCA and travel-time measures.

**Table 3.** Column definitions.

| Column | Type | Description |
|--------|------|-------------|
| `geoid` | string | FIPS code (12-, 11-, or 5-digit) or health district name |
| `year` | integer | Calendar year of CMS data |
| `measure` | string | Measure identifier (see Measure Definitions) |
| `value` | float | Numeric value |
| `moe` | float | Margin of error (NA for all records) |
| `region_type` | string | `block_group`, `tract`, `county`, or `health_district` |
| `data_method` | string | `observed` or `modeled` |

### Measure Definitions

Each specialty produces six measures. The table below lists all 18 measures across the three specialties. FCA scores are expressed as physicians per 1,000 population. Population denominators vary by specialty: total population for Primary Care, female population aged 15 and older for OB-GYN, and population aged 0 to 17 for Pediatric.

**Table 4.** Measure definitions.

| Measure | Description | Units | Data Method |
|---------|-------------|-------|-------------|
| `{prefix}_cnt` | Count of unique physician NPIs within the geographic unit | physicians | observed |
| `{prefix}_2sfca` | Two-step floating catchment area score with a 30-minute driving threshold | physicians per 1,000 pop. | modeled |
| `{prefix}_e2sfca` | Enhanced 2SFCA with stepped distance decay weights | physicians per 1,000 pop. | modeled |
| `{prefix}_3sfca` | Three-step FCA with Gaussian decay (scale = 20 min) and competition weighting | physicians per 1,000 pop. | modeled |
| `{prefix}_near_10_mean` | Mean driving time to the 10 nearest physicians | minutes | modeled |
| `{prefix}_near_10_median` | Median driving time to the 10 nearest physicians | minutes | modeled |

In the table above, `{prefix}` is `primcare` for Primary Care, `obgyn` for OB-GYN, and `peds` for Pediatric.

### Scale and Coverage

Virginia files contain records at four geographic levels: approximately 5,963 block groups, 2,198 census tracts, 133 counties and independent cities, and 35 health districts, all defined by 2020 Census FIPS boundaries. NCR files cover a subset of Virginia jurisdictions plus adjacent Maryland counties and the District of Columbia, totaling 14 county-level jurisdictions, with block group, tract, and county levels but no health districts. Primary Care and Pediatric files span eight years (2018 to 2025). OB-GYN files span nine years (2017 to 2025).
