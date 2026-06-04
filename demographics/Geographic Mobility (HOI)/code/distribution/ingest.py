"""Ingest geographic mobility (HOI) data from ACS.

Configuration is read from Geographic Mobility (HOI)/pipeline.yaml.
"""

import time
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.census import CensusClient
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.profiles import resolve_states
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"
log = get_logger("geographic_mobility_hoi.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def compute_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Compute geographic mobility measures: counts and percent moving."""
    df = df.copy()
    df["geo_mobility_total_count"] = df["total_pop"]
    df["geo_mobility_moving_count"] = df["pop_moving"]
    df["perc_moving"] = 100 * df["pop_moving"] / df["total_pop"]

    id_cols = ["geoid", "year", "region_type"]
    measure_cols = ["geo_mobility_total_count", "geo_mobility_moving_count", "perc_moving"]
    long = df[id_cols + measure_cols].melt(
        id_vars=id_cols,
        var_name="measure",
        value_name="value",
    )
    long["moe"] = pd.NA
    return long.dropna(subset=["value"])


def run_source(name: str, src: dict, out_dir: Path, standardize: bool) -> RunResult:
    t0 = time.time()
    try:
        log.info("Ingesting source '%s' (profile=%s)", name, src.get("profile"))

        client = CensusClient()
        df = client.get_acs_multi(
            variables=src["variables"],
            years=src["years"],
            geographies=src["geographies"],
            profile=src.get("profile"),
            states=src.get("states"),
            cache_dir=TOPIC_DIR / "data/working/acs_cache",
        )
        log.info("Fetched %d raw rows for '%s'", len(df), name)

        result = compute_measures(df)

        states = resolve_states(src)
        auto_name = build_file_name(
            df=result,
            states=states,
            years=src.get("years"),
            source_type=src.get("type"),
            title="geographic_mobility_hoi",
        )
        filename = f"{auto_name}.csv.xz"
        out_path = write_data(
            result,
            out_dir / filename,
            census_standardize=standardize,
            measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,
        )
        log.info("Wrote %d rows to %s", len(result), out_path)

        return RunResult(
            success=True,
            rows=len(result),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error(
            "Geographic mobility (HOI) ingest failed for source '%s': %s",
            name,
            e,
            exc_info=True,
        )
        return RunResult(
            success=False,
            error=str(e),
            duration_sec=time.time() - t0,
        )


def run() -> list[RunResult]:
    config = load_config()
    out_dir = TOPIC_DIR / config["output"]["path"]
    standardize = config["output"].get("standardize", False)

    sources = config.get("sources")
    if sources is None:
        sources = {"default": config["source"]}

    results = []
    for name, src in sources.items():
        results.append(run_source(name, src, out_dir, standardize))
    return results


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
