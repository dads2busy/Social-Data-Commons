"""Compute HOI composite index from 14 sub-indicator pipelines.

Applies the exact VDH methodology:
1. Collect 14 tract-level indicators for each year
2. Min-max normalize each indicator to [0,1] within each year
3. Invert indicators 6-13 so higher = better health opportunity
4. Apply PCA-derived weight matrix → 4 profile scores
5. Compute composite as weighted sum of profiles
6. Assign quintiles

Weight matrix reverse-engineered from VDH published data (see docs/composite_indices_methodology.md).
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd

from sdc_core.io import read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult
from sdc_core.versioning import update_version

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"

YEARS = list(range(2017, 2024))

log = get_logger("hoi.composite")

# The 14 indicators in VDH's column order.
# Each entry: (indicator_name, measure_name, file_glob_relative_to_repo, inverted)
INDICATORS = [
    (
        "access_to_care",
        "access_care_indicator_geo20",
        "health/Access to Care Index (HOI)/data/distribution/va_hdcttr_*access_care*.csv.xz",
        False,
    ),
    (
        "education",
        "average_years_schooling_geo20",
        "education/Years of Schooling/data/distribution/va_hdcttr_*years_of_schooling*.csv.xz",
        False,
    ),
    (
        "employment_access",
        "employment_access_index_geo20",
        "financial_well_being/Employment Access Index/data/distribution/va_hdcttr_*employment_access*.csv.xz",
        False,
    ),
    (
        "labor_force_participation",
        "labor_participate_rate_geo20",
        "financial_well_being/Employment Rates/data/distribution/va_hdcttr_*labor_participate_rate*.csv.xz",
        False,
    ),
    (
        "population_density",
        "population_density_geo20",
        "demographics/Population Density/data/distribution/va_hdcttr_*population_density*.csv.xz",
        False,
    ),
    (
        "walkability",
        "walkability_index_geo20",
        "transportation/Walkability/data/distribution/va_hdcttr_*walkability_index*.csv.xz",
        False,
    ),
    (
        "segregation",
        "segregation_indicator_geo20",
        "demographics/Segregation Index (HOI)/data/distribution/va_hdcttr_*segregation*.csv.xz",
        True,
    ),
    (
        "income_inequality",
        "gini_index_geo20",
        "financial_well_being/Income Inequality/data/distribution/va_hdcttr_*income_inequality*.csv.xz",
        True,
    ),
    (
        "affordability",
        "affordability_index",
        "housing/Cost/Affordability_HT/data/distribution/va_cttrbg_reproduced_all_years_affordability_ht_index.csv.xz",
        True,
    ),
    (
        "environmental_hazard",
        "environmental_hazard_index_geo20",
        "environment/Environmental Hazard Index (HOI)/data/distribution/va_hdcttr_*environmental_hazard*.csv.xz",
        True,
    ),
    (
        "food_access",
        "food_access_percentage_geo20",
        "food/Food Access/Food Accessibility Indicator (HOI)/data/distribution/va_hdcttr_*food_access*.csv.xz",
        True,
    ),
    (
        "material_deprivation",
        "material_deprivation_indicator_geo20",
        "financial_well_being/Material_Deprivation/data/distribution/va_hdcttr_*material_deprivation*.csv.xz",
        True,
    ),
    (
        "incarceration",
        "incarceration_rate_per_100000_geo20",
        "public_safety/Incarceration (HOI)/data/distribution/va_hdcttr_*incarceration_rate*.csv.xz",
        True,
    ),
    (
        "geographic_mobility",
        "perc_moving_geo20",
        "demographics/Geographic Mobility (HOI)/data/distribution/va_hdcttrbg_*geographic_mobility*.csv.xz",
        True,
    ),
]

# Weight matrix: 14 indicators × 4 profiles
# Rows = indicators (in order above), Columns = [Built Environment, Economic, Social Impact, Consumer]
WEIGHT_MATRIX = np.array([
    [ 0.126959, -0.569812,  0.877328, -0.369157],  # Access to Care
    [ 0.186815,  0.026156,  0.183904,  0.076218],  # Education
    [ 0.197667,  0.040961,  0.062257, -0.116375],  # Employment Access
    [-0.054056,  0.308118, -0.085525, -0.000987],  # Labor Force
    [ 0.117221,  0.153745,  0.030498, -0.382302],  # Pop Density
    [ 0.273904, -0.059131, -0.044121,  0.149943],  # Walkability
    [-0.227893,  0.029868,  0.182972, -0.220734],  # Segregation
    [-0.318781,  0.422138, -0.129801,  0.083492],  # Income Inequality
    [-0.008530,  0.099447, -0.100766, -0.217298],  # Affordability
    [-0.221318, -0.069300,  0.005989,  0.125674],  # Environmental
    [ 0.312486,  0.027708,  0.022635,  0.274875],  # Food Access
    [-0.052431,  0.066343,  0.093376,  0.273215],  # Material Deprivation
    [-0.021854,  0.149189,  0.141892,  0.085672],  # Incarceration
    [ 0.090131,  0.043833, -0.119968,  0.468253],  # Mobility
])

PROFILE_INTERCEPTS = np.array([0.501075, 0.212378, -0.186243, 0.193488])

PROFILE_NAMES = [
    "built_environment_profile",
    "economic_opportunity_profile",
    "social_impact_profile",
    "consumer_opportunity_profile",
]

# Composite = intercept + w1*BE + w2*Econ + w3*Social + w4*Consumer
COMPOSITE_INTERCEPT = -1.112348
COMPOSITE_WEIGHTS = np.array([0.557569, 0.741344, 0.895643, 0.561597])

QUINTILE_LABELS = [
    "Very Low Opportunity",
    "Low Opportunity",
    "Moderate Opportunity",
    "High Opportunity",
    "Very High Opportunity",
]


def load_indicator(indicator_name: str, measure_name: str, glob_pattern: str) -> pd.DataFrame:
    """Load a single indicator's tract-level data."""
    candidates = sorted(REPO_DIR.glob(glob_pattern))
    if not candidates:
        raise FileNotFoundError(f"No file found for {indicator_name}: {glob_pattern}")

    path = candidates[-1]  # Most recent by name
    log.info("Loading %s from %s", indicator_name, path.name)

    df = read_data(path)
    # Filter to tract level and target measure
    df = df[
        (df["region_type"] == "tract")
        & (df["measure"] == measure_name)
    ].copy()

    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df[["geoid", "year", "value"]].rename(columns={"value": indicator_name})

    log.info("  %d tract-year rows, years %s", len(df), sorted(df["year"].unique()))
    return df


