"""sdc-redistribute: redistribute values between geographies."""

from importlib.metadata import PackageNotFoundError, version

from sdc_redistribute.redistribute import (
    redistribute_direct,
    redistribute_parcels,
    run_redistribution,
)

try:
    __version__ = version("sdc-redistribute")
except PackageNotFoundError:  # running from a raw checkout, not installed
    __version__ = "0.0.0"

__all__ = [
    "redistribute_direct",
    "redistribute_parcels",
    "run_redistribution",
]
