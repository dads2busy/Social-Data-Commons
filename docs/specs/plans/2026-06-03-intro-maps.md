# Visual Maps in the Introduction Articles — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real-geography map figures to the redistribute and catchment introduction articles.

**Architecture:** Extract small real-geography GeoJSON assets from the committed NCR block-group file; render static PNG maps with matplotlib + geopandas via committed, reproducible figure scripts; rewrite the two intro examples to use the real geographies (run-verified). Docs-site only, no release.

**Tech Stack:** geopandas, matplotlib (dev group), sdc-redistribute / sdc-catchment, MkDocs.

**Spec:** `docs/specs/2026-06-03-intro-maps-design.md`

**Branch:** `feat/intro-maps` (already created).

**Run all commands from the repo root** `/Users/ads7fg/git/social-data-commons`. Source geometry file (referred to as `$NCR_BG`):
`geographies/NCR/Census Geographies/Block Group/2020/data/distribution/ncr_geo_census_cb_2020_census_block_groups.geojson`

**Authoring rule:** the figure scripts print both the package-function output and the figure path. Paste the **real** printed output into the article and embed the **committed PNG**. Selection of the tract/county is deterministic in code (no manual picking).

---

## File Structure

**Create:**
- `docsite/packages/sdc-redistribute/articles/data/tract_bgs.geojson` (asset)
- `docsite/packages/sdc-redistribute/articles/figures/redistribute_map.py`
- `docsite/packages/sdc-redistribute/articles/img/redistribute-tract-to-bg.png`
- `docsite/packages/sdc-catchment/articles/data/county_bgs.geojson` (asset)
- `docsite/packages/sdc-catchment/articles/figures/catchment_map.py`
- `docsite/packages/sdc-catchment/articles/img/catchment-county-access.png`

**Modify:**
- `docsite/packages/sdc-redistribute/articles/introduction.md`
- `docsite/packages/sdc-catchment/articles/introduction.md`

---

## Task 1: redistribute intro map

- [ ] **Step 1: Extract the real tract + block groups asset**

Run (deterministic: first Arlington tract with exactly 4 block groups):

```bash
mkdir -p docsite/packages/sdc-redistribute/articles/data
uv run --group dev python - <<'PY'
import geopandas as gpd
src = "geographies/NCR/Census Geographies/Block Group/2020/data/distribution/ncr_geo_census_cb_2020_census_block_groups.geojson"
g = gpd.read_file(src); g["geoid"] = g["geoid"].astype(str)
arl = g[g["geoid"].str[:5] == "51013"].copy()
arl["tract"] = arl["geoid"].str[:11]
counts = arl["tract"].value_counts()
tract_id = sorted(counts[counts == 4].index)[0]
sub = arl[arl["tract"] == tract_id][["geoid", "geometry"]].sort_values("geoid").reset_index(drop=True)
sub.to_file("docsite/packages/sdc-redistribute/articles/data/tract_bgs.geojson", driver="GeoJSON")
print("tract", tract_id, "bgs", len(sub))
PY
```

Expected: prints `tract 51013... bgs 4` and writes the asset.

- [ ] **Step 2: Write the figure script `docsite/packages/sdc-redistribute/articles/figures/redistribute_map.py`**

```python
"""Render the redistribute introduction map (tract count -> block groups)."""
import pathlib
import tempfile

import geopandas as gpd
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sdc_redistribute import redistribute_direct

HERE = pathlib.Path(__file__).resolve().parent
asset = HERE.parent / "data" / "tract_bgs.geojson"
img = HERE.parent / "img" / "redistribute-tract-to-bg.png"
img.parent.mkdir(parents=True, exist_ok=True)

bgs = gpd.read_file(asset)
bgs["geoid"] = bgs["geoid"].astype(str)
tract_id = bgs["geoid"].str[:11].iloc[0]
tract = bgs.dissolve().assign(geoid=tract_id)[["geoid", "geometry"]]

tmp = pathlib.Path(tempfile.mkdtemp())
tract.to_file(tmp / "tract.geojson", driver="GeoJSON")
bgs[["geoid", "geometry"]].to_file(tmp / "bgs.geojson", driver="GeoJSON")

source_df = pd.DataFrame({"geoid": [tract_id], "year": [2020], "measure": ["pop"], "value": [1000.0]})
out = redistribute_direct(
    source_df, source_geo=tmp / "tract.geojson",
    target_geos={"block_group": tmp / "bgs.geojson"}, count_cols=["pop"],
)
bgs["pop_direct"] = bgs["geoid"].map(out.set_index("geoid")["value"])

tract_p = tract.to_crs(32618)
bgs_p = bgs.to_crs(32618)
fig, ax = plt.subplots(1, 2, figsize=(11, 5))
tract_p.plot(ax=ax[0], color="#cbd5e1", edgecolor="black")
ax[0].set_title(f"Tract {tract_id}\n1,000 people"); ax[0].axis("off")
bgs_p.plot(ax=ax[1], column="pop_direct", cmap="Blues", edgecolor="black",
           legend=True, legend_kwds={"label": "people (pop_direct)"})
ax[1].set_title("Redistributed to block groups\n(area-weighted)"); ax[1].axis("off")
fig.tight_layout()
fig.savefig(img, dpi=130, bbox_inches="tight")
print("wrote", img)
print(out[["geoid", "measure", "value"]].to_string(index=False))
```

