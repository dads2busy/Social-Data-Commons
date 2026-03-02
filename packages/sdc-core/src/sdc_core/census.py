"""Census Bureau API client.

Talks directly to the Census Bureau REST API via httpx — no third-party
Census wrapper needed. Supports ACS 5-year estimates at block group, tract,
and county geographies with automatic GEOID construction and long-format output.

Usage:
    from sdc_core.census import CensusClient

    client = CensusClient(api_key="...")
    df = client.get_acs(
        variables=["B28002_001", "B28002_004"],
        geography="block_group",
        state="VA",
        year=2021,
    )
"""

from __future__ import annotations

import os
import time
from typing import Literal

import httpx
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

# fmt: off
STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08",
    "CT": "09", "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15",
    "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
    "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27",
    "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56", "PR": "72",
}
# fmt: on

FIPS_TO_STATE = {v: k for k, v in STATE_FIPS.items()}

Geography = Literal["block_group", "tract", "county"]

ACS_BASE_URL = "https://api.census.gov/data/{year}/acs/acs5"


def _resolve_fips(state: str) -> str:
    """Accept either a state abbreviation ('VA') or a FIPS code ('51')."""
    if state in STATE_FIPS:
        return STATE_FIPS[state]
    if state in FIPS_TO_STATE:
        return state
    raise ValueError(f"Unknown state: {state!r}. Use a 2-letter abbreviation or FIPS code.")


