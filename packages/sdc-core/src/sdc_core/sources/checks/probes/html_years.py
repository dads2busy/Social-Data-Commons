"""Vintage from a web page: the largest plausible year a one-group regex captures."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from sdc_core.sources.checks.compare import Observation
from sdc_core.sources.checks.probes._http import ProbeError, request_with_retry
from sdc_core.sources.checks.probes._spec import ProbeSpec

YEAR_MIN, YEAR_MAX = 1900, 2100


def extract_max_year(text: str, pattern: str) -> int | None:
    years: list[int] = []
    for match in re.findall(pattern, text):
        try:
            year = int(match)
        except (TypeError, ValueError):
            continue
        if YEAR_MIN <= year <= YEAR_MAX:
            years.append(year)
    return max(years) if years else None


def validate(params: dict) -> None:
    try:
        compiled = re.compile(params["pattern"])
    except re.error as exc:
        raise ValueError(f"pattern is not a valid regex: {exc}") from exc
    if compiled.groups != 1:
        raise ValueError("pattern must contain exactly one capture group (the year)")


def run(params: dict, client: httpx.Client) -> Observation:
    url, pattern = params["url"], params["pattern"]
    resp = request_with_retry(client, "GET", url)
    year = extract_max_year(resp.text, pattern)
    if year is None:
        raise ProbeError(f"no year matched {pattern!r} at {url}")
    return Observation("vintage", year, datetime.now(timezone.utc), url)


SPEC = ProbeSpec(
    name="html_years",
    kind="vintage",
    required=frozenset({"url", "pattern"}),
    optional=frozenset(),
    run=run,
    validate=validate,
)
