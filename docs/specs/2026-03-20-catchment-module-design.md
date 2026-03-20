# sdc_core.catchment — Spatial Accessibility Module

## Overview

A general-purpose floating catchment area (FCA) library for computing spatial accessibility metrics. Implements 2SFCA, E2SFCA, KD2SFCA, 3SFCA, modified 2SFCA, balanced FCA, and commute-based FCA as parameter variations on a single `catchment_ratio()` function.

Replaces the R `catchment` package (`github.com/uva-bi-sdad/catchment`) with a Python module integrated into `sdc_core`. Eliminates the R dependency for spatial accessibility pipelines (Daycare Accessibility, Employment Access, and the ~9 Health Care Services pipelines pending conversion).

## Location

Single module: `packages/sdc-core/src/sdc_core/catchment.py` (~500-700 lines).

## Dependencies

All already available in the monorepo — no new packages:

- `scipy.sparse` — sparse weight/cost matrices
- `scipy.spatial.distance` — Euclidean distance helper
- `numpy` — array operations
- `pandas` — DataFrame I/O

## Type Alias

```python
WeightSpec = None | float | list[tuple[float, float]] | str | Callable[[np.ndarray], np.ndarray]
```

Defined at module level. Used by `catchment_weight` and `catchment_ratio`.

## Public API

All functions use NumPy-style docstrings (Parameters, Returns, Examples sections), matching the convention in `geo.py` and `redistribute.py`.

### `catchment_weight(cost, weight=None, max_cost=None, scale=2.0, normalize_weight=False, adjust_zeros=1e-6)`

