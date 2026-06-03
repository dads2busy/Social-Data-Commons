"""Tests for sdc_catchment."""

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose
from scipy import sparse


class TestKernels:
    def test_gaussian(self):
        from sdc_catchment import KERNELS
        cost = np.array([0.0, 1.0, 2.0, 5.0])
        scale = 2.0
        result = KERNELS["gaussian"](cost, scale)
        expected = np.exp(-cost**2 / (2 * scale**2))
        assert_allclose(result, expected)

    def test_linear(self):
        from sdc_catchment import KERNELS
        cost = np.array([0.0, 1.0, 2.0, 5.0])
        scale = 3.0
        result = KERNELS["linear"](cost, scale)
        expected = np.maximum(0, (scale - cost) / scale)
        assert_allclose(result, expected)

    def test_exponential(self):
        from sdc_catchment import KERNELS
        cost = np.array([0.0, 1.0, 2.0])
        scale = 0.5
        result = KERNELS["exponential"](cost, scale)
        expected = np.exp(-cost * scale)
        assert_allclose(result, expected)

    def test_gravity(self):
        from sdc_catchment import KERNELS
        cost = np.array([1.0, 2.0, 4.0])
        scale = 2.0
        result = KERNELS["gravity"](cost, scale)
        expected = cost ** (-scale / 2)
        assert_allclose(result, expected)

    def test_logistic(self):
        from sdc_catchment import KERNELS
        cost = np.array([0.0, 1.0, 2.0])
        scale = 1.0
        result = KERNELS["logistic"](cost, scale)
        expected = 1.0 / (1.0 + np.exp(scale * cost))
        assert_allclose(result, expected)

    def test_logarithmic(self):
        from sdc_catchment import KERNELS
        cost = np.array([1.0, 2.0, 10.0])
        scale = 10.0
        result = KERNELS["logarithmic"](cost, scale)
        expected = 1.0 / (1.0 + np.log(cost) / np.log(scale))
        assert_allclose(result, expected)


class TestCatchmentWeight:
    def test_none_weight_returns_cost_as_sparse(self):
        from sdc_catchment import catchment_weight
        cost = np.array([[1.0, 2.0], [3.0, 4.0]])
        w = catchment_weight(cost, weight=None)
        assert sparse.issparse(w)
        assert_allclose(w.toarray(), cost)

    def test_binary_threshold_exclusive(self):
        from sdc_catchment import catchment_weight
        cost = np.array([[5.0, 15.0, 25.0]])
        w = catchment_weight(cost, weight=20.0)
        expected = np.array([[1.0, 1.0, 0.0]])
        assert_allclose(w.toarray(), expected)

    def test_stepped_weights(self):
        from sdc_catchment import catchment_weight
        cost = np.array([[5.0, 15.0, 25.0]])
        w = catchment_weight(cost, weight=[(10, 1.0), (20, 0.5), (30, 0.25)])
        expected = np.array([[1.0, 0.5, 0.25]])
        assert_allclose(w.toarray(), expected)

    def test_kernel_string(self):
        from sdc_catchment import catchment_weight
        cost = np.array([[0.0, 1.0], [2.0, 3.0]])
        w = catchment_weight(cost, weight="gaussian", scale=2.0)
        expected = np.exp(-cost**2 / (2 * 2.0**2))
        assert_allclose(w.toarray(), expected, atol=1e-10)

    def test_callable_weight(self):
        from sdc_catchment import catchment_weight
        cost = np.array([[1.0, 2.0]])
        w = catchment_weight(cost, weight=lambda c: 1.0 / c)
        expected = np.array([[1.0, 0.5]])
        assert_allclose(w.toarray(), expected)

    def test_max_cost(self):
        from sdc_catchment import catchment_weight
        cost = np.array([[5.0, 15.0, 25.0]])
        w = catchment_weight(cost, weight="gaussian", scale=10.0, max_cost=20.0)
        result = w.toarray()
        assert result[0, 2] == 0.0
        assert result[0, 0] > 0.0

    def test_normalize_weight_3sfca(self):
        from sdc_catchment import catchment_weight
        cost = np.array([[1.0, 2.0, 3.0]])
        w_raw = catchment_weight(cost, weight=10.0)
        w_norm = catchment_weight(cost, weight=10.0, normalize_weight=True)
        raw = w_raw.toarray()
        row_sum = raw.sum(axis=1, keepdims=True)
        expected = raw * (raw / row_sum)
        assert_allclose(w_norm.toarray(), expected)

    def test_adjust_zeros_skipped_when_weight_none(self):
        from sdc_catchment import catchment_weight
        cost = np.array([[0.0, 1.0]])
        w = catchment_weight(cost, weight=None)
        assert w.toarray()[0, 0] == 0.0

    def test_adjust_zeros_applied_for_kernel(self):
        from sdc_catchment import catchment_weight
        cost = np.array([[0.0, 1.0]])
        w = catchment_weight(cost, weight="gravity", scale=2.0)
        assert np.all(np.isfinite(w.toarray()))
        assert w.toarray()[0, 0] > 0

    def test_sparse_input(self):
        from sdc_catchment import catchment_weight
        cost_dense = np.array([[1.0, 0.0], [0.0, 2.0]])
        cost_sparse = sparse.csc_matrix(cost_dense)
        w_dense = catchment_weight(cost_dense, weight="gaussian", scale=2.0)
        w_sparse = catchment_weight(cost_sparse, weight="gaussian", scale=2.0)
        assert_allclose(w_dense.toarray(), w_sparse.toarray())


