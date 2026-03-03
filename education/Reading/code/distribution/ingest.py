"""Ingest 3rd grade English reading SOL pass rates from VDOE.

Reads "Division Test-by-Test" Excel/CSV files from data/working/ (downloaded
manually from the VDOE SOL Test Pass Rates page), extracts Grade 3 English
Reading pass rates by school division, and maps division names to Virginia
county FIPS codes via Census county names.

Year convention: school year start year (2015-2016 -> year 2015).

Files cover three school years each; when years overlap between files, the
most recent file takes precedence.

Download source:
  https://www.doe.virginia.gov/data-policy-funding/data-reports/statistics-reports/sol-test-pass-rates-other-results
  -> "Division Test-by-Test" links
"""

import re
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
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
WORKING_DIR = TOPIC_DIR / "data/working"

log = get_logger("reading_scores.ingest")

SUBJECT = "English: Reading"
GRADE = "Gr 3"


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Division name -> county FIPS crosswalk
# ---------------------------------------------------------------------------

# VDOE division names that don't match Census county names directly.
# These are combined divisions or towns with independent school divisions.
DIVISION_EXCEPTIONS: dict[str, str] = {
    "alleghany highlands": "51005",  # Alleghany County (combined w/ Covington City)
    "colonial beach": "51193",       # Westmoreland County (Colonial Beach is a town)
    "west point": "51101",           # King William County (West Point is a town)
    "williamsburg james city county": "51095",  # James City County (combined division; hyphen stripped by normalization)
}


def _normalize(name: str) -> str:
    """Lowercase, collapse whitespace, remove punctuation for matching."""
    name = name.lower().strip()
    name = re.sub(r"[-]", " ", name)  # treat hyphens as word separators
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name


def get_division_fips_crosswalk() -> dict[str, str]:
    """Map VDOE division names to Virginia county/city FIPS codes.

    Fetches Virginia county names from the Census Bureau's decennial API
    and matches them to VDOE division names by normalized string comparison.
    """
    url = (
        "https://api.census.gov/data/2020/dec/pl"
        "?get=NAME&for=county:*&in=state:51"
    )
    resp = httpx.get(url, timeout=30)
    resp.raise_for_status()
    headers, *rows = resp.json()

    # Census returns: [NAME, state, county]
    # NAME is like "Accomack County, Virginia" or "Alexandria city, Virginia"
    crosswalk: dict[str, str] = {}
    for row in rows:
        full_name = row[0]
        state_fips = row[1]
        county_fips = row[2]
        geoid = state_fips + county_fips
        # Strip ", Virginia" suffix
        short_name = full_name.split(", Virginia")[0].strip()
        crosswalk[_normalize(short_name)] = geoid

    log.info("Loaded %d VA county/city FIPS codes from Census", len(crosswalk))
    return crosswalk


def match_division(div_name: str, crosswalk: dict[str, str]) -> str | None:
    """Return the FIPS for a VDOE division name, or None if not matched."""
    key = _normalize(div_name)
    if key in DIVISION_EXCEPTIONS:
        return DIVISION_EXCEPTIONS[key]
    if key in crosswalk:
        return crosswalk[key]
    # VDOE uses "City" (capital C); Census uses "city" (lowercase c) — already
    # handled by normalization. Try also without type suffix as last resort.
    key_no_suffix = re.sub(r"\s+(county|city)$", "", key).strip()
    matches = [
        geoid
        for census_name, geoid in crosswalk.items()
        if re.sub(r"\s+(county|city)$", "", census_name) == key_no_suffix
    ]
    if len(matches) == 1:
        return matches[0]
    return None


# ---------------------------------------------------------------------------
# File parsing
# ---------------------------------------------------------------------------

def _read_file(path: Path, header_row: int) -> pd.DataFrame:
    """Read a division-test-by-test file regardless of format."""
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, header=header_row)
    return pd.read_excel(path, header=header_row)


def _year_from_col(col: str) -> int | None:
    """Extract the start year from a column like '2015-2016 Pass Rate'."""
    m = re.match(r"^(\d{4})-\d{4}\s+Pass Rate$", col.strip())
    return int(m.group(1)) if m else None


