# Fix convert_2010_to_2020_bounds to Conserve Counts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `convert_2010_to_2020_bounds` conserve counts (source-area weighting `area_part/area10`), with tests, docs, a `v0.1.2` release, and the census10to20 intro map redone on a county whose tracts changed.

**Architecture:** Replace the `same`/`split`/`moved` branching in `convert` with one source-area-weighted sum. TDD: rewrite the tests that encode the bug + add conservation tests, then fix. Keep the official Census crosswalk as the weight source (not delegating to `redistribute`). Then redo the intro map on county 51121.

**Tech Stack:** pandas, pytest, sdc-census10to20, geopandas/matplotlib (map), hatch-vcs release.

**Spec:** `docs/specs/2026-06-03-census10to20-count-conservation-fix-design.md`

**Branch:** `fix/census10to20-count-conservation` (already created).

**Run from repo root.** The unit tests are offline (synthetic crosswalk via monkeypatch); the map figure + real-data check fetch the Census crosswalk.

**Verified fixture** (`test_convert.py` `fake_crosswalk`): same=`...001`(src `...010`); split children `...002`(area20 600, area_part 600)/`...003`(area20 400, area_part 400) of src `...020`; moved `...004`/`...005`(area20 600, area_part 400) of src `...030`; all `area10=1000`.

---

## File Structure

**Modify:**
- `packages/sdc-census10to20/tests/test_convert.py` — rewrite 2 tests, add 2 conservation tests
- `packages/sdc-census10to20/src/sdc_census10to20/convert.py` — the fix + docstring
- `docsite/packages/sdc-census10to20/articles/introduction.md` — "What redistribute actually does" section + the boundary-change section (county 51121)
- `packages/sdc-census10to20/CHANGELOG.md` — `[0.1.2]`
- `docsite/packages/sdc-census10to20/articles/figures/census10to20_map.py` — county title
- `docsite/packages/sdc-census10to20/articles/data/tracts_2010.geojson`, `tracts_2020.geojson` — re-extract for 51121
- `docsite/packages/sdc-census10to20/articles/img/census10to20-boundary-change.png` — re-render

---

## Task 1: TDD — corrected + conservation tests (failing)

**Files:** `packages/sdc-census10to20/tests/test_convert.py`

- [ ] **Step 1: Rewrite the split test to expect conservation**

Replace `test_convert_distributes_split_values` with:

```python
def test_convert_distributes_split_values(monkeypatch, fake_crosswalk):
    """A split source tract splits its value among children by source-area share."""
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({"geoid": ["51001000020"], "value": [500.0]})
    out = convert.convert_2010_to_2020_bounds(data)

    vals = out.set_index("geoid")["value"]
    # area_part/area10: child A = 500*600/1000 = 300; child B = 500*400/1000 = 200
    assert vals["51001000002"] == pytest.approx(300.0)
    assert vals["51001000003"] == pytest.approx(200.0)
    assert vals[["51001000002", "51001000003"]].sum() == pytest.approx(500.0)
```

- [ ] **Step 2: Rewrite the moved test to use area_part/area10**

Replace `test_convert_area_weights_moved_values` with:

```python
def test_convert_area_weights_moved_values(monkeypatch, fake_crosswalk):
    """Moved relationships scale by area_part / area10 (source-area share)."""
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: fake_crosswalk)

    data = pd.DataFrame({"geoid": ["51001000030"], "value": [1200.0]})
    out = convert.convert_2010_to_2020_bounds(data)

    # Each moved row: area_part=400, area10=1000 -> 1200 * 0.4 = 480
    moved = out[out["geoid"].isin(["51001000004", "51001000005"])]
    assert moved["value"].tolist() == pytest.approx([480.0, 480.0])
```

- [ ] **Step 3: Add a total-conservation test (complete tiling)**

Append:

