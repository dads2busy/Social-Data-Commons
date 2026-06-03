# Visual Maps in the Introduction Articles — Design

## Overview

Add rendered map figures to the **redistribute** and **catchment** introduction
articles on the docs site, using **real census geographies** drawn with
matplotlib + geopandas and committed as PNGs. The redistribute intro shows a
census tract's count redistributed to its block groups (before/after
choropleth); the catchment intro shows accessibility across a real county's block
groups to a few clinics (choropleth on a real county basemap).

## Decisions settled in brainstorming

- **Scope:** redistribute + catchment introductions only. census10to20 deferred.
- **Real census geographies** for both, sourced from the committed
  `geographies/NCR/Census Geographies/Block Group/2020/data/distribution/ncr_geo_census_cb_2020_census_block_groups.geojson`
  (EPSG:4326; columns `geoid, region_name, region_type, year, geometry`; 3,626
  NCR block groups). A small extracted asset is shipped per article so each is
  self-contained and reproducible.
- **Rendering:** static PNG via matplotlib + geopandas (already in the root dev
  group). No new dependency, no interactive/JS, **no web-tile basemap** — the
  "basemap" is the real county/tract polygons themselves (avoids a contextily +
  network dependency).
- **Docs-site only — no PyPI release.** READMEs unchanged (PyPI renders
  repo-relative images poorly); no `v0.1.2`.

## Shared technical notes

- **Projected CRS for distance/area.** Plot and (for catchment) compute distances
  in **UTM 18N (EPSG:32618)**, which covers the NCR in meters. Lat/lon degrees
  (EPSG:4326) would give wrong distances/areas.
- **Figure scripts are committed and reproducible.** Each figure has a generation
  script under `docsite/packages/<pkg>/articles/figures/` that reads the shipped
  asset and writes the PNG under `docsite/packages/<pkg>/articles/img/`. Run with
  `uv run --group dev python <script>` during authoring; the PNG is committed.
- **Examples stay runnable and run-verified;** outputs in the prose are real
  captured output, regenerated since both intro examples change.

## redistribute introduction

### Data asset
`docsite/packages/sdc-redistribute/articles/data/tract_bgs.geojson` — one real
NCR tract with ~4 block groups, extracted from the source file: filter BGs whose
`geoid[:11]` equals a chosen tract with 3–5 BGs (selected during implementation,
e.g. a Fairfax/Arlington tract), and dissolve them to form the tract polygon
(`tract = bgs.dissolve()`).

### Example (rewritten)
Replace the current toy-`box()` example with one that:
1. Loads `tract_bgs.geojson`; derives the single tract geometry by dissolve.
2. Writes the tract and BG geometries to temp GeoJSON (what `redistribute_direct`
   consumes) — or passes the loaded GeoDataFrames if the API accepts paths only
   (it requires paths, so write temp files).
3. Assigns the tract a synthetic count (e.g. `pop = 1000`).
4. Runs `redistribute_direct(source_df, source_geo=tract, target_geos={"block_group": bgs}, count_cols=["pop"])`.
5. Prints the per-BG `pop_direct` (real captured output in the article).

### Figure
`articles/img/redistribute-tract-to-bg.png` — two panels side by side (projected
to EPSG:32618):
- **Left:** the tract, single polygon, labeled with the total count (1,000).
- **Right:** the block groups, choropleth-shaded by redistributed `pop_direct`,
  with a shared colorbar/value labels.

Caption: counts split in proportion to each block group's area.

## catchment introduction

### Data asset
`docsite/packages/sdc-catchment/articles/data/county_bgs.geojson` — all block
groups of one real NCR county (e.g. Arlington, `geoid[:5] == "51013"`, ~204 BGs),
extracted from the source file.

### Example (rewritten to a real 2-D scenario)
Replace the 1-D toy line with:
1. Load `county_bgs.geojson`, project to EPSG:32618.
2. Each block group is a demand unit: `consumers` = BG `geoid` + a synthetic
   population (e.g. derived deterministically, or a flat value); coordinates =
   BG centroids.
3. Place 3 clinics (`providers`) at chosen coordinates inside the county, each
   with a bed capacity.
4. `cost = euclidean_cost(bg_centroids_xy, clinic_xy)` (meters).
5. `access = catchment_ratio(consumers, providers, cost, weight="gaussian", scale=..., max_cost=...)`.
6. Print a short head() of the access scores (real captured output).

### Figure
`articles/img/catchment-county-access.png` — one map (EPSG:32618):
- The county's block groups shaded by access score (choropleth).
- The 3 clinics overplotted as markers sized by capacity.
- Colorbar for access; caption noting darker = better access, and that access
  falls off with distance from clinics.

## Article integration

- Embed each PNG with `![<alt>](img/<file>.png)` plus a short caption line.
- Keep the existing prose structure (Setup → worked example → output → See also),
  inserting the map after the worked example.
- The catchment intro's mention of `KERNELS` and binary-vs-decay stays; the figure
  illustrates the decay variant on real geography.

## Verification / success criteria

- Both figure scripts run clean and write their PNGs; PNGs committed under
  `articles/img/`.
- Both rewritten intro examples run and the article output blocks match real
  output.
- `mkdocs build --strict` clean; the two PNGs are present in the built `site/`.
- After merge + docs deploy: the two article pages return 200 and the `<img>`
  tags resolve (HTTP 200 on the image URLs).

## Out of scope

- census10to20 map (deferred follow-on).
- Interactive/web-tile maps.
- Changes to the method-comparison or case-study articles.
- README image embedding / any PyPI release.
- Any package source change.
