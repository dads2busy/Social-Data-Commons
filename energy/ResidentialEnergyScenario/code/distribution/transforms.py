"""Pure transformation functions for the ResidentialEnergyScenario pipeline.

The three compute functions (compute_adoption_measures,
compute_residential_load, compute_pv_generation) land in a follow-up task.
This file currently provides shared infrastructure.
"""

from __future__ import annotations

import pandas as pd


ENERGY_LONG_FORMAT_COLUMNS = [
    "geoid",
    "datetime",
    "measure",
    "value",
    "moe",
    "region_type",
    "data_method",
    "scenario",
]


def add_geoid(df: pd.DataFrame, *, region_type: str) -> pd.DataFrame:
    """Add a 5- or 11-digit FIPS `geoid` column from admin codes.

    Required columns: admin1, admin2; admin3 also required for region_type="tract".

    region_type:
        "county" → geoid = admin1.zfill(2) + admin2.zfill(3)        (5 chars)
        "tract"  → geoid = admin1.zfill(2) + admin2.zfill(3) + admin3.zfill(6)  (11 chars)
    """
    if region_type not in ("county", "tract"):
        raise ValueError(
            f"region_type must be 'county' or 'tract', got {region_type!r}"
        )

    out = df.copy()
    geoid_str = (
        out["admin1"].astype(int).astype(str).str.zfill(2)
        + out["admin2"].astype(int).astype(str).str.zfill(3)
    )
    if region_type == "tract":
        geoid_str = geoid_str + out["admin3"].astype(int).astype(str).str.zfill(6)

    # Force numpy object dtype (not pandas StringDtype) so tests that assert
    # `dtype == object` pass under pandas 3.x.
    out["geoid"] = geoid_str.astype(object)
    return out
