"""Ingest the integrated 2030 VA residential-energy scenario.

Reads 4 source CSVs, computes 3 transforms (adoption measures, residential
load, PV generation) at both county and tract resolution, concatenates
to a single long-format CSV.

Run: uv run python energy/ResidentialEnergyScenario/code/distribution/ingest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger

THIS_DIR = Path(__file__).resolve().parent
TOPIC_DIR = THIS_DIR.parents[1]
REPO_DIR = TOPIC_DIR.parents[1]

sys.path.insert(0, str(THIS_DIR))
from transforms import (
    compute_adoption_measures,
    compute_pv_generation,
    compute_residential_load,
)

log = get_logger("residential_energy_scenario.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def verify_resstock_column_indexing(resstock: pd.DataFrame) -> None:
    """Sanity-check that `total_kwh_1` corresponds to hour 0 (overnight),
    not hour 1 or some other offset.

    Heuristic: the mean of total_kwh_1 (presumed midnight–1am) should be
    LOWER than the mean of total_kwh_19 (presumed 6–7pm peak). If that
    relationship doesn't hold, the indexing convention may be different —
    stop and surface the issue.
    """
    hour_0_mean = resstock["total_kwh_1"].mean()
    hour_18_mean = resstock["total_kwh_19"].mean()
    log.info(
        "ResStock indexing spot-check: total_kwh_1 mean=%.3f, total_kwh_19 mean=%.3f",
        hour_0_mean, hour_18_mean,
    )
    if hour_0_mean >= hour_18_mean:
        raise RuntimeError(
            "ResStock column indexing assumption appears wrong: "
            f"total_kwh_1 mean ({hour_0_mean:.3f}) >= total_kwh_19 mean ({hour_18_mean:.3f}). "
            "Expected hour-0 (overnight) load to be lower than hour-18 (evening peak). "
            "Inspect the data and adjust the column-to-hour mapping in transforms.py."
        )


def run() -> None:
    config = load_config()
    source = config["source"]
    out = config["output"]

    log.info("Reading source files")
    household = pd.read_csv(TOPIC_DIR / source["household_csv"])
    log.info("  household: %d rows", len(household))
    adoption = pd.read_csv(TOPIC_DIR / source["adoption_csv"])
    log.info("  adoption: %d rows", len(adoption))
    pv_profiles = pd.read_csv(TOPIC_DIR / source["pv_profiles_csv"])
    log.info("  pv_profiles: %d rows", len(pv_profiles))
    resstock = pd.read_csv(TOPIC_DIR / source["resstock_csv"])
    log.info("  resstock: %d rows", len(resstock))

    verify_resstock_column_indexing(resstock)

    pieces: list[pd.DataFrame] = []
    for resolution in config["resolutions"]:
        log.info("Computing transforms at %s resolution", resolution)
        pieces.append(compute_adoption_measures(
            household, adoption,
            region_type=resolution, scenario=source["scenario"],
        ))
        pieces.append(compute_residential_load(
            resstock, household,
            region_type=resolution, scenario=source["scenario"],
            scenario_year=source["scenario_year"],
        ))
        pieces.append(compute_pv_generation(
            pv_profiles, adoption, household,
            region_type=resolution, scenario=source["scenario"],
            scenario_year=source["scenario_year"],
        ))

    combined = pd.concat(pieces, ignore_index=True)
    log.info("Combined long-format: %d rows", len(combined))

    combined_csv = TOPIC_DIR / out["combined_csv"]
    combined_csv.parent.mkdir(parents=True, exist_ok=True)
    log.info("Writing → %s", combined_csv)
    write_data(combined, combined_csv, standardize=False, census_standardize=False)
    log.info("Done.")


if __name__ == "__main__":
    run()
