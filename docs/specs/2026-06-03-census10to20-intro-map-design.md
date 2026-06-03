# census10to20 Introduction Map — Design

## Overview

Add a real-geography before/after map to the `sdc-census10to20` introduction
article showing a value recorded on a real **2010** census tract redistributed
onto the overlapping **2020** tracts via `convert_2010_to_2020_bounds`. Same
static-PNG rendering pattern as the redistribute and catchment intro maps;
adapted to census10to20's boundary-change story.

## Direction settled in brainstorming

- **Depicts:** one real VA "moved" 2010 tract (1,000 people) → its 2020 successor
  tracts, area-weighted. Two-panel before/after choropleth.
- **Real geometry from committed files:** 2010-vintage `education/docs/maps/tract_2018.geojson`
  (3,475 VA tracts, `GEOID`/`geometry`, EPSG:4269) and 2020-vintage
  `education/docs/maps/tract_2020.geojson` (3,857 tracts). Extract one tract +
  its successors into small per-article assets.
- **Network dependency accepted (intrinsic).** `convert_2010_to_2020_bounds` and
  `get_2010_2020_bound_changes` fetch the Census 2010↔2020 relationship file
  (`https://www2.census.gov/geo/docs/maps-data/data/rel2020/...`); there is no
  bundled crosswalk. The article's existing examples already rely on this. The
  committed PNG renders offline; re-running the figure/example needs network.
- **Additive:** keep the existing `standardize_all` intro content; add a new
  "Visualizing a boundary change" section with the map.
- **Docs-only — no PyPI release.**

## Verified facts

- Crosswalk (`get_2010_2020_bound_changes(res="tract")`, VA) columns:
  `geoid20, geoid10, area20, area10, area_part, type_change`. `type_change`
  values: `moved` (most common), `same`, `split`.
- `convert_2010_to_2020_bounds(data, *, geoid_col="geoid", val_col="value", state_fips="51")`:
  one row per 2010 GEOID in → 2020-GEOID rows out; "moved" boundaries are split
  area-proportionally (`area_part / area20`), "same"/"split" pass through.
- For a **moved** 2010 tract mapping to multiple 2020 tracts, a single 1,000-person
  input is divided across the successors — the meaningful before/after.

## Tract selection (deterministic)

In the extraction step:
1. Fetch the VA tract crosswalk.
2. Restrict to `type_change == "moved"`.
3. Group by `geoid10`; keep those mapping to 2–4 distinct `geoid20`.
4. Require the `geoid10` to be present in `tract_2018.geojson` and **all** its
   `geoid20` successors present in `tract_2020.geojson` (so every polygon can be
   drawn).
5. Choose the first such `geoid10` by sorted order (deterministic).

This guarantees a drawable, genuinely-divided example with no manual picking.

## Data assets

- `docsite/packages/sdc-census10to20/articles/data/tract_2010.geojson` — the one
  chosen 2010 tract polygon (from `tract_2018.geojson`), column `geoid`.
- `docsite/packages/sdc-census10to20/articles/data/tracts_2020.geojson` — its
  2020 successor tracts (from `tract_2020.geojson`), column `geoid`.

## Example (added to the article)

A new "Visualizing a boundary change" section:

1. Build a one-row input: the chosen 2010 `geoid` with `value = 1000`.
2. `convert_2010_to_2020_bounds(data, state_fips="51")` → values on the 2020
   successor geoids (real captured output shown).
3. Note the values sum back to ~1,000 (area-weighted split for the "moved" case).

The example is shown with the real chosen GEOID; output captured by running.

## Figure

`docsite/packages/sdc-census10to20/articles/figures/census10to20_map.py` — reads
the two assets, runs `convert_2010_to_2020_bounds`, renders a two-panel PNG
(`articles/img/census10to20-boundary-change.png`), projected EPSG:32618:

- **Left:** the 2010 tract, single polygon, labeled with the GEOID + "1,000 people".
- **Right:** the 2020 successor tracts, choropleth-shaded by redistributed value,
  with a colorbar.

Caption: the 2010-boundary value is split across the 2020 tracts that replaced it.

## Verification / success criteria

- The extraction picks a real moved tract, writes both assets, prints the chosen
  GEOID + successor count.
- The figure script runs (with network for the crosswalk), writes the PNG, and
  prints the per-2020-geoid values summing to ~1,000.
- The added example's output block matches real captured output.
- `mkdocs build --strict` clean; the PNG is in the built `site/`.
- After merge + deploy: the article page returns 200 and the image URL
  (`.../articles/img/census10to20-boundary-change.png`) returns 200.

## Out of scope

- Block-group-level boundary-change map.
- Offline-caching the crosswalk / removing the network dependency.
- Changes to the other articles or any package source.
- Any PyPI release.
