"""Ingest marketplace insurance premiums from CMS Public Use Files.

Downloads Rate, Plan Attributes, and Service Area PUFs for both FFM and
SBE states, then computes the second-lowest-cost Silver plan (SLCSP) and
lowest-cost Bronze plan (LCBP) per US county.

Output is long-format (geoid, year, measure, value, moe, region_type).
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
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"

log = get_logger("health_care_cost.ingest")

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


# Slug → hyphenated form used in legacy CMS SBE PUF URLs
_HYPHENATED_SLUGS = {
    "districtofcolumbia": "district-columbia",
    "newjersey": "new-jersey",
    "newmexico": "new-mexico",
    "newyork": "new-york",
    "rhodeisland": "rhode-island",
}

# US state abbreviation → 2-digit FIPS code (50 states + DC)
_STATE_ABBR_TO_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
    "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
    "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
    "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55",
    "WY": "56",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def _download(url: str, cache_dir: Path, label: str = "", cache_name: str = "") -> bytes:
    """Download a URL, caching the raw bytes to *cache_dir*."""
    fname = cache_name or url.rsplit("/", 1)[-1]
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
        # Prefer shortest match to avoid variants like _round3
        name = min(matches, key=len)
        with zf.open(name) as f:
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
    """Load Rate PUF, filter to age-30, keep needed columns."""
    df = _read_csv_from_zip(zip_bytes, r"rate", dtype={"IssuerId": str, "ISSUER ID": str})
    df = _normalise_cols(df)

    df["IssuerId"] = df["IssuerId"].astype(str).str.strip()
    df["Age"] = df["Age"].astype(str).str.strip()
    df["IndividualRate"] = pd.to_numeric(df["IndividualRate"], errors="coerce")

    df = df[df["Age"] == "30"].copy()

    keep = [c for c in _RATE_COLS_FFM if c in df.columns]
    df = df[keep]
    return df.reset_index(drop=True)


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
    df.loc[df["MetalLevel"] == "Expanded Bronze", "MetalLevel"] = "Bronze"

    keep = [c for c in _PLAN_COLS_FFM if c in df.columns]
    df = df[keep]
    return df.reset_index(drop=True)


def _parse_sbe_county_fips(county_val: str) -> str | None:
    """Extract 5-digit FIPS from SBE Service Area COUNTY field.

    SBE format: "Fairfax City - 51600" or just "51600" or plain FIPS.
    FFM format: "51600".
    """
    if pd.isna(county_val) or not str(county_val).strip():
        return None
    s = str(county_val).strip()
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

    df["County"] = df["County"].apply(_parse_sbe_county_fips)

    keep = [c for c in _SA_COLS_FFM if c in df.columns]
    df = df[keep]
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Download & combine FFM + SBE data
# ---------------------------------------------------------------------------

def _load_pufs_for_year(
    puf_config: dict,
    year: int,
    cache_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Download and parse FFM + SBE PUFs for a single plan year.

    Returns combined (rates, plan_attrs, service_areas) for that year.
    """
    rates_parts: list[pd.DataFrame] = []
    plans_parts: list[pd.DataFrame] = []
    sa_parts: list[pd.DataFrame] = []

    # --- FFM PUFs (only for years in the FFM year list) ---
    ffm = puf_config["ffm"]
    ffm_years = ffm.get("years", [])
    if year in ffm_years:
        rate_url = ffm["rate"].format(year=year)
        plan_url = ffm["plan_attributes"].format(year=year)
        sa_url = ffm["service_area"].format(year=year)

        log.info("Loading FFM PUFs (PY%d)…", year)
        rate_zip = _download(rate_url, cache_dir, f"FFM Rate PUF {year}", cache_name=f"rate-puf-{year}.zip")
        plan_zip = _download(plan_url, cache_dir, f"FFM Plan Attrs PUF {year}", cache_name=f"plan-attributes-puf-{year}.zip")
        sa_zip = _download(sa_url, cache_dir, f"FFM Service Area PUF {year}", cache_name=f"service-area-puf-{year}.zip")
        rates_parts.append(_load_rate(rate_zip))
        plans_parts.append(_load_plan_attrs(plan_zip))
        sa_parts.append(_load_service_area(sa_zip))

    # --- SBE PUFs ---
    sbe = puf_config["sbe"]
    sbe_years = sbe.get("years", [])
    if year in sbe_years:
        url_templates = sbe.get("url_templates", {})
        url_overrides = sbe.get("url_overrides", {})

        for slug, state_abbr in sbe["states"].items():
            # Check for explicit override first
            override_key = f"{slug}_{year}"
            override_url = (
                url_overrides.get(override_key)
                or url_overrides.get(str(override_key))
            )
            if override_url:
                url = override_url
            else:
                # YAML parses unquoted 2016 as int; try both key types
                template = (
                    url_templates.get(year)
                    or url_templates.get(str(year))
                    or url_templates.get("default", "")
                )
                hyphen_slug = _HYPHENATED_SLUGS.get(slug, slug)
                abbr = state_abbr.lower()
                url = template.format(
                    slug=slug, hyphen_slug=hyphen_slug, abbr=abbr, year=year,
                )
            try:
                sbe_zip = _download(url, cache_dir, f"SBE {state_abbr} {year}")
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError):
                continue
            try:
                r = _load_rate(sbe_zip)
                p = _load_plan_attrs(sbe_zip)
                s = _load_service_area(sbe_zip)
            except (FileNotFoundError, KeyError, ValueError) as e:
                log.warning("  SBE %s %d: skipping (incompatible PUF format: %s)", state_abbr, year, e)
                continue
            rates_parts.append(r)
            plans_parts.append(p)
            sa_parts.append(s)

    if not rates_parts:
        empty = pd.DataFrame()
        return empty, empty, empty

    rates = pd.concat(rates_parts, ignore_index=True)
    plans = pd.concat(plans_parts, ignore_index=True)
    sa = pd.concat(sa_parts, ignore_index=True)
    return rates, plans, sa