class TestCatchmentRatio:
    @pytest.fixture
    def setup(self):
        consumers = pd.DataFrame({"geoid": ["C1", "C2", "C3"], "value": [100, 200, 150]})
        providers = pd.DataFrame({"geoid": ["P1", "P2"], "value": [50, 30]})
        cost = np.array([[5.0, 25.0], [8.0, 8.0], [25.0, 5.0]])
        return consumers, providers, cost

    def test_2sfca_original(self, setup):
        from sdc_catchment import catchment_ratio
        consumers, providers, cost = setup
        result = catchment_ratio(consumers, providers, cost, weight=10.0, return_type="original")
        assert isinstance(result, pd.Series)
        assert list(result.index) == ["C1", "C2", "C3"]
        assert_allclose(result["C1"], 50 / 300, rtol=1e-10)
        assert_allclose(result["C2"], 50 / 300 + 30 / 350, rtol=1e-10)
        assert_allclose(result["C3"], 30 / 350, rtol=1e-10)

    def test_return_type_supply(self, setup):
        from sdc_catchment import catchment_ratio
        consumers, providers, cost = setup
        result = catchment_ratio(consumers, providers, cost, weight=10.0, return_type="supply")
        assert_allclose(result["C1"], 50.0)
        assert_allclose(result["C2"], 80.0)
        assert_allclose(result["C3"], 30.0)

    def test_return_type_numeric(self, setup):
        from sdc_catchment import catchment_ratio
        consumers, providers, cost = setup
        result_raw = catchment_ratio(consumers, providers, cost, weight=10.0, return_type="original")
        result_1k = catchment_ratio(consumers, providers, cost, weight=10.0, return_type=1000)
        assert_allclose(result_1k.values, result_raw.values * 1000)

    def test_return_type_demand(self, setup):
        from sdc_catchment import catchment_ratio
        consumers, providers, cost = setup
        result = catchment_ratio(consumers, providers, cost, weight=10.0, return_type="demand")
        assert isinstance(result, pd.Series)
        assert list(result.index) == ["P1", "P2"]
        assert_allclose(result["P1"], 300.0)
        assert_allclose(result["P2"], 350.0)

    def test_return_type_normalized(self, setup):
        from sdc_catchment import catchment_ratio
        consumers, providers, cost = setup
        result = catchment_ratio(consumers, providers, cost, weight=10.0, return_type="normalized")
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_return_type_region(self, setup):
        from sdc_catchment import catchment_ratio
        consumers, providers, cost = setup
        result = catchment_ratio(consumers, providers, cost, weight=10.0, return_type="region")
        result_raw = catchment_ratio(consumers, providers, cost, weight=10.0, return_type="original")
        expected = result_raw * consumers["value"].values
        assert_allclose(result.values, expected.values)

    def test_dimension_mismatch_raises(self):
        from sdc_catchment import catchment_ratio
        consumers = pd.DataFrame({"geoid": ["C1", "C2"], "value": [100, 200]})
        providers = pd.DataFrame({"geoid": ["P1"], "value": [50]})
        cost = np.array([[1.0, 2.0]])
        with pytest.raises(ValueError, match="dimension"):
            catchment_ratio(consumers, providers, cost, weight=10.0)


