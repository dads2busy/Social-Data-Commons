"""Build a crosswalk between Mobility Database feed IDs and Transitland onestop IDs.

Matching strategies (applied in order):
  1. Exact URL match (direct_download_url ↔ static_current or static_historic)
  2. Fuzzy provider name match (≥0.80 similarity)

Requires: data/transitland-atlas/ (clone from github.com/transitland/transitland-atlas)

Usage:
    uv run python build_crosswalk.py

Output: data/mdb_transitland_crosswalk.csv
"""

import json
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
from sdc_core.log import get_logger

BASE_DIR = Path(__file__).resolve().parents[1]
CATALOG_PATH = BASE_DIR / "data/feeds_catalog.csv"
ATLAS_DIR = BASE_DIR / "data/transitland-atlas/feeds"
OUT_PATH = BASE_DIR / "data/mdb_transitland_crosswalk.csv"

log = get_logger("transit_stops.build_crosswalk")

NAME_SIMILARITY_THRESHOLD = 0.80


def parse_transitland_atlas() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse all DMFR files and return (feeds_df, operators_df)."""
    feeds = []
    operators = []

    for f in sorted(ATLAS_DIR.glob("*.dmfr.json")):
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue

        for feed in data.get("feeds", []):
            if feed.get("spec") != "gtfs":
                continue
            urls = feed.get("urls", {})
            static_url = urls.get("static_current", "")
            historic_urls = urls.get("static_historic", [])
            all_urls = ([static_url] if static_url else []) + historic_urls
            feeds.append({
                "onestop_id": feed.get("id", ""),
                "static_url": static_url,
                "all_urls": all_urls,
            })

        for op in data.get("operators", []):
            for assoc in op.get("associated_feeds", []):
                operators.append({
                    "onestop_id": assoc.get("feed_onestop_id", ""),
                    "operator_name": op.get("name", ""),
                })

    feeds_df = pd.DataFrame(feeds)
    ops_df = pd.DataFrame(operators).drop_duplicates("onestop_id")
    feeds_df = feeds_df.merge(ops_df, on="onestop_id", how="left")
    return feeds_df, ops_df


def normalize_name(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.lower().strip()
    for rem in ["inc.", "inc", "llc", "ltd", "co.", "corporation", "corp.", "corp"]:
        s = s.replace(rem, "")
    return " ".join(s.split())


def run():
    if not ATLAS_DIR.exists():
        raise FileNotFoundError(
            f"Transitland Atlas not found at {ATLAS_DIR}. "
            "Clone it: git clone --depth 1 https://github.com/transitland/transitland-atlas.git data/transitland-atlas"
        )

    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"Catalog not found at {CATALOG_PATH}. Run fetch_catalog.py first."
        )

    tl_df, _ = parse_transitland_atlas()
    mdb = pd.read_csv(CATALOG_PATH, dtype=str)
    log.info("Transitland GTFS feeds: %d, Mobility DB feeds: %d", len(tl_df), len(mdb))

    # Strategy 1: URL matching (current + historic URLs)
    url_to_onestop: dict[str, str] = {}
    for _, row in tl_df.iterrows():
        for u in row["all_urls"]:
            if u and isinstance(u, str):
                url_to_onestop[u.strip().rstrip("/").lower()] = row["onestop_id"]

    results = []
    for _, row in mdb.iterrows():
        url = str(row.get("direct_download_url") or "").strip().rstrip("/").lower()
        oid = url_to_onestop.get(url, "")
        results.append({
            "mdb_id": row["id"],
            "onestop_id": oid,
            "method": "url" if oid else "",
        })

    url_matched = sum(1 for r in results if r["onestop_id"])
    log.info("URL matches: %d", url_matched)

    # Strategy 2: Fuzzy name matching for unmatched feeds
    tl_names = tl_df[["onestop_id", "operator_name"]].dropna(subset=["operator_name"]).drop_duplicates("onestop_id")
    tl_name_lookup = [
        (normalize_name(row["operator_name"]), row["onestop_id"])
        for _, row in tl_names.iterrows()
        if normalize_name(row["operator_name"])
    ]

    name_matched = 0
    for r in results:
        if r["onestop_id"]:
            continue
        mdb_row = mdb[mdb["id"] == r["mdb_id"]].iloc[0]
        mdb_name = normalize_name(str(mdb_row.get("provider", "")))
        if not mdb_name or len(mdb_name) < 5:
            continue

        best_score = 0.0
        best_oid = ""
        for tl_name, oid in tl_name_lookup:
            if abs(len(mdb_name) - len(tl_name)) > 20:
                continue
            score = SequenceMatcher(None, mdb_name, tl_name).ratio()
            if score > best_score:
                best_score = score
                best_oid = oid
        if best_score >= NAME_SIMILARITY_THRESHOLD:
            r["onestop_id"] = best_oid
            r["method"] = f"name_{best_score:.2f}"
            name_matched += 1

    log.info("Name matches: %d", name_matched)

    # Save crosswalk
    xwalk = pd.DataFrame(results)
    xwalk = xwalk[xwalk["onestop_id"] != ""]
    xwalk.to_csv(OUT_PATH, index=False)

    total = len(xwalk)
    active_mdb = set(mdb[mdb["status"] == "active"]["id"])
    active_matched = sum(1 for r in results if r["onestop_id"] and r["mdb_id"] in active_mdb)

    log.info(
        "Crosswalk: %d/%d total (%.1f%%), %d/%d active (%.1f%%)",
        total, len(mdb), 100 * total / len(mdb),
        active_matched, len(active_mdb), 100 * active_matched / len(active_mdb),
    )
    log.info("Wrote %s", OUT_PATH)


if __name__ == "__main__":
    run()
