# Residential Energy Scenario (VA, 2030)

Integrates four source files from a single 2030 VA residential-energy simulation into a long-format CSV with five measures at both county and tract resolution.

## Status

`prepare.py` is intentionally not present yet. Output lives at `data/distribution/` only.

## Source files

Copy these four files into `data/original/` (gitignored). The pipeline reads from these exact local names:

| Local filename (in `data/original/`) | Source filename | Rows |
|---|---|---|
| `va_household.csv` | `va_household_2_4_0.csv` | 3,094,255 |
| `va_adoption.csv` | `va_solar_2030_324k_0.25_ev.csv` | 3,094,255 |
| `va_pv_profiles.csv` | `51_solar_2030_01_01.csv` | 75,523 (75,522 unique hids) |
| `va_resstock.csv` | `VA001-NSD-RUN1.csv` | 13,475 |

All four share `hid` as the join key. All are VA-only.

## Schema

Output uses the **energy long-format schema** with both resolutions in one file:

| Column      | Type  | Notes                                                                                 |
|-------------|-------|---------------------------------------------------------------------------------------|
| geoid       | str   | 5-digit (county) or 11-digit (tract) FIPS, constructed from source admin codes        |
| datetime    | str   | `"2030-01-01"` for static measures, `"2030-01-01THH:00:00"` for hourly                 |
| measure     | str   | one of 5 (see measure_info.json)                                                       |
| value       | float | numeric, or NaN where the measure cannot be computed (see caveats)                     |
| moe         | float | NaN (simulation has no measurement uncertainty)                                        |
| region_type | str   | `"county"` or `"tract"` — discriminates resolution within the same file                |
| data_method | str   | `"simulated"`                                                                          |
| scenario    | str   | `"va_2030_solar_324k_0_25ev"`                                                          |

## Five measures

| Measure | Resolution | Time | Source |
|---|---|---|---|
| `synthetic_household_count_geo20` | county + tract | static | household |
| `pv_adoption_rate_geo20` | county + tract | static | household + adoption |
| `ev_adoption_rate_geo20` | county + tract | static | household + adoption |
| `battery_adoption_rate_geo20` | county + tract | static | household + adoption |
| `pv_generation_kwh_geo20` | county + tract | 24 hourly | household + adoption + pv_profiles |

Each measure also appears as `{measure}_geo10` on the original 2010 tracts (see below).

## 2010 → 2020 tracts

The source simulation keys tracts by **2010** GEOIDs (all 1,872 are 2010 tracts; 268 of them,
holding 699,090 of 3,094,255 synthetic households, do not exist in 2020). `ingest.py` therefore
follows the spec §7.1 naming. Tract rows are published twice: as `{measure}_geo10` (the original
values on 2010 tracts) and as `{measure}_geo20`, redistributed onto 2,175 2020 tracts with
`sdc-census10to20`. County rows are unchanged and named `{measure}_geo20`. The year-based
`write_data(census_standardize=True)` path does not apply, because the scenario year is 2030, so
`transforms.standardize_tracts_to_2020` calls `standardize_all` per `datetime` slice using the
`geo_standardize` specs in `measure_info.json`:

- **Counts** (`synthetic_household_count`, `pv_generation_kwh` hour by hour): count-conserving
  areal interpolation.
- **Adoption rates**: household-weighted, i.e. rate × households and households converted
  separately and divided.
- **Missing values**: a 2020 tract overlapping a 2010 tract with no PV profile (NaN
  `pv_generation_kwh`; 156 2010 tracts) is left missing, which affects 237 2020 tracts.
  `sdc-census10to20` warns that it does this, but its `convert_2010_to_2020_bounds` actually sums
  the remaining overlaps (NaN counted as 0), so the pipeline enforces it after conversion.

Counties equal the sum of their `_geo10` tracts exactly. The `_geo20` tracts conserve the statewide
total (within about 2 households, lost to 23 relationship-file overlaps that cross the state line),
but per county they can differ by up to about 2% for small independent cities. Areal interpolation
moves households with land where 2010 and 2020 tract boundaries cross county lines (595 such
overlaps in Virginia).

## Deferred measures

