# Documentation Articles for the Python Packages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an article template plus Introduction (+ one deeper article for redistribute & catchment) to the three published packages, enrich their READMEs, wire everything into the docs site, and patch-release `v0.1.1`.

**Architecture:** Articles are Markdown under `docsite/packages/<pkg>/articles/`, examples authored against the real Python API and **verified by running them** (real output pasted in). READMEs are brought to Introduction level. Nav gains an `Articles` group per package. Three patch releases via existing Trusted Publishing.

**Tech Stack:** MkDocs + mkdocstrings, geopandas/shapely (redistribute examples), numpy/scipy/pandas (catchment examples), hatch-vcs tag releases.

**Spec:** `docs/specs/2026-06-03-package-articles-design.md`

**Branch:** `feat/package-articles` (already created).

**Run all commands from the repo root** `/Users/ads7fg/git/social-data-commons`.

**Authoring rule for every example:** write the example as a standalone script, run it with `uv run --group dev python <script>`, and paste the **actual** captured output into the article's output block. Never invent output. The example code below is written against the verified signatures (`redistribute_direct(source_df, source_geo, target_geos, count_cols, pct_specs=None, *, source_id="geoid", ...)`; `catchment_ratio(consumers, providers, cost, weight=None, scale=2.0, max_cost=None, ..., consumers_id="geoid", consumers_value="value", providers_id="geoid", providers_value="value")`; `euclidean_cost(consumers_xy, providers_xy)`).

---

## File Structure

**Create:**
- `docs/article-template.md` (internal authoring guide)
- `docsite/packages/sdc-redistribute/articles/introduction.md`
- `docsite/packages/sdc-redistribute/articles/method-comparison.md`
- `docsite/packages/sdc-catchment/articles/introduction.md`
- `docsite/packages/sdc-catchment/articles/case-study.md`

**Move:**
- `docsite/packages/sdc-census10to20/getting-started.md` → `docsite/packages/sdc-census10to20/articles/introduction.md`

**Modify:**
- `mkdocs.yml` (Articles nav groups, census10to20 link)
- `packages/sdc-{census10to20,redistribute,catchment}/README.md`
- `packages/sdc-{census10to20,redistribute,catchment}/CHANGELOG.md`
- `docsite/packages/sdc-census10to20/index.md` (fix getting-started link → articles/introduction.md)

---

## Task 1: Article template (authoring guide)

**Files:** Create `docs/article-template.md`

- [ ] **Step 1: Write `docs/article-template.md`**

```markdown
# Article template & authoring guide

Standard structure for package documentation articles
(`docsite/packages/<pkg>/articles/<name>.md`). Python is the canonical version;
examples mirror the R-vignette scenarios as closely as the Python API allows.

## Rules

- Every code block must be **run and verified**; paste the real captured output.
- Use small inline/synthetic data — articles must be self-contained (no shipped
  or downloaded data files). Redistribute examples generate tiny GeoJSON at
  runtime via shapely.
- Read the actual function signature before writing an example; do not assume
  parameter names from the R package.

## Skeleton

​```markdown
# <Article Title>

<One paragraph: what this shows and why it matters.>

## Setup

​```bash
pip install <pkg>
​```

​```python
import ...
​```

## <Worked example heading>

​```python
# runnable example
​```

​```text
# real captured output
​```

<short explanation of the result>

## See also

- [<Reference page>](../reference/<page>.md)
- [<Sibling article>](<name>.md)
​```

## Article types

- **Introduction** — the core workflow, one end-to-end runnable example.
- **Method comparison** — run alternative methods on the same input; show results
  side by side; add a "when to use which".
- **Case study** — a realistic (synthetic) scenario, the computation, and an
  interpretation.

## README standard (PyPI long_description)

Each package README mirrors the Introduction: a tight "what & why", a single
runnable Quickstart (the smallest Introduction example), and a **Documentation**
section linking to the articles + reference on the umbrella site.
```

