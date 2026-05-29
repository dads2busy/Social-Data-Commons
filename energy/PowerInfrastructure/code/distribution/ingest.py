"""Ingest HIFLD power plants and electric substations for Virginia.

Fetches the HIFLD Power_Plants and Electric_Substations ArcGIS REST layers
(republished by the 543rd Engineer Detachment GPC) filtered to STATE='VA',
shapes them to the point schema, and writes:

  data/distribution/{point_csv}    point-schema rows (one per facility)
  data/distribution/{county_csv}   long-format county counts + capacity

County FIPS comes from the source COUNTYFIPS field (no spatial join needed).

Run: uv run python energy/PowerInfrastructure/code/distribution/ingest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pandas as pd
import yaml
from sdc_core.io import write_data, write_point_data
from sdc_core.log import get_logger

THIS_DIR = Path(__file__).resolve().parent
TOPIC_DIR = THIS_DIR.parents[1]

sys.path.insert(0, str(THIS_DIR))
from transforms import aggregate_to_counties, shape_records

log = get_logger("power_infrastructure.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def fetch_layer(layer: dict, *, state_filter: str, page_size: int) -> pd.DataFrame:
    """Page through an ArcGIS FeatureServer /query endpoint; return attributes as a DataFrame."""
    url = layer["url"]
    where = f"STATE='{state_filter}'"
    offset = 0
    frames = []
    while True:
        params = {
            "where": where,
            "outFields": layer["out_fields"],
            "f": "json",
            "returnGeometry": "false",
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "orderByFields": layer["id_field"],
        }
        resp = httpx.get(url, params=params, timeout=120)
        resp.raise_for_status()
        payload = resp.json()
        if "error" in payload:
            raise RuntimeError(f"ArcGIS error from {url}: {payload['error']}")
        feats = payload.get("features", [])
        if not feats:
            break
        frames.append(pd.DataFrame([f["attributes"] for f in feats]))
        log.info("  fetched %d rows (offset %d)", len(feats), offset)
        if not payload.get("exceededTransferLimit") and len(feats) < page_size:
            break
        offset += len(feats)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def run() -> None:
    config = load_config()
    source = config["source"]
    out = config["output"]

    point_csv = TOPIC_DIR / out["point_csv"]
    county_csv = TOPIC_DIR / out["county_csv"]
    cache_dir = TOPIC_DIR / out["raw_cache_dir"]
    cache_dir.mkdir(parents=True, exist_ok=True)

    point_parts = []
    for kind, layer in source["layers"].items():
        log.info("Fetching HIFLD layer '%s' (STATE=%s)", kind, source["state_filter"])
        raw = fetch_layer(layer, state_filter=source["state_filter"], page_size=source["page_size"])
        log.info("Retrieved %d %s rows", len(raw), kind)
        if raw.empty:
            raise SystemExit(f"No rows returned for layer '{kind}' — check the service/where clause")
        raw.to_parquet(cache_dir / f"hifld_va_{kind}.parquet")
        shaped = shape_records(
            raw,
            kind=kind,
            id_field=layer["id_field"],
            id_prefix=layer["id_prefix"],
            snapshot_year=source["snapshot_year"],
            sentinel=source["null_sentinel"],
        )
        point_parts.append(shaped)

    point_rows = pd.concat(point_parts, ignore_index=True)
    log.info("Combined %d point rows", len(point_rows))

    log.info("Writing point CSV → %s", point_csv)
    point_csv.parent.mkdir(parents=True, exist_ok=True)
    write_point_data(point_rows, point_csv)

    log.info("Aggregating to county long-format")
    county_rows = aggregate_to_counties(
        point_rows,
        scenario=source["scenario"],
        scenario_date=source["snapshot_date"],
    )
    log.info("Produced %d county-level rows", len(county_rows))

    log.info("Writing county CSV → %s", county_csv)
    county_csv.parent.mkdir(parents=True, exist_ok=True)
    write_data(county_rows, county_csv, standardize=False, census_standardize=False)

    log.info("Done.")


if __name__ == "__main__":
    run()
