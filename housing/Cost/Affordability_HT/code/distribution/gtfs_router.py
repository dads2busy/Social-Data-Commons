"""Lightweight GTFS router for computing transit accessibility metrics.

Parses GTFS feeds from cached zip files, resolves service calendars,
builds a transit graph, and runs a Connection Scan Algorithm (CSA) to
compute 30-minute transit access sheds from block group centroids.

This is the novel component for reproducing the CNT H+T Affordability
Index independently — no GTFS schedule parsing existed in the codebase.
"""

from __future__ import annotations

import csv
import datetime
import heapq
import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from sdc_core.log import get_logger

log = get_logger("affordability_ht.gtfs_router")

# --- Constants ---
WALK_SPEED_MPS = 1.2  # meters per second (~4.3 km/h)
TRANSFER_PENALTY_SEC = 120  # 2-minute wait penalty at transfer
MAX_ACCESS_M = 800  # BG centroid → stop (0.5 mi)
MAX_TRANSFER_M = 400  # stop → stop transfer walking
EARTH_RADIUS_M = 6_371_000

# Virginia bounding box (generous) for feed filtering
VA_BBOX = (36.0, 40.0, -84.0, -75.0)  # min_lat, max_lat, min_lon, max_lon

# Feeds that serve VA but may be registered elsewhere (WMATA, etc.)
EXTRA_FEED_IDS = {"mdb-1846", "mdb-1847", "mdb-483", "tld-61", "mdb-481",
                  "mdb-1156", "mdb-478"}

REPO_DIR = Path(__file__).resolve().parents[5]
TRANSIT_DIR = REPO_DIR / "transportation/Walkability/transit_stops"
GTFS_CACHE_DIR = TRANSIT_DIR / "data/gtfs_cache"
FEEDS_CATALOG = TRANSIT_DIR / "data/feeds_catalog.csv"
CENTROIDS_PATH = REPO_DIR / "geographies/osrm/bg_centroids_2020.csv"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Stop:
    stop_id: str
    lat: float
    lon: float
    feed_id: str


@dataclass
class Connection:
    """A single scheduled connection (one stop-to-stop segment of a trip)."""
    dep_stop_idx: int
    arr_stop_idx: int
    dep_time: int  # seconds since midnight
    arr_time: int
    trip_id: str
    route_id: str
    route_type: int
    feed_id: str


@dataclass
class FeedData:
    """Parsed GTFS data from a single feed."""
    feed_id: str
    stops: dict[str, Stop]
    connections: list[Connection]
    route_types: dict[str, int]  # route_id → route_type
    route_trips_per_week: dict[str, float]  # route_id → weekly trip count
    stop_route_map: dict[str, set[str]]  # stop_id → set of route_ids


# ---------------------------------------------------------------------------
# GTFS file reading helpers
# ---------------------------------------------------------------------------


def _open_gtfs_file(zf: zipfile.ZipFile, filename: str) -> IO[str] | None:
    """Open a GTFS text file from a zip, handling subdirectories."""
    for name in zf.namelist():
        if name.endswith(filename) and not name.startswith("__"):
            return io.TextIOWrapper(zf.open(name), encoding="utf-8-sig")
    return None


def _parse_time(t: str) -> int | None:
    """Parse HH:MM:SS to seconds since midnight.  Handles >24h times."""
    try:
        parts = t.strip().split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except (ValueError, IndexError):
        return None


def _parse_date(d: str) -> datetime.date | None:
    """Parse YYYYMMDD date string."""
    try:
        return datetime.date(int(d[:4]), int(d[4:6]), int(d[6:8]))
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# Calendar resolution
# ---------------------------------------------------------------------------


def _first_tuesday_in_october(year: int) -> datetime.date:
    """Return the first Tuesday in October of the given year."""
    d = datetime.date(year, 10, 1)
    while d.weekday() != 1:  # 1 = Tuesday
        d += datetime.timedelta(days=1)
    return d