`residential_load_kwh` is intentionally NOT emitted in this iteration. The
ResStock source file currently in `data/original/` covers only Accomack County
(FIPS 51001, 8 of 1,872 VA tracts). Publishing a "statewide hourly residential
load" measure off that file would be misleading by omission across the 132
unmapped counties. The `compute_residential_load` transform function and its
unit tests remain in `transforms.py` and `test_transforms.py`; the ingest call
and ResStock-indexing verification are commented out with the rationale. When a
statewide ResStock file replaces the Accomack-only one, uncomment both the
verification and the call to re-enable the measure.

End-use breakouts (HVAC, hot water, lights, etc.) and net load (load − generation)
remain future work as previously planned.

## Scenario placeholder

`scenario = "va_2030_solar_324k_0_25ev"` mirrors the source filename. The `0_25ev` suffix's exact meaning isn't yet attributed (it is NOT the total-stock EV adoption rate, which is 14.6%, not 25%). Revise the placeholder when the source authors clarify.

## Run

```bash
# From repo root:
uv run python energy/ResidentialEnergyScenario/code/distribution/ingest.py
```

The ingest reads 3.1M-row joins and may take several minutes.

## Tests

```bash
uv run pytest energy/ResidentialEnergyScenario/code/distribution/test_transforms.py -v
```

## Outputs

- `data/distribution/va_cttr_sim_2030_residential_energy_scenario.csv.xz` — single long-format CSV with 5 measures × {county, tract}: 4 adoption-static measures + `pv_generation_kwh` (24 hourly)

## Known caveats

- **`residential_load_kwh` is deferred.** See the "Deferred measures" section above.
- **PV generation is scaled from a 23% subset.** Only 75,522 of 324,461 PV adopters have generation profiles. The pipeline computes mean profile across profiled adopters per geography, then multiplies by the total adopter count per geography. This assumes the profiled subset is locally representative.
- **Battery adoption is real (2.6%), not zero.** An earlier reconnaissance pass misreported `is_battery` as uniformly zero; direct file verification showed 81,115 adopters.
- **Hour-of-day-only timestamps.** `datetime` values use the energy category's hour-of-day convention (`2030-01-01THH:00:00`); they don't represent specific calendar dates. See `energy/README.md`.
- **No microdata in output.** Per-household details (`hid`, `lat/lon`, `hh_unit_wt`, demographics) are used internally but not retained in outputs.
- **No `prepare.py`.** Energy dashboards aren't yet wired.

## What this pipeline deliberately does NOT do

- **No point file.** Households are private and 3.1M scale isn't dashboard-friendly.
- **No end-use breakouts.** ResStock has hourly HVAC, hot water, lights, etc. — deferred to a future "Full" scope.
- **No net load measure.** Future addition once load and generation are validated.
- **No multi-scenario support.** Single scenario; multi-scenario follows the DataCentersProjected pattern when needed.
- **No `hh_unit_wt` weighting.** County totals use simple ratio scaling, matching the PV scaling approach.

## RDF output (exploratory, lossless)

`prepare.py` builds `data/distribution/va_cttr_sim_2030_residential_energy_scenario.nt.xz`
(about 0.5M triples, sorted N-Triples, xz-compressed) and copies it into
`dashboard_data/va_energy_data/`. The combined CSV mixes two period conventions, so the graph
holds static datasets (adoption rates and household counts; `datetime = 2030-01-01` is read as the
scenario year) and hourly datasets (`pv_generation_kwh` as a typical-day profile, year plus
`sdc:hourOfDay`), split by tract vintage as described below.

The graph holds only the published county and tract aggregates: no point data and no
household microdata. The dashboard CSV is **staged from the graph** (`to_rdf.long_format_from_graph`
stitches the two datasets back together) and verified row for row against the distribution CSV.

The graph holds four datasets: static and hourly, each split into `_geo20` (counties and 2020
tracts) and `_geo10` (2010 tracts, on `sdcid:tract-2010/{geoid}` with `sdc:vintage`).

### Known data issues (not yet resolved)

- **Exact 0% / 100% tract adoption rates** come from the source simulation (e.g. whole Accomack
  tracts at 100% EV adoption) and carry through the conversion; confirm with the source authors.
- **County PV generation is not the sum of its tracts.** Household counts add up exactly
  against their `_geo10` tracts (asserted in tests via
  `rdf/queries/county_tract_household_consistency.rq`), but daily
  `pv_generation_kwh` tract sums range from 0.24× to 1.23× the county value (median
  0.99). This may be intended, if county values come from county-level profiles; confirm
  with the source authors.
