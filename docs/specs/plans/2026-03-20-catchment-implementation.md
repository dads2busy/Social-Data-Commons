# sdc_core.catchment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a general-purpose floating catchment area module in sdc_core and validate it by refactoring the Daycare Accessibility pipeline.

**Architecture:** Single module `sdc_core/catchment.py` with 5 public functions. Weight matrix construction is separated from ratio computation. All FCA variants (2SFCA, E2SFCA, KD2SFCA, 3SFCA, modified, balanced, commute-based) are parameter combinations on `catchment_ratio()`. Sparse matrices throughout for scalability.

**Tech Stack:** scipy.sparse, scipy.spatial.distance, numpy, pandas (all already in monorepo).

**Spec:** `docs/specs/2026-03-20-catchment-module-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `packages/sdc-core/src/sdc_core/catchment.py` | CREATE — all catchment functions + KERNELS dict |
| `packages/sdc-core/src/sdc_core/__init__.py` | MODIFY — add catchment exports |
| `packages/sdc-core/src/sdc_core/geo.py` | MODIFY — add `weights` parameter to `aggregate_up()` |
| `packages/sdc-core/tests/test_catchment.py` | CREATE — all catchment tests |
| `packages/sdc-core/tests/test_geo_weighted.py` | CREATE — tests for weighted aggregation in geo.py |
| `education/Daycare Accessibility/code/distribution/ingest.py` | MODIFY — replace inline 3SFCA with catchment_ratio |

---

### Task 1: Kernel Functions and euclidean_cost

**Files:**
- Create: `packages/sdc-core/src/sdc_core/catchment.py`
- Create: `packages/sdc-core/tests/test_catchment.py`

- [ ] **Step 1: Write failing tests for all 6 kernels + euclidean_cost**

```python
"""Tests for sdc_core.catchment."""

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose
from scipy import sparse


class TestKernels:
    """Test each kernel function against hand-computed values."""

    def test_gaussian(self):
        from sdc_core.catchment import KERNELS
        cost = np.array([0.0, 1.0, 2.0, 5.0])
        scale = 2.0
        result = KERNELS["gaussian"](cost, scale)
        expected = np.exp(-cost**2 / (2 * scale**2))
        assert_allclose(result, expected)

    def test_linear(self):
        from sdc_core.catchment import KERNELS
        cost = np.array([0.0, 1.0, 2.0, 5.0])
        scale = 3.0
        result = KERNELS["linear"](cost, scale)
        expected = np.maximum(0, (scale - cost) / scale)
        assert_allclose(result, expected)

    def test_exponential(self):
        from sdc_core.catchment import KERNELS
        cost = np.array([0.0, 1.0, 2.0])
        scale = 0.5
        result = KERNELS["exponential"](cost, scale)
        expected = np.exp(-cost * scale)
        assert_allclose(result, expected)

    def test_gravity(self):
        from sdc_core.catchment import KERNELS
        cost = np.array([1.0, 2.0, 4.0])
        scale = 2.0
        result = KERNELS["gravity"](cost, scale)
        # sqrt(1 / cost^scale) = cost^(-scale/2)
        expected = cost ** (-scale / 2)
        assert_allclose(result, expected)

    def test_logistic(self):
        from sdc_core.catchment import KERNELS
        cost = np.array([0.0, 1.0, 2.0])
        scale = 1.0
        result = KERNELS["logistic"](cost, scale)
        expected = 1.0 / (1.0 + np.exp(scale * cost))
        assert_allclose(result, expected)

    def test_logarithmic(self):
        from sdc_core.catchment import KERNELS
        cost = np.array([1.0, 2.0, 10.0])
        scale = 10.0
        result = KERNELS["logarithmic"](cost, scale)
        expected = 1.0 / (1.0 + np.log(cost) / np.log(scale))
        assert_allclose(result, expected)