def resolve_active_services(
    zf: zipfile.ZipFile,
    ref_date: datetime.date,
) -> set[str]:
    """Determine which service_ids are active on ref_date.

    If the ref_date falls outside the feed's service window (common when
    cached feeds are newer than the target year), automatically finds a
    valid Tuesday within the feed's service window.
    """
    active = set()
    cal_rows = []

    # Try calendar.txt first
    cal_file = _open_gtfs_file(zf, "calendar.txt")
    has_calendar = cal_file is not None
    if has_calendar:
        reader = csv.DictReader(cal_file)
        cal_rows = list(reader)
        cal_file.close()

        day_name = ref_date.strftime("%A").lower()
        for row in cal_rows:
            start = _parse_date(row.get("start_date", ""))
            end = _parse_date(row.get("end_date", ""))
            if start and end and start <= ref_date <= end:
                if row.get(day_name, "0") == "1":
                    active.add(row["service_id"])

    # Apply calendar_dates.txt exceptions
    cd_file = _open_gtfs_file(zf, "calendar_dates.txt")
    all_exceptions: dict[str, list[tuple[datetime.date, int]]] = {}
    if cd_file is not None:
        reader = csv.DictReader(cd_file)
        for row in reader:
            d = _parse_date(row.get("date", ""))
            if d is None:
                continue
            sid = row["service_id"]
            etype = int(row.get("exception_type", "1"))
            all_exceptions.setdefault(sid, []).append((d, etype))

            if d == ref_date:
                if etype == 1:
                    active.add(sid)
                elif etype == 2:
                    active.discard(sid)
        cd_file.close()

    # If ref_date falls outside the feed's service window, find a valid Tuesday
    if not active and has_calendar and cal_rows:
        # Find the service window
        all_starts = []
        all_ends = []
        for row in cal_rows:
            s = _parse_date(row.get("start_date", ""))
            e = _parse_date(row.get("end_date", ""))
            if s:
                all_starts.append(s)
            if e:
                all_ends.append(e)

        if all_starts and all_ends:
            window_start = min(all_starts)
            window_end = max(all_ends)

            # Find the Tuesday closest to ref_date within the window
            # Start from the middle of the window for best coverage
            mid = window_start + (window_end - window_start) / 2
            candidate = mid
            # Adjust to nearest Tuesday
            days_to_tuesday = (1 - candidate.weekday()) % 7
            if days_to_tuesday == 0 and candidate.weekday() != 1:
                days_to_tuesday = 7
            candidate = candidate + datetime.timedelta(days=days_to_tuesday)
            if candidate.weekday() != 1:
                candidate = candidate - datetime.timedelta(days=candidate.weekday() - 1)

            # Ensure it's within the window
            if candidate < window_start:
                candidate = window_start
                while candidate.weekday() != 1:
                    candidate += datetime.timedelta(days=1)
            elif candidate > window_end:
                candidate = window_end
                while candidate.weekday() != 1:
                    candidate -= datetime.timedelta(days=1)

            if window_start <= candidate <= window_end:
                day_name = "tuesday"
                for row in cal_rows:
                    s = _parse_date(row.get("start_date", ""))
                    e = _parse_date(row.get("end_date", ""))
                    if s and e and s <= candidate <= e:
                        if row.get(day_name, "0") == "1":
                            active.add(row["service_id"])

                # Apply exceptions for this date
                for sid, exceptions in all_exceptions.items():
                    for d, etype in exceptions:
                        if d == candidate:
                            if etype == 1:
                                active.add(sid)
                            elif etype == 2:
                                active.discard(sid)

    # If still nothing and we only have calendar_dates.txt
    if not active and not has_calendar and all_exceptions:
        tuesday_services: dict[datetime.date, set[str]] = {}
        for sid, exceptions in all_exceptions.items():
            for d, etype in exceptions:
                if d.weekday() == 1 and etype == 1:
                    tuesday_services.setdefault(d, set()).add(sid)
        if tuesday_services:
            best_date = min(
                tuesday_services,
                key=lambda d: abs((d - ref_date).days),
            )
            active = tuesday_services[best_date]

    return active


