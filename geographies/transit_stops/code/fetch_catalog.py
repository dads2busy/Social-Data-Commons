"""Fetch the Mobility Database catalog and filter to US GTFS schedule feeds.

Output: data/feeds_catalog.csv with columns:
  id, provider, name, subdivision_name, municipality,
  direct_download_url, latest_url, status,
  min_lat, max_lat, min_lon, max_lon
"""

import urllib.request
from io import StringIO
from pathlib import Path

import pandas as pd
from sdc_core.log import get_logger

CATALOG_URL = "https://files.mobilitydatabase.org/feeds_v2.csv"
BASE_DIR = Path(__file__).resolve().parents[1]
OUT_PATH = BASE_DIR / "data/feeds_catalog.csv"

log = get_logger("transit_stops.fetch_catalog")


def run():
    log.info("Downloading Mobility Database catalog from %s", CATALOG_URL)
    response = urllib.request.urlopen(CATALOG_URL)
    raw = response.read().decode("utf-8")
    df = pd.read_csv(StringIO(raw), dtype=str)

    # Filter to US GTFS schedule feeds
    us_gtfs = df[
        (df["location.country_code"] == "US")
        & (df["data_type"] == "gtfs")
    ].copy()

    log.info("Total US GTFS feeds: %d (active: %d)", len(us_gtfs), (us_gtfs["status"] == "active").sum())

    out = us_gtfs.rename(columns={
        "location.subdivision_name": "subdivision_name",
        "location.municipality": "municipality",
        "urls.direct_download": "direct_download_url",
        "urls.latest": "latest_url",
        "location.bounding_box.minimum_latitude": "min_lat",
        "location.bounding_box.maximum_latitude": "max_lat",
        "location.bounding_box.minimum_longitude": "min_lon",
        "location.bounding_box.maximum_longitude": "max_lon",
    })[
        ["id", "provider", "name", "subdivision_name", "municipality",
         "direct_download_url", "latest_url", "status",
         "min_lat", "max_lat", "min_lon", "max_lon"]
    ]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    log.info("Wrote %d feeds to %s", len(out), OUT_PATH)


if __name__ == "__main__":
    run()
