"""Ingest tract-level healthy days estimates from CDC PLACES.

Fetches frequent mental distress and frequent physical distress prevalence
from 6 CDC PLACES Socrata API releases (2020-2025 releases), taking the
latest model year from each to build a 2018-2023 time series.

Source: CDC PLACES — https://www.cdc.gov/places/
API: Socrata Open Data API at data.cdc.gov
"""

import time
from pathlib import Path

import httpx
import pandas as pd
import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.profiles import resolve_profile
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[2]  # 3-level nesting: health/Mental Health/Mental and Physical Healthy Days
DIST_DIR = TOPIC_DIR / "data/distribution"

log = get_logger("healthy_days.ingest")

SOCRATA_PAGE_SIZE = 50000
REQUEST_DELAY_SEC = 1


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def fetch_places_year(
    client: httpx.Client,
    base_url: str,
    dataset_id: str,
    year: int,
    state_abbrs: list[str],
    measure_ids: list[str],
) -> pd.DataFrame:
    """Fetch tract-level PLACES data for one year from a specific release.

    Parameters
    ----------
    client : httpx client
    base_url : Socrata base URL (e.g. https://data.cdc.gov/resource)
    dataset_id : Socrata dataset identifier for the release
    year : model year to fetch
    state_abbrs : state abbreviations to include (e.g. ["VA", "MD", "DC"])
    measure_ids : PLACES measure IDs (e.g. ["MHLTH", "PHLTH"])

    Returns
    -------
    DataFrame with columns: locationid, countyfips, measureid, data_value,
    low_confidence_limit, high_confidence_limit, year
    """
    endpoint = f"{base_url}/{dataset_id}.json"
    states_str = ",".join(f"'{s}'" for s in state_abbrs)
    measures_str = ",".join(f"'{m}'" for m in measure_ids)

    all_rows = []
    offset = 0

    while True:
        params = {
            "$where": (
                f"stateabbr in ({states_str}) "
                f"AND measureid in ({measures_str}) "
                f"AND year='{year}'"
            ),
            "$limit": str(SOCRATA_PAGE_SIZE),
            "$offset": str(offset),
            "$select": (
                "locationid,countyfips,measureid,data_value,"
                "low_confidence_limit,high_confidence_limit,year"
            ),
        }

        resp = client.get(endpoint, params=params)
        resp.raise_for_status()
        rows = resp.json()

        if not rows:
            break

        all_rows.extend(rows)
        log.info(
            "  Fetched %d rows (offset=%d) from %s year=%d",
            len(rows), offset, dataset_id, year,
        )

        if len(rows) < SOCRATA_PAGE_SIZE:
            break
        offset += SOCRATA_PAGE_SIZE
        time.sleep(REQUEST_DELAY_SEC)

    # Normalize column names — older PLACES releases may use mixed casing
    df = pd.DataFrame(all_rows)
    if not df.empty:
        df.columns = df.columns.str.lower()
    return df


def fetch_all_years(config: dict, state_abbrs: list[str]) -> pd.DataFrame:
    """Fetch PLACES data across all configured release years."""
    places_cfg = config["places"]
    base_url = places_cfg["base_url"]
    releases = places_cfg["releases"]
    measure_ids = [m["id"] for m in places_cfg["measures"]]

    client = httpx.Client(
        follow_redirects=True,
        timeout=120,
        headers={"User-Agent": "sdc-monorepo/healthy_days (research)"},
    )

    frames = []
    try:
        for year, dataset_id in sorted(releases.items()):
            year = int(year)
            log.info("Fetching year %d from release %s", year, dataset_id)
            df = fetch_places_year(
                client, base_url, dataset_id, year, state_abbrs, measure_ids,
            )
            if df.empty:
                log.warning("No data for year %d from %s", year, dataset_id)
            else:
                frames.append(df)
            time.sleep(REQUEST_DELAY_SEC)
    finally:
        client.close()

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def to_long_format(raw: pd.DataFrame, measure_map: dict[str, str]) -> pd.DataFrame:
    """Convert raw PLACES JSON data to SDC long format.

    Parameters
    ----------
    raw : DataFrame from fetch_all_years
    measure_map : mapping of PLACES measureid → SDC measure name
        e.g. {"MHLTH": "perc_freq_mental_distress"}
    """
    df = raw.copy()

    # Drop rows with missing values
    df = df.dropna(subset=["data_value"])
    df["data_value"] = pd.to_numeric(df["data_value"], errors="coerce")
    df = df.dropna(subset=["data_value"])

    # Map measure IDs to SDC names
    df["measure"] = df["measureid"].map(measure_map)
    df = df.dropna(subset=["measure"])

    # Build confidence interval → approximate MOE at 90% CI
    # PLACES provides 95% CI; convert to 90% CI: MOE_90 = (upper - lower) / 2 * (1.645 / 1.96)
    df["low_confidence_limit"] = pd.to_numeric(df["low_confidence_limit"], errors="coerce")
    df["high_confidence_limit"] = pd.to_numeric(df["high_confidence_limit"], errors="coerce")
    df["moe"] = (
        (df["high_confidence_limit"] - df["low_confidence_limit"])
        / 2
        * (1.645 / 1.96)
    )
    # Set MOE to NA where CIs were missing
    df.loc[df["low_confidence_limit"].isna() | df["high_confidence_limit"].isna(), "moe"] = pd.NA

    # Determine region type from GEOID length
    df["geoid"] = df["locationid"].astype(str)
    df["region_type"] = df["geoid"].str.len().map({5: "county", 11: "tract"})
    df = df.dropna(subset=["region_type"])

    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype(int)
    df["value"] = df["data_value"]
    df["data_method"] = "modeled"

    return df[["geoid", "year", "measure", "value", "moe", "region_type", "data_method"]]


