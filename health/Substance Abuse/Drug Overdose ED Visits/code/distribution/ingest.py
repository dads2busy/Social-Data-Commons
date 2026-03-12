"""Ingest drug overdose ED visit rates from VDH Excel file.

Data must be manually downloaded from:
  https://www.vdh.virginia.gov/surveillance-and-investigation/
  syndromic-surveillance/drug-overdose-surveillance/

Place the downloaded file in data/original/ before running this script.
Expected filename: Drug-Overdose-ED-Visits_Virginia-September-2021.xlsx

The Excel sheet (sheet index 2) has a two-row header:
  Row 0: Year/month labels ("January 2015", "2015 Total", etc.)
  Row 1: Sub-headers ("Locality", "FIPS", "Avg Monthly Rate per 100k Pop", etc.)

For 2015-2020, annual "Avg Monthly Rate per 100k Pop" columns are used directly.
For 2021, 9 monthly "Rate per 100k Pop" columns are averaged.
"""

import time
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"

log = get_logger("drug_overdose_ed_visits.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def parse_overdose_excel(filepath: Path, sheet_index: int) -> pd.DataFrame:
    """Parse the VDH drug overdose Excel file into long format.

    Uses FIPS codes from column 1 (no Census API lookup needed).
    """
    raw = pd.read_excel(filepath, sheet_name=sheet_index, header=None)

    sub_header = raw.iloc[1]
    month_header = raw.iloc[0]

    # Data rows: rows 2 through 134 (133 VA counties/cities)
    # Row 1 is sub-header, rows after 134 may be totals/notes
    n_rows = 133
    county_names = raw.iloc[2 : 2 + n_rows, 0].tolist()
    fips_codes = raw.iloc[2 : 2 + n_rows, 1].tolist()

    # Build GEOIDs from FIPS
    geoids = []
    for fips in fips_codes:
        try:
            geoids.append(str(int(fips)).zfill(5))
        except (ValueError, TypeError):
            geoids.append(None)

    # Clean county names (remove dagger symbol)
    county_names = [str(n).replace("\u2021", "").strip() for n in county_names]

    records: list[dict] = []

    # Find "Avg Monthly Rate per 100k Pop" columns in sub-header (row 1)
    avg_rate_cols = [
        i
        for i, val in enumerate(sub_header)
        if isinstance(val, str) and val == "Avg Monthly Rate per 100k Pop"
    ]

    # Map each avg column to its year using row 0 year headers
    for col_idx in avg_rate_cols:
        # Search backward in row 0 to find the year label
        year = None
        for j in range(col_idx, -1, -1):
            if pd.notna(month_header.iloc[j]):
                label = str(month_header.iloc[j])
                # Extract 4-digit year
                for word in label.split():
                    if word.isdigit() and len(word) == 4:
                        year = int(word)
                        break
                if year:
                    break
        if not year:
            continue

        values = raw.iloc[2 : 2 + n_rows, col_idx]
        for geoid, val in zip(geoids, values):
            if geoid is None:
                continue
            v = pd.to_numeric(val, errors="coerce")
            if pd.notna(v):
                records.append(
                    {
                        "geoid": geoid,
                        "year": year,
                        "measure": "avg_monthly_rate",
                        "value": float(v),
                    }
                )

    # 2021: average the 9 monthly "Rate per 100k Pop" columns
    # These are after the last annual block (2020 Total)
    last_avg_col = avg_rate_cols[-1] if avg_rate_cols else 0
    monthly_rate_cols = [
        i
        for i in range(last_avg_col + 1, raw.shape[1])
        if isinstance(sub_header.iloc[i], str) and sub_header.iloc[i] == "Rate per 100k Pop"
    ]

    if monthly_rate_cols:
        log.info("Found %d monthly rate columns for 2021", len(monthly_rate_cols))
        monthly_data = raw.iloc[2 : 2 + n_rows, monthly_rate_cols].apply(
            pd.to_numeric, errors="coerce"
        )
        # R code: replace NAs with 0, then average
        avg_2021 = monthly_data.fillna(0).mean(axis=1)

        for geoid, val in zip(geoids, avg_2021):
            if geoid is None:
                continue
            records.append(
                {
                    "geoid": geoid,
                    "year": 2021,
                    "measure": "avg_monthly_rate",
                    "value": float(val),
                }
            )
    else:
        log.warning("No 2021 monthly Rate per 100k Pop columns found")

    return pd.DataFrame(records)


def run() -> list[RunResult]:
    t0 = time.time()
    config = load_config()
    source_cfg = config["sources"]["va"]
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    try:
        working_file = source_cfg["vdh"]["working_files"][0]
        filepath = TOPIC_DIR / "data/original" / working_file["filename"]
        if not filepath.exists():
            return [
                RunResult(
                    success=False,
                    error=f"Source file not found: {filepath}. Download from "
                    f"{source_cfg['vdh']['download_url']}",
                    duration_sec=time.time() - t0,
                )
            ]

        log.info("Parsing %s", filepath)
        df = parse_overdose_excel(filepath, working_file["sheet_index"])

        if df.empty:
            return [
                RunResult(
                    success=False,
                    error="No data parsed from Excel file",
                    duration_sec=time.time() - t0,
                )
            ]

        df["moe"] = pd.NA
        df["region_type"] = "county"
        result = df[["geoid", "year", "measure", "value", "moe", "region_type"]].copy()

        auto_name = build_file_name(
            coverage_area="va",
            data_source="vdh",
            years=sorted(result["year"].unique().tolist()),
            title="drug_overdose_ed_visits",
        )
        out_path = write_data(result, DIST_DIR / f"{auto_name}.csv.xz")
        log.info("Wrote %d rows to %s", len(result), out_path)

        return [
            RunResult(
                success=True,
                rows=len(result),
                output_path=str(out_path),
                duration_sec=time.time() - t0,
            )
        ]
    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        return [
            RunResult(success=False, error=str(e), duration_sec=time.time() - t0)
        ]


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
