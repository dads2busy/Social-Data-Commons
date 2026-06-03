# census10to20 Corruption Remediation — Design Spec

**Date:** 2026-06-03
**Status:** BLOCKED — design approved, but execution is gated on the intensive-measure
fix (see §9). Do not regenerate until that fix lands and its design is approved.
**Authoritative impact reference:** `docs/census10to20-conversion-data-impact.md`
**Related:** `docs/specs/2026-06-03-census10to20-count-conservation-fix-design.md`,
memory `feedback_update_version_side_effects`, `reference_census10to20_convert_semantics`

## 1. Problem

`sdc-census10to20`'s `convert_2010_to_2020_bounds` had a count-inflation bug
(weighted "moved" overlaps by `area_part/area20` and passed "same"/"split"
through unchanged, so a split 2010 tract **replicated** its full value onto each
2020 child). Fixed in v0.1.2 (weight by `area_part/area10`, which conserves);
v0.1.3 memoized the relationship-file download. The corrected code is **live in
the uv workspace** (confirmed: `sdc_census10to20.__version__` resolves to a dev
build off the fixed `main`).

The **distribution data** produced before the fix is still corrupted and has not
been regenerated. This spec designs the regeneration of the 24 affected datasets.

### Corruption scope (from the impact doc — authoritative)

Wrong only for: redistributed **`_geo20`** measures, **sub-county** rows (tract
geoid len 11, block group len 12), **years < 2020**, where the source 2010 tract
**split or moved**. Errors are over-counts. County/health-district aggregates
built from the bad `_geo20` rows are correspondingly inflated.

Correct/unaffected: original `_geo10` values; all `year >= 2020` rows; unchanged
("same") tracts; non-sub-county geographies.

### The 24 affected datasets

Per the impact doc, in regeneration order.

**Phase 1 — base ACS indicators** (independent; fetch from Census API):
- `demographics/Age` *(first — harness checkpoint)*
- `demographics/Race`
- `demographics/Gender`
- `demographics/Language`
- `demographics/Veteran`
- `demographics/Population Density`
- `demographics/Cooperative extension`
- `financial_well_being/Household Income`
- `financial_well_being/Income Inequality`
- `financial_well_being/Employment Rates`
- `financial_well_being/Material_Deprivation` *(standardizes in `prepare.py`)*
- `health/System Usage and Insurance/Without Health Insurance`
- `education/Years of Schooling`
- `education/Postsecondary`
- `broadband/Household Broadband` *(standardizes in `prepare.py`)*
- `transportation/Population Characteristics`

**Phase 2 — composites / HOI / derived** (depend on inputs or external services):
- `environment/Environmental Hazard Index (HOI)` *(direct `convert_2010_to_2020_bounds`; EJSCREEN cached)*
- `food/Food Access/Food Accessibility Indicator (HOI)`
- `public_safety/Incarceration (HOI)`
- `demographics/Geographic Mobility (HOI)`
- `demographics/Segregation Index (HOI)`
- `financial_well_being/Employment Access Index`
- `transportation/Walkability` *(direct `convert`; reads cached `transit_stops/data/walkability`)*
- `housing/Cost/Affordability_HT` *(ingest standardizes into `data/working/`; `prepare.py` propagates to `data/distribution/`)*

## 2. Known blockers and how the design handles them

### 2.1 Auto-publish on `update_version`
`update_version(TOPIC_DIR)` (called in every `prepare.py` `__main__`, and in
`health/Health Opportunity Index/.../compute_composite.py`) defaults to
`auto_tag=True, auto_release=True`, which **pushes a git tag and creates a GitHub
release**. `create_git_tag` itself also pushes. This project already suffered one
accidental release (`demographics/Age` v1.0.0→v2.0.0, since rolled back).

**Handling — two layers:**
1. **Driver bypass (primary).** No `ingest.py` calls `update_version` (verified);
   only `prepare.py`/`compute_composite.py` `__main__` blocks do. The driver loads
   each module *by file path* and calls its `run()` function directly, which
   executes module top-level imports but **not** the `if __name__ == "__main__"`
   block — so `update_version` never fires during regeneration.
2. **`SDC_NO_PUBLISH` kill-switch (defense-in-depth).** Add a small,
   backward-compatible guard to `sdc_core.versioning.update_version`: when the
   `SDC_NO_PUBLISH` env var is set (any non-empty value), force
   `auto_tag=False, auto_release=False` regardless of arguments. Defaults to
   current behavior when unset. Set for the whole remediation session so any stray
   manual `python prepare.py` cannot publish. ⚠️ This modifies `sdc-core`; the
   change is additive and behavior-preserving when the env var is absent.

