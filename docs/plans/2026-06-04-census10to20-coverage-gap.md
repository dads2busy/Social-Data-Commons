# census10to20 Coverage-Gap Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize 7 datasets with pre-2020 2010-vintage tract/BG data onto 2020 boundaries (emit `_geo10`/`_geo20`), consistent with the 24 already-remediated datasets.

**Architecture:** One backward-compatible sdc-core change adds a configurable `vintage_cutoff_year` to `standardize_all` (threaded through `write_data`), generalizing the hardcoded `year < 2020` boundary. Each dataset then gets `geo_standardize` metadata (count vs replicate), its ingest `write_data` flipped to `census_standardize=True` with the right cutoff, then is regenerated and conservation-gated by a small net-new runner that reuses the existing `run_entrypoint` + `check_conservation` (the existing driver's `process_dataset` gate assumes a prior broken `_geo20` and does NOT fit net-new standardization, so it is not used here).

**Tech Stack:** Python 3.12, uv workspace, pandas, pytest, `sdc-census10to20`, `sdc-core`.

**Reference:** spec `docs/specs/2026-06-04-census10to20-coverage-gap-design.md`. Re-read `docs/pipeline-conversion-spec.md` before editing pipelines.

---

## File Structure

- `packages/sdc-census10to20/src/sdc_census10to20/convert.py` — add `vintage_cutoff_year` param to `standardize_all` (replaces two hardcoded `2020` literals at ~line 366 and ~line 376).
- `packages/sdc-core/src/sdc_core/io.py` — add `vintage_cutoff_year` param to `write_data`, forwarded to `standardize_all`.
- `packages/sdc-census10to20/tests/test_convert.py` — unit test for the cutoff.
- `tools/census10to20_remediation/add_geo_standardize.py` — NEW helper: inject `geo_standardize` blocks by name rule.
- `tools/census10to20_remediation/standardize_one.py` — NEW helper: regenerate one dataset (ingest via `run_entrypoint`, no auto-publish) and run the region-wide conservation gate.
- Per dataset (7): `data/distribution/measure_info.json` (+ `geo_standardize` blocks), `code/distribution/ingest.py` (load measure_info; flip `census_standardize`; pass `measure_info` + `vintage_cutoff_year`).

**Type rule (every dataset):** `measure_type = "count"` when the measure name ends with `_count` or `_cnt`, or is exactly `population`, `Minority_employment`, or `Nonminority_employment`; otherwise `"replicate"`. No `ratio` is used (SNAP `pct` has no published households denominator; Worker_diversity `*_perc` denominators are not cleanly recomputable — both intensive → replicate).

**Per-dataset cutoffs:** PLACES 2022; Rent `max(years)+1`; OB-GYN/Pediatric/PrimaryCare 2021; SNAP 2020 (default); Worker_diversity 2020 (default).

**`measure_info` loading idiom (used in every ingest wiring step):** add near the top of the module
```python
import json
from pathlib import Path
_MI = json.load(open(Path(__file__).resolve().parents[2] / "data/distribution/measure_info.json"))
```
`parents[2]` = topic dir from `<topic>/code/distribution/ingest.py`. Confirm the relative depth per file.

---

## Task 1: Add `vintage_cutoff_year` to `standardize_all` and `write_data`

**Files:** Modify `packages/sdc-census10to20/src/sdc_census10to20/convert.py:281,366,376`; `packages/sdc-core/src/sdc_core/io.py:77` + its `standardize_all(...)` call. Test: `packages/sdc-census10to20/tests/test_convert.py`.

- [ ] **Step 1: Write the failing test** — append to `packages/sdc-census10to20/tests/test_convert.py`:

```python
def test_vintage_cutoff_treats_2020_as_pre_cutoff(monkeypatch, synthetic_tract_relationship_csv):
    import pandas as pd
    from sdc_census10to20.convert import standardize_all
    monkeypatch.setattr(pd, "read_csv", lambda *a, **k: synthetic_tract_relationship_csv)
    df = pd.DataFrame({
        "geoid": ["51001000010"], "year": [2020], "measure": ["idx"],
        "value": [5.0], "moe": [pd.NA], "region_type": ["tract"],
    })
    mi = {"idx": {"geo_standardize": {"measure_type": "replicate"}}}
    out_default = standardize_all(df, measure_info=mi, state_fips="51")
    assert not out_default["measure"].str.endswith("_geo10").any()
    out_cut = standardize_all(df, measure_info=mi, vintage_cutoff_year=2021, state_fips="51")
    assert out_cut["measure"].str.endswith("_geo10").any()
    assert out_cut["measure"].str.endswith("_geo20").any()
```

- [ ] **Step 2: Run to verify it fails** — `uv run pytest "packages/sdc-census10to20/tests/test_convert.py::test_vintage_cutoff_treats_2020_as_pre_cutoff" -v`. Expected: FAIL, `unexpected keyword argument 'vintage_cutoff_year'`.

- [ ] **Step 3: Add the parameter to `standardize_all`** — in `convert.py`, add after `state_fips: str = "51",`:
```python
    vintage_cutoff_year: int = 2020,
```
Replace the suffix condition `row[year_col] < 2020` (in the `.apply` lambda, ~line 366) with `row[year_col] < vintage_cutoff_year`. Replace the loop gate `if yr < 2020:` (~line 376) with `if yr < vintage_cutoff_year:`.

- [ ] **Step 4: Thread through `write_data`** — in `packages/sdc-core/src/sdc_core/io.py`, add to the signature after `input_only_measures=None,`:
```python
    vintage_cutoff_year: int = 2020,
```
In the `census_standardize` branch where `standardize_all(...)` is called, add the argument `vintage_cutoff_year=vintage_cutoff_year,`.

- [ ] **Step 5: Run the suites** — `uv run pytest packages/sdc-census10to20 packages/sdc-core -q`. Expected: PASS (new test passes; existing tests unchanged — default `2020` preserves behavior).

- [ ] **Step 6: Commit**
```bash
git add packages/sdc-census10to20/src/sdc_census10to20/convert.py packages/sdc-census10to20/tests/test_convert.py packages/sdc-core/src/sdc_core/io.py
git commit -m "feat(census10to20): configurable vintage_cutoff_year in standardize_all (default 2020)"
```

---

## Task 2: Create the two helper scripts

**Files:** Create `tools/census10to20_remediation/add_geo_standardize.py`, `tools/census10to20_remediation/standardize_one.py`.

- [ ] **Step 1: Create `add_geo_standardize.py`**
```python
"""Add geo_standardize blocks to a dataset's measure_info.json by name rule.
Usage: python add_geo_standardize.py "<topic dir>"
count := name endswith _count/_cnt OR in {population, Minority_employment, Nonminority_employment}
replicate := everything else. Never overwrites an existing geo_standardize block."""
import json, sys
from pathlib import Path
COUNT_EXACT = {"population", "Minority_employment", "Nonminority_employment"}
def mtype(name): return "count" if (name.endswith(("_count", "_cnt")) or name in COUNT_EXACT) else "replicate"
def main(topic):
    p = Path(topic) / "data/distribution/measure_info.json"
    mi = json.load(open(p)); changed = 0
    for k, v in mi.items():
        if k.startswith("_") or not isinstance(v, dict) or "geo_standardize" in v: continue
        v["geo_standardize"] = {"measure_type": mtype(k)}; changed += 1
    json.dump(mi, open(p, "w"), indent=2, ensure_ascii=False)
    print(f"{topic}: added {changed} geo_standardize blocks")
if __name__ == "__main__": main(sys.argv[1])
```

- [ ] **Step 2: Create `standardize_one.py`**
```python
"""Regenerate one dataset (ingest via run_entrypoint -> no __main__ auto-publish) and run
the region-wide conservation gate. Usage: python standardize_one.py "<topic dir>"."""
import sys, glob
sys.path.insert(0, "tools/census10to20_remediation")
from driver import run_entrypoint
from acceptance_test import check_conservation
def main(topic):
    run_entrypoint(topic + "/code/distribution/ingest.py", "run")
    fail = False; geo20 = geo10 = False
    import pandas as pd
    for f in sorted(glob.glob(topic + "/data/distribution/*.csv.xz")):
        r = check_conservation(f)
        print(f"  {f.split('/')[-1]}: gate={r['status']} max_ratio={r.get('max_ratio')}")
        if r["status"] == "fail": fail = True
        ms = pd.read_csv(f, usecols=["measure"]).measure
        geo20 = geo20 or ms.str.endswith("_geo20").any()
        geo10 = geo10 or ms.str.endswith("_geo10").any()
    print(f"GEO20={geo20} GEO10={geo10} GATE={'FAIL' if fail else 'PASS'}")
    sys.exit(1 if (fail or not geo20) else 0)
if __name__ == "__main__": main(sys.argv[1])
```

- [ ] **Step 3: Commit**
```bash
git add tools/census10to20_remediation/add_geo_standardize.py tools/census10to20_remediation/standardize_one.py
git commit -m "tools(census10to20): helpers to inject geo_standardize and regenerate+gate one dataset"
```

---

## Per-dataset task template (Tasks 3–9 follow this exact shape)

Each per-dataset task has the same 5 steps; only the **topic**, **cutoff argument**, and **measure expectations** differ. The cutoff argument is passed by editing the dataset's ingest `write_data` (not the helper).

1. **Inject metadata:** `uv run python tools/census10to20_remediation/add_geo_standardize.py "<TOPIC>"`; verify the printed count and spot-check types.
2. **Wire ingest:** load `_MI` (idiom above) and set the `write_data` that targets `data/distribution` to `census_standardize=True, measure_info=_MI[, vintage_cutoff_year=<CUTOFF>]`. First confirm which `write_data` writes the published distribution file: `grep -nE "write_data|data/distribution|DIST_DIR|out_dir" "<TOPIC>/code/distribution/ingest.py" "<TOPIC>/code/distribution/prepare.py"`.
3. **Regenerate + gate:** `SDC_NO_PUBLISH=1 uv run python tools/census10to20_remediation/standardize_one.py "<TOPIC>"`. Expected: `GEO20=True GEO10=True GATE=PASS`.
4. **Validate the boundary** (per-dataset assertion below).
5. **Commit** the dataset.

---

## Task 3: PLACES — Mental and Physical Healthy Days (cutoff 2022)

**Files:** `health/Mental Health/Mental and Physical Healthy Days/{data/distribution/measure_info.json, code/distribution/ingest.py:285}`.

- [ ] **Step 1: Inject** — `uv run python tools/census10to20_remediation/add_geo_standardize.py "health/Mental Health/Mental and Physical Healthy Days"`. Expected: `added 2`; both `perc_freq_mental_distress`, `perc_freq_physical_distress` → `replicate`.
- [ ] **Step 2: Wire (cutoff 2022)** — add the `_MI` idiom; replace the `census_standardize=False` comment + `out_path = write_data(df, out_dir / f"{auto_name}.csv.xz")` (line ~285) with:
```python
        out_path = write_data(df, out_dir / f"{auto_name}.csv.xz",
                              census_standardize=True, measure_info=_MI, vintage_cutoff_year=2022)
```
- [ ] **Step 3: Regenerate + gate** — `SDC_NO_PUBLISH=1 uv run python tools/census10to20_remediation/standardize_one.py "health/Mental Health/Mental and Physical Healthy Days"`. Expected: `GEO20=True GEO10=True GATE=PASS` (no count measures → gate `n/a`/`pass`).
- [ ] **Step 4: Validate** —
```bash
uv run python -c "
import pandas as pd, glob
d=pd.concat([pd.read_csv(f,usecols=['year','measure']) for f in glob.glob('health/Mental Health/Mental and Physical Healthy Days/data/distribution/*.csv.xz')])
print('2021 geo10:', not d[(d.year==2021)&(d.measure.str.endswith('_geo10'))].empty, '(expect True)')
print('2023 geo10:', not d[(d.year==2023)&(d.measure.str.endswith('_geo10'))].empty, '(expect False)')"
```
- [ ] **Step 5: Commit** — `git add "health/Mental Health/Mental and Physical Healthy Days"` then `git commit -m "feat(places): census-standardize Mental/Physical Healthy Days to 2020 (cutoff 2022)"`.

---

## Task 4: Rent — HUD FMR (all years 2010-vintage)

**Files:** `housing/Cost/Rent/{data/distribution/measure_info.json, code/distribution/ingest.py:476,488}`.

- [ ] **Step 1: Inject** — `uv run python tools/census10to20_remediation/add_geo_standardize.py "housing/Cost/Rent"`. Expected: `added 5`; all `monthly_rent_*` → `replicate`.
- [ ] **Step 2: Wire (cutoff = max(years)+1, both writes)** — add the `_MI` idiom and `_CUTOFF = max(years) + 1` where `years` is in scope. Change BOTH `va_path = write_data(... census_standardize=False)` (~476) and `ncr_path = write_data(... census_standardize=False)` (~488) to `census_standardize=True, measure_info=_MI, vintage_cutoff_year=_CUTOFF`.
- [ ] **Step 3: Regenerate + gate** — `SDC_NO_PUBLISH=1 uv run python tools/census10to20_remediation/standardize_one.py "housing/Cost/Rent"`. Expected: `GEO20=True GEO10=True GATE=PASS`.
- [ ] **Step 4: Validate (every year converted)** —
```bash
uv run python -c "
import pandas as pd, glob
d=pd.concat([pd.read_csv(f,usecols=['year','measure']) for f in glob.glob('housing/Cost/Rent/data/distribution/*.csv.xz')])
print('years total:', d.year.nunique(), '| years with geo10:', d[d.measure.str.endswith('_geo10')].year.nunique(), '(expect equal)')"
```
- [ ] **Step 5: Commit** — `git add "housing/Cost/Rent"` then `git commit -m "feat(rent): census-standardize HUD FMR rents to 2020 (all years 2010-vintage)"`.

---

## Task 5: OB-GYN Service Access Scores (cutoff 2021)

**Files:** `health/Health Care Services/Physicians/OB-GYN/Service Access Scores/{data/distribution/measure_info.json, code/distribution/ingest.py}`.

- [ ] **Step 1: Confirm canonical write_data** — `grep -nE "write_data|data/distribution|DIST_DIR" "health/Health Care Services/Physicians/OB-GYN/Service Access Scores/code/distribution/ingest.py" "health/Health Care Services/Physicians/OB-GYN/Service Access Scores/code/distribution/prepare.py"`. Standardize the `write_data` whose path is under `data/distribution`; confirm `prepare.py` does not overwrite it with a non-standardized file.
- [ ] **Step 2: Inject** — `uv run python tools/census10to20_remediation/add_geo_standardize.py "health/Health Care Services/Physicians/OB-GYN/Service Access Scores"`. Expected: `obgyn_cnt` → count; `obgyn_2sfca/3sfca/e2sfca/near_10_mean/near_10_median` → replicate.
- [ ] **Step 3: Wire (cutoff 2021)** — add `_MI` idiom; set the canonical distribution `write_data` to `census_standardize=True, measure_info=_MI, vintage_cutoff_year=2021`.
- [ ] **Step 4: Regenerate + gate** — `SDC_NO_PUBLISH=1 uv run python tools/census10to20_remediation/standardize_one.py "health/Health Care Services/Physicians/OB-GYN/Service Access Scores"`. Expected: `GEO20=True GEO10=True GATE=PASS` (gate checks `obgyn_cnt` region-wide ≈1.0).
- [ ] **Step 5: Validate (boundary at 2021)** —
```bash
uv run python -c "
import pandas as pd, glob
d=pd.concat([pd.read_csv(f,usecols=['year','measure']) for f in glob.glob('health/Health Care Services/Physicians/OB-GYN/Service Access Scores/data/distribution/*.csv.xz')])
print('2020 geo10:', not d[(d.year==2020)&(d.measure.str.endswith('_geo10'))].empty, '(expect True)')
print('2021 geo10:', not d[(d.year==2021)&(d.measure.str.endswith('_geo10'))].empty, '(expect False)')"
```
- [ ] **Step 6: Commit** — `git add "health/Health Care Services/Physicians/OB-GYN/Service Access Scores"` then `git commit -m "feat(obgyn): census-standardize OB-GYN access scores to 2020 (cutoff 2021)"`.

---

## Task 6: Pediatric Service Access Scores (cutoff 2021)

**Files:** `health/Health Care Services/Physicians/Pediatric/Service Access Scores/{data/distribution/measure_info.json, code/distribution/ingest.py}`.

- [ ] **Step 1: Confirm canonical write_data** — `grep -nE "write_data|data/distribution|DIST_DIR" "health/Health Care Services/Physicians/Pediatric/Service Access Scores/code/distribution/ingest.py" "health/Health Care Services/Physicians/Pediatric/Service Access Scores/code/distribution/prepare.py"`.
- [ ] **Step 2: Inject** — `uv run python tools/census10to20_remediation/add_geo_standardize.py "health/Health Care Services/Physicians/Pediatric/Service Access Scores"`. Expected: `peds_cnt` → count; `peds_2sfca/3sfca/e2sfca/near_10_mean/near_10_median` → replicate. If the data carries an extra `pediatrician_e2sfca` measure absent from measure_info, add a measure_info entry for it with `{"measure_type": "replicate"}`.
- [ ] **Step 3: Wire (cutoff 2021)** — add `_MI` idiom; set the canonical distribution `write_data` to `census_standardize=True, measure_info=_MI, vintage_cutoff_year=2021`.
- [ ] **Step 4: Regenerate + gate** — `SDC_NO_PUBLISH=1 uv run python tools/census10to20_remediation/standardize_one.py "health/Health Care Services/Physicians/Pediatric/Service Access Scores"`. Expected: `GEO20=True GEO10=True GATE=PASS`.
- [ ] **Step 5: Validate (boundary at 2021)** —
```bash
uv run python -c "
import pandas as pd, glob
d=pd.concat([pd.read_csv(f,usecols=['year','measure']) for f in glob.glob('health/Health Care Services/Physicians/Pediatric/Service Access Scores/data/distribution/*.csv.xz')])
print('2020 geo10:', not d[(d.year==2020)&(d.measure.str.endswith('_geo10'))].empty, '(expect True)')
print('2021 geo10:', not d[(d.year==2021)&(d.measure.str.endswith('_geo10'))].empty, '(expect False)')"
```
- [ ] **Step 6: Commit** — `git add "health/Health Care Services/Physicians/Pediatric/Service Access Scores"` then `git commit -m "feat(pediatric): census-standardize Pediatric access scores to 2020 (cutoff 2021)"`.

---

## Task 7: Primary Care Service Access Scores (cutoff 2021)

**Files:** `health/Health Care Services/Physicians/Primary Care/Service Access Scores/{data/distribution/measure_info.json, code/distribution/ingest.py}`.

- [ ] **Step 1: Confirm canonical write_data** — `grep -nE "write_data|data/distribution|DIST_DIR" "health/Health Care Services/Physicians/Primary Care/Service Access Scores/code/distribution/ingest.py" "health/Health Care Services/Physicians/Primary Care/Service Access Scores/code/distribution/prepare.py"`.
- [ ] **Step 2: Inject** — `uv run python tools/census10to20_remediation/add_geo_standardize.py "health/Health Care Services/Physicians/Primary Care/Service Access Scores"`. Expected: `primcare_cnt` → count; `primcare_2sfca/e2sfca/3sfca/near_10_mean/near_10_median` → replicate.
- [ ] **Step 3: Wire (cutoff 2021)** — add `_MI` idiom; set the canonical distribution `write_data` to `census_standardize=True, measure_info=_MI, vintage_cutoff_year=2021`.
- [ ] **Step 4: Regenerate + gate** — `SDC_NO_PUBLISH=1 uv run python tools/census10to20_remediation/standardize_one.py "health/Health Care Services/Physicians/Primary Care/Service Access Scores"`. Expected: `GEO20=True GEO10=True GATE=PASS`.
- [ ] **Step 5: Validate (boundary at 2021)** —
```bash
uv run python -c "
import pandas as pd, glob
d=pd.concat([pd.read_csv(f,usecols=['year','measure']) for f in glob.glob('health/Health Care Services/Physicians/Primary Care/Service Access Scores/data/distribution/*.csv.xz')])
print('2020 geo10:', not d[(d.year==2020)&(d.measure.str.endswith('_geo10'))].empty, '(expect True)')
print('2021 geo10:', not d[(d.year==2021)&(d.measure.str.endswith('_geo10'))].empty, '(expect False)')"
```
- [ ] **Step 6: Commit** — `git add "health/Health Care Services/Physicians/Primary Care/Service Access Scores"` then `git commit -m "feat(primcare): census-standardize Primary Care access scores to 2020 (cutoff 2021)"`.

---

## Task 8: SNAP (ACS) — cutoff 2020 (default)

**Files:** `food/Food and Nutrition Assistance/Supplemental Nutrition Assistance Program (SNAP)/{data/distribution/measure_info.json, code/distribution/ingest.py:84 and/or prepare.py:121}`.

- [ ] **Step 1: Confirm canonical write_data** — `grep -nE "write_data|data/distribution|out_dir|DIST_DIR" "food/Food and Nutrition Assistance/Supplemental Nutrition Assistance Program (SNAP)/code/distribution/ingest.py" "food/Food and Nutrition Assistance/Supplemental Nutrition Assistance Program (SNAP)/code/distribution/prepare.py"`. Standardize the `write_data` writing `data/distribution`. If the data mixes `block group` and `block_group` region_type labels, normalize to `block_group` before the write.
- [ ] **Step 2: Inject** — `uv run python tools/census10to20_remediation/add_geo_standardize.py "food/Food and Nutrition Assistance/Supplemental Nutrition Assistance Program (SNAP)"`. Expected: `hh_received_snap_cnt` → count, `population` → count, `hh_received_snap_pct` → replicate.
- [ ] **Step 3: Wire (default cutoff 2020)** — add `_MI` idiom; set the canonical distribution `write_data` to `census_standardize=True, measure_info=_MI` (omit `vintage_cutoff_year` — default 2020 matches the clean 2020 switch).
- [ ] **Step 4: Regenerate + gate** — `SDC_NO_PUBLISH=1 uv run python tools/census10to20_remediation/standardize_one.py "food/Food and Nutrition Assistance/Supplemental Nutrition Assistance Program (SNAP)"`. Expected: `GEO20=True GEO10=True GATE=PASS` (gate checks `hh_received_snap_cnt`, `population`).
- [ ] **Step 5: Validate (boundary at 2020)** —
```bash
uv run python -c "
import pandas as pd, glob
d=pd.concat([pd.read_csv(f,usecols=['year','measure']) for f in glob.glob('food/Food and Nutrition Assistance/Supplemental Nutrition Assistance Program (SNAP)/data/distribution/*.csv.xz')])
print('2019 geo10:', not d[(d.year==2019)&(d.measure.str.endswith('_geo10'))].empty, '(expect True)')
print('2020 geo10:', not d[(d.year==2020)&(d.measure.str.endswith('_geo10'))].empty, '(expect False)')"
```
- [ ] **Step 6: Commit** — `git add "food/Food and Nutrition Assistance/Supplemental Nutrition Assistance Program (SNAP)"` then `git commit -m "feat(snap): census-standardize SNAP to 2020 (counts area-weighted, pct replicated)"`.

---

## Task 9: Worker_diversity (LODES) — reconcile measure_info, then standardize (cutoff 2020)

**Files:** `business_climate/Employment/Worker_diversity/{data/distribution/measure_info.json, code/distribution/ingest.py:148}`.

- [ ] **Step 1: Diagnose the measure_info ↔ data naming mismatch**
```bash
uv run python -c "
import pandas as pd, json, glob
data=set()
for f in glob.glob('business_climate/Employment/Worker_diversity/data/distribution/*.csv.xz'): data|=set(pd.read_csv(f,usecols=['measure']).measure.unique())
mi=set(k for k in json.load(open('business_climate/Employment/Worker_diversity/data/distribution/measure_info.json')) if not k.startswith('_'))
print('in data not mi:', sorted(data-mi)[:8], '| count', len(data-mi))
print('in mi not data:', sorted(mi-data)[:8], '| count', len(mi-data))"
```
Expected: confirms data is unprefixed (e.g. `age_29_and_under_female_count`) while measure_info uses `wac_`/`rac_` prefixes and documents `rac_*` not emitted.

- [ ] **Step 2: Reconcile measure_info keys to emitted data measures** — edit `measure_info.json` so its non-`_` keys exactly equal the set of measures in the distribution data: drop entries not emitted; rename to the emitted names (preserve each entry's descriptions/fields; only the key changes). Verify:
```bash
uv run python -c "
import pandas as pd, json, glob
data=set()
for f in glob.glob('business_climate/Employment/Worker_diversity/data/distribution/*.csv.xz'): data|=set(pd.read_csv(f,usecols=['measure']).measure.unique())
mi=set(k for k in json.load(open('business_climate/Employment/Worker_diversity/data/distribution/measure_info.json')) if not k.startswith('_'))
assert data==mi, ('mismatch', data^mi); print('matches:', len(data))"
```
> If reconciliation reveals deeper inconsistency (e.g. the data measure set varies across files, like the Hospitals case), STOP and treat Worker_diversity as a separate investigation.

- [ ] **Step 3: Inject** — `uv run python tools/census10to20_remediation/add_geo_standardize.py "business_climate/Employment/Worker_diversity"`. Expected: every `*_count` + `Minority_employment`/`Nonminority_employment` → count; every `*_perc` → replicate.
- [ ] **Step 4: Wire (default cutoff 2020)** — add `_MI` idiom; change line 148 `write_data(combined, out_path, census_standardize=False)` to `write_data(combined, out_path, census_standardize=True, measure_info=_MI)`.
- [ ] **Step 5: Regenerate + gate** — `SDC_NO_PUBLISH=1 uv run python tools/census10to20_remediation/standardize_one.py "business_climate/Employment/Worker_diversity"`. Expected: `GEO20=True GEO10=True GATE=PASS` (all years 2010–2019 are pre-2020 → all converted; gate checks the `*_count` measures).
- [ ] **Step 6: Validate** —
```bash
uv run python -c "
import pandas as pd, glob
d=pd.concat([pd.read_csv(f,usecols=['measure']) for f in glob.glob('business_climate/Employment/Worker_diversity/data/distribution/*.csv.xz')])
print('geo10:', d.measure.str.endswith('_geo10').any(), '| geo20:', d.measure.str.endswith('_geo20').any())"
```
- [ ] **Step 7: Commit** — `git add "business_climate/Employment/Worker_diversity"` then `git commit -m "feat(worker_diversity): reconcile measure_info + census-standardize LODES to 2020"`.

---

## Task 10: Full verification, finish branch, tags, releases

- [ ] **Step 1: Full suite** — `uv run pytest -q`. Expected: all pass (the existing 24-dataset harness must still pass — confirms the `vintage_cutoff_year` default did not regress them).
- [ ] **Step 2: Confirm all 7 emit `_geo10`+`_geo20`** —
```bash
uv run python -c "
import pandas as pd, glob
for t in ['health/Mental Health/Mental and Physical Healthy Days','housing/Cost/Rent',
          'health/Health Care Services/Physicians/OB-GYN/Service Access Scores',
          'health/Health Care Services/Physicians/Pediatric/Service Access Scores',
          'health/Health Care Services/Physicians/Primary Care/Service Access Scores',
          'food/Food and Nutrition Assistance/Supplemental Nutrition Assistance Program (SNAP)',
          'business_climate/Employment/Worker_diversity']:
    ms=set()
    for f in glob.glob(t+'/data/distribution/*.csv.xz'): ms|=set(pd.read_csv(f,usecols=['measure']).measure.unique())
    print('OK' if any(m.endswith('_geo20') for m in ms) and any(m.endswith('_geo10') for m in ms) else 'FAIL', t.split('/')[-1])"
```
Expected: all 7 OK.
- [ ] **Step 3: Finish the branch** — use superpowers:finishing-a-development-branch (verify tests → merge to main → push).
- [ ] **Step 4: Tags + GitHub releases** — for each of the 7, bump version per the project flow, create a git tag, and `gh release create <tag> <topic>/data/distribution/*.csv.xz --title ... --notes ...` (the same approach used for the 24 — `gh release create` per existing tag with the dataset's `data/distribution/*.csv.xz` attached). **No Zenodo** — verify none has a deposit: `for t in <the 7>; do grep -L zenodo_deposit_id "$t/pipeline.yaml"; done`.

---

## Notes for the implementer

- Re-read `docs/pipeline-conversion-spec.md` before editing any pipeline.
- `run_entrypoint` (in `driver.py`) loads ingest under a non-`__main__` name, so the pipeline's `if __name__ == "__main__": update_version(...)` auto-publish block does NOT run — that is why regeneration goes through `standardize_one.py`, not `python ingest.py`.
- The existing driver's `process_dataset` is intentionally NOT used: its gate requires `_inflation_reduced(before, after)`, which assumes a prior broken `_geo20`. These 7 have none, so `standardize_one.py` uses only `run_entrypoint` + `check_conservation`.
- Block-group rows (Worker_diversity, SNAP, access scores): the tract relationship file is national, but block-group conversion uses the per-state file — confirm the gate passes at BG level for the coverage state(s); if a BG file is missing for a state, surface it rather than silently dropping rows.
- Standardize only the ingest `write_data` that targets `data/distribution`; if `prepare.py` re-emits a distribution-level file, ensure it does not overwrite the standardized output with a non-standardized one.
```
