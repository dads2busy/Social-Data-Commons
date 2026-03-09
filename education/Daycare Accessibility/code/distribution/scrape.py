"""Scrape Virginia DSS child day care facility data and geocode.

Fetches all licensed child care facilities from the VDSS search portal,
retrieves detail pages for capacity/age info, geocodes addresses via the
Census Bureau geocoder, and writes a locations CSV + GeoJSON.
"""

import hashlib
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from sdc_core.log import get_logger

TOPIC_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = TOPIC_DIR / "data"
CACHE_DIR = DATA_DIR / "original/search_cache"

SEARCH_URL = "https://www.dss.virginia.gov/facility/search/cc.cgi"
DETAIL_URL = "https://www.dss.virginia.gov/facility/search/cc2.cgi"

CENSUS_GEOCODER_URL = (
    "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
)

log = get_logger("daycare.scrape")


# ---------------------------------------------------------------------------
# Step 1: Fetch facility list
# ---------------------------------------------------------------------------

def fetch_facility_list() -> pd.DataFrame:
    """POST to VDSS search and parse facility IDs, names, addresses, phones."""
    log.info("Fetching facility list from VDSS...")
    resp = httpx.post(
        SEARCH_URL,
        data={
            "rm": "Search",
            "search_keywords_name": "",
            "search_exact_fips": "",
            "search_contains_zip": "",
        },
        timeout=60,
        verify=False,
    )
    resp.raise_for_status()
    html = resp.content.decode("latin-1")

    rows = html.split("<tr>")
    facilities = []
    for row in rows:
        if "cc2.cgi" not in row or ";ID=" not in row:
            continue

        id_m = re.search(r";ID=([^;]+);", row)
        name_m = re.search(r">([^<]+)</a>", row)
        quality_m = re.search(r"level_(\d+)\.svg", row)
        addr_m = re.search(r">\n\t+([^<]+<br>[^<]+)</td>", row)
        phone_m = re.search(r"(\(\d+\) [0-9-]+)", row)

        fac_id = id_m.group(1) if id_m else None
        if not fac_id:
            continue

        address = ""
        if addr_m:
            address = re.sub(r"[\n\t]+", " ", addr_m.group(1))
            address = address.replace("<br>", ", ").strip()

        facilities.append({
            "id": int(fac_id),
            "name": name_m.group(1).strip() if name_m else "",
            "quality": int(quality_m.group(1)) if quality_m else None,
            "address": address,
            "phone": phone_m.group(1) if phone_m else "",
        })

    df = pd.DataFrame(facilities)

    # Deduplicate by id + address hash
    df["addr_hash"] = df["address"].apply(
        lambda a: hashlib.md5(a.encode()).hexdigest()[:16]
    )
    df["uid"] = df["id"].astype(str) + "_" + df["addr_hash"]
    df = df.drop_duplicates(subset=["uid"])

    log.info("Found %d unique facilities", len(df))
    return df


# ---------------------------------------------------------------------------
# Step 2: Fetch facility details
# ---------------------------------------------------------------------------

def _fetch_detail(fac_id: int, addr_hash: str, client: httpx.Client) -> str | None:
    """Fetch and cache a single facility detail page."""
    cache_file = CACHE_DIR / f"{fac_id}_{addr_hash}.html"
    if cache_file.exists():
        return cache_file.read_text(encoding="latin-1")

    try:
        resp = client.get(
            DETAIL_URL,
            params={"rm": "Details", "ID": str(fac_id)},
            timeout=30,
        )
        if resp.status_code == 200:
            content = resp.content.decode("latin-1")
            cache_file.write_text(content, encoding="latin-1")
            return content
    except Exception as e:
        log.warning("Failed to fetch detail for ID %s: %s", fac_id, e)
    return None


