"""Ingest employment by minority/nonminority workers from LODES WAC data.

Downloads LODES Workplace Area Characteristics (WAC) files for VA, MD, DC,
aggregates block-level data to block groups, then computes Minority_employment
and Nonminority_employment by summing race-based job counts (CR01-CR07).

Outputs one file per coverage area (ncr, va059, rva) with block_group, tract,
and county levels.

Data source: https://lehd.ces.census.gov/data/lodes/
"""

import io
import time
from pathlib import Path

import httpx
import pandas as pd
import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"

log = get_logger("worker_diversity.ingest")

LODES_URL = "https://lehd.ces.census.gov/data/lodes/LODES8/{state}/wac/{state}_wac_S000_JT00_{year}.csv.gz"
LODES7_URL = "https://lehd.ces.census.gov/data/lodes/LODES7/{state}/wac/{state}_wac_S000_JT00_{year}.csv.gz"

RACE_COLS = ["CR01", "CR02", "CR03", "CR04", "CR05", "CR07"]

MINORITY_MAP = {
    "CR01": "Nonminority",
    "CR02": "Minority",
    "CR03": "Minority",
    "CR04": "Minority",
    "CR05": "Minority",
    "CR07": "Minority",
}


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def download_lodes_wac(state: str, year: int, client: httpx.Client) -> pd.DataFrame | None:
    """Download a single LODES WAC file and return block-group-aggregated DataFrame."""
    for url_template in [LODES_URL, LODES7_URL]:
        url = url_template.format(state=state, year=year)
        try:
            resp = client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                df = pd.read_csv(io.BytesIO(resp.content), compression="gzip", dtype={"w_geocode": str})
                keep_cols = ["w_geocode"] + [c for c in RACE_COLS if c in df.columns]
                df = df[keep_cols].copy()
                # w_geocode is 15-digit block FIPS; first 12 digits = block group
                df["geoid"] = df["w_geocode"].str[:12]
                df = df.drop(columns=["w_geocode"])
                # Aggregate blocks to block groups
                df = df.groupby("geoid", as_index=False).sum()
                df["year"] = year
                log.info("Downloaded %s %d: %d block groups", state.upper(), year, len(df))
                return df
        except Exception as e:
            log.warning("Failed %s for %s %d: %s", url_template.split("/")[5], state, year, e)
            continue
    log.error("Could not download LODES WAC for %s %d", state, year)
    return None


def compute_minority_employment(bg_data: pd.DataFrame) -> pd.DataFrame:
    """Compute Minority_employment and Nonminority_employment from race columns."""
    rows = []
    for _, row in bg_data.iterrows():
        minority_jobs = 0
        nonminority_jobs = 0
        for col, group in MINORITY_MAP.items():
            val = row.get(col, 0)
            if pd.notna(val):
                if group == "Minority":
                    minority_jobs += int(val)
                else:
                    nonminority_jobs += int(val)
        rows.append({
            "geoid": row["geoid"],
            "year": row["year"],
            "measure": "Minority_employment",
            "value": minority_jobs,
        })
        rows.append({
            "geoid": row["geoid"],
            "year": row["year"],
            "measure": "Nonminority_employment",
            "value": nonminority_jobs,
        })
    return pd.DataFrame(rows)


def aggregate_to_levels(bg_long: pd.DataFrame) -> pd.DataFrame:
    """From block-group long data, aggregate to tract and county levels."""
    bg = bg_long.copy()
    bg["region_type"] = "block_group"

    # Tract: first 11 chars of geoid
    tr = bg.copy()
    tr["geoid"] = tr["geoid"].str[:11]
    tr = tr.groupby(["geoid", "year", "measure"], as_index=False)["value"].sum()
    tr["region_type"] = "tract"

    # County: first 5 chars of geoid
    ct = bg.copy()
    ct["geoid"] = ct["geoid"].str[:5]
    ct = ct.groupby(["geoid", "year", "measure"], as_index=False)["value"].sum()
    ct["region_type"] = "county"

    combined = pd.concat([bg[["geoid", "year", "measure", "value", "region_type"]],
                          tr, ct], ignore_index=True)
    combined["moe"] = pd.NA
    return combined


def run_source(name: str, src: dict, all_bg: pd.DataFrame) -> tuple[str, int] | None:
    """Filter block-group data to a coverage area, aggregate, and write."""
    counties = src["counties"]
    filtered = all_bg[all_bg["geoid"].str[:5].isin(counties)].copy()
    if filtered.empty:
        log.warning("No data for source '%s' after county filter", name)
        return None

    long = compute_minority_employment(filtered)
    combined = aggregate_to_levels(long)
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

    years = sorted(combined["year"].unique())
    auto_name = build_file_name(
        coverage_area=name,
        data_source="lodes",
        geographies=["county", "tract", "block_group"],
        years=years,
        title="employment_by_minority_workers",
    )
    filename = f"{auto_name}.csv.xz"
    out_path = DIST_DIR / filename
    write_data(combined, out_path, census_standardize=False)
    log.info("Wrote %d rows to %s", len(combined), out_path)
    return str(out_path), len(combined)


def run() -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        DIST_DIR.mkdir(parents=True, exist_ok=True)

        # Collect all unique state/year combinations needed
        all_states = set()
        all_years = set()
        for src in config["sources"].values():
            all_states.update(src["states"])
            all_years.update(src["years"])

        # Download all LODES WAC data
        frames = []
        with httpx.Client(timeout=60) as client:
            for state in sorted(all_states):
                for year in sorted(all_years):
                    df = download_lodes_wac(state, year, client)
                    if df is not None:
                        frames.append(df)
                    time.sleep(0.5)  # rate limit

        if not frames:
            return RunResult(success=False, error="No LODES data downloaded", duration_sec=time.time() - t0)

        all_bg = pd.concat(frames, ignore_index=True)
        log.info("Total block-group rows across all states/years: %d", len(all_bg))

        # Process each coverage area
        results = {}
        for name, src in config["sources"].items():
            result = run_source(name, src, all_bg)
            if result:
                results[name] = result

        total_rows = sum(r[1] for r in results.values())
        return RunResult(success=True, rows=total_rows, duration_sec=time.time() - t0)

    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
