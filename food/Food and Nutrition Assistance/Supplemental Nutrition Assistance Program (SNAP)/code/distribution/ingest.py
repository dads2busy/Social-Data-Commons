"""Ingest ACS data: households receiving SNAP (B22010).

Fetches B22010_001 (total households) and B22010_002 (households receiving SNAP)
for VA, MD, and DC, computes count, percent, and population measures, and writes
one long-format .csv.xz per coverage area to data/distribution/.
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
DIST_DIR = TOPIC_DIR / "data/distribution"

log = get_logger("snap.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def compute_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Compute SNAP count, percent, and population; melt to long format."""
    cnt = df["hh_snap"]
    pop = df["total_hh"]
    pct = (cnt / pop * 100).where(pop.gt(0), other=0.0)

    id_cols = ["geoid", "year", "region_type"]
    rows = []
    for measure, val in [
        ("hh_received_snap_cnt", cnt),
        ("hh_received_snap_pct", pct),
        ("population", pop),
    ]:
        part = df[id_cols].copy()
        part["measure"] = measure
        part["value"] = val
        part["moe"] = pd.NA
        rows.append(part)

    return pd.concat(rows, ignore_index=True)


def run_source(
    name: str, src: dict, out_dir: Path, client: CensusClient
) -> RunResult:
    t0 = time.time()
    try:
        log.info("Ingesting source '%s'", name)
        df = client.get_acs_multi(
            variables=src["variables"],
            years=src["years"],
            geographies=src["geographies"],
            profile=src.get("profile"),
            states=src.get("states"),
            estimate_only=True,
        )
        if df.empty:
            return RunResult(
                success=False,
                error=f"No data for '{name}'",
                duration_sec=time.time() - t0,
            )

        result = compute_measures(df)

        states = resolve_states(src)
        auto_name = build_file_name(
            df=result,
            states=states,
            years=src.get("years"),
            source_type=src.get("type"),
            title="hh_receiving_snap",
        )
        out_path = write_data(result, out_dir / f"{auto_name}.csv.xz")
        log.info("Wrote %d rows to %s", len(result), out_path)

        return RunResult(
            success=True,
            rows=len(result),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Ingest failed for '%s': %s", name, e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


def run() -> list[RunResult]:
    config = load_config()
    out_dir = DIST_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    client = CensusClient()

    results = []
    for name, src in config["sources"].items():
        results.append(run_source(name, src, out_dir, client))
    return results


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
