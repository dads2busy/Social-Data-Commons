"""Download source data files for the Incarceration Rate pipeline.

Fetches:
1. Vera Institute incarceration_trends_county.csv from GitHub
2. PPI 2020 VA tract data scraped from prisonpolicy.org HTML table

Writes both to data/original/.
"""

import re
from pathlib import Path

import pandas as pd
import requests
from sdc_core.log import get_logger

TOPIC_DIR = Path(__file__).resolve().parents[2]
ORIG_DIR = TOPIC_DIR / "data" / "original"

VERA_URL = (
    "https://raw.githubusercontent.com/vera-institute/incarceration-trends"
    "/main/incarceration_trends_county.csv"
)
PPI_URL = "https://www.prisonpolicy.org/origin/va/2020/tract.html"

log = get_logger("incarceration.download")


def download_vera() -> Path:
    """Download Vera Institute county-level incarceration trends CSV."""
    out = ORIG_DIR / "incarceration_trends_county.csv"
    log.info("Downloading Vera county trends from GitHub...")
    resp = requests.get(VERA_URL, timeout=120)
    resp.raise_for_status()
    out.write_bytes(resp.content)
    size_mb = len(resp.content) / 1024 / 1024
    log.info("Wrote %s (%.1f MB)", out.name, size_mb)
    return out


def download_ppi() -> Path:
    """Scrape PPI VA tract table from HTML and write as CSV."""
    out = ORIG_DIR / "ppi_va_tract_2020.csv"
    log.info("Scraping PPI tract data from %s...", PPI_URL)
    resp = requests.get(PPI_URL, timeout=60)
    resp.raise_for_status()

    # Parse all <tr> rows from the appendix table
    rows = []
    for tr in re.finditer(r"<tr[^>]*>(.*?)</tr>", resp.text, re.DOTALL):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr.group(1), re.DOTALL)
        if len(cells) == 6:
            # Clean HTML entities and formatting
            clean = [re.sub(r"&nbsp;", " ", c).replace(",", "").strip() for c in cells]
            rows.append(clean)

    if not rows:
        raise RuntimeError("No data rows found in PPI HTML table")

    df = pd.DataFrame(rows, columns=[
        "geoid", "name", "incarcerated", "census_pop", "total_pop", "rate_per_100k",
    ])

    # Convert numeric columns
    for col in ["incarcerated", "census_pop", "total_pop", "rate_per_100k"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df.to_csv(out, index=False)
    log.info("Wrote %s (%d tracts)", out.name, len(df))
    return out


def main() -> None:
    ORIG_DIR.mkdir(parents=True, exist_ok=True)
    download_vera()
    download_ppi()
    log.info("Download complete.")


if __name__ == "__main__":
    main()
