"""Upstream source freshness checks: probes -> compare -> rows.

Entry point is ``run_checks``. See docs/specs/2026-10-13-source-freshness-check-design.md.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from sdc_core.log import get_logger
from sdc_core.sources.checks.compare import Observation, Row, compare, describe
from sdc_core.sources.checks.probes import PROBES
from sdc_core.sources.checks.probes._http import ProbeError, make_client
from sdc_core.sources.checks.registry import Registry, discover_pipelines
from sdc_core.sources.checks.report import sort_rows

log = get_logger("sdc.sources.checks")

__all__ = ["run_checks", "make_client"]


def run_checks(
    registry: Registry,
    state: dict[str, Observation],
    repo_root: Path,
    *,
    source_filter: set[str] = frozenset(),
    pipeline_filter: set[str] = frozenset(),
    client: httpx.Client | None = None,
) -> tuple[list[Row], dict[str, Observation]]:
    """Probe every (filtered) source once and emit one row per consuming pipeline.

    Returns sorted rows and the observations worth persisting (successful, non-manual).
    """
    own_client = client is None
    client = client or make_client()
    rows: list[Row] = []
    observed: dict[str, Observation] = {}
    try:
        for entry in registry.sources:
            if source_filter and entry.id not in source_filter:
                continue
            refs = [r for r in entry.pipelines if not pipeline_filter or r.path in pipeline_filter]
            if not refs:
                continue
            spec = PROBES[entry.probe]
            try:
                obs = spec.run(entry.params, client)
            except ProbeError as exc:
                message = str(exc)
            except Exception as exc:  # noqa: BLE001 - any probe failure is an error row, never a crash
                message = f"{type(exc).__name__}: {exc}"
            else:
                message = None
            if message is not None:
                log.warning("%s: %s", entry.id, message)
                rows.extend(
                    Row("error", entry.id, r.path, r.latest, None, message, None) for r in refs
                )
                continue
            if obs.kind != "manual":
                observed[entry.id] = obs
            prior = state.get(entry.id)
            for r in refs:
                status = compare(obs, r.latest, prior)
                upstream = obs.value if obs.kind == "vintage" else None
                rows.append(
                    Row(
                        status,
                        entry.id,
                        r.path,
                        r.latest,
                        upstream,
                        describe(status, obs, prior),
                        obs.fetched_at,
                    )
                )
    finally:
        if own_client:
            client.close()

    if not source_filter and not pipeline_filter:
        tracked = registry.tracked_paths()
        for path in discover_pipelines(repo_root):
            if path not in tracked:
                reason = registry.untracked.get(path, "no registry entry")
                rows.append(Row("not_tracked", None, path, None, None, reason, None))
    return sort_rows(rows), observed
