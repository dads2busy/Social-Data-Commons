"""Prepare DataCentersProjected outputs for the va_energy_data dashboard."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.io import export_point_layer
from sdc_core.log import get_logger
from sdc_rdf import add_region_labels_from_geojson, read_csv_exact, write_graph
from to_rdf import build_graph

THIS_DIR = Path(__file__).resolve().parent
TOPIC_DIR = THIS_DIR.parents[1]
REPO_DIR = TOPIC_DIR.parents[1]
DASHBOARD_DIR = REPO_DIR / "dashboard_data" / "va_energy_data"
MEASURE_INFO = TOPIC_DIR / "measure_info.json"

log = get_logger("data_centers_projected.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def run() -> None:
    config = load_config()
    out = config["output"]
    source = config["source"]

    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

    point_csv = TOPIC_DIR / out["point_csv"]
    county_csv = TOPIC_DIR / out["county_csv"]

    log.info("Copying %s → %s", point_csv.name, DASHBOARD_DIR)
    shutil.copy2(point_csv, DASHBOARD_DIR / point_csv.name)
    log.info("Copying %s → %s", county_csv.name, DASHBOARD_DIR)
    shutil.copy2(county_csv, DASHBOARD_DIR / county_csv.name)

    log.info("Writing point GeoJSON via export_point_layer")
    geojson_path = export_point_layer(
        source_path=point_csv,
        output_dir=DASHBOARD_DIR,
        coverage_area=source["coverage_area"],
        data_source=source["data_source_token"],
        title="data_centers_projected",
    )
    log.info("Wrote %s", geojson_path)

    # Update / create scenarios.json — a list of unique scenario labels across
    # all pipelines, used by the dashboard's scenario selector.
    scenarios_path = DASHBOARD_DIR / "scenarios.json"
    if scenarios_path.exists():
        with open(scenarios_path) as f:
            existing = set(json.load(f))
    else:
        existing = set()

    county_df = pd.read_csv(county_csv)
    new_scenarios = set(county_df["scenario"].unique())
    combined = sorted(existing | new_scenarios)

    log.info("Writing scenarios.json (%d unique scenarios)", len(combined))
    with open(scenarios_path, "w") as f:
        json.dump(combined, f, indent=2)

    write_rdf(config, point_csv, county_csv)
    log.info("Done.")


def write_rdf(config: dict, point_csv: Path, county_csv: Path) -> Path:
    """Write the county cube + projected-site graph and stage it for the dashboard."""
    graph = build_graph(
        read_csv_exact(point_csv),
        read_csv_exact(county_csv),
        measure_info=json.loads(MEASURE_INFO.read_text()),
        county_dataset_id=county_csv.name.removesuffix(".csv.xz"),
        default_scenario=config["source"]["scenario_canonical"],
    )
    add_region_labels_from_geojson(graph, REPO_DIR / config["geographies"]["va_counties"], "county")
    graph_path = write_graph(graph, TOPIC_DIR / config["output"]["rdf_graph"])
    log.info("Wrote %s (%d triples)", graph_path, len(graph))
    shutil.copy2(graph_path, DASHBOARD_DIR / graph_path.name)
    return graph_path


if __name__ == "__main__":
    run()
