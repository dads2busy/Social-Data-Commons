"""Prepare environmental hazard data for VA and NCR dashboards.

Steps:
1. Read ingest output (VA tracts)
2. Aggregate tracts → counties (mean)
3. Aggregate counties → health districts via crosswalk (mean)
4. Combine tract + county + HD
5. Write VA distribution file
6. Reformat for VA dashboard
"""

import time
from pathlib import Path

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

log = get_logger("env_hazard.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path, prefix: str = "va") -> Path | None:
    """Find the ingest output file (tracts)."""
    candidates = list(dist_dir.glob(f"{prefix}_tr_epa*environmental_hazard*.csv.xz"))
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    # Fall back to combined file from previous prepare run
    candidates = list(dist_dir.glob(f"{prefix}_*epa*environmental_hazard*.csv.xz"))
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    return None


def aggregate_to_counties(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate tracts to counties by truncating GEOID to 5 digits."""
    tracts = df[df["region_type"] == "tract"].copy()
    tracts["county_geoid"] = tracts["geoid"].str[:5]

    group_cols = ["county_geoid", "year", "measure"]
    if "data_method" in tracts.columns and tracts["data_method"].notna().any():
        group_cols.append("data_method")

    counties = (
        tracts.groupby(group_cols)["value"]
        .mean()
        .reset_index()
        .rename(columns={"county_geoid": "geoid"})
    )
    counties["moe"] = pd.NA
    counties["region_type"] = "county"
    return counties


def run() -> None:
    t0 = time.time()
    config = load_config()
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    # --- VA pipeline ---
    va_source = find_source(DIST_DIR, "va")
    if va_source:
        log.info("Reading VA source: %s", va_source)
        df = read_data(va_source)

        # If reading combined file, extract only tract-level rows
        if "region_type" in df.columns:
            df = df[df["region_type"] == "tract"].copy()
            log.info("Extracted %d tract rows from combined file", len(df))

        # Aggregate tracts → counties
        counties = aggregate_to_counties(df)
        log.info("Aggregated to %d county rows", len(counties))

        # Aggregate counties → health districts
        xwalk = pd.read_csv(
            crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str},
        )
        hd = aggregate_with_crosswalk(
            counties,
            crosswalk=xwalk,
            source_col="ct_geoid",
            target_col="hd_geoid",
            method="mean",
            value_col="value",
            target_region_type="health_district",
        )
        hd["moe"] = pd.NA
        # Carry data_method from counties (all rows in a year share the same method)
        if "data_method" in counties.columns:
            year_to_method = counties.drop_duplicates("year").set_index("year")["data_method"]
            hd["data_method"] = hd["year"].map(year_to_method)
        log.info("Aggregated to %d health district rows", len(hd))

        # Combine all levels
        va_combined = pd.concat([df, counties, hd], ignore_index=True)
        va_combined = va_combined.sort_values(
            ["geoid", "year", "measure"],
        ).reset_index(drop=True)

        # Write combined VA file
        va_name = build_file_name(
            coverage_area="va",
            data_source="epa",
            years=sorted(va_combined["year"].unique().tolist()),
            title="environmental_hazard",
            geographies=["health_district", "county", "tract"],
        )
        va_path = write_data(va_combined, DIST_DIR / f"{va_name}.csv.xz")
        log.info("Wrote %d rows to %s", len(va_combined), va_path)

        # Delete ingest-only tract file (superset written above)
        if va_source != va_path and va_source.exists():
            va_source.unlink()
            log.info("Removed ingest-only file: %s", va_source.name)

        # Reformat for VA dashboard
        for p in data_reformat_for_site(
            source_path=va_path,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county", "tract"],
            coverage_area="va",
            data_source="epa",
            title="environmental_hazard",
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)
    else:
        log.warning("No VA environmental hazard file found in %s", DIST_DIR)

    # --- NCR pipeline (no HD aggregation needed) ---
    ncr_source = find_source(DIST_DIR, "ncr")
    if ncr_source:
        log.info("Reading NCR source: %s", ncr_source)
        ncr_df = read_data(ncr_source)

        # If tract-only ingest output, aggregate to counties
        if "region_type" in ncr_df.columns:
            ncr_tracts = ncr_df[ncr_df["region_type"] == "tract"].copy()
        else:
            ncr_tracts = ncr_df.copy()
            ncr_tracts["region_type"] = "tract"

        ncr_counties = aggregate_to_counties(ncr_tracts)
        ncr_combined = pd.concat([ncr_tracts, ncr_counties], ignore_index=True)
        ncr_combined = ncr_combined.sort_values(
            ["geoid", "year", "measure"],
        ).reset_index(drop=True)

        # Write combined NCR file
        ncr_name = build_file_name(
            coverage_area="ncr",
            data_source="epa",
            years=sorted(ncr_combined["year"].unique().tolist()),
            title="environmental_hazard",
            geographies=["county", "tract"],
        )
        ncr_path = write_data(ncr_combined, DIST_DIR / f"{ncr_name}.csv.xz")
        log.info("Wrote %d rows to %s", len(ncr_combined), ncr_path)

        # Delete ingest-only tract file
        if ncr_source != ncr_path and ncr_source.exists():
            ncr_source.unlink()
            log.info("Removed ingest-only file: %s", ncr_source.name)

        # Reformat for NCR dashboard
        for p in data_reformat_for_site(
            source_path=ncr_path,
            output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
            levels=["county", "tract"],
            coverage_area="ncr",
            data_source="epa",
            title="environmental_hazard",
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)
    else:
        log.warning("No NCR environmental hazard file found in %s", DIST_DIR)

    log.info("Done in %.1fs", time.time() - t0)
    update_version(TOPIC_DIR)


if __name__ == "__main__":
    run()