### 2.2 Stale manifests → phantom MAJOR bumps
Many committed `manifest.json` files record a `schema` lacking `data_method`
though the data has it (confirmed: `demographics/Age` manifest schema =
`[geoid, year, measure, value, moe, region_type]`). `detect_bump` would read this
as a schema change → spurious MAJOR bump.

**Handling.** The controlled version step uses `force_level="patch"`, which
bypasses `detect_bump`'s level decision entirely (and bypasses
`skip_if_unchanged`). The step still calls `generate_manifest`, which reads the
**current** data file and writes a corrected, non-stale manifest as a side effect.
One move fixes both the phantom bump and the staleness.

## 3. Components

Built under a remediation directory (proposed:
`docs/superpowers/remediation/census10to20/`), kept out of the pipeline tree.

### 3.1 `acceptance_test.py`
Reusable function `check_conservation(path) -> Report`. Per the impact doc:

```python
df = pd.read_csv(path, dtype={"geoid": str})
tr = df[(df.year < 2020) & (df.region_type == "tract")].copy()
tr["county"] = tr["geoid"].str[:5]
# for each base measure with a _geo20/_geo10 pair that is a COUNT measure:
#   ratio = geo20.groupby(county).sum() / geo10.groupby(county).sum()
#   record max ratio
```

- **Count detection.** Only count measures conserve. A measure pair is asserted
  iff the base name denotes a count (heuristic: contains `count` or `pop`/`total`
  and not `percent`/`pct`/`rate`/`index`/`median`/`mean`). Non-count `_geo20`
  pairs are reported informationally, not gated.
- **Pass criterion.** `max county ratio <= 1.01` for every gated measure (≈1.0 ==
  fixed). Tolerance absorbs rounding; exact 1.0 not required.
- **N/A.** If a file has no gated `_geo20` count measure (e.g. a percent-only or
  index-only output), the test returns `status="n/a"` and the dataset is gated on
  BEFORE>AFTER row/value sanity only (see §5).
