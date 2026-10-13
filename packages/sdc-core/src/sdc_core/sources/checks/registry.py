"""meta/source_checks.yaml: which upstream sources feed which pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from sdc_core.sources.checks.probes import PROBES

REGISTRY_HEADER = (
    "# Machine-maintained by `sdc sources sync-latest`; comments outside this header are lost\n"
    "# on rewrite. Use a source's `note` key for remarks that must survive.\n"
)
ENTRY_KEYS = {"probe", "pipelines"}
PIPELINE_KEYS = {"path", "latest", "source", "key"}
SKIP_DIR_PARTS = {"node_modules"}


class RegistryError(ValueError):
    """The registry file is malformed."""


@dataclass(frozen=True)
class PipelineRef:
    path: str  # pipeline dir relative to repo root, as on disk
    latest: int | None = None  # max year we have ingested (vintage probes only)
    source: str | None = None  # name under the pipeline's `sources:`; None = all
    key: str | None = None  # sub-key within that source to restrict the year walk


@dataclass(frozen=True)
class SourceEntry:
    id: str
    probe: str
    params: dict
    pipelines: tuple[PipelineRef, ...]


@dataclass(frozen=True)
class Registry:
    sources: tuple[SourceEntry, ...]
    untracked: dict[str, str]  # pipeline path -> reason

    def tracked_paths(self) -> set[str]:
        return {ref.path for entry in self.sources for ref in entry.pipelines}


def _parse_pipeline(sid: str, spec_kind: str, raw: object) -> PipelineRef:
    if not isinstance(raw, dict) or "path" not in raw:
        raise RegistryError(f"{sid}: each pipeline entry needs a `path`")
    unknown = raw.keys() - PIPELINE_KEYS
    if unknown:
        raise RegistryError(f"{sid}/{raw['path']}: unknown pipeline keys {sorted(unknown)}")
    latest = raw.get("latest")
    if spec_kind == "vintage" and not isinstance(latest, int):
        raise RegistryError(f"{sid}/{raw['path']}: vintage probe requires integer latest")
    if spec_kind != "vintage" and latest is not None:
        raise RegistryError(f"{sid}/{raw['path']}: latest is only allowed on vintage probes")
    return PipelineRef(
        path=str(raw["path"]), latest=latest, source=raw.get("source"), key=raw.get("key")
    )


def _parse_entry(sid: str, body: object) -> SourceEntry:
    if not isinstance(body, dict):
        raise RegistryError(f"{sid}: entry must be a mapping")
    probe_name = body.get("probe")
    spec = PROBES.get(probe_name)
    if spec is None:
        raise RegistryError(f"{sid}: unknown probe {probe_name!r}; known: {sorted(PROBES)}")
    params = {k: v for k, v in body.items() if k not in ENTRY_KEYS}
    missing = spec.required - params.keys()
    if missing:
        raise RegistryError(f"{sid}: missing keys {sorted(missing)} for probe {probe_name}")
    unknown = params.keys() - spec.required - spec.optional
    if unknown:
        raise RegistryError(f"{sid}: unknown keys {sorted(unknown)} for probe {probe_name}")
    if spec.validate is not None:
        try:
            spec.validate(params)
        except ValueError as exc:
            raise RegistryError(f"{sid}: {exc}") from exc
    refs = tuple(_parse_pipeline(sid, spec.kind, p) for p in body.get("pipelines") or [])
    if not refs:
        raise RegistryError(f"{sid}: no pipelines listed")
    return SourceEntry(id=sid, probe=probe_name, params=params, pipelines=refs)


def load_registry(path: Path) -> Registry:
    raw = yaml.safe_load(path.read_text()) or {}
    entries = tuple(_parse_entry(sid, body) for sid, body in (raw.get("sources") or {}).items())
    untracked: dict[str, str] = {}
    for item in raw.get("untracked") or []:
        if not isinstance(item, dict) or "path" not in item or "reason" not in item:
            raise RegistryError("untracked entries need path and reason")
        untracked[str(item["path"])] = str(item["reason"])
    return Registry(sources=entries, untracked=untracked)


def discover_pipelines(repo_root: Path) -> list[str]:
    """Every dir under the repo containing pipeline.yaml, excluding hidden dirs and worktrees."""
    found: list[str] = []
    for p in repo_root.rglob("pipeline.yaml"):
        rel = p.parent.relative_to(repo_root)
        if any(
            part.startswith(".") or "worktree" in part or part in SKIP_DIR_PARTS
            for part in rel.parts
        ):
            continue
        found.append(rel.as_posix())
    return sorted(found)


def audit(registry: Registry, repo_root: Path) -> tuple[list[str], list[str]]:
    on_disk = set(discover_pipelines(repo_root))
    known = registry.tracked_paths() | set(registry.untracked)
    return sorted(on_disk - known), sorted(known - on_disk)


def max_year(obj: object) -> int | None:
    """Largest year in any `years:` list or `urls:` dict key, at any depth."""
    found: set[int] = set()

    def walk(x: object) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "years" and isinstance(v, list):
                    found.update(int(y) for y in v if str(y).isdigit())
                elif k == "urls" and isinstance(v, dict):
                    found.update(int(y) for y in v if str(y).isdigit())
                else:
                    walk(v)
        elif isinstance(x, list):
            for item in x:
                walk(item)

    walk(obj)
    return max(found) if found else None


def compute_latest(repo_root: Path, ref: PipelineRef) -> int | None:
    cfg_path = repo_root / ref.path / "pipeline.yaml"
    if not cfg_path.exists():
        return None
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    target: object = cfg.get("sources") or {}
    if not isinstance(target, dict):
        return None
    if ref.source is not None:
        if ref.source not in target:
            return None
        target = target[ref.source]
    if ref.key is not None:
        if not isinstance(target, dict) or ref.key not in target:
            return None
        target = target[ref.key]
    return max_year(target)


def sync_latest(
    registry_path: Path, repo_root: Path, *, dry_run: bool
) -> list[tuple[str, str, int | None, int | None]]:
    """Rewrite each vintage pipeline's `latest` from its pipeline.yaml.

    Returns (source_id, pipeline_path, old, new) for every vintage pipeline ref.
    `new is None` means the source/key could not be resolved; that ref is left untouched.
    """
    raw = yaml.safe_load(registry_path.read_text()) or {}
    registry = load_registry(registry_path)
    changes: list[tuple[str, str, int | None, int | None]] = []
    dirty = False
    for entry in registry.sources:
        if PROBES[entry.probe].kind != "vintage":
            continue
        for i, ref in enumerate(entry.pipelines):
            new = compute_latest(repo_root, ref)
            changes.append((entry.id, ref.path, ref.latest, new))
            if new is not None and new != ref.latest:
                raw["sources"][entry.id]["pipelines"][i]["latest"] = new
                dirty = True
    if dirty and not dry_run:
        body = yaml.safe_dump(raw, sort_keys=False, allow_unicode=True, width=120)
        registry_path.write_text(REGISTRY_HEADER + body)
    return changes