- [ ] **Step 3: Run the figure script; capture output + image**

Run: `uv run --group dev python docsite/packages/sdc-redistribute/articles/figures/redistribute_map.py`
Expected: `wrote .../redistribute-tract-to-bg.png` and a 4-row table of `pop_direct` values summing to ~1000. **Record the printed table** (real per-BG values). Open the PNG to confirm two readable panels (grey tract; blue choropleth BGs).

- [ ] **Step 4: Rewrite the redistribute introduction's worked example + embed the map**

In `docsite/packages/sdc-redistribute/articles/introduction.md`, replace the
toy-`box()` "Redistributing a count" example with the real-geography version
(loads the shipped asset, dissolves to the tract, writes temp GeoJSON, runs
`redistribute_direct`), followed by the **captured table** from Step 3 and the
embedded figure:

```markdown
![A census tract's 1,000 people redistributed to its four block groups by area](img/redistribute-tract-to-bg.png)

*The tract's count is split across its block groups in proportion to each one's
share of the tract area.*
```

The example code block is the body of the figure script **minus the matplotlib
section** (load asset → dissolve → temp GeoJSON → `redistribute_direct` → print).
Keep the intro paragraph, Setup, and See also. Use the real `tract_id` from
Step 1 in the prose.

- [ ] **Step 5: Commit**

```bash
git add docsite/packages/sdc-redistribute/articles
git commit -m "docs(redistribute): real tract->block-group map in the introduction"
```

---

## Task 2: catchment intro map

- [ ] **Step 1: Extract the real county block groups asset**

Run (Arlington County, VA = `51013`):

```bash
mkdir -p docsite/packages/sdc-catchment/articles/data
uv run --group dev python - <<'PY'
import geopandas as gpd
src = "geographies/NCR/Census Geographies/Block Group/2020/data/distribution/ncr_geo_census_cb_2020_census_block_groups.geojson"
g = gpd.read_file(src); g["geoid"] = g["geoid"].astype(str)
arl = g[g["geoid"].str[:5] == "51013"][["geoid", "geometry"]].sort_values("geoid").reset_index(drop=True)
arl.to_file("docsite/packages/sdc-catchment/articles/data/county_bgs.geojson", driver="GeoJSON")
print("arlington bgs", len(arl))
PY
```

Expected: prints `arlington bgs 204` (or similar) and writes the asset.

- [ ] **Step 2: Write the figure script `docsite/packages/sdc-catchment/articles/figures/catchment_map.py`**

```python
"""Render the catchment introduction map (accessibility across a real county)."""
import pathlib

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sdc_catchment import catchment_ratio, euclidean_cost

HERE = pathlib.Path(__file__).resolve().parent
asset = HERE.parent / "data" / "county_bgs.geojson"
img = HERE.parent / "img" / "catchment-county-access.png"
img.parent.mkdir(parents=True, exist_ok=True)

bgs = gpd.read_file(asset).to_crs(32618).reset_index(drop=True)
bgs["geoid"] = bgs["geoid"].astype(str)
cent = bgs.geometry.centroid
bg_xy = np.c_[cent.x.values, cent.y.values]

rng = np.random.default_rng(0)
consumers = pd.DataFrame({"geoid": bgs["geoid"], "value": rng.integers(500, 2500, len(bgs)).astype(float)})

# 3 clinics at the centroids of 3 evenly-spaced block groups (guaranteed inside the county).
idx = np.linspace(0, len(bgs) - 1, 3).astype(int)
clinic_xy = bg_xy[idx]
clinics = pd.DataFrame({"geoid": ["A", "B", "C"], "value": [20.0, 15.0, 30.0]})

cost = euclidean_cost(bg_xy, clinic_xy)
access = catchment_ratio(consumers, clinics, cost, weight="gaussian", scale=2000.0, max_cost=8000.0)
bgs["access"] = access.values * 1000.0  # beds per 1,000 people

fig, ax = plt.subplots(figsize=(7, 7))
bgs.plot(ax=ax, column="access", cmap="viridis", edgecolor="white", linewidth=0.2,
         legend=True, legend_kwds={"label": "clinic beds per 1,000 people"})
ax.scatter(clinic_xy[:, 0], clinic_xy[:, 1], c="red", s=clinics["value"] * 8,
           marker="*", edgecolor="black", zorder=5, label="clinics")
ax.set_title("Accessibility to clinics — Arlington County, VA\n(gaussian distance decay)")
ax.axis("off"); ax.legend(loc="upper right")
fig.tight_layout()
fig.savefig(img, dpi=130, bbox_inches="tight")
print("wrote", img)
print("access stats — min/median/max:",
      round(float(bgs["access"].min()), 3),
      round(float(bgs["access"].median()), 3),
      round(float(bgs["access"].max()), 3))
print(bgs[["geoid", "access"]].head().to_string(index=False))
```

