import json

import httpx
import pytest

from sdc_core.sources.checks.probes import PROBES
from sdc_core.sources.checks.probes._http import ProbeError, make_client
from sdc_core.sources.checks.probes.census_vintage import DATA_JSON_URL, max_vintage

CATALOG = {
    "dataset": [
        {"c_dataset": ["acs", "acs5"], "c_vintage": 2022, "title": "ACS 5-Year 2022"},
        {"c_dataset": ["acs", "acs5"], "c_vintage": 2024, "title": "ACS 5-Year 2024"},
        {"c_dataset": ["acs", "acs5", "profile"], "c_vintage": 2025, "title": "profile, must not match"},
        {"c_dataset": ["acs", "acs1"], "c_vintage": 2026, "title": "acs1, must not match"},
        {"c_dataset": ["timeseries", "eits"], "title": "no c_vintage, must be ignored"},
        {"c_dataset": ["acs", "acs5"], "c_vintage": "not-an-int"},
    ]
}


def test_max_vintage_exact_dataset_match():
    assert max_vintage(CATALOG, "acs/acs5") == 2024
    assert max_vintage(CATALOG, "acs/acs5/profile") == 2025
    assert max_vintage(CATALOG, "dec/pl") is None
    assert max_vintage({}, "acs/acs5") is None


def test_run_hits_data_json_and_returns_vintage():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, content=json.dumps(CATALOG).encode())

    spec = PROBES["census_vintage"]
    assert spec.kind == "vintage" and spec.required == {"dataset"}
    obs = spec.run({"dataset": "acs/acs5"}, make_client(transport=httpx.MockTransport(handler)))
    assert seen["url"] == DATA_JSON_URL
    assert (obs.value, obs.detail) == (2024, "api.census.gov/data.json")


def test_run_unknown_dataset_is_probe_error():
    client = make_client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=CATALOG)))
    with pytest.raises(ProbeError, match="dec/pl"):
        PROBES["census_vintage"].run({"dataset": "dec/pl"}, client)
