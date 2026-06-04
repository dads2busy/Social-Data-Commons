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


def check_conservation(dist_path, *, tol: float = 0.02, worst_n: int = 5) -> dict:
    """Region-wide geo20/geo10 conservation for pre-2020 tract COUNT measures.

    Gates on REGION-WIDE conservation per count measure: fail if any measure's
    sum(geo20)/sum(geo10) deviates from 1.0 by more than `tol`. This directly tests
    that counts are conserved by the regeneration (the bug doubled them -> ~2.0; the
    2009 2000-vintage mismatch dropped ~35% -> ~0.65), and is robust to legitimate
    PER-COUNTY variation (subgroup clustering, small counts, 2010->2020 county
    boundary changes) which can reach 15-20% without indicating an error.

    Per-county worst-N deviations are REPORTED (per_county_worst) for human review
    but NOT gated.

    Returns {"status": "pass"|"fail"|"n/a",
             "max_ratio": worst region ratio across measures (largest |r-1|; may be <1),
             "per_measure": {base: region_ratio},
             "per_county_worst": {base: [[county, ratio], ...] up to worst_n by |ratio-1|}}.
    """
    df = pd.read_csv(dist_path, dtype={"geoid": str})
    tr = df[(df["year"] < 2020) & (df["region_type"] == "tract")].copy()
    if tr.empty:
        return {"status": "n/a", "max_ratio": None, "per_measure": {}, "per_county_worst": {}}
    tr["county"] = tr["geoid"].str[:5]
    bases = sorted({m[: -len(_GEO20)] for m in tr["measure"].unique() if m.endswith(_GEO20)})
    per_measure, per_county_worst = {}, {}
    for base in bases:
        if not _is_count(base):
            continue
        g10 = tr[tr["measure"] == base + _GEO10]
        g20 = tr[tr["measure"] == base + _GEO20]
        s10, s20 = g10["value"].sum(), g20["value"].sum()
        if s10 == 0:
            continue
        per_measure[base] = float(s20 / s10)
        # per-county worst-N (report only, not gated)
        c10 = g10.groupby("county")["value"].sum()
        c20 = g20.groupby("county")["value"].sum()
        cr = (c20 / c10).replace([np.inf, -np.inf], np.nan).dropna()
        worst = cr.reindex(cr.sub(1).abs().sort_values(ascending=False).index).head(worst_n)
        per_county_worst[base] = [[c, float(v)] for c, v in worst.items()]
    if not per_measure:
        return {"status": "n/a", "max_ratio": None, "per_measure": {}, "per_county_worst": {}}
    worst_ratio = max(per_measure.values(), key=lambda r: abs(r - 1))
    return {
        "status": "pass" if abs(worst_ratio - 1) <= tol else "fail",
        "max_ratio": worst_ratio,
        "per_measure": per_measure,
        "per_county_worst": per_county_worst,
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
