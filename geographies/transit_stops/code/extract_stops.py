"""Extract transit stop locations from downloaded GTFS zips.

Reads all zips in data/gtfs_cache/{year}/, extracts stops.txt from each,
deduplicates by snapping to a ~10m grid, and writes a consolidated parquet.

Usage:
    uv run python extract_stops.py --year 2024

Output: data/stops/us_transit_stops_{year}.parquet
"""

import argparse
import zipfile
from io import TextIOWrapper
from pathlib import Path

import pandas as pd
from sdc_core.log import get_logger

BASE_DIR = Path(__file__).resolve().parents[1]
CACHE_DIR = BASE_DIR / "data/gtfs_cache"
STOPS_DIR = BASE_DIR / "data/stops"

log = get_logger("transit_stops.extract_stops")

# Grid resolution for deduplication (~10m at mid-latitudes)
GRID_PRECISION = 4  # decimal places


def extract_stops_from_zip(zip_path: Path) -> pd.DataFrame | None:
    """Extract stops.txt from a GTFS zip file."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            # stops.txt may be at root or in a subdirectory
            stops_file = next(
                (n for n in names if n.endswith("stops.txt")),
                None,
            )
            if stops_file is None:
                log.debug("No stops.txt in %s", zip_path.name)
                return None

            with zf.open(stops_file) as f:
                df = pd.read_csv(
                    TextIOWrapper(f, encoding="utf-8-sig"),
                    usecols=lambda c: c in {"stop_id", "stop_name", "stop_lat", "stop_lon"},
                    dtype={"stop_id": str, "stop_name": str},
                )
            if df.empty or "stop_lat" not in df.columns:
                return None

            df["feed_id"] = zip_path.stem  # e.g., "mdb-1846"
            return df

    except (zipfile.BadZipFile, Exception) as e:
        log.warning("Failed to read %s: %s", zip_path.name, e)
        return None


def deduplicate_stops(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate stops by snapping to a grid.

    Multiple feeds may report stops at the same physical location
    (e.g., WMATA bus and rail). Snap to ~10m grid and keep one per cell.
    """
    df = df.dropna(subset=["stop_lat", "stop_lon"]).copy()
    df = df[
        (df["stop_lat"].between(-90, 90))
        & (df["stop_lon"].between(-180, 180))
        & (df["stop_lat"] != 0)
    ]

    df["grid_lat"] = df["stop_lat"].round(GRID_PRECISION)
    df["grid_lon"] = df["stop_lon"].round(GRID_PRECISION)
    deduped = df.drop_duplicates(subset=["grid_lat", "grid_lon"])
    deduped = deduped.drop(columns=["grid_lat", "grid_lon"])

    log.info("Deduplicated %d stops to %d unique locations", len(df), len(deduped))
    return deduped


def run(year: int):
    year_dir = CACHE_DIR / str(year)
    if not year_dir.exists():
        raise FileNotFoundError(
            f"No GTFS cache for year {year}. Run fetch_feeds.py --year {year} first."
        )

    zips = sorted(year_dir.glob("*.zip"))
    log.info("Processing %d GTFS zips for year %d", len(zips), year)

    # Load feed catalog for agency names
    catalog_path = BASE_DIR / "data/feeds_catalog.csv"
    agency_map = {}
    if catalog_path.exists():
        catalog = pd.read_csv(catalog_path, dtype=str, usecols=["id", "provider"])
        agency_map = dict(zip(catalog["id"], catalog["provider"]))

    parts = []
    for zip_path in zips:
        stops = extract_stops_from_zip(zip_path)
        if stops is not None and not stops.empty:
            parts.append(stops)

    if not parts:
        log.warning("No stops extracted for year %d", year)
        return

    all_stops = pd.concat(parts, ignore_index=True)
    all_stops["agency_name"] = all_stops["feed_id"].map(agency_map).fillna("")
    log.info("Total raw stops: %d from %d feeds", len(all_stops), len(parts))

    deduped = deduplicate_stops(all_stops)

    STOPS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = STOPS_DIR / f"us_transit_stops_{year}.parquet"
    deduped[["stop_lat", "stop_lon", "feed_id", "agency_name", "stop_name"]].to_parquet(
        out_path, index=False,
    )
    log.info("Wrote %d stops to %s", len(deduped), out_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract stops from GTFS zips")
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()
    run(args.year)
