"""Sync pipeline data from dashboard_data/ to dashboard repos.

Copies per-pipeline wide-format CSVs, merges them into per-level combined
CSVs, builds measure_info.json (with exclusion support), and optionally
runs npm run build:data in the target repo.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

import pandas as pd
import yaml

from sdc_core.log import get_logger

log = get_logger("sdc.sync")

# Map filename resolution codes (second segment) to geographic level names
RESOLUTION_MAP = {
    "bg": "block_group",
    "tr": "tract",
    "ct": "county",
    "hd": "health_district",
    "ca": "civic_association",
    "hsr": "human_services_region",
    "pd": "planning_district",
    "sd": "supervisor_district",
    "zc": "zip_code",
}


def load_sync_config(repo_root: Path) -> dict:
    """Load sync.yaml from the repo root."""
    config_path = repo_root / "sync.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"No sync.yaml found at {config_path}")
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_exclusions(source_dir: Path) -> set[str]:
    """Load excluded measure names from exclude_measures.txt."""
    exclude_path = source_dir / "exclude_measures.txt"
    if not exclude_path.exists():
        return set()
    excluded = set()
    for line in exclude_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            excluded.add(line)
    return excluded


def classify_file(filename: str) -> str | None:
    """Extract geographic level from a dashboard CSV filename.

    Filenames follow: {area}_{resolution}_{source}_{years}_{title}.csv.xz
    The resolution code is the second underscore-delimited segment.
    """
    stem = filename.replace(".csv.xz", "")
    parts = stem.split("_")
    if len(parts) < 3:
        return None
    code = parts[1]
    return RESOLUTION_MAP.get(code)


def load_geo_ids(geo_path: Path) -> set[str]:
    """Extract valid region IDs from a GeoJSON or keyed-JSON geo file."""
    with open(geo_path) as f:
        geo = json.load(f)

    ids: set[str] = set()

    # Standard GeoJSON FeatureCollection
    if isinstance(geo.get("features"), list):
        for feat in geo["features"]:
            props = feat.get("properties", {})
            gid = props.get("geoid") or props.get("GEOID") or feat.get("id")
            if gid:
                ids.add(str(gid))
    else:
        # Keyed format: top-level keys are region IDs
        skip = {"_meta", "type", "name", "crs"}
        for key in geo:
            if key not in skip:
                ids.add(key)

    return ids


def merge_csvs_for_level(
    csv_paths: list[Path],
    level: str,
    valid_ids: set[str] | None = None,
) -> pd.DataFrame:
    """Read and outer-join all wide-format CSVs for a geographic level.

    If valid_ids is provided, filter each CSV to only include those region IDs
    before merging (left join starting from the valid ID set).
    """
    dfs = []
    for p in csv_paths:
        df = pd.read_csv(p, dtype={"ID": str, "time": str})
        if valid_ids:
            df = df[df["ID"].isin(valid_ids)]
        dfs.append(df)
        log.info("  Read %s (%d rows, %d cols)", p.name, len(df), len(df.columns) - 2)

    if len(dfs) == 1:
        return dfs[0]

    merged = dfs[0]
    for df in dfs[1:]:
        merged = pd.merge(merged, df, on=["ID", "time"], how="outer")

    # Sort columns: ID, time, then alphabetical
    fixed = ["ID", "time"]
    other = sorted(c for c in merged.columns if c not in fixed)
    merged = merged[fixed + other]

    return merged


def sync_dashboard(
    name: str,
    config: dict,
    repo_root: Path,
    *,
    dry_run: bool = False,
    no_build: bool = False,
) -> None:
    """Sync a single dashboard."""
    source_dir = repo_root / config["source"]
    target_dir = Path(config["target"])
    levels = config["levels"]

    if not source_dir.exists():
        log.error("Source directory does not exist: %s", source_dir)
        return
    if not target_dir.exists():
        log.error("Target directory does not exist: %s", target_dir)
        return

    log.info("Syncing '%s': %s → %s", name, source_dir, target_dir)

    # 1. Collect pipeline CSVs and classify by level
    csv_files = sorted(source_dir.glob("*.csv.xz"))
    by_level: dict[str, list[Path]] = defaultdict(list)
    unclassified = []

    for f in csv_files:
        level = classify_file(f.name)
        if level and level in levels:
            by_level[level].append(f)
        elif level:
            log.warning("  Skipping %s (level '%s' not in dashboard levels)", f.name, level)
        else:
            unclassified.append(f)

    if unclassified:
        log.warning("  Could not classify: %s", [f.name for f in unclassified])

    # 2. Build measure_info.json by merging all pipeline measure_info files,
    #    then applying exclusions. This ensures new measures are picked up
    #    automatically without manual measure_info.json maintenance.
    exclusions = load_exclusions(source_dir)

    # Collect all measure names from CSV columns
    all_measures = set()
    for csvs in by_level.values():
        for p in csvs:
            header = pd.read_csv(p, nrows=0).columns.tolist()
            all_measures.update(c for c in header if c not in ("ID", "time"))

    # Scan all pipeline measure_info.json files in the repo
    measure_info: dict = {}
    for mi_path in sorted(repo_root.rglob("data/distribution/measure_info.json")):
        if any(skip in str(mi_path) for skip in (".claude", "worktree", "/meta/")):
            continue
        with open(mi_path) as f:
            pipeline_mi = json.load(f)
        for measure_name, meta in pipeline_mi.items():
            if measure_name in all_measures:
                measure_info[measure_name] = meta

    # Apply exclusions
    for ex in exclusions:
        measure_info.pop(ex, None)

    log.info("  measure_info: %d measures (%d in CSVs, %d excluded)",
             len(measure_info), len(all_measures), len(exclusions))

    if dry_run:
        log.info("[dry-run] Would sync:")
        for level in levels:
            csvs = by_level.get(level, [])
            log.info("  %s: %d CSVs → %s.csv.xz", level, len(csvs), level)
            for c in csvs:
                log.info("    - %s", c.name)
        log.info("  measure_info.json: %d measures", len(measure_info))
        if exclusions:
            log.info("  Excluded: %s", sorted(exclusions))
        return

    # 3. Copy individual pipeline CSVs to target
    for f in csv_files:
        level = classify_file(f.name)
        if level and level in levels:
            dest = target_dir / f.name
            shutil.copy2(f, dest)
    log.info("  Copied %d pipeline CSVs", len(csv_files))

    # 4. Load valid region IDs from GeoJSON files (if configured)
    geo_dir = Path(config["geo_dir"]) if "geo_dir" in config else None
    geo_files: dict[str, str] = config.get("geo_files", {})
    geo_ids_by_level: dict[str, set[str]] = {}
    if geo_dir and geo_files:
        for level_name, geo_filename in geo_files.items():
            geo_path = geo_dir / geo_filename
            if geo_path.exists():
                ids = load_geo_ids(geo_path)
                geo_ids_by_level[level_name] = ids
                log.info("  Loaded %d valid IDs for '%s' from %s", len(ids), level_name, geo_filename)
            else:
                log.warning("  GeoJSON not found for '%s': %s", level_name, geo_path)

    # 5. Merge into per-level combined CSVs
    for level in levels:
        csvs = by_level.get(level, [])
        if not csvs:
            log.warning("  No CSVs for level '%s'", level)
            continue
        valid_ids = geo_ids_by_level.get(level)
        log.info("  Merging %d CSVs for '%s'...", len(csvs), level)
        merged = merge_csvs_for_level(csvs, level, valid_ids=valid_ids)
        # Drop excluded measure columns from the merged CSV
        drop_cols = [c for c in merged.columns if c in exclusions]
        if drop_cols:
            merged = merged.drop(columns=drop_cols)
            log.info("  Dropped %d excluded columns", len(drop_cols))
        out_path = target_dir / f"{level}.csv.xz"
        merged.to_csv(out_path, index=False, compression="xz")
        log.info("  Wrote %s (%d rows, %d cols)", out_path.name, len(merged), len(merged.columns) - 2)

    # 6. Write measure_info.json
    mi_path = target_dir / "measure_info.json"
    with open(mi_path, "w") as f:
        json.dump(measure_info, f, indent=4)
    log.info("  Wrote measure_info.json")

    # 7. Run npm run build:data
    if no_build:
        log.info("  Skipping build (--no-build)")
        return

    dashboard_repo = target_dir.parent
    package_json = dashboard_repo / "package.json"
    if not package_json.exists():
        log.warning("  No package.json at %s — skipping build", dashboard_repo)
        return

    log.info("  Running npm run build:data in %s...", dashboard_repo)
    result = subprocess.run(
        ["npm", "run", "build:data"],
        cwd=dashboard_repo,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        log.info("  build:data completed successfully")
    else:
        log.error("  build:data failed (exit %d):\n%s", result.returncode, result.stderr)


def run_sync(
    dashboard: str | None = None,
    *,
    dry_run: bool = False,
    no_build: bool = False,
    repo_root: Path | None = None,
) -> None:
    """Run sync for one or all dashboards."""
    if repo_root is None:
        repo_root = Path.cwd()
        # Walk up to find sync.yaml
        for parent in [repo_root] + list(repo_root.parents):
            if (parent / "sync.yaml").exists():
                repo_root = parent
                break

    config = load_sync_config(repo_root)
    dashboards = config.get("dashboards", {})

    if dashboard:
        if dashboard not in dashboards:
            raise ValueError(f"Unknown dashboard '{dashboard}'. Available: {sorted(dashboards)}")
        sync_dashboard(dashboard, dashboards[dashboard], repo_root, dry_run=dry_run, no_build=no_build)
    else:
        for name, cfg in dashboards.items():
            sync_dashboard(name, cfg, repo_root, dry_run=dry_run, no_build=no_build)