# ---------------------------------------------------------------------------
# Feed parsing
# ---------------------------------------------------------------------------


def parse_feed(
    zip_path: Path,
    ref_date: datetime.date,
    global_stop_idx: dict[tuple[float, float], int],
    global_stops: list[Stop],
) -> FeedData | None:
    """Parse a single GTFS feed zip, returning connections and stop data.

    Stops are deduplicated globally by rounding coordinates to ~10m grid
    and reusing indices from global_stop_idx / global_stops.
    """
    feed_id = zip_path.stem
    try:
        zf = zipfile.ZipFile(zip_path, "r")
    except (zipfile.BadZipFile, FileNotFoundError):
        log.warning("Skipping bad/missing zip: %s", zip_path)
        return None

    with zf:
        # --- Active services ---
        active_services = resolve_active_services(zf, ref_date)
        if not active_services:
            log.debug("No active services on %s for %s", ref_date, feed_id)
            return None

        # --- Routes ---
        route_types: dict[str, int] = {}
        routes_file = _open_gtfs_file(zf, "routes.txt")
        if routes_file:
            for row in csv.DictReader(routes_file):
                rt = int(row.get("route_type", "3"))
                route_types[row["route_id"]] = rt
            routes_file.close()

        # --- Stops ---
        local_stops: dict[str, int] = {}  # local stop_id → global index
        stops_file = _open_gtfs_file(zf, "stops.txt")
        if stops_file is None:
            return None
        for row in csv.DictReader(stops_file):
            loc_type = row.get("location_type", "0") or "0"
            if loc_type not in ("0", ""):
                continue
            try:
                lat = round(float(row["stop_lat"]), 4)
                lon = round(float(row["stop_lon"]), 4)
            except (ValueError, KeyError):
                continue
            if lat == 0 and lon == 0:
                continue
            key = (lat, lon)
            if key not in global_stop_idx:
                idx = len(global_stops)
                global_stop_idx[key] = idx
                global_stops.append(Stop(row["stop_id"], lat, lon, feed_id))
            local_stops[row["stop_id"]] = global_stop_idx[key]
        stops_file.close()

        # --- Trips (filter to active services) ---
        trip_route: dict[str, str] = {}  # trip_id → route_id
        trip_service: dict[str, str] = {}
        trips_file = _open_gtfs_file(zf, "trips.txt")
        if trips_file is None:
            return None
        for row in csv.DictReader(trips_file):
            if row["service_id"] in active_services:
                trip_route[row["trip_id"]] = row["route_id"]
                trip_service[row["trip_id"]] = row["service_id"]
        trips_file.close()

        if not trip_route:
            return None

        # --- Frequencies (expand frequency-based trips) ---
        freq_trips: dict[str, list[tuple[int, int, int]]] = {}
        freq_file = _open_gtfs_file(zf, "frequencies.txt")
        if freq_file:
            for row in csv.DictReader(freq_file):
                tid = row["trip_id"]
                if tid not in trip_route:
                    continue
                start = _parse_time(row.get("start_time", ""))
                end = _parse_time(row.get("end_time", ""))
                headway = int(row.get("headway_secs", "0"))
                if start is not None and end is not None and headway > 0:
                    freq_trips.setdefault(tid, []).append((start, end, headway))
            freq_file.close()

        # --- Stop times ---
        # Group by trip, sort by stop_sequence
        trip_stoptimes: dict[str, list[tuple[int, int, int, str]]] = {}
        st_file = _open_gtfs_file(zf, "stop_times.txt")
        if st_file is None:
            return None
        for row in csv.DictReader(st_file):
            tid = row["trip_id"]
            if tid not in trip_route:
                continue
            sid = row["stop_id"]
            if sid not in local_stops:
                continue
            dep = _parse_time(row.get("departure_time", ""))
            arr = _parse_time(row.get("arrival_time", ""))
            seq = int(row.get("stop_sequence", "0"))
            if dep is not None and arr is not None:
                trip_stoptimes.setdefault(tid, []).append(
                    (seq, arr, dep, sid)
                )
        st_file.close()

        # --- Build connections ---
        connections: list[Connection] = []
        stop_route_map: dict[str, set[str]] = {}
        route_trip_counts: dict[str, int] = {}

        for tid, stoptimes in trip_stoptimes.items():
            stoptimes.sort(key=lambda x: x[0])  # sort by stop_sequence
            route_id = trip_route[tid]
            rt = route_types.get(route_id, 3)

            # Track stops served by each route
            for _, _, _, sid in stoptimes:
                stop_route_map.setdefault(sid, set()).add(route_id)

            if tid in freq_trips:
                # Frequency-based: expand into concrete departures
                for start, end, headway in freq_trips[tid]:
                    base_dep = stoptimes[0][2]  # first stop departure
                    offset = start
                    while offset < end:
                        time_shift = offset - base_dep
                        route_trip_counts[route_id] = (
                            route_trip_counts.get(route_id, 0) + 1
                        )
                        for i in range(len(stoptimes) - 1):
                            dep_t = stoptimes[i][2] + time_shift
                            arr_t = stoptimes[i + 1][1] + time_shift
                            if arr_t > dep_t:
                                connections.append(Connection(
                                    dep_stop_idx=local_stops[stoptimes[i][3]],
                                    arr_stop_idx=local_stops[stoptimes[i + 1][3]],
                                    dep_time=dep_t,
                                    arr_time=arr_t,
                                    trip_id=tid,
                                    route_id=route_id,
                                    route_type=rt,
                                    feed_id=feed_id,
                                ))
                        offset += headway
            else:
                # Regular scheduled trip
                route_trip_counts[route_id] = (
                    route_trip_counts.get(route_id, 0) + 1
                )
                for i in range(len(stoptimes) - 1):
                    dep_t = stoptimes[i][2]
                    arr_t = stoptimes[i + 1][1]
                    if arr_t > dep_t:
                        connections.append(Connection(
                            dep_stop_idx=local_stops[stoptimes[i][3]],
                            arr_stop_idx=local_stops[stoptimes[i + 1][3]],
                            dep_time=dep_t,
                            arr_time=arr_t,
                            trip_id=tid,
                            route_id=route_id,
                            route_type=rt,
                            feed_id=feed_id,
                        ))

        # Estimate weekly trips per route (Tuesday count × 5 weekdays)
        # Conservative: weekday-only since we resolved a Tuesday
        route_trips_per_week = {
            rid: count * 5 for rid, count in route_trip_counts.items()
        }

    feed_data = FeedData(
        feed_id=feed_id,
        stops={sid: global_stops[idx] for sid, idx in local_stops.items()},
        connections=connections,
        route_types=route_types,
        route_trips_per_week=route_trips_per_week,
        stop_route_map=stop_route_map,
    )
    log.info(
        "Parsed %s: %d stops, %d connections, %d routes",
        feed_id, len(local_stops), len(connections), len(route_types),
    )
    return feed_data


