"""Ingest HUD Fair Market Rents from FMR and SAFMR Excel files.

Downloads county-level FMR and ZIP-level SAFMR data for each fiscal year,
computes population-weighted county and tract averages, and writes
long-format distribution files for VA and NCR.
"""

import os
import time
from pathlib import Path

import pandas as pd
import requests
import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data" / "distribution"
WORKING_DIR = TOPIC_DIR / "data" / "working"

log = get_logger("housing_cost.ingest")

MEASURES = ["monthly_rent_0br", "monthly_rent_1br", "monthly_rent_2br",
            "monthly_rent_3br", "monthly_rent_4br"]
RENT_COLS = ["rent_0br", "rent_1br", "rent_2br", "rent_3br", "rent_4br"]
FMR_COLS = ["fmr_0", "fmr_1", "fmr_2", "fmr_3", "fmr_4"]


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def download_file(url: str, dest: Path) -> Path:
    """Download a file if not already cached."""
    if dest.exists():
        log.info("Using cached %s", dest.name)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading %s", url)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    log.info("Saved %s (%d bytes)", dest.name, len(resp.content))
    return dest


def parse_safmr(path: Path) -> pd.DataFrame:
    """Parse SAFMR Excel → DataFrame with columns: zip, rent_0br..rent_4br.

    SAFMR files have 18 columns: ZIP code, then for each bedroom size (0-4BR)
    three columns: base SAFMR, 90% payment standard, 110% payment standard.
    We keep only the ZIP and the 5 base SAFMR columns.
    """
    _fix_xlsx_properties(path)
    df = pd.read_excel(path, engine="openpyxl")
    # First column is ZIP (may have embedded newline in header)
    zip_col = df.columns[0]
    # Columns: ZIP, HUD Area Code, HUD Area Name, then triplets of
    # (SAFMR, 90% payment, 110% payment) for each of 0BR..4BR.
    # Rent columns are at 0-indexed positions 3, 6, 9, 12, 15.
    rent_indices = [3, 6, 9, 12, 15]
    cols_to_keep = [zip_col] + [df.columns[i] for i in rent_indices]
    df = df[cols_to_keep].copy()
    df.columns = ["zip"] + RENT_COLS
    df["zip"] = df["zip"].astype(str).str.zfill(5)
    for col in RENT_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _fix_xlsx_properties(path: Path) -> Path:
    """Fix malformed ISO dates in xlsx core.xml that crash openpyxl.

    Some HUD FMR files (created by SAS) have dates like '2022- 8-21T...'
    instead of '2022-08-21T...'. We rewrite the zip in-place with fixed XML.
    """
    import re
    import zipfile
    import tempfile

    try:
        with zipfile.ZipFile(path, "r") as zin:
            if "docProps/core.xml" not in zin.namelist():
                return path
            core_xml = zin.read("docProps/core.xml").decode("utf-8")

        # Fix dates like "2022- 8-21" → "2022-08-21"
        fixed = re.sub(
            r"(\d{4})-\s*(\d)-(\d{2})",
            lambda m: f"{m.group(1)}-0{m.group(2)}-{m.group(3)}",
            core_xml,
        )
        # Fix times like "19: 8: 0Z" → "19:08:00Z"
        fixed = re.sub(
            r"T\s*(\d{1,2}):\s*(\d{1,2}):\s*(\d{1,2})Z",
            lambda m: f"T{m.group(1).zfill(2)}:{m.group(2).zfill(2)}:{m.group(3).zfill(2)}Z",
            fixed,
        )
        if fixed == core_xml:
            return path  # no change needed

        log.info("Fixing malformed dates in %s", path.name)
        fd, tmp_str = tempfile.mkstemp(suffix=".xlsx", dir=path.parent)
        os.close(fd)
        tmp = Path(tmp_str)
        with zipfile.ZipFile(path, "r") as zin, zipfile.ZipFile(tmp, "w") as zout:
            for item in zin.infolist():
                if item.filename == "docProps/core.xml":
                    zout.writestr(item, fixed.encode("utf-8"))
                else:
                    zout.writestr(item, zin.read(item.filename))
        tmp.replace(path)
        return path
    except Exception as e:
        log.warning("Could not fix xlsx properties for %s: %s", path.name, e)
        return path


