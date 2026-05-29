"""Unit tests for PowerInfrastructure pure transforms."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from transforms import parse_capacity


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("100 MW", 100.0),
        ("2.5 MW", 2.5),
        ("750000 W", 0.75),
        ("750 kW", 0.75),
        ("1.5 GW", 1500.0),
        ("100MW", 100.0),       # no space
        ("100", 100.0),         # bare number assumed MW
        ("yes", math.nan),      # non-numeric sentinel
        ("", math.nan),
        (None, math.nan),
    ],
)
def test_parse_capacity(raw, expected):
    result = parse_capacity(raw)
    if math.isnan(expected):
        assert math.isnan(result)
    else:
        assert result == pytest.approx(expected)