def load_all_indicators() -> pd.DataFrame:
    """Load and merge all 14 indicators into a single wide DataFrame."""
    merged = None

    for indicator_name, measure_name, glob_pattern, _inverted in INDICATORS:
        df = load_indicator(indicator_name, measure_name, glob_pattern)

        if merged is None:
            merged = df
        else:
            merged = merged.merge(df, on=["geoid", "year"], how="inner")

    # Filter to target years
    merged = merged[merged["year"].isin(YEARS)].copy()

    indicator_names = [i[0] for i in INDICATORS]
    n_missing = merged[indicator_names].isna().sum()
    if n_missing.any():
        log.warning("Missing values per indicator:\n%s", n_missing[n_missing > 0])

    # Drop rows with any missing indicator (can't compute profiles with NaN)
    before = len(merged)
    merged = merged.dropna(subset=indicator_names).copy()
    if len(merged) < before:
        log.info("Dropped %d rows with missing indicator values", before - len(merged))

    log.info(
        "Merged: %d tract-year rows, %d tracts, years %s",
        len(merged), merged["geoid"].nunique(), sorted(merged["year"].unique()),
    )
    return merged


def normalize_and_invert(df: pd.DataFrame) -> pd.DataFrame:
    """Min-max normalize each indicator per year, then invert where needed."""
    indicator_names = [i[0] for i in INDICATORS]
    inverted = [i[3] for i in INDICATORS]

    result = df.copy()

    for year in sorted(result["year"].unique()):
        mask = result["year"] == year

        for name, invert in zip(indicator_names, inverted):
            col = result.loc[mask, name]
            col_min = col.min()
            col_max = col.max()

            if col_max > col_min:
                normalized = (col - col_min) / (col_max - col_min)
            else:
                normalized = pd.Series(0.5, index=col.index)

            if invert:
                normalized = 1.0 - normalized

            result.loc[mask, name] = normalized

        log.info("  Normalized year %d: %d tracts", year, mask.sum())

    return result


