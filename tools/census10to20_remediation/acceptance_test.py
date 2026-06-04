"""Acceptance checks for the census10to20 data remediation (Phase 3)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sdc_census10to20 import parse_geo_standardize_info

_GEO20 = "_geo20"
_GEO10 = "_geo10"


def _is_count(base: str) -> bool:
    """Heuristic: a measure is a conserved count if its name marks it so."""
    b = base.lower()
    if any(h in b for h in ("percent", "_pct", "rate", "median", "mean", "index",
                            "score", "gini", "density", "indicator", "ratio", "frac")):
        return False
    return b.endswith("_count") or "count" in b or b.endswith("_pop") or "population" in b


def check_conservation(dist_path, *, tol: float = 0.03) -> dict:
    """County geo20/geo10 sum ratio for pre-2020 tract COUNT measures must be ~1.0.

    tol is the maximum allowed absolute deviation from 1.0 (e.g. 0.03 = ±3%).
    Returns {"status": "pass"|"fail"|"n/a", "max_ratio": float|None,
             "per_measure": {base: worst_county_ratio}}.
    max_ratio holds the county ratio with the largest absolute deviation from 1.0
    across all count measures (may be <1 or >1).
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
            # Pick the county ratio with the largest absolute deviation from 1.0
            per_measure[base] = float(ratio.iloc[(ratio - 1).abs().argmax()])
    if not per_measure:
        return {"status": "n/a", "max_ratio": None, "per_measure": {}}
    # worst_ratio is the per-measure value with the largest absolute deviation from 1.0
    worst_ratio = max(per_measure.values(), key=lambda r: abs(r - 1))
    return {
        "status": "pass" if abs(worst_ratio - 1) <= tol else "fail",
        "max_ratio": worst_ratio,
        "per_measure": per_measure,
    }


def check_ratio_consistency(dist_path, measure_info, *, tol: float = 0.5) -> dict:
    """Each ratio _geo20 must equal scale * numerator_geo20 / denominator_geo20.

    Only ratio specs whose numerator AND denominator _geo20 are present in the file
    are checked (frame-change datasets drop their helper counts, so they are skipped).
    Returns {"status": "pass"|"fail"|"n/a", "max_abs_diff": float|None,
             "checked": [base, ...]}.
    """
    df = pd.read_csv(dist_path, dtype={"geoid": str})
    df = df[df["region_type"] == "tract"]
    specs = parse_geo_standardize_info(measure_info)
    present = set(df["measure"].unique())

    def series(base):
        return df[df["measure"] == base + _GEO20].set_index(["geoid", "year"])["value"]

    checked, max_diff = [], 0.0
    for base, spec in specs.items():
        if spec.get("measure_type") not in ("ratio", "rate"):
            continue
        num, den = spec.get("numerator"), spec.get("denominator")
        if not (num and den):
            continue
        if not ({num + _GEO20, den + _GEO20, base + _GEO20} <= present):
            continue
        scale = spec.get("scale", 100)
        recomputed = scale * series(num) / series(den)
        published = series(base)
        diff = (recomputed - published).abs().replace([np.inf, -np.inf], np.nan).dropna()
        if not diff.empty:
            checked.append(base)
            max_diff = max(max_diff, float(diff.max()))
    if not checked:
        return {"status": "n/a", "max_abs_diff": None, "checked": []}
    return {
        "status": "pass" if max_diff <= tol else "fail",
        "max_abs_diff": max_diff,
        "checked": checked,
    }
