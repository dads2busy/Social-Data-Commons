"""RDF output for Social Data Commons pipelines.

Maps long-format distribution files onto the RDF Data Cube vocabulary and
provides the shared namespaces, region IRIs and core ontology that pipeline-level
ontology extensions (e.g. energy facilities) build on.
"""

from .cube import (
    add_measure,
    add_scenario,
    cube_to_long_format,
    dataset_iri,
    long_format_to_cube,
    measure_iri,
    scenario_iri,
)
from .io import (
    assert_same_csv_rows,
    csv_rows,
    load_core_ontology,
    load_core_shapes,
    read_csv_exact,
    read_graph,
    write_graph,
)
from .namespaces import GEO, SDC, SDCID, SDCM, bind_prefixes
from .points import (
    add_point_geometry,
    decimal_literal,
    integer_literal,
    is_missing,
    number_value,
    point_lat_lon,
    ref_year,
    year_literal,
)
from .regions import REGION_CLASSES, add_region, add_region_labels_from_geojson, region_iri

__all__ = [
    "GEO", "SDC", "SDCID", "SDCM", "REGION_CLASSES",
    "add_measure", "add_region", "assert_same_csv_rows", "csv_rows", "dataset_iri", "add_region_labels_from_geojson", "add_scenario",
    "bind_prefixes", "cube_to_long_format", "load_core_ontology", "load_core_shapes",
    "long_format_to_cube",
    "add_point_geometry", "decimal_literal", "integer_literal", "is_missing", "number_value",
    "point_lat_lon", "ref_year", "year_literal",
    "measure_iri", "read_csv_exact", "read_graph", "region_iri", "scenario_iri", "write_graph",
]