def _parse_detail(html: str) -> dict:
    """Parse facility detail page HTML into structured fields."""
    tables = html.split("<table")

    info = {
        "type": "",
        "licence": "",
        "expiration": "",
        "administrator": "",
        "capacity": None,
        "ages": "",
        "inspector": "",
        "subsidiary": "",
        "facility_id": "",
    }

    # Find the data table with Facility Type
    for table in tables:
        if "Facility Type" not in table:
            continue

        lines = re.split(r"[\r\n\t]+", table)

        def _field_after(label: str, offset: int = 7) -> str:
            indices = [i for i, l in enumerate(lines) if label in l]
            if indices:
                idx = indices[0] + offset
                if idx < len(lines):
                    return re.sub(r"<[^>]+>", "", lines[idx]).strip()
            return ""

        info["type"] = _field_after("Facility Type", 7)
        licence_raw = _field_after("License Type", 5)
        # Extract text between <u> tags if present
        u_match = re.search(r"<u>(.*?)</u>", lines[
            [i for i, l in enumerate(lines) if "License Type" in l][0] + 5
        ] if [i for i, l in enumerate(lines) if "License Type" in l] else "")
        info["licence"] = u_match.group(1) if u_match else licence_raw

        info["expiration"] = _field_after("Expiration Date", 3)
        info["administrator"] = _field_after("Administrator", 3)

        # Capacity
        cap_indices = [i for i, l in enumerate(lines) if "Capacity" in l and "Subsidy" not in l]
        if cap_indices:
            cap_raw = re.sub(r"<[^>]+>", "", lines[min(cap_indices[0] + 3, len(lines) - 1)]).strip()
            try:
                info["capacity"] = int(cap_raw)
            except (ValueError, TypeError):
                pass

        # Ages
        age_indices = [i for i, l in enumerate(lines) if "Ages:" in l]
        if age_indices:
            age_parts = []
            for offset in range(3, 7):
                idx = age_indices[0] + offset
                if idx < len(lines):
                    cleaned = re.sub(r"<[^>]+>", "", lines[idx]).strip()
                    if cleaned:
                        age_parts.append(cleaned)
            info["ages"] = " ".join(age_parts).strip()

        info["inspector"] = _field_after("Inspector:", 3)
        info["subsidiary"] = _field_after("Current Subsidy Provider", 3)
        info["facility_id"] = _field_after("License/Facility ID#", 3)
        break

    return info


