"""sdc-census10to20: redistribute 2010-2019 census data onto 2020 boundaries."""

__version__ = "0.1.0"

__all__ = [
    "convert_2010_to_2020_bounds",
    "create_crosswalk",
    "get_2010_2020_bound_changes",
    "standardize_all",
]


def __getattr__(name: str):
    if name in {"get_2010_2020_bound_changes", "create_crosswalk"}:
        from sdc_census10to20 import crosswalk

        return getattr(crosswalk, name)
    if name in {"convert_2010_to_2020_bounds", "standardize_all"}:
        from sdc_census10to20 import convert

        return getattr(convert, name)
    raise AttributeError(f"module 'sdc_census10to20' has no attribute {name!r}")
