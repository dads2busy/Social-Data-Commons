"""Descriptor each probe module exposes as ``SPEC``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import httpx

from sdc_core.sources.checks.compare import Kind, Observation

RunFn = Callable[[dict, httpx.Client], Observation]
ValidateFn = Callable[[dict], None]


@dataclass(frozen=True)
class ProbeSpec:
    name: str
    kind: Kind
    required: frozenset[str]  # registry keys this probe needs
    optional: frozenset[str]  # registry keys it accepts
    run: RunFn
    validate: ValidateFn | None = None  # extra param checks; raise ValueError
