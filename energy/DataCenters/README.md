# Data Centers (IM3 Atlas, VA-filtered)

Ingests the IM3 Open Source Data Center Atlas (OSM-derived, US-wide) and produces VA-only outputs:

1. A point-schema CSV with one row per facility record (point, building, or campus geometry).
2. A county-aggregated long-format CSV with 5 measures (counts by geometry type + total + total sqft).

## Status

`prepare.py` is intentionally not present yet. Energy dashboards aren't wired; outputs live at `data/distribution/` only.

## Source

[IM3 Open Source Data Center Atlas](https://data.msdlive.org/records/p147s-4h760) — v2026.02.09, published by Pacific Northwest National Laboratory under DOE's IM3 program. Derived from OpenStreetMap (OSM).

Download the CSV from the MSDLive record page and place it at:

```
energy/DataCenters/data/original/im3_atlas_data_centers.csv
```

The directory is gitignored.

## Source columns

`id, state, state_abb, state_id, county, county_id, ref, operator, name, sqft, lat, lon, type`

- `county_id` is the 5-digit county FIPS (no spatial join needed).
- `type` is one of `point`, `building`, `campus` — the geometric representation of the facility in OSM.
- A single physical facility may appear in multiple rows if OSM represents it both as, say, a building and a campus.

## Schema

Output uses the **energy long-format schema** (see `energy/README.md`):

| Column      | Type  | Notes                                                  |
|-------------|-------|--------------------------------------------------------|
| geoid       | str   | 5-digit county FIPS (from source `county_id`)          |
| datetime    | str   | ISO 8601; "2026-02-09" — IM3 Atlas publication date    |
| measure     | str   | one of 5 measure names (see measure_info.json)         |
| value       | float | numeric measure value                                  |
| moe         | float | NaN — observed source has no measurement uncertainty   |
| region_type | str   | "county"                                               |
| data_method | str   | "observed"                                             |
| scenario    | str   | "im3_atlas_v2026_02_09" — source-snapshot revision     |

## Multi-representation rows (no expansion)

Unlike `EVChargingStations` (which multi-type-expands one source row into multiple), the source here already arrives one-row-per-(facility, geometry_type). We keep each row as-is. The `facility_id` is `f"im3_{id}_{type}"` so different geometric representations of the same physical facility don't collide.

If you need a unique-physical-facility count instead of records, dedupe on `ref` (the OSM reference) downstream — that's not done here because it requires a design decision about which geometric representation to prefer.

## Run

```bash
# From repo root:
uv run python energy/DataCenters/code/distribution/ingest.py
```

## Tests

```bash
uv run pytest energy/DataCenters/code/distribution/test_transforms.py -v
```

## Outputs

- `data/distribution/va_pt_im3_2026_data_centers.csv.xz` (point CSV)
- `data/distribution/va_ct_im3_2026_data_centers.csv.xz` (county long-format)

## Known caveats

- **Counts are records, not unique physical facilities.** A facility represented in OSM as both a building and a campus contributes 2 to `total_data_center_count`. The per-geometry-type measures don't have this issue. Future work could dedupe on `ref`.
- **sqft is NaN for many point records** (points have no polygon area). These are treated as 0 in `total_data_center_sqft`, so the per-county sqft is a lower bound on actual facility area.
- **VA is a known data-center hotspot.** Loudoun County (`51107`) hosts the world's largest data center concentration. Expect 51107 to dominate every measure.
