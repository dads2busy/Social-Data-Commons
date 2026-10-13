"""Pure comparison of a probe observation against our recorded state.

No I/O here. Probes produce an ``Observation``; ``compare`` turns it, plus the
pipeline's ``latest`` year and the prior stored observation, into a ``Status``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

Kind = Literal["vintage", "content", "manual"]
Status = Literal["new_vintage", "changed", "unverified", "error", "baseline", "current", "not_tracked"]

STATUS_ORDER: dict[str, int] = {
    s: i
    for i, s in enumerate(
        ["new_vintage", "changed", "unverified", "error", "baseline", "current", "not_tracked"]
    )
}
ACTION_STATUSES: frozenset[str] = frozenset({"new_vintage", "changed", "unverified", "error"})


@dataclass(frozen=True)
class Observation:
    """What a probe saw upstream at one moment."""

    kind: Kind
    value: int | str | None  # year for vintage, fingerprint for content, None for manual
    fetched_at: datetime  # UTC
    detail: str  # one human-readable line: URL inspected, header used, ...

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "value": self.value,
            "fetched_at": self.fetched_at.isoformat(),
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Observation:
        return cls(
            kind=d["kind"],
            value=d.get("value"),
            fetched_at=datetime.fromisoformat(d["fetched_at"]),
            detail=d.get("detail", ""),
        )


@dataclass(frozen=True)
class Row:
    """One line of the report: a (source, pipeline) pair with its status."""

    status: Status
    source: str | None
    pipeline: str
    ours: int | None
    upstream: int | str | None
    detail: str
    fetched_at: datetime | None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["fetched_at"] = self.fetched_at.isoformat() if self.fetched_at else None
        return d


def compare(observation: Observation, latest: int | None, prior: Observation | None) -> Status:
    """Apply the status matrix from the spec (Section 3)."""
    if observation.kind == "manual":
        return "unverified"
    if observation.kind == "vintage":
        if latest is None:
            raise ValueError("vintage comparison requires the pipeline's `latest` year")
        return "new_vintage" if int(observation.value) > latest else "current"
    # content
    if prior is None or prior.kind != "content":
        return "baseline"
    return "changed" if observation.value != prior.value else "current"


def describe(status: Status, observation: Observation, prior: Observation | None) -> str:
    """Detail column text for a row."""
    if status == "changed" and prior is not None:
        return f"{observation.detail} changed (was {prior.value})"
    if status == "baseline":
        return f"{observation.detail} recorded"
    return observation.detail
