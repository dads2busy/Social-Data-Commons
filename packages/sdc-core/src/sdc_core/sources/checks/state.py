"""Last accepted observation per source id, persisted as committed JSON."""

from __future__ import annotations

import json
from pathlib import Path

from sdc_core.sources.checks.compare import Observation


def load_state(path: Path) -> dict[str, Observation]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {sid: Observation.from_dict(d) for sid, d in raw.items()}


def save_state(path: Path, state: dict[str, Observation]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {sid: state[sid].to_dict() for sid in sorted(state)}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