Construct a weight matrix from a cost matrix using kernel decay functions.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cost` | sparse matrix, ndarray, or DataFrame | required | Rows = consumers, cols = providers. Values = travel cost/time/distance. |
| `weight` | `WeightSpec` | None | Weight specification (see Weight Types below). None = use cost values directly (adjust_zeros is skipped when weight is None). |
| `max_cost` | float or None | None | Zero out weights where cost exceeds this value. |
| `scale` | float | 2.0 | Scale parameter for kernel functions. |
| `normalize_weight` | bool | False | If True, apply 3SFCA selection probability normalization: `w_ij * (w_ij / sum_j(w_ij))`. This is NOT simple row normalization — it squares the weight and divides by the row sum, giving higher relative weight to nearer providers (Wan et al. 2012). |
| `adjust_zeros` | float or False | 1e-6 | Replace true zeros in cost matrix with this value. Only applied when `weight` is not None. False to skip. |

**Weight types:**

| Type | Example | Behavior |
|------|---------|----------|
| `None` | `weight=None` | Use raw cost values as weights. `adjust_zeros` is skipped. |
| `float` | `weight=30.0` | Binary threshold: 1.0 if cost < 30, else 0. Exclusive of threshold (matches R package). |
| `list[tuple[float, float]]` | `weight=[(10, 1.0), (20, 0.5), (30, 0.25)]` | Stepped: weight at each distance band. Sorted by distance automatically. |
| `str` | `weight="gaussian"` | Named kernel function (see Kernel Functions). |
| `callable` | `weight=my_func` | Custom function `(cost_matrix) -> weight_matrix`. |

**Returns:** `scipy.sparse.csc_matrix` with same dimensions as cost.

### `catchment_ratio(consumers, providers, cost, weight=None, scale=2.0, max_cost=None, normalize_weight=False, adjust_consumers=None, adjust_providers=None, consumers_commutes=None, consumers_id="geoid", consumers_value="value", providers_id="geoid", providers_value="value", adjust_zeros=1e-6, return_type="original")`

Calculate provider-to-consumer ratios within floating catchment areas.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `consumers` | DataFrame | required | Consumer data with ID and value (population) columns. |
| `providers` | DataFrame | required | Provider data with ID and value (capacity/supply) columns. |
| `cost` | sparse matrix, ndarray, or DataFrame | required | Cost matrix: rows = consumers, cols = providers. |
| `weight` | `WeightSpec` | None | Passed to `catchment_weight()`. |
| `scale` | float | 2.0 | Passed to `catchment_weight()`. |
| `max_cost` | float or None | None | Passed to `catchment_weight()`. |
| `normalize_weight` | bool | False | Apply 3SFCA selection probability normalization (see `catchment_weight`). |
| `adjust_consumers` | callable or None | None | Function applied to weight matrix before consumer aggregation. |
| `adjust_providers` | callable or None | None | Function applied to weight matrix before provider ratio computation. |
| `consumers_commutes` | ndarray, sparse matrix, or None | None | Square origin-destination matrix (n_consumers x n_consumers) for commute-based FCA. See Commute-Based FCA section. |
| `consumers_id` | str | "geoid" | Column name for consumer IDs in `consumers` DataFrame. |
| `consumers_value` | str | "value" | Column name for consumer values in `consumers` DataFrame. |
| `providers_id` | str | "geoid" | Column name for provider IDs in `providers` DataFrame. |
| `providers_value` | str | "value" | Column name for provider values in `providers` DataFrame. |
| `adjust_zeros` | float or False | 1e-6 | Passed to `catchment_weight()`. |
| `return_type` | str or numeric | "original" | Output format (see Return Types). |

**Cost matrix alignment:**

The cost matrix must have dimensions matching the consumer and provider DataFrames. Specifically:
- `cost.shape[0]` must equal `len(consumers)`
- `cost.shape[1]` must equal `len(providers)`
- Row ordering must match `consumers` DataFrame row ordering
- Column ordering must match `providers` DataFrame row ordering

If `cost` is a DataFrame, its index and columns are used for validation but alignment is NOT performed automatically. Mismatches raise `ValueError`. Callers are responsible for ensuring consistent ordering before calling.

**Return types:**

| Value | Description |
|-------|-------------|
| `"original"` | Access score: resources per consumer (standard FCA output). |
| `"supply"` | Total weighted resources reachable per consumer (no demand normalization). |
| `"region"` | Total resources allocated to each consumer region. |
| `"normalized"` | Access score normalized to 0-1 range. |
| numeric (e.g., `1000`) | Resources per N consumers (e.g., seats per 1,000 children). |
| `"demand"` | Demand per provider (indexed by provider ID). |

**Returns:** `pd.Series` indexed by consumer ID (or provider ID for `"demand"`).

**Core algorithm (2SFCA):**

```
W = catchment_weight(cost, weight, ...)
weighted_demand = W.T @ consumer_values          # Step 1: demand seen by each provider
ratios = provider_values / weighted_demand        # Provider capacity relative to demand
access = W @ ratios                               # Step 2: consumer access scores
```

For `return_type="supply"`, skip the demand normalization:
```
access = W @ provider_values
```

### `catchment_connections(cost, weight=None, consumer_ids=None, provider_ids=None, **weight_kwargs)`

Extract non-zero consumer-provider connections with their weights and costs.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cost` | sparse matrix, ndarray, or DataFrame | required | Cost matrix. |
| `weight` | `WeightSpec` | None | Passed to `catchment_weight()`. |
| `consumer_ids` | array-like or None | None | Labels for rows. Defaults to 0-based indices. |
| `provider_ids` | array-like or None | None | Labels for columns. Defaults to 0-based indices. |
| `**weight_kwargs` | | | Additional args passed to `catchment_weight()`. |

**Returns:** DataFrame with columns: `from_id`, `to_id`, `weight`, `cost`.

### `catchment_network(connections, from_start=None, to_start=None)`

Extract the subgraph of connections reachable from a starting consumer or provider via breadth-first search.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `connections` | DataFrame | required | Output from `catchment_connections()`. |
| `from_start` | hashable or None | None | Consumer ID to start traversal from. |
| `to_start` | hashable or None | None | Provider ID to start traversal from. |

**Returns:** Subset of `connections` DataFrame containing only the connected subgraph.

### `euclidean_cost(consumers_xy, providers_xy)`

Compute Euclidean distance matrix between consumer and provider coordinates.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `consumers_xy` | ndarray (n, 2) | Consumer coordinates (x, y). |
| `providers_xy` | ndarray (m, 2) | Provider coordinates (x, y). |

