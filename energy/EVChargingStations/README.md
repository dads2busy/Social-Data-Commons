# EV Charging Stations (VA, 2030 scenario)

Ingests a simulated EV charging-station inventory for Virginia and produces:

1. A point-schema CSV of one row per (station, charger-level) where the level count > 0 — consumable by `sdc_core.io.export_point_layer` when a dashboard pipeline is added.
2. A county-aggregated long-format CSV with 8 measures (station and charger counts by level + totals).

## Status

`prepare.py` is intentionally not present yet. Once the new energy dashboard's shape is decided, `prepare.py` will be added to emit GeoJSON + dashboard files to `dashboard_data/va_energy_data/`. For now, the pipeline stops at `data/distribution/`.

## Source

`va_charging_stations_30.csv` (5,241 rows). Currently sourced from
`~/git/scratch/Energy work/Data/`. Copy into `data/original/` before running
`ingest.py`. The directory is gitignored.

## Schema

Output uses the **energy long-format schema** (see `energy/README.md`):

| Column      | Type  | Notes                                                  |
|-------------|-------|--------------------------------------------------------|
| geoid       | str   | 5-digit county FIPS, assigned by spatial join          |
| datetime    | str   | ISO 8601; "2030-01-01" for this static inventory       |
| measure     | str   | one of 8 measure names (see measure_info.json)         |
| value       | float | numeric measure value                                  |
| moe         | float | NaN — simulation has no measurement uncertainty        |
| region_type | str   | "county"                                               |
| data_method | str   | "simulated"                                            |
| scenario    | str   | "va_2030_run30"                                        |

## Scenario placeholder

The source filename's `_30` suffix has not been attributed (charger-count
target? run index? penetration scenario?). Until clarified, the `scenario`
column and filename token both use `va_2030_run30`. Filename `data_source`
token is `sim`.

When the meaning is known, update:
- `pipeline.yaml` (`source.scenario`, `source.data_source_token`)
- `measure_info.json` provenance fields
- Output filenames will change accordingly — rerun ingest

## Multi-type rows

A station with multiple non-zero charger levels (e.g., l2_charger_count=1
and l3_charger_count=2) produces multiple point rows — one per level. The
`facility_id` is the composite `{ID}_{level}` so each row is uniquely
identifiable; `station_id` retains the original ID for dedup when computing
station-level (vs. charger-level) measures.

## Run

```bash
# From repo root:
uv run python energy/EVChargingStations/code/distribution/ingest.py
```

## Tests

```bash
uv run pytest energy/EVChargingStations/code/distribution/test_transforms.py -v
```

## Outputs

- `data/distribution/va_pt_sim_2030_run30_ev_charging_stations.csv.xz` (point CSV)
- `data/distribution/va_ct_sim_2030_run30_ev_charging_stations.csv.xz` (county long-format)

## Known data losses

The spatial join uses the 2020 Census cartographic boundary file for VA
counties (`geographies/VA/Census Geographies/County/2020/...`). The
source's OSM-derived station coordinates don't always align perfectly:

- **~20 stations (≈0.4%) fall outside any VA county polygon** and are
  dropped with a warning. These are typically near the state border where
  the cartographic generalization doesn't quite match OSM-derived coords.
- **~2 stations land on county polygon boundaries** and would match
  multiple counties under `predicate="intersects"`. `spatial_join_counties`
  dedupes these (first match wins) with a warning.

Net effect: total chargers in the output is about **45 fewer** than the
raw source sum (≈9,879 vs. ≈9,924), a 0.45% loss. The station-count
measures use `nunique(station_id)` and are unaffected by any residual
boundary edge cases.

If a downstream consumer needs lossless geography assignment, switch the
input shapefile to TIGER full-resolution boundaries (or add a buffer to
the cartographic polygons).