# ---------------------------------------------------------------------------
# Feed selection
# ---------------------------------------------------------------------------


def get_va_feed_ids(catalog_path: Path = FEEDS_CATALOG) -> set[str]:
    """Return feed IDs that serve Virginia or the DC/MD border region."""
    feed_ids = set(EXTRA_FEED_IDS)
    df = pd.read_csv(catalog_path, dtype=str)

    min_lat, max_lat, min_lon, max_lon = VA_BBOX
    for _, row in df.iterrows():
        try:
            rlat_min = float(row.get("min_lat", 0))
            rlat_max = float(row.get("max_lat", 0))
            rlon_min = float(row.get("min_lon", 0))
            rlon_max = float(row.get("max_lon", 0))
        except (ValueError, TypeError):
            continue
        # Bounding box overlap test
        if (rlat_max >= min_lat and rlat_min <= max_lat and
                rlon_max >= min_lon and rlon_min <= max_lon):
            feed_ids.add(row["id"])

    # Also include feeds with Virginia in subdivision_name
    for _, row in df.iterrows():
        sub = str(row.get("subdivision_name", "")).lower()
        muni = str(row.get("municipality", "")).lower()
        prov = str(row.get("provider", "")).lower()
        if any("virginia" in s or ", va" in s for s in [sub, muni, prov]):
            feed_ids.add(row["id"])

    return feed_ids


