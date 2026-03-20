"""Tests for weighted aggregation in sdc_core.geo."""

import pandas as pd
from numpy.testing import assert_allclose

from sdc_core.geo import aggregate_up


def test_weighted_mean_aggregation():
    df = pd.DataFrame({
        "geoid": ["51001090100", "51001090200", "51003010100"],
        "year": [2020, 2020, 2020],
        "measure": ["access", "access", "access"],
        "value": [0.5, 0.3, 0.8],
    })
    weights = pd.Series([100, 200, 150], index=df.index)
    result = aggregate_up(df, target_geo="county", method="mean", weights=weights)
    county_51001 = result[result["geoid"] == "51001"]
    assert_allclose(county_51001["value"].values[0], 110 / 300, rtol=1e-10)
    county_51003 = result[result["geoid"] == "51003"]
    assert_allclose(county_51003["value"].values[0], 0.8)


def test_weighted_none_falls_back_to_unweighted():
    df = pd.DataFrame({
        "geoid": ["51001090100", "51001090200"],
        "year": [2020, 2020],
        "value": [0.5, 0.3],
    })
    result_no_weight = aggregate_up(df, target_geo="county", method="mean")
    result_none = aggregate_up(df, target_geo="county", method="mean", weights=None)
    assert_allclose(result_no_weight["value"].values, result_none["value"].values)