- **Scope note.** The doc's canonical test uses `region_type == "tract"`. Block
  groups (len-12) are also sub-county; the test additionally reports the
  block-group county-ratio where present, but the tract ratio is the gate (matches
  the doc's worked example).

### 3.2 `regenerate.py` (driver)
Iterates the per-dataset manifest (§3.3) in order. Per dataset, in an **isolated
subprocess** (fresh interpreter — avoids pandas/global state bleed and matches how
pipelines are meant to run):

1. **BEFORE.** Run `acceptance_test.check_conservation` on the currently-committed
   distribution file(s); record max ratio (expected > 1.0 for affected datasets,
   e.g. Age ≈ 2.0 in the worked example).
2. **Regenerate.** For each entrypoint in the dataset's ordered list: load the
   module by path (`importlib.util.spec_from_file_location`), call its `run()`.
   Default order `[ingest.run, prepare.run]`; datasets with an intermediate
   compute step list it between.
3. **AFTER.** Re-run the acceptance test on the regenerated distribution file(s).
4. **Gate.** Require AFTER `status == "pass"` (max ratio ≤ 1.01) **and**
   AFTER.max_ratio < BEFORE.max_ratio (or BEFORE was already ≈1.0 / N/A, meaning
   no split/moved tracts in this dataset's footprint). On failure: **halt the
   batch** and report; do not commit.
5. **Version.** `update_version(TOPIC_DIR, force_level="patch", auto_tag=False,
   auto_release=False)` → refreshed manifest + patch-bumped `pipeline.yaml`, no
   tag, no release. Then create a **local** annotated tag manually
   (`git tag -a <slug>/vX.Y.Z -m ...`, **no push**) to mark the correction.
6. **Commit.** One commit per dataset (§5).

The driver is **resumable**: it skips datasets whose AFTER test already passes and
whose working tree shows a committed regeneration, so a halt mid-batch can be
re-run without redoing completed datasets.

### 3.3 Per-dataset entrypoint manifest
A table (in `regenerate.py` or an adjacent JSON/py) of the 24 datasets with:
`topic_dir`, ordered `entrypoints` (relative paths + function name, default
`code/distribution/ingest.py:run`, `code/distribution/prepare.py:run`), and the
glob(s) for the distribution file(s) the acceptance test reads. Encodes Phase 1
then Phase 2, **Age first**. Datasets needing an extra compute step (verify per
each `pipeline.yaml` during plan execution) list it explicitly.

## 4. Prerequisites & environment
- `CENSUS_API_KEY` — present in repo-root `.env`; pipelines call
  `dotenv.load_dotenv()`, so Phase 1 is unblocked.
- `SDC_NO_PUBLISH=1` exported for the remediation session (after §2.1 layer 2 is
  in place).
- Cached Phase-2 inputs verified present: EJSCREEN (9 files in
  `environment/Environmental Hazard Index (HOI)/data/original/`), transit
  walkability parquets (`transportation/Walkability/transit_stops/data/walkability/`).
  EnvHazard's optional `demographics/Population` block-group input is absent and
  handled gracefully (`return None`). Re-fetch a live external source **only** if
  its cache is missing — flag to the user before any live EPA/OSM fetch.

## 5. Acceptance gate & commit policy (per dataset)
- **Gate:** §3.2 test passes (or N/A) AND the inflation measurably dropped.
- **Commit contents:** regenerated `data/distribution/*.csv.xz`, refreshed
  `manifest.json`, patch-bumped `pipeline.yaml`, refreshed
  `dashboard_data/{virginia_public_health_data,national_capital_region_data}/`
  outputs.
- **Commit message:** `fix(<topic>): regenerate _geo20 counts on corrected
  census10to20 (vX.Y.Z)` with the BEFORE→AFTER max-ratio in the body.
- **Expected noise:** re-fetching current ACS may produce trivial diffs unrelated
  to the fix (stable vintages). Acceptable; the acceptance test isolates the fix.
  Record row-count deltas in the commit body for transparency.
- **Dashboard parity:** `prepare.py` writes both VA and NCR `dashboard_data/`
  outputs; both refresh together. No divergence introduced.

## 6. Explicit non-goals / will-not-do
- No `git push`, no `gh release` — publishing is a separate, later, deliberate
  step. This remediation produces only local commits and local tags.
- No re-fetch of cached external inputs unless a cache is missing (user-flagged).
- No change to conversion logic (already fixed/merged) or to any pipeline's
  business logic. Only the standardization output values change.
- No `demographics/Population` resurrection — its absence is handled by EnvHazard.

## 7. Rollout
Age runs first as the harness checkpoint: confirm the full chain (BEFORE>AFTER,
local patch bump, no publish, clean per-dataset commit) before continuing. No
separate pilot phase — Age is simply first. Then the rest of Phase 1, then Phase
2. A dataset that fails its gate halts the batch for inspection.

## 8. Open items to resolve during planning
- Confirm each Phase-2 dataset's actual entrypoint sequence from its
  `pipeline.yaml` (whether an intermediate compute step exists between ingest and
  prepare).
- Confirm `housing/Cost/Affordability_HT`'s ingest→working→prepare→distribution
  chain end-to-end (ingest writes `data/working/`; prepare reads working and
  writes `va_hdcttr_*`/`ncr_cttrbg_*` to `data/distribution/`).
- Decide whether to also gate on block-group county ratios or tract-only (default:
  tract-only gate per the doc, block-group reported).

## 9. BLOCKING DEPENDENCY — intensive-measure regression

Discovered during design review: `standardize_all` area-weights **every** measure,
not just counts. The v0.1.2 count fix therefore *also* changed intensive `_geo20`
measures (percent/rate/median/mean/density/index) — and area-weighting an intensive
quantity is wrong. Demonstrated on real split tract `51121020300`: a parent at 30%
under-20 yields children reported at 1.96% / 28.0% / 0.003% (sums to 30 — the wrong
invariant) instead of ~30% each (recompute-from-counts / population-weighted).

These intensive `_geo20` measures are **displayed** (declared in `measure_info.json`,
carried wide by `data_reformat_for_site`, referenced in both dashboards). Because
counts and intensive measures emerge from the **same** `standardize_all` pass,
regenerating to fix counts would simultaneously ship a severe percent regression
(worse than the current pre-fix replication behavior).

**Decision (user):** pause this remediation; design the intensive-measure fix as its
own spec; then run ONE combined regeneration that corrects counts *and* intensive
measures. The acceptance gate (§3.2, §5) must be extended to also verify intensive
`_geo20` measures (e.g., ratio measures equal their count-recomputed value within
tolerance) before any dataset is committed.

See `docs/specs/2026-06-03-census10to20-intensive-measure-fix-design.md` (the
prerequisite design).
