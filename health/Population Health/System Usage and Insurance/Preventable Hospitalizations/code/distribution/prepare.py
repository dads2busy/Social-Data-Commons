"""Prepare preventable hospitalizations from County Health Rankings.

Steps:
1. Download CHR Excel files for configured years (Ranked Measure Data sheet)
2. Extract preventable hospitalization rate column (name varies by year)
3. Convert 2015-2018 values from per 1k to per 100k
4. Write long-format VA distribution file to data/distribution/
5. Aggregate county -> health district using simple mean
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
from sdc_core.result import RunResult
from sdc_core.sources.chr import ingest_chr

TOPIC_DIR = Path(__file__).resolve().parents[2]


def _find_repo_root() -> Path:
    p = TOPIC_DIR
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    raise FileNotFoundError("Could not find repo root (pyproject.toml)")


REPO_DIR = _find_repo_root()
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("preventable_hospitalizations.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def run() -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        source_cfg = config["sources"]["va"]
        crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]

        log.info("Ingesting preventable hospitalizations from CHR")
        df = ingest_chr(
            source_cfg["county_health_rankings"],
            working_dir=TOPIC_DIR / "data" / "working",
            state_fips_prefix="51",
        )

        # Exclude state-level row (51000) — only want counties
        df = df[df["geoid"] != "51000"].copy()

        if df.empty:
            return RunResult(
                success=False,
                error="No data ingested",
                duration_sec=time.time() - t0,
            )

        # 2015-2018 values are per 1,000; convert to per 100,000
        mask = df["year"].isin([2015, 2016, 2017, 2018])
        df.loc[mask, "value"] = df.loc[mask, "value"] * 100

        auto_name = build_file_name(
            coverage_area="va",
            data_source=source_cfg.get("type"),
            years=sorted(df["year"].unique().tolist()),
            title="preventable_hospitalizations",
        )
        out_path = write_data(df, DIST_DIR / f"{auto_name}.csv.xz")
        log.info("Wrote %d rows to %s", len(df), out_path)

        # Aggregate county -> health district
        df_dist = read_data(out_path)
        counties = df_dist[df_dist["region_type"] == "county"].copy()
        xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})

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

        combined = pd.concat([counties, hd], ignore_index=True)
        combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(
            drop=True
        )
        combined_path = write_data(combined, out_path)
        log.info(
            "Wrote %d rows (with health districts) to %s", len(combined), combined_path
        )

        # Reformat for VA dashboard
        measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None
        paths = data_reformat_for_site(
            source_path=combined_path,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county"],
            coverage_area="va",
            data_source="county_health_rankings",
            title="preventable_hospitalizations",
            measure_info_path=measure_info,
        )
        for p in paths:
            log.info("Wrote %s", p)

        return RunResult(
            success=True,
            rows=len(combined),
            output_path=str(combined_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Prepare failed: %s", e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