- [ ] **Step 2: Commit**

```bash
git add docs/article-template.md
git commit -m "docs: add article template + authoring guide"
```

---

## Task 2: census10to20 — Introduction (align existing)

**Files:** move `getting-started.md`; modify `mkdocs.yml`, `index.md`.

- [ ] **Step 1: Move the existing article into the articles dir**

```bash
mkdir -p docsite/packages/sdc-census10to20/articles
git mv docsite/packages/sdc-census10to20/getting-started.md docsite/packages/sdc-census10to20/articles/introduction.md
```

- [ ] **Step 2: Retitle and add a "See also" to `articles/introduction.md`**

Change the first heading from `# Getting Started` to `# Introduction`, and append at the end:

```markdown

## See also

- [standardize_all reference](../reference/standardize_all.md)
- [convert_2010_to_2020_bounds reference](../reference/convert_2010_to_2020_bounds.md)
```

- [ ] **Step 3: Fix the overview's link to the moved article**

In `docsite/packages/sdc-census10to20/index.md`, the overview links to
`getting-started.md`. Update it:

```bash
sed -i '' 's#(getting-started.md)#(articles/introduction.md)#g' docsite/packages/sdc-census10to20/index.md
grep -n "getting-started" docsite/packages/sdc-census10to20/index.md || echo "no stale link"
```

Expected: `no stale link`.

- [ ] **Step 4: Update the census10to20 nav block in `mkdocs.yml`**

Replace the existing census10to20 block:

```yaml
  - sdc-census10to20:
      - Overview: packages/sdc-census10to20/index.md
      - Getting Started: packages/sdc-census10to20/getting-started.md
      - Reference:
          - standardize_all: packages/sdc-census10to20/reference/standardize_all.md
          - convert_2010_to_2020_bounds: packages/sdc-census10to20/reference/convert_2010_to_2020_bounds.md
          - create_crosswalk: packages/sdc-census10to20/reference/create_crosswalk.md
          - get_2010_2020_bound_changes: packages/sdc-census10to20/reference/get_2010_2020_bound_changes.md
```

with:

```yaml
  - sdc-census10to20:
      - Overview: packages/sdc-census10to20/index.md
      - Articles:
          - Introduction: packages/sdc-census10to20/articles/introduction.md
      - Reference:
          - standardize_all: packages/sdc-census10to20/reference/standardize_all.md
          - convert_2010_to_2020_bounds: packages/sdc-census10to20/reference/convert_2010_to_2020_bounds.md
          - create_crosswalk: packages/sdc-census10to20/reference/create_crosswalk.md
          - get_2010_2020_bound_changes: packages/sdc-census10to20/reference/get_2010_2020_bound_changes.md
```

- [ ] **Step 5: Strict build + commit**

```bash
uv run --group docs mkdocs build --strict 2>&1 | grep -E "WARNING|ERROR|Documentation built"
git add -A
git commit -m "docs(census10to20): introduction article under Articles nav group"
```

Expected: `Documentation built` with no warnings.

---

## Task 3: redistribute — Introduction + Method Comparison

**Files:** create the two articles. Examples generate tiny GeoJSON at runtime.

- [ ] **Step 1: Write & run the Introduction example script**

Create `/tmp/redist_intro.py`:

```python
import tempfile, pathlib
import geopandas as gpd
import pandas as pd
from shapely.geometry import box
from sdc_redistribute import redistribute_direct

tmp = pathlib.Path(tempfile.mkdtemp())

# One source tract (T1) covering a 2x2 square.
source = gpd.GeoDataFrame({"geoid": ["T1"]}, geometry=[box(0, 0, 2, 2)], crs="EPSG:4326")
src_path = tmp / "tract.geojson"
source.to_file(src_path, driver="GeoJSON")

# Two block groups splitting the tract into left/right halves.
bg = gpd.GeoDataFrame(
    {"geoid": ["BG1", "BG2"]},
    geometry=[box(0, 0, 1, 2), box(1, 0, 2, 2)],
    crs="EPSG:4326",
)
bg_path = tmp / "bg.geojson"
bg.to_file(bg_path, driver="GeoJSON")

# Long-format source data: 100 people in T1 in 2020.
source_df = pd.DataFrame(
    {"geoid": ["T1"], "year": [2020], "measure": ["pop"], "value": [100.0]}
)

out = redistribute_direct(
    source_df,
    source_geo=src_path,
    target_geos={"block_group": bg_path},
    count_cols=["pop"],
)
print(out.to_string(index=False))
```

