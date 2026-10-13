"""Content fingerprint of a single URL: ETag, else Last-Modified, else SHA-256."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import httpx

from sdc_core.sources.checks.compare import Observation
from sdc_core.sources.checks.probes._http import ProbeError, request_with_retry
from sdc_core.sources.checks.probes._spec import ProbeSpec


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run(params: dict, client: httpx.Client) -> Observation:
    url = params["url"]
    try:
        head = request_with_retry(client, "HEAD", url)
    except ProbeError:
        head = None  # e.g. 405 Method Not Allowed; fall through to GET
    if head is not None:
        etag = head.headers.get("ETag")
        if etag:
            return Observation("content", etag, _now(), "ETag")
        last_modified = head.headers.get("Last-Modified")
        if last_modified:
            return Observation("content", last_modified, _now(), "Last-Modified")

    digest = hashlib.sha256()
    try:
        with client.stream("GET", url) as resp:
            if resp.status_code >= 400:
                raise ProbeError(f"HTTP {resp.status_code} from {url}")
            for chunk in resp.iter_bytes():
                digest.update(chunk)
    except httpx.TransportError as exc:
        raise ProbeError(f"{exc!r} fetching {url}") from exc
    return Observation("content", digest.hexdigest(), _now(), "SHA-256")


SPEC = ProbeSpec(
    name="http_file",
    kind="content",
    required=frozenset({"url"}),
    optional=frozenset(),
    run=run,
)