class TestFCAVariants:
    @pytest.fixture
    def setup(self):
        consumers = pd.DataFrame({"geoid": ["C1", "C2", "C3"], "value": [100, 200, 150]})
        providers = pd.DataFrame({"geoid": ["P1", "P2"], "value": [50, 30]})
        cost = np.array([[5.0, 25.0], [8.0, 8.0], [25.0, 5.0]])
        return consumers, providers, cost

    def test_e2sfca_stepped(self, setup):
        from sdc_catchment import catchment_ratio

        consumers, providers, cost = setup
        result = catchment_ratio(consumers, providers, cost, weight=[(10, 1.0), (30, 0.5)])
        assert isinstance(result, pd.Series)
        assert len(result) == 3
        result_binary = catchment_ratio(consumers, providers, cost, weight=30.0)
        assert not np.allclose(result.values, result_binary.values)

    def test_3sfca_normalized(self, setup):
        from sdc_catchment import catchment_ratio

        consumers, providers, cost = setup
        result = catchment_ratio(consumers, providers, cost, weight="gaussian", scale=10.0, normalize_weight=True)
        result_non = catchment_ratio(consumers, providers, cost, weight="gaussian", scale=10.0)
        assert not np.allclose(result.values, result_non.values)

    def test_modified_2sfca(self, setup):
        from sdc_catchment import catchment_ratio

        consumers, providers, cost = setup
        result = catchment_ratio(consumers, providers, cost, weight="gaussian", scale=10.0, adjust_providers=lambda w: w**2)
        result_base = catchment_ratio(consumers, providers, cost, weight="gaussian", scale=10.0)
        assert not np.allclose(result.values, result_base.values)

    def test_balanced_fca(self, setup):
        from sdc_catchment import catchment_ratio

        consumers, providers, cost = setup
        row_norm = lambda w: w / np.where(w.sum(axis=1, keepdims=True) > 0, w.sum(axis=1, keepdims=True), 1)
        col_norm = lambda w: w / np.where(w.sum(axis=0, keepdims=True) > 0, w.sum(axis=0, keepdims=True), 1)
        result = catchment_ratio(
            consumers, providers, cost, weight=30.0, adjust_consumers=row_norm, adjust_providers=col_norm
        )
        assert isinstance(result, pd.Series)
        assert len(result) == 3


class TestCommuteBased:
    def test_commute_blending(self):
        from sdc_catchment import catchment_ratio

        consumers = pd.DataFrame({"geoid": ["C1", "C2"], "value": [100, 200]})
        providers = pd.DataFrame({"geoid": ["P1"], "value": [50]})
        cost = np.array([[5.0], [5.0]])
        od = np.array([[0, 20], [10, 0]])
        result = catchment_ratio(consumers, providers, cost, weight=10.0, consumers_commutes=od)
        assert isinstance(result, pd.Series)
        assert len(result) == 2

    def test_commute_diagonal_zeroed(self):
        from sdc_catchment import catchment_ratio

        consumers = pd.DataFrame({"geoid": ["C1", "C2"], "value": [100, 200]})
        providers = pd.DataFrame({"geoid": ["P1"], "value": [50]})
        cost = np.array([[5.0], [5.0]])
        od_dirty = np.array([[50, 20], [10, 100]])
        od_clean = np.array([[0, 20], [10, 0]])
        result_dirty = catchment_ratio(consumers, providers, cost, weight=10.0, consumers_commutes=od_dirty)
        result_clean = catchment_ratio(consumers, providers, cost, weight=10.0, consumers_commutes=od_clean)
        assert_allclose(result_dirty.values, result_clean.values)


