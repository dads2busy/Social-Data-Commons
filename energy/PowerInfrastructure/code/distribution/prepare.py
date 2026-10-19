"""Prepare PowerInfrastructure outputs for the va_energy_data dashboard."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml
from rdflib import Graph
from sdc_core.io import export_point_layer, write_data, write_point_data
from sdc_core.log import get_logger
from sdc_rdf import (
    add_region_labels_from_geojson,
    assert_same_csv_rows,
    cube_to_long_format,
    dataset_iri,
    read_csv_exact,
    read_graph,
    stage_vocabulary,
    write_graph,
)
from to_rdf import build_graph, points_from_graph

THIS_DIR = Path(__file__).resolve().parent
TOPIC_DIR = THIS_DIR.parents[1]
REPO_DIR = TOPIC_DIR.parents[1]
DASHBOARD_DIR = REPO_DIR / "dashboard_data" / "va_energy_data"
ENERGY_RDF_DIR = TOPIC_DIR.parent / "rdf"
ONTOLOGY = ENERGY_RDF_DIR / "ontology.ttl"
MEASURE_INFO = TOPIC_DIR / "measure_info.json"

log = get_logger("power_infrastructure.prepare")


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

    # The graph is the source: build it, then stage the dashboard CSVs from it.
    graph_path = write_rdf(config, point_csv, county_csv)
    staged_point, staged_county = stage_from_graph(graph_path, point_csv, county_csv)

    log.info("Writing point GeoJSON via export_point_layer")
    geojson_path = export_point_layer(
        source_path=staged_point,
        output_dir=DASHBOARD_DIR,
        coverage_area=source["coverage_area"],
        data_source=source["data_source_token"],
        title="power_infrastructure",
    )
    log.info("Wrote %s", geojson_path)

    log.info("Done.")


def write_rdf(config: dict, point_csv: Path, county_csv: Path) -> Path:
    """Write the county cube + facility graph and stage it for the dashboard."""
    out = config["output"]
    source = config["source"]
    graph, unknown = build_graph(
        read_csv_exact(point_csv),
        read_csv_exact(county_csv),
        ontology=Graph().parse(ONTOLOGY),
        measure_info=json.loads(MEASURE_INFO.read_text()),
        county_dataset_id=county_csv.name.removesuffix(".csv.xz"),
        layer_urls=[layer["url"].removesuffix("/query") for layer in source["layers"].values()],
        null_sentinel=source["null_sentinel"],
    )
    add_region_labels_from_geojson(graph, REPO_DIR / config["geographies"]["va_counties"], "county")
    if unknown:
        log.warning("Codes not declared in energy/rdf/ontology.ttl: %s", sorted(unknown))

    graph_path = write_graph(graph, TOPIC_DIR / out["rdf_graph"])
    log.info("Wrote %s (%d triples)", graph_path, len(graph))
    shutil.copy2(graph_path, DASHBOARD_DIR / graph_path.name)
    stage_vocabulary(DASHBOARD_DIR / "vocabulary", {
        "sdc-energy.ttl": ENERGY_RDF_DIR / "ontology.ttl",
        "sdc-energy-shapes.ttl": ENERGY_RDF_DIR / "shapes.ttl",
    })
    return graph_path


def stage_from_graph(graph_path: Path, point_csv: Path, county_csv: Path) -> tuple[Path, Path]:
    """Write the dashboard CSVs from the published graph, not the distribution CSVs.

    Each is checked row for row against the distribution CSV it must reproduce,
    so a lossy graph fails the run instead of reaching the dashboard.
    """
    graph = read_graph(graph_path)
    staged_point = write_point_data(points_from_graph(graph), DASHBOARD_DIR / point_csv.name)
    staged_county = write_data(
        cube_to_long_format(graph, dataset_iri(county_csv.name.removesuffix(".csv.xz"))),
        DASHBOARD_DIR / county_csv.name,
        standardize=False,
        census_standardize=False,
    )
    assert_same_csv_rows(staged_point, point_csv)
    assert_same_csv_rows(staged_county, county_csv)
    log.info("Staged %s and %s from %s", staged_point.name, staged_county.name, graph_path.name)
    return staged_point, staged_county


if __name__ == "__main__":
    run()