**Returns:** `np.ndarray` of shape (n, m) with pairwise Euclidean distances.

## Kernel Functions

Six built-in kernel functions, selected by name string:

| Name | Formula | Notes |
|------|---------|-------|
| `"linear"` | `max(0, (scale - cost) / scale)` | Linear decay to zero at `scale`. |
| `"gaussian"` | `exp(-cost^2 / (2 * scale^2))` | Standard Gaussian bell curve. |
| `"gravity"` | `cost^(-scale/2)` | Power-law decay. Note: the `sqrt(1/cost^scale)` form means the effective exponent is `scale/2`, not `scale`. Matches R package. |
| `"exponential"` | `exp(-cost * scale)` | Exponential decay. |
| `"logarithmic"` | `1 / (1 + ln(cost) / ln(scale))` | Log-base-scale decay. Implementation uses `np.log(cost) / np.log(scale)` since numpy has no direct base-n log. |
| `"logistic"` | `1 / (1 + exp(scale * cost))` | S-curve decay. |

Implemented as a `KERNELS` dict of callables at module level, each taking `(cost_array, scale)` and returning a weight array.

## FCA Variant Reference

All variants are parameter combinations on `catchment_ratio()`:

| Variant | Parameters |
|---------|------------|
| **2SFCA** (Luo & Wang 2003) | `weight=threshold` |
| **E2SFCA** (Lou & Qi 2009) | `weight=[(d1, w1), (d2, w2), ...]` |
| **KD2SFCA** (Dai 2010) | `weight="gaussian"` (or any kernel) |
| **3SFCA** (Wan et al. 2012) | `weight=..., normalize_weight=True` |
| **Modified 2SFCA** (Delamater 2013) | `adjust_providers=lambda w: w ** 2` |
| **Balanced FCA** (Paez et al. 2019) | `adjust_consumers=row_norm, adjust_providers=col_norm` |
| **Commute-based FCA** | `consumers_commutes=od_matrix` |

## 3SFCA Normalization Detail

The `normalize_weight=True` flag applies the Wan et al. (2012) selection probability formula:

```
w_normalized[i,j] = w[i,j] * (w[i,j] / sum_j(w[i,j]))
                   = w[i,j]^2 / sum_j(w[i,j])
```

This is NOT simple row normalization (`w[i,j] / sum_j(w[i,j])`). The quadratic effect gives disproportionately higher weight to nearer providers within a consumer's catchment.

Note: the existing inline Daycare Accessibility code uses simple row normalization. The validation refactor will adopt the R package's formula (above) and verify that the magnitude change is acceptable. The simple normalization can still be achieved via `adjust_consumers=lambda w: w / w.sum(axis=1, keepdims=True)` if needed.

## Commute-Based FCA Detail

When `consumers_commutes` is provided (a square OD matrix where entry [i,k] = number of people commuting from consumer location i to consumer location k):

1. Zero the diagonal of the OD matrix (within-location commutes are not cross-location demand). If the input has non-zero diagonal entries, the implementation zeros them.
2. Compute the fraction of each consumer's population that commutes to each location: `commute_frac[i,k] = od[i,k] / od[i,:].sum()`
3. Non-commuter fraction for consumer i: `stay_frac[i] = 1 - sum_k(commute_frac[i,k]) for k != i`
4. For each consumer i, effective demand at provider j is a blend:
   `effective_weight[i,j] = stay_frac[i] * W[i,j] + sum_k(commute_frac[i,k] * W[k,j])`
5. This effective weight replaces W in the standard 2SFCA formula.

This follows the R implementation (catchment_ratio.R lines 345-368).

## Sparse Matrix Strategy

