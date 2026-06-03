# census10to20 Introduction Map — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real before/after boundary-change map to the sdc-census10to20 introduction (a 2010 tract's 1,000 people redistributed onto its 2020 successor tracts).

**Architecture:** Deterministically pick a real VA "moved" 2010 tract from the fetched crosswalk; extract it + its 2020 successors from the committed VA tract GeoJSONs into small assets; render a static two-panel PNG via a committed figure script that calls `convert_2010_to_2020_bounds`; add a "Visualizing a boundary change" section to the article. Docs-only.

**Tech Stack:** geopandas, matplotlib (dev group), sdc-census10to20 (network crosswalk fetch), MkDocs.

**Spec:** `docs/specs/2026-06-03-census10to20-intro-map-design.md`

**Branch:** `feat/census10to20-intro-map` (already created).

**Run all commands from the repo root.** Network is required (the crosswalk is fetched from census.gov); the committed PNG renders offline afterward.

**Verified API:** `convert_2010_to_2020_bounds(data, *, geoid_col="geoid", val_col="value", state_fips="51")` returns columns `geoid` (2020) + `value`; for `type_change=="moved"` each 2020 tract gets `value * area_part/area20`. Crosswalk columns: `geoid20, geoid10, area20, area10, area_part, type_change`. Tract GeoJSONs use column `GEOID`, CRS EPSG:4269.

---

## File Structure

**Create:**
- `docsite/packages/sdc-census10to20/articles/data/tract_2010.geojson`
- `docsite/packages/sdc-census10to20/articles/data/tracts_2020.geojson`
- `docsite/packages/sdc-census10to20/articles/figures/census10to20_map.py`
- `docsite/packages/sdc-census10to20/articles/img/census10to20-boundary-change.png`

**Modify:**
- `docsite/packages/sdc-census10to20/articles/introduction.md`

---

## Task 1: Extract the real 2010 tract + 2020 successors

- [ ] **Step 1: Run the deterministic extraction**

```bash
mkdir -p docsite/packages/sdc-census10to20/articles/data
uv run --group dev python - <<'PY'
import pathlib
import geopandas as gpd
from sdc_census10to20 import get_2010_2020_bound_changes

t2010 = gpd.read_file("education/docs/maps/tract_2018.geojson"); t2010["GEOID"] = t2010["GEOID"].astype(str)
t2020 = gpd.read_file("education/docs/maps/tract_2020.geojson"); t2020["GEOID"] = t2020["GEOID"].astype(str)
g2010, g2020 = set(t2010["GEOID"]), set(t2020["GEOID"])

cw = get_2010_2020_bound_changes(res="tract")
cw["geoid10"] = cw["geoid10"].astype(str); cw["geoid20"] = cw["geoid20"].astype(str)
moved = cw[cw["type_change"] == "moved"]
grp = moved.groupby("geoid10")["geoid20"].apply(lambda s: sorted(set(s)))

cand = [(g10, g20s) for g10, g20s in grp.items()
        if 2 <= len(g20s) <= 4 and g10 in g2010 and all(x in g2020 for x in g20s)]
cand.sort(key=lambda x: x[0])
g10, g20s = cand[0]
print("chosen 2010 tract:", g10, "-> 2020 successors:", g20s)

d = pathlib.Path("docsite/packages/sdc-census10to20/articles/data")
(t2010[t2010["GEOID"] == g10][["GEOID", "geometry"]]
 .rename(columns={"GEOID": "geoid"}).to_file(d / "tract_2010.geojson", driver="GeoJSON"))
(t2020[t2020["GEOID"].isin(g20s)][["GEOID", "geometry"]]
 .rename(columns={"GEOID": "geoid"}).to_file(d / "tracts_2020.geojson", driver="GeoJSON"))
print("wrote", d / "tract_2010.geojson", "and", d / "tracts_2020.geojson")
PY
```