def parse_fmr(path: Path) -> pd.DataFrame:
    """Parse FMR Excel → DataFrame with columns: county_fips, fmr_0..fmr_4.

    FMR files have a 'fips' or 'fips2010' column with trailing '99999'
    (county FIPS + metro area suffix). We truncate to 5 digits for county FIPS.
    """
    _fix_xlsx_properties(path)
    df = pd.read_excel(path, engine="openpyxl")
    # Find the FIPS column (varies by year: 'fips', 'fips2010', etc.)
    fips_col = next((c for c in df.columns if c.lower().startswith("fips")), None)
    if fips_col is None:
        raise KeyError(f"No FIPS column found in {path.name}. Columns: {list(df.columns)}")
    df["county_fips"] = df[fips_col].astype(str).str[:5].str.zfill(5)
    # FMR columns: typically named fmr_0 through fmr_4
    fmr_found = [c for c in df.columns if c.startswith("fmr_")]
    if len(fmr_found) < 5:
        log.warning("Found %d fmr_* columns (expected 5), check Excel layout", len(fmr_found))
    keep = ["county_fips"] + fmr_found
    df = df[keep].copy()
    # Normalize column names to fmr_0..fmr_4
    rename = {}
    for i, c in enumerate(sorted(fmr_found)):
        rename[c] = f"fmr_{i}"
    df = df.rename(columns=rename)
    # Deduplicate: same county FIPS can appear multiple times (metro areas)
    df = df.drop_duplicates(subset="county_fips", keep="first")
    for col in FMR_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_zip_tract_crosswalk(path: Path) -> pd.DataFrame:
    """Load ZIP-to-tract crosswalk. Returns columns: zip, tract.

    The CSV has columns: zip, geoid (tract FIPS), res_ratio, bus_ratio, etc.
    Both zip and geoid are stored as integers, so zero-padding is needed.
    """
    df = pd.read_csv(path, dtype=str)
    df = df.rename(columns={"geoid": "tract"})
    df["zip"] = df["zip"].str.zfill(5)
    df["tract"] = df["tract"].str.zfill(11)
    return df[["zip", "tract"]].copy()


def load_zcta_county(path: Path) -> pd.DataFrame:
    """Load ZCTA-county relationship file. Returns columns: zcta, county_fips, pop."""
    df = pd.read_csv(path)
    df["zcta"] = df["ZCTA5"].astype(str).str.zfill(5)
    df["county_fips"] = df["GEOID"].astype(str).str.zfill(5)
    df["pop"] = pd.to_numeric(df["POPPT"], errors="coerce").fillna(0)
    return df[["zcta", "county_fips", "pop"]].copy()


