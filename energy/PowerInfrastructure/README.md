# Power Infrastructure (OpenStreetMap, VA)

Pulls OpenStreetMap power **plants** (`power=plant`) and **substations**
(`power=substation`) for Virginia via the Overpass API and produces:

1. A point-schema CSV — one row per OSM feature (for a map overlay).
2. A county-aggregated long-format CSV — counts and total plant capacity per county.

## Status

`prepare.py` is intentionally not present yet. Energy dashboards aren't wired;
outputs live at `data/distribution/` only. No Zenodo publishing / no
`update_version()` (energy-category convention).

## Source

OpenStreetMap, queried live through the Overpass API via
[`osmnx`](https://osmnx.readthedocs.io) `features_from_place("Virginia, United States",
tags={"power": ["plant", "substation"]})`. The raw GeoDataFrame is cached to
`data/original/osm_va_power.parquet` (gitignored) so reruns are reproducible and
offline. Snapshot label: `osm_overpass_2026_05_29`.

## Schema

Point CSV (`va_pt_osm_2026_power_infrastructure.csv.xz`): standard point schema
(`facility_id, facility_name, lat, lon, year, type`) plus `operator`,
`plant_source`, `plant_capacity_mw`, `voltage`, `osm_id`, `geoid`.

County CSV (`va_ct_osm_2026_power_infrastructure.csv.xz`): energy long-format
`(geoid, datetime, measure, value, moe, region_type, data_method, scenario)` with
`data_method="observed"`. Measures: `power_plant_count`, `substation_count`,
`power_facility_count`, `total_plant_capacity_mw`. See `measure_info.json`.

## Run

```bash
# From repo root:
uv run python energy/PowerInfrastructure/code/distribution/ingest.py
# Force a fresh Overpass query (ignore the cache):
uv run python energy/PowerInfrastructure/code/distribution/ingest.py --refresh
```

## Tests

```bash
uv run pytest energy/PowerInfrastructure/code/distribution/test_transforms.py -v
```

## Outputs

- `data/distribution/va_pt_osm_2026_power_infrastructure.csv.xz` (point CSV)
- `data/distribution/va_ct_osm_2026_power_infrastructure.csv.xz` (county long-format)

## Validation (sanity checks, no R reference)

This is a net-new dataset; there is no prior output to compare against. After a
run, confirm:

- Total plant and substation counts for VA are plausible (hundreds of substations,
  tens-to-hundreds of plants).
- Known facilities appear: North Anna (Louisa County, 51109) and Surry
  (Surry County, 51181) nuclear stations.
- Substation density is highest in Northern Virginia (Loudoun 51107, Fairfax 51059).
- The count of centroids dropped for falling outside VA counties is small.

_Fill in the observed numbers after the first run._

## Known caveats

- **OSM completeness varies** — counts reflect what is mapped in OSM, not a
  regulatory inventory. Undermapped areas undercount.
- **Multi-representation** — a physical site mapped as both a node and a relation
  could be double-counted; `facility_id` keeps them distinct, but the count
  measures include both. Dedupe is future work.
- **`total_plant_capacity_mw` is a lower bound** — many plants lack
  `plant:output:electricity`.
- **Snapshot, not time series** — one snapshot at the query date; no historical years.