def parse_file(path: Path, header_row: int) -> pd.DataFrame:
    """Extract Gr 3 English Reading pass rates from one working file.

    Returns a DataFrame with columns: div_name, year, value.
    """
    df = _read_file(path, header_row)

    # Normalize column names (strip whitespace)
    df.columns = [str(c).strip() for c in df.columns]

    # Keep only division-level rows
    if "LEVEL" in df.columns:
        df = df[df["LEVEL"].astype(str).str.strip() == "DIV"].copy()

    # Filter to Gr 3 English Reading
    df = df[
        df["Subject"].astype(str).str.strip() == SUBJECT
    ]
    df = df[df["Grade"].astype(str).str.strip() == GRADE]

    if df.empty:
        log.warning("No Gr 3 English Reading rows in %s", path.name)
        return pd.DataFrame()

    # Identify pass-rate columns and melt to long format
    pass_rate_cols = [c for c in df.columns if _year_from_col(c) is not None]
    if not pass_rate_cols:
        log.warning("No pass-rate columns found in %s", path.name)
        return pd.DataFrame()

    id_col = "Div Name" if "Div Name" in df.columns else None
    if id_col is None:
        log.warning("No 'Div Name' column in %s", path.name)
        return pd.DataFrame()

    melted = df[[id_col] + pass_rate_cols].melt(
        id_vars=[id_col],
        var_name="col",
        value_name="value",
    )
    melted["year"] = melted["col"].map(_year_from_col)
    melted = melted.rename(columns={id_col: "div_name"})
    melted["value"] = pd.to_numeric(melted["value"], errors="coerce")
    melted = melted.dropna(subset=["value", "year"])
    return melted[["div_name", "year", "value"]].copy()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        source_cfg = config["sources"]["va"]
        working_files = source_cfg["working_files"]

        log.info("Building division -> FIPS crosswalk from Census")
        crosswalk = get_division_fips_crosswalk()

        # Parse all working files; later files override earlier ones for
        # the same (div_name, year) pair
        all_records: dict[tuple, float] = {}
        unmatched: set[str] = set()

        for file_cfg in working_files:
            path = WORKING_DIR / file_cfg["filename"]
            if not path.exists():
                log.warning("Working file not found, skipping: %s", path.name)
                continue
            log.info("Parsing %s", path.name)
            rows = parse_file(path, file_cfg["header_row"])
            if rows.empty:
                continue
            for _, row in rows.iterrows():
                all_records[(row["div_name"], int(row["year"]))] = row["value"]

        if not all_records:
            return RunResult(
                success=False,
                error="No data parsed from any working file",
                duration_sec=time.time() - t0,
            )

        # Map division names to county FIPS
        records = []
        for (div_name, year), value in all_records.items():
            geoid = match_division(div_name, crosswalk)
            if geoid is None:
                unmatched.add(div_name)
                continue
            records.append(
                {
                    "geoid": geoid,
                    "year": year,
                    "measure": "mean_read_pass_rate",
                    "value": round(value, 2),
                    "moe": pd.NA,
                    "region_type": "county",
                }
            )

        if unmatched:
            log.warning(
                "%d division names could not be matched to FIPS: %s",
                len(unmatched),
                sorted(unmatched),
            )

        result = pd.DataFrame(records).sort_values(
            ["geoid", "year", "measure"]
        ).reset_index(drop=True)

        auto_name = build_file_name(
            df=result,
            states=["VA"],
            years=sorted(result["year"].unique().tolist()),
            source_type=source_cfg.get("type"),
            title="3rd_grade_read_pass_rate",
        )
        DIST_DIR.mkdir(parents=True, exist_ok=True)
        out_path = write_data(result, DIST_DIR / f"{auto_name}.csv.xz")
        log.info(
            "Wrote %d rows (%d unmatched divisions) to %s",
            len(result),
            len(unmatched),
            out_path,
        )

        return RunResult(
            success=True,
            rows=len(result),
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
