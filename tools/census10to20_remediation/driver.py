"""Driver for the census10to20 data regeneration (Phase 3b runs this)."""
from __future__ import annotations

import glob as _glob
import importlib.util
import subprocess
import sys
from pathlib import Path

from sdc_core.versioning import update_version

# Ensure the package directory is on sys.path so that sibling modules
# (acceptance_test, datasets) are importable when driver is imported directly
# (e.g. via importlib) rather than through a test that pre-inserts the path.
_PKG_DIR = str(Path(__file__).parent)
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)

from acceptance_test import check_conservation


def run_entrypoint(module_path, func_name: str):
    """Import a module by file path and call one of its functions.

    Executes module top-level code (imports, constants) but NOT the
    ``if __name__ == "__main__"`` block — so a pipeline's ``run()`` is invoked
    without triggering the ``update_version`` auto-publish in its ``__main__``.
    """
    module_path = Path(module_path)
    spec = importlib.util.spec_from_file_location(f"_regen_{module_path.stem}", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, func_name)
    return fn()


def _dist_files(entry, repo_root):
    matches = sorted(_glob.glob(str(Path(repo_root) / entry["topic"] / entry["dist_glob"])))
    if not matches:
        raise FileNotFoundError(f"{entry['topic']}: no file matches {entry['dist_glob']}")
    return matches


def _acceptance_conservation(entry, repo_root):
    """Run check_conservation over ALL of a dataset's distribution files; aggregate.

    status = fail if any file fails; n/a only if every file is n/a; else pass.
    max_ratio = worst (largest) across files.
    """
    files = _dist_files(entry, repo_root)
    reps = [check_conservation(f) for f in files]
    ratios = [r["max_ratio"] for r in reps if r["max_ratio"] is not None]
    if any(r["status"] == "fail" for r in reps):
        status = "fail"
    elif all(r["status"] == "n/a" for r in reps):
        status = "n/a"
    else:
        status = "pass"
    return {"status": status, "max_ratio": max(ratios) if ratios else None,
            "per_file": {Path(f).name: r for f, r in zip(files, reps)}}


def _acceptance(entry, repo_root):
    """Combined gate: count conservation (all files) + ratio consistency (all files)."""
    from acceptance_test import check_ratio_consistency
    import json as _json

    cons = _acceptance_conservation(entry, repo_root)
    mi_path = Path(repo_root) / entry["topic"] / entry["measure_info"]
    measure_info = _json.loads(mi_path.read_text()) if mi_path.exists() else {}
    ratio_reps = [check_ratio_consistency(f, measure_info) for f in _dist_files(entry, repo_root)]
    ratio_status = (
        "fail" if any(r["status"] == "fail" for r in ratio_reps)
        else ("n/a" if all(r["status"] == "n/a" for r in ratio_reps) else "pass")
    )
    overall = "fail" if cons["status"] == "fail" or ratio_status == "fail" else (
        "n/a" if cons["status"] == "n/a" and ratio_status == "n/a" else "pass"
    )
    return {"status": overall, "conservation": cons,
            "ratio": {"status": ratio_status, "reps": ratio_reps}}


def _local_tag(tag: str, repo_root) -> None:
    """Create an annotated tag locally WITHOUT pushing."""
    subprocess.run(["git", "tag", "-a", tag, "-m", f"remediation {tag}"],
                   cwd=str(repo_root), check=True, capture_output=True, text=True)


def _commit_dataset(entry, repo_root, message) -> None:
    """Stage the dataset's regenerated outputs + metadata and commit."""
    topic = entry["topic"]
    subprocess.run(["git", "add", f"{topic}/data/distribution", f"{topic}/pipeline.yaml"],
                   cwd=str(repo_root), check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "dashboard_data"], cwd=str(repo_root),
                   check=False, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", message], cwd=str(repo_root),
                   check=True, capture_output=True, text=True)


def _inflation_reduced(before, after) -> bool:
    """True if the count-inflation signature dropped (or there was none to begin with)."""
    b = before["conservation"]["max_ratio"]
    a = after["conservation"]["max_ratio"]
    if b is None or a is None:
        return True
    return a < b


def regenerate_dataset(entry, *, repo_root, dry_run: bool):
    """Regenerate one dataset (or, in dry_run, only report BEFORE acceptance).

    Real-mode (dry_run=False) is exercised by Phase 3b. It must run with
    SDC_NO_PUBLISH set and is responsible for: running each entrypoint via
    run_entrypoint, re-running acceptance (AFTER), gating on AFTER pass AND
    AFTER.max_ratio < BEFORE.max_ratio, version-bumping local-patch
    (update_version(topic, force_level="patch", auto_tag=False, auto_release=False)),
    and committing. 3a only validates the dry-run path.
    """
    repo_root = Path(repo_root)
    before = _acceptance(entry, repo_root)
    report = {
        "topic": entry["topic"], "dry_run": dry_run,
        "before": before, "regenerated": False, "committed": False,
    }
    if dry_run:
        return report
    topic_dir = Path(repo_root) / entry["topic"]
    for ep in entry["entrypoints"]:
        mod_rel, _, func = ep.partition(":")
        run_entrypoint(topic_dir / mod_rel, func)
    after = _acceptance(entry, repo_root)
    report["after"] = after
    report["regenerated"] = True
    if after["status"] == "fail" or not _inflation_reduced(before, after):
        report["gate"] = "failed"
        return report
    result = update_version(topic_dir, force_level="patch", auto_tag=False, auto_release=False)
    if result is not None and getattr(result, "tag", None):
        _local_tag(result.tag, repo_root)
    _commit_dataset(entry, repo_root,
                    f"fix({entry['topic']}): regenerate census10to20 _geo20 (remediation)")
    report["committed"] = True
    return report
