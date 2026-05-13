# Energy

Pipelines covering electric infrastructure, simulated residential energy demand and generation, EV adoption scenarios, and related datasets for Virginia (with eventual nationwide expansion).

## Pipelines

| Topic | Source | Status |
|---|---|---|
| EVChargingStations | Simulated VA EV charging-station inventory (`va_charging_stations_30.csv`) | Ingest landed (no prepare.py yet) |
| DataCenters | Existing US data centers, OSM-derived ([IM3 Atlas](https://data.msdlive.org/records/p147s-4h760)), VA-filtered | Ingest landed (no prepare.py yet) |
| DataCentersProjected | Projected US data center siting, 20 scenarios ([IM3 CERF](https://data.msdlive.org/records/r0cga-34g05)), VA-filtered | Ingest landed (no prepare.py yet) |
| EVChargingDemand | Simulated 2026 VA hourly EV charging events (376k events at location × hour-of-day) | Ingest landed (no prepare.py yet) |
| ResidentialEnergyScenario | Synthetic VA household population + adoption scenarios + PV generation (2030; ResStock load deferred until statewide source available) | Ingest landed (no prepare.py yet) |

## Schema differences vs. other SDC categories

Energy pipelines bend the standard SDC long-format schema in two ways:

1. **`datetime` replaces `year`.** Energy data has intra-day granularity (hourly bins on representative days); `year` (int) can't hold hour-of-day. We store ISO 8601 timestamps as strings: `"2030-01-01T15:00:00"` for hourly, `"2030-01-01"` for daily/static.
2. **New `scenario` column.** These are simulation outputs, not observed measurements. Different simulation runs (different adoption rates, scenario years, weather days) produce different result sets that need to be distinguishable. The `scenario` column is also encoded in output filenames for archive distinguishability.

The point schema (`sdc_core.io.POINT_SCHEMA_REQUIRED`) is unchanged — points use the existing `year: int` field. Energy-specific point datasets that need datetime granularity will get a schema extension when the need arises.

## Hour-of-day-profile data convention

When a dataset captures typical hour-of-day patterns (24 buckets representing average behavior across a day) rather than specific timestamps, encode the hour into `datetime` as:

```
{scenario_year}-01-01THH:00:00
```

The Jan 1 anchor is canonical — the date component is **not** a real observation date; it's a fixed marker for "typical hour-of-day pattern in this scenario year." Hour `HH` is zero-padded (0 → `"00"`, 7 → `"07"`, 23 → `"23"`).

Pipelines that follow this convention:
- `energy/EVChargingDemand/` — hourly EV charging energy and active-location counts

Future pipelines (residential ResStock load profiles, hourly PV generation) will use the same convention. If a future dataset needs a real multi-day time series instead, use the full ISO 8601 datetime with the correct calendar date.

## Dashboard target

Energy pipelines emit dashboard files to `dashboard_data/va_energy_data/` (separate from `virginia_public_health_data/` and `national_capital_region_data/`). A new dashboard consumer will be built against this directory.
