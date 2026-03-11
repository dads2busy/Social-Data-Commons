"""Compute transit accessibility metrics per block group.

Produces the 5 transit-derived independent variables for the CNT H+T model:
  1. Bus Transit Connectivity Index (Bus TCI)
  2. Other Transit Connectivity Index (Other TCI)
  3. Transit Access Shed Area (TAS Area, in acres)
  4. Transit Access Shed Jobs (TAS Jobs)
  5. Average Available Transit Trips per Week at Peak Times
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from sdc_core.log import get_logger

from .gtfs_router import (
    Connection,
    FeedData,
    Stop,
    build_stop_kdtree,
    compute_access_shed,
    haversine_m,
    load_centroids,
    parse_all_feeds,
    _latlon_to_xyz,
    _meters_to_chord,
    WALK_SPEED_MPS,
)

log = get_logger("affordability_ht.transit_metrics")

REPO_DIR = Path(__file__).resolve().parents[5]
LODES_CACHE = REPO_DIR / "transportation/Walkability/transit_stops/data/lodes_cache"

# Cache GTFS-only transit results keyed by (gtfs_year, target_geoids_key)
# Values: (tci_df, access_sheds, peak_df, stops, centroids, bg_areas)
_gtfs_cache: dict[tuple, tuple] = {}

# Buffer distances for TCI (in meters)
BUS_BUFFER_M = 603  # 3/8 mile
OTHER_BUFFER_M = 1609  # 1 mile

# Peak hours for transit trip counting (seconds since midnight)
PEAK_START = 7 * 3600   # 7:00 AM
PEAK_END = 9 * 3600     # 9:00 AM

# BG boundary proximity for peak trips (1/2 mile ≈ 805m from centroid)
PEAK_BUFFER_M = 805

# M² to acres conversion
M2_TO_ACRES = 0.000247105


def compute_tci(
    feed_data_list: list[FeedData],
    stops: list[Stop],
    stop_tree: cKDTree,
    bg_centroids: pd.DataFrame,
    bg_areas_m2: pd.Series,
) -> pd.DataFrame:
    """Compute Bus TCI and Other TCI per block group.

    TCI = Σ (area_fraction × route_trips_per_week) for each route type.

    Uses centroid-distance approximation: if a route has stops within the
    buffer distance of a BG centroid, the area fraction is approximated as
    min(π × r² / BG_area, 1.0) where r is the buffer radius.

    Parameters
    ----------
    feed_data_list : parsed feed data with route info
    stops : global stop list
    stop_tree : KD-tree of stop locations
    bg_centroids : DataFrame with geoid, lat, lon
    bg_areas_m2 : Series indexed by geoid, land area in m²

    Returns
    -------
    DataFrame with columns: geoid, bus_tci, other_tci
    """
    bus_buffer_area = np.pi * BUS_BUFFER_M ** 2
    other_buffer_area = np.pi * OTHER_BUFFER_M ** 2
    bus_chord = _meters_to_chord(BUS_BUFFER_M)
    other_chord = _meters_to_chord(OTHER_BUFFER_M)

    # Build fast (lat, lon) → global stop index lookup
    global_stop_lookup: dict[tuple[float, float], int] = {}
    for gi, gs in enumerate(stops):
        key = (round(gs.lat, 4), round(gs.lon, 4))
        global_stop_lookup[key] = gi

    # Build route → (route_type, trips_per_week, stop_indices) mapping
    route_info: dict[str, tuple[int, float, set[int]]] = {}
    for fd in feed_data_list:
        for route_id, rt in fd.route_types.items():
            trips = fd.route_trips_per_week.get(route_id, 0)
            if trips == 0:
                continue
            # Find global stop indices for this route's stops
            stop_indices = set()
            for local_sid, route_ids in fd.stop_route_map.items():
                if route_id in route_ids and local_sid in fd.stops:
                    s = fd.stops[local_sid]
                    key = (round(s.lat, 4), round(s.lon, 4))
                    gi = global_stop_lookup.get(key)
                    if gi is not None:
                        stop_indices.add(gi)
            rkey = f"{fd.feed_id}:{route_id}"
            if rkey in route_info:
                route_info[rkey][2].update(stop_indices)
            else:
                route_info[rkey] = (rt, trips, stop_indices)

    log.info("Computing TCI for %d routes across %d BGs",
             len(route_info), len(bg_centroids))

    bus_tci = {}
    other_tci = {}

    for _, row in bg_centroids.iterrows():
        geoid = row["geoid"]
        xyz = _latlon_to_xyz(row["lat"], row["lon"])
        bg_area = bg_areas_m2.get(geoid, 1e6)  # default ~1 km²

        bt = 0.0
        ot = 0.0

        # Find all stops within the larger buffer (1 mile)
        nearby_other = set(stop_tree.query_ball_point(xyz, other_chord))
        nearby_bus = set(stop_tree.query_ball_point(xyz, bus_chord))

        for rkey, (rt, trips, r_stops) in route_info.items():
            if rt == 3:  # Bus
                overlap = r_stops & nearby_bus
                if overlap:
                    frac = min(bus_buffer_area / bg_area, 1.0)
                    bt += frac * trips
            else:  # Non-bus (rail, ferry, tram, etc.)
                overlap = r_stops & nearby_other
                if overlap:
                    frac = min(other_buffer_area / bg_area, 1.0)
                    ot += frac * trips

        bus_tci[geoid] = bt
        other_tci[geoid] = ot

    return pd.DataFrame({
        "geoid": list(bus_tci.keys()),
        "bus_tci": list(bus_tci.values()),
        "other_tci": list(other_tci.values()),
    })


def compute_tas(
    access_sheds: dict[str, set[int]],
    stops: list[Stop],
    bg_centroids: pd.DataFrame,
    bg_areas_m2: pd.Series,
    bg_jobs: pd.Series,
) -> pd.DataFrame:
    """Compute Transit Access Shed Area and Jobs per block group.

    For each BG, the TAS is the set of BGs reachable within 30 minutes by
    transit. TAS Area = sum of land areas of reachable BGs. TAS Jobs = sum
    of LODES employment in reachable BGs.

    The access shed maps reached *stops* to BGs by finding the BG whose
    centroid is closest to each reached stop (within 1/4 mile).

    Parameters
    ----------
    access_sheds : geoid → set of reachable stop indices (from CSA)
    stops : global stop list
    bg_centroids : DataFrame with geoid, lat, lon
    bg_areas_m2 : Series indexed by geoid, land area in m²
    bg_jobs : Series indexed by geoid, total LODES jobs (C000)

    Returns
    -------
    DataFrame with columns: geoid, tas_area_acres, tas_jobs
    """
    # Map each stop to nearest BG (within 1/4 mile = 402m)
    quarter_mile_chord = _meters_to_chord(402)
    bg_coords = np.array([
        _latlon_to_xyz(row["lat"], row["lon"])
        for _, row in bg_centroids.iterrows()
    ])
    bg_tree = cKDTree(bg_coords)
    bg_geoids = bg_centroids["geoid"].values

    stop_to_bg: dict[int, str] = {}
    for i, s in enumerate(stops):
        xyz = _latlon_to_xyz(s.lat, s.lon)
        dists, idxs = bg_tree.query(xyz, k=1)
        if dists <= quarter_mile_chord:
            stop_to_bg[i] = bg_geoids[idxs]

    log.info("Mapped %d / %d stops to BGs", len(stop_to_bg), len(stops))

    rows = []
    for geoid, reached_stops in access_sheds.items():
        # Map reached stops to BGs
        reached_bgs = set()
        for si in reached_stops:
            if si in stop_to_bg:
                reached_bgs.add(stop_to_bg[si])

        # Include the origin BG itself
        reached_bgs.add(geoid)

        tas_area = sum(
            bg_areas_m2.get(bg, 0) * M2_TO_ACRES
            for bg in reached_bgs
        )
        tas_jobs = sum(bg_jobs.get(bg, 0) for bg in reached_bgs)

        rows.append({
            "geoid": geoid,
            "tas_area_acres": tas_area,
            "tas_jobs": int(tas_jobs),
        })

    # BGs with no transit access get 0
    all_geoids = set(bg_centroids["geoid"])
    for geoid in all_geoids - set(r["geoid"] for r in rows):
        rows.append({
            "geoid": geoid,
            "tas_area_acres": 0.0,
            "tas_jobs": 0,
        })

    return pd.DataFrame(rows)


def compute_peak_trips(
    feed_data_list: list[FeedData],
    stops: list[Stop],
    stop_tree: cKDTree,
    bg_centroids: pd.DataFrame,
) -> pd.DataFrame:
    """Compute average available transit trips per week at peak times per BG.

    Counts distinct trip departures at stops within 1/2 mile of BG centroid
    during peak hours (7-9 AM), then multiplies by 5 for weekly estimate.

    Returns
    -------
    DataFrame with columns: geoid, peak_trips_week
    """
    peak_chord = _meters_to_chord(PEAK_BUFFER_M)

    # Collect all (stop_idx, dep_time) pairs during peak hours
    peak_departures: dict[int, int] = {}  # stop_idx → count of departures
    for fd in feed_data_list:
        for conn in fd.connections:
            if PEAK_START <= conn.dep_time < PEAK_END:
                peak_departures[conn.dep_stop_idx] = (
                    peak_departures.get(conn.dep_stop_idx, 0) + 1
                )

    rows = []
    for _, row in bg_centroids.iterrows():
        geoid = row["geoid"]
        xyz = _latlon_to_xyz(row["lat"], row["lon"])
        nearby = stop_tree.query_ball_point(xyz, peak_chord)

        n_nearby = len(nearby)
        total = sum(peak_departures.get(si, 0) for si in nearby)
        # Average trips per stop during peak, not total across all stops.
        # CNT: "Average Available Transit Trips per Week at Peak Times"
        avg_per_stop = total / n_nearby if n_nearby > 0 else 0
        # This count is for one typical Tuesday peak period
        # Multiply by 5 for weekly (weekdays only)
        rows.append({"geoid": geoid, "peak_trips_week": avg_per_stop * 5})

    return pd.DataFrame(rows)


def load_lodes_jobs(states: list[str], year: int) -> pd.Series:
    """Load LODES total jobs (C000) aggregated to block group level.

    Returns Series indexed by 12-digit BG GEOID.
    """
    state_abbr_map = {
        "51": "va", "24": "md", "11": "dc", "54": "wv",
        "37": "nc", "47": "tn", "21": "ky", "10": "de",
    }

    frames = []
    for fips in states:
        abbr = state_abbr_map.get(fips, fips.lower())
        # Try nearby years: exact, then ±1, ±2, ±3
        search_years = [year]
        for delta in range(1, 4):
            search_years.extend([year - delta, year + delta])
        for yr in search_years:
            path = LODES_CACHE / f"{abbr}_wac_{yr}.parquet"
            if path.exists():
                df = pd.read_parquet(path, columns=["w_geocode", "C000"])
                df["geoid"] = df["w_geocode"].astype(str).str.zfill(15).str[:12]
                bg_jobs = df.groupby("geoid")["C000"].sum()
                frames.append(bg_jobs)
                log.info("LODES %s %d (requested %d): %d BGs", abbr, yr, year, len(bg_jobs))
                break
        else:
            log.warning("No LODES data found for %s near year %d", abbr, year)

    if not frames:
        return pd.Series(dtype=float, name="C000")
    return pd.concat(frames).groupby(level=0).sum()


def load_lodes_by_sector(states: list[str], year: int) -> pd.DataFrame:
    """Load LODES employment by NAICS sector aggregated to block group.

    Returns DataFrame indexed by 12-digit BG GEOID with columns CNS01-CNS20 + C000.
    """
    state_abbr_map = {
        "51": "va", "24": "md", "11": "dc", "54": "wv",
        "37": "nc", "47": "tn", "21": "ky", "10": "de",
    }
    cns_cols = [f"CNS{i:02d}" for i in range(1, 21)] + ["C000"]

    frames = []
    for fips in states:
        abbr = state_abbr_map.get(fips, fips.lower())
        search_years = [year]
        for delta in range(1, 4):
            search_years.extend([year - delta, year + delta])
        for yr in search_years:
            path = LODES_CACHE / f"{abbr}_wac_{yr}.parquet"
            if path.exists():
                cols = ["w_geocode"] + [c for c in cns_cols if c != "w_geocode"]
                df = pd.read_parquet(path, columns=cols)
                df["geoid"] = df["w_geocode"].astype(str).str.zfill(15).str[:12]
                df = df.drop(columns=["w_geocode"])
                bg = df.groupby("geoid").sum()
                frames.append(bg)
                log.info("LODES sectors %s %d (requested %d)", abbr, yr, year)
                break

    if not frames:
        return pd.DataFrame(columns=cns_cols)
    return pd.concat(frames).groupby(level=0).sum()


def compute_all_transit_metrics(
    year: int,
    target_states: list[str] = ("51",),
    buffer_states: list[str] = ("51", "24", "11", "54"),
    target_counties: set[str] | None = None,
    gtfs_year: int | None = None,
) -> pd.DataFrame:
    """Compute all 5 transit variables for target state block groups.

    Parameters
    ----------
    year : data year (used for LODES)
    target_states : FIPS codes for states we want output for (default VA)
    buffer_states : FIPS codes for states to include in routing (neighbors)
    target_counties : if provided, restrict target BGs to these 5-digit
        county FIPS codes instead of entire states
    gtfs_year : override GTFS year (e.g. use 2017 feeds for 2015-2016 data)

    Returns
    -------
    DataFrame with columns: geoid, bus_tci, other_tci, tas_area_acres,
                           tas_jobs, peak_trips_week
    """
    # Load centroids for routing region
    state_map = {
        "51": "VA", "24": "MD", "11": "DC", "54": "WV",
        "37": "NC", "47": "TN", "21": "KY", "10": "DE",
    }
    buffer_abbrs = [state_map[f] for f in buffer_states]
    centroids = load_centroids(states=buffer_abbrs)
    log.info("Loaded %d BG centroids for %s", len(centroids), buffer_abbrs)

    # Filter target centroids (output BGs)
    if target_counties:
        target_centroids = centroids[
            centroids["geoid"].str[:5].isin(target_counties)
        ].copy()
    else:
        target_centroids = centroids[
            centroids["geoid"].str[:2].isin(target_states)
        ].copy()

    effective_gtfs_year = gtfs_year if gtfs_year is not None else year
    # Build cache key from GTFS year + target BG set
    if target_counties:
        target_key = ("counties", tuple(sorted(target_counties)))
    else:
        target_key = ("states", tuple(sorted(target_states)))
    cache_key = (effective_gtfs_year, target_key)

    if cache_key in _gtfs_cache:
        log.info("Using cached GTFS transit results for gtfs_year=%d", effective_gtfs_year)
        tci_df, access_sheds, peak_df, stops, centroids_all, bg_areas = _gtfs_cache[cache_key]
    else:
        if effective_gtfs_year != year:
            log.info("Using GTFS year %d as proxy for data year %d", effective_gtfs_year, year)
        stops, connections, feed_data_list = parse_all_feeds(effective_gtfs_year)

        if not stops:
            log.warning("No transit stops found for year %d", year)
            return _empty_transit_df(target_centroids)

        stop_tree = build_stop_kdtree(stops)
        bg_areas = _load_bg_areas(buffer_states)

        tci_df = compute_tci(
            feed_data_list, stops, stop_tree, target_centroids, bg_areas,
        )
        access_sheds = compute_access_shed(
            connections, stops, stop_tree, target_centroids,
        )
        peak_df = compute_peak_trips(
            feed_data_list, stops, stop_tree, target_centroids,
        )
        centroids_all = centroids
        _gtfs_cache[cache_key] = (tci_df, access_sheds, peak_df, stops, centroids_all, bg_areas)

    # TAS jobs depends on LODES year — always recompute
    bg_jobs = load_lodes_jobs(buffer_states, year)
    tas_df = compute_tas(
        access_sheds, stops, centroids_all, bg_areas, bg_jobs,
    )

    result = tci_df.merge(tas_df, on="geoid", how="outer")
    result = result.merge(peak_df, on="geoid", how="outer")
    result = result.fillna(0)

    log.info("Transit metrics computed for %d BGs (data year %d, gtfs year %d)",
             len(result), year, effective_gtfs_year)
    return result


def _load_bg_areas(state_fips_list: list[str]) -> pd.Series:
    """Load BG land areas in m² from TIGER shapefiles.

    Falls back to TIGERweb API or cached data if available.
    """
    import geopandas as gpd
    import tempfile
    import httpx

    all_areas = {}
    for fips in state_fips_list:
        # Try cached shapefile first
        cache_dir = REPO_DIR / "geographies/tiger_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"bg_areas_{fips}.parquet"

        if cache_file.exists():
            df = pd.read_parquet(cache_file)
            for _, row in df.iterrows():
                all_areas[row["geoid"]] = row["aland"]
            continue

        # Download TIGER BG shapefile
        url = (
            f"https://www2.census.gov/geo/tiger/TIGER2020/BG/"
            f"tl_2020_{fips}_bg.zip"
        )
        log.info("Downloading TIGER BG boundaries for FIPS %s", fips)
        try:
            with httpx.Client(follow_redirects=True, timeout=120) as client:
                resp = client.get(url)
                resp.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
                tmp.write(resp.content)
                tmp.flush()
                gdf = gpd.read_file(tmp.name)
            geoid_col = "GEOID" if "GEOID" in gdf.columns else "GEOID20"
            areas = gdf[[geoid_col, "ALAND"]].rename(
                columns={geoid_col: "geoid", "ALAND": "aland"}
            )
            areas["geoid"] = areas["geoid"].astype(str).str.zfill(12)
            areas.to_parquet(cache_file, index=False)
            for _, row in areas.iterrows():
                all_areas[row["geoid"]] = row["aland"]
            log.info("Cached %d BG areas for FIPS %s", len(areas), fips)
        except Exception as e:
            log.warning("Failed to load TIGER areas for %s: %s", fips, e)

    return pd.Series(all_areas, name="aland_m2", dtype=float)


def _empty_transit_df(centroids: pd.DataFrame) -> pd.DataFrame:
    """Return a zero-filled transit metrics DataFrame."""
    return pd.DataFrame({
        "geoid": centroids["geoid"],
        "bus_tci": 0.0,
        "other_tci": 0.0,
        "tas_area_acres": 0.0,
        "tas_jobs": 0,
        "peak_trips_week": 0,
    })
