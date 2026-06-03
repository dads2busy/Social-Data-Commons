# Fix `convert_2010_to_2020_bounds` to Conserve Counts — Design

## Overview

`convert_2010_to_2020_bounds` (in `sdc-census10to20`) redistributes 2010-vintage
census measures onto 2020 boundaries. Its sole purpose is **count
redistribution** for time-series analysis across a common (2020) geography. As
implemented it does **not** conserve counts: it weights "moved" overlaps by
`area_part/area20` and passes "same"/"split" through unchanged, so a tract that
splits has its value **replicated** to each child. Fix it to use source-area
weighting (`area_part/area10`), which conserves totals. Then resume the
census10to20 intro map (now on a county whose tracts changed).

## The bug (verified)

Real case — 2010 tract `51121020300` (1,000 people) split into two 2020 tracts;
`convert` returned `51121020301 → 1000`, `51121020302 → 998.6`, sliver `→ 0.03`,
**sum 1998.7**. Each 2020 child fully inside the 2010 parent inherited the full
1,000. The current code (`convert.py`):

- `same`/`split` → `groupby(geoid20).first()` (passthrough — replicates on split);
- `moved` → `value * area_part/area20` summed (intensive/rate weighting).

Both are wrong for counts.

## The fix

Replace the branching with a single source-area-weighted sum:

```python
joined = crosswalk.merge(data, left_on="geoid10", right_on=geoid_col, how="left")
joined["value"] = joined["value"] * (joined["area_part"] / joined["area10"])
redistributed = (
    joined.groupby("geoid20", as_index=False)["value"].sum()
    .rename(columns={"geoid20": "geoid", "value": val_col})
)
```

`area_part/area10` is the fraction of each 2010 **source** tract that falls in a
given 2020 tract. A source's overlaps tile it, so the fractions sum to 1 and the
source's full count is distributed across the 2020 tracts — **total conserved**.
`type_change` no longer affects the math (the geometry already encodes same vs
split vs moved):

- **same** (`area_part == area10`) → weight 1, passthrough. ✓
- **split** → children split by area (500 → 300/200), sum 500. ✓
- **moved/merge** → `value × area_part/area10` per overlap, conserved across the
  full crosswalk. ✓

`standardize_all` calls `convert` and is fixed automatically.

### NaN handling

Keep the existing "missing input values" warning. With `groupby.sum()`, a 2020
tract fed only by NaN-valued sources sums to 0 (skipna). This is acceptable and
no worse than the current mixed behavior; not changing it further (YAGNI). The
warning text stays.

## Tests (TDD — existing tests encode the bug and must change)

In `packages/sdc-census10to20/tests/test_convert.py` (synthetic `fake_crosswalk`
fixture: same=001, split=002/003 of source 020, moved=004/005 of source 030):

- **Rewrite** `test_convert_distributes_split_values`: source 020 value 500 →
  child 002 = `500*600/1000 = 300`, child 003 = `500*400/1000 = 200` (sum 500).
- **Rewrite** `test_convert_area_weights_moved_values`: source 030 value 1200 →
  004 and 005 each `1200*400/1000 = 480` (the two shown overlaps; the rest of the
  source's area maps to 2020 tracts outside this partial fixture).
- **Keep** `test_convert_passes_same_values_through` (100 → 100 still holds).
- **Add** `test_convert_conserves_total_over_complete_crosswalk`: a synthetic
  crosswalk where one source's overlaps fully tile it (`Σ area_part == area10`);
  assert `Σ output value == Σ input value`.
- **Add** `test_convert_conserves_county_total`: model a small "county" — several
  2010 tracts whose overlaps stay within the county and fully tile each — and
  assert the **county-level** output total equals the input total (the user's
  criterion: a county's population is unchanged by reprojection because its
  boundary didn't move).
- Keep the missing/duplicate-geoid validation tests.

## Docstring + article

- Rewrite the `convert_2010_to_2020_bounds` docstring: source-area-weighted areal
  interpolation that conserves totals; remove the "same/split pass through"
  language.
- Update the census10to20 intro article's "What 'redistribute' actually does"
  section (it currently describes the buggy passthrough + `area_part/area20`).

## Release

- `sdc-census10to20` **patch release `v0.1.2`** (correctness bugfix).
- CHANGELOG `[0.1.2]`: "Fixed — `convert_2010_to_2020_bounds` now conserves counts
  (source-area weighting `area_part/area10`); previously split tracts replicated
  their value and moved tracts used `area_part/area20`, inflating totals.
  Re-run any pipeline that converted counts."
- Tag `census10to20-v0.1.2` after merge (Trusted Publishing already configured).

## Resume the census10to20 intro map (Phase 2)

After the fix is released, redo the intro map on a county whose **tracts**
changed (county boundary fixed), e.g. **51121** (16 → 23 tracts). The figure
scripts/assets from the prior (parked) map work are reused, switching the county
and re-running on the corrected `convert`. Verify **county-level conservation**
in the figure (2010 county total == 2020 county total) and that the before/after
panels show visibly different internal tract boundaries.

## Verification / success criteria

- New + rewritten unit tests pass; full `sdc-census10to20` suite green.
- Real-data check: for a county whose tracts changed (51121), inputting all its
  2010 tracts and converting yields a 2020 county total equal to the 2010 county
  total (within rounding).
- `v0.1.2` live on PyPI; CHANGELOG updated.
- census10to20 intro map shows a real boundary change with conserved county total.

## Out of scope

- Block-group vs tract behavior differences (the same fix applies to both;
  `convert` is resolution-agnostic).
- Changing `get_2010_2020_bound_changes` / `create_crosswalk` (unchanged).
- Population- or housing-weighted interpolation (area weighting only, as today).
- The redistribute/catchment packages.
