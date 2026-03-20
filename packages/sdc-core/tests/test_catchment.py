"""Tests for sdc_core.catchment."""

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose
from scipy import sparse


class TestKernels:
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
