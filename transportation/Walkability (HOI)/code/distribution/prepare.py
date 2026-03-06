"""Prepare walkability index for dashboard sites.

Steps:
1. Find VA ingest output, aggregate counties to health districts
2. Write combined VA distribution file and per-level dashboard files
3. Find NCR ingest output and write per-level dashboard files

Configuration is read from Walkability (HOI)/pipeline.yaml.
"""

import time
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.geo import aggregate_with_crosswalk
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("walkability.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path, prefix: str) -> Path | None:
    candidates = sorted(dist_dir.glob(f"{prefix}_cttr_epa_sld*walkability*.csv.xz"))
    return candidates[-1] if candidates else None


def run() -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
        measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

        # --- VA pipeline ---
        va_source = find_source(DIST_DIR, "va")
        if va_source:
            log.info("Reading VA source: %s", va_source)
            df = read_data(va_source)

            counties = df[df["region_type"] == "county"].copy()
            xwalk = pd.read_csv(crosswalk_path, dtype=str)
            hd = aggregate_with_crosswalk(
                counties, crosswalk=xwalk,
                source_col="ct_geoid", target_col="hd_geoid",
                method="mean", target_region_type="health_district",
            )
            log.info("Aggregated %d county rows to %d HD rows", len(counties), len(hd))

            result = pd.concat([df, hd], ignore_index=True)

            auto_name = build_file_name(
                df=result, coverage_area="va", years=[2019],
                source_type="epa_sld", title="walkability_index",
            )
            filename = f"{auto_name}.csv.xz" if auto_name else "va_walkability_index.csv.xz"
            va_out = write_data(result, DIST_DIR / filename, census_standardize=False)
            log.info("Wrote %d rows to %s", len(result), va_out)

            if va_out != va_source:
                va_source.unlink()
                log.info("Removed ingest-only file: %s", va_source.name)

            for p in data_reformat_for_site(
                source_path=va_out,
                output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
                levels=["health_district", "county", "tract"],
                coverage_area="va", data_source="epa_sld",
                title="walkability_index",
                measure_info_path=measure_info,
            ):
                log.info("Wrote %s", p)
        else:
            log.warning("No VA source file found in %s", DIST_DIR)

        # --- NCR pipeline ---
        ncr_source = find_source(DIST_DIR, "ncr")
        if ncr_source:
            log.info("Reading NCR source: %s", ncr_source)
            for p in data_reformat_for_site(
                source_path=ncr_source,
                output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
                levels=["county", "tract"],
                coverage_area="ncr", data_source="epa_sld",
                title="walkability_index",
                measure_info_path=measure_info,
            ):
                log.info("Wrote %s", p)
        else:
            log.warning("No NCR source file found in %s", DIST_DIR)

        return RunResult(
            success=True,
            rows=len(result) if va_source else 0,
            output_path=str(va_out) if va_source else "",
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Prepare failed: %s", e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
    update_version(TOPIC_DIR)