```python
def test_convert_conserves_total_over_complete_crosswalk(monkeypatch):
    """When a source's overlaps tile it (sum area_part == area10), the total is preserved."""
    crosswalk = pd.DataFrame({
        "geoid20":    ["51001000101", "51001000102"],
        "geoid10":    ["51001000100", "51001000100"],
        "area10":     [1000, 1000],
        "area20":     [600, 400],
        "area_part":  [600, 400],   # sums to area10 -> fully tiled
        "type_change": ["split", "split"],
    })
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: crosswalk)

    data = pd.DataFrame({"geoid": ["51001000100"], "value": [1000.0]})
    out = convert.convert_2010_to_2020_bounds(data)
    assert out["value"].sum() == pytest.approx(1000.0)
```

- [ ] **Step 4: Add a county-level conservation test (splits + a merge)**

Append:

```python
def test_convert_conserves_county_total(monkeypatch):
    """A county's total is unchanged by reprojection (county boundary fixed).

    Two 2010 sources fully tile into 2020 tracts within the same county,
    including a 2020 tract (M) fed by both sources (a merge).
    """
    crosswalk = pd.DataFrame({
        "geoid20":    ["51999000A", "51999000M", "51999000M", "51999000D"],
        "geoid10":    ["51999000S1", "51999000S1", "51999000S2", "51999000S2"],
        "area10":     [1000, 1000, 1000, 1000],
        "area20":     [600, 1000, 1000, 800],
        "area_part":  [600, 400, 600, 400],  # S1: 600+400=1000; S2: 600+400=1000
        "type_change": ["split", "moved", "moved", "split"],
    })
    monkeypatch.setattr(convert, "create_crosswalk", lambda *a, **k: crosswalk)

    data = pd.DataFrame({"geoid": ["51999000S1", "51999000S2"], "value": [1000.0, 2000.0]})
    out = convert.convert_2010_to_2020_bounds(data)

    # county boundary fixed -> all output geoids are in county 51999, total preserved
    assert (out["geoid"].str[:5] == "51999").all()
    assert out["value"].sum() == pytest.approx(3000.0)
    vals = out.set_index("geoid")["value"]
    assert vals["51999000A"] == pytest.approx(600.0)   # 1000 * 600/1000
    assert vals["51999000M"] == pytest.approx(1600.0)  # 1000*400/1000 + 2000*600/1000
    assert vals["51999000D"] == pytest.approx(800.0)   # 2000 * 400/1000
```

- [ ] **Step 5: Run the tests; confirm the two rewritten + two new fail**

Run: `uv run --group dev pytest packages/sdc-census10to20/tests/test_convert.py -q`
Expected: FAIL — `distributes_split_values` (gets 500/500), `area_weights_moved_values` (gets 800), and the two conservation tests fail against the current `area20`/passthrough code. `test_convert_passes_same_values_through` and the validation tests still pass.

---

## Task 2: Apply the fix

**Files:** `packages/sdc-census10to20/src/sdc_census10to20/convert.py`

- [ ] **Step 1: Replace the redistribution core**

In `convert.py`, replace this block:

```python
    joined = crosswalk.merge(data, left_on="geoid10", right_on=geoid_col, how="left")

    same_bounds = (
        joined[joined["type_change"].isin(["same", "split"])]
        .groupby("geoid20", as_index=False)["value"]
        .first()
    )

    moved_bounds = joined[joined["type_change"] == "moved"].copy()
    moved_bounds["pct_overlap"] = moved_bounds["area_part"] / moved_bounds["area20"]
    moved_bounds["value"] = moved_bounds["value"] * moved_bounds["pct_overlap"]
    moved_bounds = moved_bounds.groupby("geoid20", as_index=False)["value"].sum()

    redistributed = pd.concat([same_bounds, moved_bounds], ignore_index=True)
    redistributed = redistributed.rename(columns={"geoid20": "geoid", "value": val_col})
    return redistributed
```

with:

