"""Download source data files for the Food Accessibility Indicator pipeline.

Fetches:
1. USDA FARA 2015 Excel (from ZIP) → FoodAccessResearchAtlasData2015.xlsx
2. USDA FARA 2019 Excel (direct)   → FoodAccessResearchAtlasData2019.xlsx
3. Census 2010→2020 tract crosswalk → crosswalk_tracts.csv

Writes all to data/original/.
"""

import zipfile
from io import BytesIO
from pathlib import Path

import requests
from sdc_core.log import get_logger

TOPIC_DIR = Path(__file__).resolve().parents[2]
ORIG_DIR = TOPIC_DIR / "data" / "original"

FARA_2015_ZIP_URL = "https://www.ers.usda.gov/media/5623/2015-food-access-research-atlas.zip"
FARA_2015_INNER = "FoodAccessResearchAtlasData2015.xlsx"

FARA_2019_URL = "https://www.ers.usda.gov/media/5626/food-access-research-atlas-data-download-2019.xlsx"
FARA_2019_FILE = "FoodAccessResearchAtlasData2019.xlsx"

CROSSWALK_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/tract/tab20_tract20_tract10_natl.txt"
CROSSWALK_FILE = "crosswalk_tracts.csv"

log = get_logger("food_access.download")


def download_fara_2015() -> Path:
    """Download FARA 2015 ZIP and extract the Excel file."""
    out = ORIG_DIR / FARA_2015_INNER
    log.info("Downloading FARA 2015 ZIP (%.0f MB)...", 75.6)
    resp = requests.get(FARA_2015_ZIP_URL, timeout=300)
    resp.raise_for_status()

    with zipfile.ZipFile(BytesIO(resp.content)) as zf:
        data = zf.read(FARA_2015_INNER)
        out.write_bytes(data)

    size_mb = out.stat().st_size / 1024 / 1024
    log.info("Wrote %s (%.1f MB)", out.name, size_mb)
    return out


def download_fara_2019() -> Path:
    """Download FARA 2019 Excel directly."""
    out = ORIG_DIR / FARA_2019_FILE
    log.info("Downloading FARA 2019 Excel (%.0f MB)...", 85.8)
    resp = requests.get(FARA_2019_URL, timeout=300)
    resp.raise_for_status()
    out.write_bytes(resp.content)

    size_mb = len(resp.content) / 1024 / 1024
    log.info("Wrote %s (%.1f MB)", out.name, size_mb)
    return out


def download_crosswalk() -> Path:
    """Download Census 2010→2020 tract relationship file."""
    out = ORIG_DIR / CROSSWALK_FILE
    log.info("Downloading Census tract crosswalk (%.0f MB)...", 18.7)
    resp = requests.get(CROSSWALK_URL, timeout=120)
    resp.raise_for_status()
    out.write_bytes(resp.content)

    size_mb = len(resp.content) / 1024 / 1024
    log.info("Wrote %s (%.1f MB)", out.name, size_mb)
    return out


def main() -> None:
    ORIG_DIR.mkdir(parents=True, exist_ok=True)
    download_fara_2015()
    download_fara_2019()
    download_crosswalk()
    log.info("Download complete.")


if __name__ == "__main__":
    main()
