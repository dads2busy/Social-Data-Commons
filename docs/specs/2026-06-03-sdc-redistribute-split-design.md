# Split `sdc-redistribute` into its own package — Design

## Overview

Extract the spatial value-redistribution code from `sdc-core` into a standalone,
PyPI-publishable package `sdc-redistribute`, following the established
`sdc-census10to20` template: new package owns the canonical code, `sdc-core`
keeps a transparent re-export shim so existing imports are unchanged. Full arc —
package + shim + tests + docs section + publish workflow. The actual PyPI release
is gated on the user's one-time Trusted Publishing setup.

Specs this builds on: `feedback_standalone_package_split_pattern` (Option A
shim), `project_pypi_publish_flow` (tag-derived hatch-vcs + `root=../..`),
`project_umbrella_docs_site` (one umbrella docs site, add a section).

## Decisions settled in brainstorming

- **Contents: `redistribute.py` only.** `parcels.py` stays in `sdc-core` — it is
  the (currently unused, httpx-based) parcel-centroid *fetcher*; `redistribute.py`
  is decoupled from it (it reads parquet files from disk via its own
  `_load_parcels`, never imports `parcels.py`). Redistribute functions fully
  without it; the `parcels` redistribution method is itself optional
  (`methods` defaults to `["direct"]`).
- **Full arc:** package + shim + tests + docs section + publish workflow.
- **pyarrow is a plain dependency** (not a `[parcels]` extra).
- **Tag prefix `redistribute-v`**, first release `v0.1.0`.

## Current state (verified)

- `packages/sdc-core/src/sdc_core/redistribute.py` — public API:
  `redistribute_direct`, `redistribute_parcels`, `run_redistribution`
  (plus private helpers `_load_geo`, `_load_parcels`, `_strip_geo_suffix`).
- **Not** re-exported in `sdc_core.__all__`; consumed via direct module import.
- **One consumer in the monorepo:**
  `demographics/Geographic Mobility (HOI)/code/distribution/prepare.py` →
  `from sdc_core.redistribute import run_redistribution`.
- Hard deps: **geopandas** (`read_file`, `.geometry.area`, `overlay`) and
  **pyarrow** (via `pd.read_parquet` in the parcels path). pandas throughout.
- Tests: `packages/sdc-core/tests/test_redistribute.py`.

## Package layout

```
packages/sdc-redistribute/
  pyproject.toml
  README.md
  CHANGELOG.md
  src/sdc_redistribute/
    __init__.py            # eager re-exports + __all__ + __version__
    redistribute.py        # git mv from sdc-core, imports unchanged internally
  tests/
    test_redistribute.py   # git mv, imports updated to sdc_redistribute
```

`__init__.py`:

```python
"""sdc-redistribute: redistribute values between geographies."""

from importlib.metadata import PackageNotFoundError, version

from sdc_redistribute.redistribute import (
    redistribute_direct,
    redistribute_parcels,
    run_redistribution,
)

try:
    __version__ = version("sdc-redistribute")
except PackageNotFoundError:  # running from a raw checkout, not installed
    __version__ = "0.0.0"

__all__ = [
    "redistribute_direct",
    "redistribute_parcels",
    "run_redistribution",
]
```

Eager imports are required (mkdocstrings/griffe static analysis).

## pyproject.toml (new package)

Mirror `sdc-census10to20`'s metadata shape, adjusted:

- `name = "sdc-redistribute"`, `dynamic = ["version"]`, MIT, author Aaron
  Schroeder, `requires-python = ">=3.10"`.
- `dependencies = ["geopandas>=1.0", "pandas>=2.0", "pyarrow>=15"]`.
- `[project.optional-dependencies]` `dev = ["pytest>=8", "ruff>=0.8"]`,
  `docs = ["mkdocs>=1.6", "mkdocs-material>=9.5", "mkdocstrings[python]>=0.24"]`.
- `[project.urls]` → umbrella docs + monorepo repo:
  - Homepage / Documentation: `https://dads2busy.github.io/Social-Data-Commons/packages/sdc-redistribute/`
  - Repository: `https://github.com/dads2busy/Social-Data-Commons`
  - Issues: `https://github.com/dads2busy/Social-Data-Commons/issues`
  - Changelog: `https://github.com/dads2busy/Social-Data-Commons/blob/main/packages/sdc-redistribute/CHANGELOG.md`
