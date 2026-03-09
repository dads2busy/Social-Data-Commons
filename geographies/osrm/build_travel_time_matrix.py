"""Build a block-group-to-block-group driving time matrix using a local Docker OSRM server.

States: VA, MD, DC, DE, WV, NC, TN, KY (8 states for cross-border daycare modeling)
Source: Census 2020 block group centroids from TIGERweb API
Output: geographies/bg2bg_travel_times.csv.xz

Prerequisites — Docker OSRM setup (files stored in geographies/osrm/data/):

    1. One-time setup (~30-45 min, downloads ~4 GB, produces ~15 GB):
       cd geographies/osrm && bash setup.sh

    2. Start the OSRM server:
       cd geographies/osrm && docker compose up -d

    3. Stop when done:
       cd geographies/osrm && docker compose down

Usage:
    uv run python geographies/build_travel_time_matrix.py [--osrm-url http://localhost:5555]
"""

from __future__ import annotations

import argparse
import csv
import lzma
import math
import time
from collections import defaultdict
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).parent

# 8 states for daycare cross-border modeling
STATE_FIPS = ["10", "11", "21", "24", "37", "47", "51", "54"]
STATE_NAMES = {
    "10": "DE", "11": "DC", "21": "KY", "24": "MD",
    "37": "NC", "47": "TN", "51": "VA", "54": "WV",
}

TIGERWEB_BG_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/tigerWMS_Census2020/MapServer/8/query"
)

# Pre-filter: only query OSRM for pairs within this straight-line distance (km)
HAVERSINE_THRESHOLD_KM = 120.0

# Keep results within this driving time (minutes)
MAX_DRIVING_MINUTES = 60.0

# OSRM batch sizes — URL length is the practical limit (~4KB).
# Each coordinate is ~20 chars, so ~200 coordinates max per request.
# 25 sources x 175 destinations = 200 coords = 4,375 pairs per request.
SRC_CHUNK = 25
DST_CHUNK = 175

MAX_RETRIES = 3

# Output files
CENTROIDS_FILE = SCRIPT_DIR / "bg_centroids_2020.csv"
PROGRESS_FILE = SCRIPT_DIR / "_bg_travel_times_progress.csv"
OUTPUT_FILE = SCRIPT_DIR / "bg2bg_travel_times.csv.xz"


def download_bg_centroids() -> pd.DataFrame:
    """Download Census 2020 block group centroids from TIGERweb API."""
    if CENTROIDS_FILE.exists():
        print(f"Loading cached centroids from {CENTROIDS_FILE}")
        df = pd.read_csv(CENTROIDS_FILE, dtype={"geoid": str})
        print(f"  {len(df)} block groups loaded")
        return df

    print("Downloading block group centroids from TIGERweb...")
    all_rows = []

    with httpx.Client(timeout=60) as client:
        for fips in STATE_FIPS:
            state_name = STATE_NAMES[fips]

            resp = client.get(TIGERWEB_BG_URL, params={
                "where": f"STATE='{fips}'",
                "returnCountOnly": "true",
                "f": "json",
            })
            total = resp.json().get("count", 0)
            print(f"  {state_name} ({fips}): {total} block groups")

            offset = 0
            page_size = 1000
            fetched = 0
            while fetched < total:
                resp = client.get(TIGERWEB_BG_URL, params={
                    "where": f"STATE='{fips}'",
                    "outFields": "GEOID,CENTLAT,CENTLON",
                    "returnGeometry": "false",
                    "f": "json",
                    "resultOffset": str(offset),
                    "resultRecordCount": str(page_size),
                })
                resp.raise_for_status()
                features = resp.json().get("features", [])
                if not features:
                    break

                for feat in features:
                    a = feat["attributes"]
                    all_rows.append({
                        "geoid": a["GEOID"],
                        "lat": float(a["CENTLAT"]),
                        "lon": float(a["CENTLON"]),
                    })

                fetched += len(features)
                offset += page_size
                time.sleep(0.2)

            print(f"    fetched {fetched}")

    centroids = pd.DataFrame(all_rows)
    centroids.to_csv(CENTROIDS_FILE, index=False)
    print(f"  Saved {len(centroids)} block group centroids to {CENTROIDS_FILE}")
    return centroids


def build_neighbor_index(centroids: pd.DataFrame) -> dict[int, list[int]]:
    """For each BG (by index), find indices of BGs within haversine threshold."""
    print(f"Building neighbor index (threshold={HAVERSINE_THRESHOLD_KM} km)...")
    n = len(centroids)
    lats = np.radians(centroids["lat"].values)
    lons = np.radians(centroids["lon"].values)

    neighbors: dict[int, list[int]] = {}
    total_pairs = 0

    for i in range(n):
        dlat = lats - lats[i]
        dlon = lons - lons[i]
        a = (
            np.sin(dlat / 2) ** 2
            + np.cos(lats[i]) * np.cos(lats) * np.sin(dlon / 2) ** 2
        )
        dist_km = 6371.0 * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

        mask = (dist_km <= HAVERSINE_THRESHOLD_KM) & (np.arange(n) != i)
        nbrs = np.where(mask)[0].tolist()
        neighbors[i] = nbrs
        total_pairs += len(nbrs)

        if (i + 1) % 2000 == 0:
            print(f"  {i + 1}/{n} block groups indexed...")

    print(f"  {total_pairs:,} directional pairs ({total_pairs // 2:,} unique)")
    return neighbors


