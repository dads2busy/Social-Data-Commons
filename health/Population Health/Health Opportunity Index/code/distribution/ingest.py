"""Ingest Health Opportunity Index indicators from VDH Excel files.

Data files must be manually downloaded and placed in data/original/:
  - Individual indicator Excel files from https://apps.vdh.virginia.gov/omhhe/hoi/
  - "HOI V3 14 Variables_For UVA.xlsx" (consolidated 2020 indicator data)
  - "hoi_indexes_quintile_2022.xlsx" (profile-level quintile data)

See pipeline.yaml for the complete list of expected files and column mappings.
"""

import time
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"
DATA_DIR = TOPIC_DIR / "data/original"

log = get_logger("health_opportunity_index.ingest")

# Quintile text label mappings (matching R code exactly)
QUINTILE_TEXT_MAP = {
    "Very Low": 1,
    "Low": 2,
    "Average": 3,
    "High": 4,
    "Very High": 5,
}

QUINTILE_TEXT_EXTENDED_MAP = {
    "Very Low Opportunity": 1,
    "Low Opportunity": 2,
    "Moderate Opportunity": 3,
    "High Opportunity": 4,
    "Very High Opportunity": 5,
}


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def _map_quintile_text(series: pd.Series, extended: bool = False) -> pd.Series:
    """Map quintile text labels to integers 1-5."""
    mapping = QUINTILE_TEXT_EXTENDED_MAP if extended else QUINTILE_TEXT_MAP
    return series.map(mapping).astype("Int64")


def _compute_quintile_bins(series: pd.Series, n: int = 5) -> pd.Series:
    """Replicate R fabricatr::split_quantile(x, 5).

    Assigns each value to a quintile bin (1-5) based on quantile breaks.
    Uses the full series (including NAs are dropped) to compute breaks.
    """
    valid = series.dropna()
    if valid.empty:
        return pd.Series(dtype="Int64")
    return pd.qcut(valid, q=n, labels=range(1, n + 1)).astype(int)


def _process_source(src: dict, data_dir: Path) -> pd.DataFrame:
    """Read a single source file and extract quintile values."""
    filepath = data_dir / src["file"]
    if not filepath.exists():
        log.warning("File not found: %s", filepath)
        return pd.DataFrame()

    df = pd.read_excel(filepath, sheet_name=0)
    geoid_col = src["geoid_col"]
    value_col = src["value_col"]

    if geoid_col not in df.columns:
        log.warning("Column '%s' not found in %s", geoid_col, filepath.name)
        return pd.DataFrame()
    if value_col not in df.columns:
        log.warning("Column '%s' not found in %s", value_col, filepath.name)
        return pd.DataFrame()

    result = pd.DataFrame()
    result["geoid"] = df[geoid_col].astype(str)

    value_type = src["value_type"]
    if value_type == "quintile_text":
        result["value"] = _map_quintile_text(df[value_col])
    elif value_type == "quintile_text_extended":
        result["value"] = _map_quintile_text(df[value_col], extended=True)
    elif value_type == "continuous_quintile":
        raw = pd.to_numeric(df[value_col], errors="coerce")
        # Compute quintile bins on the full column (matching R behavior)
        bins = _compute_quintile_bins(raw)
        result["value"] = pd.NA
        result.loc[raw.dropna().index, "value"] = bins.values
        result["value"] = result["value"].astype("Int64")
        if src.get("invert", False):
            result["value"] = abs(result["value"] - 6)
    else:
        log.warning("Unknown value_type '%s'", value_type)
        return pd.DataFrame()

    return result


def process_indicator(indicator_cfg: dict, data_dir: Path, fixup: dict) -> pd.DataFrame:
    """Process a single HOI indicator for all configured years."""
    measure_name = indicator_cfg["name"]
    records: list[pd.DataFrame] = []

    for year in indicator_cfg["years"]:
        source_key = f"source_{year}"
        src = indicator_cfg.get(source_key)
        if not src:
            log.warning("No source config for %s year %d", measure_name, year)
            continue

        result = _process_source(src, data_dir)
        if result.empty:
            continue

        result["year"] = year
        result["measure"] = measure_name
        result["moe"] = pd.NA
        result["region_type"] = "tract"

        # Bedford city tract fixup (applies to 2017 data)
        old_geoid = fixup.get("old_geoid")
        new_geoid = fixup.get("new_geoid")
        if old_geoid and new_geoid:
            result.loc[result["geoid"] == old_geoid, "geoid"] = new_geoid

        # Remove duplicates and NAs
        result = result.drop_duplicates(subset=["geoid", "year", "measure"])
        result = result.dropna(subset=["value"])
        records.append(result)

    if not records:
        return pd.DataFrame()
    return pd.concat(records, ignore_index=True)


def run() -> list[RunResult]:
    t0 = time.time()
    config = load_config()
    hoi_cfg = config["sources"]["va"]["vdh_hoi"]
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    try:
        indicators = hoi_cfg["indicators"]
        fixup = hoi_cfg.get("bedford_city_fixup", {})

        all_frames: list[pd.DataFrame] = []
        for ind_cfg in indicators:
            log.info("Processing indicator: %s", ind_cfg["name"])
            df = process_indicator(ind_cfg, DATA_DIR, fixup)
            if df.empty:
                log.warning("No data for indicator: %s", ind_cfg["name"])
            else:
                log.info("  %d rows", len(df))
                all_frames.append(df)

        if not all_frames:
            return [
                RunResult(
                    success=False,
                    error="No HOI indicator data ingested",
                    duration_sec=time.time() - t0,
                )
            ]

        combined = pd.concat(all_frames, ignore_index=True)
        combined = combined[
            ["geoid", "year", "measure", "value", "moe", "region_type"]
        ]

        auto_name = build_file_name(
            coverage_area="va",
            data_source="vdh",
            years=sorted(combined["year"].unique().tolist()),
            title="health_opportunity_index",
        )
        out_path = write_data(combined, DIST_DIR / f"{auto_name}.csv.xz")
        log.info("Wrote %d rows to %s", len(combined), out_path)

        return [
            RunResult(
                success=True,
                rows=len(combined),
                output_path=str(out_path),
                duration_sec=time.time() - t0,
            )
        ]
    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        return [
            RunResult(success=False, error=str(e), duration_sec=time.time() - t0)
        ]


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
