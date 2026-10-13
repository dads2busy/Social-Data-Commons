import httpx

from sdc_core.sources.checks.probes import PROBES
from sdc_core.sources.checks.probes._http import make_client


def test_manual_registered():
    spec = PROBES["manual"]
    assert spec.kind == "manual"
    assert spec.required == {"url"}
    assert spec.optional == {"note"}


def test_manual_never_calls_network():
    def boom(request):  # pragma: no cover - would fail the test if called
        raise AssertionError("manual probe must not hit the network")

    client = make_client(transport=httpx.MockTransport(boom))
    obs = PROBES["manual"].run({"url": "https://x.example/page"}, client)
    assert obs.kind == "manual"
    assert obs.value is None
    assert obs.detail == "https://x.example/page"


def test_manual_appends_note():
    client = make_client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    obs = PROBES["manual"].run({"url": "https://x.example", "note": "look at tab 2"}, client)
    assert obs.detail == "https://x.example | look at tab 2"
