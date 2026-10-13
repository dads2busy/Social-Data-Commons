import httpx
import pytest

from sdc_core.sources.checks.probes import PROBES
from sdc_core.sources.checks.probes._http import ProbeError, make_client
from sdc_core.sources.checks.probes.html_years import extract_max_year

PAGE = """
<a href="/doc/2023%20County%20Health%20Rankings%20Virginia%20Data%20-%20v3.xlsx">2023</a>
<a href="/doc/2025 County Health Rankings Virginia Data - v4.xlsx">2025</a>
<img width="3000" height="1024px">
"""
CHR_PATTERN = r"(\d{4})(?: |%20)County(?: |%20)Health(?: |%20)Rankings(?: |%20)Virginia(?: |%20)Data"


def client_with(text, status=200):
    return make_client(transport=httpx.MockTransport(lambda r: httpx.Response(status, text=text)))


def test_spec():
    spec = PROBES["html_years"]
    assert spec.kind == "vintage"
    assert spec.required == {"url", "pattern"}
    assert spec.validate is not None


def test_extract_max_year_filters_implausible():
    assert extract_max_year(PAGE, CHR_PATTERN) == 2025
    assert extract_max_year("width=3000 1024px 0999", r"(\d{4})") is None


def test_run_returns_vintage_observation():
    obs = PROBES["html_years"].run(
        {"url": "https://x.example/p", "pattern": CHR_PATTERN}, client_with(PAGE)
    )
    assert (obs.kind, obs.value, obs.detail) == ("vintage", 2025, "https://x.example/p")


def test_run_no_match_is_probe_error():
    with pytest.raises(ProbeError, match="no year matched"):
        PROBES["html_years"].run(
            {"url": "https://x.example/p", "pattern": r"nothing(\d{4})"}, client_with(PAGE)
        )


@pytest.mark.parametrize("pattern", [r"(\d{4})-(\d{4})", r"\d{4}", r"(\d{4"])
def test_validate_requires_exactly_one_group(pattern):
    with pytest.raises(ValueError):
        PROBES["html_years"].validate({"url": "u", "pattern": pattern})


def test_validate_accepts_one_group():
    PROBES["html_years"].validate({"url": "u", "pattern": r"fmr(20\d{2})/"})


LODES_LISTING = """
<a href="va_wac_S000_JT00_2002.csv.gz">va_wac_S000_JT00_2002.csv.gz</a>
<a href="va_wac_S000_JT00_2022.csv.gz">va_wac_S000_JT00_2022.csv.gz</a>
<a href="va_wac_S000_JT00_2023.csv.gz">va_wac_S000_JT00_2023.csv.gz</a>
"""


def test_lodes_default_pattern():
    spec = PROBES["lodes_vintage"]
    assert spec.kind == "vintage"
    assert spec.required == {"url"}
    assert spec.optional == {"pattern"}
    obs = spec.run({"url": "https://lehd.example/va/wac/"}, client_with(LODES_LISTING))
    assert obs.value == 2023


def test_lodes_custom_pattern_validated():
    with pytest.raises(ValueError):
        PROBES["lodes_vintage"].validate({"url": "u", "pattern": r"(\d{4})(\d{2})"})
    PROBES["lodes_vintage"].validate({"url": "u"})  # no pattern is fine
