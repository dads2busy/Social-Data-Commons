"""Driver for the census10to20 data regeneration (Phase 3b runs this)."""
from __future__ import annotations

import importlib.util
from pathlib import Path


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
