"""Back-compat shim. Canonical code now lives in the sdc-catchment package."""

from sdc_catchment import (  # noqa: F401
    KERNELS,
    WeightSpec,
    catchment_connections,
    catchment_network,
    catchment_ratio,
    catchment_weight,
    euclidean_cost,
)
