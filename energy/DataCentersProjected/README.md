# Data Centers Projected (IM3 CERF, VA-filtered, all 20 scenarios)

Ingests the IM3 CERF projected data center siting dataset and produces VA-only outputs spanning all 20 scenario combinations (4 demand growth tiers × 5 market-gravity weights).

## Status

`prepare.py` is intentionally not present yet. Outputs live at `data/distribution/` only.

## Source

[IM3 Projected US Data Center Locations](https://data.msdlive.org/records/r0cga-34g05) — published by Pacific Northwest National Laboratory under DOE's IM3 program. Generated using the CERF (Capacity Expansion Regional Feasibility) — Data Centers model. Polygons in Albers Equal Area Conic (ESRI:102003).

Downloaded to `data/original/` (gitignored). Layout:

```
data/original/
├── README.pdf
├── changelog.txt
├── low_growth/        (5 files: 0/25/50/75/100_market_gravity.geojson)
├── moderate_growth/   (5 files)
├── high_growth/       (5 files)
└── higher_growth/     (5 files)
```

Each GeoJSON contains polygons for one (growth_tier, gravity_weight) combination — 20 in total.

## Scenarios

The 20 scenarios are encoded as combinations of:
- **Growth tier** (annual demand growth rate from 2023): `low`, `moderate`, `high`, `higher`
- **Market gravity weight** (relative weight of market proximity vs. locational cost in siting score): `0`, `25`, `50`, `75`, `100`

Combined into the `scenario` column as `im3_cerf_{tier}_{weight}`. Example values:
- `im3_cerf_low_0` (lowest demand, pure locational-cost siting)
- `im3_cerf_moderate_50` — **canonical / default scenario** (mid demand, balanced)
- `im3_cerf_higher_100` (highest demand, pure market-proximity siting)

Important: each scenario is a fully independent re-siting. The same `id` (e.g. `"51_0"`) across two scenarios does NOT refer to the same physical site.

## Schema

Output uses the **energy long-format schema** (see `energy/README.md`):

| Column      | Type  | Notes                                                            |
|-------------|-------|------------------------------------------------------------------|
| geoid       | str   | 5-digit county FIPS (from centroid sjoin against 2020 boundaries) |
| datetime    | str   | "2035-01-01" (projection horizon)                                 |
| measure     | str   | one of 6 measure names (see measure_info.json)                    |
| value       | float | numeric measure value                                             |
| moe         | float | NaN — simulation has no measurement uncertainty                   |
| region_type | str   | "county"                                                          |
| data_method | str   | "simulated"                                                       |
| scenario    | str   | one of 20 `im3_cerf_*` labels                                     |

## Geometry handling

Source polygons are facility-level campus footprints in Albers meters. For the dashboard overlay we:

1. Reproject to WGS84 (EPSG:4326)
2. Compute polygon centroids
3. Use the centroid as the point marker location
4. Pass campus size and IT power through as point properties

The campus polygon outline itself is not retained in the output (we don't need it for the overlay). If a future use requires polygon footprints, re-read the source GeoJSONs.

## Canonical scenario

`im3_cerf_moderate_50` is the recommended default for any dashboard view. The other 19 are valid alternative scenarios and ship in the same output files; consumers should filter on the `scenario` column.

## Run

```bash
# From repo root:
uv run python energy/DataCentersProjected/code/distribution/ingest.py
```

## Tests

```bash
uv run pytest energy/DataCentersProjected/code/distribution/test_transforms.py -v
```

## Outputs

- `data/distribution/va_pt_im3_2035_data_centers_projected.csv.xz` (point CSV — all 20 scenarios, ~3,770 rows)
- `data/distribution/va_ct_im3_2035_data_centers_projected.csv.xz` (county long-format — 6 measures × N VA counties × 20 scenarios)

## Known caveats

- **No real facility names.** These are hypothetical sites; `facility_name` is synthetic (`"Projected Data Center ({scenario})"`).
- **Uniform facility sizes within a tier.** The CERF model places identically-sized candidate facilities; per-row variability in `data_center_it_power_mw` exists only across demand tiers, not within.
- **Spatial-join boundary edge cases.** Some centroids may fall outside VA county polygons (cartographic boundary file is generalized). The ingest logs a warning and drops them. Magnitude is typically small (a few rows out of thousands).
- **Each scenario is independent.** The same `id` value across scenarios does NOT refer to the same physical site. Count rows per (county, scenario), not per (county, id).
