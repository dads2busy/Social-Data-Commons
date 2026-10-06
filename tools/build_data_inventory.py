"""Build the docs-site data inventory from what the two dashboards actually serve.

Reads each dashboard repo's ``data/measure_info.json`` and per-geography wide
files, works out which measures have data at which geographic level and for
which years, and writes ``docsite/inventory/inventory.json`` for the Data
inventory page to render.

Usage (from the repo root)::

    uv run python tools/build_data_inventory.py
    uv run python tools/build_data_inventory.py --ncr ../national_capital_region_data --va ../virginia_public_health_data

The output JSON is committed so the docs build needs nothing outside this repo.
Re-run whenever dashboard data changes.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "docsite" / "inventory" / "inventory.json"

# Geographic levels per dashboard, in display order: (file stem, column label).
SITES = {
    "ncr": {
        "label": "National Capital Region",
        "default_path": REPO_ROOT.parent / "national_capital_region_data",
        "levels": [
            ("county", "county"),
            ("tract", "tract"),
            ("block_group", "block group"),
            ("zip_code", "zip code"),
            ("planning_district", "planning dist"),
            ("human_services_region", "human srvc reg"),
            ("supervisor_district", "supervisor dist"),
            ("civic_association", "civic assoc"),
        ],
    },
    "va": {
        "label": "Virginia",
        "default_path": REPO_ROOT.parent / "virginia_public_health_data",
        "levels": [
            ("health_district", "health district"),
            ("county", "county"),
            ("tract", "tract"),
        ],
    },
}

GEO_SUFFIX = re.compile(r"_geo(10|20)$")
# NAICS-coded business climate variables, e.g. NAICS72_entry_rate, NAICS31_33_entry_rate.
NAICS_PREFIX = re.compile(r"^NAICS\d+(?:_\d+)?_")


def scan_levels(site_path: Path, levels: list[tuple[str, str]]) -> dict[str, dict[str, list[int]]]:
    """Return {variable: {level_key: [min_year, max_year]}} for one dashboard."""
    coverage: dict[str, dict[str, list[int]]] = {}
    for level_key, _label in levels:
        path = site_path / "data" / f"{level_key}.csv.xz"
        if not path.exists():
            print(f"  skip {path.name}: not found")
            continue
        df = pd.read_csv(path, dtype={"ID": str})
        for col in df.columns:
            if col in ("ID", "time"):
                continue
            years = df.loc[df[col].notna(), "time"]
            if years.empty:
                continue
            coverage.setdefault(col, {})[level_key] = [int(years.min()), int(years.max())]
        print(f"  {path.name}: {len(df.columns) - 2} variables, {len(df)} rows")
    return coverage


def load_measure_info(site_path: Path) -> dict[str, dict]:
    info = json.loads((site_path / "data" / "measure_info.json").read_text())
    return {k: v for k, v in info.items() if isinstance(v, dict) and not k.startswith("_")}


def base_name(var: str) -> str:
    return GEO_SUFFIX.sub("", var)


def build_rows(scans: dict[str, dict], infos: dict[str, dict]) -> list[dict]:
    """Fold variables across sites and boundary variants into one row per measure."""
    rows: dict[str, dict] = {}
    for site, coverage in scans.items():
        info = infos[site]
        for var, by_level in coverage.items():
            key = base_name(var)
            row = rows.setdefault(
                key,
                {
                    "key": key,
                    "label": None,
                    "category": None,
                    "description": "",
                    "geo10": False,
                    "levels": {},
                    "years": None,
                },
            )
            if var.endswith("_geo10"):
                row["geo10"] = True
            meta = info.get(var) or info.get(key) or info.get(key + "_geo20") or {}
            # Prefer the 2020-boundary metadata; fall back to whatever exists.
            if meta and (row["label"] is None or var.endswith("_geo20")):
                row["label"] = (meta.get("short_name") or meta.get("long_name") or key).strip()
                row["category"] = meta.get("category") or "Other"
                row["description"] = meta.get("short_description") or ""
            for level_key, (lo, hi) in by_level.items():
                lk = f"{site}:{level_key}"
                cur = row["levels"].get(lk)
                row["levels"][lk] = [min(lo, cur[0]), max(hi, cur[1])] if cur else [lo, hi]
    for row in rows.values():
        if row["label"] is None:
            row["label"] = row["key"]
            row["category"] = "Other"
        spans = list(row["levels"].values())
        row["years"] = [min(s[0] for s in spans), max(s[1] for s in spans)]
    return sorted(rows.values(), key=lambda r: (r["category"].lower(), r["label"].lower()))


def group_naics(rows: list[dict]) -> list[dict]:
    """Attach per-industry business climate rows to their all-industry parent."""
    by_key = {r["key"]: r for r in rows}
    for row in rows:
        m = NAICS_PREFIX.match(row["key"])
        if not m:
            continue
        metric = row["key"][m.end():]
        parent = by_key.get(metric)
        if parent is None:
            parent = by_key[metric] = {
                "key": metric,
                "label": metric.replace("_", " "),
                "category": row["category"],
                "description": "",
                "geo10": False,
                "levels": {},
                "years": row["years"][:],
            }
            rows.append(parent)
        row["group"] = metric
        parent.setdefault("children", 0)
        parent["children"] += 1
        parent["years"] = [min(parent["years"][0], row["years"][0]), max(parent["years"][1], row["years"][1])]
    return sorted(rows, key=lambda r: (r["category"].lower(), r.get("group", r["key"]) != r["key"], r["label"].lower()))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ncr", type=Path, default=SITES["ncr"]["default_path"], help="path to the NCR dashboard repo")
    ap.add_argument("--va", type=Path, default=SITES["va"]["default_path"], help="path to the VA dashboard repo")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    paths = {"ncr": args.ncr, "va": args.va}
    scans, infos = {}, {}
    for site, cfg in SITES.items():
        print(f"{cfg['label']} ({paths[site]})")
        scans[site] = scan_levels(paths[site], cfg["levels"])
        infos[site] = load_measure_info(paths[site])

    rows = group_naics(build_rows(scans, infos))
    out = {
        "generated": date.today().isoformat(),
        "sites": [
            {"key": site, "label": cfg["label"], "levels": [{"key": f"{site}:{k}", "label": lbl} for k, lbl in cfg["levels"]]}
            for site, cfg in SITES.items()
        ],
        "categories": sorted({r["category"] for r in rows}, key=str.lower),
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    n_parents = sum(1 for r in rows if "group" not in r)
    print(f"wrote {args.out} ({len(rows)} rows, {n_parents} top-level, {len(out['categories'])} categories)")


if __name__ == "__main__":
    main()
