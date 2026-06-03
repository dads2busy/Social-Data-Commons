# Split `sdc-catchment` into its own package — Design

## Overview

Extract the floating-catchment-area spatial-accessibility code from `sdc-core`
into a standalone, PyPI-publishable package `sdc-catchment`, following the now-
established split arc (`sdc-census10to20`, `sdc-redistribute`): new package owns
the canonical code, `sdc-core` keeps a re-export shim. Full arc — package + shim
+ tests + docs section + publish workflow. The actual PyPI release is gated on
the user's one-time Trusted Publishing registration.

Builds on: `feedback_standalone_package_split_pattern` (Option A shim),
`project_pypi_publish_flow` (tag-derived hatch-vcs + `root=../..`),
`project_umbrella_docs_site` (one umbrella docs site, add a section). The
original in-`sdc-core` module design is `docs/specs/2026-03-20-catchment-module-design.md`.

## Key difference from the redistribute split

`catchment` **is part of `sdc-core`'s public API** — `sdc_core/__init__.py`
re-exports all of its public names. `redistribute` was not. Consequences:

- The shim must re-export the **full** public surface (7 names), not just the
  functions a consumer happens to use.
- `sdc_core/__init__.py` needs **zero changes**: it keeps importing those names
  from `sdc_core.catchment` (now the shim), so both `from sdc_core import
  catchment_ratio` and `from sdc_core.catchment import catchment_ratio` keep
  working.

## Decisions settled in brainstorming

- **Full arc:** package + shim + tests + docs section + publish workflow.
- **Dependencies: `numpy>=1.26`, `scipy>=1.11`, `pandas>=2.0`.** No geopandas,
  no pyarrow, no scikit-learn.
- **Shim preserves all 7 public names; `sdc_core/__init__.py` unchanged.**
- **Tag prefix `catchment-v`**, first release `v0.1.0`.

## Current state (verified)

- `packages/sdc-core/src/sdc_core/catchment.py` — **self-contained** (no
  `sdc_core` imports). Public surface (7):
  - `WeightSpec` (type alias), `KERNELS` (dict of kernel callables)
  - `euclidean_cost`, `catchment_weight`, `catchment_ratio`,
    `catchment_connections`, `catchment_network`
- `sdc_core/__init__.py` imports all 7 from `sdc_core.catchment` and lists the
  functions + `KERNELS` + `WeightSpec` in `__all__`.
- Hard deps: numpy, scipy (`scipy.sparse`, `scipy.spatial.distance.cdist`),
  pandas.
- **Three consumers**, all `from sdc_core.catchment import catchment_ratio`:
  - `health/Health Care Services/code/compute_service_access.py`
  - `education/Daycare Accessibility/code/distribution/script.py`
  - `education/Daycare Accessibility/code/distribution/ingest.py`
- Tests: `packages/sdc-core/tests/test_catchment.py`.

## Package layout

```
packages/sdc-catchment/
  pyproject.toml
  README.md
  CHANGELOG.md
  src/sdc_catchment/
    __init__.py            # eager re-exports + __all__ + __version__
    catchment.py           # git mv from sdc-core, body unchanged
  tests/
    test_catchment.py      # git mv, import updated to sdc_catchment
```

`__init__.py`:

```python
"""sdc-catchment: floating catchment area spatial accessibility."""

from importlib.metadata import PackageNotFoundError, version

from sdc_catchment.catchment import (
    KERNELS,
    WeightSpec,
    catchment_connections,
    catchment_network,
    catchment_ratio,
    catchment_weight,
    euclidean_cost,
)

try:
    __version__ = version("sdc-catchment")
except PackageNotFoundError:  # running from a raw checkout, not installed
    __version__ = "0.0.0"

__all__ = [
    "KERNELS",
    "WeightSpec",
    "catchment_connections",
    "catchment_network",
    "catchment_ratio",
    "catchment_weight",
    "euclidean_cost",
]
```

Eager imports required (mkdocstrings/griffe static analysis).

## pyproject.toml (new package)

Mirror `sdc-redistribute`'s shape, adjusted:

- `name = "sdc-catchment"`, `dynamic = ["version"]`, MIT, author Aaron Schroeder,
  `requires-python = ">=3.10"`.
- `dependencies = ["numpy>=1.26", "scipy>=1.11", "pandas>=2.0"]`.
- `keywords = ["accessibility", "2sfca", "e2sfca", "catchment", "spatial", "gis"]`.
- `[project.optional-dependencies]` `dev = ["pytest>=8", "ruff>=0.8"]`,
  `docs = ["mkdocs>=1.6", "mkdocs-material>=9.5", "mkdocstrings[python]>=0.24"]`.
