"""Prepare drug overdose ED visits for dashboard sites."""

from pathlib import Path

import pandas as pd
import yaml
from sdc_core.geo import aggregate_with_crosswalk
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name

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

log = get_logger("drug_overdose_ed_visits.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path) -> Path | None:
    # Match ingest output (county-only), not prepare output (adds HD)
    candidates = sorted(
        p for p in dist_dir.glob("va_*vdh_*drug_overdose*.csv.xz")
        if "hdct" not in p.name
    )
    return candidates[-1] if candidates else None


def run() -> None:
    config = load_config()
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    va_source = find_source(DIST_DIR)
    if not va_source:
        raise FileNotFoundError(
            f"No drug overdose ingest output found in {DIST_DIR}. Run ingest.py first."
        )

    log.info("Reading ingest output: %s", va_source)
    df = read_data(va_source)

    # Aggregate county -> health district using simple mean
    counties = df[df["region_type"] == "county"].copy()
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

    filename = (
        build_file_name(
            coverage_area="va",
            data_source="vdh",
            years=combined["year"].unique().tolist(),
            title="drug_overdose_ed_visits",
            geographies=["health_district", "county"],
        )
        + ".csv.xz"
    )
    out_path = write_data(combined, DIST_DIR / filename)
    log.info("Wrote %d rows to %s", len(combined), out_path)

    # Reformat for VA dashboard
    for p in data_reformat_for_site(
        source_path=out_path,
        output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
        levels=["health_district", "county"],
        coverage_area="va",
        data_source="vdh",
        title="drug_overdose_ed_visits",
        measure_info_path=measure_info,
    ):
        log.info("Wrote %s", p)


if __name__ == "__main__":
    run()
