"""Prepare ResidentialEnergyScenario outputs for the va_energy_data dashboard.

This pipeline emits only a long-format combined CSV (county + tract resolutions
in one file). No point output. The dashboard copy is staged from the RDF graph
and verified row for row against the distribution CSV.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_rdf import (
    add_region_labels_from_geojson,
    assert_same_csv_rows,
    read_csv_exact,
    read_graph,
    stage_vocabulary,
    write_graph,
)
from to_rdf import build_graph, long_format_from_graph

THIS_DIR = Path(__file__).resolve().parent
TOPIC_DIR = THIS_DIR.parents[1]
REPO_DIR = TOPIC_DIR.parents[1]
DASHBOARD_DIR = REPO_DIR / "dashboard_data" / "va_energy_data"
ENERGY_RDF_DIR = TOPIC_DIR.parent / "rdf"
MEASURE_INFO = TOPIC_DIR / "measure_info.json"

log = get_logger("residential_energy_scenario.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def run() -> None:
    config = load_config()
    out = config["output"]

    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

    combined_csv = TOPIC_DIR / out["combined_csv"]

    # The graph is the source: build it, then stage the dashboard CSV from it.
    graph_path = write_rdf(config, combined_csv)
    staged_csv = stage_from_graph(graph_path, combined_csv)

    # Union our scenario into scenarios.json so the dashboard's scenario list
    # includes residential alongside any data-center-projected scenarios.
    scenarios_path = DASHBOARD_DIR / "scenarios.json"
    if scenarios_path.exists():
        with open(scenarios_path) as f:
            existing = set(json.load(f))
    else:
        existing = set()

    combined_df = pd.read_csv(staged_csv)
    new_scenarios = set(combined_df["scenario"].dropna().unique())
    combined = sorted(existing | new_scenarios)

    log.info("Writing scenarios.json (%d unique scenarios)", len(combined))
    with open(scenarios_path, "w") as f:
        json.dump(combined, f, indent=2)

    log.info("Done.")


def write_rdf(config: dict, combined_csv: Path) -> Path:
    """Write the static + hourly county/tract graph and stage it for the dashboard."""
    geos = config["geographies"]
    graph = build_graph(
        read_csv_exact(combined_csv),
        measure_info=json.loads(MEASURE_INFO.read_text()),
        dataset_stem=combined_csv.name.removesuffix(".csv.xz"),
        tract_vintage=geos.get("tract_vintage"),
        description=config["description"],
    )
    add_region_labels_from_geojson(graph, REPO_DIR / geos["va_counties"], "county")
    add_region_labels_from_geojson(
        graph, REPO_DIR / geos["va_tracts"], "tract", vintage=geos.get("tract_vintage")
    )

    graph_path = write_graph(graph, TOPIC_DIR / config["output"]["rdf_graph"])
    log.info("Wrote %s (%d triples)", graph_path, len(graph))
    shutil.copy2(graph_path, DASHBOARD_DIR / graph_path.name)
    stage_vocabulary(DASHBOARD_DIR / "vocabulary", {
        "sdc-energy.ttl": ENERGY_RDF_DIR / "ontology.ttl",
        "sdc-energy-shapes.ttl": ENERGY_RDF_DIR / "shapes.ttl",
    })
    return graph_path


def stage_from_graph(graph_path: Path, combined_csv: Path) -> Path:
    """Write the dashboard CSV from the published graph, not the distribution CSV.

    It is checked row for row against the distribution CSV it must reproduce, so
    a lossy graph fails the run instead of reaching the dashboard.
    """
    graph = read_graph(graph_path)
    staged = write_data(
        long_format_from_graph(graph, combined_csv.name.removesuffix(".csv.xz")),
        DASHBOARD_DIR / combined_csv.name,
        standardize=False,
        census_standardize=False,
    )
    assert_same_csv_rows(staged, combined_csv)
    log.info("Staged %s from %s", staged.name, graph_path.name)
    return staged


if __name__ == "__main__":
    run()
