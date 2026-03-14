"""County Health Rankings (CHR) data ingestion.

Provides a shared function for downloading and parsing CHR Excel files.
Used by multiple pipeline topics (e.g. Funding, Cooperative Extension).
"""

import logging
from pathlib import Path

import httpx
import pandas as pd
from tqdm import tqdm

log = logging.getLogger(__name__)


def _resolve_col(measure_def: dict, year: int) -> str | None:
    """Resolve column name for a given year.

    Supports two formats:

    - ``column: "Name"`` — single fixed name across all years
    - ``columns: {2022: "Old Name", 2023: "New Name"}`` — year-keyed dict
    """
    if "column" in measure_def:
        return measure_def["column"]
    col_by_year = measure_def.get("columns", {})
    return col_by_year.get(str(year)) or col_by_year.get(year)


def _resolve_sheet(chr_cfg: dict, year: int, default: str) -> str:
    """Resolve the Excel sheet name for a given year.

    Supports:
    - ``sheet_name: "Name"`` — single fixed name across all years
    - ``sheet_names: {2023: "Old Name", 2024: "New Name"}`` — year-keyed dict
    """
    by_year = chr_cfg.get("sheet_names", {})
    resolved = by_year.get(str(year)) or by_year.get(year)
    if resolved:
        return resolved
    return chr_cfg.get("sheet_name", default)


def ingest_chr(
    chr_cfg: dict,
    working_dir: Path,
    *,
    state_fips_prefix: str | None = None,
    sheet_name: str = "Additional Measure Data",
) -> pd.DataFrame:
    """Download CHR Excel files and extract measures into a long-format DataFrame.

    Parameters
    ----------
    chr_cfg:
        The ``county_health_rankings:`` block from a pipeline config, containing:

        - ``urls``: mapping of year -> download URL
        - ``measures``: list of dicts, each with ``name`` and either
          ``column`` (fixed name across years) or ``columns`` (year-keyed dict)
        - ``sheet_name`` (optional): overrides the *sheet_name* parameter
        - ``sheet_names`` (optional): year-keyed dict for per-year sheet names

    working_dir:
        Directory where downloaded Excel files are cached.

    state_fips_prefix:
        If given (e.g. ``"51"`` for Virginia), only rows whose FIPS starts
        with this prefix are kept.  Pass ``None`` to keep all rows.

    sheet_name:
        Excel sheet to read.  Defaults to ``"Additional Measure Data"``.
        Can also be set via ``chr_cfg["sheet_name"]`` or per-year via
        ``chr_cfg["sheet_names"]``.

    Returns
    -------
    pd.DataFrame with columns: geoid, year, measure, value, moe, region_type
    """
    urls = chr_cfg["urls"]
    measures = chr_cfg["measures"]
    working_dir = Path(working_dir)
    working_dir.mkdir(parents=True, exist_ok=True)

    records = []
    for year, url in tqdm(urls.items(), desc="CHR"):
        year = int(year)
        tmp = working_dir / f"chr_{year}.xlsx"

        if tmp.exists():
            log.info("Using cached CHR %d: %s", year, tmp)
        else:
            try:
                resp = httpx.get(url, timeout=30, follow_redirects=True)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                log.warning("Could not download CHR %d: %s", year, e)
                continue
            tmp.write_bytes(resp.content)

        resolved_sheet = _resolve_sheet(chr_cfg, year, sheet_name)
        try:
            df = pd.read_excel(tmp, sheet_name=resolved_sheet, header=1)
        except Exception as e:
            log.warning("Could not parse CHR %d: %s", year, e)
            continue

        if "FIPS" not in df.columns:
            log.warning("No FIPS column in CHR %d, skipping", year)
            continue

        # Defragment before adding columns (avoids pandas PerformanceWarning on
        # wide CHR sheets that have been parsed with many columns)
        df = df.copy()

        # Newer CHR files (2024+) store FIPS as floats (e.g. 51001.0)
        df["geoid"] = (
            pd.to_numeric(df["FIPS"], errors="coerce")
            .apply(lambda x: str(int(x)).zfill(5) if pd.notna(x) else None)
        )

        if state_fips_prefix:
            n = len(state_fips_prefix)
            df = df[df["geoid"].str[:n] == state_fips_prefix].copy()

        for measure_def in measures:
            col_name = _resolve_col(measure_def, year)
            measure_name = measure_def["name"]
            if col_name and col_name in df.columns:
                subset = df[["geoid"]].copy()
                subset["year"] = year
                subset["measure"] = measure_name
                subset["value"] = pd.to_numeric(df[col_name], errors="coerce")
                subset["moe"] = pd.NA
                subset["region_type"] = "county"
                records.append(subset.dropna(subset=["value"]))
            else:
                log.warning(
                    "Column '%s' not found in CHR %d, skipping", col_name, year
                )

    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()
