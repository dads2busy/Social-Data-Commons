"""Ingest Employment Access Index from H+T Affordability Index (CNT).

Reads pre-downloaded CSV files from data/original/, extracts the emp_gravity
measure, interpolates missing years (2016-2018) between 2015 and 2019, and
extrapolates 2021 from the 2019-2020 rate of change. Writes long-format
.csv.xz to data/distribution/.

Data source: https://htaindex.cnt.org/download/
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"

log = get_logger("employment_access.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def read_ht_file(path: Path, geo_col: str) -> pd.DataFrame:
    """Read an H+T Index CSV and extract geoid + emp_gravity."""
    df = pd.read_csv(path, dtype=str)
    # H+T files have values wrapped in double quotes — strip them
    for col in df.columns:
        df[col] = df[col].str.strip('"')
    df = df[[geo_col, "emp_gravity"]].copy()
    df = df.rename(columns={geo_col: "geoid"})
    df["geoid"] = df["geoid"].str.strip()
    df["value"] = pd.to_numeric(df["emp_gravity"], errors="coerce")
    df = df[["geoid", "value"]].dropna(subset=["value"])
    return df


def load_observed_data(config: dict) -> pd.DataFrame:
    """Load all observed (non-interpolated) years from original CSV files."""
    src = config["sources"]["va"]
    files = src["original_files"]
    frames = []

    file_keys = {"tract": "tracts", "county": "counties"}
    for geo_level, geo_col in [("tract", "tract"), ("county", "county")]:
        for year_str, rel_path in files[file_keys[geo_level]].items():
            year = int(year_str)
            path = TOPIC_DIR / rel_path
            if not path.exists():
                log.warning("Missing file: %s", path)
                continue
            df = read_ht_file(path, geo_col)
            df["year"] = year
            df["region_type"] = geo_level
            frames.append(df)
            log.info("Loaded %d rows from %s (year=%d, %s)", len(df), path.name, year, geo_level)

    return pd.concat(frames, ignore_index=True)


def interpolate_years(observed: pd.DataFrame) -> pd.DataFrame:
    """Linearly interpolate values for 2016-2018 between 2015 and 2019."""
    # Work per (geoid, region_type) group using 2015 and 2019 endpoints
    d15 = observed[observed["year"] == 2015][["geoid", "region_type", "value"]].rename(columns={"value": "v15"})
    d19 = observed[observed["year"] == 2019][["geoid", "region_type", "value"]].rename(columns={"value": "v19"})

    merged = d15.merge(d19, on=["geoid", "region_type"], how="inner")

    frames = []
    for year in [2016, 2017, 2018]:
        frac = (year - 2015) / (2019 - 2015)
        row = merged.copy()
        row["year"] = year
        row["value"] = row["v15"] + frac * (row["v19"] - row["v15"])
        frames.append(row[["geoid", "region_type", "year", "value"]])

    return pd.concat(frames, ignore_index=True)


def extrapolate_year(observed: pd.DataFrame, target_year: int = 2021) -> pd.DataFrame:
    """Extrapolate target_year from the 2019-2020 rate of change."""
    d19 = observed[observed["year"] == 2019][["geoid", "region_type", "value"]].rename(columns={"value": "v19"})
    d20 = observed[observed["year"] == 2020][["geoid", "region_type", "value"]].rename(columns={"value": "v20"})

    merged = d19.merge(d20, on=["geoid", "region_type"], how="inner")
    merged["rate"] = merged["v20"] - merged["v19"]  # per-year rate (1-year gap)
    merged["year"] = target_year
    merged["value"] = merged["v20"] + merged["rate"] * (target_year - 2020)

    return merged[["geoid", "region_type", "year", "value"]].dropna(subset=["value"])


def run() -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        DIST_DIR.mkdir(parents=True, exist_ok=True)

        observed = load_observed_data(config)
        if observed.empty:
            return RunResult(success=False, error="No data loaded from original files", duration_sec=time.time() - t0)

        interpolated = interpolate_years(observed)
        extrapolated = extrapolate_year(observed, target_year=2021)

        combined = pd.concat([observed, interpolated, extrapolated], ignore_index=True)
        combined["measure"] = "employment_access_index"
        combined["moe"] = pd.NA
        combined = combined[["geoid", "year", "measure", "value", "moe", "region_type"]]
        combined = combined.sort_values(["geoid", "year"]).reset_index(drop=True)

        log.info("Total rows: %d (observed=%d, interpolated=%d, extrapolated=%d)",
                 len(combined), len(observed), len(interpolated), len(extrapolated))

        filename = build_file_name(
            coverage_area="va", data_source="mixed", years=config["sources"]["va"]["years"],
            title="employment_access", geographies=["county", "tract"],
        ) + ".csv.xz"

        out_path = write_data(combined, DIST_DIR / filename, census_standardize=True)
        log.info("Wrote %d rows to %s", len(combined), out_path)

        return RunResult(success=True, rows=len(combined), output_path=str(out_path), duration_sec=time.time() - t0)

    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