def compute_county_fmr(
    safmr: pd.DataFrame,
    zcta_county: pd.DataFrame,
    county_fips_list: list[str],
    fmr_fallback: pd.DataFrame,
) -> pd.DataFrame:
    """Compute county-level FMR as population-weighted average of ZCTA SAFMRs.

    For counties with no ZCTA overlap in the SAFMR data, falls back to
    direct HUD county FMR from the FMR Excel file.

    Returns DataFrame with columns: geoid, rent_0br..rent_4br, data_method.
    """
    # Join ZCTA SAFMRs with ZCTA-county population weights
    # SAFMR zip ≈ ZCTA for this purpose
    merged = zcta_county.merge(safmr, left_on="zcta", right_on="zip", how="inner")

    rows = []
    for fips in county_fips_list:
        county_data = merged[merged["county_fips"] == fips]
        total_pop = county_data["pop"].sum()
        if total_pop > 0 and not county_data[RENT_COLS].isna().all().any():
            row = {"geoid": fips, "data_method": "observed"}
            for col in RENT_COLS:
                row[col] = (county_data[col] * county_data["pop"]).sum() / total_pop
            rows.append(row)
        else:
            # Fallback to direct HUD county FMR.  "observed" because the value
            # is a direct HUD observation at the county level (not derived via
            # weighting).  When the same FMR is later assigned to tracts as a
            # fallback, it becomes "scaled" since it was not measured at tract.
            fmr_row = fmr_fallback[fmr_fallback["county_fips"] == fips]
            if not fmr_row.empty:
                row = {"geoid": fips, "data_method": "observed"}
                for i, col in enumerate(RENT_COLS):
                    row[col] = fmr_row[FMR_COLS[i]].iloc[0]
                rows.append(row)
            else:
                log.warning("No FMR data for county %s", fips)

    return pd.DataFrame(rows)


def compute_tract_fmr(
    safmr: pd.DataFrame,
    zip_tract: pd.DataFrame,
    zip_pop: pd.DataFrame,
    county_fmr: pd.DataFrame,
    fmr_fallback: pd.DataFrame,
    state_fips: list[str],
    tract_geoids: list[str] | None = None,
) -> pd.DataFrame:
    """Compute tract-level FMR as population-weighted average of ZIP SAFMRs.

    Fallback chain:
    1. ZIP-weighted SAFMR average (data_method = "observed")
    2. County pop-weighted average from county_fmr (data_method = "scaled")
    3. Direct HUD county FMR from fmr_fallback (data_method = "scaled")
    """
    # Filter crosswalk to relevant states
    state_mask = zip_tract["tract"].str[:2].isin(state_fips)
    xwalk = zip_tract[state_mask].copy()

    # Join crosswalk with SAFMR and population
    merged = xwalk.merge(safmr, on="zip", how="left")
    merged = merged.merge(zip_pop, on="zip", how="left")
    merged["pop"] = merged["pop"].fillna(0)

    # Determine tract list
    if tract_geoids is not None:
        tracts = tract_geoids
    else:
        tracts = sorted(xwalk["tract"].unique())

    # Build county FMR lookup for fallback
    county_lookup = {}
    if not county_fmr.empty:
        for _, row in county_fmr.iterrows():
            county_lookup[row["geoid"]] = row

    rows = []
    for tract in tracts:
        tract_data = merged[merged["tract"] == tract]
        # Remove rows with no SAFMR data or no population
        valid = tract_data.dropna(subset=RENT_COLS)
        valid = valid[valid["pop"] > 0]
        total_pop = valid["pop"].sum()

        county = tract[:5]

        if total_pop > 0:
            # Primary: ZIP-weighted average
            row = {"geoid": tract, "data_method": "observed"}
            for col in RENT_COLS:
                row[col] = (valid[col] * valid["pop"]).sum() / total_pop
            # Check for zero values (treat as missing)
            if any(row[col] == 0 for col in RENT_COLS):
                row["data_method"] = "scaled"
                county_row = county_lookup.get(county)
                if county_row is not None:
                    for col in RENT_COLS:
                        if row[col] == 0:
                            row[col] = county_row[col]
            rows.append(row)
        elif county in county_lookup:
            # Fallback: county pop-weighted average
            county_row = county_lookup[county]
            row = {"geoid": tract, "data_method": "scaled"}
            for col in RENT_COLS:
                row[col] = county_row[col]
            rows.append(row)
        else:
            # Last resort: direct HUD county FMR
            fmr_row = fmr_fallback[fmr_fallback["county_fips"] == county]
            if not fmr_row.empty:
                row = {"geoid": tract, "data_method": "scaled"}
                for i, col in enumerate(RENT_COLS):
                    row[col] = fmr_row[FMR_COLS[i]].iloc[0]
                rows.append(row)
            else:
                log.warning("No FMR data for tract %s (county %s)", tract, county)

    return pd.DataFrame(rows)


