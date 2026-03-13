"""Ingest school funding adequacy from County Health Rankings.

Downloads CHR Excel files for configured years, extracts the school funding
adequacy column, and writes long-format VA distribution file.
"""

import time
from pathlib import Path

import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult
from sdc_core.sources.chr import ingest_chr

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"

log = get_logger("school_funding_adequacy.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def run() -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        source_cfg = config["sources"]["va"]

        log.info("Ingesting school funding adequacy from CHR")
        df = ingest_chr(
            source_cfg["county_health_rankings"],
            working_dir=TOPIC_DIR / "data" / "working",
            state_fips_prefix="51",
        )

        if df.empty:
            return RunResult(
                success=False,
                error="No data ingested",
                duration_sec=time.time() - t0,
            )

        DIST_DIR.mkdir(parents=True, exist_ok=True)
        auto_name = build_file_name(
            coverage_area="va",
            data_source=source_cfg.get("type"),
            years=sorted(df["year"].unique().tolist()),
            title="school_funding_adequacy",
        )
        out_path = write_data(df, DIST_DIR / f"{auto_name}.csv.xz")
        log.info("Wrote %d rows to %s", len(df), out_path)

        return RunResult(
            success=True,
            rows=len(df),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


if __name__ == "__main__":
    results = [run()]
    if any(not r.success for r in results):
        raise SystemExit(1)
