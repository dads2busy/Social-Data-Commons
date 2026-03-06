"""Download GTFS feed zips for a target year.

For the current year, uses Mobility Database latest URLs.
For historical years, uses Transitland API to find the closest feed version.

Usage:
    uv run python fetch_feeds.py --year 2024
    uv run python fetch_feeds.py --year 2019 --transitland-key YOUR_KEY

Requires TRANSITLAND_API_KEY env var or --transitland-key for historical years.

Output: data/gtfs_cache/{year}/ directory with one zip per feed.
"""

import argparse
import os
import time
import urllib.request
from pathlib import Path

import pandas as pd
from sdc_core.log import get_logger

BASE_DIR = Path(__file__).resolve().parents[1]
CATALOG_PATH = BASE_DIR / "data/feeds_catalog.csv"
CACHE_DIR = BASE_DIR / "data/gtfs_cache"

TRANSITLAND_API_BASE = "https://transit.land/api/v2/rest"

log = get_logger("transit_stops.fetch_feeds")


def download_latest(feed_id: str, latest_url: str, dest: Path) -> bool:
    """Download the latest feed version from Mobility Database."""
    try:
        urllib.request.urlretrieve(latest_url, dest)
        return True
    except Exception as e:
        log.warning("Failed to download %s: %s", feed_id, e)
        return False


def download_historical(feed_id: str, year: int, api_key: str, dest: Path) -> bool:
    """Download the closest feed version to the target year from Transitland.

    Strategy: query feed versions, find the one whose fetched_at is closest
    to July 1 of the target year.
    """
    # TODO: Map Mobility Database feed IDs to Transitland onestop_ids.
    # This requires a crosswalk between the two catalogs, which could be
    # built by matching on agency name + bounding box overlap.
    #
    # Once mapped, the Transitland API call would be:
    #   GET /feed_versions?feed_onestop_id={onestop_id}&fetched_after={year}-01-01&fetched_before={year+1}-01-01
    #
    # Then download the best match:
    #   GET /feed_versions/{sha1}/download
    #   Headers: apikey={api_key}
    log.debug("Historical download not yet implemented for %s year=%d", feed_id, year)
    return False


def run(year: int, transitland_key: str | None = None):
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"Catalog not found at {CATALOG_PATH}. Run fetch_catalog.py first."
        )

    catalog = pd.read_csv(CATALOG_PATH, dtype=str)
    active = catalog[catalog["status"] == "active"]
    log.info("Processing %d active feeds for year %d", len(active), year)

    dest_dir = CACHE_DIR / str(year)
    dest_dir.mkdir(parents=True, exist_ok=True)

    success = 0
    skipped = 0
    failed = 0

    for _, row in active.iterrows():
        feed_id = row["id"]
        dest = dest_dir / f"{feed_id}.zip"

        if dest.exists():
            skipped += 1
            continue

        # TODO: determine if year is "current" based on whether feeds are
        # likely to still represent the target year's service.
        # For now, use latest URL for any year (placeholder logic).
        if row.get("latest_url") and pd.notna(row["latest_url"]):
            ok = download_latest(feed_id, row["latest_url"], dest)
        elif transitland_key:
            ok = download_historical(feed_id, year, transitland_key, dest)
        else:
            log.debug("No download URL for %s", feed_id)
            ok = False

        if ok:
            success += 1
        else:
            failed += 1

        # Rate limiting
        time.sleep(0.1)

    log.info(
        "Year %d: %d downloaded, %d cached, %d failed",
        year, success, skipped, failed,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download GTFS feeds for a target year")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--transitland-key", default=os.environ.get("TRANSITLAND_API_KEY"))
    args = parser.parse_args()
    run(args.year, args.transitland_key)
