"""Ingest ALICE and poverty rate data from United for ALICE Virginia State Data Sheet.

Downloads the Excel file, computes alice_pct (ALICE households / total) and
poverty_pct (poverty households / total), and writes county-level long format.

The Excel file is downloaded fresh on each run — no caching. Years available
depend on the file's content (currently 2010–2021).
"""

import io
import time
from pathlib import Path

import httpx
import pandas as pd
import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"

log = get_logger("alice.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def fetch_alice(src: dict) -> pd.DataFrame:
    """Download the United for ALICE Virginia Excel file and return a cleaned DataFrame.

    Columns returned: geoid, year, total_households, alice_households,
    poverty_households.
    """
    log.info("Downloading ALICE data from %s", src["url"])
    resp = httpx.get(src["url"], follow_redirects=True, timeout=60)
    resp.raise_for_status()

    df = pd.read_excel(io.BytesIO(resp.content), sheet_name=src["sheet"])

    col_map = {
        "GEO.id2": "geoid",
        "Year": "year",
        "Households": "total_households",
        "ALICE Households": "alice_households",
        "Poverty Households": "poverty_households",
    }
    df = df[list(col_map.keys())].rename(columns=col_map)

    # Ensure geoid is a zero-padded 5-character string (FIPS)
    df["geoid"] = df["geoid"].astype(int).apply(lambda x: str(x).zfill(5))

    # Drop rows where total_households is zero to avoid division-by-zero
    df = df[df["total_households"] != 0].copy()

    log.info("Fetched %d rows (%d years)", len(df), df["year"].nunique())
    return df


def compute_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Compute alice_pct and poverty_pct and melt to long format.

    Returns columns: geoid, year, measure, value, moe, region_type.
    """
    df = df.copy()
    df["alice_pct"] = (df["alice_households"] / df["total_households"] * 100).round(4)
    df["poverty_pct"] = (df["poverty_households"] / df["total_households"] * 100).round(4)

    long = df[["geoid", "year", "alice_pct", "poverty_pct"]].melt(
        id_vars=["geoid", "year"],
        var_name="measure",
        value_name="value",
    )
    long["moe"] = pd.NA
    long["region_type"] = "county"

    long = long.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)
    return long[["geoid", "year", "measure", "value", "moe", "region_type"]]


def run() -> list[RunResult]:
    t0 = time.time()
    try:
        config = load_config()
        src = config["sources"]["va"]

        raw = fetch_alice(src)
        result = compute_measures(raw)

        auto_name = build_file_name(
            df=result,
            states=["VA"],
            years=sorted(result["year"].unique().tolist()),
            source_type="alice",
            title="alice",
        )
        DIST_DIR.mkdir(parents=True, exist_ok=True)
        out_path = write_data(result, DIST_DIR / f"{auto_name}.csv.xz", census_standardize=False)
        log.info("Wrote %d rows to %s", len(result), out_path)

        return [
            RunResult(
                success=True,
                rows=len(result),
                output_path=str(out_path),
                duration_sec=time.time() - t0,
            )
        ]
    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        return [RunResult(success=False, error=str(e), duration_sec=time.time() - t0)]


if __name__ == "__main__":
    results = run()
    if not all(r.success for r in results):
        raise SystemExit(1)