- Build + versioning:

  ```toml
  [build-system]
  requires = ["hatchling", "hatch-vcs"]
  build-backend = "hatchling.build"

  [tool.hatch.version]
  source = "vcs"
  tag-pattern = "redistribute-v(?P<version>.+)"

  [tool.hatch.version.raw-options]
  # Package lives in a monorepo subdir; point setuptools_scm at the repo root.
  root = "../.."
  git_describe_command = ["git", "describe", "--dirty", "--tags", "--long", "--match", "redistribute-v*"]

  [tool.hatch.build.targets.wheel]
  packages = ["src/sdc_redistribute"]
  ```

## sdc-core re-export shim (Option A)

Replace the body of `packages/sdc-core/src/sdc_core/redistribute.py` with:

```python
"""Back-compat shim. Canonical code now lives in the sdc-redistribute package."""

from sdc_redistribute import (  # noqa: F401
    redistribute_direct,
    redistribute_parcels,
    run_redistribution,
)
```

Existing `from sdc_core.redistribute import run_redistribution` (the HOI pipeline)
keeps working.

Wire the dependency:

- `packages/sdc-core/pyproject.toml`: add `"sdc-redistribute"` to `dependencies`
  and `sdc-redistribute = { workspace = true }` to `[tool.uv.sources]`.
- Root `pyproject.toml`: add `sdc-redistribute = { workspace = true }` to
  `[tool.uv.sources]` (workspace members already auto-discovered via
  `packages/*`). Add `sdc-redistribute` to the root `sdc` package `dependencies`
  for parity with the other members.

**Side effect (flagged, not changed):** `sdc-redistribute` requires geopandas, so
`sdc-core` now pulls geopandas transitively through the shim. The existing
`sdc-core[geo]` optional extra is left as-is.

## Publish workflow

`.github/workflows/publish-redistribute.yml` — copy of `publish-census10to20.yml`,
changed:

- `name: Publish sdc-redistribute to PyPI`
- trigger tag: `redistribute-v*`
- `url: https://pypi.org/p/sdc-redistribute`
- `working-directory: packages/sdc-redistribute`
- `packages-dir: packages/sdc-redistribute/dist/`
- keeps: single `publish` job, `environment: pypi`, `id-token: write`,
  `checkout@v6` with `fetch-depth: 0`, `setup-python@v6`, `python -m build`,
  `pypa/gh-action-pypi-publish@release/v1`.

## Docs section

- `docsite/packages/sdc-redistribute/index.md` — overview + install.
- `docsite/packages/sdc-redistribute/reference/redistribute.md` — body
  `::: sdc_redistribute`.
- Root `mkdocs.yml`: add a `sdc-redistribute` nav block (placed between
  `sdc-core` and `sdc-census10to20`), and add `packages/sdc-redistribute/src` to
  the mkdocstrings `paths` list.

## Verification / success criteria

- `from sdc_core.redistribute import run_redistribution` resolves (shim intact).
- `from sdc_redistribute import redistribute_direct, redistribute_parcels, run_redistribution`
  resolves.
- Moved `test_redistribute.py` passes against `sdc_redistribute`; full `sdc-core`
  test suite still passes.
- `uv lock` consistent; workspace resolves.
- `mkdocs build --strict` clean with the new section.
- With a temp `redistribute-v0.1.0` tag on a clean tree, `python -m build`
  produces `sdc_redistribute-0.1.0` sdist + wheel (not a `.dev`/`+d<date>`
  version); `twine check` PASSED. Temp tag deleted after.
- The HOI Geographic Mobility `prepare.py` import is unbroken (grep + import
  check).

## Out of scope

- `parcels.py` (stays in `sdc-core`).
- The actual PyPI release — needs a separate Trusted Publishing pending-publisher
  registration (project `sdc-redistribute`, workflow `publish-redistribute.yml`,
  env `pypi`) done by the user, then a `redistribute-v0.1.0` tag push.
- Any change to the HOI pipeline beyond confirming the import.
- Publishing `sdc-core`.