def query_osrm_table(
    client: httpx.Client,
    osrm_url: str,
    coords: list[tuple[float, float]],
    src_indices: list[int],
    dst_indices: list[int],
) -> tuple[list[list[float | None]], list[list[float | None]]]:
    """Query OSRM table API. Returns (durations, distances)."""
    coord_str = ";".join(f"{lon},{lat}" for lon, lat in coords)
    src_str = ";".join(str(i) for i in src_indices)
    dst_str = ";".join(str(i) for i in dst_indices)

    url = f"{osrm_url}/table/v1/driving/{coord_str}"
    params = {
        "sources": src_str,
        "destinations": dst_str,
        "annotations": "duration,distance",
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(url, params=params)

            if resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                print(f"  Rate limited, waiting {wait}s")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != "Ok":
                msg = data.get("message", "")
                print(f"  OSRM error: {data.get('code')} — {msg}")
                time.sleep(1)
                continue

            return data["durations"], data["distances"]

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            wait = 2 ** attempt
            print(f"  Request error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            time.sleep(wait)

    return [], []


def load_completed_sources() -> set[str]:
    """Load source geoids that have been fully processed from progress file."""
    completed_file = SCRIPT_DIR / "_bg_completed_sources.txt"
    if not completed_file.exists():
        return set()
    with open(completed_file) as f:
        sources = {line.strip() for line in f if line.strip()}
    print(f"Resuming: {len(sources)} source BGs already completed")
    return sources


def mark_sources_completed(geoid_list: list[str]) -> None:
    """Append completed source geoids to the tracking file."""
    completed_file = SCRIPT_DIR / "_bg_completed_sources.txt"
    with open(completed_file, "a") as f:
        for geoid in geoid_list:
            f.write(geoid + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build BG-to-BG travel time matrix")
    parser.add_argument(
        "--osrm-url",
        default="http://localhost:5555",
        help="OSRM server URL (default: http://localhost:5555)",
    )
    args = parser.parse_args()
    osrm_url = args.osrm_url.rstrip("/")

    # Verify OSRM is running
    print(f"Checking OSRM server at {osrm_url}...")
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{osrm_url}/table/v1/driving/-77.0,38.9;-77.1,38.9")
            if resp.json().get("code") != "Ok":
                print(f"OSRM server error: {resp.text[:200]}")
                return
        print("  OSRM server is ready")
    except Exception as e:
        print(f"Cannot reach OSRM server: {e}")
        print("See docstring for Docker setup instructions.")
        return

    centroids = download_bg_centroids()
    geoids = centroids["geoid"].values
    lats = centroids["lat"].values
    lons = centroids["lon"].values

    neighbors = build_neighbor_index(centroids)

    # Collect unique pairs (src < dst) to avoid computing both directions
    unique_pairs: set[tuple[int, int]] = set()
    for src_idx, dst_indices in neighbors.items():
        for dst_idx in dst_indices:
            pair = (min(src_idx, dst_idx), max(src_idx, dst_idx))
            unique_pairs.add(pair)

    print(f"\n{len(unique_pairs):,} unique pairs to query via OSRM")

    # Resume support: skip already-completed source BGs
    done_sources = load_completed_sources()

    # Group by source for batching
    src_to_dsts: dict[int, list[int]] = defaultdict(list)
    for src_idx, dst_idx in unique_pairs:
        src_geoid = geoids[src_idx]
        if src_geoid not in done_sources:
            src_to_dsts[src_idx].append(dst_idx)

    src_indices_sorted = sorted(src_to_dsts.keys())
    remaining_pairs = sum(len(d) for d in src_to_dsts.values())
    print(f"{remaining_pairs:,} pairs remaining after resume filter")
    print(f"{len(src_indices_sorted):,} source BGs to process")

    if not src_indices_sorted:
        print("All pairs already computed. Compressing output...")
        _compress_progress()
        return

    # --- Multi-source batching strategy ---
    # Group consecutive sources into chunks. For each chunk of sources,
    # collect the union of all their destinations. Then split that union
    # into sub-batches that fit within OSRM's coordinate limit.
    # Each OSRM request handles SRC_CHUNK sources x DST_CHUNK destinations
    # = up to 40,000 pairs per request (vs 450 with single-source batching).

    # Build chunks of sources
    src_chunks: list[list[int]] = []
    for i in range(0, len(src_indices_sorted), SRC_CHUNK):
        src_chunks.append(src_indices_sorted[i : i + SRC_CHUNK])

    # Estimate requests
    est_requests = 0
    for chunk in src_chunks:
        all_dsts = set()
        for s in chunk:
            all_dsts.update(src_to_dsts[s])
        est_requests += math.ceil(len(all_dsts) / DST_CHUNK)

    print(f"Estimated {est_requests:,} API requests "
          f"({len(src_chunks)} source chunks x ~{DST_CHUNK} dests)\n")

    # Open progress file for appending
    write_header = not PROGRESS_FILE.exists()
    progress_fp = open(PROGRESS_FILE, "a", newline="")
    writer = csv.writer(progress_fp)
    if write_header:
        writer.writerow(["bg_orig", "bg_dest", "dist_meters", "time_mins"])

    total_requests = 0
    total_found = 0
    t_start = time.time()

    with httpx.Client(timeout=120) as client:
        for ci, src_chunk in enumerate(src_chunks):
            # Collect union of all destinations for this source chunk
            all_dsts_set: set[int] = set()
            for s in src_chunk:
                all_dsts_set.update(src_to_dsts[s])
            all_dsts = sorted(all_dsts_set)

            # Split destinations into sub-batches
            for dst_start in range(0, len(all_dsts), DST_CHUNK):
                dst_batch = all_dsts[dst_start : dst_start + DST_CHUNK]

                # Build coordinate list: sources first, then destinations
                coords: list[tuple[float, float]] = []
                for s in src_chunk:
                    coords.append((lons[s], lats[s]))
                for d in dst_batch:
                    coords.append((lons[d], lats[d]))

                n_src = len(src_chunk)
                src_api_indices = list(range(n_src))
                dst_api_indices = list(range(n_src, n_src + len(dst_batch)))

                durations, distances = query_osrm_table(
                    client, osrm_url, coords, src_api_indices, dst_api_indices
                )

                if not durations:
                    continue

                # Process results: durations[i][j] = time from src_chunk[i] to dst_batch[j]
                for i, src_idx in enumerate(src_chunk):
                    # Only record if this destination is actually in this source's neighbor list
                    src_dst_set = set(src_to_dsts[src_idx])
                    for j, dst_idx in enumerate(dst_batch):
                        if dst_idx not in src_dst_set:
                            continue

                        dur = durations[i][j]
                        dist = distances[i][j] if distances else None

                        if dur is None or dist is None:
                            continue

                        time_mins = round(dur / 60.0, 1)
                        dist_m = round(dist)

                        if time_mins <= MAX_DRIVING_MINUTES:
                            s_geoid = geoids[src_idx]
                            d_geoid = geoids[dst_idx]
                            writer.writerow([s_geoid, d_geoid, dist_m, time_mins])
                            writer.writerow([d_geoid, s_geoid, dist_m, time_mins])
                            total_found += 2

                total_requests += 1

            # Mark all sources in this chunk as completed
            mark_sources_completed([geoids[s] for s in src_chunk])
            progress_fp.flush()

            # Progress report per chunk
            elapsed = time.time() - t_start
            rate = total_requests / elapsed if elapsed > 0 else 0
            remaining = (est_requests - total_requests) / rate if rate > 0 else 0
            pct = (ci + 1) / len(src_chunks) * 100
            print(
                f"  Chunk {ci + 1}/{len(src_chunks)} ({pct:.1f}%) — "
                f"{total_requests:,} requests — "
                f"{total_found:,} pairs — "
                f"{rate:.1f} req/s — "
                f"~{remaining / 60:.0f} min remaining"
            )

    progress_fp.close()
    elapsed = time.time() - t_start
    print(f"\nDone! {total_found:,} pairs in {elapsed / 60:.1f} minutes")

    _compress_progress()


def _compress_progress() -> None:
    """Compress progress CSV to final xz output."""
    print(f"Compressing to {OUTPUT_FILE}...")

    df = pd.read_csv(PROGRESS_FILE, dtype={"bg_orig": str, "bg_dest": str})
    df = df.drop_duplicates(subset=["bg_orig", "bg_dest"])
    df = df.sort_values(["bg_orig", "bg_dest"])

    with lzma.open(OUTPUT_FILE, "wt", preset=6) as f:
        df.to_csv(f, index=False)

    n_origins = df["bg_orig"].nunique()
    n_states = df["bg_orig"].str[:2].nunique()
    print(f"  {len(df):,} rows, {n_origins:,} origin BGs, {n_states} states")
    print(f"  File size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.1f} MB")

    # Cross-state pairs
    cross = df[df["bg_orig"].str[:2] != df["bg_dest"].str[:2]]
    print(f"  Cross-state pairs: {len(cross):,}")

    # Clean up progress files
    print("  Keeping progress files for potential resume.")


if __name__ == "__main__":
    main()