Run: `uv run --group dev python /tmp/redist_intro.py`
Expected: a long-format frame with `pop_direct` ≈ 50 for each of BG1/BG2 (equal-area split). Capture the exact printed output.

- [ ] **Step 2: Write `docsite/packages/sdc-redistribute/articles/introduction.md`**

Use the template. Sections: a one-paragraph intro (redistribute moves count
measures from a source geography onto target geographies by areal interpolation —
the area-weighted analogue of the R intro's disaggregation example); **Setup**
(`pip install sdc-redistribute`, imports); **Redistributing a count** containing
the exact code from Step 1 and the **captured output**; a sentence explaining the
equal-area split gives ~50/50; **See also** linking
`../reference/redistribute.md` and `method-comparison.md`.

```bash
mkdir -p docsite/packages/sdc-redistribute/articles
```

- [ ] **Step 3: Write & run the Method-Comparison example script**

Create `/tmp/redist_methods.py`:

```python
import tempfile, pathlib
import geopandas as gpd
import pandas as pd
from shapely.geometry import box
from sdc_redistribute import redistribute_direct, redistribute_parcels

tmp = pathlib.Path(tempfile.mkdtemp())
source = gpd.GeoDataFrame({"geoid": ["T1"]}, geometry=[box(0, 0, 2, 2)], crs="EPSG:4326")
src_path = tmp / "tract.geojson"; source.to_file(src_path, driver="GeoJSON")
bg = gpd.GeoDataFrame(
    {"geoid": ["BG1", "BG2"]},
    geometry=[box(0, 0, 1, 2), box(1, 0, 2, 2)], crs="EPSG:4326",
)
bg_path = tmp / "bg.geojson"; bg.to_file(bg_path, driver="GeoJSON")
source_df = pd.DataFrame({"geoid": ["T1"], "year": [2020], "measure": ["pop"], "value": [100.0]})

# Parcels concentrated in the LEFT half (BG1): 4 parcels left, 1 right.
parcels = pd.DataFrame({"lon": [0.2, 0.4, 0.6, 0.8, 1.8], "lat": [1.0, 1.0, 1.0, 1.0, 1.0]})

direct = redistribute_direct(source_df, source_geo=src_path,
                             target_geos={"block_group": bg_path}, count_cols=["pop"])
parcel = redistribute_parcels(source_df, parcel_centroids=parcels, source_geo=src_path,
                              target_geos={"block_group": bg_path}, count_cols=["pop"])

cmp = (direct.rename(columns={"value": "direct"})[["geoid", "measure", "direct"]]
       .merge(parcel.rename(columns={"value": "parcels"})[["geoid", "measure", "parcels"]],
              on=["geoid", "measure"]))
print(cmp.to_string(index=False))
```

Run: `uv run --group dev python /tmp/redist_methods.py`
Expected: `pop_direct` splits ~50/50 by area, while `pop_parcels` puts ~80 in BG1 / ~20 in BG2 (weighted by parcel density). Capture the exact output. (If the printed `measure`/column names differ from the assumption, adjust the article's prose to match the real output.)

- [ ] **Step 4: Write `docsite/packages/sdc-redistribute/articles/method-comparison.md`**

Template sections: intro paragraph (area-weighting assumes population is spread
evenly across a tract; parcel-weighting uses where parcels actually are);
**Setup**; **Same input, two methods** with the Step-3 code + captured output;
a short table/paragraph contrasting the BG1/BG2 numbers; **When to use which**
(direct when you lack parcel data or population is roughly uniform; parcels when
settlement is uneven and parcel centroids are available); **See also**.

- [ ] **Step 5: Strict build + commit**

```bash
uv run --group docs mkdocs build 2>&1 | grep -E "WARNING|ERROR|Documentation built"
git add docsite/packages/sdc-redistribute/articles
git commit -m "docs(redistribute): introduction + method-comparison articles"
```

(Plain build here — nav entries are added in Task 6; `--strict` would warn about
not-in-nav pages until then.)

---

## Task 4: catchment — Introduction + Case Study

**Files:** create the two articles. Pure inline numpy/pandas.

- [ ] **Step 1: Write & run the Introduction example script**

Create `/tmp/catch_intro.py`:

```python
import numpy as np
import pandas as pd
from sdc_catchment import catchment_ratio, euclidean_cost

# 3 consumers (demand, "value" = population) and 2 providers (supply, "value" = capacity).
consumers = pd.DataFrame({"geoid": ["c1", "c2", "c3"], "value": [100.0, 100.0, 100.0]})
providers = pd.DataFrame({"geoid": ["p1", "p2"], "value": [10.0, 10.0]})
consumers_xy = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
providers_xy = np.array([[0.0, 0.0], [2.0, 0.0]])
cost = euclidean_cost(consumers_xy, providers_xy)

# Binary catchment: everyone within max_cost=1.5 counts equally.
binary = catchment_ratio(consumers, providers, cost, max_cost=1.5)
# Distance-decay catchment: gaussian kernel.
decay = catchment_ratio(consumers, providers, cost, weight="gaussian", scale=1.0)

print("cost matrix:\n", cost)
print("\nbinary access:\n", binary.to_string())
print("\ngaussian-decay access:\n", decay.to_string())
```

Run: `uv run --group dev python /tmp/catch_intro.py`
Expected: an access score per consumer; the middle consumer (c2) has the highest
binary access (reaches both providers within 1.5), and decay smooths the scores
by distance. Capture exact output. (Confirm the returned `pd.Series` index = the
consumer ids; adjust prose if `return_type` changes the shape.)

- [ ] **Step 2: Write `docsite/packages/sdc-catchment/articles/introduction.md`**

Template sections: intro paragraph (floating catchment areas measure access of
demand points to supply within a travel-cost bound and/or decay — `catchment_ratio`
is the one function, varied by parameters, mirroring the R FCA intro); **Setup**;
**A tiny catchment** with the Step-1 code + captured output; explanation of binary
vs gaussian-decay scores; a note that `KERNELS` offers
`linear/gaussian/gravity/exponential/logistic/logarithmic`; **See also**
(`../reference/catchment.md`, `case-study.md`).

- [ ] **Step 3: Write & run the Case-Study example script**

Create `/tmp/catch_case.py`:

```python
import numpy as np
import pandas as pd
from sdc_catchment import catchment_ratio, euclidean_cost

# Synthetic county: 5 demand neighborhoods (population) and 3 clinics (capacity, beds).
demand = pd.DataFrame({
    "geoid": ["n1", "n2", "n3", "n4", "n5"],
    "value": [1200.0, 800.0, 1500.0, 600.0, 2000.0],
})
demand_xy = np.array([[0, 0], [3, 1], [6, 0], [1, 4], [5, 5]], dtype=float)
clinics = pd.DataFrame({"geoid": ["A", "B", "C"], "value": [20.0, 15.0, 30.0]})
clinics_xy = np.array([[1, 1], [5, 1], [4, 5]], dtype=float)

cost = euclidean_cost(demand_xy, clinics_xy)
# E2SFCA-style: gaussian decay within a 4-unit travel bound.
access = catchment_ratio(demand, clinics, cost, weight="gaussian", scale=2.0, max_cost=4.0)
result = demand.assign(access_per_1000=(access.values * 1000).round(3))
print(result.to_string(index=False))
```

Run: `uv run --group dev python /tmp/catch_case.py`
Expected: an `access_per_1000` (beds per 1000 people) score for each
neighborhood; remote/underserved neighborhoods score lower. Capture exact output.

- [ ] **Step 4: Write `docsite/packages/sdc-catchment/articles/case-study.md`**

Template sections: intro (a worked accessibility analysis for a small synthetic
county — clinics with bed capacity, neighborhoods with population); **Setup**;
**Computing accessibility** with the Step-3 code + captured output; **Interpreting
the result** (which neighborhoods are under-served and why — distance to capacity);
a note this is the same computation SDC health-access pipelines run at scale;
**See also**.

- [ ] **Step 5: Build + commit**

```bash
uv run --group docs mkdocs build 2>&1 | grep -E "WARNING|ERROR|Documentation built"
git add docsite/packages/sdc-catchment/articles
git commit -m "docs(catchment): introduction + case-study articles"
```

---

## Task 5: Enrich the three READMEs

**Files:** modify each package `README.md`.

- [ ] **Step 1: Enrich `packages/sdc-redistribute/README.md`**

Replace its body with: the existing "what & why" (kept), a **Quickstart** section
containing the *Introduction* example from Task 3 Step 1 (the smallest runnable
snippet) with its captured output, and a **Documentation** section:

```markdown
## Documentation

- [Introduction](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-redistribute/articles/introduction/)
- [Method comparison](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-redistribute/articles/method-comparison/)
- [API reference](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-redistribute/reference/redistribute/)
```

- [ ] **Step 2: Enrich `packages/sdc-catchment/README.md`**

Same pattern: keep "what & why", add a **Quickstart** with the catchment
Introduction snippet (Task 4 Step 1, trimmed to the binary + gaussian calls) +
captured output, and a **Documentation** section:

```markdown
## Documentation

- [Introduction to floating catchment areas](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-catchment/articles/introduction/)
- [Case study](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-catchment/articles/case-study/)
- [API reference](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-catchment/reference/catchment/)
```

- [ ] **Step 3: Enrich `packages/sdc-census10to20/README.md`**

Add a **Documentation** section (it already has install + a short description):

```markdown
## Documentation

- [Introduction](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-census10to20/articles/introduction/)
- [API reference](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-census10to20/reference/standardize_all/)
```

- [ ] **Step 4: Commit**

```bash
git add packages/*/README.md
git commit -m "docs: enrich package READMEs with quickstart + docs links"
```

---

## Task 6: Wire redistribute & catchment nav + strict build

**Files:** modify `mkdocs.yml`.

- [ ] **Step 1: Add Articles groups to the redistribute and catchment nav blocks**

Replace the redistribute block:

```yaml
  - sdc-redistribute:
      - Overview: packages/sdc-redistribute/index.md
      - Reference:
          - Redistribute: packages/sdc-redistribute/reference/redistribute.md
```

with:

```yaml
  - sdc-redistribute:
      - Overview: packages/sdc-redistribute/index.md
      - Articles:
          - Introduction: packages/sdc-redistribute/articles/introduction.md
          - Method comparison: packages/sdc-redistribute/articles/method-comparison.md
      - Reference:
          - Redistribute: packages/sdc-redistribute/reference/redistribute.md
```

Replace the catchment block:

```yaml
  - sdc-catchment:
      - Overview: packages/sdc-catchment/index.md
      - Reference:
          - Catchment: packages/sdc-catchment/reference/catchment.md
```

with:

```yaml
  - sdc-catchment:
      - Overview: packages/sdc-catchment/index.md
      - Articles:
          - Introduction to floating catchment areas: packages/sdc-catchment/articles/introduction.md
          - Case study: packages/sdc-catchment/articles/case-study.md
      - Reference:
          - Catchment: packages/sdc-catchment/reference/catchment.md
```

- [ ] **Step 2: Strict build (all articles now in nav)**

Run: `uv run --group docs mkdocs build --strict 2>&1 | grep -E "WARNING|ERROR|Aborted|Documentation built"`
Expected: `Documentation built`, no warnings.

- [ ] **Step 3: Commit**

```bash
git add mkdocs.yml
git commit -m "docs: add Articles nav groups for redistribute and catchment"
```

---

## Task 7: CHANGELOGs + merge + release

**Files:** modify the three CHANGELOGs.

- [ ] **Step 1: Add a 0.1.1 entry to each CHANGELOG**

Insert below the format header (above `## [0.1.0] ...`) in each of
`packages/sdc-{census10to20,redistribute,catchment}/CHANGELOG.md`:

```markdown
## [0.1.1] - 2026-06-03

### Added
- Documentation articles on the Social Data Commons site.

### Changed
- Enriched README with a runnable quickstart and documentation links.
```

- [ ] **Step 2: Commit**

```bash
git add packages/*/CHANGELOG.md
git commit -m "docs: changelog 0.1.1 (articles + enriched READMEs)"
```

- [ ] **Step 3: Finish the development branch**

Use **superpowers:finishing-a-development-branch** to merge `feat/package-articles`
to `main` (verify `mkdocs build --strict` + full pytest on the merged result) and
push. This redeploys the docs site (articles go live).

- [ ] **Step 4: Cut the three patch releases**

Trusted Publishing + the `pypi` environment already exist for all three, so no
manual setup. On `main`:

```bash
git checkout main && git pull
for pkg in census10to20 redistribute catchment; do
  git tag "${pkg}-v0.1.1"
  git push origin "${pkg}-v0.1.1"
done
```

- [ ] **Step 5: Watch the three publish runs**

```bash
for wf in publish-census10to20 publish-redistribute publish-catchment; do
  rid=$(gh run list --workflow=${wf}.yml --limit 1 --json databaseId -q '.[0].databaseId')
  echo "=== $wf (run $rid) ==="; gh run watch "$rid" --exit-status --interval 15 2>&1 | tail -3
done
```

Expected: all three green.

- [ ] **Step 6: Verify 0.1.1 live on PyPI**

```bash
for pkg in sdc-census10to20 sdc-redistribute sdc-catchment; do
  echo -n "$pkg 0.1.1 -> "
  curl -s -o /dev/null -w "HTTP %{http_code}\n" https://pypi.org/pypi/$pkg/0.1.1/json
done
```

Expected: `HTTP 200` for all three.

---

## Self-Review

- **Spec coverage:** template artifact → Task 1. census10to20 intro alignment →
  Task 2. redistribute intro+method-comparison → Task 3. catchment intro+case-study
  → Task 4. README enrichment → Task 5. nav Articles groups → Tasks 2/6. CHANGELOG
  0.1.1 + patch-release all three → Task 7. Runnable-verified examples → the
  per-example run steps in Tasks 3–4. All spec sections covered.
- **Placeholder scan:** none — example scripts are complete and signature-correct;
  outputs are captured by explicit run steps (not invented). Prose is specified by
  section with required content. No "TODO".
- **Consistency:** package import names (`sdc_redistribute`, `sdc_catchment`),
  function names and the verified signatures (`redistribute_direct`/`redistribute_parcels`
  args `source_geo`, `target_geos`, `count_cols`; `catchment_ratio`/`euclidean_cost`
  args, `weight="gaussian"`, `KERNELS`) match across scripts, READMEs, and articles.
  Article filenames (`introduction.md`, `method-comparison.md`, `case-study.md`)
  match the nav entries and README doc links. Tag prefixes (`census10to20-v`,
  `redistribute-v`, `catchment-v`) match the existing publish workflows.
- **Build-strictness note:** Tasks 3–4 use plain `mkdocs build` (articles not yet
  in nav); Task 6 adds nav then runs `--strict`. Intentional, called out in-task.
