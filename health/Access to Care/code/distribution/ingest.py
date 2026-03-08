"""Ingest and compute access-to-care index for Virginia census tracts.

Pipeline:
1. Load ACS population + uninsured data (B01001_001, B27010_033, B27010_050)
2. Load CMS Medicare Physician PUF, filter VA primary care providers
3. Assign physicians to tracts via HUD ZIP-to-tract crosswalk
4. Build tract-to-tract distances from BG travel time parquets (≤30 mi)
5. For each tract, sum physicians in all tracts within 30 miles
6. Compute composite z-score: access_index = -1 × z(z(pop/phys) + z(pct_uninsured))

Replaces R scripts: ingest_pop_insur.R, ingest_primcare.R,
prepare_primcare_tracts.R, prepare_phys_pop_ratio_insur_pct.R
"""

import json
import lzma
import re
import time
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import pandas as pd
from sdc_core.census import CensusClient
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"

CMS_DIR = (
    REPO_DIR
    / "health/Health Care Services/Physicians/data/original"
    / "Medicare Physician & Other Practitioners - by Provider"
)
ZIP_TRACT_PATH = REPO_DIR / "housing/Cost/Rent/data/original/ZIP_TRACT_122021.csv"
TRAVEL_TIMES_DIR = REPO_DIR / "geographies/osrm/travel_times"

YEARS = [2017, 2018, 2019, 2020, 2021, 2022, 2023]
PRIMARY_CARE_TYPES = {
    "Internal Medicine",
    "Family Practice",
    "Pediatric Medicine",
    "Obstetrics & Gynecology",
}
THIRTY_MILES_METERS = 48_280  # 30 miles in meters

log = get_logger("access_care.ingest")


def load_acs_data(years: list[int]) -> pd.DataFrame:
    """Fetch tract-level population and uninsured counts from ACS 5-year."""
    variables = {
        "tot_pop": "B01001_001",
        "uninsured_19_34": "B27010_033",
        "uninsured_35_64": "B27010_050",
    }
    api = CensusClient()
    df = api.get_acs_multi(
        variables=variables,
        years=years,
        states=["VA"],
        geographies=["tract"],
        estimate_only=True,
    )
    # Already wide format: geoid, year, region_type, tot_pop, uninsured_19_34, ...
    return df


CMS_CATALOG_URL = "https://data.cms.gov/data.json"
CMS_DATASET_TITLE = "Medicare Physician & Other Practitioners - by Provider"


def _fetch_cms_catalog() -> dict[int, str]:
    """Query CMS data.json catalog for PUF download URLs by year.

    Returns a dict mapping data year (int) to CSV download URL.
    Filenames encode the data year as D{YY} (e.g. D23 = 2023).
    """
    log.info("Fetching CMS data catalog from %s", CMS_CATALOG_URL)
    with urlopen(CMS_CATALOG_URL) as resp:
        catalog = json.loads(resp.read())

    urls_by_year: dict[int, str] = {}
    for dataset in catalog.get("dataset", []):
        if dataset.get("title") != CMS_DATASET_TITLE:
            continue
        for dist in dataset.get("distribution", []):
            url = dist.get("downloadURL", "")
            if not url or not url.endswith(".csv"):
                continue
            # Extract data year from filename: ...D{YY}_Prov.csv
            m = re.search(r"_D(\d{2})_Prov\.csv$", url)
            if m:
                year = 2000 + int(m.group(1))
                urls_by_year[year] = url

    return urls_by_year


