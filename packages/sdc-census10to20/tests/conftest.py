"""Shared pytest fixtures for sdc-census10to20 tests."""

from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def synthetic_tract_relationship_csv() -> pd.DataFrame:
    """A canned Census 2010→2020 tract relationship frame.

    Covers three cases:
    - "same":  one 2010 → one 2020, AREALAND_PART == both AREALAND_*
    - "split": one 2010 → two 2020s, AREALAND_PART sums to AREALAND_10
    - "moved": one 2010 → one 2020 but only partial overlap
    """
    return pd.DataFrame(
        {
            "GEOID_TRACT_20": ["51001000001", "51001000002", "51001000003", "51001000004"],
            "GEOID_TRACT_10": ["51001000010", "51001000020", "51001000020", "51001000030"],
            "AREALAND_TRACT_20": [1000, 600, 400, 800],
            "AREALAND_TRACT_10": [1000, 1000, 1000, 1000],
            "AREALAND_PART":     [1000, 600, 400, 800],
        }
    )
