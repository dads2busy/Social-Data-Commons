"""Newest year a BEA Regional table offers, via GetParameterValuesFiltered."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone

import httpx

from sdc_core.sources.checks.compare import Observation
from sdc_core.sources.checks.probes._http import ProbeError, request_with_retry
from sdc_core.sources.checks.probes._spec import ProbeSpec

BEA_URL = "https://apps.bea.gov/api/data/"
_YEAR = re.compile(r"\b(19\d{2}|20\d{2})\b")


def max_year_from_params(payload: dict) -> int | None:
    values = payload.get("BEAAPI", {}).get("Results", {}).get("ParamValue", [])
    if isinstance(values, dict):
        values = [values]
    years: list[int] = []
    for item in values:
        for v in item.values():
            years.extend(int(y) for y in _YEAR.findall(str(v)))
    return max(years) if years else None


def run(params: dict, client: httpx.Client) -> Observation:
    key = os.environ.get("BEA_API_KEY", "")
    if not key:
        raise ProbeError("BEA_API_KEY environment variable is not set")
    query = {
        "UserID": key,
        "method": "GetParameterValuesFiltered",
        "datasetname": params["dataset"],
        "TargetParameter": "Year",
        "TableName": params["table"],
        "ResultFormat": "json",
    }
    resp = request_with_retry(client, "GET", BEA_URL, params=query)
    payload = resp.json()
    error = payload.get("BEAAPI", {}).get("Results", {}).get("Error")
    if error:
        raise ProbeError(f"BEA API error: {error.get('APIErrorDescription', error)}")
    year = max_year_from_params(payload)
    if year is None:
        raise ProbeError(f"no Year values returned for {params['dataset']}/{params['table']}")
    detail = f"apps.bea.gov {params['dataset']}/{params['table']} Year values"
    return Observation("vintage", year, datetime.now(timezone.utc), detail)


SPEC = ProbeSpec(
    name="bea_vintage",
    kind="vintage",
    required=frozenset({"dataset", "table"}),
    optional=frozenset(),
    run=run,
)
