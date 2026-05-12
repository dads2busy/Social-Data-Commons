# EV Charging Demand (VA, 2026 scenario)

Ingests simulated 2026 VA EV charging events (location × hour-of-day granularity) and produces:

1. A point-schema CSV with one row per unique charging location, summing daily kWh and counting active hours.
2. A county-level long-format CSV at hour-of-day granularity, with 2 measures: total energy demand (kWh) and distinct active charging locations.

## Status

`prepare.py` is intentionally not present yet. Outputs live at `data/distribution/` only.

## Source

`charging_events_va_2026_grouped_run_2_eval_30.csv` (28 MB, 376,186 events). Currently sourced from `~/git/scratch/Energy work/Data/` and copied into `data/original/charging_events_va_2026.csv` (gitignored).

Source columns: `charging_station_id, old_pop_hid, latitude, longitude, hour, total_kWh_added`.

- `charging_station_id` is unique per location (65,914 distinct values). ID format hints at type:
  - `va_<digits>_existing` → public station (~1,232 locations)
  - purely numeric → residential or other simulated location (~64,577)
  - other formats → `unknown` (~105)
- `hour` is hour-of-day (0–23), representing a typical daily profile — not an absolute timestamp.
- `old_pop_hid` is the synthetic household ID for residential rows; `"Not present"` for ~5.6% of rows. **Per the no-microdata policy this column is dropped during ingest and not retained in outputs.**

## Scenario placeholder

The filename's `_run_2_eval_30` suffixes have not been attributed (run index? evaluation index? penetration scenario?). The `scenario` column holds `"va_2026_run2_eval30"` as a stable placeholder; revise when the meaning is clarified.

## Schema

Output uses the **energy long-format schema** (see `energy/README.md`):

| Column      | Type  | Notes                                                                  |
|-------------|-------|------------------------------------------------------------------------|
| geoid       | str   | 5-digit county FIPS (from centroid sjoin)                              |
| datetime    | str   | ISO 8601, e.g. `"2026-01-01T07:00:00"` — hour-of-day profile (see below) |
| measure     | str   | `ev_charging_demand_kwh` or `n_active_charging_locations`              |
| value       | float | numeric measure value                                                  |
| moe         | float | NaN — simulation has no measurement uncertainty                        |
| region_type | str   | `"county"`                                                              |
| data_method | str   | `"simulated"`                                                           |
| scenario    | str   | `"va_2026_run2_eval30"`                                                |

## Hour-of-day convention

This pipeline establishes the convention for typical-day-profile energy data: `datetime = "{scenario_year}-01-01THH:00:00"` for hour-of-day HH (zero-padded, 0–23). The Jan 1 anchor is canonical — the value represents typical hour-of-day patterns, not events on any specific calendar date. Future hourly pipelines (ResStock load, PV generation) follow this convention. Documented in `energy/README.md`.

## Run

```bash
# From repo root:
uv run python energy/EVChargingDemand/code/distribution/ingest.py
```

## Tests

```bash
uv run pytest energy/EVChargingDemand/code/distribution/test_transforms.py -v
```

## Outputs

- `data/distribution/va_pt_sim_2026_ev_charging_demand.csv.xz` (point CSV — ~65,914 rows, one per location)
- `data/distribution/va_ct_sim_2026_ev_charging_demand.csv.xz` (county long-format — 2 measures × 24 hours × N active VA counties)

## Known caveats

- **Typical-day profile, not real timestamps.** All `datetime` values land on 2026-01-01. This is a hour-of-day convention, not an actual time series. Don't treat them as if they were 24 specific minutes of Jan 1.
- **No household attribution in output.** `old_pop_hid` is dropped at ingest. If a future pipeline needs to join individual events back to synthetic households, re-derive from the source.
- **Public vs. residential split is heuristic.** The `type` field is inferred from `charging_station_id` format, not from authoritative metadata. The `va_*_existing` pattern is a reliable signal for public stations; numeric IDs are reliably non-public, but their further classification (residential vs. workplace vs. other) is not distinguished here.
