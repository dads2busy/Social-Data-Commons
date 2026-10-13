"""Registry of probe kinds. Add a module and list it here to add a probe."""

from __future__ import annotations

from sdc_core.sources.checks.probes import html_years, http_file, lodes_vintage, manual
from sdc_core.sources.checks.probes._spec import ProbeSpec

PROBES: dict[str, ProbeSpec] = {
    m.SPEC.name: m.SPEC for m in (manual, http_file, html_years, lodes_vintage)
}

__all__ = ["PROBES", "ProbeSpec"]
