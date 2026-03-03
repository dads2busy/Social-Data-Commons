"""Entrypoint for school funding adequacy ingest.

The ingest and prepare steps are combined in prepare.py since data comes
from a single external source (County Health Rankings).
"""

from __future__ import annotations

from prepare import run

if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
