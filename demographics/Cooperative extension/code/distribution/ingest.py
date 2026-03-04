"""Entrypoint for cooperative extension ingest.

This pipeline is implemented in prepare.py (ACS + County Health Rankings),
so ingest.py simply delegates to that run() function for consistency with
other demographics pipelines.
"""

from __future__ import annotations

from prepare import run

if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
