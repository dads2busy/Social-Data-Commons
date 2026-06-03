# SDC PyPI Publish Flow — Design

## Overview

A repeatable, tag-driven release flow that publishes the standalone SDC leaf
packages to PyPI via GitHub Actions OIDC Trusted Publishing. `sdc-census10to20`
is published now; `sdc-redistribute` and `sdc-catchment` follow the same
template when they are split out of `sdc-core`. `sdc-core` itself is never
published.

This completes the publishing half of the package work begun with the umbrella
docs site (`docs/specs/2026-06-03-sdc-docs-site-design.md`).

## Decisions settled in brainstorming

- **Publish scope:** `sdc-census10to20` (now), `sdc-redistribute` + `sdc-catchment`
  (future). **NOT `sdc-core`** — it stays monorepo-internal (pipelines install it
  from the uv workspace). All publishable packages are standalone leaves
  depending only on third-party libraries (never on `sdc-core`), so there is no
  inter-package publish-ordering constraint.
- **Versioning:** tag-derived via `hatch-vcs`. The git tag is the single source
  of truth; no static version in `pyproject.toml`.
- **TestPyPI:** dropped. Tag push publishes straight to PyPI. One trusted-publisher
  registration per package; no TestPyPI account/env.
- **Workflow shape:** one self-contained workflow file per package, each
  triggered by its own tag prefix. No shared/reusable workflow.
- **First release:** `sdc-census10to20` at `v0.1.0` (tag `census10to20-v0.1.0`).
- **Workflow rename:** the current root `publish.yml` becomes
  `publish-census10to20.yml` (per-package naming for the packages to come).

## Versioning — hatch-vcs (per publishable package)

`packages/sdc-census10to20/pyproject.toml`:

- Remove the static `version = "0.1.0"`; add `dynamic = ["version"]` to
  `[project]`.
- Build system gains `hatch-vcs`:

  ```toml
  [build-system]
  requires = ["hatchling", "hatch-vcs"]
  build-backend = "hatchling.build"

  [tool.hatch.version]
  source = "vcs"
  tag-pattern = "census10to20-v(?P<version>.+)"

  [tool.hatch.version.raw-options]
  git_describe_command = ["git", "describe", "--dirty", "--tags", "--long", "--match", "census10to20-v*"]
  ```

  The `--match census10to20-v*` is **essential in a monorepo**: without it,
  `git describe` would pick up a future `redistribute-v*` / `catchment-v*` tag
  and compute the wrong version for this package.

- `src/sdc_census10to20/__init__.py`: replace the hardcoded
  `__version__ = "0.1.0"` with a metadata lookup so the runtime version tracks
  the published version:

  ```python
  from importlib.metadata import PackageNotFoundError, version

  try:
      __version__ = version("sdc-census10to20")
  except PackageNotFoundError:  # not installed (e.g. running from a raw checkout)
      __version__ = "0.0.0"
  ```

  This keeps eager imports intact (no impact on mkdocstrings reference pages).

**`hatch-vcs` is a new build-time dependency.** It is only a `build-system`
requirement (fetched in an isolated build env by `python -m build`), not a
runtime or workspace dependency — no `uv add` needed, no change to the lockfile's
runtime graph.

## Publish workflow

Rename `.github/workflows/publish.yml` →
`.github/workflows/publish-census10to20.yml`. Collapse from three jobs
(build / publish-testpypi / publish-pypi) to a single `publish` job, since
dropping TestPyPI removes the artifact handoff:

```yaml
name: Publish sdc-census10to20 to PyPI

on:
  push:
    tags:
      - "census10to20-v*"

jobs:
  publish:
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/sdc-census10to20
    permissions:
      id-token: write          # OIDC Trusted Publishing — no API tokens
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0        # hatch-vcs needs full tag history
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - name: Build wheel and sdist
        working-directory: packages/sdc-census10to20
        run: |
          python -m pip install --upgrade build
          python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: packages/sdc-census10to20/dist/
```

`fetch-depth: 0` is the critical change over the old workflow — `checkout`
defaults to a shallow clone, which has no tags, which makes `git describe` (and
thus hatch-vcs) fail.

## Metadata cleanup (prerequisite for a clean PyPI page)

`packages/sdc-census10to20/pyproject.toml` `[project.urls]` currently point at
the dead `uva-bi-sdad` standalone site/org. Replace with:

```toml
[project.urls]
Homepage      = "https://dads2busy.github.io/Social-Data-Commons/packages/sdc-census10to20/"
Documentation = "https://dads2busy.github.io/Social-Data-Commons/packages/sdc-census10to20/"
Repository    = "https://github.com/dads2busy/Social-Data-Commons"
Issues        = "https://github.com/dads2busy/Social-Data-Commons/issues"
Changelog     = "https://github.com/dads2busy/Social-Data-Commons/blob/main/packages/sdc-census10to20/CHANGELOG.md"
```

The `uva-bi-sdad` link inside `docsite/packages/sdc-census10to20/index.md` is
the genuine R-package home and stays.

## Trusted Publishing — one-time manual setup (user)

Before pushing the first tag, register a **pending publisher** at
<https://pypi.org/manage/account/publishing/>:

| Field | Value |
| --- | --- |
| PyPI Project Name | `sdc-census10to20` |
| Owner | `dads2busy` |
| Repository name | `Social-Data-Commons` |
| Workflow name | `publish-census10to20.yml` |
| Environment name | `pypi` |

And create a GitHub **environment named `pypi`** (repo Settings → Environments).
No API tokens are stored anywhere.

## Release process (developer UX, once set up)

```bash
git tag census10to20-v0.1.0
git push origin census10to20-v0.1.0
# workflow builds 0.1.0 (from the tag) and publishes to PyPI
```

## Out of scope

- Publishing `sdc-core`.
- `sdc-redistribute` / `sdc-catchment` workflows — this establishes the template
  they will copy once those packages exist.
- Automated changelog generation.
- Signing/attestations beyond `gh-action-pypi-publish` defaults (it already
  attaches PEP 740 attestations by default).

## Success criteria

- `python -m build` in `packages/sdc-census10to20` (with tags present) produces
  `sdc_census10to20-<tag-version>.tar.gz` + matching wheel, version derived from
  the git tag (not hardcoded).
- `pyproject.toml` has `dynamic = ["version"]`, hatch-vcs config with the
  `census10to20-v*` match, and corrected `[project.urls]`.
- `__version__` resolves from installed metadata.
- `.github/workflows/publish-census10to20.yml` exists (single job, `fetch-depth: 0`,
  `environment: pypi`, OIDC); old `publish.yml` is gone.
- After the user completes Trusted Publishing setup and pushes
  `census10to20-v0.1.0`, the workflow run is green and
  `https://pypi.org/project/sdc-census10to20/0.1.0/` exists and
  `pip install sdc-census10to20` works.
