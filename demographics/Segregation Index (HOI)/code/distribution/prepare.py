"""Prepare segregation data: aggregate tracts to counties and health districts, then reformat for dashboard.

Steps:
1. Find the VA ACS distribution file produced by ingest.py (tract-level only)
2. Aggregate tracts to counties (sum)
3. Aggregate counties to health districts via crosswalk (sum)
4. Combine all levels and write VA distribution file
5. Reformat to wide per-level files for the VA dashboard repo

Configuration is read from segregation/pipeline.yaml.
Uses sum aggregation (matching the R implementation).
"""

import time
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.geo import aggregate_up, aggregate_with_crosswalk
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.profiles import resolve_states
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("segregation.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_va_source(dist_dir: Path) -> Path | None:
    """Find the most recent VA segregation ingest output (tracts only, no health districts)."""
    candidates = sorted(dist_dir.glob("va_tr_*census_acs*segregation.csv.xz"))
    return candidates[-1] if candidates else None


def run(pipeline=None) -> None:
    t0 = time.time()
    config = load_config()
    out = config["output"]
    prep = config["prepare"]
    source_config = config.get("sources", {}).get("va", config.get("source"))

    va_source = find_va_source(DIST_DIR)
    if va_source is None:
        raise FileNotFoundError(f"No VA segregation file found in {DIST_DIR}")
    log.info("Reading VA source: %s", va_source)
    df = read_data(va_source)

    tract_data = df[df["region_type"] == "tract"].copy()

    # Tract -> County (sum, matching R implementation)
    log.info("Aggregating %d tract rows to counties", len(tract_data))
    county = aggregate_up(tract_data, target_geo="county", method="sum")

    # County -> Health District (sum via crosswalk)
    crosswalk_path = TOPIC_DIR / prep["crosswalk"]
    log.info("Loading crosswalk from %s", crosswalk_path)
    crosswalk = pd.read_csv(crosswalk_path, dtype=str)

    hd = aggregate_with_crosswalk(
        county,
        crosswalk=crosswalk,
        source_col=prep["source_col"],
        target_col=prep["target_col"],
        method=prep["method"],
        target_region_type="health_district",
    )
    log.info("Aggregated to %d health district rows", len(hd))

    result = pd.concat([tract_data, county, hd], ignore_index=True)
    result["moe"] = pd.NA

    states = resolve_states(source_config)
    auto_name = build_file_name(
        df=result,
        states=states,
        years=source_config.get("years"),
        source_type=source_config.get("type"),
        title=config.get("name"),
    )
    filename = f"{auto_name}.csv.xz" if auto_name else "va_segregation.csv.xz"
    out_path = write_data(
        result,
        DIST_DIR / filename,
        census_standardize=False,
    )
    log.info("Wrote %d rows to %s", len(result), out_path)
    if out_path != va_source:
        va_source.unlink()
        log.info("Removed ingest-only file: %s", va_source.name)

    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None
    paths = data_reformat_for_site(
        source_path=out_path,
        output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
        levels=["health_district", "county", "tract"],
        coverage_area="va",
        data_source="census_acs",
        title="segregation",
        measure_info_path=measure_info,
    )
    for p in paths:
        log.info("Wrote %s", p)

    log.info("Done in %.1fs", time.time() - t0)
    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
