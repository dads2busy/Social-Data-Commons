"""Driver for the census10to20 data regeneration (Phase 3b runs this)."""
from __future__ import annotations

import glob as _glob
import importlib.util
import sys
from pathlib import Path

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


def _dist_file(entry, repo_root):
    matches = sorted(_glob.glob(str(Path(repo_root) / entry["topic"] / entry["dist_glob"])))
    if not matches:
        raise FileNotFoundError(f"{entry['topic']}: no file matches {entry['dist_glob']}")
    return matches[-1]


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
    before = check_conservation(_dist_file(entry, repo_root))
    report = {
        "topic": entry["topic"], "dry_run": dry_run,
        "before": before, "regenerated": False, "committed": False,
    }
    if dry_run:
        return report
    raise NotImplementedError(
        "real-mode regeneration is executed in Phase 3b (run with SDC_NO_PUBLISH=1)"
    )