Expected: prints `chosen 2010 tract: 51... -> 2020 successors: [...]` (2–4 geoids) and writes both assets. **Record the chosen `g10` and successors.** If `cand` is empty (no qualifying tract), widen the size bound to `2 <= len(g20s) <= 6` and re-run.

- [ ] **Step 2: Sanity-check the assets**

```bash
uv run --group dev python -c "
import geopandas as gpd
a=gpd.read_file('docsite/packages/sdc-census10to20/articles/data/tract_2010.geojson')
b=gpd.read_file('docsite/packages/sdc-census10to20/articles/data/tracts_2020.geojson')
print('2010 tract rows:', len(a), 'geoid:', list(a['geoid']))
print('2020 successor rows:', len(b), 'geoids:', list(b['geoid']))
"
```

Expected: 1 row in `tract_2010.geojson`; 2–4 rows in `tracts_2020.geojson`.

---

## Task 2: Figure script + article section

- [ ] **Step 1: Write `docsite/packages/sdc-census10to20/articles/figures/census10to20_map.py`**

```python
"""Render the census10to20 introduction map (2010 tract value -> 2020 tracts)."""
import pathlib

import geopandas as gpd
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sdc_census10to20 import convert_2010_to_2020_bounds

HERE = pathlib.Path(__file__).resolve().parent
data = HERE.parent / "data"
img = HERE.parent / "img" / "census10to20-boundary-change.png"
img.parent.mkdir(parents=True, exist_ok=True)

t2010 = gpd.read_file(data / "tract_2010.geojson"); t2010["geoid"] = t2010["geoid"].astype(str)
t2020 = gpd.read_file(data / "tracts_2020.geojson"); t2020["geoid"] = t2020["geoid"].astype(str)
g10 = t2010["geoid"].iloc[0]

inp = pd.DataFrame({"geoid": [g10], "value": [1000.0]})
out = convert_2010_to_2020_bounds(inp, state_fips="51")
t2020["value"] = t2020["geoid"].map(out.set_index("geoid")["value"])

a = t2010.to_crs(32618)
b = t2020.to_crs(32618)
fig, ax = plt.subplots(1, 2, figsize=(11, 5))
a.plot(ax=ax[0], color="#cbd5e1", edgecolor="black")
ax[0].set_title(f"2010 tract {g10}\n1,000 people"); ax[0].axis("off")
b.plot(ax=ax[1], column="value", cmap="Greens", edgecolor="black",
       legend=True, legend_kwds={"label": "people (2020 boundaries)"})
ax[1].set_title("Redistributed onto 2020 tracts\n(area-weighted, \"moved\")"); ax[1].axis("off")
fig.tight_layout()
fig.savefig(img, dpi=130, bbox_inches="tight")
print("wrote", img)
print(out.to_string(index=False))
print("sum:", round(float(out["value"].sum()), 2))
```

- [ ] **Step 2: Run the figure script; capture output + view the image**

Run: `uv run --group dev python docsite/packages/sdc-census10to20/articles/figures/census10to20_map.py`
Expected: `wrote .../census10to20-boundary-change.png`, then the `geoid`/`value`
rows (one per 2020 successor) and a `sum:`. **Record the printed table and sum.**
Open the PNG: left grey 2010 tract; right the 2020 successor tracts in green
shades. Confirm every successor has a value (no missing/grey polygon on the
right); if any is missing, note it in the prose rather than claiming a clean
split.

- [ ] **Step 3: Add the "Visualizing a boundary change" section to the article**

In `docsite/packages/sdc-census10to20/articles/introduction.md`, insert a new
section immediately before `## See also`. Use the **real `g10` and the captured
output** from Step 2:

```markdown
## Visualizing a boundary change

When a 2010 tract was redrawn for 2020 (`type_change == "moved"`), its value is
split across the overlapping 2020 tracts in proportion to the shared area. Here a
real Virginia 2010 tract (`<g10>`) holding 1,000 people is mapped onto the 2020
tracts that replaced it. The geometries ship with this page.

​```python
import geopandas as gpd
import pandas as pd
from sdc_census10to20 import convert_2010_to_2020_bounds

