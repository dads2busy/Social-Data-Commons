"""Ingest marketplace insurance premiums from CMS Public Use Files.

Replaces the Selenium-based KFF scraper.  Downloads Rate, Plan Attributes,
and Service Area PUFs for both FFM and SBE states, then computes the
second-lowest-cost Silver plan (SLCSP) and lowest-cost Bronze plan (LCBP)
per US county.

Output matches the old kff_marketplace_premium.csv schema so the downstream
prepare_healthcare_data_cleaning.py works unchanged.
"""

from __future__ import annotations

import io
import re
import time
import zipfile
from pathlib import Path

import httpx
import pandas as pd
import yaml
from sdc_core.log import get_logger
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[1]

log = get_logger("healthcare_cost.ingest")

# ---------------------------------------------------------------------------
# Column name mappings: SBE PUFs use space-separated quoted names;
# FFM PUFs use camelCase.  We normalise everything to the FFM names.
# ---------------------------------------------------------------------------
_SBE_COL_MAP = {
    # Rate PUF
    "BUSINESS YEAR": "BusinessYear",
    "STATE CODE": "StateCode",
    "ISSUER ID": "IssuerId",
    "PLAN ID": "PlanId",
    "RATING AREA ID": "RatingAreaId",
    "INDIVIDUAL RATE": "IndividualRate",
    "AGE": "Age",
    "TOBACCO": "Tobacco",
    # Plan Attributes PUF
    "STANDARD COMPONENT ID": "StandardComponentId",
    "METAL LEVEL": "MetalLevel",
    "MARKET COVERAGE": "MarketCoverage",
    "DENTAL ONLY PLAN": "DentalOnlyPlan",
    "SERVICE AREA ID": "ServiceAreaId",
    "ISSUER NAME": "IssuerMarketPlaceMarketingName",
    # Service Area PUF
    "COVER ENTIRE STATE": "CoverEntireState",
    "COUNTY": "County",
    "COUNTY NAME": "CountyName",
    "PARTIAL COUNTY": "PartialCounty",
    "ZIP CODE": "ZipCodes",
    "DENTAL PLAN ONLY": "DentalOnlyPlan",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def _download(url: str, cache_dir: Path, label: str = "") -> bytes:
    """Download a URL, caching the raw bytes to *cache_dir*."""
    fname = url.rsplit("/", 1)[-1]
    cached = cache_dir / fname
    if cached.exists():
        log.info("Using cached %s → %s", label or fname, cached)
        return cached.read_bytes()
    log.info("Downloading %s → %s", url, cached)
    resp = httpx.get(url, timeout=120, follow_redirects=True)
    resp.raise_for_status()
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(resp.content)
    return resp.content


def _read_csv_from_zip(
    zip_bytes: bytes,
    pattern: str,
    usecols: list[str] | None = None,
    dtype: dict | None = None,
) -> pd.DataFrame:
    """Read the first CSV inside *zip_bytes* whose name matches *pattern*."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        matches = [n for n in zf.namelist() if re.search(pattern, n, re.I)]
        if not matches:
            raise FileNotFoundError(
                f"No file matching '{pattern}' in ZIP "
                f"(contents: {zf.namelist()})"
            )
        name = matches[0]
        with zf.open(name) as f:
            # SBE files may have BOM; engine='python' handles it but is slow.
            # Use encoding_errors='replace' as a safety net.
            df = pd.read_csv(
                f,
                usecols=usecols,
                dtype=dtype,
                encoding_errors="replace",
                low_memory=False,
            )
    return df


def _normalise_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Rename SBE-style columns to FFM-style camelCase names."""
    return df.rename(columns=_SBE_COL_MAP)


# ---------------------------------------------------------------------------
# Load PUF data
# ---------------------------------------------------------------------------

# Columns we actually need from each PUF (FFM names)
_RATE_COLS_FFM = [
    "StateCode", "IssuerId", "PlanId", "RatingAreaId",
    "Tobacco", "Age", "IndividualRate",
]

_PLAN_COLS_FFM = [
    "StateCode", "IssuerId", "StandardComponentId", "MetalLevel",
    "MarketCoverage", "DentalOnlyPlan", "ServiceAreaId",
]

_SA_COLS_FFM = [
    "StateCode", "IssuerId", "ServiceAreaId", "CoverEntireState",
    "County", "MarketCoverage", "DentalOnlyPlan",
]


def _load_rate(zip_bytes: bytes) -> pd.DataFrame:
    """Load Rate PUF, filter to non-tobacco age-30, keep needed columns."""
    df = _read_csv_from_zip(zip_bytes, r"rate", dtype={"IssuerId": str, "ISSUER ID": str})
    df = _normalise_cols(df)

    # Coerce types
    df["IssuerId"] = df["IssuerId"].astype(str).str.strip()
    df["Age"] = df["Age"].astype(str).str.strip()
    df["IndividualRate"] = pd.to_numeric(df["IndividualRate"], errors="coerce")

    # Filter: age 30, non-tobacco rate
    df = df[df["Age"] == "30"].copy()

    keep = [c for c in _RATE_COLS_FFM if c in df.columns]
    return df[keep].reset_index(drop=True)


def _load_plan_attrs(zip_bytes: bytes) -> pd.DataFrame:
    """Load Plan Attributes PUF, filter to Individual Silver/Bronze medical."""
    df = _read_csv_from_zip(zip_bytes, r"plan", dtype={"IssuerId": str, "ISSUER ID": str})
    df = _normalise_cols(df)

    df["IssuerId"] = df["IssuerId"].astype(str).str.strip()
    df["MetalLevel"] = df["MetalLevel"].astype(str).str.strip()
    df["MarketCoverage"] = df["MarketCoverage"].astype(str).str.strip()
    df["DentalOnlyPlan"] = df["DentalOnlyPlan"].astype(str).str.strip()

    df = df[
        df["MetalLevel"].isin(["Silver", "Bronze", "Expanded Bronze"])
        & (df["MarketCoverage"] == "Individual")
        & (df["DentalOnlyPlan"] == "No")
    ].copy()
    # Normalise "Expanded Bronze" → "Bronze" for downstream grouping
    df.loc[df["MetalLevel"] == "Expanded Bronze", "MetalLevel"] = "Bronze"

    keep = [c for c in _PLAN_COLS_FFM if c in df.columns]
    return df[keep].reset_index(drop=True)


def _parse_sbe_county_fips(county_val: str) -> str | None:
    """Extract 5-digit FIPS from SBE Service Area COUNTY field.

    SBE format: "Fairfax City - 51600" or just "51600" or plain FIPS.
    FFM format: "51600".
    """
    if pd.isna(county_val) or not str(county_val).strip():
        return None
    s = str(county_val).strip()
    # Try to find a 5-digit FIPS at the end after a dash
    m = re.search(r"(\d{4,5})\s*$", s)
    if m:
        return m.group(1).zfill(5)
    return s.zfill(5) if s.isdigit() else None


def _load_service_area(zip_bytes: bytes) -> pd.DataFrame:
    """Load Service Area PUF, filter to Individual non-dental."""
    df = _read_csv_from_zip(
        zip_bytes, r"service.?area",
        dtype={"IssuerId": str, "ISSUER ID": str, "County": str, "COUNTY": str},
    )
    df = _normalise_cols(df)

    df["IssuerId"] = df["IssuerId"].astype(str).str.strip()
    df["MarketCoverage"] = df["MarketCoverage"].astype(str).str.strip()
    df["DentalOnlyPlan"] = df["DentalOnlyPlan"].astype(str).str.strip()
    df["CoverEntireState"] = df["CoverEntireState"].astype(str).str.strip()

    df = df[
        (df["MarketCoverage"] == "Individual")
        & (df["DentalOnlyPlan"] == "No")
    ].copy()

    # Normalise county FIPS — handles both FFM and SBE formats
    df["County"] = df["County"].apply(_parse_sbe_county_fips)

    keep = [c for c in _SA_COLS_FFM if c in df.columns]
    return df[keep].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Download & combine FFM + SBE data
# ---------------------------------------------------------------------------

def download_all_pufs(
    config: dict,
    cache_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Download and return combined (rates, plan_attrs, service_areas)."""

    rates_parts: list[pd.DataFrame] = []
    plans_parts: list[pd.DataFrame] = []
    sa_parts: list[pd.DataFrame] = []

    # --- FFM PUFs ---
    ffm = config["puf"]["ffm"]
    log.info("Loading FFM PUFs (PY%s)…", ffm["year"])
    rate_zip = _download(ffm["rate"], cache_dir, "FFM Rate PUF")
    plan_zip = _download(ffm["plan_attributes"], cache_dir, "FFM Plan Attrs PUF")
    sa_zip = _download(ffm["service_area"], cache_dir, "FFM Service Area PUF")
    rates_parts.append(_load_rate(rate_zip))
    plans_parts.append(_load_plan_attrs(plan_zip))
    sa_parts.append(_load_service_area(sa_zip))

    # --- SBE PUFs ---
    sbe = config["puf"]["sbe"]
    base = sbe["base_url"]
    year = sbe["year"]
    for slug, state_abbr in sbe["states"].items():
        url = f"{base}/{slug}sbepuf{year}.zip"
        log.info("Loading SBE PUF for %s (PY%s)…", state_abbr, year)
        try:
            sbe_zip = _download(url, cache_dir, f"SBE {state_abbr}")
        except httpx.HTTPStatusError:
            log.warning("Could not download SBE PUF for %s – skipping", state_abbr)
            continue
        rates_parts.append(_load_rate(sbe_zip))
        plans_parts.append(_load_plan_attrs(sbe_zip))
        sa_parts.append(_load_service_area(sbe_zip))

    rates = pd.concat(rates_parts, ignore_index=True)
    plans = pd.concat(plans_parts, ignore_index=True)
    sa = pd.concat(sa_parts, ignore_index=True)
    log.info(
        "Loaded %d rate rows, %d plan rows, %d service-area rows",
        len(rates), len(plans), len(sa),
    )
    return rates, plans, sa


# ---------------------------------------------------------------------------
# County-to-rating-area crosswalk
# ---------------------------------------------------------------------------

def load_county_rating_areas(config: dict, cache_dir: Path) -> pd.DataFrame:
    """Load the county → rating area mapping.

    Returns DataFrame with columns: state_fips, county_fips, rating_area,
    state_abbr.
    """
    url = config["county_rating_areas_url"]
    raw = _download(url, cache_dir, "CountyRAs")
    df = pd.read_csv(io.BytesIO(raw), dtype={"statefip": str, "countyfip": str})
    df["countyfip"] = df["countyfip"].str.zfill(5)
    df["statefip"] = df["statefip"].str.zfill(2)
    # Build "Rating Area N" string to match PUF RatingAreaId values
    df = df.dropna(subset=["ratingarea"])
    df["RatingAreaId"] = "Rating Area " + df["ratingarea"].astype(int).astype(str)
    return df


# ---------------------------------------------------------------------------
# SLCSP / LCBP computation
# ---------------------------------------------------------------------------

def compute_premiums(
    rates: pd.DataFrame,
    plans: pd.DataFrame,
    sa: pd.DataFrame,
    county_ras: pd.DataFrame,
    all_counties: pd.DataFrame,
) -> pd.DataFrame:
    """Compute SLCSP and LCBP for every county.

    Parameters
    ----------
    rates : Rate PUF (age-30 rows only)
    plans : Plan Attributes PUF (Silver/Bronze Individual medical)
    sa    : Service Area PUF (Individual non-dental)
    county_ras : county FIPS → RatingAreaId mapping
    all_counties : every US county FIPS with state_id column

    Returns DataFrame with columns: fips, Raw_Cost_of_Silver, Raw_Cost_of_Bronze
    """

    # 1. Join plans with service areas to get plan → county mapping
    #    Plans reference a ServiceAreaId; the SA PUF maps that to counties.
    # Deduplicate SA by the join keys + County + CoverEntireState
    sa_dedup = sa[["StateCode", "IssuerId", "ServiceAreaId", "CoverEntireState", "County"]].drop_duplicates()
    plan_sa = plans.merge(
        sa_dedup,
        on=["StateCode", "IssuerId", "ServiceAreaId"],
        how="inner",
    )
    # 2. Expand CoverEntireState rows: replace with all counties in state
    cover_all = plan_sa[
        plan_sa["CoverEntireState"].str.lower().isin(["yes", "true"])
    ].drop(columns=["County", "CoverEntireState"])

    cover_specific = plan_sa[
        ~plan_sa["CoverEntireState"].str.lower().isin(["yes", "true"])
    ].copy()
    cover_specific = cover_specific.dropna(subset=["County"])
    cover_specific = cover_specific.drop(columns=["CoverEntireState"])

    # Build state → counties lookup from the county_ras crosswalk
    state_abbr_to_fips = (
        all_counties[["state_id", "county_fips"]]
        .drop_duplicates()
        .rename(columns={"state_id": "StateCode", "county_fips": "County"})
    )

    if not cover_all.empty:
        cover_all_expanded = cover_all.merge(
            state_abbr_to_fips, on="StateCode", how="inner",
        )
    else:
        cover_all_expanded = pd.DataFrame(columns=cover_specific.columns)

    plan_county = pd.concat(
        [cover_specific, cover_all_expanded], ignore_index=True,
    )
    plan_county = plan_county.rename(columns={"County": "fips"})

    # 3. Add rating area for each county
    ra_map = county_ras[["countyfip", "RatingAreaId"]].rename(
        columns={"countyfip": "fips"},
    )
    plan_county = plan_county.merge(ra_map, on="fips", how="left")

    # 4. Join with rates to get the premium for each plan×county
    #    Rate PUF key: StandardComponentId + RatingAreaId
    plan_county = plan_county.merge(
        rates[["PlanId", "RatingAreaId", "IndividualRate"]],
        left_on=["StandardComponentId", "RatingAreaId"],
        right_on=["PlanId", "RatingAreaId"],
        how="inner",
    )
    # 5. Compute SLCSP and LCBP per county
    #    SLCSP = 2nd-lowest *unique* Silver rate
    #    LCBP  = lowest Bronze rate
    silver = plan_county[plan_county["MetalLevel"] == "Silver"].copy()
    bronze = plan_county[plan_county["MetalLevel"] == "Bronze"].copy()

    records: list[dict] = []
    for fips, grp in silver.groupby("fips"):
        unique_rates = sorted(grp["IndividualRate"].dropna().unique())
        slcsp = (
            unique_rates[1] if len(unique_rates) >= 2
            else unique_rates[0] if unique_rates
            else None
        )
        records.append({"fips": fips, "Raw_Cost_of_Silver": slcsp})

    slcsp_df = pd.DataFrame(records)

    records = []
    for fips, grp in bronze.groupby("fips"):
        rates_sorted = grp["IndividualRate"].dropna().sort_values()
        lcbp = rates_sorted.iloc[0] if len(rates_sorted) > 0 else None
        records.append({"fips": fips, "Raw_Cost_of_Bronze": lcbp})

    lcbp_df = pd.DataFrame(records)

    if slcsp_df.empty and lcbp_df.empty:
        return pd.DataFrame(columns=["fips", "Raw_Cost_of_Silver", "Raw_Cost_of_Bronze"])

    result = slcsp_df.merge(lcbp_df, on="fips", how="outer")
    return result


# ---------------------------------------------------------------------------
# Build final output
# ---------------------------------------------------------------------------

def build_output(premiums: pd.DataFrame, geo: pd.DataFrame) -> pd.DataFrame:
    """Join premiums with county geography and format as the old CSV schema."""
    geo = geo.copy()
    geo["county_fips"] = geo["county_fips"].astype(str).str.zfill(5)
    geo["zip"] = geo["zip"].astype(str).str.zfill(5)

    # One representative ZIP per county (matches old scraper logic)
    geo_dedup = (
        geo.groupby("county_fips")
        .first()
        .reset_index()[["county_fips", "state_name", "county_name", "zip"]]
    )

    df = geo_dedup.merge(premiums, left_on="county_fips", right_on="fips", how="left")
    # Drop the duplicate fips column from premiums (keep county_fips)
    if "fips" in df.columns:
        df = df.drop(columns=["fips"])

    # At $120k income for a single 30-year-old (~766% FPL), there is
    # effectively no subsidy.  Subsidized = Raw.
    df["Subsidized_Cost_of_Silver"] = df["Raw_Cost_of_Silver"]
    df["Subsidized_Cost_of_Bronze"] = df["Raw_Cost_of_Bronze"]

    # Cast cost columns to rounded integers (matching old CSV)
    for col in [
        "Subsidized_Cost_of_Silver", "Subsidized_Cost_of_Bronze",
        "Raw_Cost_of_Silver", "Raw_Cost_of_Bronze",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce").round().astype("Int64")

    df = df.rename(columns={
        "state_name": "State",
        "county_name": "County",
        "zip": "Zip_Code",
        "county_fips": "fips",
    })

    # Match exact column order of old CSV
    df = df[[
        "State", "County", "Zip_Code",
        "Subsidized_Cost_of_Silver", "Subsidized_Cost_of_Bronze",
        "Raw_Cost_of_Silver", "Raw_Cost_of_Bronze",
        "fips",
    ]]
    return df.sort_values("fips").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        cache_dir = TOPIC_DIR / "data" / "Working" / "puf_cache"
        out_path = TOPIC_DIR / config["output"]["path"]

        # 1. Load geography
        geo_path = TOPIC_DIR / "data" / "Original" / "uszips.csv"
        geo = pd.read_csv(
            geo_path,
            dtype={"zip": str, "county_fips": str, "state_id": str},
            usecols=["zip", "state_id", "state_name", "county_fips", "county_name"],
        )
        excluded = set(config.get("excluded_territories", []))
        geo = geo[~geo["state_id"].isin(excluded)].copy()

        # 2. Download PUFs
        rates, plans, sa = download_all_pufs(config, cache_dir)

        # 3. Load county → rating area crosswalk
        county_ras = load_county_rating_areas(config, cache_dir)

        # 4. Compute SLCSP and LCBP
        log.info("Computing SLCSP and LCBP per county…")
        premiums = compute_premiums(rates, plans, sa, county_ras, geo)
        log.info("Computed premiums for %d counties", len(premiums))

        # 5. Build output CSV
        df = build_output(premiums, geo)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        log.info("Wrote %d rows to %s", len(df), out_path)

        # Summary stats
        n_silver = df["Raw_Cost_of_Silver"].notna().sum()
        n_missing = df["Raw_Cost_of_Silver"].isna().sum()
        warnings = []
        if n_missing:
            warnings.append(
                f"{n_missing} counties have no Silver plan data "
                f"(likely missing PUF coverage)"
            )

        log.info(
            "Done: %d counties total, %d with Silver data, %d missing",
            len(df), n_silver, n_missing,
        )

        return RunResult(
            success=True,
            rows=len(df),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
            warnings=warnings,
        )
    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        return RunResult(
            success=False,
            error=str(e),
            duration_sec=time.time() - t0,
        )


if __name__ == "__main__":
    result = run()
    log.info("Result: %s", result.to_dict())
    if not result.success:
        raise SystemExit(1)
