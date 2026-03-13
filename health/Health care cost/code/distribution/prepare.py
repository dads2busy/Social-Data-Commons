"""Prepare marketplace premium data for dashboard sites.

Steps:
1. Read ingest output from data/distribution/
2. Interpolate VA 2023 gap (VA transitioned FFM→SBE; no PUF that year)
3. Filter to VA counties, aggregate to health districts
4. Write combined VA file (county + HD) to data/distribution/
5. Reformat for VA dashboard (health_district + county levels)
6. Reformat for NCR dashboard (county level)
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sdc_core.geo import aggregate_with_crosswalk
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("health_care_cost.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path) -> Path | None:
    """Find the ingest output file (national, us_ prefix).

    If multiple files match, prefer the most recently modified.
    """
    candidates = list(dist_dir.glob("us_ct_cms_puf*marketplace_premium*.csv.xz"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def interpolate_va_2023(df: pd.DataFrame) -> pd.DataFrame:
    """Interpolate VA 2023 premiums from 2022 (FFM) and 2024 (SBE) data.

    VA transitioned from the FFM to its own SBE in 2023, but no SBE PUF
    was published that year.  For counties that have both 2022 and 2024
    values, synthesize a 2023 row as the midpoint.
    """
    va = df[df["geoid"].str.startswith("51")]
    if va.empty or 2023 in va["year"].unique():
        return df  # nothing to interpolate

    y22 = va[va["year"] == 2022].set_index(["geoid", "measure"])
    y24 = va[va["year"] == 2024].set_index(["geoid", "measure"])

    both = y22.index.intersection(y24.index)
    if both.empty:
        return df

    interp = y22.loc[both].copy()
    interp["year"] = 2023
    interp["value"] = np.round(
        (y22.loc[both, "value"].values + y24.loc[both, "value"].values) / 2, 2,
    )
    interp["moe"] = pd.NA
    interp = interp.reset_index()

    log.info("Interpolated %d VA 2023 rows from 2022/2024 data", len(interp))
    return pd.concat([df, interp], ignore_index=True)


def run() -> None:
    t0 = time.time()
    config = load_config()
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    source = find_source(DIST_DIR)
    if not source:
        raise FileNotFoundError("No ingest output found in data/distribution/")

    log.info("Reading ingest output: %s", source)
    df = read_data(source)

    # Fill VA 2023 gap via linear interpolation
    df = interpolate_va_2023(df)

    # --- VA dashboard: county + health district ---
    va_counties = df[df["geoid"].str.startswith("51")].copy()

    if not va_counties.empty:
        xwalk = pd.read_csv(
            crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str},
        )
        hd = aggregate_with_crosswalk(
            va_counties,
            crosswalk=xwalk,
            source_col="ct_geoid",
            target_col="hd_geoid",
            method="mean",
            value_col="value",
            target_region_type="health_district",
        )
        hd["moe"] = pd.NA

        va_combined = pd.concat([va_counties, hd], ignore_index=True)
        va_combined = va_combined.sort_values(
            ["geoid", "year", "measure"]
        ).reset_index(drop=True)

        va_name = build_file_name(
            coverage_area="va",
            data_source="cms_puf",
            years=sorted(va_combined["year"].unique().tolist()),
            title="marketplace_premium",
            geographies=["health_district", "county"],
        )
        va_path = write_data(va_combined, DIST_DIR / f"{va_name}.csv.xz")
        log.info("Wrote %d rows to %s", len(va_combined), va_path)

        for p in data_reformat_for_site(
            source_path=va_path,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county"],
            coverage_area="va",
            data_source="cms_puf",
            title="marketplace_premium",
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)

    # --- NCR dashboard: county only (DC + MD + VA) ---
    ncr_states = {"11", "24", "51"}  # DC, MD, VA
    ncr_counties = df[df["geoid"].str[:2].isin(ncr_states)].copy()

    if not ncr_counties.empty:
        ncr_name = build_file_name(
            coverage_area="ncr",
            data_source="cms_puf",
            years=sorted(ncr_counties["year"].unique().tolist()),
            title="marketplace_premium",
            geographies=["county"],
        )
        ncr_path = write_data(ncr_counties, DIST_DIR / f"{ncr_name}.csv.xz")
        log.info("Wrote %d NCR rows to %s", len(ncr_counties), ncr_path)

        for p in data_reformat_for_site(
            source_path=ncr_path,
            output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
            levels=["county"],
            coverage_area="ncr",
            data_source="cms_puf",
            title="marketplace_premium",
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)

    log.info("Done in %.1fs", time.time() - t0)
    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
