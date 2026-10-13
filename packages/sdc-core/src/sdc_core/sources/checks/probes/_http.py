"""Shared HTTP client and retry policy for probes."""

from __future__ import annotations

import httpx

DEFAULT_TIMEOUT = 30.0
USER_AGENT = "sdc-sources-check/1.0 (+https://github.com/dads2busy/Social-Data-Commons)"


class ProbeError(Exception):
    """A probe could not produce an observation. Becomes an `error` row."""


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
        transport=transport,
    )


def request_with_retry(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    """One retry on transport error or 5xx. 4xx raises immediately."""
    last: Exception | None = None
    for _attempt in range(2):
        try:
            resp = client.request(method, url, **kwargs)
        except httpx.TransportError as exc:
            last = exc
            continue
        if resp.status_code >= 500:
            last = ProbeError(f"HTTP {resp.status_code} from {url}")
            continue
        if resp.status_code >= 400:
            raise ProbeError(f"HTTP {resp.status_code} from {url}")
        return resp
    raise ProbeError(f"{last} after retry")
