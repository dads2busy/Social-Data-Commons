"""sdc-census10to20: redistribute 2010-2019 census data onto 2020 boundaries."""

from sdc_census10to20.convert import convert_2010_to_2020_bounds, standardize_all
from sdc_census10to20.crosswalk import create_crosswalk, get_2010_2020_bound_changes

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sdc-census10to20")
except PackageNotFoundError:  # running from a raw checkout, not installed
    __version__ = "0.0.0"

__all__ = [
    "convert_2010_to_2020_bounds",
    "create_crosswalk",
    "get_2010_2020_bound_changes",
    "standardize_all",
]
