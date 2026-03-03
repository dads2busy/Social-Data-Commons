"""Ingest agricultural statistics from USDA NASS Census of Agriculture.

Fetches county-level agricultural data for Virginia using the NASS QuickStats
API. Queries each measure from pipeline.yaml for the target year, falling back
to earlier years if data is unavailable.

Data source: https://quickstats.nass.usda.gov/
Requires NASS_KEY environment variable.
"""

import os
import time
from pathlib import Path

import httpx
import pandas as pd
import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"

log = get_logger("agriculture.ingest")

NASS_API_URL = "https://quickstats.nass.usda.gov/api/api_GET/"


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def fetch_nass_measure(
    client: httpx.Client, key: str, data_item: str, state_fips: str, year: int
) -> pd.DataFrame | None:
    """Query NASS QuickStats API for a single measure/year."""
    params = {
        "key": key,
        "source_desc": "CENSUS",
        "sector_desc": "ECONOMICS",
        "state_fips_code": state_fips,
        "year": str(year),
        "short_desc": data_item,
        "format": "JSON",
    }
    try:
        resp = client.get(NASS_API_URL, params=params, timeout=60)
        if resp.status_code != 200:
            return None
        data = resp.json().get("data", [])
        if not data:
            return None
        df = pd.DataFrame(data)
        # Filter to county-level rows
        if "agg_level_desc" in df.columns:
            df = df[df["agg_level_desc"] == "COUNTY"]
        # Prefer TOTAL domain (one aggregate row per county); fall back to
        # keeping all county rows when no TOTAL domain exists (e.g. AG LAND
        # measures only have IRRIGATION STATUS domain with one row per county).
        if "domain_desc" in df.columns:
            total_rows = df[df["domain_desc"] == "TOTAL"]
            if not total_rows.empty:
                df = total_rows
        return df
    except Exception as e:
        log.warning("NASS API error for '%s' year %d: %s", data_item, year, e)
        return None


def run() -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        DIST_DIR.mkdir(parents=True, exist_ok=True)

        key = os.environ.get("NASS_KEY", "")
        if not key:
            return RunResult(success=False, error="NASS_KEY environment variable not set", duration_sec=time.time() - t0)

        src = config["sources"]["va"]
        state_fips = src["state_fips"]
        years = sorted(src["years"], reverse=True)  # try newest first
        measures_cfg = src["measures"]

        all_rows = []
        with httpx.Client() as client:
            for m_cfg in measures_cfg:
                search_term = m_cfg["search_term"]
                measure_name = m_cfg["measure"]
                fetched = False

                for year in years:
                    time.sleep(3)  # NASS rate limit
                    df = fetch_nass_measure(client, key, search_term, state_fips, year)
                    if df is not None and len(df) > 0:
                        # Extract county-level rows
                        county_df = df[df["county_code"].notna() & (df["county_code"] != "")].copy()
                        if county_df.empty:
                            continue
                        for _, row in county_df.iterrows():
                            geoid = str(row.get("state_fips_code", "")).zfill(2) + str(row.get("county_code", "")).zfill(3)
                            value_str = str(row.get("Value", "")).replace(",", "")
                            try:
                                value = float(value_str)
                            except (ValueError, TypeError):
                                continue
                            all_rows.append({
                                "geoid": geoid,
                                "year": int(row.get("year", year)),
                                "measure": measure_name,
                                "value": value,
                            })
                        log.info("Fetched '%s' (%s) for year %d: %d counties", measure_name, search_term, year, len(county_df))
                        fetched = True
                        break  # got data for this measure, move on

                if not fetched:
                    log.warning("No data found for '%s' (%s) in any year", measure_name, search_term)

        if not all_rows:
            return RunResult(success=False, error="No NASS data fetched", duration_sec=time.time() - t0)

        result = pd.DataFrame(all_rows)
        result["moe"] = pd.NA
        result["region_type"] = "county"
        result = result[["geoid", "year", "measure", "value", "moe", "region_type"]]
        result = result.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

        # Group output by year for filenames matching old pattern
        for year in sorted(result["year"].unique()):
            year_df = result[result["year"] == year]
            filename = f"va_ct_{year}_industry_agriculture.csv.xz"
            out_path = write_data(year_df, DIST_DIR / filename, census_standardize=False)
            log.info("Wrote %d rows to %s", len(year_df), out_path)

        return RunResult(success=True, rows=len(result), duration_sec=time.time() - t0)

    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
