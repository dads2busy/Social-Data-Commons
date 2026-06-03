"""Back-compat shim. Canonical code now lives in the sdc-redistribute package."""

from sdc_redistribute import (  # noqa: F401
    redistribute_direct,
    redistribute_parcels,
    run_redistribution,
)
