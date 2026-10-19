"""Prepare EVChargingStations outputs for the va_energy_data dashboard.

Copies the point and county-aggregated CSVs from data/distribution/ into
dashboard_data/va_energy_data/, and writes a GeoJSON of the point CSV via
sdc_core.io.export_point_layer for the dashboard's map overlay.

No update_version() — energy data is not yet ready to publish.

Run: uv run python energy/EVChargingStations/code/distribution/prepare.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml
from rdflib import Graph
from sdc_core.io import export_point_layer, read_data, read_point_data
from sdc_core.log import get_logger
from sdc_rdf import add_region_labels_from_geojson, write_graph
from to_rdf import build_graph

THIS_DIR = Path(__file__).resolve().parent
TOPIC_DIR = THIS_DIR.parents[1]
REPO_DIR = TOPIC_DIR.parents[1]
DASHBOARD_DIR = REPO_DIR / "dashboard_data" / "va_energy_data"
ONTOLOGY = TOPIC_DIR.parent / "rdf" / "ontology.ttl"
MEASURE_INFO = TOPIC_DIR / "measure_info.json"

log = get_logger("ev_charging_stations.prepare")


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
        title=f"{source['scenario']}_ev_charging_stations",
    )
    log.info("Wrote %s", geojson_path)

    write_rdf(config, point_csv, county_csv)
    log.info("Done.")


def write_rdf(config: dict, point_csv: Path, county_csv: Path) -> Path:
    """Write the county cube + station graph and stage it for the dashboard."""
    graph, unknown = build_graph(
        read_point_data(point_csv),
        read_data(county_csv),
        ontology=Graph().parse(ONTOLOGY),
        measure_info=json.loads(MEASURE_INFO.read_text()),
        county_dataset_id=county_csv.name.removesuffix(".csv.xz"),
        description=config["description"],
    )
    add_region_labels_from_geojson(graph, REPO_DIR / config["geographies"]["va_counties"], "county")
    if unknown:
        log.warning("Charger levels not declared in energy/rdf/ontology.ttl: %s", sorted(unknown))

    graph_path = write_graph(graph, TOPIC_DIR / config["output"]["rdf_graph"])
    log.info("Wrote %s (%d triples)", graph_path, len(graph))
    shutil.copy2(graph_path, DASHBOARD_DIR / graph_path.name)
    return graph_path


if __name__ == "__main__":
    run()
