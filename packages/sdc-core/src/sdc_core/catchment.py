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
        None = use cost as weight. float = binary threshold (exclusive: cost < threshold).
        list of (distance, weight) tuples = stepped. str = kernel name.
        callable = custom function (cost_matrix) -> weight_matrix.
    max_cost : float or None
        Zero out weights where cost exceeds this value.
    scale : float
        Scale parameter for kernel functions.
    normalize_weight : bool
        Apply 3SFCA selection probability: w * (w / rowsum). NOT simple row normalization.
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
        if adjust_zeros and isinstance(adjust_zeros, (int, float)):
            c = np.where((c == 0) & (c >= 0), adjust_zeros, c)
        w = np.asarray(weight(c), dtype=float)
    elif isinstance(weight, str):
        if weight not in KERNELS:
            raise ValueError(f"Unknown kernel '{weight}'. Choose from: {list(KERNELS)}")
        if adjust_zeros and isinstance(adjust_zeros, (int, float)):
            c = np.where((c == 0) & (c >= 0), adjust_zeros, c)
        w = KERNELS[weight](c, scale)
    elif isinstance(weight, (int, float)) and not isinstance(weight, bool):
        if adjust_zeros and isinstance(adjust_zeros, (int, float)):
            c = np.where((c == 0) & (c >= 0), adjust_zeros, c)
        w = np.where((c > 0) & (c < float(weight)), 1.0, 0.0)
    elif isinstance(weight, list):
        if adjust_zeros and isinstance(adjust_zeros, (int, float)):
            c = np.where((c == 0) & (c >= 0), adjust_zeros, c)
        steps = sorted(weight, key=lambda x: x[0])
        w = np.zeros_like(c)
        for dist, wt in steps:
            w = np.where((c > 0) & (c < dist) & (w == 0), wt, w)
    else:
        raise TypeError(f"Unsupported weight type: {type(weight)}")

    if max_cost is not None:
        cost_arr = cost_sp.toarray().astype(float)
        w[cost_arr > max_cost] = 0.0

    w[~np.isfinite(w)] = 0.0
    w[w < 0] = 0.0
    w[cost_sp.toarray() < 0] = 0.0

    if normalize_weight:
        row_sums = w.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        w = w * (w / row_sums)

    return sparse.csc_matrix(w)
