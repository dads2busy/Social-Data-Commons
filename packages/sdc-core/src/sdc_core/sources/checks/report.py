"""Render rows as a fixed-width table or JSON; derive the exit code."""

from __future__ import annotations

import json

from sdc_core.sources.checks.compare import ACTION_STATUSES, STATUS_ORDER, Row

COLUMNS = ["STATUS", "SOURCE", "PIPELINE", "OURS", "UPSTREAM", "DETAIL"]


def sort_rows(rows: list[Row]) -> list[Row]:
    return sorted(rows, key=lambda r: (STATUS_ORDER[r.status], r.source or "~", r.pipeline))


def _cell(value: object) -> str:
    return "-" if value is None else str(value)


def render_table(rows: list[Row]) -> str:
    data = [
        [r.status, _cell(r.source), r.pipeline, _cell(r.ours), _cell(r.upstream), r.detail]
        for r in rows
    ]
    widths = [max(len(line[i]) for line in [COLUMNS, *data]) for i in range(len(COLUMNS) - 1)]

    def fmt(cells: list[str]) -> str:
        fixed = "  ".join(c.ljust(w) for c, w in zip(cells[:-1], widths))
        return f"{fixed}  {cells[-1]}".rstrip()

    return "\n".join([fmt(COLUMNS), *(fmt(d) for d in data)])


def render_json(rows: list[Row]) -> str:
    return json.dumps([r.to_dict() for r in rows], indent=2) + "\n"


def exit_code(rows: list[Row]) -> int:
    return 1 if any(r.status in ACTION_STATUSES for r in rows) else 0