def to_long_format(
    df: pd.DataFrame, year: int, region_type: str
) -> pd.DataFrame:
    """Convert wide rent columns to long format using pd.melt."""
    rename_map = dict(zip(RENT_COLS, MEASURES))
    long = df.rename(columns=rename_map).melt(
        id_vars=["geoid", "data_method"],
        value_vars=MEASURES,
        var_name="measure",
        value_name="value",
    )
    long["year"] = year
    long["moe"] = pd.NA
    long["region_type"] = region_type
    return long[["geoid", "year", "measure", "value", "moe", "region_type", "data_method"]]


def load_zip_pop(path: Path) -> pd.DataFrame:
    """Load ZCTA population from a cached CSV. Returns columns: zip, pop."""
    df = pd.read_csv(path, dtype={"zip": str})
    df["zip"] = df["zip"].str.zfill(5)
    return df


def fetch_zcta_population(year: int) -> pd.DataFrame:
    """Fetch ZCTA total population from ACS DP05_0001E via direct Census API.

    CensusClient.get_acs_wide() does not support geography="zcta", so we
    call the Census API directly. Caches result to data/working/zcta_pop_{year}.csv.
    """
    import os

    cache_path = WORKING_DIR / f"zcta_pop_{year}.csv"
    if cache_path.exists():
        return load_zip_pop(cache_path)

    api_key = os.environ.get("CENSUS_API_KEY", "")
    url = f"https://api.census.gov/data/{year}/acs/acs5/profile"
    params = {
        "get": "NAME,DP05_0001E",
        "for": "zip code tabulation area:*",
        "key": api_key,
    }
    log.info("Fetching ZCTA population from Census API for %d", year)
    resp = requests.get(url, params=params, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    header = data[0]
    rows = data[1:]
    df = pd.DataFrame(rows, columns=header)
    zcta_col = [c for c in df.columns if "zip code" in c.lower()][0]
    df = df.rename(columns={zcta_col: "zip", "DP05_0001E": "pop"})
    df["zip"] = df["zip"].astype(str).str.zfill(5)
    df["pop"] = pd.to_numeric(df["pop"], errors="coerce").fillna(0)
    df = df[["zip", "pop"]].copy()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False)
    log.info("Cached ZCTA population for %d (%d ZCTAs)", year, len(df))
    return df


def run_year(
    fy: int,
    config: dict,
    zcta_county: pd.DataFrame,
    zip_tract: pd.DataFrame,
    zip_pop: pd.DataFrame,
) -> pd.DataFrame:
    """Process one fiscal year. Returns long-format DataFrame."""
    year = fy - 1  # FY2023 → year 2022
    hud = config["hud_fmr"]

    # Download FMR and SAFMR Excel files
    fmr_url = hud["fmr_urls"][fy]
    safmr_url = hud["safmr_urls"][fy]
    fmr_path = download_file(fmr_url, WORKING_DIR / f"fmr_{fy}.xlsx")
    safmr_path = download_file(safmr_url, WORKING_DIR / f"safmr_{fy}.xlsx")

    # Parse Excel files
    safmr = parse_safmr(safmr_path)
    fmr = parse_fmr(fmr_path)
    log.info("FY%d: %d SAFMRs, %d county FMRs", fy, len(safmr), len(fmr))

    # NCR + VA county lists
    ncr_counties = hud["ncr_counties"]
    va_counties = sorted(fmr[fmr["county_fips"].str.startswith("51")]["county_fips"].unique())

    # All unique counties across both coverage areas
    all_counties = sorted(set(va_counties + ncr_counties))

    # Compute county-level FMR for all needed counties
    county_fmr = compute_county_fmr(safmr, zcta_county, all_counties, fmr)

    # Compute tract-level FMR for all relevant states
    state_fips = ["51", "11", "24"]  # VA, DC, MD
    tract_fmr = compute_tract_fmr(
        safmr, zip_tract, zip_pop, county_fmr, fmr, state_fips=state_fips,
    )

    # Convert to long format
    county_long = to_long_format(county_fmr, year, "county")
    tract_long = to_long_format(tract_fmr, year, "tract")

    combined = pd.concat([county_long, tract_long], ignore_index=True)
    log.info("FY%d (year %d): %d rows", fy, year, len(combined))
    return combined


