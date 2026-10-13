import httpx
import pytest

from sdc_core.sources.checks.probes import PROBES
from sdc_core.sources.checks.probes._http import ProbeError, make_client
from sdc_core.sources.checks.probes.bea_vintage import max_year_from_params

PARAMS = {"dataset": "Regional", "table": "CAINC4"}


def test_spec():
    spec = PROBES["bea_vintage"]
    assert spec.kind == "vintage"
    assert spec.required == {"dataset", "table"}


@pytest.mark.parametrize(
    "payload, expected",
    [
        (
            {"BEAAPI": {"Results": {"ParamValue": [{"Key": "2022", "Desc": "2022"}, {"Key": "2024", "Desc": "2024"}]}}},
            2024,
        ),
        (
            {"BEAAPI": {"Results": {"ParamValue": {"TableName": "CAINC4", "FirstYear": "1969", "LastYear": "2023"}}}},
            2023,
        ),
        ({"BEAAPI": {"Results": {"ParamValue": []}}}, None),
        ({}, None),
    ],
)
def test_max_year_from_params(payload, expected):
    assert max_year_from_params(payload) == expected


def test_missing_api_key_is_probe_error(monkeypatch):
    monkeypatch.delenv("BEA_API_KEY", raising=False)
    client = make_client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    with pytest.raises(ProbeError, match="BEA_API_KEY"):
        PROBES["bea_vintage"].run(PARAMS, client)


def test_run_sends_expected_query(monkeypatch):
    monkeypatch.setenv("BEA_API_KEY", "k123")
    seen = {}

    def handler(request):
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"BEAAPI": {"Results": {"ParamValue": [{"Key": "2024"}]}}})

    obs = PROBES["bea_vintage"].run(PARAMS, make_client(transport=httpx.MockTransport(handler)))
    assert obs.value == 2024
    assert seen["UserID"] == "k123"
    assert seen["method"] == "GetParameterValuesFiltered"
    assert seen["datasetname"] == "Regional"
    assert seen["TargetParameter"] == "Year"
    assert seen["TableName"] == "CAINC4"
    assert obs.detail == "apps.bea.gov Regional/CAINC4 Year values"


def test_bea_error_payload_is_probe_error(monkeypatch):
    monkeypatch.setenv("BEA_API_KEY", "k123")
    payload = {
        "BEAAPI": {
            "Results": {"Error": {"APIErrorCode": "3", "APIErrorDescription": "Invalid API UserId"}}
        }
    }
    client = make_client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    with pytest.raises(ProbeError, match="Invalid API UserId"):
        PROBES["bea_vintage"].run(PARAMS, client)
