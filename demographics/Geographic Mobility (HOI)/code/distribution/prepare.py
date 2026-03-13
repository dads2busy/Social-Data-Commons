"""Prepare geographic mobility (HOI) data: aggregate to health districts and reformat for dashboard.

Steps:
1. Find the VA ACS distribution file produced by ingest.py
2. Aggregate county-level mobility to health districts via crosswalk
3. Combine all levels and write updated VA distribution file
4. Reformat to wide per-level files for the VA dashboard repo

Configuration is read from Geographic Mobility (HOI)/pipeline.yaml.
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
from sdc_core.redistribute import run_redistribution
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("geographic_mobility_hoi.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_va_source(dist_dir: Path) -> Path | None:
    """Find the most recent VA geographic mobility ingest output (county+tract, no health districts)."""
    candidates = sorted(dist_dir.glob("va_cttr_*geographic_mobility_hoi.csv.xz"))
    return candidates[-1] if candidates else None


def find_ncr_source(dist_dir: Path) -> Path | None:
    """Find the most recent NCR geographic mobility ingest output."""
    candidates = sorted(dist_dir.glob("ncr_cttr_*geographic_mobility_hoi.csv.xz"))
    return candidates[-1] if candidates else None


def run(pipeline=None) -> None:
    t0 = time.time()
    config = load_config()
    out = config["output"]
    prep = config["prepare"]

    va_source = find_va_source(DIST_DIR)
    if va_source is None:
        raise FileNotFoundError(f"No VA geographic mobility file found in {DIST_DIR}")
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

    # Redistribution step: estimate block group values from tracts
    redist_config = prep.get("redistribution")
    if redist_config:
        redistributed = run_redistribution(
            df=result,
            config=redist_config,
            repo_dir=REPO_DIR,
            coverage_area="va",
            logger=log,
        )
        if not redistributed.empty:
            log.info("Redistribution produced %d rows", len(redistributed))
            result = pd.concat([result, redistributed], ignore_index=True)

    source_cfg = config.get("sources", {}).get("va", config.get("source", {}))
    states = resolve_states(source_cfg)
    auto_name = build_file_name(
        df=result,
        states=states,
        years=source_cfg.get("years"),
        source_type=source_cfg.get("type"),
        title=config.get("name"),
    )
    filename = f"{auto_name}.csv.xz" if auto_name else "va_geographic_mobility_hoi.csv.xz"
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
        levels=["health_district", "county", "tract", "block_group"],
        coverage_area="va",
        data_source="census_acs",
        title="geographic_mobility_hoi",
        measure_info_path=measure_info,
    )
    for p in paths:
        log.info("Wrote %s", p)

    # --- NCR pipeline ---
    ncr_source = find_ncr_source(DIST_DIR)
    if ncr_source:
        log.info("Reading NCR source: %s", ncr_source)
        ncr_df = read_data(ncr_source)

        ncr_prep = config.get("prepare_ncr", {})
        ncr_redist_config = ncr_prep.get("redistribution")
        if ncr_redist_config:
            ncr_redistributed = run_redistribution(
                df=ncr_df,
                config=ncr_redist_config,
                repo_dir=REPO_DIR,
                coverage_area="ncr",
                logger=log,
            )
            if not ncr_redistributed.empty:
                log.info("NCR redistribution produced %d rows", len(ncr_redistributed))
                ncr_df = pd.concat([ncr_df, ncr_redistributed], ignore_index=True)

                # Write updated NCR file with block group data
                ncr_source_cfg = config.get("sources", {}).get("ncr", {})
                ncr_states = resolve_states(ncr_source_cfg)
                ncr_auto_name = build_file_name(
                    df=ncr_df,
                    states=ncr_states,
                    years=ncr_source_cfg.get("years"),
                    source_type=ncr_source_cfg.get("type"),
                    title=config.get("name"),
                )
                ncr_filename = f"{ncr_auto_name}.csv.xz" if ncr_auto_name else "ncr_geographic_mobility_hoi.csv.xz"
                ncr_out_path = write_data(
                    ncr_df,
                    DIST_DIR / ncr_filename,
                    census_standardize=False,
                )
                log.info("Wrote %d NCR rows to %s", len(ncr_df), ncr_out_path)
                if ncr_out_path != ncr_source:
                    ncr_source.unlink()
                    log.info("Removed ingest-only NCR file: %s", ncr_source.name)
                ncr_source = ncr_out_path

        paths = data_reformat_for_site(
            source_path=ncr_source,
            output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
            levels=["county", "tract", "block_group"],
            coverage_area="ncr",
            data_source="census_acs",
            title="geographic_mobility_hoi",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)
    else:
        log.warning("No NCR source file found in %s", DIST_DIR)

    log.info("Done in %.1fs", time.time() - t0)
    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
