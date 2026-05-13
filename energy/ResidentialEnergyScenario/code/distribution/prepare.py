"""Prepare ResidentialEnergyScenario outputs for the va_energy_data dashboard.

This pipeline emits only a long-format combined CSV (county + tract resolutions
in one file). No point output.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.log import get_logger

THIS_DIR = Path(__file__).resolve().parent
TOPIC_DIR = THIS_DIR.parents[1]
REPO_DIR = TOPIC_DIR.parents[1]
DASHBOARD_DIR = REPO_DIR / "dashboard_data" / "va_energy_data"

log = get_logger("residential_energy_scenario.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def run() -> None:
    config = load_config()
    out = config["output"]

    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

    combined_csv = TOPIC_DIR / out["combined_csv"]

    log.info("Copying %s → %s", combined_csv.name, DASHBOARD_DIR)
    shutil.copy2(combined_csv, DASHBOARD_DIR / combined_csv.name)

    # Union our scenario into scenarios.json so the dashboard's scenario list
    # includes residential alongside any data-center-projected scenarios.
    scenarios_path = DASHBOARD_DIR / "scenarios.json"
    if scenarios_path.exists():
        with open(scenarios_path) as f:
            existing = set(json.load(f))
    else:
        existing = set()

    combined_df = pd.read_csv(combined_csv)
    new_scenarios = set(combined_df["scenario"].dropna().unique())
    combined = sorted(existing | new_scenarios)

    log.info("Writing scenarios.json (%d unique scenarios)", len(combined))
    with open(scenarios_path, "w") as f:
        json.dump(combined, f, indent=2)

    log.info("Done.")


if __name__ == "__main__":
    run()
