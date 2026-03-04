"""Prepare population density: aggregate to health districts and reformat for dashboard.

Steps:
1. Find the VA ACS distribution file produced by ingest.py
2. Aggregate county-level density to health districts via crosswalk
3. Combine all levels and write updated VA distribution file
4. Reformat to wide per-level files for the VA dashboard repo

Configuration is read from population_density/pipeline.yaml.
"""

import time
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.geo import aggregate_with_crosswalk
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.profiles import resolve_states
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("population_density.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_va_source(dist_dir: Path) -> Path | None:
    """Find the most recent VA population density ingest output (county+tract, no health districts)."""
    candidates = sorted(dist_dir.glob("va_cttr_*population_density.csv.xz"))
    return candidates[-1] if candidates else None


def run(pipeline=None) -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        out = config["output"]
        prep = config["prepare"]

        va_source = find_va_source(DIST_DIR)
        if va_source is None:
            raise FileNotFoundError(f"No VA population density file found in {DIST_DIR}")
        log.info("Reading VA source: %s", va_source)
        df = read_data(va_source)

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

        source_cfg = config.get("sources", {}).get("va", config.get("source", {}))
        states = resolve_states(source_cfg)
        auto_name = build_file_name(
            df=result,
            states=states,
            years=source_cfg.get("years"),
            source_type=source_cfg.get("type"),
            title=config.get("name"),
        )
        filename = f"{auto_name}.csv.xz" if auto_name else "va_population_density.csv.xz"
        out_path = write_data(
            result,
            DIST_DIR / filename,
            census_standardize=False,
        )
        log.info("Wrote %d rows to %s", len(result), out_path)

        measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None
        paths = data_reformat_for_site(
            source_path=out_path,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county", "tract"],
            coverage_area="va",
            data_source="census_acs",
            title="population_density",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)

        return RunResult(
            success=True,
            rows=len(result),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Population density prepare failed: %s", e, exc_info=True)
        return RunResult(
            success=False,
            error=str(e),
            duration_sec=time.time() - t0,
        )


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