def ensure_cms_files(years: list[int]) -> None:
    """Download and compress any missing CMS PUF files."""
    missing = [y for y in years if not list((CMS_DIR / str(y)).glob("*.csv.xz"))]
    if not missing:
        return

    log.info("Missing CMS PUF files for years: %s", missing)
    catalog = _fetch_cms_catalog()

    for year in missing:
        url = catalog.get(year)
        if not url:
            log.warning("No CMS PUF download URL found for %d", year)
            continue

        year_dir = CMS_DIR / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        fname = re.search(r"/([^/]+\.csv)$", url).group(1)
        out_path = year_dir / f"{fname}.xz"

        log.info("Downloading %d PUF: %s", year, fname)
        with urlopen(url) as resp:
            raw = resp.read()

        log.info("Compressing %d PUF (%d MB) → %s", year, len(raw) // 1_000_000, out_path.name)
        with lzma.open(out_path, "wb", preset=3) as f:
            f.write(raw)

        log.info("Saved %s (%.0f MB)", out_path.name, out_path.stat().st_size / 1_000_000)


def load_cms_physicians(years: list[int]) -> pd.DataFrame:
    """Load CMS PUF files, filter to VA primary care physicians."""
    ensure_cms_files(years)

    frames = []
    for year in years:
        year_dir = CMS_DIR / str(year)
        csvs = list(year_dir.glob("*.csv.xz"))
        if not csvs:
            log.warning("No CMS PUF file for %d in %s", year, year_dir)
            continue

        log.info("Reading CMS PUF %d: %s", year, csvs[0].name)
        df = pd.read_csv(
            csvs[0],
            usecols=[
                "Rndrng_NPI",
                "Rndrng_Prvdr_State_FIPS",
                "Rndrng_Prvdr_Type",
                "Rndrng_Prvdr_Crdntls",
                "Rndrng_Prvdr_Zip5",
            ],
            dtype=str,
            encoding="latin-1",
        )
        # Filter: VA, primary care, has credentials
        df = df[
            (df["Rndrng_Prvdr_State_FIPS"] == "51")
            & (df["Rndrng_Prvdr_Type"].isin(PRIMARY_CARE_TYPES))
            & (df["Rndrng_Prvdr_Crdntls"].notna())
        ].copy()
        df["year"] = year
        frames.append(df[["Rndrng_NPI", "Rndrng_Prvdr_Zip5", "year"]])

    result = pd.concat(frames, ignore_index=True)
    log.info(
        "Loaded %d VA primary care physicians across %d years", len(result), len(years)
    )
    return result


def assign_physicians_to_tracts(
    physicians: pd.DataFrame,
    crosswalk: pd.DataFrame,
) -> pd.DataFrame:
    """Map physicians from ZIP codes to census tracts using HUD crosswalk.

    Each physician is fractionally allocated to tracts proportional to
    the residential ratio (res_ratio) of the ZIP-tract overlap.
    """
    merged = physicians.merge(
        crosswalk[["zip", "geoid", "res_ratio"]],
        left_on="Rndrng_Prvdr_Zip5",
        right_on="zip",
        how="inner",
    )
    # Weight physician count by residential ratio
    merged["phys_count"] = merged["res_ratio"]

    phys_by_tract = merged.groupby(["geoid", "year"])["phys_count"].sum().reset_index()
    log.info(
        "Assigned physicians to %d tract-year pairs (%.0f unmatched ZIPs)",
        len(phys_by_tract),
        physicians["Rndrng_Prvdr_Zip5"].nunique() - merged["zip"].nunique(),
    )
    return phys_by_tract


def build_tract_distances() -> pd.DataFrame:
    """Load BG travel times, aggregate to tract pairs, filter ≤30 miles.

    Uses only the VA origin file (bg2bg_51.parquet) which includes
    cross-state destinations.
    """
    va_parquet = TRAVEL_TIMES_DIR / "bg2bg_51.parquet"
    log.info("Loading travel times from %s", va_parquet)
    bg = pd.read_parquet(va_parquet, columns=["bg_orig", "bg_dest", "dist_meters"])

    # Truncate BG GEOIDs (12-digit) to tract GEOIDs (11-digit)
    bg["tract_orig"] = bg["bg_orig"].str[:11]
    bg["tract_dest"] = bg["bg_dest"].str[:11]

    # Min distance per tract pair (most direct route between any BG pair)
    tract_dist = (
        bg.groupby(["tract_orig", "tract_dest"])["dist_meters"].min().reset_index()
    )
    # Filter to ≤30 miles
    tract_dist = tract_dist[tract_dist["dist_meters"] <= THIRTY_MILES_METERS]

    # Add self-pairs (distance = 0)
    va_tracts = tract_dist["tract_orig"].unique()
    self_pairs = pd.DataFrame(
        {"tract_orig": va_tracts, "tract_dest": va_tracts, "dist_meters": 0},
    )
    tract_dist = pd.concat([tract_dist, self_pairs], ignore_index=True)
    tract_dist = tract_dist.drop_duplicates(subset=["tract_orig", "tract_dest"])

    log.info(
        "%d tract pairs within 30 miles (%d unique VA origin tracts)",
        len(tract_dist),
        len(va_tracts),
    )
    return tract_dist


def count_physicians_within_30mi(
    phys_by_tract: pd.DataFrame,
    tract_dist: pd.DataFrame,
) -> pd.DataFrame:
    """For each VA tract and year, sum physicians in all reachable tracts."""
    # Join: for each VA origin tract, find all destination tracts within 30mi
    # Then sum the physician count at those destination tracts
    merged = tract_dist[["tract_orig", "tract_dest"]].merge(
        phys_by_tract,
        left_on="tract_dest",
        right_on="geoid",
        how="inner",
    )
    result = (
        merged.groupby(["tract_orig", "year"])["phys_count"]
        .sum()
        .reset_index()
        .rename(columns={"tract_orig": "geoid", "phys_count": "phys_30mi"})
    )
    log.info(
        "Physician-within-30mi: %d tract-years, median=%.0f",
        len(result),
        result["phys_30mi"].median(),
    )
    return result


def compute_access_index(
    acs: pd.DataFrame,
    phys_30mi: pd.DataFrame,
) -> pd.DataFrame:
    """Compute composite z-score access index per tract-year.

    Formula: access_index = -1 × z(z(pop_per_physician) + z(pct_uninsured))
    Higher values = better access.
    """
    df = acs.merge(phys_30mi, on=["geoid", "year"], how="left")

    # Tracts with no physicians within 30mi
    n_missing = df["phys_30mi"].isna().sum()
    if n_missing:
        log.warning("%d tract-years with no physicians within 30 miles", n_missing)

    # Population per physician
    df["pop_per_phys"] = df["tot_pop"] / df["phys_30mi"]

    # Percent uninsured
    df["pct_uninsured"] = (
        (df["uninsured_19_34"] + df["uninsured_35_64"]) / df["tot_pop"] * 100
    )

    # Drop rows with NaN/inf before z-scoring
    valid = df["pop_per_phys"].notna() & np.isfinite(df["pop_per_phys"])
    valid &= df["pct_uninsured"].notna() & np.isfinite(df["pct_uninsured"])
    df_valid = df[valid].copy()

    # Z-scores (using pandas: (x - mean) / std)
    def _zscore(s: pd.Series) -> pd.Series:
        return (s - s.mean()) / s.std()

    df_valid["pop_per_phys_z"] = _zscore(df_valid["pop_per_phys"])
    df_valid["pct_uninsured_z"] = _zscore(df_valid["pct_uninsured"])

    # Composite: sum z-scores, then z-score the sum, then negate
    df_valid["sum_z"] = df_valid["pop_per_phys_z"] + df_valid["pct_uninsured_z"]
    df_valid["access_index"] = -1 * _zscore(df_valid["sum_z"])

    log.info(
        "Access index: n=%d, mean=%.3f, std=%.3f, range=[%.2f, %.2f]",
        len(df_valid),
        df_valid["access_index"].mean(),
        df_valid["access_index"].std(),
        df_valid["access_index"].min(),
        df_valid["access_index"].max(),
    )
    return df_valid[["geoid", "year", "access_index"]]


def to_long_format(df: pd.DataFrame) -> pd.DataFrame:
    """Convert to standard long format: geoid, year, measure, value, moe, region_type."""
    out = pd.DataFrame(
        {
            "geoid": df["geoid"],
            "year": df["year"],
            "measure": "access_care_indicator_geo20",
            "value": df["access_index"].round(4),
            "moe": pd.NA,
            "region_type": "tract",
        }
    )
    return out.sort_values(["geoid", "year"]).reset_index(drop=True)


def run() -> RunResult:
    t0 = time.time()
    try:
        DIST_DIR.mkdir(parents=True, exist_ok=True)

        # Step 1: ACS data
        log.info("Loading ACS population + insurance data")
        acs = load_acs_data(YEARS)
        log.info("ACS: %d tract-years", len(acs))

        # Step 2: CMS physicians
        log.info("Loading CMS physician data")
        physicians = load_cms_physicians(YEARS)

        # Step 3: ZIP-to-tract assignment
        log.info("Loading ZIP-to-tract crosswalk")
        crosswalk = pd.read_csv(ZIP_TRACT_PATH, dtype={"zip": str, "geoid": str})
        phys_by_tract = assign_physicians_to_tracts(physicians, crosswalk)

        # Step 4: Tract distances
        log.info("Building tract distance matrix from BG travel times")
        tract_dist = build_tract_distances()

        # Step 5: Physicians within 30 miles
        phys_30mi = count_physicians_within_30mi(phys_by_tract, tract_dist)

        # Step 6: Compute access index
        access = compute_access_index(acs, phys_30mi)
        result_df = to_long_format(access)

        # Write output
        fname = build_file_name(
            coverage_area="va",
            data_source="cms_acs",
            years=YEARS,
            title="access_care",
            geographies=["tract"],
        )
        out_path = write_data(result_df, DIST_DIR / f"{fname}.csv.xz")
        log.info("Wrote %d rows to %s", len(result_df), out_path)

        return RunResult(
            success=True,
            rows=len(result_df),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
