# census10to20 Introduction Map — Design (revised)

## Overview

Add a real-geography **before/after** map to the `sdc-census10to20` introduction
showing a small county's tract-level values converted from **2010** boundaries to
**2020** boundaries with `convert_2010_to_2020_bounds`. Static-PNG pattern as the
other intro maps.

> **Revision note (2026-06-03):** the original single-tract design was scrapped
> during implementation. `convert_2010_to_2020_bounds` is **not** count-conserving
> for a single-tract input — for "moved" tracts it computes
> `value × area_part/area20` (the fraction of each *2020* tract covered) and sums
> across *all* overlapping 2010 sources. Feeding it one tract makes every 2020
> tract it fully covers inherit the *full* value (a 1,000-person tract produced a
> 3,017 total). The function is meant to convert a **complete** 2010 dataset to
> 2020 boundaries. So the illustration must be **area-level** (a full set of a
> small area's 2010 tracts), where conversion behaves as area-weighted
> reaggregation and totals are approximately preserved.

## Direction settled in brainstorming + revision

- **Depicts:** a small VA county's 2010 tracts (each with a synthetic population)
  converted as a full set onto its 2020 tracts — two choropleths of the same
  measure over the same county footprint (2010 boundaries vs 2020 boundaries).
- **County: 51027 (Buchanan County, VA)** — chosen because the full-set
  conversion is essentially total-conserving (validated: 7 input tracts,
  input sum 22,925 → output sum 22,925) and it has a readable tract count.
- **Real geometry from committed files:** 2010-vintage
  `education/docs/maps/tract_2018.geojson`, 2020-vintage `tract_2020.geojson`
  (both VA, `GEOID`/`geometry`, EPSG:4269). Extract the county's tracts into
  small assets.
- **Network dependency accepted (intrinsic):** `convert_2010_to_2020_bounds`
  fetches the Census relationship file; the article's other examples already do.
  Committed PNG renders offline.
- **Additive:** keep the existing `standardize_all` intro content; add a
  "Visualizing a boundary change" section.
- **Docs-only — no PyPI release.**

## Verified API / semantics

- `convert_2010_to_2020_bounds(data, *, geoid_col="geoid", val_col="value", state_fips="51")`
  → columns `geoid` (2020) + value. Input: one row per 2010 GEOID. "moved" →
  `value × area_part/area20` summed across sources; "same"/"split" pass through.
- Used on a **full** county of 2010 tracts, each 2020 tract's coverage fractions
  from its overlapping 2010 sources sum to ≈1, so the result is an area-weighted
  reaggregation with totals approximately preserved (minor leakage where county
  tracts straddle the county line).

## Tract cluster selection (deterministic)

Hard-code county FIPS **`51027`** (validated above). The extraction:
1. Loads 2010 VA tracts (`tract_2018`) and 2020 VA tracts (`tract_2020`).
2. `cty10 = tracts where GEOID[:5] == "51027"` (the input set).
3. `cty20 = 2020 tracts where GEOID[:5] == "51027"` (the drawn 2020 footprint).
4. Writes both to assets. Assigns synthetic populations with a fixed RNG seed.

(If 51027's geometry is somehow missing from a file, fall back to `51005`, the
next-best validated county — noted in the plan.)

## Data assets

- `docsite/packages/sdc-census10to20/articles/data/tracts_2010.geojson` — the
  county's 2010 tracts, column `geoid`.
- `docsite/packages/sdc-census10to20/articles/data/tracts_2020.geojson` — the
  county's 2020 tracts, column `geoid`.

## Example (added to the article)

A "Visualizing a boundary change" section:
1. Load `tracts_2010.geojson`; assign each tract a synthetic population
   (fixed seed) — a small long-format frame (`geoid`, `value`).
2. `convert_2010_to_2020_bounds(data, state_fips="51")` → values on the 2020
   tracts (real captured output; show `head()` and the input/output totals).
3. Note the total is approximately preserved (area-weighted reaggregation), with
   minor leakage at the county edge.

## Figure

`docsite/packages/sdc-census10to20/articles/figures/census10to20_map.py` — reads
both assets + the synthetic populations, runs `convert_2010_to_2020_bounds`,
renders a **two-panel** PNG (`articles/img/census10to20-boundary-change.png`),
projected EPSG:32618, with a **shared color scale** across panels:

- **Left:** the 2010 tracts, choropleth by population, titled "2010 boundaries".
- **Right:** the county's 2020 tracts, choropleth by the converted population,
  titled "2020 boundaries". The redrawn boundaries are visible between panels.

Caption: the same population, re-expressed on the redrawn 2020 tracts.

## Verification / success criteria

- Extraction writes both county assets (2010 and 2020 tracts present, drawable).
- The figure script runs (network for the crosswalk), writes the PNG, prints the
  input total and 2020 output total (close, modulo edge leakage).
- The added example's output block matches real captured output.
- Both panels share a color scale and show the same county with different tract
  boundaries.
- `mkdocs build --strict` clean; PNG in the built `site/`.
- After merge + deploy: article 200; image URL 200.

## Out of scope

- Block-group-level map; removing the network dependency; other articles; any
  package source change; any PyPI release.