class TestEuclideanCost:

    def test_basic(self):
        from sdc_core.catchment import euclidean_cost
        consumers = np.array([[0, 0], [3, 4]])
        providers = np.array([[0, 0], [1, 0]])
        result = euclidean_cost(consumers, providers)
        assert result.shape == (2, 2)
        assert_allclose(result[0, 0], 0.0)
        assert_allclose(result[0, 1], 1.0)
        assert_allclose(result[1, 0], 5.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/test_catchment.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sdc_core.catchment'`

- [ ] **Step 3: Implement KERNELS dict and euclidean_cost**

In `packages/sdc-core/src/sdc_core/catchment.py`:

```python
"""Spatial accessibility via floating catchment area (FCA) methods.

Implements 2SFCA, E2SFCA, KD2SFCA, 3SFCA, modified 2SFCA, balanced FCA,
and commute-based FCA as parameter variations on catchment_ratio().

References
----------
- 2SFCA: Luo & Wang (2003) doi:10.1068/b29120
- E2SFCA: Lou & Qi (2009) doi:10.1016/j.healthplace.2009.06.002
- KD2SFCA: Dai (2010) doi:10.1016/j.healthplace.2010.06.012
- 3SFCA: Wan, Zou & Sternberg (2012) doi:10.1080/13658816.2011.624987
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Union

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.spatial.distance import cdist

WeightSpec = Union[None, float, list[tuple[float, float]], str, Callable[[np.ndarray], np.ndarray]]

# --- Kernel functions ---
# Each takes (cost_array, scale) and returns weight_array.

KERNELS: dict[str, Callable[[np.ndarray, float], np.ndarray]] = {
    "linear": lambda c, s: np.maximum(0, (s - c) / s),
    "gaussian": lambda c, s: np.exp(-c**2 / (2 * s**2)),
    "gravity": lambda c, s: np.where(c > 0, c ** (-s / 2), 0.0),
    "exponential": lambda c, s: np.exp(-c * s),
    "logarithmic": lambda c, s: np.where(
        c > 0, 1.0 / (1.0 + np.log(c) / np.log(s)), 0.0
    ),
    "logistic": lambda c, s: 1.0 / (1.0 + np.exp(s * c)),
}


def euclidean_cost(consumers_xy: np.ndarray, providers_xy: np.ndarray) -> np.ndarray:
    """Compute Euclidean distance matrix between consumer and provider coordinates.

    Parameters
    ----------
    consumers_xy : ndarray of shape (n, 2)
        Consumer coordinates (x, y).
    providers_xy : ndarray of shape (m, 2)
        Provider coordinates (x, y).

    Returns
    -------
    ndarray of shape (n, m)
        Pairwise Euclidean distances.
    """
    return cdist(np.asarray(consumers_xy), np.asarray(providers_xy), metric="euclidean")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/test_catchment.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/ads7fg/git/sdc-monorepo
git add packages/sdc-core/src/sdc_core/catchment.py packages/sdc-core/tests/test_catchment.py
git commit -m "feat(catchment): add kernel functions and euclidean_cost helper"
```

---

### Task 2: catchment_weight

**Files:**
- Modify: `packages/sdc-core/src/sdc_core/catchment.py`
- Modify: `packages/sdc-core/tests/test_catchment.py`

- [ ] **Step 1: Write failing tests for catchment_weight**

Add to `test_catchment.py`:

```python
from sdc_core.catchment import catchment_weight


class TestCatchmentWeight:

    def test_none_weight_returns_cost_as_sparse(self):
        cost = np.array([[1.0, 2.0], [3.0, 4.0]])
        w = catchment_weight(cost, weight=None)
        assert sparse.issparse(w)
        assert_allclose(w.toarray(), cost)

    def test_binary_threshold_exclusive(self):
        cost = np.array([[5.0, 15.0, 25.0]])
        w = catchment_weight(cost, weight=20.0)
        # Exclusive: cost < 20
        expected = np.array([[1.0, 1.0, 0.0]])
        assert_allclose(w.toarray(), expected)

    def test_stepped_weights(self):
        cost = np.array([[5.0, 15.0, 25.0]])
        w = catchment_weight(cost, weight=[(10, 1.0), (20, 0.5), (30, 0.25)])
        expected = np.array([[1.0, 0.5, 0.25]])
        assert_allclose(w.toarray(), expected)

    def test_kernel_string(self):
        cost = np.array([[0.0, 1.0], [2.0, 3.0]])
        w = catchment_weight(cost, weight="gaussian", scale=2.0)
        expected = np.exp(-cost**2 / (2 * 2.0**2))
        assert_allclose(w.toarray(), expected, atol=1e-10)

    def test_callable_weight(self):
        cost = np.array([[1.0, 2.0]])
        w = catchment_weight(cost, weight=lambda c: 1.0 / c)
        expected = np.array([[1.0, 0.5]])
        assert_allclose(w.toarray(), expected)

    def test_max_cost(self):
        cost = np.array([[5.0, 15.0, 25.0]])
        w = catchment_weight(cost, weight="gaussian", scale=10.0, max_cost=20.0)
        result = w.toarray()
        assert result[0, 2] == 0.0  # cost=25 > max_cost=20
        assert result[0, 0] > 0.0

    def test_normalize_weight_3sfca(self):
        # 3SFCA normalization: w^2 / rowsum(w)
        cost = np.array([[1.0, 2.0, 3.0]])
        w_raw = catchment_weight(cost, weight=10.0)  # binary: all 1s
        w_norm = catchment_weight(cost, weight=10.0, normalize_weight=True)
        raw = w_raw.toarray()
        row_sum = raw.sum(axis=1, keepdims=True)
        expected = raw * (raw / row_sum)
        assert_allclose(w_norm.toarray(), expected)

    def test_adjust_zeros_skipped_when_weight_none(self):
        cost = np.array([[0.0, 1.0]])
        w = catchment_weight(cost, weight=None)
        # Zero in cost should remain zero (not adjusted to 1e-6)
        assert w.toarray()[0, 0] == 0.0

    def test_adjust_zeros_applied_for_kernel(self):
        cost = np.array([[0.0, 1.0]])
        # Gravity kernel: cost^(-scale/2). At cost=0 without adjust_zeros → inf.
        # With adjust_zeros=1e-6, cost becomes 1e-6 → finite result.
        w = catchment_weight(cost, weight="gravity", scale=2.0)
        assert np.all(np.isfinite(w.toarray()))
        assert w.toarray()[0, 0] > 0  # adjusted zero produced a weight

    def test_sparse_input(self):
        cost_dense = np.array([[1.0, 0.0], [0.0, 2.0]])
        cost_sparse = sparse.csc_matrix(cost_dense)
        w_dense = catchment_weight(cost_dense, weight="gaussian", scale=2.0)
        w_sparse = catchment_weight(cost_sparse, weight="gaussian", scale=2.0)
        assert_allclose(w_dense.toarray(), w_sparse.toarray())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/test_catchment.py::TestCatchmentWeight -v`
Expected: FAIL — `ImportError: cannot import name 'catchment_weight'`

- [ ] **Step 3: Implement catchment_weight**

Add to `catchment.py`:

```python
def _to_sparse(x):
    """Convert input to CSC sparse matrix."""
    if sparse.issparse(x):
        return x.tocsc()
    if isinstance(x, pd.DataFrame):
        return sparse.csc_matrix(x.values)
    return sparse.csc_matrix(np.asarray(x, dtype=float))


def catchment_weight(
    cost,
    weight: WeightSpec = None,
    max_cost: float | None = None,
    scale: float = 2.0,
    normalize_weight: bool = False,
    adjust_zeros: float | bool = 1e-6,
) -> sparse.csc_matrix:
    """Construct a weight matrix from a cost matrix using kernel decay functions.

    Parameters
    ----------
    cost : sparse matrix, ndarray, or DataFrame
        Cost/distance matrix. Rows = consumers, columns = providers.
    weight : WeightSpec
        None = use cost as weight. float = binary threshold (exclusive).
        list of (distance, weight) tuples = stepped. str = kernel name.
        callable = custom function (cost_array) -> weight_array.
    max_cost : float or None
        Zero out weights where cost exceeds this value.
    scale : float
        Scale parameter for kernel functions.
    normalize_weight : bool
        Apply 3SFCA selection probability: w * (w / rowsum).
    adjust_zeros : float or False
        Replace zeros in cost with this value. Skipped when weight is None.

    Returns
    -------
    scipy.sparse.csc_matrix
    """
    cost_sp = _to_sparse(cost)
    c = cost_sp.toarray().astype(float)

    if weight is None:
        w = c.copy()
    elif callable(weight) and not isinstance(weight, str):
        # Custom function
        if adjust_zeros and isinstance(adjust_zeros, (int, float)):
            c = np.where((c == 0) & (c >= 0), adjust_zeros, c)
        w = np.asarray(weight(c), dtype=float)
    elif isinstance(weight, str):
        # Named kernel
        if weight not in KERNELS:
            raise ValueError(f"Unknown kernel '{weight}'. Choose from: {list(KERNELS)}")
        if adjust_zeros and isinstance(adjust_zeros, (int, float)):
            c = np.where((c == 0) & (c >= 0), adjust_zeros, c)
        w = KERNELS[weight](c, scale)
    elif isinstance(weight, (int, float)) and not isinstance(weight, bool):
        # Binary threshold (exclusive)
        if adjust_zeros and isinstance(adjust_zeros, (int, float)):
            c = np.where((c == 0) & (c >= 0), adjust_zeros, c)
        w = np.where((c > 0) & (c < float(weight)), 1.0, 0.0)
    elif isinstance(weight, list):
        # Stepped weights
        if adjust_zeros and isinstance(adjust_zeros, (int, float)):
            c = np.where((c == 0) & (c >= 0), adjust_zeros, c)
        steps = sorted(weight, key=lambda x: x[0])
        w = np.zeros_like(c)
        for dist, wt in steps:
            w = np.where((c > 0) & (c < dist) & (w == 0), wt, w)
    else:
        raise TypeError(f"Unsupported weight type: {type(weight)}")

    # Zero out entries beyond max_cost
    if max_cost is not None:
        cost_arr = cost_sp.toarray().astype(float)
        w[cost_arr > max_cost] = 0.0

    # Zero out non-finite, negative weight, and negative-cost entries
    w[~np.isfinite(w)] = 0.0
    w[w < 0] = 0.0
    w[cost_sp.toarray() < 0] = 0.0

    # 3SFCA normalization: w * (w / rowsum)
    if normalize_weight:
        row_sums = w.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        w = w * (w / row_sums)

    return sparse.csc_matrix(w)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/test_catchment.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/ads7fg/git/sdc-monorepo
git add packages/sdc-core/src/sdc_core/catchment.py packages/sdc-core/tests/test_catchment.py
git commit -m "feat(catchment): implement catchment_weight with all weight types"
```

---

### Task 3: catchment_ratio — core 2SFCA and return types

**Files:**
- Modify: `packages/sdc-core/src/sdc_core/catchment.py`
- Modify: `packages/sdc-core/tests/test_catchment.py`

- [ ] **Step 1: Write failing tests for 2SFCA and return types**

Add to `test_catchment.py`:

```python
from sdc_core.catchment import catchment_ratio


class TestCatchmentRatio:
    """3 consumers, 2 providers hand-computed 2SFCA example."""

    @pytest.fixture
    def setup(self):
        consumers = pd.DataFrame({"geoid": ["C1", "C2", "C3"], "value": [100, 200, 150]})
        providers = pd.DataFrame({"geoid": ["P1", "P2"], "value": [50, 30]})
        # Binary weights: C1→P1, C2→P1+P2, C3→P2
        cost = np.array([
            [5.0, 25.0],   # C1: within P1 only
            [8.0, 8.0],    # C2: within both
            [25.0, 5.0],   # C3: within P2 only
        ])
        return consumers, providers, cost

    def test_2sfca_original(self, setup):
        consumers, providers, cost = setup
        result = catchment_ratio(
            consumers, providers, cost,
            weight=10.0,  # binary threshold
            return_type="original",
        )
        assert isinstance(result, pd.Series)
        assert list(result.index) == ["C1", "C2", "C3"]
        # Step 1: weighted_demand P1 = 100+200=300, P2 = 200+150=350
        # Step 1: ratios P1 = 50/300, P2 = 30/350
        # Step 2: C1 = 50/300, C2 = 50/300 + 30/350, C3 = 30/350
        assert_allclose(result["C1"], 50 / 300, rtol=1e-10)
        assert_allclose(result["C2"], 50 / 300 + 30 / 350, rtol=1e-10)
        assert_allclose(result["C3"], 30 / 350, rtol=1e-10)

    def test_return_type_supply(self, setup):
        consumers, providers, cost = setup
        result = catchment_ratio(consumers, providers, cost, weight=10.0, return_type="supply")
        # supply: W @ provider_values (no demand normalization)
        # C1: 1*50 + 0*30 = 50, C2: 1*50 + 1*30 = 80, C3: 0*50 + 1*30 = 30
        assert_allclose(result["C1"], 50.0)
        assert_allclose(result["C2"], 80.0)
        assert_allclose(result["C3"], 30.0)

    def test_return_type_numeric(self, setup):
        consumers, providers, cost = setup
        result_raw = catchment_ratio(consumers, providers, cost, weight=10.0, return_type="original")
        result_1k = catchment_ratio(consumers, providers, cost, weight=10.0, return_type=1000)
        assert_allclose(result_1k.values, result_raw.values * 1000)

    def test_return_type_demand(self, setup):
        consumers, providers, cost = setup
        result = catchment_ratio(consumers, providers, cost, weight=10.0, return_type="demand")
        assert isinstance(result, pd.Series)
        assert list(result.index) == ["P1", "P2"]
        # demand = W.T @ consumer_values
        assert_allclose(result["P1"], 300.0)
        assert_allclose(result["P2"], 350.0)

    def test_return_type_normalized(self, setup):
        consumers, providers, cost = setup
        result = catchment_ratio(consumers, providers, cost, weight=10.0, return_type="normalized")
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_return_type_region(self, setup):
        consumers, providers, cost = setup
        result = catchment_ratio(consumers, providers, cost, weight=10.0, return_type="region")
        # region = access * consumer_value
        result_raw = catchment_ratio(consumers, providers, cost, weight=10.0, return_type="original")
        expected = result_raw * consumers["value"].values
        assert_allclose(result.values, expected.values)

    def test_dimension_mismatch_raises(self):
        consumers = pd.DataFrame({"geoid": ["C1", "C2"], "value": [100, 200]})
        providers = pd.DataFrame({"geoid": ["P1"], "value": [50]})
        cost = np.array([[1.0, 2.0]])  # 1 row but 2 consumers
        with pytest.raises(ValueError, match="dimension"):
            catchment_ratio(consumers, providers, cost, weight=10.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/test_catchment.py::TestCatchmentRatio -v`
Expected: FAIL

- [ ] **Step 3: Implement catchment_ratio**

Add to `catchment.py`:

```python
def catchment_ratio(
    consumers: pd.DataFrame,
    providers: pd.DataFrame,
    cost,
    weight: WeightSpec = None,
    scale: float = 2.0,
    max_cost: float | None = None,
    normalize_weight: bool = False,
    adjust_consumers: Callable | None = None,
    adjust_providers: Callable | None = None,
    consumers_commutes=None,
    consumers_id: str = "geoid",
    consumers_value: str = "value",
    providers_id: str = "geoid",
    providers_value: str = "value",
    adjust_zeros: float | bool = 1e-6,
    return_type: str | int | float = "original",
) -> pd.Series:
    """Calculate provider-to-consumer ratios within floating catchment areas.

    Parameters
    ----------
    consumers : DataFrame
        Consumer data with ID and value (population) columns.
    providers : DataFrame
        Provider data with ID and value (capacity/supply) columns.
    cost : sparse matrix, ndarray, or DataFrame
        Cost matrix. Rows = consumers, columns = providers.
    weight : WeightSpec
        Passed to catchment_weight().
    scale : float
        Passed to catchment_weight().
    max_cost : float or None
        Passed to catchment_weight().
    normalize_weight : bool
        Apply 3SFCA selection probability normalization.
    adjust_consumers : callable or None
        Function applied to weight matrix before consumer aggregation.
    adjust_providers : callable or None
        Function applied to weight matrix before provider ratio computation.
    consumers_commutes : ndarray, sparse matrix, or None
        Square OD matrix for commute-based FCA.
    consumers_id : str
        Column name for consumer IDs.
    consumers_value : str
        Column name for consumer values.
    providers_id : str
        Column name for provider IDs.
    providers_value : str
        Column name for provider values.
    adjust_zeros : float or False
        Passed to catchment_weight().
    return_type : str or numeric
        "original", "supply", "region", "normalized", "demand", or numeric multiplier.

    Returns
    -------
    pd.Series
        Indexed by consumer ID (or provider ID for return_type="demand").
    """
    c_ids = consumers[consumers_id].values
    c_vals = consumers[consumers_value].values.astype(float)
    p_ids = providers[providers_id].values
    p_vals = providers[providers_value].values.astype(float)

    # Validate dimensions
    cost_sp = _to_sparse(cost)
    if cost_sp.shape[0] != len(consumers):
        raise ValueError(
            f"Cost matrix dimension mismatch: {cost_sp.shape[0]} rows "
            f"but {len(consumers)} consumers"
        )
    if cost_sp.shape[1] != len(providers):
        raise ValueError(
            f"Cost matrix dimension mismatch: {cost_sp.shape[1]} columns "
            f"but {len(providers)} providers"
        )

    # Build weight matrix
    W = catchment_weight(cost, weight, max_cost, scale, normalize_weight, adjust_zeros)

    # Apply commute-based blending
    if consumers_commutes is not None:
        W = _apply_commute_blending(W, consumers_commutes)

    # Apply adjustment functions.
    # W_providers is used in step 1 (computing provider demand denominators).
    # W_consumers is used in step 2 (computing consumer access scores).
    W_consumers = W.toarray().copy()
    W_providers = W.toarray().copy()
    if adjust_consumers is not None:
        W_consumers = np.asarray(adjust_consumers(W_consumers))
    if adjust_providers is not None:
        W_providers = np.asarray(adjust_providers(W_providers))

    # Return type: demand
    if return_type == "demand":
        demand = W_consumers.T @ c_vals
        return pd.Series(demand, index=p_ids)

    # Return type: supply (no demand normalization)
    if return_type == "supply":
        supply = W_consumers @ p_vals
        return pd.Series(supply, index=c_ids)

    # Standard 2SFCA
    # Step 1: weighted demand per provider
    weighted_demand = W_providers.T @ c_vals
    # Avoid division by zero
    weighted_demand = np.where(weighted_demand > 0, weighted_demand, np.inf)
    ratios = p_vals / weighted_demand

    # Step 2: consumer access scores
    access = W_consumers @ ratios

    # Format output
    if isinstance(return_type, (int, float)) and not isinstance(return_type, bool):
        access = access * float(return_type)
    elif return_type == "region":
        access = access * c_vals
    elif return_type == "normalized":
        a_min, a_max = access.min(), access.max()
        if a_max > a_min:
            access = (access - a_min) / (a_max - a_min)
        else:
            access = np.zeros_like(access)
    elif return_type != "original":
        raise ValueError(f"Unknown return_type: {return_type!r}")

    return pd.Series(access, index=c_ids)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/test_catchment.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/ads7fg/git/sdc-monorepo
git add packages/sdc-core/src/sdc_core/catchment.py packages/sdc-core/tests/test_catchment.py
git commit -m "feat(catchment): implement catchment_ratio with 2SFCA and all return types"
```

---

### Task 4: FCA Variants — E2SFCA, 3SFCA, Modified, Balanced

**Files:**
- Modify: `packages/sdc-core/tests/test_catchment.py`

- [ ] **Step 1: Write validation tests for FCA variants** (these exercise parameter combinations already implemented in Task 3)

Add to `test_catchment.py`:

```python
class TestFCAVariants:

    @pytest.fixture
    def setup(self):
        consumers = pd.DataFrame({"geoid": ["C1", "C2", "C3"], "value": [100, 200, 150]})
        providers = pd.DataFrame({"geoid": ["P1", "P2"], "value": [50, 30]})
        cost = np.array([[5.0, 25.0], [8.0, 8.0], [25.0, 5.0]])
        return consumers, providers, cost

    def test_e2sfca_stepped(self, setup):
        consumers, providers, cost = setup
        result = catchment_ratio(
            consumers, providers, cost,
            weight=[(10, 1.0), (30, 0.5)],
        )
        # C1→P1: cost=5 < 10 → w=1.0, C1→P2: cost=25 < 30 → w=0.5
        # C2→P1: cost=8 < 10 → w=1.0, C2→P2: cost=8 < 10 → w=1.0
        # C3→P1: cost=25 < 30 → w=0.5, C3→P2: cost=5 < 10 → w=1.0
        assert isinstance(result, pd.Series)
        assert len(result) == 3
        # Verify it's different from binary
        result_binary = catchment_ratio(consumers, providers, cost, weight=30.0)
        assert not np.allclose(result.values, result_binary.values)

    def test_3sfca_normalized(self, setup):
        consumers, providers, cost = setup
        result = catchment_ratio(
            consumers, providers, cost,
            weight=30.0,
            normalize_weight=True,
        )
        # Just verify it runs and differs from non-normalized
        result_non = catchment_ratio(consumers, providers, cost, weight=30.0)
        assert not np.allclose(result.values, result_non.values)

    def test_modified_2sfca(self, setup):
        consumers, providers, cost = setup
        result = catchment_ratio(
            consumers, providers, cost,
            weight=30.0,
            adjust_providers=lambda w: w ** 2,
        )
        result_base = catchment_ratio(consumers, providers, cost, weight=30.0)
        assert not np.allclose(result.values, result_base.values)

    def test_balanced_fca(self, setup):
        consumers, providers, cost = setup
        row_norm = lambda w: w / np.where(w.sum(axis=1, keepdims=True) > 0, w.sum(axis=1, keepdims=True), 1)
        col_norm = lambda w: w / np.where(w.sum(axis=0, keepdims=True) > 0, w.sum(axis=0, keepdims=True), 1)
        result = catchment_ratio(
            consumers, providers, cost,
            weight=30.0,
            adjust_consumers=row_norm,
            adjust_providers=col_norm,
        )
        assert isinstance(result, pd.Series)
        assert len(result) == 3
```

- [ ] **Step 2: Run validation tests**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/test_catchment.py::TestFCAVariants -v`
Expected: All PASS (these validate parameter combinations from Task 3)

- [ ] **Step 3: Commit**

```bash
cd /Users/ads7fg/git/sdc-monorepo
git add packages/sdc-core/tests/test_catchment.py
git commit -m "test(catchment): add tests for E2SFCA, 3SFCA, modified, balanced FCA variants"
```

---

### Task 5: Commute-Based FCA

**Files:**
- Modify: `packages/sdc-core/src/sdc_core/catchment.py`
- Modify: `packages/sdc-core/tests/test_catchment.py`

- [ ] **Step 1: Write failing test for commute-based FCA**

Add to `test_catchment.py`:

```python
class TestCommuteBased:

    def test_commute_blending(self):
        consumers = pd.DataFrame({"geoid": ["C1", "C2"], "value": [100, 200]})
        providers = pd.DataFrame({"geoid": ["P1"], "value": [50]})
        cost = np.array([[5.0], [5.0]])
        # OD matrix: 20 people commute C1→C2, 10 people commute C2→C1
        od = np.array([[0, 20], [10, 0]])
        result = catchment_ratio(
            consumers, providers, cost,
            weight=10.0,
            consumers_commutes=od,
        )
        # Without commutes: both consumers see P1 at cost 5, equal access
        result_no_commute = catchment_ratio(consumers, providers, cost, weight=10.0)
        # With commutes: demand distribution shifts
        assert isinstance(result, pd.Series)
        assert len(result) == 2

    def test_commute_diagonal_zeroed(self):
        consumers = pd.DataFrame({"geoid": ["C1", "C2"], "value": [100, 200]})
        providers = pd.DataFrame({"geoid": ["P1"], "value": [50]})
        cost = np.array([[5.0], [5.0]])
        # OD with non-zero diagonal (should be zeroed internally)
        od = np.array([[50, 20], [10, 100]])
        od_clean = np.array([[0, 20], [10, 0]])
        result_dirty = catchment_ratio(consumers, providers, cost, weight=10.0, consumers_commutes=od)
        result_clean = catchment_ratio(consumers, providers, cost, weight=10.0, consumers_commutes=od_clean)
        assert_allclose(result_dirty.values, result_clean.values)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/test_catchment.py::TestCommuteBased -v`
Expected: FAIL — `_apply_commute_blending` not defined

- [ ] **Step 3: Implement _apply_commute_blending**

Add to `catchment.py` before `catchment_ratio`:

```python
def _apply_commute_blending(
    W: sparse.csc_matrix, commutes
) -> sparse.csc_matrix:
    """Blend weight matrix with commute OD flows.

    Parameters
    ----------
    W : sparse matrix
        Original weight matrix (n_consumers x n_providers).
    commutes : ndarray or sparse matrix
        Square OD matrix (n_consumers x n_consumers).

    Returns
    -------
    sparse.csc_matrix
        Blended weight matrix.
    """
    od = np.asarray(commutes, dtype=float).copy()
    n = od.shape[0]

    # Zero the diagonal
    np.fill_diagonal(od, 0.0)

    # Commute fractions
    row_sums = od.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0  # avoid division by zero
    frac = od / row_sums

    # Stay fraction per consumer
    stay = 1.0 - frac.sum(axis=1, keepdims=True)

    # Blend: effective_W[i,j] = stay[i]*W[i,j] + sum_k(frac[i,k]*W[k,j])
    W_dense = W.toarray()
    blended = stay * W_dense + frac @ W_dense

    return sparse.csc_matrix(blended)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/test_catchment.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/ads7fg/git/sdc-monorepo
git add packages/sdc-core/src/sdc_core/catchment.py packages/sdc-core/tests/test_catchment.py
git commit -m "feat(catchment): implement commute-based FCA blending"
```

---

### Task 6: catchment_connections and catchment_network

**Files:**
- Modify: `packages/sdc-core/src/sdc_core/catchment.py`
- Modify: `packages/sdc-core/tests/test_catchment.py`

- [ ] **Step 1: Write failing tests**

Add to `test_catchment.py`:

```python
from sdc_core.catchment import catchment_connections, catchment_network


class TestConnections:

    def test_basic_connections(self):
        cost = np.array([[5.0, 25.0], [8.0, 8.0], [25.0, 5.0]])
        result = catchment_connections(
            cost, weight=10.0,
            consumer_ids=["C1", "C2", "C3"],
            provider_ids=["P1", "P2"],
        )
        assert isinstance(result, pd.DataFrame)
        assert set(result.columns) == {"from_id", "to_id", "weight", "cost"}
        # C1→P1 (cost=5), C2→P1 (cost=8), C2→P2 (cost=8), C3→P2 (cost=5)
        assert len(result) == 4

    def test_default_ids(self):
        cost = np.array([[5.0, 25.0]])
        result = catchment_connections(cost, weight=10.0)
        assert result["from_id"].iloc[0] == 0
        assert result["to_id"].iloc[0] == 0


class TestNetwork:

    def test_basic_network(self):
        connections = pd.DataFrame({
            "from_id": ["C1", "C2", "C2", "C3", "C4"],
            "to_id": ["P1", "P1", "P2", "P2", "P3"],
            "weight": [1, 1, 1, 1, 1],
            "cost": [5, 8, 8, 5, 5],
        })
        # Starting from C1: C1→P1→C2→P2→C3 (connected subgraph)
        result = catchment_network(connections, from_start="C1")
        assert "C4" not in result["from_id"].values  # C4 only connects to P3
        assert "P3" not in result["to_id"].values
        assert len(result) == 4  # C1→P1, C2→P1, C2→P2, C3→P2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/test_catchment.py::TestConnections -v`
Expected: FAIL

- [ ] **Step 3: Implement catchment_connections and catchment_network**

Add to `catchment.py`:

```python
def catchment_connections(
    cost,
    weight: WeightSpec = None,
    consumer_ids=None,
    provider_ids=None,
    **weight_kwargs,
) -> pd.DataFrame:
    """Extract non-zero consumer-provider connections with weights and costs.

    Parameters
    ----------
    cost : sparse matrix, ndarray, or DataFrame
        Cost matrix.
    weight : WeightSpec
        Passed to catchment_weight().
    consumer_ids : array-like or None
        Labels for rows. Defaults to 0-based indices.
    provider_ids : array-like or None
        Labels for columns. Defaults to 0-based indices.

    Returns
    -------
    DataFrame
        Columns: from_id, to_id, weight, cost.
    """
    W = catchment_weight(cost, weight, **weight_kwargs)
    cost_arr = _to_sparse(cost).toarray()

    n_rows, n_cols = W.shape
    if consumer_ids is None:
        consumer_ids = np.arange(n_rows)
    if provider_ids is None:
        provider_ids = np.arange(n_cols)

    W_coo = W.tocoo()
    rows = []
    for i, j, w in zip(W_coo.row, W_coo.col, W_coo.data):
        if w > 0:
            rows.append({
                "from_id": consumer_ids[i],
                "to_id": provider_ids[j],
                "weight": w,
                "cost": cost_arr[i, j],
            })

    return pd.DataFrame(rows, columns=["from_id", "to_id", "weight", "cost"])


def catchment_network(
    connections: pd.DataFrame,
    from_start=None,
    to_start=None,
) -> pd.DataFrame:
    """Extract connected subgraph via breadth-first search.

    Parameters
    ----------
    connections : DataFrame
        Output from catchment_connections(). Must have from_id and to_id columns.
    from_start : hashable or None
        Consumer ID to start from.
    to_start : hashable or None
        Provider ID to start from.

    Returns
    -------
    DataFrame
        Subset of connections in the connected subgraph.
    """
    froms = set()
    tos = set()

    if from_start is not None:
        froms.add(from_start)
    if to_start is not None:
        tos.add(to_start)
    if not froms and not tos:
        froms.add(connections["from_id"].iloc[0])

    while True:
        # Find all tos reachable from current froms
        new_tos = set(connections[connections["from_id"].isin(froms)]["to_id"])
        # Find all froms that reach current tos
        new_froms = set(connections[connections["to_id"].isin(tos)]["from_id"])

        combined_froms = froms | new_froms
        combined_tos = tos | new_tos

        if combined_froms == froms and combined_tos == tos:
            break
        froms = combined_froms
        tos = combined_tos

    mask = connections["from_id"].isin(froms) & connections["to_id"].isin(tos)
    return connections[mask].reset_index(drop=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/test_catchment.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/ads7fg/git/sdc-monorepo
git add packages/sdc-core/src/sdc_core/catchment.py packages/sdc-core/tests/test_catchment.py
git commit -m "feat(catchment): implement catchment_connections and catchment_network"
```

---

### Task 7: Edge Cases and Exports

**Files:**
- Modify: `packages/sdc-core/tests/test_catchment.py`
- Modify: `packages/sdc-core/src/sdc_core/__init__.py`

- [ ] **Step 1: Write edge case validation tests** (expected to pass with existing implementation)

Add to `test_catchment.py`:

```python
class TestEdgeCases:

    def test_empty_catchment(self):
        consumers = pd.DataFrame({"geoid": ["C1"], "value": [100]})
        providers = pd.DataFrame({"geoid": ["P1"], "value": [50]})
        cost = np.array([[100.0]])  # beyond any reasonable threshold
        result = catchment_ratio(consumers, providers, cost, weight=10.0)
        assert_allclose(result["C1"], 0.0)

    def test_single_provider(self):
        consumers = pd.DataFrame({"geoid": ["C1", "C2"], "value": [100, 200]})
        providers = pd.DataFrame({"geoid": ["P1"], "value": [50]})
        cost = np.array([[5.0], [5.0]])
        result = catchment_ratio(consumers, providers, cost, weight=10.0)
        # Both consumers share P1: ratio = 50/300, both get same score
        assert_allclose(result["C1"], 50 / 300)
        assert_allclose(result["C2"], 50 / 300)

    def test_zero_population_consumer(self):
        consumers = pd.DataFrame({"geoid": ["C1", "C2"], "value": [0, 200]})
        providers = pd.DataFrame({"geoid": ["P1"], "value": [50]})
        cost = np.array([[5.0], [5.0]])
        result = catchment_ratio(consumers, providers, cost, weight=10.0)
        # Zero-pop consumer still gets access score
        assert np.isfinite(result["C1"])

    def test_all_zero_cost_row(self):
        """Consumer with all-zero costs (unreachable) should get zero access."""
        consumers = pd.DataFrame({"geoid": ["C1", "C2"], "value": [100, 200]})
        providers = pd.DataFrame({"geoid": ["P1"], "value": [50]})
        cost = np.array([[0.0], [5.0]])  # C1 has zero cost (unreachable after adjust)
        result = catchment_ratio(consumers, providers, cost, weight=10.0)
        assert np.isfinite(result["C1"])

    def test_sparse_dense_equivalence(self):
        consumers = pd.DataFrame({"geoid": ["C1", "C2"], "value": [100, 200]})
        providers = pd.DataFrame({"geoid": ["P1", "P2"], "value": [50, 30]})
        cost_dense = np.array([[5.0, 25.0], [8.0, 8.0]])
        cost_sparse = sparse.csc_matrix(cost_dense)
        r_dense = catchment_ratio(consumers, providers, cost_dense, weight=10.0)
        r_sparse = catchment_ratio(consumers, providers, cost_sparse, weight=10.0)
        assert_allclose(r_dense.values, r_sparse.values)
```

- [ ] **Step 2: Run validation tests**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/test_catchment.py::TestEdgeCases -v`
Expected: All PASS (validates existing implementation handles edge cases)

- [ ] **Step 3: Add catchment exports to __init__.py**

Add to `packages/sdc-core/src/sdc_core/__init__.py`:

```python
from sdc_core.catchment import (
    KERNELS,
    WeightSpec,
    catchment_connections,
    catchment_network,
    catchment_ratio,
    catchment_weight,
    euclidean_cost,
)
```

And add to `__all__`:
```python
"KERNELS",
"WeightSpec",
"catchment_connections",
"catchment_network",
"catchment_ratio",
"catchment_weight",
"euclidean_cost",
```

- [ ] **Step 4: Verify import works**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run python -c "from sdc_core import catchment_ratio; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd /Users/ads7fg/git/sdc-monorepo
git add packages/sdc-core/src/sdc_core/__init__.py packages/sdc-core/tests/test_catchment.py
git commit -m "feat(catchment): add edge case tests and public exports"
```

---

### Task 8: Add weighted aggregation to sdc_core.geo

**Files:**
- Modify: `packages/sdc-core/src/sdc_core/geo.py`
- Create: `packages/sdc-core/tests/test_geo_weighted.py`

- [ ] **Step 1: Write failing test for weighted aggregation**

Create `packages/sdc-core/tests/test_geo_weighted.py`:

```python
"""Tests for weighted aggregation in sdc_core.geo."""

import pandas as pd
from numpy.testing import assert_allclose

from sdc_core.geo import aggregate_up


def test_weighted_mean_aggregation():
    df = pd.DataFrame({
        "geoid": ["51001090100", "51001090200", "51003010100"],
        "year": [2020, 2020, 2020],
        "measure": ["access", "access", "access"],
        "value": [0.5, 0.3, 0.8],
    })
    weights = pd.Series([100, 200, 150], index=df.index)
    result = aggregate_up(df, target_geo="county", method="mean", weights=weights)
    # County 51001: weighted mean = (0.5*100 + 0.3*200) / 300 = 110/300
    county_51001 = result[result["geoid"] == "51001"]
    assert_allclose(county_51001["value"].values[0], 110 / 300, rtol=1e-10)
    # County 51003: single tract, value = 0.8
    county_51003 = result[result["geoid"] == "51003"]
    assert_allclose(county_51003["value"].values[0], 0.8)


def test_weighted_none_falls_back_to_unweighted():
    df = pd.DataFrame({
        "geoid": ["51001090100", "51001090200"],
        "year": [2020, 2020],
        "value": [0.5, 0.3],
    })
    result_no_weight = aggregate_up(df, target_geo="county", method="mean")
    result_none = aggregate_up(df, target_geo="county", method="mean", weights=None)
    assert_allclose(result_no_weight["value"].values, result_none["value"].values)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/test_geo_weighted.py -v`
Expected: FAIL — `aggregate_up() got an unexpected keyword argument 'weights'`

- [ ] **Step 3: Add weights parameter to aggregate_up**

In `packages/sdc-core/src/sdc_core/geo.py`, modify `aggregate_up` (currently at line 88):

```python
def aggregate_up(
    df: pd.DataFrame,
    target_geo: str,
    method: AggMethod = "mean",
    value_col: str = "value",
    weights: pd.Series | None = None,
) -> pd.DataFrame:
    """Aggregate a DataFrame to a higher geography level.

    Parameters
    ----------
    df : pd.DataFrame
        Must have columns: geoid, year, value (at minimum).
    target_geo : str
        Target geography: "tract" or "county".
    method : str
        Aggregation method for the value column.
    value_col : str
        Column to aggregate.
    weights : pd.Series or None
        Population weights for weighted mean aggregation. Index must align
        with df. Only used when method="mean". If None, simple mean is used.

    Returns
    -------
    pd.DataFrame
        Aggregated DataFrame with geoid, year, measure, value, region_type.
    """
    target_length = GEOID_LENGTHS[target_geo]
    result = df.copy()
    result["_target_geoid"] = result["geoid"].str[:target_length]

    group_cols = ["_target_geoid", "year"]
    if "measure" in result.columns:
        group_cols.append("measure")

    if weights is not None and method == "mean":
        result["_weight"] = weights.values
        result["_weighted_val"] = result[value_col] * result["_weight"]

        agg = result.groupby(group_cols).agg(
            _wsum=("_weighted_val", "sum"),
            _wtotal=("_weight", "sum"),
        ).reset_index()
        agg[value_col] = agg["_wsum"] / agg["_wtotal"].replace(0, float("nan"))
        agg = agg.drop(columns=["_wsum", "_wtotal"])
    else:
        agg = result.groupby(group_cols)[value_col].agg(method).reset_index()

    agg = agg.rename(columns={"_target_geoid": "geoid"})
    agg["region_type"] = target_geo
    return agg
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/test_geo_weighted.py -v`
Expected: All PASS

- [ ] **Step 5: Run all existing tests to verify no regressions**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/ads7fg/git/sdc-monorepo
git add packages/sdc-core/src/sdc_core/geo.py packages/sdc-core/tests/test_geo_weighted.py
git commit -m "feat(geo): add population-weighted mean aggregation to aggregate_up"
```

---

### Task 9: Validate via Daycare Accessibility Refactor

**Files:**
- Modify: `education/Daycare Accessibility/code/distribution/ingest.py`

- [ ] **Step 1: Read the current Daycare ingest.py and identify the inline functions to replace**

Read: `education/Daycare Accessibility/code/distribution/ingest.py`
Identify: `_gaussian_weight()`, `compute_3sfca()`, and their call sites.

- [ ] **Step 2: Run the current ingest.py and capture baseline output**

```bash
cd /Users/ads7fg/git/sdc-monorepo
uv run python "education/Daycare Accessibility/code/distribution/ingest.py" 2>&1 | tail -20
```

Save the output file path and row count for comparison.

- [ ] **Step 3: Replace inline 3SFCA with catchment_ratio calls**

Replace `_gaussian_weight()` and `compute_3sfca()` with imports from `sdc_core.catchment`. The key mapping:
- `_gaussian_weight(time, scale=18)` → `catchment_weight(cost, weight="gaussian", scale=18/np.sqrt(2))`
- `compute_3sfca(...)` → `catchment_ratio(..., weight="gaussian", scale=18/np.sqrt(2), normalize_weight=True, return_type=1000)`

Keep `compute_min_drivetime()` and `compute_capacity()` as-is (these are not FCA calculations).

- [ ] **Step 4: Run validation step 1 — scale reconciliation without normalization**

Write a temporary test that compares the Gaussian weight output from the old inline formula vs the new module with `normalize_weight=False`, confirming rtol=1e-6 equivalence.

- [ ] **Step 5: Run the refactored ingest.py and compare output**

```bash
cd /Users/ads7fg/git/sdc-monorepo
uv run python "education/Daycare Accessibility/code/distribution/ingest.py" 2>&1 | tail -20
```

Compare output row count and value statistics with baseline. Document any magnitude differences from the normalization formula change.

- [ ] **Step 6: Commit**

```bash
cd /Users/ads7fg/git/sdc-monorepo
git add "education/Daycare Accessibility/code/distribution/ingest.py"
git commit -m "refactor(daycare): replace inline 3SFCA with sdc_core.catchment"
```

---

### Task 10: Final — Run all tests, push

**Files:** None new

- [ ] **Step 1: Run all catchment tests**

Run: `cd /Users/ads7fg/git/sdc-monorepo && uv run pytest packages/sdc-core/tests/ -v`
Expected: All PASS

- [ ] **Step 2: Push**

```bash
cd /Users/ads7fg/git/sdc-monorepo && git push
```