tract_2010 = gpd.read_file("tract_2010.geojson")
g10 = str(tract_2010["geoid"].iloc[0])

# 1,000 people recorded on the 2010 tract boundary.
data = pd.DataFrame({"geoid": [g10], "value": [1000.0]})

# Redistribute onto 2020 boundaries (fetches the Census crosswalk).
out = convert_2010_to_2020_bounds(data, state_fips="51")
print(out.to_string(index=False))
​```

​```text
<captured output table from Step 2>
​```

![A 2010 census tract's population redistributed onto its 2020 successor tracts](img/census10to20-boundary-change.png)

*The 2010-boundary value is divided among the 2020 tracts that replaced it, each
receiving a share proportional to the area they share with the original tract.*

> `convert_2010_to_2020_bounds` downloads the Census 2010↔2020 relationship file,
> so this example needs network access.
```

Replace `<g10>` with the real GEOID and `<captured output table from Step 2>`
with the actual printed `geoid`/`value` rows. If the captured `sum:` is close to
1,000, you may add a sentence noting the shares sum to about that; if not, keep
the area-share wording above (do not assert a clean 1,000 partition).

- [ ] **Step 4: Commit**

```bash
git add docsite/packages/sdc-census10to20/articles
git commit -m "docs(census10to20): real 2010->2020 boundary-change map in the introduction"
```

---

## Task 3: Build, merge, verify live

- [ ] **Step 1: Strict build with the new image**

Run: `uv run --group docs mkdocs build --strict 2>&1 | grep -E "WARNING|ERROR|Aborted|Documentation built"`
Expected: `Documentation built`, no warnings.

```bash
ls site/packages/sdc-census10to20/articles/img/
```

Expected: `census10to20-boundary-change.png` present.

- [ ] **Step 2: Finish the development branch**

Use **superpowers:finishing-a-development-branch** to merge
`feat/census10to20-intro-map` to `main` (verify strict build on the merged
result) and push. This redeploys the docs site.

- [ ] **Step 3: Verify the image renders live (after deploy)**

```bash
base="https://dads2busy.github.io/Social-Data-Commons/packages/sdc-census10to20/articles"
echo -n "img -> "; curl -s -o /dev/null -w "HTTP %{http_code}\n" "$base/img/census10to20-boundary-change.png"
echo -n "intro page references it: "; curl -s "$base/introduction/" | grep -c "census10to20-boundary-change.png"
```

Expected: image `HTTP 200`; page reference count `1`. (Note the live image path is
`.../articles/img/...` — MkDocs rewrites the in-page `img/...` link to `../img/...`
because of directory-style URLs.)

---

## Self-Review

- **Spec coverage:** deterministic moved-tract selection from the crosswalk +
  presence in both committed geometry files → Task 1. real geometry assets →
  Task 1. figure script calling `convert_2010_to_2020_bounds`, two-panel PNG,
  EPSG:32618 → Task 2 §1-2. added "Visualizing a boundary change" section
  (additive; existing standardize_all content kept) with captured output + map +
  network note → Task 2 §3. strict build + merge + live image verification →
  Task 3. docs-only/no release → no release task. All covered.
- **Placeholder scan:** the article-section template contains `<g10>` and
  `<captured output table>` — these are explicitly filled from the Task 2 run
  (captured, not invented); flagged as fill-from-run, the legitimate pattern for
  verified output. Scripts are complete and signature-correct.
- **Consistency:** import name `sdc_census10to20`, function
  `convert_2010_to_2020_bounds(..., state_fips="51")` and its `geoid`/`value`
  output columns match across the extraction, figure script, and article example.
  Asset paths (`articles/data/tract_2010.geojson`, `tracts_2020.geojson`),
  figure-script path, and image path (`articles/img/census10to20-boundary-change.png`,
  embedded as `img/...`) are consistent with the live-URL check. EPSG:32618 used
  for plotting, matching the other two intro maps.
