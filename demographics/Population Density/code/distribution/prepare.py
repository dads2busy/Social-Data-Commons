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
from sdc_core.versioning import update_version

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


def find_va_prepared(dist_dir: Path) -> Path | None:
    """Find the already-prepared VA population density file (HD+county+tract)."""
    candidates = sorted(dist_dir.glob("va_hdcttr_*population_density.csv.xz"))
    return candidates[-1] if candidates else None


def find_ncr_source(dist_dir: Path) -> Path | None:
    """Find the most recent NCR population density ingest output."""
    candidates = sorted(dist_dir.glob("ncr_*population_density.csv.xz"))
    return candidates[-1] if candidates else None


def run(pipeline=None) -> None:
    t0 = time.time()
    config = load_config()
    out = config["output"]
    prep = config["prepare"]

    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    # --- VA pipeline ---
    va_source = find_va_source(DIST_DIR)
    if va_source is not None:
        # Fresh ingest output: aggregate counties → health districts
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
        va_out_path = write_data(
            result,
            DIST_DIR / filename,
            census_standardize=False,
        )
        log.info("Wrote %d rows to %s", len(result), va_out_path)
        if va_out_path != va_source:
            va_source.unlink()
            log.info("Removed ingest-only file: %s", va_source.name)
    else:
        # Already prepared — use existing hdcttr file
        va_out_path = find_va_prepared(DIST_DIR)
        if va_out_path:
            log.info("Using already-prepared VA file: %s", va_out_path)
        else:
            log.warning("No VA population density file found in %s", DIST_DIR)

    if va_out_path:
        paths = data_reformat_for_site(
            source_path=va_out_path,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county", "tract"],
            coverage_area="va",
            data_source="census_acs",
            title="population_density",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)

    # --- NCR pipeline (no HD aggregation needed) ---
    ncr_source = find_ncr_source(DIST_DIR)
    if ncr_source:
        log.info("Reading NCR source: %s", ncr_source)
        ncr_df = read_data(ncr_source)

        ncr_levels = sorted(ncr_df["region_type"].dropna().unique().tolist())
        log.info("NCR levels: %s (%d rows)", ncr_levels, len(ncr_df))

        ncr_paths = data_reformat_for_site(
            source_path=ncr_source,
            output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
            levels=ncr_levels,
            coverage_area="ncr",
            data_source="census_acs",
            title="population_density",
            measure_info_path=measure_info,
        )
        for p in ncr_paths:
            log.info("Wrote %s", p)
    else:
        log.warning("No NCR population density file found in %s", DIST_DIR)

    log.info("Done in %.1fs", time.time() - t0)
    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
