"""Build 2010↔2020 census-boundary crosswalks from Census relationship files."""

from __future__ import annotations

import pandas as pd

__all__ = ["get_2010_2020_bound_changes", "create_crosswalk"]


def get_2010_2020_bound_changes(
    res: str = "tract",
    geoids: list[str] | None = None,
    *,
    state_fips: str = "51",
) -> pd.DataFrame:
    """Load 2010→2020 relationship data and classify boundary changes.

    Parameters
    ----------
    res : str
        Resolution: ``"tract"`` or ``"block group"``.
    geoids : list[str] or None
        Optional list of 2010 GEOIDs to filter.
    state_fips : str
        State FIPS for the block-group relationship file (default Virginia, "51").

    Returns
    -------
    pd.DataFrame
        Crosswalk with columns ``geoid20``, ``geoid10``, ``area20``, ``area10``,
        ``area_part``, ``type_change``. ``type_change`` is one of:

        - ``"same"``  — one-to-one mapping, identical area
        - ``"split"`` — one 2010 GEOID divided into multiple 2020 GEOIDs with no
          boundary movement
        - ``"moved"`` — partial overlap; boundary shifted
    """
    if res == "tract":
        file_path = (
            "https://www2.census.gov/geo/docs/maps-data/data/rel2020/"
            "tract/tab20_tract20_tract10_natl.txt"
        )
        res_code = "TRACT"
    elif res == "block group":
        file_path = (
            "https://www2.census.gov/geo/docs/maps-data/data/rel2020/blkgrp/"
            f"tab20_blkgrp20_blkgrp10_st{state_fips}.txt"
        )
        res_code = "BLKGRP"
    else:
        raise ValueError('Invalid resolution. Use "tract" or "block group".')

    crosswalk = pd.read_csv(
        file_path,
        sep="|",
        dtype={
            f"GEOID_{res_code}_10": str,
            f"GEOID_{res_code}_20": str,
        },
    )

    keep_cols = [
        f"GEOID_{res_code}_20",
        f"GEOID_{res_code}_10",
        f"AREALAND_{res_code}_20",
        f"AREALAND_{res_code}_10",
        "AREALAND_PART",
    ]
    crosswalk = crosswalk[keep_cols]
    crosswalk = crosswalk[crosswalk["AREALAND_PART"] != 0]

    crosswalk.columns = ["geoid20", "geoid10", "area20", "area10", "area_part"]

    if geoids is not None:
        crosswalk = crosswalk[crosswalk["geoid10"].isin(geoids)]

    crosswalk["count_20"] = crosswalk.groupby("geoid20")["geoid20"].transform("size")
    crosswalk["count_10"] = crosswalk.groupby("geoid10")["geoid10"].transform("size")

    geoid_10_20 = (
        crosswalk[["geoid10", "area20"]]
        .groupby("geoid10", as_index=False)
        .sum()
        .rename(columns={"area20": "match_area"})
    )
    crosswalk = crosswalk.merge(geoid_10_20, on="geoid10", how="left")

    # Match R's case_when first-match-wins semantics: "same" is checked
    # before "split", so apply lower-priority masks first and let higher-
    # priority masks overwrite.
    crosswalk["type_change"] = "moved"
    split_mask = crosswalk["area10"] == crosswalk["match_area"]
    crosswalk.loc[split_mask, "type_change"] = "split"
    same_mask = (crosswalk["count_10"] == 1) & (crosswalk["count_20"] == 1)
    crosswalk.loc[same_mask, "type_change"] = "same"

    crosswalk = crosswalk.drop(columns=["count_10", "count_20", "match_area"])
    return crosswalk


def create_crosswalk(geoids: list[str], *, state_fips: str = "51") -> pd.DataFrame:
    """Create a combined crosswalk for all GEOID resolutions present in ``geoids``.

    Handles 11-character tract IDs and 12-character block-group IDs; other
    lengths are skipped with a printed notice.
    """
    resolutions = sorted({len(g) for g in geoids})
    crosswalks: list[pd.DataFrame] = []

    for res in resolutions:
        if res == 11:
            crosswalks.append(
                get_2010_2020_bound_changes(res="tract", geoids=geoids, state_fips=state_fips)
            )
        elif res == 12:
            crosswalks.append(
                get_2010_2020_bound_changes(
                    res="block group", geoids=geoids, state_fips=state_fips
                )
            )
        else:
            print(f"crosswalk not available for resolution: {res}")

    if not crosswalks:
        return pd.DataFrame(
            columns=["geoid20", "geoid10", "area20", "area10", "area_part", "type_change"]
        )

    return pd.concat(crosswalks, ignore_index=True)
