# Residential Energy Scenario (VA, 2030)

Integrates four source files from a single 2030 VA residential-energy simulation into a long-format CSV with six measures at both county and tract resolution.

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
| measure     | str   | one of 6 (see measure_info.json)                                                       |
| value       | float | numeric, or NaN where the measure cannot be computed (see caveats)                     |
| moe         | float | NaN (simulation has no measurement uncertainty)                                        |
| region_type | str   | `"county"` or `"tract"` — discriminates resolution within the same file                |
| data_method | str   | `"simulated"`                                                                          |
| scenario    | str   | `"va_2030_solar_324k_0_25ev"`                                                          |

## Six measures

| Measure | Resolution | Time | Source |
|---|---|---|---|
| `synthetic_household_count` | county + tract | static | household |
| `pv_adoption_rate` | county + tract | static | household + adoption |
| `ev_adoption_rate` | county + tract | static | household + adoption |
| `battery_adoption_rate` | county + tract | static | household + adoption |
| `residential_load_kwh` | county + tract | 24 hourly | household + resstock |
| `pv_generation_kwh` | county + tract | 24 hourly | household + adoption + pv_profiles |

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

- `data/distribution/va_cttr_sim_2030_residential_energy_scenario.csv.xz` — single long-format CSV with 6 measures × {county, tract}

## Known caveats

- **ResStock is sparse at tract resolution.** Only 13,475 of 3.1M households (~0.4%) are simulated by ResStock; many VA tracts have zero ResStock representation and emit `NaN` for `residential_load_kwh`. County-level load is reasonably populated.
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
