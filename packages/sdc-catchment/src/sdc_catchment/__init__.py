"""sdc-catchment: floating catchment area spatial accessibility."""

from importlib.metadata import PackageNotFoundError, version

from sdc_catchment.catchment import (
    KERNELS,
    WeightSpec,
    catchment_connections,
    catchment_network,
    catchment_ratio,
    catchment_weight,
    euclidean_cost,
)

try:
    __version__ = version("sdc-catchment")
except PackageNotFoundError:  # running from a raw checkout, not installed
    __version__ = "0.0.0"

__all__ = [
    "KERNELS",
    "WeightSpec",
    "catchment_connections",
    "catchment_network",
    "catchment_ratio",
    "catchment_weight",
    "euclidean_cost",
]