# ---------------------------------------------------------------------------
# Spatial utilities
# ---------------------------------------------------------------------------


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters between two points."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return EARTH_RADIUS_M * 2 * np.arcsin(np.sqrt(a))


def build_stop_kdtree(
    stops: list[Stop],
) -> cKDTree:
    """Build a KD-tree from stop coordinates (in radians for haversine)."""
    coords = np.array([(s.lat, s.lon) for s in stops])
    # Convert to radians for angular distance queries
    coords_rad = np.radians(coords)
    # Convert to 3D Cartesian for accurate KD-tree queries
    x = np.cos(coords_rad[:, 0]) * np.cos(coords_rad[:, 1])
    y = np.cos(coords_rad[:, 0]) * np.sin(coords_rad[:, 1])
    z = np.sin(coords_rad[:, 0])
    return cKDTree(np.column_stack([x, y, z]))


def _latlon_to_xyz(lat: float, lon: float) -> tuple[float, float, float]:
    """Convert lat/lon (degrees) to unit sphere Cartesian."""
    lat_r, lon_r = np.radians(lat), np.radians(lon)
    return (
        np.cos(lat_r) * np.cos(lon_r),
        np.cos(lat_r) * np.sin(lon_r),
        np.sin(lat_r),
    )


def _meters_to_chord(meters: float) -> float:
    """Convert surface distance in meters to chord distance on unit sphere."""
    angle = meters / EARTH_RADIUS_M
    return 2 * np.sin(angle / 2)


# ---------------------------------------------------------------------------
# Connection Scan Algorithm (CSA)
# ---------------------------------------------------------------------------


