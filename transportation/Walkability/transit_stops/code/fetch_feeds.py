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
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import pandas as pd
from sdc_core.log import get_logger

BASE_DIR = Path(__file__).resolve().parents[1]
CATALOG_PATH = BASE_DIR / "data/feeds_catalog.csv"
CROSSWALK_PATH = BASE_DIR / "data/mdb_transitland_crosswalk.csv"
CACHE_DIR = BASE_DIR / "data/gtfs_cache"

TRANSITLAND_API_BASE = "https://transit.land/api/v2/rest"
MAX_WORKERS = 20
TIMEOUT = 30  # seconds per download
TIMEOUT_HISTORICAL = 60  # longer timeout for Transitland downloads
MAX_SIZE = 100 * 1024 * 1024  # 100MB max per feed
CHUNK_SIZE = 64 * 1024  # 64KB chunks

log = get_logger("transit_stops.fetch_feeds")


def _streamed_download(url: str, dest: Path, headers: dict | None = None,
                       timeout: int = TIMEOUT) -> bool:
    """Download a URL to dest with streaming, size limit, and cleanup on failure."""
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            size = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_SIZE:
                        raise ValueError(f"Feed exceeds {MAX_SIZE // (1024*1024)}MB limit")
                    f.write(chunk)
        return True
    except Exception:
        if dest.exists():
            dest.unlink()
        raise


def download_latest(feed_id: str, latest_url: str, dest: Path) -> bool:
    """Download the latest feed version from Mobility Database."""
    try:
        return _streamed_download(latest_url, dest)
    except Exception as e:
        log.warning("Failed to download %s: %s", feed_id, e)
        return False


def _query_transitland(endpoint: str, api_key: str, params: dict | None = None) -> dict:
    """Query the Transitland REST API and return JSON response."""
    url = f"{TRANSITLAND_API_BASE}/{endpoint}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"
    req = urllib.request.Request(url, headers={"apikey": api_key})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def download_historical(feed_id: str, onestop_id: str, year: int,
                        api_key: str, dest: Path) -> bool:
    """Download the feed version closest to the target year from Transitland.

    Strategy:
      1. Query feed versions for the onestop_id within the target year window.
      2. Pick the version whose calendar dates best overlap with the target year.
      3. Download the GTFS zip by SHA1 hash.
    """
    try:
        # Query feed versions fetched within a wide window around the target year
        data = _query_transitland(
            f"feeds/{onestop_id}/feed_versions",
            api_key,
            params={
                "fetched_after": f"{year - 1}-06-01T00:00:00Z",
                "fetched_before": f"{year + 1}-06-01T00:00:00Z",
                "limit": 20,
            },
        )

        versions = data.get("feed_versions", [])
        if not versions:
            log.debug("No feed versions found for %s (%s) year=%d", feed_id, onestop_id, year)
            return False

        # Pick the version whose service dates best cover July 1 of the target year
        target = date(year, 7, 1)
        best_version = None
        best_score = float("inf")

        for v in versions:
            earliest = v.get("earliest_calendar_date", "")
            latest = v.get("latest_calendar_date", "")
            if not earliest or not latest:
                continue
            try:
                start = date.fromisoformat(earliest)
                end = date.fromisoformat(latest)
            except ValueError:
                continue

            # Score: prefer versions whose service window contains the target date
            if start <= target <= end:
                # Contains target — score by how centered the target is
                score = 0
            else:
                # Doesn't contain target — score by distance
                score = min(abs((target - start).days), abs((target - end).days))

            if score < best_score:
                best_score = score
                best_version = v

        if best_version is None:
            log.debug("No suitable version for %s (%s) year=%d", feed_id, onestop_id, year)
            return False

        sha1 = best_version["sha1"]
        log.debug(
            "Selected version %s for %s year=%d (service: %s to %s)",
            sha1[:12], feed_id, year,
            best_version.get("earliest_calendar_date"),
            best_version.get("latest_calendar_date"),
        )

        # Download the GTFS zip
        download_url = f"{TRANSITLAND_API_BASE}/feed_versions/{sha1}/download"
        return _streamed_download(
            download_url, dest,
            headers={"apikey": api_key},
            timeout=TIMEOUT_HISTORICAL,
        )

    except Exception as e:
        log.warning("Failed historical download %s (%s): %s", feed_id, onestop_id, e)
        return False


def _download_task(row: dict, dest_dir: Path, year: int,
                   transitland_key: str | None,
                   crosswalk: dict[str, str]) -> tuple[str, str]:
    """Download a single feed. Returns (feed_id, status)."""
    feed_id = row["id"]
    dest = dest_dir / f"{feed_id}.zip"

    if dest.exists():
        return feed_id, "skipped"

    # For current/recent years, use Mobility Database latest URLs
    if row.get("latest_url") and pd.notna(row["latest_url"]) and not transitland_key:
        ok = download_latest(feed_id, row["latest_url"], dest)
        return feed_id, "success" if ok else "failed"

    # If we have a Transitland key + crosswalk match, use historical download
    if transitland_key:
        onestop_id = crosswalk.get(feed_id, "")
        if onestop_id:
            ok = download_historical(feed_id, onestop_id, year, transitland_key, dest)
            if ok:
                return feed_id, "success"
        # Fall back to latest URL if historical download fails or no crosswalk match
        if row.get("latest_url") and pd.notna(row["latest_url"]):
            ok = download_latest(feed_id, row["latest_url"], dest)
            return feed_id, "success" if ok else "failed"

    return feed_id, "failed"


def _load_crosswalk() -> dict[str, str]:
    """Load the MDB→Transitland crosswalk. Returns {mdb_id: onestop_id}."""
    if not CROSSWALK_PATH.exists():
        return {}
    df = pd.read_csv(CROSSWALK_PATH, dtype=str)
    return dict(zip(df["mdb_id"], df["onestop_id"]))


def run(year: int, transitland_key: str | None = None):
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"Catalog not found at {CATALOG_PATH}. Run fetch_catalog.py first."
        )

    catalog = pd.read_csv(CATALOG_PATH, dtype=str)
    active = catalog[catalog["status"] == "active"]
    log.info("Processing %d active feeds for year %d", len(active), year)

    crosswalk = _load_crosswalk()
    if transitland_key:
        log.info("Transitland key provided. Crosswalk has %d entries.", len(crosswalk))
        if not crosswalk:
            log.warning("No crosswalk found. Run build_crosswalk.py first for historical downloads.")
    else:
        log.info("No Transitland key. Using Mobility Database latest URLs only.")

    dest_dir = CACHE_DIR / str(year)
    dest_dir.mkdir(parents=True, exist_ok=True)

    rows = active.to_dict("records")

    success = 0
    skipped = 0
    failed = 0

    # Use fewer workers for Transitland API to avoid rate limiting
    workers = 5 if transitland_key else MAX_WORKERS

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_download_task, row, dest_dir, year, transitland_key, crosswalk): row["id"]
            for row in rows
        }

        for future in as_completed(futures):
            feed_id, status = future.result()
            if status == "success":
                success += 1
            elif status == "skipped":
                skipped += 1
            else:
                failed += 1

            total = success + skipped + failed
            if total % 50 == 0:
                log.info("Progress: %d/%d (downloaded=%d, cached=%d, failed=%d)",
                         total, len(rows), success, skipped, failed)

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
