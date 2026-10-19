"""RDF output for Social Data Commons pipelines.

Maps long-format distribution files onto the RDF Data Cube vocabulary and
provides the shared namespaces, region IRIs and core ontology that pipeline-level
ontology extensions (e.g. energy facilities) build on.
"""

from .cube import add_measure, add_scenario, long_format_to_cube, measure_iri, scenario_iri
from .io import load_core_ontology, load_core_shapes, read_graph, read_turtle, write_graph, write_turtle
from .namespaces import GEO, SDC, SDCID, SDCM, bind_prefixes
from .regions import REGION_CLASSES, add_region, add_region_labels_from_geojson, region_iri

__all__ = [
    "GEO", "SDC", "SDCID", "SDCM", "REGION_CLASSES",
    "add_measure", "add_region", "add_region_labels_from_geojson", "add_scenario",
    "bind_prefixes", "load_core_ontology", "load_core_shapes", "long_format_to_cube",
    "measure_iri", "read_graph", "read_turtle", "region_iri", "scenario_iri", "write_graph",
    "write_turtle",
]
