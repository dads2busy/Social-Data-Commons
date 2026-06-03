# census10to20 Introduction Map — Implementation Plan (revised: area-level)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real before/after boundary-change map to the sdc-census10to20 introduction (a small county's tract populations re-expressed from 2010 onto 2020 tract boundaries).

**Architecture:** Extract one small VA county's 2010 + 2020 tracts (county 51027, Buchanan — validated total-conserving) from the committed VA tract GeoJSONs; assign synthetic populations; run `convert_2010_to_2020_bounds` on the full county set; render a two-panel, shared-scale choropleth PNG; add a "Visualizing a boundary change" section. Docs-only.

**Tech Stack:** geopandas, matplotlib (dev group), sdc-census10to20 (network crosswalk fetch), MkDocs.

**Spec:** `docs/specs/2026-06-03-census10to20-intro-map-design.md` (revised area-level)

**Branch:** `feat/census10to20-intro-map` (already created). Note: an earlier run wrote single-tract assets under `articles/data/`; this plan overwrites them.

**Run from repo root.** Network required (crosswalk fetched from census.gov); committed PNG renders offline.

**Verified semantics:** `convert_2010_to_2020_bounds` is NOT count-conserving for a single tract; on a **full** county set it is ≈total-conserving (validated for 51027: input 22,925 → output 22,925). Returns columns `geoid` (2020) + value.

---

## File Structure

**Create/overwrite:**
- `docsite/packages/sdc-census10to20/articles/data/tracts_2010.geojson`
- `docsite/packages/sdc-census10to20/articles/data/tracts_2020.geojson`
- `docsite/packages/sdc-census10to20/articles/figures/census10to20_map.py`
- `docsite/packages/sdc-census10to20/articles/img/census10to20-boundary-change.png`

**Remove (leftover from the scrapped single-tract attempt, if present):**
- `docsite/packages/sdc-census10to20/articles/data/tract_2010.geojson` (singular)

**Modify:**
- `docsite/packages/sdc-census10to20/articles/introduction.md`

---

## Task 1: Extract the county's 2010 + 2020 tracts

- [ ] **Step 1: Extract county 51027 tracts; remove the stale singular asset**

```bash
mkdir -p docsite/packages/sdc-census10to20/articles/data
rm -f docsite/packages/sdc-census10to20/articles/data/tract_2010.geojson
uv run --group dev python - <<'PY'
import pathlib
import geopandas as gpd
CTY = "51027"  # Buchanan County, VA — validated total-conserving full-set conversion
t2010 = gpd.read_file("education/docs/maps/tract_2018.geojson"); t2010["GEOID"] = t2010["GEOID"].astype(str)
t2020 = gpd.read_file("education/docs/maps/tract_2020.geojson"); t2020["GEOID"] = t2020["GEOID"].astype(str)
c10 = t2010[t2010["GEOID"].str[:5] == CTY][["GEOID", "geometry"]].rename(columns={"GEOID": "geoid"}).sort_values("geoid").reset_index(drop=True)
c20 = t2020[t2020["GEOID"].str[:5] == CTY][["GEOID", "geometry"]].rename(columns={"GEOID": "geoid"}).sort_values("geoid").reset_index(drop=True)
assert len(c10) >= 3 and len(c20) >= 3, (len(c10), len(c20))
d = pathlib.Path("docsite/packages/sdc-census10to20/articles/data")
c10.to_file(d / "tracts_2010.geojson", driver="GeoJSON")
c20.to_file(d / "tracts_2020.geojson", driver="GeoJSON")
print("county", CTY, "2010 tracts:", len(c10), "2020 tracts:", len(c20))
PY
```

Expected: `county 51027 2010 tracts: 7 2020 tracts: 7` (or similar), both assets written.

---

## Task 2: Figure script + article section

- [ ] **Step 1: Write `docsite/packages/sdc-census10to20/articles/figures/census10to20_map.py`**

```python
"""Render the census10to20 introduction map (county population, 2010 vs 2020 boundaries)."""
import pathlib

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt

from sdc_census10to20 import convert_2010_to_2020_bounds

HERE = pathlib.Path(__file__).resolve().parent
data = HERE.parent / "data"
img = HERE.parent / "img" / "census10to20-boundary-change.png"
img.parent.mkdir(parents=True, exist_ok=True)

t10 = gpd.read_file(data / "tracts_2010.geojson"); t10["geoid"] = t10["geoid"].astype(str)
t20 = gpd.read_file(data / "tracts_2020.geojson"); t20["geoid"] = t20["geoid"].astype(str)
t10 = t10.sort_values("geoid").reset_index(drop=True)

# Synthetic 2010 populations (fixed seed for reproducibility).
rng = np.random.default_rng(0)
t10["pop"] = rng.integers(800, 5000, len(t10)).astype(float)

inp = pd.DataFrame({"geoid": t10["geoid"], "value": t10["pop"]})
out = convert_2010_to_2020_bounds(inp, state_fips="51")
t20["pop"] = t20["geoid"].map(out.set_index("geoid")["value"])

a = t10.to_crs(32618)
b = t20.to_crs(32618)
vmax = float(max(a["pop"].max(), np.nanmax(b["pop"].values)))
norm = mpl.colors.Normalize(vmin=0, vmax=vmax)

fig, ax = plt.subplots(1, 2, figsize=(12, 6))
a.plot(ax=ax[0], column="pop", cmap="Oranges", norm=norm, edgecolor="black")
ax[0].set_title("2010 tract boundaries"); ax[0].axis("off")
b.plot(ax=ax[1], column="pop", cmap="Oranges", norm=norm, edgecolor="black",
       missing_kwds={"color": "lightgrey", "label": "no in-sample source"})
ax[1].set_title("2020 tract boundaries"); ax[1].axis("off")
sm = mpl.cm.ScalarMappable(cmap="Oranges", norm=norm); sm.set_array([])
fig.colorbar(sm, ax=ax, fraction=0.025, pad=0.02, label="population")
fig.suptitle("Buchanan County, VA — population on 2010 vs 2020 tract boundaries", y=0.98)
fig.savefig(img, dpi=130, bbox_inches="tight")
print("wrote", img)
print("input total:", round(float(inp["value"].sum()), 1))
print("2020 in-county total:", round(float(np.nansum(t20["pop"].values)), 1))
print("2020 tracts with no in-sample value:", int(t20["pop"].isna().sum()))
print(out.head().to_string(index=False))
```

