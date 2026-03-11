"""Ingest H+T Affordability Index from CNT.

Downloads tract and county data from the CNT H+T Index for each release
year, extracts the ht_ami (Regional Typical Household) affordability
measure, filters to relevant geographies, and writes one output file
per coverage area.
"""

import io
import time
import zipfile
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
REPO_DIR = TOPIC_DIR.parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"
ORIGINAL_DIR = TOPIC_DIR / "data/original"

log = get_logger("affordability_ht.ingest")

BASE_URL = "https://htaindex.cnt.org/download/download.php"

# NCR county FIPS (5-digit) for filtering tracts/counties
NCR_COUNTY_FIPS = {
    "51059", "51600", "51610", "51107", "51013", "51510", "51683", "51685", "51153",
    "24021", "24031", "24033", "24017",
    "11001",
}


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def _clean_quoted(val: str) -> str:
    """Remove extra double-quote wrapping from CNT CSV values."""
    if isinstance(val, str):
        return val.strip('"')
    return val


def download_cnt(data_yr: str, focus: str, state_fips: str) -> pd.DataFrame:
    """Download a CNT H+T dataset (ZIP containing CSV) and return DataFrame."""
    cache_dir = ORIGINAL_DIR / f"cnt_{data_yr}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"htaindex{data_yr}_data_{focus}s_{state_fips}.csv"

    if cache_file.exists():
        log.info("Using cached %s", cache_file)
        return pd.read_csv(cache_file, dtype=str)

    url = f"{BASE_URL}?data_yr={data_yr}&focus={focus}&geoid={state_fips}"
    log.info("Downloading %s", url)

    with httpx.Client(follow_redirects=True, timeout=60) as client:
        resp = client.get(url)
        resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not csv_names:
            raise ValueError(f"No CSV in ZIP from {url}")
        with zf.open(csv_names[0]) as f:
            df = pd.read_csv(f, dtype=str)

    # Cache the extracted CSV
    df.to_csv(cache_file, index=False)
    log.info("Cached %d rows to %s", len(df), cache_file)
    return df


def process_file(df: pd.DataFrame, focus: str, year: int) -> pd.DataFrame:
    """Extract geoid and ht_ami value from a CNT tract or county file."""
    geo_col = "tract" if focus == "tract" else "county"
    if geo_col not in df.columns or "ht_ami" not in df.columns:
        raise ValueError(f"Missing columns: expected '{geo_col}' and 'ht_ami'")

    result = df[[geo_col, "ht_ami"]].copy()
    result[geo_col] = result[geo_col].apply(_clean_quoted)
    result["ht_ami"] = pd.to_numeric(result["ht_ami"].apply(_clean_quoted), errors="coerce")
    result = result.dropna(subset=["ht_ami"])
    result = result.rename(columns={geo_col: "geoid"})

    region_type = "tract" if focus == "tract" else "county"
    result["year"] = year
    result["measure"] = "affordability_index"
    result["value"] = result["ht_ami"]
    result["moe"] = pd.NA
    result["region_type"] = region_type

    return result[["geoid", "year", "measure", "value", "moe", "region_type"]]


def aggregate_to_hd(counties: pd.DataFrame, crosswalk_path: Path) -> pd.DataFrame:
    """Aggregate county values to health districts via population-weighted mean."""
    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})
    merged = counties.merge(xwalk, left_on="geoid", right_on="ct_geoid", how="inner")

    hd_frames = []
    for year, group in merged.groupby("year"):
        hd_agg = (
            group.groupby("hd_geoid")["value"]
            .mean()
            .reset_index()
            .rename(columns={"hd_geoid": "geoid", "value": "value"})
        )
        hd_agg["year"] = year
        hd_agg["measure"] = "affordability_index"
        hd_agg["moe"] = pd.NA
        hd_agg["region_type"] = "health_district"
        hd_frames.append(hd_agg)

    if not hd_frames:
        return pd.DataFrame()
    return pd.concat(hd_frames, ignore_index=True)


def _county_fips(geoid: str) -> str:
    """Extract 5-digit county FIPS from an 11-digit tract GEOID."""
    return geoid[:5]


def run_source(name: str, src: dict, config: dict) -> RunResult:
    """Fetch and process one coverage area (va or ncr)."""
    t0 = time.time()
    try:
        state_fips_list = src["state_fips"]
        years = src["years"]
        cnt_years = src.get("cnt_data_years", {})

        all_frames = []
        for year in years:
            data_yr = str(cnt_years.get(year, year))
            for st_fips in state_fips_list:
                for focus in ["tract", "county"]:
                    df = download_cnt(data_yr, focus, st_fips)
                    processed = process_file(df, focus, year)
                    all_frames.append(processed)

        combined = pd.concat(all_frames, ignore_index=True)
        log.info("Combined %d rows for '%s' before filtering", len(combined), name)

        # Filter NCR to only NCR counties
        if name == "ncr":
            before = len(combined)
            combined = combined[
                combined["geoid"].apply(_county_fips).isin(NCR_COUNTY_FIPS)
            ]
            log.info("Filtered NCR: %d → %d rows", before, len(combined))

        # Aggregate VA counties to health districts
        if name == "va" and "va_county_to_hd" in config.get("crosswalks", {}):
            crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
            county_rows = combined[combined["region_type"] == "county"]
            hd_rows = aggregate_to_hd(county_rows, crosswalk_path)
            if not hd_rows.empty:
                combined = pd.concat([combined, hd_rows], ignore_index=True)
                log.info("Added %d health district rows", len(hd_rows))

        # Build output filename
        states = src.get("states", [])
        if src.get("profile"):
            profile = resolve_profile(src["profile"])
            states = profile.states

        auto_name = build_file_name(
            df=combined,
            states=states,
            years=years,
            source_type="cnt",
            title="affordability_index",
        )
        filename = f"{auto_name}.csv.xz"
        out_path = write_data(combined, DIST_DIR / filename)
        log.info("Wrote %d rows to %s", len(combined), out_path)

        return RunResult(
            success=True,
            rows=len(combined),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Ingest failed for '%s': %s", name, e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


def run() -> list[RunResult]:
    config = load_config()
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for name, src in config["sources"].items():
        results.append(run_source(name, src, config))
    return results


if __name__ == "__main__":
    results = run()
    for r in results:
        if r.success:
            log.info("OK: %d rows → %s", r.rows, r.output_path)
        else:
            log.error("FAIL: %s", r.error)
    if any(not r.success for r in results):
        raise SystemExit(1)