def compute_access_shed(
    connections: list[Connection],
    stops: list[Stop],
    stop_tree: cKDTree,
    bg_centroids: pd.DataFrame,
    *,
    max_time_sec: int = 1800,
    departure_times: list[int] | None = None,
    max_transfers: int = 1,
) -> dict[str, set[int]]:
    """Compute transit access sheds: for each BG, find reachable stop indices.

    Uses Connection Scan Algorithm (CSA) — a simpler, faster alternative to
    time-expanded Dijkstra. Processes connections sorted by departure time.

    Parameters
    ----------
    connections : sorted by dep_time
    stops : global stop list
    stop_tree : KD-tree of stops (3D Cartesian on unit sphere)
    bg_centroids : DataFrame with columns geoid, lat, lon
    max_time_sec : maximum travel time in seconds (default 1800 = 30 min)
    departure_times : list of departure times (seconds since midnight)
    max_transfers : maximum number of transfers allowed

    Returns
    -------
    dict mapping geoid → set of reachable stop indices
    """
    if departure_times is None:
        departure_times = [
            7 * 3600,       # 7:00 AM
            7 * 3600 + 1800,  # 7:30 AM
            8 * 3600,       # 8:00 AM
            8 * 3600 + 1800,  # 8:30 AM
        ]

    n_stops = len(stops)
    access_chord = _meters_to_chord(MAX_ACCESS_M)

    # Pre-compute transfer edges once
    transfer_chord = _meters_to_chord(MAX_TRANSFER_M)
    transfer_targets: dict[int, list[tuple[int, int]]] = {}
    # For each stop, find nearby stops for transfers
    for i, stop in enumerate(stops):
        xyz = _latlon_to_xyz(stop.lat, stop.lon)
        nearby = stop_tree.query_ball_point(xyz, transfer_chord)
        targets = []
        for j in nearby:
            if j != i:
                dist_m = haversine_m(stop.lat, stop.lon,
                                     stops[j].lat, stops[j].lon)
                walk_time = int(dist_m / WALK_SPEED_MPS) + TRANSFER_PENALTY_SEC
                targets.append((j, walk_time))
        if targets:
            transfer_targets[i] = targets

    # Sort connections by departure time
    sorted_conns = sorted(connections, key=lambda c: c.dep_time)

    # For each BG centroid, find nearby stops (access edges)
    bg_access: dict[str, list[tuple[int, int]]] = {}  # geoid → [(stop_idx, walk_sec)]
    for _, row in bg_centroids.iterrows():
        geoid = row["geoid"]
        xyz = _latlon_to_xyz(row["lat"], row["lon"])
        nearby = stop_tree.query_ball_point(xyz, access_chord)
        access = []
        for j in nearby:
            dist_m = haversine_m(row["lat"], row["lon"],
                                 stops[j].lat, stops[j].lon)
            walk_sec = int(dist_m / WALK_SPEED_MPS)
            access.append((j, walk_sec))
        if access:
            bg_access[geoid] = access

    log.info(
        "CSA: %d BGs with transit access, %d connections, %d departure times",
        len(bg_access), len(sorted_conns), len(departure_times),
    )

    # Run CSA for each BG × departure_time, keep union of reached stops
    result: dict[str, set[int]] = {}

    # Process in batches of BGs for memory efficiency
    bg_list = list(bg_access.items())
    batch_size = 500

    for batch_start in range(0, len(bg_list), batch_size):
        batch = bg_list[batch_start:batch_start + batch_size]
        log.info("CSA batch %d/%d", batch_start // batch_size + 1,
                 (len(bg_list) + batch_size - 1) // batch_size)

        for geoid, access_edges in batch:
            reached = set()

            for dep_time_base in departure_times:
                # Initialize earliest arrival times
                # (stop_idx, transfers_used) → earliest arrival time
                earliest: dict[int, list[int]] = {}
                # earliest[stop_idx] = [arrival_with_0_transfers, arrival_with_1_transfer]

                for stop_idx, walk_sec in access_edges:
                    arrival = dep_time_base + walk_sec
                    if arrival <= dep_time_base + max_time_sec:
                        if stop_idx not in earliest:
                            earliest[stop_idx] = [float("inf")] * (max_transfers + 1)
                        earliest[stop_idx][0] = min(earliest[stop_idx][0], arrival)
                        reached.add(stop_idx)

                # Propagate through transfers from initial stops
                for stop_idx in list(earliest.keys()):
                    arr_time = earliest[stop_idx][0]
                    if stop_idx in transfer_targets and arr_time < float("inf"):
                        for t_stop, t_time in transfer_targets[stop_idx]:
                            new_arr = arr_time + t_time
                            if new_arr <= dep_time_base + max_time_sec:
                                if t_stop not in earliest:
                                    earliest[t_stop] = [float("inf")] * (max_transfers + 1)
                                if new_arr < earliest[t_stop][1]:
                                    earliest[t_stop][1] = new_arr
                                    reached.add(t_stop)

                # Scan connections in departure order
                # Track which trips we're "on" (trip_id → arrival_time at last boarded stop)
                trip_boarded: dict[str, int] = {}  # trip_id → transfers_used when boarded

                for conn in sorted_conns:
                    if conn.dep_time < dep_time_base:
                        continue
                    if conn.dep_time > dep_time_base + max_time_sec:
                        break

                    # Can we board this connection?
                    can_board = False
                    board_transfers = -1

                    # Check if we're already on this trip
                    if conn.trip_id in trip_boarded:
                        can_board = True
                        board_transfers = trip_boarded[conn.trip_id]
                    else:
                        # Check if we can board from the departure stop
                        if conn.dep_stop_idx in earliest:
                            for t in range(max_transfers + 1):
                                if earliest[conn.dep_stop_idx][t] <= conn.dep_time:
                                    can_board = True
                                    board_transfers = t
                                    break

                    if not can_board:
                        continue

                    # Ride the connection
                    if conn.arr_time <= dep_time_base + max_time_sec:
                        trip_boarded[conn.trip_id] = board_transfers
                        arr_idx = conn.arr_stop_idx
                        if arr_idx not in earliest:
                            earliest[arr_idx] = [float("inf")] * (max_transfers + 1)
                        if conn.arr_time < earliest[arr_idx][board_transfers]:
                            earliest[arr_idx][board_transfers] = conn.arr_time
                            reached.add(arr_idx)

                            # Propagate transfers from this newly reached stop
                            if (board_transfers < max_transfers and
                                    arr_idx in transfer_targets):
                                for t_stop, t_time in transfer_targets[arr_idx]:
                                    new_arr = conn.arr_time + t_time
                                    if new_arr <= dep_time_base + max_time_sec:
                                        if t_stop not in earliest:
                                            earliest[t_stop] = [float("inf")] * (max_transfers + 1)
                                        next_t = board_transfers + 1
                                        if new_arr < earliest[t_stop][next_t]:
                                            earliest[t_stop][next_t] = new_arr
                                            reached.add(t_stop)

            if reached:
                result[geoid] = reached

    log.info("CSA complete: %d / %d BGs have transit access sheds",
             len(result), len(bg_centroids))
    return result


# ---------------------------------------------------------------------------
# High-level API
# ---------------------------------------------------------------------------


def load_centroids(
    states: list[str] | None = None,
) -> pd.DataFrame:
    """Load BG centroids, optionally filtered by state FIPS."""
    df = pd.read_csv(CENTROIDS_PATH, dtype={"geoid": str})
    # Pad GEOIDs to 12 characters
    df["geoid"] = df["geoid"].str.zfill(12)
    if states:
        from sdc_core.profiles import resolve_profile
        # Convert state abbreviations to FIPS
        state_fips_map = {
            "VA": "51", "MD": "24", "DC": "11", "WV": "54",
            "NC": "37", "TN": "47", "KY": "21", "DE": "10",
            "PA": "42",
        }
        fips_prefixes = [state_fips_map.get(s, s) for s in states]
        df = df[df["geoid"].str[:2].isin(fips_prefixes)]
    return df.reset_index(drop=True)


def parse_all_feeds(
    year: int,
    feed_ids: set[str] | None = None,
) -> tuple[list[Stop], list[Connection], list[FeedData]]:
    """Parse all VA-region GTFS feeds for a given year.

    Returns
    -------
    global_stops : deduplicated stop list
    all_connections : merged connection list (sorted by dep_time)
    feed_data_list : per-feed parsed data (for TCI/peak trips)
    """
    if feed_ids is None:
        feed_ids = get_va_feed_ids()

    cache_dir = GTFS_CACHE_DIR / str(year)
    if not cache_dir.exists():
        raise FileNotFoundError(f"No GTFS cache for year {year}: {cache_dir}")

    ref_date = _first_tuesday_in_october(year)
    log.info("Parsing GTFS feeds for %d (ref date: %s), %d feed IDs",
             year, ref_date, len(feed_ids))

    global_stop_idx: dict[tuple[float, float], int] = {}
    global_stops: list[Stop] = []
    feed_data_list: list[FeedData] = []

    for fid in sorted(feed_ids):
        zip_path = cache_dir / f"{fid}.zip"
        if not zip_path.exists():
            continue
        fd = parse_feed(zip_path, ref_date, global_stop_idx, global_stops)
        if fd is not None:
            feed_data_list.append(fd)

    # Merge all connections
    all_connections = []
    for fd in feed_data_list:
        all_connections.extend(fd.connections)
    all_connections.sort(key=lambda c: c.dep_time)

    log.info(
        "Total: %d stops, %d connections from %d feeds",
        len(global_stops), len(all_connections), len(feed_data_list),
    )
    return global_stops, all_connections, feed_data_list