class TestConnections:
    def test_basic_connections(self):
        from sdc_catchment import catchment_connections

        cost = np.array([[5.0, 25.0], [8.0, 8.0], [25.0, 5.0]])
        result = catchment_connections(cost, weight=10.0, consumer_ids=["C1", "C2", "C3"], provider_ids=["P1", "P2"])
        assert isinstance(result, pd.DataFrame)
        assert set(result.columns) == {"from_id", "to_id", "weight", "cost"}
        assert len(result) == 4

    def test_default_ids(self):
        from sdc_catchment import catchment_connections

        cost = np.array([[5.0, 25.0]])
        result = catchment_connections(cost, weight=10.0)
        assert result["from_id"].iloc[0] == 0
        assert result["to_id"].iloc[0] == 0


class TestNetwork:
    def test_basic_network(self):
        from sdc_catchment import catchment_network

        connections = pd.DataFrame(
            {
                "from_id": ["C1", "C2", "C2", "C3", "C4"],
                "to_id": ["P1", "P1", "P2", "P2", "P3"],
                "weight": [1, 1, 1, 1, 1],
                "cost": [5, 8, 8, 5, 5],
            }
        )
        result = catchment_network(connections, from_start="C1")
        assert "C4" not in result["from_id"].values
        assert "P3" not in result["to_id"].values
        assert len(result) == 4


class TestEdgeCases:
    def test_empty_catchment(self):
        from sdc_catchment import catchment_ratio
        consumers = pd.DataFrame({"geoid": ["C1"], "value": [100]})
        providers = pd.DataFrame({"geoid": ["P1"], "value": [50]})
        cost = np.array([[100.0]])
        result = catchment_ratio(consumers, providers, cost, weight=10.0)
        assert_allclose(result["C1"], 0.0)

    def test_single_provider(self):
        from sdc_catchment import catchment_ratio
        consumers = pd.DataFrame({"geoid": ["C1", "C2"], "value": [100, 200]})
        providers = pd.DataFrame({"geoid": ["P1"], "value": [50]})
        cost = np.array([[5.0], [5.0]])
        result = catchment_ratio(consumers, providers, cost, weight=10.0)
        assert_allclose(result["C1"], 50 / 300)
        assert_allclose(result["C2"], 50 / 300)

    def test_zero_population_consumer(self):
        from sdc_catchment import catchment_ratio
        consumers = pd.DataFrame({"geoid": ["C1", "C2"], "value": [0, 200]})
        providers = pd.DataFrame({"geoid": ["P1"], "value": [50]})
        cost = np.array([[5.0], [5.0]])
        result = catchment_ratio(consumers, providers, cost, weight=10.0)
        assert np.isfinite(result["C1"])

    def test_all_zero_cost_row(self):
        from sdc_catchment import catchment_ratio
        consumers = pd.DataFrame({"geoid": ["C1", "C2"], "value": [100, 200]})
        providers = pd.DataFrame({"geoid": ["P1"], "value": [50]})
        cost = np.array([[0.0], [5.0]])
        result = catchment_ratio(consumers, providers, cost, weight=10.0)
        assert np.isfinite(result["C1"])

    def test_sparse_dense_equivalence(self):
        from sdc_catchment import catchment_ratio
        consumers = pd.DataFrame({"geoid": ["C1", "C2"], "value": [100, 200]})
        providers = pd.DataFrame({"geoid": ["P1", "P2"], "value": [50, 30]})
        cost_dense = np.array([[5.0, 25.0], [8.0, 8.0]])
        cost_sparse = sparse.csc_matrix(cost_dense)
        r_dense = catchment_ratio(consumers, providers, cost_dense, weight=10.0)
        r_sparse = catchment_ratio(consumers, providers, cost_sparse, weight=10.0)
        assert_allclose(r_dense.values, r_sparse.values)


class TestEuclideanCost:
    def test_basic(self):
        from sdc_catchment import euclidean_cost
        consumers = np.array([[0, 0], [3, 4]])
        providers = np.array([[0, 0], [1, 0]])
        result = euclidean_cost(consumers, providers)
        assert result.shape == (2, 2)
        assert_allclose(result[0, 0], 0.0)
        assert_allclose(result[0, 1], 1.0)
        assert_allclose(result[1, 0], 5.0)
