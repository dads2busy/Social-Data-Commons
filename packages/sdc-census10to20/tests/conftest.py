"""Shared pytest fixtures for sdc-census10to20 tests."""

from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _clear_relationship_cache():
    """Reset the in-process relationship-file cache so tests are isolated."""
    from sdc_census10to20 import crosswalk as _cw

    getattr(_cw, "_RELATIONSHIP_CACHE", {}).clear()
    yield
    getattr(_cw, "_RELATIONSHIP_CACHE", {}).clear()


@pytest.fixture
def synthetic_tract_relationship_csv() -> pd.DataFrame:
    """A canned Census 2010→2020 tract relationship frame.

    Covers three cases that exercise each branch of the R case_when:
    - "same":  one 2010 → one 2020, identical area (geoid10=51001000010)
    - "split": one 2010 → two 2020s, AREALAND_PART sums to AREALAND_10 with
      no boundary movement (geoid10=51001000020)
    - "moved": one 2010 → two 2020s with only partial overlap on each
      (geoid10=51001000030)
    """
    return pd.DataFrame(
        {
            "GEOID_TRACT_20": [
                "51001000001",  # same
                "51001000002",  # split, child A
                "51001000003",  # split, child B
                "51001000004",  # moved, partial overlap A
                "51001000005",  # moved, partial overlap B
            ],
            "GEOID_TRACT_10": [
                "51001000010",
                "51001000020",
                "51001000020",
                "51001000030",
                "51001000030",
            ],
            "AREALAND_TRACT_20": [1000, 600, 400, 600, 600],
            "AREALAND_TRACT_10": [1000, 1000, 1000, 1000, 1000],
            "AREALAND_PART":     [1000, 600, 400, 400, 400],
        }
    )
