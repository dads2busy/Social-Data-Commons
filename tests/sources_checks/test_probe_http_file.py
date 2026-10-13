import hashlib

import httpx
import pytest

from sdc_core.sources.checks.probes import PROBES
from sdc_core.sources.checks.probes._http import ProbeError, make_client, request_with_retry

URL = "https://files.example/data.xlsx"


def client_with(handler):
    return make_client(transport=httpx.MockTransport(handler))


def test_spec():
    spec = PROBES["http_file"]
    assert spec.kind == "content"
    assert spec.required == {"url"}
    assert spec.optional == frozenset()


def test_etag_preferred():
    def handler(request):
        assert request.method == "HEAD"
        return httpx.Response(
            200, headers={"ETag": 'W/"abc"', "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT"}
        )

    obs = PROBES["http_file"].run({"url": URL}, client_with(handler))
    assert (obs.kind, obs.value, obs.detail) == ("content", 'W/"abc"', "ETag")


def test_last_modified_fallback():
    def handler(request):
        return httpx.Response(200, headers={"Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT"})

    obs = PROBES["http_file"].run({"url": URL}, client_with(handler))
    assert (obs.value, obs.detail) == ("Mon, 01 Jan 2024 00:00:00 GMT", "Last-Modified")


def test_sha256_fallback_when_no_headers():
    body = b"hello world"

    def handler(request):
        if request.method == "HEAD":
            return httpx.Response(200)
        return httpx.Response(200, content=body)

    obs = PROBES["http_file"].run({"url": URL}, client_with(handler))
    assert obs.detail == "SHA-256"
    assert obs.value == hashlib.sha256(body).hexdigest()


def test_head_405_falls_back_to_get():
    body = b"payload"

    def handler(request):
        if request.method == "HEAD":
            return httpx.Response(405)
        return httpx.Response(200, content=body)

    obs = PROBES["http_file"].run({"url": URL}, client_with(handler))
    assert obs.value == hashlib.sha256(body).hexdigest()


def test_redirect_followed():
    def handler(request):
        if request.url.path == "/old":
            return httpx.Response(302, headers={"Location": "https://files.example/new"})
        return httpx.Response(200, headers={"ETag": '"final"'})

    obs = PROBES["http_file"].run({"url": "https://files.example/old"}, client_with(handler))
    assert obs.value == '"final"'


def test_404_is_probe_error():
    def handler(request):
        return httpx.Response(404)

    with pytest.raises(ProbeError):
        PROBES["http_file"].run({"url": URL}, client_with(handler))


def test_retry_once_on_5xx_then_succeed():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, headers={"ETag": '"ok"'})

    resp = request_with_retry(client_with(handler), "HEAD", URL)
    assert resp.status_code == 200
    assert calls["n"] == 2


def test_retry_once_on_5xx_then_fail():
    def handler(request):
        return httpx.Response(503)

    with pytest.raises(ProbeError, match="503"):
        request_with_retry(client_with(handler), "GET", URL)


def test_retry_on_transport_error():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200)

    assert request_with_retry(client_with(handler), "GET", URL).status_code == 200


def test_4xx_fails_immediately():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(403)

    with pytest.raises(ProbeError, match="403"):
        request_with_retry(client_with(handler), "GET", URL)
    assert calls["n"] == 1


def test_get_fallback_retries_once_on_5xx():
    body = b"payload"
    calls = {"GET": 0}

    def handler(request):
        if request.method == "HEAD":
            return httpx.Response(200)  # no ETag / Last-Modified
        calls["GET"] += 1
        if calls["GET"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, content=body)

    obs = PROBES["http_file"].run({"url": URL}, client_with(handler))
    assert obs.value == hashlib.sha256(body).hexdigest()
    assert calls["GET"] == 2
