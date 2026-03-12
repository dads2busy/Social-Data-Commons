"""Ingest USDA Food Access Research Atlas data for Virginia.

Replaces: code/distribution/prepare_fara.Rmd, code/working/prepare_fara.Rmd

Steps:
1. Read FARA 2015 & 2019 Excel files from data/original/
2. Filter to Virginia census tracts
3. Extract food access metric: lalowi1share (fallback to lalowihalfshare, then 0)
4. Convert 2010 Census tract IDs to 2020 using area-weighted crosswalk
5. Linearly interpolate values for 2016-2018
6. Linearly extrapolate values for 2020-2023 using 2015-2019 trend
7. Write tract-level output to data/distribution/
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
ORIG_DIR = TOPIC_DIR / "data/original"
DIST_DIR = TOPIC_DIR / "data/distribution"

FARA_FILES = {
    2015: "FoodAccessResearchAtlasData2015.xlsx",
    2019: "FoodAccessResearchAtlasData2019.xlsx",
}
CROSSWALK_FILE = ORIG_DIR / "crosswalk_tracts.csv"
SHEET_NAME = "Food Access Research Atlas"
STATE_FILTER = "Virginia"
MEASURE_NAME = "food_access_percentage"

# Years to produce via interpolation between 2015 and 2019
INTERPOLATION_YEARS = [2016, 2017, 2018]
# Years to produce via extrapolation beyond 2019 (no newer FARA edition exists)
EXTRAPOLATION_YEARS = [2020, 2021, 2022, 2023]

log = get_logger("food_access.ingest")


def read_fara(year: int) -> pd.DataFrame:
    """Read a FARA Excel file and extract Virginia food access percentages.

    Uses lalowi1share (% low-income pop >1mi from supermarket) as the primary
    metric. Falls back to lalowihalfshare if 1mi is missing. Remaining NAs → 0.
    """
    path = ORIG_DIR / FARA_FILES[year]
    log.info("Reading FARA %d: %s", year, path.name)

    df = pd.read_excel(path, sheet_name=SHEET_NAME, dtype={"CensusTract": str})
    df = df[df["State"] == STATE_FILTER].copy()
    log.info("  Virginia tracts: %d", len(df))

    # 2015 file uses POP2010 (uppercase), 2019 uses Pop2010
    pop_col = "POP2010" if "POP2010" in df.columns else "Pop2010"

    # Extract food access metric with fallback chain
    val = df["lalowi1share"].astype(float)
    fallback = df["lalowihalfshare"].astype(float)
    val = val.where(val.notna(), fallback)
    val = val.fillna(0.0)

    # 2015 FARA stores shares as proportions (0-1); 2019 stores as percentages (0-100)
    if val.max() <= 1.0:
        log.info("  Detected proportions (0-1), converting to percentages")
        val = val * 100.0

    result = pd.DataFrame({
        "geoid_2010": df["CensusTract"].values,
        "value": val.values,
        "pop2010": df[pop_col].astype(float).values,
    })

    log.info("  Food access: mean=%.2f%%, range=[%.2f, %.2f]",
             result["value"].mean(), result["value"].min(), result["value"].max())
    return result


def load_crosswalk() -> pd.DataFrame:
    """Load the Census 2010→2020 tract relationship file.

    Returns columns: geoid_2010, geoid_2020, arealand_2020, arealand_part
    The crosswalk handles three cases:
    - same: tract boundaries unchanged (pass value through)
    - split: 2010 tract split into multiple 2020 tracts (replicate value)
    - moved: boundaries changed (area-weighted redistribution)
    """
    log.info("Loading tract crosswalk: %s", CROSSWALK_FILE.name)

    df = pd.read_csv(
        CROSSWALK_FILE,
        sep="|",
        dtype={"GEOID_TRACT_20": str, "GEOID_TRACT_10": str},
    )

    xwalk = df[["GEOID_TRACT_20", "GEOID_TRACT_10",
                "AREALAND_TRACT_20", "AREALAND_PART"]].copy()
    xwalk.columns = ["geoid_2020", "geoid_2010", "arealand_2020", "arealand_part"]

    # Filter to Virginia (FIPS 51)
    xwalk = xwalk[xwalk["geoid_2010"].str.startswith("51")].copy()
    log.info("  VA crosswalk rows: %d", len(xwalk))
    return xwalk


def convert_tracts_2010_to_2020(df: pd.DataFrame, xwalk: pd.DataFrame) -> pd.DataFrame:
    """Convert 2010 tract data to 2020 boundaries using area-weighted crosswalk.

    For tracts that split or shifted boundaries, the value is weighted by the
    fraction of the 2020 tract's land area that came from each 2010 tract.
    """
    # Compute overlap weight: what fraction of the 2020 tract came from this 2010 tract
    xwalk = xwalk.copy()
    xwalk["weight"] = xwalk["arealand_part"] / xwalk["arealand_2020"]
    xwalk.loc[xwalk["weight"] > 1.0, "weight"] = 1.0  # cap rounding errors

    merged = xwalk.merge(df, on="geoid_2010", how="inner")
    merged["weighted_value"] = merged["value"] * merged["weight"]

    # Sum weighted contributions for each 2020 tract
    result = (
        merged.groupby("geoid_2020")
        .agg(value=("weighted_value", "sum"))
        .reset_index()
        .rename(columns={"geoid_2020": "geoid"})
    )

    log.info("  Converted %d 2010-tracts → %d 2020-tracts", len(df), len(result))
    return result


def interpolate_extrapolate(
    df_2015: pd.DataFrame, df_2019: pd.DataFrame, years: list[int]
) -> pd.DataFrame:
    """Linearly interpolate/extrapolate food access values using the 2015-2019 trend."""
    merged = df_2015.merge(
        df_2019, on="geoid", how="outer", suffixes=("_2015", "_2019")
    )
    # Fill missing with the other year's value (tracts that only appear in one edition)
    merged["value_2015"] = merged["value_2015"].fillna(merged["value_2019"])
    merged["value_2019"] = merged["value_2019"].fillna(merged["value_2015"])

    slope = (merged["value_2019"] - merged["value_2015"]) / 4.0

    interp_set = set(INTERPOLATION_YEARS)
    frames = []
    for year in years:
        years_since = year - 2015
        row = merged[["geoid"]].copy()
        row["value"] = merged["value_2015"] + slope * years_since
        row["year"] = year
        row["data_method"] = "interpolated" if year in interp_set else "extrapolated"
        frames.append(row)

    result = pd.concat(frames, ignore_index=True)
    log.info("Interpolated/extrapolated %d tract-year rows for years %s", len(result), years)
    return result


def to_long_format(df: pd.DataFrame) -> pd.DataFrame:
    """Convert to standard long format: geoid, year, measure, value, moe, region_type, data_method."""
    out = df[["geoid", "year", "value", "data_method"]].copy()
    out["measure"] = MEASURE_NAME
    out["moe"] = pd.NA
    out["region_type"] = "tract"
    return out[["geoid", "year", "measure", "value", "moe", "region_type", "data_method"]]


def run() -> RunResult:
    t0 = time.time()
    try:
        # Read FARA source files
        raw_2015 = read_fara(2015)
        raw_2019 = read_fara(2019)

        # Load crosswalk and convert to 2020 boundaries
        xwalk = load_crosswalk()
        df_2015 = convert_tracts_2010_to_2020(raw_2015, xwalk)
        df_2019 = convert_tracts_2010_to_2020(raw_2019, xwalk)

        # Tag source years
        df_2015["year"] = 2015
        df_2015["data_method"] = "observed"
        df_2019["year"] = 2019
        df_2019["data_method"] = "observed"

        # Interpolate intermediate years + extrapolate beyond 2019
        derived = interpolate_extrapolate(
            df_2015, df_2019, INTERPOLATION_YEARS + EXTRAPOLATION_YEARS
        )

        # Combine all years
        cols = ["geoid", "year", "value", "data_method"]
        all_years = pd.concat(
            [df_2015[cols], derived[cols], df_2019[cols]],
            ignore_index=True,
        )

        # Clip negative values from interpolation
        all_years["value"] = all_years["value"].clip(lower=0.0)

        # Convert to long format
        long = to_long_format(all_years)
        long = long.sort_values(["geoid", "year"]).reset_index(drop=True)

        log.info(
            "Final: %d rows, %d tracts, years %s",
            len(long),
            long["geoid"].nunique(),
            sorted(long["year"].unique()),
        )

        # Write output
        DIST_DIR.mkdir(parents=True, exist_ok=True)
        out_name = build_file_name(
            coverage_area="va",
            data_source="usda",
            years=sorted(long["year"].unique().tolist()),
            title="food_access",
            geographies=["tract"],
        )
        out_path = write_data(long, DIST_DIR / f"{out_name}.csv.xz", census_standardize=True)
        log.info("Wrote %s", out_path)

        return RunResult(
            success=True,
            rows=len(long),
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
