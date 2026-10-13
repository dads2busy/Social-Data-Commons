"""Where the registry and state live, relative to the monorepo root."""

from __future__ import annotations

from pathlib import Path

ROOT_MARKER = "sync.yaml"


def find_repo_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    for candidate in [start, *start.parents]:
        if (candidate / ROOT_MARKER).exists():
            return candidate
    raise FileNotFoundError(f"could not find repo root: no {ROOT_MARKER} in {start} or its parents")


def registry_path(root: Path) -> Path:
    return root / "meta" / "source_checks.yaml"


def state_path(root: Path) -> Path:
    return root / "meta" / "source_checks_state.json"