```python
    joined = crosswalk.merge(data, left_on="geoid10", right_on=geoid_col, how="left")

    # Areal interpolation that conserves counts: each 2010 source distributes its
    # value to overlapping 2020 tracts by the fraction of the *source* area in the
    # overlap (area_part / area10). A source's overlaps tile it, so the fractions
    # sum to 1 and the source's full value is distributed. type_change does not
    # affect the math -- the geometry in area_part/area10 already encodes same vs
    # split vs moved.
    joined["value"] = joined["value"] * (joined["area_part"] / joined["area10"])
    redistributed = joined.groupby("geoid20", as_index=False)["value"].sum()
    redistributed = redistributed.rename(columns={"geoid20": "geoid", "value": val_col})
    return redistributed
```

- [ ] **Step 2: Fix the docstring**

Replace the docstring lines describing the old behavior:

```python
    """Redistribute a single year/measure of 2010-vintage values onto 2020 boundaries.

    The input frame must contain exactly one row per GEOID (one year, one
    measure). For "moved" boundaries the value is split by area-proportional
    weighting; "same" and "split" boundaries pass the value through unchanged.
```

with:

```python
    """Redistribute a single year/measure of 2010-vintage values onto 2020 boundaries.

    The input frame must contain exactly one row per GEOID (one year, one
    measure). Each 2010 source distributes its value to the overlapping 2020
    tracts by the fraction of the *source* area in each overlap
    (``area_part / area10``); a source's overlaps tile it, so the fractions sum to
    1 and the total is conserved (count-preserving areal interpolation, using the
    Census relationship file's land-area overlaps).
```

- [ ] **Step 3: Run the tests; all pass**

Run: `uv run --group dev pytest packages/sdc-census10to20/tests/ -q`
Expected: all pass (the four from Task 1 now pass; crosswalk/standardize tests unaffected).

- [ ] **Step 4: Commit**

```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/tests/test_convert.py
git commit -m "fix(census10to20): conserve counts in convert_2010_to_2020_bounds (area_part/area10)"
```

---

## Task 3: Update the intro article's mechanism section

**Files:** `docsite/packages/sdc-census10to20/articles/introduction.md`

- [ ] **Step 1: Rewrite the "What redistribute actually does" steps**

Replace:

```markdown
3. For `same` and `split` rows, passes the source value through to each target
   geoid.
4. For `moved` rows, multiplies the source value by `area_part / area20` and
   sums across all source contributors to each target geoid.

This area-weighted approach is suitable for counts and densities. For rates,
ratios, and indices, redistribute the numerator and denominator separately and
recompute the ratio at the 2020 level.
```

with:

```markdown
3. Distributes each 2010 tract's value to the overlapping 2020 tracts in
   proportion to the share of the **2010 source** area in each overlap
   (`area_part / area10`).

Because a source tract's overlaps tile it, the shares sum to 1 and the total is
**conserved** — a county's population is unchanged by reprojection onto 2020
boundaries (its county boundary didn't move). This is count-preserving areal
interpolation. For rates and indices, redistribute the numerator and denominator
separately and recompute the ratio at the 2020 level.
```

- [ ] **Step 2: Commit**

```bash
git add docsite/packages/sdc-census10to20/articles/introduction.md
git commit -m "docs(census10to20): correct the redistribution mechanism description"
```

---

## Task 4: Redo the intro map on a changed county (51121)

The current map uses county 51027 (Buchanan), whose tracts did NOT change. Switch
to **51121 (Montgomery County, VA)** — 16 tracts (2010) → 23 (2020) — so the
boundary change is visible, now on the fixed (conserving) `convert`.

**Files:** the map assets, figure script, and the article's boundary-change section.

- [ ] **Step 1: Re-extract county 51121 tracts**

