"""Ingest incarceration data: PPI 2020 tract baseline scaled by Vera county trends.

Virginia uses regional jails shared across counties, causing Vera's county-level
jail population to be 3-280x higher than PPI's tract-based counts (double-counting).
We solve this by using Vera ONLY for year-over-year scaling, anchored to PPI 2020.

Steps:
1. Load PPI 2020 VA tract data (baseline incarceration counts + population)
2. Load Vera county-level jail pop → compute annual mean per county
3. Compute Vera scaling factor per county-year relative to 2020
4. Scale PPI 2020 tract counts by county's Vera trend
5. Compute rate per 100,000 using PPI total population
6. Write tract-level output to data/distribution/
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd

from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"
ORIG_DIR = TOPIC_DIR / "data/original"
DIST_DIR = TOPIC_DIR / "data/distribution"

YEARS = list(range(2016, 2024))
MEASURE_NAME = "incarceration_rate_per_100000"

log = get_logger("incarceration.ingest")


def load_ppi_tracts() -> pd.DataFrame:
    """Load PPI 2020 VA tract data."""
    path = ORIG_DIR / "ppi_va_tract_2020.csv"
    df = pd.read_csv(path, dtype={"geoid": str})

    df["county_fips"] = df["geoid"].str[:5]
    df["incarcerated"] = pd.to_numeric(df["incarcerated"], errors="coerce").fillna(0)
    df["total_pop"] = pd.to_numeric(df["total_pop"], errors="coerce").fillna(0)

    log.info(
        "PPI: %d tracts, %d counties, %d total incarcerated",
        len(df), df["county_fips"].nunique(), int(df["incarcerated"].sum()),
    )
    return df


def load_vera_scaling(fips_prefix: str = "51") -> pd.DataFrame:
    """Load Vera county data, compute year-over-year scaling relative to 2020.

    Returns DataFrame with columns: county_fips, year, scale_factor
    where scale_factor = vera_jail_pop(year) / vera_jail_pop(2020).
    """
    path = ORIG_DIR / "incarceration_trends_county.csv"
    df = pd.read_csv(path, low_memory=False)

    df["fips"] = df["fips"].astype(str).str.zfill(5)
    va = df[df["fips"].str.startswith(fips_prefix)].copy()

    # Filter to years of interest with non-null jail pop
    va = va[va["year"].isin(YEARS) & va["total_jail_pop"].notna()]

    # Annual mean across quarterly observations
    annual = (
        va.groupby(["fips", "year"])["total_jail_pop"]
        .mean()
        .reset_index()
        .rename(columns={"fips": "county_fips", "total_jail_pop": "county_jail_pop"})
    )

    # Get 2020 baseline per county
    baseline = annual[annual["year"] == 2020].set_index("county_fips")["county_jail_pop"]

    # Compute scaling factor relative to 2020
    annual["base_2020"] = annual["county_fips"].map(baseline)
    annual["scale_factor"] = np.where(
        annual["base_2020"] > 0,
        annual["county_jail_pop"] / annual["base_2020"],
        1.0,
    )

    # Counties with 2020 data but missing some other years: fill missing years with 1.0
    counties_with_baseline = set(baseline.index)
    log.info(
        "Vera: %d county-year records, %d counties with 2020 baseline",
        len(annual), len(counties_with_baseline),
    )

    # Log aggregate trend
    for y in YEARS:
        sub = annual[annual["year"] == y]
        if len(sub) > 0:
            log.info("  %d: median scale=%.3f, mean=%.3f (%d counties)",
                     y, sub["scale_factor"].median(), sub["scale_factor"].mean(), len(sub))

    return annual[["county_fips", "year", "scale_factor"]]


def scale_tracts(ppi: pd.DataFrame, vera_scaling: pd.DataFrame) -> pd.DataFrame:
    """Scale PPI 2020 tract counts by Vera county trends."""
    # Build lookup: (county_fips, year) → scale_factor
    scale_lookup = vera_scaling.set_index(["county_fips", "year"])["scale_factor"]
    vera_counties = set(vera_scaling["county_fips"].unique())

    ppi_counties = set(ppi["county_fips"].unique())
    missing = ppi_counties - vera_counties
    if missing:
        log.info(
            "Counties in PPI but not Vera (%d): %s — scale=1.0 for all years",
            len(missing), sorted(missing),
        )

    all_frames = []
    for year in YEARS:
        rows = ppi[["geoid", "county_fips", "incarcerated", "total_pop"]].copy()
        rows["year"] = year

        # Look up scale factor per county
        rows["scale"] = rows["county_fips"].map(
            lambda c, y=year: scale_lookup.get((c, y), 1.0)
        )

        # Scale incarcerated count from PPI 2020 baseline
        rows["scaled_inc"] = rows["incarcerated"] * rows["scale"]

        # Compute rate per 100K
        rows["value"] = np.where(
            rows["total_pop"] > 0,
            np.round(rows["scaled_inc"] / rows["total_pop"] * 100_000, 2),
            np.nan,
        )

        rows["data_method"] = np.where(
            rows["county_fips"].isin(vera_counties),
            np.where(year == 2020, "observed", "scaled"),
            "observed",  # PPI-only counties: use 2020 values for all years
        )

        all_frames.append(rows[["geoid", "year", "value", "data_method"]])

    combined = pd.concat(all_frames, ignore_index=True)

    for method, count in combined["data_method"].value_counts().items():
        log.info("  %s: %d rows", method, count)

    return combined


def run() -> RunResult:
    t0 = time.time()
    try:
        ppi = load_ppi_tracts()
        vera_scaling = load_vera_scaling()

        combined = scale_tracts(ppi, vera_scaling)
        combined["measure"] = MEASURE_NAME
        combined["moe"] = pd.NA
        combined["region_type"] = "tract"

        combined = combined[
            ["geoid", "year", "measure", "value", "moe", "region_type", "data_method"]
        ].sort_values(["geoid", "year"]).reset_index(drop=True)

        log.info(
            "Final: %d rows, %d tracts, years %s",
            len(combined),
            combined["geoid"].nunique(),
            sorted(combined["year"].unique()),
        )

        # Log value stats
        log.info(
            "Values: mean=%.1f, median=%.1f, p95=%.1f, max=%.1f",
            combined["value"].mean(), combined["value"].median(),
            combined["value"].quantile(0.95), combined["value"].max(),
        )

        # Write output
        DIST_DIR.mkdir(parents=True, exist_ok=True)
        out_name = build_file_name(
            coverage_area="va",
            data_source="vera_ppi",
            years=sorted(combined["year"].unique().tolist()),
            title="incarceration_rate",
            geographies=["tract"],
        )
        out_path = write_data(
            combined,
            DIST_DIR / f"{out_name}.csv.xz",
            census_standardize=True,
            measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,
        )
        log.info("Wrote %s", out_path)

        return RunResult(
            success=True,
            rows=len(combined),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