- [ ] **Step 3: Run the figure script; verify a real gradient**

Run: `uv run --group dev python docsite/packages/sdc-catchment/articles/figures/catchment_map.py`
Expected: `wrote .../catchment-county-access.png`, and the min/median/max show a
**spread** (not all equal, not all zero). If the choropleth is flat or mostly
zero, adjust `scale` (try 1500–3000) and `max_cost` (try 6000–12000) and re-run
until there is a visible gradient; **record the final values + printed stats**.
Open the PNG to confirm a readable county choropleth with 3 clinic stars.

- [ ] **Step 4: Rewrite the catchment introduction's worked example + embed the map**

In `docsite/packages/sdc-catchment/articles/introduction.md`, replace the 1-D
toy-line example under "A tiny catchment" with a real-county worked example
(load asset → project → centroids → 3 clinics → `euclidean_cost` →
`catchment_ratio`), using the **final `scale`/`max_cost` from Step 3**. Show the
`head()` of access scores (captured output) and embed the map:

```markdown
![Accessibility to three clinics across Arlington County block groups, gaussian decay](img/catchment-county-access.png)

*Each block group is shaded by clinic beds accessible per 1,000 residents; access
falls off with distance from the three clinics (stars).*
```

Keep the intro paragraph, Setup, the `KERNELS` note (binary vs. decay), and See
also. Rename the example heading to "Accessibility across a real county".

- [ ] **Step 5: Commit**

```bash
git add docsite/packages/sdc-catchment/articles
git commit -m "docs(catchment): real county accessibility map in the introduction"
```

---

## Task 3: Build, merge, verify live

- [ ] **Step 1: Strict build with the new images**

Run: `uv run --group docs mkdocs build --strict 2>&1 | grep -E "WARNING|ERROR|Aborted|Documentation built"`
Expected: `Documentation built`, no warnings. Confirm the PNGs copied into the build:

```bash
ls site/packages/sdc-redistribute/articles/img/ site/packages/sdc-catchment/articles/img/
```

Expected: the two PNG files present.

- [ ] **Step 2: Finish the development branch**

Use **superpowers:finishing-a-development-branch** to merge `feat/intro-maps` to
`main` (verify strict build on the merged result) and push. This redeploys the
docs site.

- [ ] **Step 3: Verify the images render live (after deploy)**

```bash
base="https://dads2busy.github.io/Social-Data-Commons/packages"
for u in \
  "sdc-redistribute/articles/introduction/img/redistribute-tract-to-bg.png" \
  "sdc-catchment/articles/introduction/img/catchment-county-access.png"; do
  echo -n "$u -> "; curl -s -o /dev/null -w "HTTP %{http_code}\n" "$base/$u"
done
```

Expected: `HTTP 200` for both image URLs. Also confirm the two article pages
return 200 and contain `<img`.

---

## Self-Review

- **Spec coverage:** real-geography assets from the committed NCR file → Task 1/2 §1. static matplotlib/geopandas PNGs, projected EPSG:32618 → figure scripts. redistribute before/after choropleth → Task 1 §2-4. catchment real-county access choropleth + clinic markers → Task 2 §2-4. examples rewritten + run-verified → Task 1/2 §3-4. docs-only/no release → no release task. strict build + live image verification → Task 3. All covered.
- **Placeholder scan:** none — extraction and figure scripts are complete and deterministic (tract/county chosen in code, fixed RNG seed); example outputs and the final catchment `scale`/`max_cost` are captured/tuned by explicit run steps, not invented.
- **Consistency:** import names (`sdc_redistribute`, `sdc_catchment`) and verified signatures (`redistribute_direct(..., source_geo=, target_geos=, count_cols=)`; `catchment_ratio(consumers, providers, cost, weight=, scale=, max_cost=)`; `euclidean_cost`) match across scripts and articles. Asset paths (`articles/data/*.geojson`), figure-script paths (`articles/figures/*.py`), and image paths (`articles/img/*.png`) are consistent between creation, the embed markdown (`img/<file>.png`, relative to the article), and the live-URL checks. Projected CRS EPSG:32618 used in both figure scripts.
