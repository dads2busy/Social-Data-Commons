# Health Care Cost — Pipeline Status Report

**Date:** 2026-03-04
**Status:** ACTIVE (marketplace premiums) / DEFERRED (MEPS integration, health insurance coverage)

## Marketplace Premium Pipeline — ACTIVE

The insurance premium sub-pipeline has been converted from a deferred Selenium scraper to a fully automated CMS PUF-based pipeline conforming to the pipeline conversion spec.

**Previous blockers (all resolved):**
- ~~Insurance premium scraper requires Selenium + ChromeDriver~~ → Replaced with CMS Public Use File downloads
- ~~Scraper depends on a running browser (external service)~~ → PUFs are static ZIP downloads, no browser needed
- ~~KFF website UI may change, making the scraper fragile~~ → PUF schema is stable across years

**Pipeline files:**
- `pipeline.yaml` — CMS PUF URLs (FFM 2017–2026, SBE 2024–2025), household params, crosswalks
- `code/distribution/ingest.py` — downloads Rate, Plan Attributes, and Service Area PUFs; computes SLCSP and LCBP per county; outputs long-format `.csv.xz`
- `code/distribution/prepare.py` — aggregates to VA health districts, writes VA and NCR dashboard files

**Coverage:**
- VA: 2016–2025 (FFM 2016–2022, interpolated 2023, SBE 2024–2025). The 2023 gap (VA transitioned FFM→SBE; no PUF that year) is filled via linear interpolation from 2022 and 2024 values in `prepare.py`.
- MD: 2017, 2019–2025 (SBE PUFs). Missing 2016 and 2018 due to legacy PUF format (no service area file).
- DC: 2021–2025 (SBE PUFs). Missing 2016–2020 due to legacy PUF format (no service area file).

**SBE PUF URL patterns:** CMS changed the SBE PUF download URL pattern nearly every year (2016–2023). The pipeline handles this via per-year URL templates and explicit overrides in `pipeline.yaml`. See `url_templates` and `url_overrides` in the SBE config.

**Remaining format gaps:** Some early SBE PUFs (DC 2016–2020, MD 2016, VT 2016–2021) lack a service area file, which is needed to map plans to counties. These are skipped with a warning. Fixing would require specialized parsing that infers county coverage from other PUF data (e.g., DC has only one county, so service area is trivially known).

## Still Deferred

### MEPS/BLS Data Cleaning (`legacy/prepare_healthcare_data_cleaning.py`)
- Merges marketplace premiums with MEPS-IC employer contributions and MEPS-HC out-of-pocket expenses
- Applies BLS medical inflation adjustment
- Not yet converted to spec-conforming pipeline
- Could be a second ingest step or a separate topic

### Health Insurance Coverage (`Health Insurance/code/health_insurance_coverage.R`)
- PUMS microdata analysis via tidycensus
- Fairfax-specific (not generalized, Section 0.2)
- Requires IPUMS account for data access
- Separate topic from marketplace premiums