# ---------------------------------------------------------------------------
# County-to-rating-area crosswalk
# ---------------------------------------------------------------------------

def load_county_rating_areas(url: str, cache_dir: Path) -> pd.DataFrame:
    """Load the county → rating area mapping."""
    raw = _download(url, cache_dir, "CountyRAs")
    df = pd.read_csv(io.BytesIO(raw), dtype={"statefip": str, "countyfip": str})
    df["countyfip"] = df["countyfip"].str.zfill(5)
    df["statefip"] = df["statefip"].str.zfill(2)
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
    state_counties: pd.DataFrame,
) -> pd.DataFrame:
    """Compute SLCSP and LCBP for every county.

    Parameters
    ----------
    rates : Rate PUF (age-30 rows only)
    plans : Plan Attributes PUF (Silver/Bronze Individual medical)
    sa    : Service Area PUF (Individual non-dental)
    county_ras : county FIPS → RatingAreaId mapping
    state_counties : DataFrame with StateCode and County columns
                     (derived from county_ras + _STATE_ABBR_TO_FIPS)

    Returns DataFrame with columns: fips, Raw_Cost_of_Silver, Raw_Cost_of_Bronze
    """

    # 1. Join plans with service areas to get plan → county mapping
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

    if not cover_all.empty:
        cover_all_expanded = cover_all.merge(
            state_counties, on="StateCode", how="inner",
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
    plan_county = plan_county.merge(
        rates[["PlanId", "RatingAreaId", "IndividualRate"]],
        left_on=["StandardComponentId", "RatingAreaId"],
        right_on=["PlanId", "RatingAreaId"],
        how="inner",
    )

    # 5. Compute SLCSP and LCBP per county
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
# Build long-format output
# ---------------------------------------------------------------------------

def to_long_format(premiums: pd.DataFrame, year: int) -> pd.DataFrame:
    """Convert wide premiums (fips, Raw_Cost_of_Silver, Raw_Cost_of_Bronze)
    to long format (geoid, year, measure, value, moe, region_type).
    """
    df = premiums.rename(columns={
        "Raw_Cost_of_Silver": "marketplace_slcsp",
        "Raw_Cost_of_Bronze": "marketplace_lcbp",
    })
    df = df.melt(
        id_vars=["fips"],
        value_vars=["marketplace_slcsp", "marketplace_lcbp"],
        var_name="measure",
        value_name="value",
    )
    df = df.dropna(subset=["value"])
    df["value"] = df["value"].round(2)
    df = df.rename(columns={"fips": "geoid"})
    df["year"] = year
    df["moe"] = pd.NA
    df["region_type"] = "county"
    return df[["geoid", "year", "measure", "value", "moe", "region_type"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        source_cfg = config["sources"]["ncr"]
        puf_config = source_cfg["cms_puf"]
        cache_dir = TOPIC_DIR / "data" / "Working" / "puf_cache"

        # 1. Load county → rating area crosswalk (stable across years)
        county_ras = load_county_rating_areas(
            puf_config["county_rating_areas_url"], cache_dir,
        )

        # 2. Build state abbreviation → county FIPS mapping from county_ras
        fips_to_abbr = {v: k for k, v in _STATE_ABBR_TO_FIPS.items()}
        state_counties = county_ras[["statefip", "countyfip"]].drop_duplicates().copy()
        state_counties["StateCode"] = state_counties["statefip"].map(fips_to_abbr)
        state_counties = (
            state_counties.dropna(subset=["StateCode"])
            .rename(columns={"countyfip": "County"})
            [["StateCode", "County"]]
        )

        # 3. Process each year (union of FFM and SBE years)
        ffm_years = set(puf_config["puf"]["ffm"]["years"])
        sbe_years = set(puf_config["puf"]["sbe"].get("years", []))
        all_years = sorted(ffm_years | sbe_years)
        all_parts: list[pd.DataFrame] = []

        for year in all_years:
            log.info("Processing plan year %d…", year)
            rates, plans, sa = _load_pufs_for_year(
                puf_config["puf"], year, cache_dir,
            )
            if rates.empty:
                log.warning("  PY%d: no PUF data found, skipping", year)
                continue
            premiums = compute_premiums(rates, plans, sa, county_ras, state_counties)
            log.info("  PY%d: %d counties with premium data", year, len(premiums))
            long = to_long_format(premiums, year)
            all_parts.append(long)

        if not all_parts:
            return RunResult(
                success=False,
                error="No PUF data found for any year",
                duration_sec=time.time() - t0,
            )

        df = pd.concat(all_parts, ignore_index=True)

        # 4. Write output
        DIST_DIR.mkdir(parents=True, exist_ok=True)
        auto_name = build_file_name(
            df=df,
            coverage_area="us",
            years=sorted(df["year"].unique().tolist()),
            source_type=source_cfg.get("type"),
            title="marketplace_premium",
        )
        out_path = write_data(df, DIST_DIR / f"{auto_name}.csv.xz")
        log.info("Wrote %d rows to %s", len(df), out_path)

        n_years = df["year"].nunique()
        n_silver = df[df["measure"] == "marketplace_slcsp"].shape[0]
        n_bronze = df[df["measure"] == "marketplace_lcbp"].shape[0]

        log.info(
            "Done: %d rows across %d years (%d SLCSP, %d LCBP)",
            len(df), n_years, n_silver, n_bronze,
        )

        return RunResult(
            success=True,
            rows=len(df),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
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