class CensusClient:
    """Minimal Census Bureau API client for ACS 5-year data."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("CENSUS_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "Census API key required. Set CENSUS_API_KEY env var or pass api_key=."
            )
        self._http = httpx.Client(timeout=60)

    def _fetch(self, url: str, params: dict) -> list[list[str]]:
        """Make a single API request, returning the raw JSON rows."""
        params["key"] = self.api_key
        resp = self._http.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_acs(
        self,
        variables: list[str],
        geography: Geography,
        state: str | list[str],
        year: int,
        *,
        county: str = "*",
        estimate_only: bool = True,
        show_progress: bool = True,
    ) -> pd.DataFrame:
        """Fetch ACS 5-year variables and return a tidy long-format DataFrame.

        Parameters
        ----------
        variables : list[str]
            ACS variable IDs, e.g. ["B28002_001", "B28002_004"].
        geography : "block_group" | "tract" | "county"
            Target geography level.
        state : str or list[str]
            State abbreviation(s) or FIPS code(s).
        year : int
            ACS data year.
        county : str
            County FIPS filter. Default "*" fetches all counties.
        estimate_only : bool
            If True, only fetch estimates (E suffix). If False, also fetch
            margins of error (M suffix).
        show_progress : bool
            Show tqdm progress bar when downloading multiple states.

        Returns
        -------
        pd.DataFrame
            Columns: geoid, year, measure, value (and moe if estimate_only=False).
        """
        states = [state] if isinstance(state, str) else state
        fips_list = [_resolve_fips(s) for s in states]

        # Build field list
        suffixes = ["E", "M"] if not estimate_only else ["E"]
        fields = []
        for var in variables:
            for suffix in suffixes:
                fields.append(f"{var}{suffix}")

        url = ACS_BASE_URL.format(year=year)
        all_rows: list[pd.DataFrame] = []

        pbar = tqdm(fips_list, disable=not show_progress, desc="Fetching ACS data")
        for state_fips in pbar:
            state_abbr = FIPS_TO_STATE.get(state_fips, state_fips)
            pbar.set_postfix(state=state_abbr)

            params = {"get": ",".join(["NAME"] + fields)}
            geo_for, geo_in = _build_geo_params(geography, state_fips, county)
            params["for"] = geo_for
            params["in"] = geo_in

            try:
                rows = self._fetch(url, params)
            except httpx.HTTPStatusError as exc:
                pbar.write(f"Warning: failed for state {state_abbr}: {exc}")
                continue

            header = rows[0]
            data = rows[1:]
            df = pd.DataFrame(data, columns=header)
            df["geoid"] = _build_geoid(df, geography)
            all_rows.append(df)

            # Be polite to the API
            time.sleep(0.1)

        if not all_rows:
            return pd.DataFrame(columns=["geoid", "year", "measure", "value"])

        raw = pd.concat(all_rows, ignore_index=True)

        # Pivot to long format
        return _to_long_format(raw, variables, year, estimate_only)

    def get_acs_wide(
        self,
        variables: dict[str, str],
        geography: Geography,
        state: str | list[str],
        year: int,
        *,
        county: str = "*",
        estimate_only: bool = True,
        show_progress: bool = True,
        table_type: str = "detail",
    ) -> pd.DataFrame:
        """Fetch ACS data and return in wide format with friendly column names.

        Like get_acs(), but accepts a name→variable mapping and returns one
        column per variable using the friendly names. Useful when you need to
        compute derived measures (percentages, ratios) before melting to long.

        Parameters
        ----------
        variables : dict[str, str]
            Mapping of friendly name to ACS variable ID,
            e.g. {"total_pop": "B01001_001", "male": "B01001_002"}.
        geography, state, year, county, estimate_only, show_progress :
            Same as get_acs().

        Returns
        -------
        pd.DataFrame
            Columns: geoid, NAME, year, region_type, plus one column per
            friendly name (estimate), and {name}_moe if estimate_only=False.
        """
        var_ids = list(variables.values())
        name_for_id = {v: k for k, v in variables.items()}

        states_list = [state] if isinstance(state, str) else state
        fips_list = [_resolve_fips(s) for s in states_list]

        suffixes = ["E", "M"] if not estimate_only else ["E"]
        fields = [f"{vid}{s}" for vid in var_ids for s in suffixes]

        _table_suffix = {"profile": "/profile", "subject": "/subject"}.get(table_type, "")
        url = ACS_BASE_URL.format(year=year) + _table_suffix
        all_rows: list[pd.DataFrame] = []

        pbar = tqdm(fips_list, disable=not show_progress, desc=f"ACS {geography} {year}")
        for state_fips in pbar:
            state_abbr = FIPS_TO_STATE.get(state_fips, state_fips)
            pbar.set_postfix(state=state_abbr)

            params = {"get": ",".join(["NAME"] + fields)}
            geo_for, geo_in = _build_geo_params(geography, state_fips, county)
            params["for"] = geo_for
            params["in"] = geo_in

            try:
                rows = self._fetch(url, params)
            except httpx.HTTPStatusError as exc:
                pbar.write(f"Warning: failed for state {state_abbr} year {year}: {exc}")
                continue

            header = rows[0]
            data = rows[1:]
            df = pd.DataFrame(data, columns=header)
            df["geoid"] = _build_geoid(df, geography)
            all_rows.append(df)
            time.sleep(0.1)

        if not all_rows:
            return pd.DataFrame()

        raw = pd.concat(all_rows, ignore_index=True)

        # Rename columns: B01001_001E → total_pop, B01001_001M → total_pop_moe
        rename_map = {}
        for vid, name in name_for_id.items():
            rename_map[f"{vid}E"] = name
            if not estimate_only:
                rename_map[f"{vid}M"] = f"{name}_moe"
        raw = raw.rename(columns=rename_map)

        # Convert numeric columns
        for name in name_for_id.values():
            raw[name] = pd.to_numeric(raw[name], errors="coerce")
            if not estimate_only:
                raw[f"{name}_moe"] = pd.to_numeric(raw[f"{name}_moe"], errors="coerce")

        # Drop raw Census component columns, keep geoid + NAME + friendly names
        geo_cols = {"state", "county", "tract", "block group"}
        drop_cols = [c for c in raw.columns if c in geo_cols]
        raw = raw.drop(columns=drop_cols)

        raw["year"] = year
        raw["region_type"] = geography
        return raw

    def get_acs_multi(
        self,
        variables: dict[str, str],
        years: list[int],
        states: list[str] | None = None,
        geographies: list[Geography] | None = None,
        *,
        profile: str | None = None,
        county: str = "*",
        estimate_only: bool = True,
        show_progress: bool = True,
        block_group_min_year: int = 2013,
        table_type: str = "detail",
    ) -> pd.DataFrame:
        """Fetch ACS data across multiple years, states, and geography levels.

        Handles the common SDC pattern of looping year × geography × state,
        with the constraint that block group data is only available from 2013+.

        Parameters
        ----------
        variables : dict[str, str]
            Mapping of friendly name to ACS variable ID.
        years : list[int]
            Years to fetch.
        states : list[str] or None
            State abbreviations. Ignored if profile is set.
        geographies : list[Geography] or None
            Geography levels. Defaults to ["tract", "county", "block_group"].
        profile : str or None
            Geography profile name (e.g. "NCR", "VA"). Overrides states.
            See sdc_core.profiles for available profiles.
        county, estimate_only, show_progress, block_group_min_year :
            Same as get_acs_wide().

        Returns
        -------
        pd.DataFrame
            Wide-format DataFrame (one column per variable friendly name).
        """
        from sdc_core.profiles import resolve_profile as _resolve

        if geographies is None:
            geographies = ["tract", "county", "block_group"]

        # Resolve profile → states
        if profile:
            geo_profile = _resolve(profile)
            states = geo_profile.states
        elif states is None:
            raise ValueError("Either 'states' or 'profile' must be provided.")

        all_dfs: list[pd.DataFrame] = []

        combos = [
            (year, geo)
            for year in years
            for geo in geographies
            if not (geo == "block_group" and year < block_group_min_year)
        ]

        for year, geo in tqdm(
            combos,
            disable=not show_progress,
            desc="Fetching ACS multi",
        ):
            df = self.get_acs_wide(
                variables=variables,
                geography=geo,
                state=states,
                year=year,
                county=county,
                estimate_only=estimate_only,
                show_progress=False,
                table_type=table_type,
            )
            if not df.empty:
                all_dfs.append(df)

        if not all_dfs:
            return pd.DataFrame()

        return pd.concat(all_dfs, ignore_index=True)


def _build_geo_params(
    geography: Geography, state_fips: str, county: str
) -> tuple[str, str]:
    """Build the 'for' and 'in' query params for the Census API."""
    if geography == "block_group":
        return (
            "block group:*",
            f"state:{state_fips} county:{county} tract:*",
        )
    elif geography == "tract":
        return (
            "tract:*",
            f"state:{state_fips} county:{county}",
        )
    elif geography == "county":
        return (
            f"county:{county}",
            f"state:{state_fips}",
        )
    else:
        raise ValueError(f"Unsupported geography: {geography!r}")


def _build_geoid(df: pd.DataFrame, geography: Geography) -> pd.Series:
    """Construct a full GEOID from Census component columns."""
    if geography == "block_group":
        return df["state"] + df["county"] + df["tract"] + df["block group"]
    elif geography == "tract":
        return df["state"] + df["county"] + df["tract"]
    elif geography == "county":
        return df["state"] + df["county"]
    else:
        raise ValueError(f"Unsupported geography: {geography!r}")


def _to_long_format(
    raw: pd.DataFrame,
    variables: list[str],
    year: int,
    estimate_only: bool,
) -> pd.DataFrame:
    """Reshape wide Census response into standard long format."""
    records = []
    for var in variables:
        estimate_col = f"{var}E"
        subset = raw[["geoid"]].copy()
        subset["year"] = year
        subset["measure"] = var
        subset["value"] = pd.to_numeric(raw[estimate_col], errors="coerce")
        if not estimate_only:
            moe_col = f"{var}M"
            subset["moe"] = pd.to_numeric(raw[moe_col], errors="coerce")
        records.append(subset)

    result = pd.concat(records, ignore_index=True)

    # Census uses negative sentinel values for missing/suppressed data
    result.loc[result["value"] < 0, "value"] = pd.NA
    if "moe" in result.columns:
        result.loc[result["moe"] < 0, "moe"] = pd.NA

    return result