def add_county_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Add county-level aggregates from tract data if not already present.

    PLACES provides tract-level data only. County rows are computed as the
    unweighted mean of tract values within each county — this is consistent
    with how the dashboard aggregates tract data.

    If county-level rows already exist in the data (geoid length 5), they
    are kept as-is and no additional county rows are computed.
    """
    has_county = (df["region_type"] == "county").any()
    if has_county:
        return df

    tracts = df[df["region_type"] == "tract"].copy()
    if tracts.empty:
        return df

    tracts["county_geoid"] = tracts["geoid"].str[:5]
    county_agg = (
        tracts.groupby(["county_geoid", "year", "measure"])
        .agg(value=("value", "mean"))
        .reset_index()
    )
    county_agg = county_agg.rename(columns={"county_geoid": "geoid"})
    county_agg["moe"] = pd.NA  # MOE not valid for unweighted tract averages
    county_agg["region_type"] = "county"
    county_agg["data_method"] = "modeled"

    return pd.concat([df, county_agg], ignore_index=True)


def run_source(
    name: str,
    src: dict,
    config: dict,
    out_dir: Path,
) -> RunResult:
    """Run ingest for a single source (va or ncr)."""
    t0 = time.time()
    try:
        # Determine state abbreviations
        profile_name = src.get("profile")
        if profile_name:
            profile = resolve_profile(profile_name)
            state_abbrs = profile.states
            ncr_counties = profile.counties
        else:
            state_abbrs = src.get("states", [])
            ncr_counties = {}

        log.info("Ingesting source '%s': states=%s", name, state_abbrs)

        raw = fetch_all_years(config, state_abbrs)
        if raw.empty:
            return RunResult(
                success=False,
                error=f"No PLACES data for '{name}'",
                duration_sec=time.time() - t0,
            )

        # Map PLACES measure IDs to SDC names
        measure_map = {m["id"]: m["name"] for m in config["places"]["measures"]}
        df = to_long_format(raw, measure_map)

        # Filter NCR to configured counties only (from GeoProfile.counties)
        if ncr_counties:
            state_fips_map = {"VA": "51", "MD": "24", "DC": "11"}
            full_fips = set()
            for state_abbr, county_codes in ncr_counties.items():
                sfips = state_fips_map.get(state_abbr, "")
                for code in county_codes:
                    full_fips.add(f"{sfips}{code}")
            df = df[df["geoid"].str[:5].isin(full_fips)]

        if df.empty:
            return RunResult(
                success=False,
                error=f"No data after filtering for '{name}'",
                duration_sec=time.time() - t0,
            )

        # Add county aggregates from tracts
        df = add_county_rows(df)

        # Build filename and write
        coverage = name if name in ("va", "ncr") else name
        years = sorted(df["year"].unique().tolist())
        auto_name = build_file_name(
            df=df,
            coverage_area=coverage,
            years=years,
            source_type="cdc_places",
            title="healthy_days",
        )
        # census_standardize=False: PLACES provides estimates on each release's
        # native tract boundaries; do not redistribute across boundary vintages
        out_path = write_data(df, out_dir / f"{auto_name}.csv.xz")
        log.info("Wrote %d rows (%d tracts, %d counties) to %s",
                 len(df),
                 (df["region_type"] == "tract").sum(),
                 (df["region_type"] == "county").sum(),
                 out_path.name)

        return RunResult(
            success=True,
            rows=len(df),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Ingest failed for source '%s': %s", name, e, exc_info=True)
        return RunResult(
            success=False,
            error=str(e),
            duration_sec=time.time() - t0,
        )


def run() -> list[RunResult]:
    config = load_config()
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    return [
        run_source(name, src, config, DIST_DIR)
        for name, src in config["sources"].items()
    ]


if __name__ == "__main__":
    results = run()
    for r in results:
        log.info("Result: %s", r.to_dict())
    if any(not r.success for r in results):
        raise SystemExit(1)
