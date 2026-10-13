"""Newest vintage of a Census API dataset, from the api.census.gov/data.json catalog."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from sdc_core.sources.checks.compare import Observation
from sdc_core.sources.checks.probes._http import ProbeError, request_with_retry
from sdc_core.sources.checks.probes._spec import ProbeSpec

DATA_JSON_URL = "https://api.census.gov/data.json"
CATALOG_TIMEOUT = 120.0  # the catalog is tens of MB


def max_vintage(catalog: dict, dataset: str) -> int | None:
    want = dataset.strip("/").split("/")
    vintages = [
        entry["c_vintage"]
        for entry in catalog.get("dataset", [])
        if entry.get("c_dataset") == want and isinstance(entry.get("c_vintage"), int)
    ]
    return max(vintages) if vintages else None


def run(params: dict, client: httpx.Client) -> Observation:
    resp = request_with_retry(client, "GET", DATA_JSON_URL, timeout=CATALOG_TIMEOUT)
    year = max_vintage(resp.json(), params["dataset"])
    if year is None:
        raise ProbeError(f"dataset {params['dataset']!r} not found in {DATA_JSON_URL}")
    return Observation("vintage", year, datetime.now(timezone.utc), "api.census.gov/data.json")


SPEC = ProbeSpec(
    name="census_vintage",
    kind="vintage",
    required=frozenset({"dataset"}),
    optional=frozenset(),
    run=run,
)