```bash
uv run --group dev python - <<'PY'
import pathlib
import geopandas as gpd
CTY = "51121"  # Montgomery County, VA — tracts changed 2010->2020 (16 -> 23)
t2010 = gpd.read_file("education/docs/maps/tract_2018.geojson"); t2010["GEOID"] = t2010["GEOID"].astype(str)
t2020 = gpd.read_file("education/docs/maps/tract_2020.geojson"); t2020["GEOID"] = t2020["GEOID"].astype(str)
c10 = t2010[t2010["GEOID"].str[:5] == CTY][["GEOID","geometry"]].rename(columns={"GEOID":"geoid"}).sort_values("geoid").reset_index(drop=True)
c20 = t2020[t2020["GEOID"].str[:5] == CTY][["GEOID","geometry"]].rename(columns={"GEOID":"geoid"}).sort_values("geoid").reset_index(drop=True)
d = pathlib.Path("docsite/packages/sdc-census10to20/articles/data")
c10.to_file(d/"tracts_2010.geojson", driver="GeoJSON")
c20.to_file(d/"tracts_2020.geojson", driver="GeoJSON")
print("county", CTY, "2010 tracts:", len(c10), "2020 tracts:", len(c20))
PY
```

Expected: `county 51121 2010 tracts: 16 2020 tracts: 23`.

- [ ] **Step 2: Update the figure title in `census10to20_map.py`**

In `docsite/packages/sdc-census10to20/articles/figures/census10to20_map.py`, change the suptitle:

```python
fig.suptitle("Buchanan County, VA — population on 2010 vs 2020 tract boundaries", y=0.98)
```

to:

```python
fig.suptitle("Montgomery County, VA — population on 2010 vs 2020 tract boundaries", y=0.98)
```

- [ ] **Step 3: Re-run the figure; verify county conservation + visible change**

Run: `uv run --group dev python docsite/packages/sdc-census10to20/articles/figures/census10to20_map.py`
Expected: `wrote ...png`; **input total ≈ 2020 in-county total** (now conserved on the fixed convert — within ~rounding, not inflated); `2020 tracts with no in-sample value: 0`. **Record the totals + `out.head()`.** Open the PNG: left 16 tracts, right 23 tracts — visibly different internal boundaries, same county outline, shared color scale.

- [ ] **Step 4: Rewrite the article's "Visualizing a boundary change" section**

In `docsite/packages/sdc-census10to20/articles/introduction.md`, update that section to Montgomery County, using the **captured numbers** from Step 3. Change "Buchanan County, VA" → "Montgomery County, VA" in the prose, the code comment, and the example output block, and update the input/output totals and `out.head()` to the captured values. Keep the network-access note. The caption should state the 2010 population is **redistributed** onto the 2020 tracts and the county total is **preserved** (now true on the fixed function).