def fetch_details(facilities: pd.DataFrame, max_workers: int = 8) -> pd.DataFrame:
    """Fetch detail pages for all facilities (cached, resumable, parallel)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    details = []
    to_fetch = []

    # Separate cached from uncached
    for _, row in facilities.iterrows():
        cache_file = CACHE_DIR / f"{row['id']}_{row['addr_hash']}.html"
        if cache_file.exists():
            html = cache_file.read_text(encoding="latin-1")
            info = _parse_detail(html)
            info["id"] = row["id"]
            details.append(info)
        else:
            to_fetch.append((row["id"], row["addr_hash"]))

    log.info("Details: %d cached, %d to fetch", len(details), len(to_fetch))

    if to_fetch:
        fetched = 0

        def _fetch_one(args: tuple[int, str]) -> dict:
            fac_id, addr_hash = args
            with httpx.Client(verify=False) as client:
                html = _fetch_detail(fac_id, addr_hash, client)
            if html:
                info = _parse_detail(html)
                info["id"] = fac_id
                return info
            return {"id": fac_id}

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_fetch_one, item): item for item in to_fetch}
            for future in as_completed(futures):
                details.append(future.result())
                fetched += 1
                if fetched % 200 == 0:
                    log.info("Fetched %d/%d detail pages...", fetched, len(to_fetch))

        log.info("Fetched %d new detail pages", fetched)

    return pd.DataFrame(details)


# ---------------------------------------------------------------------------
# Step 3: Geocode addresses
# ---------------------------------------------------------------------------

def _geocode_one(address: str) -> tuple[float | None, float | None]:
    """Geocode a single address via Census Bureau geocoder."""
    try:
        resp = httpx.get(
            CENSUS_GEOCODER_URL,
            params={
                "address": address,
                "benchmark": "Public_AR_Current",
                "format": "json",
            },
            timeout=30,
        )
        data = resp.json()
        matches = data.get("result", {}).get("addressMatches", [])
        if matches:
            coords = matches[0]["coordinates"]
            return coords["y"], coords["x"]
    except Exception:
        pass
    return None, None


def geocode_facilities(facilities: pd.DataFrame) -> pd.DataFrame:
    """Geocode all facility addresses, with caching."""
    cache_path = DATA_DIR / "working/geocode_cache.csv"
    cache = {}
    if cache_path.exists():
        cache_df = pd.read_csv(cache_path, dtype={"id": int})
        cache = {
            row["id"]: (row["lat"], row["lon"])
            for _, row in cache_df.iterrows()
            if pd.notna(row["lat"])
        }
        log.info("Loaded %d cached geocode results", len(cache))

    results = []
    to_geocode = []

    for _, row in facilities.iterrows():
        fac_id = row["id"]
        if fac_id in cache:
            lat, lon = cache[fac_id]
            results.append({"id": fac_id, "lat": lat, "lon": lon})
        else:
            to_geocode.append((fac_id, row["address"]))

    if to_geocode:
        log.info("Geocoding %d new addresses...", len(to_geocode))

        def _geocode_with_retry(args: tuple[int, str]) -> dict:
            fac_id, address = args
            lat, lon = _geocode_one(address)
            # Retry with simplified address if failed
            if lat is None and "," in address:
                parts = [p.strip() for p in address.split(",")]
                if len(parts) >= 3:
                    simplified = f"{parts[0]}, {parts[-2].strip()}, {parts[-1].strip()}"
                    lat, lon = _geocode_one(simplified)
            return {"id": fac_id, "lat": lat, "lon": lon}

        done = 0
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_geocode_with_retry, item): item for item in to_geocode}
            for future in as_completed(futures):
                results.append(future.result())
                done += 1
                if done % 200 == 0:
                    log.info("Geocoded %d/%d addresses", done, len(to_geocode))

    result_df = pd.DataFrame(results)

    # Update cache
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(cache_path, index=False)
    log.info(
        "Geocoding complete: %d matched, %d failed",
        result_df["lat"].notna().sum(),
        result_df["lat"].isna().sum(),
    )
    return result_df


# ---------------------------------------------------------------------------
# Step 4: Parse ages and write output
# ---------------------------------------------------------------------------

def _parse_age_range(ages_str: str) -> tuple[int, int]:
    """Parse ages text like '2 months - 6 years 11 months' to (age_min, age_max)."""
    if not ages_str or pd.isna(ages_str):
        return 0, 12

    ages_str = str(ages_str).strip()
    parts = ages_str.split("-")

    def _extract_years(s: str) -> int | None:
        s = s.strip()
        if "birth" in s.lower():
            return 0
        # Remove month info
        s_no_months = re.sub(r"\d+\s*months?", "", s).strip()
        year_match = re.search(r"(\d+)\s*year", s_no_months)
        if year_match:
            return int(year_match.group(1))
        # Just a number
        num_match = re.match(r"(\d+)", s_no_months)
        if num_match:
            return int(num_match.group(1))
        return None

    age_min = 0
    age_max = 12

    if len(parts) >= 2:
        min_val = _extract_years(parts[0])
        max_val = _extract_years(parts[1])
        if min_val is not None:
            age_min = min_val
        if max_val is not None:
            age_max = max_val
    elif len(parts) == 1:
        val = _extract_years(parts[0])
        if val is not None:
            age_max = val

    return age_min, age_max


def scrape(year: int | None = None) -> Path:
    """Run full VDSS scrape pipeline and write locations CSV.

    Parameters
    ----------
    year : int, optional
        Year label for the output file. Defaults to current year.
    """
    if year is None:
        from datetime import datetime
        year = datetime.now().year

    t0 = time.time()

    # Step 1: Fetch facility list
    facilities = fetch_facility_list()

    # Step 2: Fetch details
    details = fetch_details(facilities)

    # Merge
    merged = facilities.merge(details, on="id", how="left")

    # Step 3: Geocode
    coords = geocode_facilities(merged)
    merged = merged.merge(coords, on="id", how="left")
    merged.rename(columns={"lon": "long"}, inplace=True)

    # Step 4: Parse ages and fill defaults
    ages_parsed = merged["ages"].apply(_parse_age_range)
    merged["age_min"] = ages_parsed.apply(lambda x: x[0])
    merged["age_max"] = ages_parsed.apply(lambda x: x[1])
    merged["capacity"] = merged["capacity"].fillna(4).astype(int)

    # Drop facilities with no coordinates
    has_coords = merged["lat"].notna() & merged["long"].notna()
    log.info(
        "Facilities with coordinates: %d / %d",
        has_coords.sum(), len(merged),
    )
    merged = merged[has_coords].copy()

    # Write locations CSV
    out_path = DATA_DIR / f"working/locations_{year}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False)
    log.info("Wrote %d facilities to %s", len(merged), out_path)

    # Write GeoJSON for map layers
    geojson_path = DATA_DIR / f"distribution/points_{year}.geojson"
    geojson_path.parent.mkdir(parents=True, exist_ok=True)
    features = []
    for _, row in merged.iterrows():
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row["long"], row["lat"]],
            },
            "properties": {
                "name": row.get("name", ""),
                "capacity": int(row["capacity"]),
                "age_min": int(row["age_min"]),
                "age_max": int(row["age_max"]),
                "type": row.get("type", ""),
            },
        })
    import json
    geojson = {"type": "FeatureCollection", "features": features}
    geojson_path.write_text(json.dumps(geojson))
    log.info("Wrote %s", geojson_path)

    elapsed = time.time() - t0
    log.info("Scrape complete in %.1f seconds", elapsed)
    return out_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape VDSS daycare facilities")
    parser.add_argument("--year", type=int, default=None, help="Year label (default: current year)")
    args = parser.parse_args()
    scrape(year=args.year)
