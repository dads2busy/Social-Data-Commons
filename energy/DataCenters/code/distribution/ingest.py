"""Ingest the IM3 Open Source Data Center Atlas, filtered to Virginia.

Reads `data/original/im3_atlas_data_centers.csv`, filters by `state_abb`,
reshapes to the point schema, and writes:

  data/distribution/{point_csv}    point-schema rows
  data/distribution/{county_csv}   long-format county aggregates

Run: uv run python energy/DataCenters/code/distribution/ingest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.io import write_data, write_point_data
from sdc_core.log import get_logger

THIS_DIR = Path(__file__).resolve().parent
TOPIC_DIR = THIS_DIR.parents[1]

sys.path.insert(0, str(THIS_DIR))
from transforms import aggregate_to_counties, filter_and_shape

log = get_logger("data_centers.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def run() -> None:
    config = load_config()
    source = config["source"]
    out = config["output"]

    input_path = TOPIC_DIR / source["input_file"]
    point_csv = TOPIC_DIR / out["point_csv"]
    county_csv = TOPIC_DIR / out["county_csv"]

    log.info("Reading %s", input_path)
    raw = pd.read_csv(input_path, dtype={"county_id": str, "state_id": str})
    log.info("Loaded %d source rows (US-wide)", len(raw))

    log.info("Filtering to state_abb=%s", source["state_filter"])
    shaped = filter_and_shape(
        raw,
        state_filter=source["state_filter"],
        snapshot_year=source["snapshot_year"],
    )
    log.info("Retained %d %s rows", len(shaped), source["state_filter"])

    log.info("Writing point CSV → %s", point_csv)
    point_csv.parent.mkdir(parents=True, exist_ok=True)
    write_point_data(shaped, point_csv)

    log.info("Aggregating to county-level long-format")
    scenario_date = f"{source['snapshot_year']}-02-09"   # IM3 Atlas v2026.02.09 publication date
    county_rows = aggregate_to_counties(
        shaped,
        scenario=source["scenario"],
        scenario_date=scenario_date,
    )
    log.info("Produced %d county-level rows", len(county_rows))

    log.info("Writing county CSV → %s", county_csv)
    county_csv.parent.mkdir(parents=True, exist_ok=True)
    write_data(county_rows, county_csv, standardize=False, census_standardize=False)

    log.info("Done.")


if __name__ == "__main__":
    run()