(If the captured 2020 in-county total differs from the input by more than rounding — it shouldn't, since the county boundary is fixed — keep the wording "approximately preserved" and note it.)

- [ ] **Step 5: Commit**

```bash
git add docsite/packages/sdc-census10to20/articles
git commit -m "docs(census10to20): redo boundary-change map on Montgomery County (changed tracts) + fixed convert"
```

---

## Task 5: Changelog

**Files:** `packages/sdc-census10to20/CHANGELOG.md`

- [ ] **Step 1: Add the 0.1.2 entry**

Insert above `## [0.1.1] - 2026-06-03`:

```markdown
## [0.1.2] - 2026-06-03

### Fixed
- `convert_2010_to_2020_bounds` now conserves counts. It weights each overlap by
  the 2010 source-area share (`area_part / area10`); previously "moved" tracts
  used `area_part / area20` and "same"/"split" tracts passed values through
  unchanged, so split tracts replicated their value and totals inflated (a 1,000-
  person tract that split became ~2,000). **Re-run any pipeline that converted
  counts through `convert_2010_to_2020_bounds` or `standardize_all`.**

```

- [ ] **Step 2: Commit**

```bash
git add packages/sdc-census10to20/CHANGELOG.md
git commit -m "docs(census10to20): changelog 0.1.2 (count-conservation fix)"
```

---

## Task 6: Finish, release v0.1.2, verify

- [ ] **Step 1: Full test suite + strict docs build on the branch**

```bash
uv run --group dev pytest packages/sdc-census10to20/tests/ -q
uv run --group docs mkdocs build --strict 2>&1 | grep -E "WARNING|ERROR|Documentation built"
```

Expected: all tests pass; docs build clean.

- [ ] **Step 2: Finish the development branch**

Use **superpowers:finishing-a-development-branch** to merge `fix/census10to20-count-conservation` to `main` (verify tests + strict build on the merged result) and push.

- [ ] **Step 3: Cut the release**

```bash
git checkout main && git pull
git tag census10to20-v0.1.2
git push origin census10to20-v0.1.2
gh run watch "$(gh run list --workflow=publish-census10to20.yml --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status --interval 15
```

Expected: green publish run.

- [ ] **Step 4: Verify the release + the live map**

```bash
curl -s -o /dev/null -w "pypi 0.1.2 -> HTTP %{http_code}\n" https://pypi.org/pypi/sdc-census10to20/0.1.2/json
cd /tmp && uv run --no-project --refresh-package sdc-census10to20 --with sdc-census10to20 \
  python -c "import sdc_census10to20 as m; print(m.__version__)"
cd /Users/ads7fg/git/social-data-commons
echo -n "map img -> "; curl -s -o /dev/null -w "HTTP %{http_code}\n" https://dads2busy.github.io/Social-Data-Commons/packages/sdc-census10to20/articles/img/census10to20-boundary-change.png
```

Expected: PyPI `HTTP 200`, version `0.1.2`, map image `HTTP 200`.

- [ ] **Step 5: Real-data county-conservation sanity check (records the guarantee)**

```bash
uv run --no-project --refresh-package sdc-census10to20 --with sdc-census10to20 --with geopandas --with pandas python - <<'PY'
import geopandas as gpd, pandas as pd, numpy as np
from sdc_census10to20 import convert_2010_to_2020_bounds
t10 = gpd.read_file("education/docs/maps/tract_2018.geojson"); t10["G"]=t10["GEOID"].astype(str)
c = t10[t10["G"].str[:5]=="51121"]
rng = np.random.default_rng(0)
data = pd.DataFrame({"geoid": c["G"].values, "value": rng.integers(800,5000,len(c)).astype(float)})
out = convert_2010_to_2020_bounds(data, state_fips="51")
incty = out[out["geoid"].str[:5]=="51121"]["value"].sum()
print("input total:", round(data['value'].sum(),1), " 2020 county total:", round(float(incty),1))
PY
```

Expected: the two totals match (within rounding) — confirming the released `0.1.2`
conserves a county's population across the 2010→2020 reprojection.

---

## Self-Review

- **Spec coverage:** unified `area_part/area10` fix → Task 2. rewrite buggy split/moved
  tests + add complete-crosswalk and county-level conservation tests → Task 1.
  docstring → Task 2 §2. article mechanism section → Task 3. patch release `v0.1.2`
  + CHANGELOG (with re-run warning) → Tasks 5–6. resume map on a changed county
  (51121) on the fixed convert, county-conservation verified → Task 4 + Task 6 §4–5.
  "keep crosswalk, don't delegate" → no redistribute changes anywhere. All covered.
- **Placeholder scan:** none — fix code, test code, docstring, article text, and
  changelog are concrete; the map's captured numbers (Task 4 §4) are fill-from-run
  (verified output), the legitimate pattern. TDD order (failing tests in Task 1,
  fix in Task 2) is explicit.
- **Consistency:** the fix formula `value * area_part/area10` matches the test
  expectations (split 500→300/200, moved 1200→480, conservation fixtures sum to
  input) and the article/docstring wording. County `51121` used consistently in
  Task 4 extraction, figure title, article, and the Task 6 §5 real-data check.
  Tag `census10to20-v0.1.2` matches the existing publish workflow's `census10to20-v*`
  trigger. No `redistribute`/`sdc-core` changes (crosswalk-based fix, per the
  decision).