- Cost and weight matrices stored as `scipy.sparse.csc_matrix` internally.
- Dense inputs (ndarray, DataFrame) converted to sparse on entry.
- DataFrame inputs: index used as consumer IDs, columns as provider IDs (for validation only).
- All matrix operations use sparse algebra (`@` operator, element-wise via `.multiply()`).
- Sparse format is most beneficial when `max_cost` creates real sparsity by zeroing out entries beyond the threshold. Without `max_cost`, a dense-in-values matrix converted to CSC adds overhead without memory savings. Callers working with dense travel time matrices (e.g., ~2000×2000 BG matrices where most pairs are reachable) should set `max_cost` to achieve meaningful sparsity.

## Aggregation Note

Geographic aggregation (block_group → tract → county → health_district) is handled by `sdc_core.geo`, not this module. However, FCA access scores require **population-weighted means** when aggregating, which `sdc_core.geo.aggregate_up` does not currently support. As a prerequisite, add a `weights` parameter to `sdc_core.geo.aggregate_up()` supporting population-weighted mean aggregation. This benefits all pipelines that aggregate rate/index data, not just catchment.

## Validation: Daycare Accessibility Refactor

Replace the inline 3SFCA implementation in `education/Daycare Accessibility/code/distribution/ingest.py`:

**Before** (inline, ~60 lines):
```python
def _gaussian_weight(time_mins, scale=18):
    return np.exp(-((time_mins / scale) ** 2))

def compute_3sfca(population_df, locations, travel_times, ...):
    ...
```

**After** (~5 lines):
```python
from sdc_core.catchment import catchment_ratio

access = catchment_ratio(
    consumers=consumer_df, providers=provider_df,
    cost=travel_time_matrix,
    weight="gaussian", scale=18 / np.sqrt(2),
    normalize_weight=True,  # 3SFCA
    consumers_id="geoid", consumers_value="population",
    providers_id="location_id", providers_value="capacity",
    return_type=1000,  # per 1,000 children
)
```

**Gaussian scale reconciliation:** The inline code uses `exp(-(cost/scale)^2)` while the module uses the standard form `exp(-cost^2 / (2*scale^2))`. These are equivalent when the module's scale = inline_scale / sqrt(2). So `scale=18` in the inline code maps to `scale=18/sqrt(2) ≈ 12.73` in the module. The Daycare refactor will use `scale=18 / np.sqrt(2)` to maintain numerical equivalence.

Validation proceeds in two steps:

1. **Scale reconciliation only** (normalization disabled): run the module with `normalize_weight=False` and compare against the inline code's pre-normalization weights. These should match at rtol=1e-6, confirming the Gaussian kernel scale mapping is correct.

2. **Normalization formula change** (intentional): the module uses Wan et al.'s quadratic formula (`w^2/rowsum`) while the inline code uses simple row normalization (`w/rowsum`). This is an algorithmic improvement, not a rounding difference, and will produce materially different access scores. Document the magnitude of change (expected: modest, since Gaussian weights are already concentrated on nearby providers) and adopt the R-package formula going forward.

## Testing

Tests in `packages/sdc-core/tests/test_catchment.py`:

1. **Kernel functions**: each kernel against hand-computed values
2. **Weight matrix**: binary threshold (exclusive), stepped, kernel, custom callable, max_cost, normalize
3. **2SFCA**: 3-consumer × 2-provider hand-computed example
4. **E2SFCA**: stepped weight variant of same example
5. **3SFCA**: normalized weight variant (verify quadratic formula)
6. **Modified/Balanced FCA**: adjust functions applied correctly
7. **Commute-based**: OD matrix blending verified against hand computation
8. **Return types**: original, supply, region, normalized, numeric, demand
9. **Connections**: correct non-zero extraction
10. **Network**: BFS traversal correctness
11. **Edge cases**: empty catchments, single provider, zero population, all-zero cost row
12. **Sparse/dense equivalence**: same result from sparse matrix and dense ndarray input
13. **Input validation**: mismatched dimensions raise ValueError

## Out of Scope

- Geographic aggregation (use `sdc_core.geo` — weighted mean support added as prerequisite)
- Census data download (use `sdc_core.census`)
- Census shape download (use `sdc_core.geo` or geopandas)
- Travel time / OSRM routing computation (pre-computed in `geographies/osrm/`)
- Test data simulation (`simulate_catchments` — low priority, add later if needed)
