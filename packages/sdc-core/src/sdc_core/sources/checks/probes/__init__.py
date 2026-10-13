"""Registry of probe kinds. Add a module and list it here to add a probe."""

from __future__ import annotations

from sdc_core.sources.checks.probes import http_file, manual
from sdc_core.sources.checks.probes._spec import ProbeSpec

PROBES: dict[str, ProbeSpec] = {m.SPEC.name: m.SPEC for m in (manual, http_file)}

__all__ = ["PROBES", "ProbeSpec"]
