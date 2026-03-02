"""Prepare geographic mobility (HOI) data: aggregate to health districts.

Reads the ingested tract/county/block_group data and aggregates counties
to Virginia health districts using a crosswalk.
Configuration is read from Geographic Mobility (HOI)/pipeline.yaml.
"""

import time
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.geo import aggregate_with_crosswalk
from sdc_core.io import read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.profiles import resolve_states
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[1]
log = get_logger("geographic_mobility_hoi.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def run(pipeline=None) -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        out = config["output"]
        prep = config["prepare"]

        data_path = TOPIC_DIR / out["path"] / out["filename"]
        log.info("Reading ingested data from %s", data_path)
        df = read_data(data_path)

        crosswalk_path = TOPIC_DIR / prep["crosswalk"]
        log.info("Loading crosswalk from %s", crosswalk_path)
        crosswalk = pd.read_csv(crosswalk_path, dtype=str)

        county_data = df[df["region_type"] == "county"].copy()
        hd = aggregate_with_crosswalk(
            county_data,
            crosswalk=crosswalk,
            source_col=prep["source_col"],
            target_col=prep["target_col"],
            method=prep["method"],
            target_region_type="health_district",
        )
        log.info(
            "Aggregated %d county rows to %d health district rows",
            len(county_data),
            len(hd),
        )

        result = pd.concat([df, hd], ignore_index=True)

        out_dir = TOPIC_DIR / out["path"]
        states = resolve_states(config["source"])
        auto_name = build_file_name(
            df=result,
            states=states,
            years=config["source"].get("years"),
            source_type=config["source"].get("type"),
            title=config.get("name"),
        )
        filename = f"{auto_name}.csv.xz" if auto_name else out["filename"]
        out_path = write_data(
            result,
            out_dir / filename,
            census_standardize=out.get("standardize", False),
        )
        log.info("Wrote %d rows to %s", len(result), out_path)

        return RunResult(
            success=True,
            rows=len(result),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Geographic mobility (HOI) prepare failed: %s", e, exc_info=True)
        return RunResult(
            success=False,
            error=str(e),
            duration_sec=time.time() - t0,
        )


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
