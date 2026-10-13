"""No-network probe: tells a human where to look."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from sdc_core.sources.checks.compare import Observation
from sdc_core.sources.checks.probes._spec import ProbeSpec


def run(params: dict, client: httpx.Client) -> Observation:
    detail = params["url"]
    if params.get("note"):
        detail = f"{detail} | {params['note']}"
    return Observation(kind="manual", value=None, fetched_at=datetime.now(timezone.utc), detail=detail)


SPEC = ProbeSpec(
    name="manual",
    kind="manual",
    required=frozenset({"url"}),
    optional=frozenset({"note"}),
    run=run,
)