- [ ] **Step 2: Run the figure script; capture output + view the image**

Run: `uv run --group dev python docsite/packages/sdc-census10to20/articles/figures/census10to20_map.py`
Expected: `wrote ...png`; an `input total` and `2020 in-county total` that are
**close** (within ~10–15%); few/no "no in-sample value" tracts. **Record the
totals + `out.head()`.** Open the PNG: two side-by-side county choropleths
(orange), same color scale, visibly different internal tract boundaries.

**Decision gate:** if the two totals diverge wildly (>25%) or many 2020 tracts are
grey (no in-sample value), fall back to county `51005`: redo Task 1 Step 1 with
`CTY = "51005"`, then re-run this step. (51005 was also validated total-conserving.)

- [ ] **Step 3: Add the "Visualizing a boundary change" section to the article**

In `docsite/packages/sdc-census10to20/articles/introduction.md`, insert before
`## See also`, using the **captured numbers** from Step 2:

```markdown
## Visualizing a boundary change

`convert_2010_to_2020_bounds` re-expresses a complete 2010-boundary dataset on
2020 tract boundaries (area-weighted for tracts that were redrawn). Here every
2010 tract in Buchanan County, VA gets a synthetic population, and we convert the
whole county at once. The tract geometries ship with this page.

​```python
import geopandas as gpd
import numpy as np
import pandas as pd
from sdc_census10to20 import convert_2010_to_2020_bounds

tracts_2010 = gpd.read_file("tracts_2010.geojson").sort_values("geoid").reset_index(drop=True)

# Synthetic 2010 populations (one row per 2010 tract).
rng = np.random.default_rng(0)
data = pd.DataFrame({"geoid": tracts_2010["geoid"], "value": rng.integers(800, 5000, len(tracts_2010)).astype(float)})

# Convert the whole county onto 2020 boundaries (fetches the Census crosswalk).
out = convert_2010_to_2020_bounds(data, state_fips="51")
print("2010 total:", data["value"].sum(), " 2020 total:", round(out["value"].sum(), 1))
print(out.head().to_string(index=False))
​```

​```text
<captured totals + out.head() from Step 2>
​```

![Buchanan County population shown on 2010 tract boundaries vs 2020 tract boundaries](img/census10to20-boundary-change.png)

*The same population, re-expressed on the redrawn 2020 tracts. Because the whole
county is converted together, the total is preserved (area-weighting only moves
people between tracts whose boundaries shifted).*

> `convert_2010_to_2020_bounds` downloads the Census 2010↔2020 relationship file,
> so this example needs network access.
```

Replace `<captured totals + out.head() from Step 2>` with the actual printed
output. If Step 2 showed meaningful leakage (totals not close), soften the
caption to "the total is approximately preserved" and keep the wording honest.

- [ ] **Step 4: Commit**

```bash
git add docsite/packages/sdc-census10to20/articles
git commit -m "docs(census10to20): real county 2010->2020 boundary-change map in the introduction"
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

Use **superpowers:finishing-a-development-branch** to merge to `main` (verify
strict build on the merged result) and push. Redeploys the docs site.

- [ ] **Step 3: Verify the image renders live**

```bash
base="https://dads2busy.github.io/Social-Data-Commons/packages/sdc-census10to20/articles"
echo -n "img -> "; curl -s -o /dev/null -w "HTTP %{http_code}\n" "$base/img/census10to20-boundary-change.png"
echo -n "intro references it: "; curl -s "$base/introduction/" | grep -c "census10to20-boundary-change.png"
```

Expected: image `HTTP 200`; reference count `1`.

---

## Self-Review

- **Spec coverage (revised):** area-level full-county conversion (not single tract)
  → Tasks 1–2. county 51027 hardcoded with fallback 51005 → Task 1 + Task 2
  decision gate. real geometry assets → Task 1. two-panel shared-scale choropleth,
  EPSG:32618 → Task 2 §1. added section with captured output + totals + network
  note → Task 2 §3. strict build + merge + live verify → Task 3. docs-only → no
  release task. All covered.
- **Placeholder scan:** `<captured totals + out.head()>` is fill-from-run (verified
  output), the legitimate pattern; scripts complete and signature-correct.
- **Consistency:** `convert_2010_to_2020_bounds(..., state_fips="51")` and its
  `geoid`/value output used identically in the figure script and the article
  example; both use the same synthetic-population recipe (`np.random.default_rng(0)`,
  `integers(800, 5000)`) so the article's printed `out.head()` matches the figure
  run. Asset names `tracts_2010.geojson` / `tracts_2020.geojson` (plural),
  figure-script and image paths consistent with the live-URL check. EPSG:32618
  matches the other intro maps.