def compute_profiles_and_composite(df: pd.DataFrame) -> pd.DataFrame:
    """Apply weight matrix to get profiles, then compute composite."""
    indicator_names = [i[0] for i in INDICATORS]
    X = df[indicator_names].values  # (n_tracts, 14)

    # Compute 4 profile scores
    profiles = X @ WEIGHT_MATRIX + PROFILE_INTERCEPTS  # (n_tracts, 4)

    for i, name in enumerate(PROFILE_NAMES):
        df[name] = profiles[:, i]
        log.info(
            "  %s: mean=%.4f, range=[%.4f, %.4f]",
            name, profiles[:, i].mean(), profiles[:, i].min(), profiles[:, i].max(),
        )

    # Compute composite
    composite = COMPOSITE_INTERCEPT + profiles @ COMPOSITE_WEIGHTS
    df["health_opportunity_index"] = composite

    log.info(
        "  Composite: mean=%.4f, range=[%.4f, %.4f]",
        composite.mean(), composite.min(), composite.max(),
    )

    # Assign quintiles per year
    df["hoi_quintile"] = ""
    for year in sorted(df["year"].unique()):
        mask = df["year"] == year
        values = df.loc[mask, "health_opportunity_index"]
        # Use pandas qcut for equal-count quintiles
        quintiles = pd.qcut(values, 5, labels=QUINTILE_LABELS)
        df.loc[mask, "hoi_quintile"] = quintiles

    return df


def reshape_to_long(df: pd.DataFrame) -> pd.DataFrame:
    """Reshape wide profile + composite data to long format for output."""
    measures = PROFILE_NAMES + ["health_opportunity_index"]
    frames = []

    for measure in measures:
        subset = df[["geoid", "year", measure]].copy()
        subset = subset.rename(columns={measure: "value"})
        subset["measure"] = measure + "_geo20"
        subset["moe"] = pd.NA
        subset["region_type"] = "tract"
        frames.append(subset)

    return pd.concat(frames, ignore_index=True)


def run() -> RunResult:
    t0 = time.time()
    try:
        log.info("=== Loading all 14 indicators ===")
        wide = load_all_indicators()

        log.info("=== Normalizing and inverting ===")
        wide = normalize_and_invert(wide)

        log.info("=== Computing profiles and composite ===")
        wide = compute_profiles_and_composite(wide)

        log.info("=== Reshaping to long format ===")
        long = reshape_to_long(wide)
        long = long.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)
        long["value"] = long["value"].round(6)

        log.info("Final: %d rows", len(long))

        # Write output
        DIST_DIR.mkdir(parents=True, exist_ok=True)
        out_name = build_file_name(
            coverage_area="va",
            data_source="computed",
            years=sorted(long["year"].unique().tolist()),
            title="health_opportunity_index",
            geographies=["tract"],
        )
        out_path = write_data(long, DIST_DIR / f"{out_name}.csv.xz")
        log.info("Wrote %s", out_path)

        # Also write the wide-format file for analysis
        wide_cols = ["geoid", "year"] + PROFILE_NAMES + ["health_opportunity_index", "hoi_quintile"]
        wide_path = DIST_DIR / "va_tract_hoi_profiles_wide.csv.xz"
        wide[wide_cols].to_csv(wide_path, index=False)
        log.info("Wrote wide format: %s", wide_path)

        update_version(TOPIC_DIR)

        return RunResult(
            success=True,
            rows=len(long),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Composite computation failed: %s", e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