- `[project.urls]` → umbrella docs + monorepo (Homepage/Documentation
  `.../packages/sdc-catchment/`, Repository/Issues on
  `dads2busy/Social-Data-Commons`, Changelog at
  `.../blob/main/packages/sdc-catchment/CHANGELOG.md`).
- Build + versioning:

  ```toml
  [build-system]
  requires = ["hatchling", "hatch-vcs"]
  build-backend = "hatchling.build"

  [tool.hatch.version]
  source = "vcs"
  tag-pattern = "catchment-v(?P<version>.+)"

  [tool.hatch.version.raw-options]
  # Package lives in a monorepo subdir; point setuptools_scm at the repo root.
  root = "../.."
  git_describe_command = ["git", "describe", "--dirty", "--tags", "--long", "--match", "catchment-v*"]

  [tool.hatch.build.targets.wheel]
  packages = ["src/sdc_catchment"]
  ```

## sdc-core re-export shim

Replace the body of `packages/sdc-core/src/sdc_core/catchment.py` with:

```python
"""Back-compat shim. Canonical code now lives in the sdc-catchment package."""

from sdc_catchment import (  # noqa: F401
    KERNELS,
    WeightSpec,
    catchment_connections,
    catchment_network,
    catchment_ratio,
    catchment_weight,
    euclidean_cost,
)
```

`sdc_core/__init__.py` is **not** modified — it continues importing the 7 names
from `sdc_core.catchment` (the shim), so the top-level `sdc_core` exports and the
three direct consumers all keep working.

Wire the dependency:

- `packages/sdc-core/pyproject.toml`: add `"sdc-catchment"` to `dependencies` and
  `sdc-catchment = { workspace = true }` to `[tool.uv.sources]`.
- Root `pyproject.toml`: add `"sdc-catchment"` to the `sdc` `dependencies` and
  `sdc-catchment = { workspace = true }` to `[tool.uv.sources]`.

## Publish workflow

`.github/workflows/publish-catchment.yml` — copy of `publish-redistribute.yml`:
`name: Publish sdc-catchment to PyPI`, trigger tag `catchment-v*`,
`url: https://pypi.org/p/sdc-catchment`, `working-directory: packages/sdc-catchment`,
`packages-dir: packages/sdc-catchment/dist/`; single `publish` job,
`environment: pypi`, `id-token: write`, `checkout@v6` + `fetch-depth: 0`,
`setup-python@v6`, `python -m build`, `pypa/gh-action-pypi-publish@release/v1`.

## Docs section

- `docsite/packages/sdc-catchment/index.md` — overview (floating catchment area
  accessibility: 2SFCA / E2SFCA / KD2SFCA / 3SFCA / modified-2SFCA / balanced /
  commute-based, all as parameter variations of `catchment_ratio`) + install.
- `docsite/packages/sdc-catchment/reference/catchment.md` — body `::: sdc_catchment`.
- Root `mkdocs.yml`: add a `sdc-catchment` nav block (after `sdc-core`, before
  `sdc-redistribute` — alphabetical), and add `packages/sdc-catchment/src` to the
  mkdocstrings `paths`.

## Verification / success criteria

- `from sdc_catchment import catchment_ratio` resolves.
- `from sdc_core.catchment import catchment_ratio` resolves (shim), and
  `from sdc_core import catchment_ratio` resolves (top-level, via unchanged
  `__init__`); the shimmed object is the same as the package's.
- Moved `test_catchment.py` passes against `sdc_catchment`; full `sdc-core` test
  suite still passes.
- All three consumer files parse and their imports resolve.
- `uv lock` consistent; `mkdocs build --strict` clean with the new section.
- With a temp `catchment-v0.1.0` tag on a clean tree, `python -m build` produces
  `sdc_catchment-0.1.0` sdist + wheel (not `.dev`/`+d<date>`); `twine check` PASSED.

## Out of scope

- The actual PyPI release — needs a separate Trusted Publishing pending-publisher
  registration (project `sdc-catchment`, workflow `publish-catchment.yml`, env
  `pypi`; the GitHub `pypi` environment is reused) done by the user, then a
  `catchment-v0.1.0` tag push.
- Any change to the three consumer pipelines beyond confirming their imports.
- Publishing `sdc-core`.
