# Power Infrastructure (HIFLD, VA)

Pulls HIFLD **power plants** and **electric substations** for Virginia from the
ArcGIS REST API and produces:

1. A point-schema CSV — one row per facility (for a map overlay).
2. A county-aggregated long-format CSV — counts and total plant capacity per county.

## Status

`prepare.py` is intentionally not present yet. Energy dashboards aren't wired;
outputs live at `data/distribution/` only. No Zenodo publishing / no
`update_version()` (energy-category convention).

## Source

HIFLD (Homeland Infrastructure Foundation-Level Data), via the ArcGIS Feature
Services republished by the **543rd Engineer Detachment GPC**
(`services5.arcgis.com/HDRa0B57OVrv2E1q`):

- Power plants: `.../Power_Plants/FeatureServer/0/query`
- Substations: `.../Electric_Substations/FeatureServer/0/query`

`ingest.py` pages each layer's `/query` endpoint with `where=STATE='VA'`,
`f=json`, and `resultOffset`/`resultRecordCount` (page size 2000). County FIPS
comes directly from the source `COUNTYFIPS` field — no spatial join. Raw per-layer
responses are cached to `data/original/` (gitignored). Snapshot label:
`hifld_snapshot_2026_05_29`.

## Schema

Point CSV (`va_pt_hifld_2026_power_infrastructure.csv.xz`): standard point schema
(`facility_id, facility_name, lat, lon, year, type`) plus `status`, `operator`,
`plant_source` (PRIM_FUEL), `plant_capacity_mw` (OPER_CAP), `max_voltage`
(MAX_VOLT), `lines`, `geoid` (COUNTYFIPS), `source_id`. `type` is `power_plant`
or `substation`.

County CSV (`va_ct_hifld_2026_power_infrastructure.csv.xz`): energy long-format
`(geoid, datetime, measure, value, moe, region_type, data_method, scenario)` with
`data_method="observed"`. Measures: `power_plant_count`, `substation_count`,
`power_facility_count`, `total_plant_capacity_mw`. See `measure_info.json`.

## Run

```bash
# From repo root (needs outbound HTTPS to services5.arcgis.com):
uv run python energy/PowerInfrastructure/code/distribution/ingest.py
```

## Tests

```bash
uv run pytest energy/PowerInfrastructure/code/distribution/test_transforms.py -v
```

## Outputs

- `data/distribution/va_pt_hifld_2026_power_infrastructure.csv.xz` (point CSV)
- `data/distribution/va_ct_hifld_2026_power_infrastructure.csv.xz` (county long-format)

## Validation (sanity checks, no R reference)

This is a net-new dataset; there is no prior output to compare against. Observed
at the **2026-05-29 snapshot** (`uv run python .../ingest.py`):

- **1,571 facility points**: 189 power plants + 1,382 substations. All coordinates
  fall inside the VA bounding box.
- **128 localities** in the county output (4 measures each = 512 rows). Statewide
  totals: 1,382 substations, 188 plants counted (1 plant dropped for a missing
  `COUNTYFIPS`), **≈31,642 MW** total operating capacity.
- Known facilities present and correctly placed: **North Anna** (Louisa County,
  51109; nuclear, 1,960 MW), **Surry** (51181; nuclear, 1,695 MW), and **Bath
  County** pumped-storage (51017; 2,862 MW) — which tops `total_plant_capacity_mw`.
- Facility density highest in Northern Virginia: Prince William (51153, 66),
  Fairfax (51059, 65), Loudoun (51107, 39).
- Capacity coverage: 181/189 plants report `OPER_CAP`; the rest contribute 0.
- Exactly **1** facility was dropped from the county counts for a missing/invalid
  `COUNTYFIPS` (it remains in the point CSV, which keeps any row with valid coords).

## Known caveats

- **HIFLD completeness & currency** — counts reflect the HIFLD snapshot, not a
  live regulatory inventory; substations are limited to ≥69 kV facilities.
- **`max_voltage` / capacity null sentinel** — HIFLD codes unknown numerics as
  `-999999`; `ingest.py` maps these to `NaN` (and to 0 in the capacity sum).
- **`total_plant_capacity_mw` is a lower bound** — plants with unreported
  `OPER_CAP` contribute 0.
- **All statuses included** — facilities are counted regardless of `STATUS`
  (e.g. operating vs. planned); `status` is carried per facility for filtering.
- **Snapshot, not time series** — one snapshot at the query date; no historical years.
