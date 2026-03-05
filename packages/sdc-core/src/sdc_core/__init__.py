"""sdc-core: Shared framework for Social Data Commons dataset pipelines."""

__version__ = "0.1.0"

from sdc_core.census import CensusClient
from sdc_core.geo import (
    aggregate_to_geographies,
    aggregate_up,
    aggregate_with_crosswalk,
    convert_2010_to_2020_bounds,
    create_crosswalk,
    get_2010_2020_bound_changes,
    infer_region_type,
    infer_region_types,
    standardize_all,
)
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import (
    DEFAULT_COVERAGE_MAP,
    REGION_TYPE_ABBR,
    RESOLUTION_ORDER,
    TableNameParts,
    build_file_name,
    infer_coverage_area_from_states,
    infer_data_source,
    infer_resolution_from_df,
    infer_resolution_from_geographies,
    infer_resolution_from_region_types,
    infer_time_period_from_years,
)
from sdc_core.pipeline import load_pipeline
from sdc_core.profiles import register_profile, resolve_profile, resolve_states
from sdc_core.result import RunResult
from sdc_core.versioning import (
    BumpResult,
    Manifest,
    VersionResult,
    detect_bump,
    generate_manifest,
    load_manifest,
    update_version,
)
from sdc_core.zenodo import ZenodoResult, upload_to_zenodo

__all__ = [
    "CensusClient",
    "RunResult",
    "aggregate_to_geographies",
    "aggregate_up",
    "aggregate_with_crosswalk",
    "convert_2010_to_2020_bounds",
    "create_crosswalk",
    "get_2010_2020_bound_changes",
    "infer_region_type",
    "infer_region_types",
    "standardize_all",
    "data_reformat_for_site",
    "get_logger",
    "load_pipeline",
    "read_data",
    "register_profile",
    "resolve_profile",
    "resolve_states",
    "write_data",
    "build_file_name",
    "infer_coverage_area_from_states",
    "infer_time_period_from_years",
    "infer_data_source",
    "infer_resolution_from_df",
    "infer_resolution_from_geographies",
    "infer_resolution_from_region_types",
    "RESOLUTION_ORDER",
    "REGION_TYPE_ABBR",
    "DEFAULT_COVERAGE_MAP",
    "TableNameParts",
    "BumpResult",
    "Manifest",
    "VersionResult",
    "detect_bump",
    "generate_manifest",
    "load_manifest",
    "update_version",
    "ZenodoResult",
    "upload_to_zenodo",
]
