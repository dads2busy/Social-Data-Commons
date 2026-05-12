"""Pytest module-isolation for this pipeline's transforms.py.

Four energy pipelines share a `transforms.py` name. pytest's default
rootdir collection collides. `--import-mode=importlib` is set in
pyproject.toml; this file inserts the test directory into sys.path and
evicts any cached `transforms` module so each test run gets the right one.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.modules.pop("transforms", None)
