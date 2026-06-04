# census10to20 Coverage Gap — Standardization Candidates

After the 24-dataset census10to20 remediation, an audit of **all** monorepo datasets (not just
ACS) found datasets that carry **pre-2020 census-tract/block-group data** (which sits on
**2010-vintage** boundaries) but are **not** standardized to 2020 geographies (no `_geo20`
measures). These are candidates for the same treatment as the 24.

**Deciding rule:** a tract/BG dataset needs census10to20 **only if it has pre-2020 years**
(2010-vintage boundaries needing conversion). Datasets that are entirely 2020-native (no
pre-2020 years) are already on 2020 geographies and need nothing.

Audit basis: read every dataset's distribution data for `region_type` (tract/BG presence),
`year` (pre-2020 presence), and `measure` (`_geo20` presence). Worktree copies and
space-in-path artifacts excluded.

---

## True gaps — pre-2020 tract/BG data, NOT standardized (9)

| # | Dataset | Source | Pre-2020 years | Levels | Likely measure type(s) to declare |
|---|---|---|---|---|---|
| 1 | business_climate/Employment/Worker_diversity | LODES | 2010–2019 | tract, BG | index/entropy → **replicate** (confirm) |
| 2 | food/Food Security/Feeding America/Overall Food Insecurity | Feeding America | 2014–2019 | tract | rate/percent → **replicate** or **ratio** |
| 3 | **food/…/Supplemental Nutrition Assistance Program (SNAP)** | **census_acs** | 2013–2019 | tract, BG | counts → **count** (+ percent → **ratio**) |
| 4 | health/Health Care Services/Hospitals and Emergency Rooms/Service Access Scores | CMS | 2015–2019 | tract, BG | access index → **replicate** |
| 5 | health/Health Care Services/Physicians/Primary Care/Service Access Scores | CMS | 2018–2019 | tract, BG | access index → **replicate** |
| 6 | health/Health Care Services/Physicians/OB-GYN/Service Access Scores | CMS | 2017–2019 | tract, BG | access index → **replicate** |
| 7 | health/Health Care Services/Physicians/Pediatric/Service Access Scores | CMS | 2018–2019 | tract, BG | access index → **replicate** |
| 8 | health/Mental Health/Mental and Physical Healthy Days | CDC PLACES | 2018–2019 | tract | percent/days → **replicate** |
| 9 | housing/Cost/Rent | HUD FMR | 2018–2019 | tract | median rent → **replicate** |

Measure-type column is a first read from each dataset's nature; **confirm per dataset** against
`measure_info.json` during the actual effort (SNAP is the only one likely to have published
counts → area-weighting; the rest look intensive → dominant-parent replicate). None of these
currently have a `geo_standardize` block.

## Verified NOT needed — 2020-native (no pre-2020 data) (9)

financial_well_being/Poverty (ACS, 2021–2024) · health/Social Vulnerability Index (ACS,
2020–2024) · education/Daycare Accessibility (2021–) · food/Food Access/Healthy Food
Availability (2023–) · health/…/Dentists (2022) · health/…/EMS (2021) · health/…/Urgent Care
(2020–) · health/…/Drug and Rehab (2021–) · health/…/Mental Health Service Access (2021–).

These are already on 2020 geographies by construction — no conversion needed.

## Excluded

- **energy/ResidentialEnergyScenario** — exploratory placeholder (no Zenodo/prepare; deviating
  datetime+scenario schema). Out of scope.
- **8 business_climate datasets** (Business_characteristics + Employment by Industry / Minority /
  Total, `mergent_intellect`) — `pipeline.yaml` declares tract/BG but the distribution output is
  **county-only**. A config-vs-output discrepancy, not a standardization gap; flag separately.

---

## Execution outcome (2026-06-04, branch census10to20-coverage-gap)

Standardized via the configurable `vintage_cutoff_year` mechanism: **PLACES** (cutoff 2022),
**Rent** (all years 2010-vintage), and **SNAP** (cutoff 2020; prepare's health-district percent
recompute updated to use the `_geo20` counts).

**Reverted — excluded from the standardize-everything rule (2026-06-04):** the three physician
**Service Access Scores** (OB-GYN, Pediatric, Primary Care) were initially standardized (cutoff
2021) but then **reverted to native**. They have a Data & Policy data paper
(`health/Health Care Services/Physicians/docs/article/`) built around native per-year block-group
geography; standardizing replicated pre-2021 FCA scores onto 2020 boundaries, changing the measure
schema (`_geo10`/`_geo20`) and the methodology the paper describes. Repo + GitHub releases reverted
to v2.0.0/v2.0.0/v4.0.1 (bare measures). The standardized Zenodo versions (10.5281/zenodo.20547473,
.20547481, .20547488) are permanent (Zenodo never deletes) and are annotated "Reverted — do not
use"; the paper-cited versions (.19152569, .19152601, .19152538) had their superseded notices
removed and are canonical again. FCA accessibility scores are a poor fit for dominant-parent
replication — native per-year geography is more defensible for them.

**Deferred to a separate investigation** (pre-existing problems beyond standardization, matching
the Hospitals case):
- **Worker_diversity** — its distribution data emits **116 measures but only 78 are documented**
  in `measure_info.json` (38 unprefixed `age_*`/`earnings_*`/`industry_*` measures have no
  metadata). Standardizing would route the 38 undocumented measures through the name heuristic.
  Fix the `measure_info` completeness first (document or stop emitting the 38), then standardize.
- **Hospitals and Emergency Rooms/Service Access Scores** — erratic per-year tract geography
  (see above), needs its geography handling understood/fixed first.

## Recommended approach (same playbook as the 24)

For each of the 9, per dataset:
1. Read `measure_info.json` + ingest/prepare; confirm the measure type(s) and whether pre-2020
   data is genuinely on 2010-vintage boundaries.
2. Add `geo_standardize` blocks (count / ratio / replicate / density as appropriate) and wire
   `measure_info` into the `write_data(census_standardize=True, …)` call (or the manual
   `replicate_2010_to_2020_bounds` path if the pipeline standardizes outside `standardize_all`).
3. Add to the harness (`tests/test_geo_standardize_metadata.py`) and regenerate via the
   `tools/census10to20_remediation/` driver (region-wide conservation gate; `SDC_NO_PUBLISH=1`).
4. The 2009-vintage exclusion likely does not apply (none of these start in 2009), but verify
   each start year.

This is a smaller, more source-varied effort than the 24; SNAP (ACS) is the most like the
already-remediated base-ACS datasets, and the Service Access Scores are like the HOI indices
(replicate).
