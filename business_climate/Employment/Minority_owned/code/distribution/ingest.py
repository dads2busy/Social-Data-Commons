"""Ingest Employment Minority owned metrics from Mergent Intellect."""

import sys
import time
from pathlib import Path

import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
MI_DIR = TOPIC_DIR.parents[1] / "Microdata" / "Mergent_intellect"
DIST_DIR = TOPIC_DIR / "data" / "distribution"

sys.path.insert(0, str(MI_DIR))
from mi_metrics import load_features, employment_dynamics, FEATURE_FILES

log = get_logger("employment.minority_owned.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def run() -> RunResult:
    t0 = time.time()
    config = load_config()
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    topic = config["topic"]
    total_rows = 0

    for prefix, src in config["sources"].items():
        feature_file = MI_DIR / "data" / "working" / src["feature_file"]
        features = load_features(feature_file)
        log.info("Loaded %s: %d rows", prefix, len(features))

        output, filename = employment_dynamics(features, topic, prefix)
        write_data(output, DIST_DIR / filename, census_standardize=False)
        log.info("Wrote %d rows to %s", len(output), filename)
        total_rows += len(output)

    return RunResult(success=True, rows=total_rows, duration_sec=time.time() - t0)


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
