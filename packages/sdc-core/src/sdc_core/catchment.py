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
