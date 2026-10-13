"""Vintage from a LEHD LODES directory listing (html_years with a LODES default pattern)."""

from __future__ import annotations

import httpx

from sdc_core.sources.checks.compare import Observation
from sdc_core.sources.checks.probes import html_years
from sdc_core.sources.checks.probes._spec import ProbeSpec

DEFAULT_PATTERN = r"_(\d{4})\.csv\.gz"


def run(params: dict, client: httpx.Client) -> Observation:
    return html_years.run(
        {"url": params["url"], "pattern": params.get("pattern", DEFAULT_PATTERN)}, client
    )


def validate(params: dict) -> None:
    if "pattern" in params:
        html_years.validate(params)


SPEC = ProbeSpec(
    name="lodes_vintage",
    kind="vintage",
    required=frozenset({"url"}),
    optional=frozenset({"pattern"}),
    run=run,
    validate=validate,
)
