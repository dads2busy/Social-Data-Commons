"""Acceptance checks for the census10to20 data remediation (Phase 3)."""
from __future__ import annotations

import numpy as np
import pandas as pd

_GEO20 = "_geo20"
_GEO10 = "_geo10"


def _is_count(base: str) -> bool:
    """Heuristic: a measure is a conserved count if its name marks it so."""
    b = base.lower()
    if any(h in b for h in ("percent", "_pct", "rate", "median", "mean", "index",
                            "score", "gini", "density", "indicator", "ratio", "frac")):
        return False
    return b.endswith("_count") or "count" in b or b.endswith("_pop") or "population" in b


def check_conservation(dist_path, *, tol: float = 1.01) -> dict:
    """County geo20/geo10 sum ratio for pre-2020 tract COUNT measures must be ~1.0.

    Returns {"status": "pass"|"fail"|"n/a", "max_ratio": float|None,
             "per_measure": {base: max_county_ratio}}.
    """
    df = pd.read_csv(dist_path, dtype={"geoid": str})
    tr = df[(df["year"] < 2020) & (df["region_type"] == "tract")].copy()
    if tr.empty:
        return {"status": "n/a", "max_ratio": None, "per_measure": {}}
    tr["county"] = tr["geoid"].str[:5]
    bases = sorted({
        m[: -len(_GEO20)] for m in tr["measure"].unique() if m.endswith(_GEO20)
    })
    per_measure: dict[str, float] = {}
    for base in bases:
        if not _is_count(base):
            continue
        g10 = tr[tr["measure"] == base + _GEO10].groupby("county")["value"].sum()
        g20 = tr[tr["measure"] == base + _GEO20].groupby("county")["value"].sum()
        ratio = (g20 / g10).replace([np.inf, -np.inf], np.nan).dropna()
        if not ratio.empty:
            per_measure[base] = float(ratio.max())
    if not per_measure:
        return {"status": "n/a", "max_ratio": None, "per_measure": {}}
    max_ratio = max(per_measure.values())
    return {
        "status": "pass" if max_ratio <= tol else "fail",
        "max_ratio": max_ratio,
        "per_measure": per_measure,
    }
