# Marketplace Insurance Premiums Dataset

## Overview

County-level ACA marketplace insurance premiums for all US counties served by the Federally-Facilitated Marketplace (FFM) or a State-Based Exchange (SBE). Computed from CMS Public Use Files (PUFs). Plan years 2016--2026.

## Measures

| Measure | Description |
|---------|-------------|
| `marketplace_slcsp` | Monthly premium for the **second-lowest-cost Silver plan** (SLCSP). The SLCSP is the ACA benchmark used to determine premium tax credit eligibility. |
| `marketplace_lcbp` | Monthly premium for the **lowest-cost Bronze plan** (LCBP). Bronze plans have lower premiums but higher cost-sharing than Silver. |

Both measures are computed for a **30-year-old non-tobacco-using individual**, the standard reference profile used by CMS.

## Output Schema

Long-format CSV (compressed `.csv.xz`):

| Column | Type | Description |
|--------|------|-------------|
| `geoid` | string | 5-digit county FIPS code (e.g. `51059`) |
| `year` | int | Plan year (2016--2026) |
| `measure` | string | `marketplace_slcsp` or `marketplace_lcbp` |
| `value` | float | Monthly premium in US dollars |
| `moe` | NA | Not applicable (no margin of error for administrative data) |
| `region_type` | string | Always `county` for ingest output |

## Source Data

**Centers for Medicare & Medicaid Services (CMS) Public Use Files:**
- https://www.cms.gov/marketplace/resources/data/public-use-files

Three PUF files are downloaded per marketplace per year:

1. **Rate PUF** -- individual premium rates by plan, rating area, age, and tobacco status
2. **Plan Attributes PUF** -- plan metadata (metal level, market coverage, dental flag, service area)
3. **Service Area PUF** -- maps each issuer's service area to counties (or "CoverEntireState")

**County-to-Rating-Area crosswalk:**
- https://github.com/hrecht/marketplace-data (`CountyRAs.csv`)

Maps every US county FIPS code to its CMS rating area. Used to join rate data (keyed by rating area) to counties.

## Computation Method

### 1. Download and parse PUFs (`ingest.py`)

For each plan year, ingest downloads FFM and SBE PUF ZIP archives:

- **FFM**: One national file set per year (2016--2026). All states that use the federal marketplace.
- **SBE**: Per-state file sets (2016--2025) for the 19 states + DC that operate their own exchanges. CMS changed the SBE download URL pattern nearly every year; the pipeline handles this via per-year URL templates and explicit overrides in `pipeline.yaml`.

### 2. Filter and normalize

- Rate PUF: filter to age 30, extract `IndividualRate`
- Plan Attributes PUF: filter to Individual market, Silver/Bronze metal level (including Expanded Bronze), non-dental
- Service Area PUF: filter to Individual market, non-dental; parse county FIPS from SBE-format fields
- SBE column names are normalized to FFM-style camelCase

### 3. Map plans to counties

Plans are mapped to counties via the Service Area PUF:
- Plans with `CoverEntireState = Yes` are expanded to all counties in that state
- Plans with specific county assignments use the FIPS code from the `County` field
- The county-to-rating-area crosswalk adds the `RatingAreaId` for each county, enabling the join with rate data

### 4. Compute premiums

For each county:
- **SLCSP**: Sort all unique Silver plan rates; take the 2nd-lowest. If only one Silver plan exists, use that rate.
- **LCBP**: Take the minimum Bronze plan rate.

### 5. Output

Results are melted to long format and written to `data/distribution/` as a compressed CSV.

## Prepare Step (`prepare.py`)

The prepare step reads the national ingest output and produces dashboard-ready files:

1. **VA 2023 interpolation**: Virginia transitioned from the FFM to its own SBE in 2023 but published no PUF that year. The gap is filled by averaging the 2022 (FFM) and 2024 (SBE) values for each county-measure pair.

2. **VA dashboard**: Filters to Virginia counties (FIPS prefix `51`), aggregates to health districts using the county-to-health-district crosswalk (method: mean), then writes combined county + health district files.

3. **NCR dashboard**: Filters to DC (`11`), Maryland (`24`), and Virginia (`51`) counties. Writes county-level files.

## Coverage Notes

| Region | Years | Notes |
|--------|-------|-------|
| FFM states (~33 states) | 2016--2026 | Full coverage |
| VA | 2016--2025 | FFM 2016--2022; interpolated 2023; SBE 2024--2025 |
| MD | 2017, 2019--2025 | SBE. Missing 2016 and 2018 (legacy PUF format lacks service area file) |
| DC | 2021--2025 | SBE. Missing 2016--2020 (legacy PUF format lacks service area file) |
| Other SBE states | varies | Depends on PUF availability and format compatibility |

Some early SBE PUFs (pre-2021 for several states) lack a service area file, which is required to map plans to counties. These state-years are skipped during ingest.

## File Naming

Output files follow the SDC naming convention: `<coverage>_<resolution>_<source>_<years>_<title>`:

- Ingest output: `us_ct_cms_puf_2016_2026_marketplace_premium.csv.xz`
- VA prepare output: `va_hdct_cms_puf_2016_2025_marketplace_premium.csv.xz`
- NCR prepare output: `ncr_ct_cms_puf_2016_2025_marketplace_premium.csv.xz`

## Pipeline Files

| File | Purpose |
|------|---------|
| `pipeline.yaml` | PUF download URLs, SBE state list, household parameters, crosswalk paths |
| `code/distribution/ingest.py` | Downloads PUFs, computes SLCSP/LCBP, writes national long-format output |
| `code/distribution/prepare.py` | Interpolates VA 2023, aggregates to health districts, writes dashboard files |
| `data/distribution/measure_info.json` | Measure metadata for dashboard rendering |
