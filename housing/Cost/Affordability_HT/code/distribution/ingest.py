"""Reproduce the H+T Affordability Index independently.

Instead of downloading pre-computed data from CNT's website, this pipeline
computes the H+T Index from scratch using:
- GTFS transit feeds (cached locally)
- ACS demographic/housing data (via Census API)
- LODES employment data (cached locally)
- TIGER geographic data (downloaded on demand)
- CNT's published regression coefficients (Tables 3-6 of methods doc)

This enables annual updates at block group resolution.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"
REPO_DIR = TOPIC_DIR.parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"
WORKING_DIR = TOPIC_DIR / "data/working"

log = get_logger("affordability_ht.ingest_reproduce")

# NCR county FIPS (5-digit) for filtering
NCR_COUNTY_FIPS = {
    "51059", "51600", "51610", "51107", "51013", "51510", "51683", "51685", "51153",
    "24021", "24031", "24033", "24017",
    "11001",
}


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def run_reproduction(
    year: int,
    target_states: list[str] = ("51",),
    buffer_states: list[str] = ("51", "24", "11", "54", "37", "21"),
    coverage_area: str = "va",
    target_counties: set[str] | None = None,
    gtfs_year: int | None = None,
) -> RunResult:
    """Run the full H+T Index reproduction for a given year.

    Parameters
    ----------
    year : data year (ACS and GTFS)
    target_states : FIPS codes for states to produce output for
    buffer_states : FIPS codes for surrounding states (gravity computation)
    coverage_area : "va" or "ncr"
    target_counties : if provided, restrict target BGs to these 5-digit
        county FIPS codes instead of entire states
    gtfs_year : override GTFS year (e.g. use 2017 for years before GTFS cache)

    Returns
    -------
    RunResult with output path and row count
    """
    from .transit_metrics import compute_all_transit_metrics
    from .variables import compute_all_variables
    from .regression import compute_ht_index

    t0 = time.time()

    try:
        # Step 1: Compute transit metrics (the novel/slow component)
        log.info("=== Step 1/4: Computing transit metrics for %d ===", year)
        transit_states = list(buffer_states[:4])  # VA + immediate neighbors
        transit_metrics = compute_all_transit_metrics(
            year, list(target_states), transit_states,
            target_counties=target_counties,
            gtfs_year=gtfs_year,
        )
        log.info("Transit metrics: %d BGs", len(transit_metrics))

        # Step 2: Compute all 17 independent variables
        log.info("=== Step 2/4: Computing independent variables ===")
        variables = compute_all_variables(
            year, list(target_states), list(buffer_states),
            transit_metrics=transit_metrics,
            target_counties=target_counties,
        )
        log.info("Variables: %d BGs × %d columns", *variables.shape)

        # Step 3: Apply regression model → H+T Index
        log.info("=== Step 3/4: Applying regression model ===")
        ht_results = compute_ht_index(variables, use_typical_household=True)

        # Step 4: Format and write output
        log.info("=== Step 4/4: Writing output ===")
        output = _format_output(ht_results, variables, year, coverage_area)

        # Write per-year file to working directory (intermediate)
        WORKING_DIR.mkdir(parents=True, exist_ok=True)
        years = [year]
        states = [{"51": "VA", "24": "MD", "11": "DC"}.get(s, s)
                  for s in target_states]
        auto_name = build_file_name(
            df=output,
            states=states,
            years=years,
            source_type="reproduced",
            title="affordability_ht_index",
        )
        filename = f"{auto_name}.csv.xz"
        out_path = write_data(
            output,
            WORKING_DIR / filename,
            census_standardize=True,
            measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,
        )
        log.info("Wrote %d rows to %s", len(output), out_path)

        return RunResult(
            success=True,
            rows=len(output),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )

    except Exception as e:
        log.error("Reproduction failed: %s", e, exc_info=True)
        return RunResult(
            success=False,
            error=str(e),
            duration_sec=time.time() - t0,
        )


def _format_output(
    ht_results: pd.DataFrame,
    variables: pd.DataFrame,
    year: int,
    coverage_area: str,
) -> pd.DataFrame:
    """Convert H+T results to standard SDC tall format.

    Produces multiple measures per BG:
    - affordability_index: the H+T Index (% of income)
    - housing_cost_pct: housing cost as % of income
    - transport_cost_pct: transportation cost as % of income
    - autos_per_hh: predicted autos per household
    - vmt_per_hh: predicted VMT per household
    - transit_frac: predicted fraction using transit
    """
    measures = {
        "affordability_index": "ht_index",
        "housing_cost_pct": "housing_cost_pct",
        "transport_cost_pct": "transport_cost_pct",
        "autos_per_hh": "autos_per_hh",
        "vmt_per_hh": "vmt_per_hh",
        "transit_frac": "transit_frac",
    }

    frames = []
    for measure_name, col in measures.items():
        df = pd.DataFrame({
            "geoid": ht_results["geoid"],
            "year": year,
            "measure": measure_name,
            "value": ht_results[col].round(2),
            "moe": pd.NA,
            "region_type": "block_group",
        })
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)

    # Filter to NCR if needed
    if coverage_area == "ncr":
        combined = combined[
            combined["geoid"].str[:5].isin(NCR_COUNTY_FIPS)
        ]

    # Aggregate to tract and county
    bg_data = combined.copy()
    tract_data = _aggregate_to_level(bg_data, "tract", 11)
    county_data = _aggregate_to_level(bg_data, "county", 5)

    return pd.concat([bg_data, tract_data, county_data], ignore_index=True)


def _aggregate_to_level(
    bg_data: pd.DataFrame,
    level_name: str,
    geoid_len: int,
) -> pd.DataFrame:
    """Aggregate BG-level data to a higher geography by mean."""
    agg = bg_data.copy()
    agg["geoid"] = agg["geoid"].str[:geoid_len]
    agg = (
        agg.groupby(["geoid", "year", "measure"])["value"]
        .mean()
        .reset_index()
    )
    agg["moe"] = pd.NA
    agg["region_type"] = level_name
    return agg


YEARS = list(range(2015, 2025))  # 2015-2024

# GTFS cache starts at 2017; use 2017 feeds as proxy for earlier years
GTFS_CACHE_START = 2017


def _resolve_gtfs_year(year: int) -> int | None:
    """Return GTFS year override, or None if exact year is available."""
    if year < GTFS_CACHE_START:
        return GTFS_CACHE_START
    return None


def run() -> list[RunResult]:
    """Run reproduction for all configured coverage areas and years."""
    results = []

    for year in YEARS:
        gtfs_yr = _resolve_gtfs_year(year)

        # VA reproduction
        log.info("===== Starting VA H+T Index Reproduction for %d =====", year)
        va_result = run_reproduction(
            year=year,
            target_states=["51"],
            buffer_states=["51", "24", "11", "54", "37", "21"],
            coverage_area="va",
            gtfs_year=gtfs_yr,
        )
        results.append(va_result)

        # NCR reproduction
        log.info("===== Starting NCR H+T Index Reproduction for %d =====", year)
        ncr_result = run_reproduction(
            year=year,
            target_states=["51", "24", "11"],
            buffer_states=["51", "24", "11", "54", "37", "21"],
            coverage_area="ncr",
            target_counties=NCR_COUNTY_FIPS,
            gtfs_year=gtfs_yr,
        )
        results.append(ncr_result)

    return results


if __name__ == "__main__":
    results = run()
    for r in results:
        if r.success:
            log.info("OK: %d rows → %s (%.1fs)", r.rows, r.output_path, r.duration_sec)
        else:
            log.error("FAIL: %s (%.1fs)", r.error, r.duration_sec)
    if any(not r.success for r in results):
        raise SystemExit(1)