def run() -> list[RunResult]:
    """Run the full ingest pipeline across all fiscal years."""
    from dotenv import load_dotenv
    load_dotenv(TOPIC_DIR.parents[1] / ".env")

    config = load_config()
    hud = config["hud_fmr"]
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    WORKING_DIR.mkdir(parents=True, exist_ok=True)

    # Load static crosswalks (same for all years per design decision)
    zcta_county = load_zcta_county(TOPIC_DIR / hud["zcta_county_file"])
    zip_tract = load_zip_tract_crosswalk(TOPIC_DIR / hud["zip_tract_crosswalk"])
    log.info("Loaded crosswalks: %d ZCTA-county rows, %d ZIP-tract rows",
             len(zcta_county), len(zip_tract))

    # Fetch ZCTA population for 2021 (matches the 2021 Q4 crosswalk vintage;
    # R code also uses 2021 ACS ZCTA populations)
    zip_pop = fetch_zcta_population(2021)
    log.info("Loaded ZCTA population: %d ZCTAs", len(zip_pop))

    ncr_counties = hud["ncr_counties"]
    years = config["sources"]["va"]["years"]  # same for both sources

    results = []
    all_frames = []

    for year in years:
        fy = year + 1
        if fy not in hud["fmr_urls"]:
            log.warning("No FMR URL for FY%d, skipping", fy)
            continue
        t0 = time.time()
        try:
            df = run_year(fy, config, zcta_county, zip_tract, zip_pop)
            all_frames.append(df)
            results.append(RunResult(
                success=True, rows=len(df),
                duration_sec=time.time() - t0,
            ))
        except Exception as e:
            log.error("Failed FY%d: %s", fy, e, exc_info=True)
            results.append(RunResult(
                success=False, error=str(e),
                duration_sec=time.time() - t0,
            ))

    if not all_frames:
        return [RunResult(success=False, error="No data produced")]

    combined = pd.concat(all_frames, ignore_index=True)
    log.info("Total rows across all years: %d", len(combined))

    # Split into VA and NCR
    va_mask = combined["geoid"].str[:2] == "51"
    ncr_mask = combined["geoid"].str[:5].isin(ncr_counties)

    va_data = combined[va_mask].copy()
    ncr_data = combined[ncr_mask].copy()

    # Write VA output
    if not va_data.empty:
        va_name = build_file_name(
            coverage_area="va", data_source="hud",
            years=years, title="housing_cost",
            geographies=["county", "tract"],
        )
        va_path = write_data(va_data, DIST_DIR / f"{va_name}.csv.xz",
                             census_standardize=False)
        log.info("Wrote VA: %d rows → %s", len(va_data), va_path.name)

    # Write NCR output
    if not ncr_data.empty:
        ncr_name = build_file_name(
            coverage_area="ncr", data_source="hud",
            years=years, title="housing_cost",
            geographies=["county", "tract"],
        )
        ncr_path = write_data(ncr_data, DIST_DIR / f"{ncr_name}.csv.xz",
                              census_standardize=False)
        log.info("Wrote NCR: %d rows → %s", len(ncr_data), ncr_path.name)

    return results


if __name__ == "__main__":
    results = run()
    for r in results:
        if r.success:
            log.info("OK: %d rows in %.1fs", r.rows, r.duration_sec)
        else:
            log.error("FAIL: %s", r.error)
    if any(not r.success for r in results):
        raise SystemExit(1)
