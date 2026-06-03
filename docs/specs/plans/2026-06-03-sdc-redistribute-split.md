# Split sdc-redistribute Into Its Own Package — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract `redistribute.py` from `sdc-core` into a standalone, PyPI-publishable `sdc-redistribute` package, with a back-compat shim, migrated tests, a docs section, and a publish workflow.

**Architecture:** New package owns the canonical code (`git mv`); `sdc-core/redistribute.py` becomes a thin re-export shim; `sdc-core` + root declare `sdc-redistribute` as a workspace dependency. Tag-derived hatch-vcs versioning (tag prefix `redistribute-v`), one publish workflow per package, one umbrella docs section. Mirrors the `sdc-census10to20` split + publish flow exactly.

**Tech Stack:** uv workspace, hatchling + hatch-vcs, geopandas/pandas/pyarrow, MkDocs + mkdocstrings, GitHub Actions OIDC, pytest.

**Spec:** `docs/specs/2026-06-03-sdc-redistribute-split-design.md`

**Branch:** `feat/sdc-redistribute-split` (already created).

**Verification note:** Run all commands from the repo root
`/Users/ads7fg/git/social-data-commons`. Build verification uses a **temporary**
`redistribute-v0.1.0` tag (deleted in the same step); the real release tag is
pushed later, after merge + Trusted Publishing setup.

---

## File Structure

**Create:**
- `packages/sdc-redistribute/pyproject.toml`
- `packages/sdc-redistribute/README.md`
- `packages/sdc-redistribute/CHANGELOG.md`
- `packages/sdc-redistribute/src/sdc_redistribute/__init__.py`
- `.github/workflows/publish-redistribute.yml`
- `docsite/packages/sdc-redistribute/index.md`
- `docsite/packages/sdc-redistribute/reference/redistribute.md`

**Move (git mv):**
- `packages/sdc-core/src/sdc_core/redistribute.py` → `packages/sdc-redistribute/src/sdc_redistribute/redistribute.py`
- `packages/sdc-core/tests/test_redistribute.py` → `packages/sdc-redistribute/tests/test_redistribute.py`

**Recreate (as shim):**
- `packages/sdc-core/src/sdc_core/redistribute.py` (new file at old path, shim body)

**Modify:**
- `packages/sdc-redistribute/tests/test_redistribute.py` — import `sdc_redistribute`
- `packages/sdc-core/pyproject.toml` — add `sdc-redistribute` dep + source
- `pyproject.toml` (root) — add `sdc-redistribute` dep + source
- `mkdocs.yml` — nav block + mkdocstrings path

**Untouched:** `parcels.py`, the HOI pipeline, `sdc-core`'s `[geo]` extra.

---

## Task 1: Create the package, move the code, add the shim

This task is atomic — the code move + shim + dependency wiring must land together
(an intermediate state with `redistribute.py` gone and no shim would break the
HOI pipeline import). One commit at the end.

**Files:** see File Structure (everything except docs + workflow).

- [ ] **Step 1: Create the package directory tree**

```bash
mkdir -p packages/sdc-redistribute/src/sdc_redistribute packages/sdc-redistribute/tests
```

- [ ] **Step 2: Write `packages/sdc-redistribute/pyproject.toml`**

```toml
[project]
name = "sdc-redistribute"
dynamic = ["version"]
description = "Redistribute values between geographies (direct area-weighted and parcel-weighted)"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [
    { name = "Aaron Schroeder", email = "ads7fg@virginia.edu" },
]
keywords = ["census", "geography", "redistribution", "areal-interpolation", "gis"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Science/Research",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Scientific/Engineering :: GIS",
    "Topic :: Scientific/Engineering :: Information Analysis",
]
dependencies = [
    "geopandas>=1.0",
    "pandas>=2.0",
    "pyarrow>=15",
]

[project.urls]
Homepage = "https://dads2busy.github.io/Social-Data-Commons/packages/sdc-redistribute/"
Documentation = "https://dads2busy.github.io/Social-Data-Commons/packages/sdc-redistribute/"
Repository = "https://github.com/dads2busy/Social-Data-Commons"
Issues = "https://github.com/dads2busy/Social-Data-Commons/issues"
Changelog = "https://github.com/dads2busy/Social-Data-Commons/blob/main/packages/sdc-redistribute/CHANGELOG.md"

[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.8"]
docs = [
    "mkdocs>=1.6",
    "mkdocs-material>=9.5",
    "mkdocstrings[python]>=0.24",
]

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

[tool.ruff]
line-length = 100
```

- [ ] **Step 3: Write `packages/sdc-redistribute/README.md`**

```markdown
# sdc-redistribute

Redistribute values between geographies — direct area-weighted interpolation and
parcel-weighted redistribution.

Part of the [Social Data Commons](https://github.com/dads2busy/Social-Data-Commons)
toolkit. Extracted from `sdc_core.redistribute`; used by SDC pipelines to move
measures from one geographic vintage/level onto another (e.g. 2010 tracts → 2020
block groups), producing `_geo10`/`_geo20`-suffixed measures.

## Install

```bash
uv add sdc-redistribute   # or: pip install sdc-redistribute
```

## Public API

- `redistribute_direct` — area-proportional redistribution between two geographies.
- `redistribute_parcels` — parcel-centroid-weighted redistribution.
- `run_redistribution` — high-level wrapper driven by a pipeline.yaml config block.

See the [documentation](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-redistribute/).
```

- [ ] **Step 4: Write `packages/sdc-redistribute/CHANGELOG.md`**

```markdown
# Changelog

All notable changes to this project will be documented in this file. The format
is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-03

### Added
- Initial release. Extracted from `sdc_core.redistribute`:
  `redistribute_direct`, `redistribute_parcels`, and the `run_redistribution`
  pipeline wrapper.
- Tag-derived versioning (hatch-vcs) and PyPI Trusted Publishing on a
  `redistribute-v*` tag.
```

- [ ] **Step 5: Move the implementation into the package**

```bash
git mv packages/sdc-core/src/sdc_core/redistribute.py packages/sdc-redistribute/src/sdc_redistribute/redistribute.py
```

(The moved file's internal imports are stdlib + pandas + lazy geopandas — no
`sdc_core` references — so no edits to its body are needed.)

- [ ] **Step 6: Write the package `__init__.py`**

`packages/sdc-redistribute/src/sdc_redistribute/__init__.py`:

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

- [ ] **Step 7: Move the tests and update their import**

```bash
git mv packages/sdc-core/tests/test_redistribute.py packages/sdc-redistribute/tests/test_redistribute.py
```

Then in `packages/sdc-redistribute/tests/test_redistribute.py`, change the import (currently line 11):

```python
from sdc_core.redistribute import redistribute_direct, redistribute_parcels
```

to:

```python
from sdc_redistribute import redistribute_direct, redistribute_parcels
```

- [ ] **Step 8: Recreate `sdc_core/redistribute.py` as a shim**

Create a new `packages/sdc-core/src/sdc_core/redistribute.py` with exactly:

```python
"""Back-compat shim. Canonical code now lives in the sdc-redistribute package."""

from sdc_redistribute import (  # noqa: F401
    redistribute_direct,
    redistribute_parcels,
    run_redistribution,
)
```

- [ ] **Step 9: Wire `sdc-redistribute` into `sdc-core`'s dependencies**

In `packages/sdc-core/pyproject.toml`, add `"sdc-redistribute"` to the
`dependencies` list (after `"sdc-census10to20"`):

```toml
dependencies = [
    "httpx>=0.27",
    "pandas>=2.2",
    "click>=8.1",
    "pyyaml>=6.0",
    "tqdm>=4.66",
    "python-dotenv>=1.2.1",
    "sdc-census10to20",
    "sdc-redistribute",
]
```

and add the workspace source under `[tool.uv.sources]`:

```toml
[tool.uv.sources]
sdc-census10to20 = { workspace = true }
sdc-redistribute = { workspace = true }
```

- [ ] **Step 10: Wire `sdc-redistribute` into the root workspace**

In the root `pyproject.toml`, add `"sdc-redistribute"` to the `sdc` package
`dependencies` (after `"sdc-census10to20"`):

```toml
    "sdc-core",
    "sdc-census10to20",
    "sdc-redistribute",
    "xlrd>=2.0.2",
```

and add the source under the root `[tool.uv.sources]`:

```toml
[tool.uv.sources]
sdc-core = { workspace = true }
sdc-census10to20 = { workspace = true }
sdc-redistribute = { workspace = true }
```

- [ ] **Step 11: Re-lock the workspace**

Run: `uv lock`
Expected: resolves successfully (it picks up the new `sdc-redistribute` member). The lockfile is updated.

- [ ] **Step 12: Verify both import paths resolve and tests pass**

```bash
uv run --group dev python -c "from sdc_redistribute import run_redistribution; from sdc_core.redistribute import run_redistribution as shim; print('ok', run_redistribution is shim)"
uv run --group dev pytest packages/sdc-redistribute/tests packages/sdc-core/tests -q 2>&1 | tail -5
```

Expected: `ok True` (the shim re-exports the same object), and all tests pass
(the redistribute tests now run under the new package; sdc-core tests still pass).

- [ ] **Step 13: Confirm the real consumer still imports cleanly**

```bash
uv run --group dev python -c "import ast; ast.parse(open('demographics/Geographic Mobility (HOI)/code/distribution/prepare.py').read()); print('HOI prepare.py parses')"
grep -n "from sdc_core.redistribute import" "demographics/Geographic Mobility (HOI)/code/distribution/prepare.py"
```

Expected: prints `HOI prepare.py parses` and shows the unchanged import line (it resolves through the shim).

- [ ] **Step 14: Commit**

```bash
git add -A
git commit -m "feat: extract sdc-redistribute package with sdc-core shim"
```

---

## Task 2: Docs section

**Files:**
- Create: `docsite/packages/sdc-redistribute/index.md`, `docsite/packages/sdc-redistribute/reference/redistribute.md`
- Modify: `mkdocs.yml`

- [ ] **Step 1: Create the overview page**

`docsite/packages/sdc-redistribute/index.md`:

```markdown
# sdc-redistribute

Redistribute values between geographies — direct area-weighted interpolation and
parcel-weighted redistribution. Extracted from `sdc_core.redistribute`.

## Install

```bash
uv add sdc-redistribute   # or: pip install sdc-redistribute
```

## Public API

| Function | What it does |
| --- | --- |
| `redistribute_direct` | Area-proportional redistribution between two geographies (pass-through for nested, area-weighted for overlapping). |
| `redistribute_parcels` | Parcel-centroid-weighted redistribution. |
| `run_redistribution` | High-level wrapper driven by a `pipeline.yaml` `redistribution` config block; handles `_geo10`/`_geo20` suffix conventions. |

See the **Reference** page for the full API.
```

- [ ] **Step 2: Create the reference page**

`docsite/packages/sdc-redistribute/reference/redistribute.md`:

```markdown
# Redistribute

::: sdc_redistribute
```

- [ ] **Step 3: Add the mkdocstrings path and nav block to `mkdocs.yml`**

In `mkdocs.yml`, add `packages/sdc-redistribute/src` to the mkdocstrings `paths`
list:

```yaml
          paths: [packages/sdc-core/src, packages/sdc-redistribute/src, packages/sdc-census10to20/src]
```

and insert a nav block between the `sdc-core` and `sdc-census10to20` blocks:

```yaml
  - sdc-redistribute:
      - Overview: packages/sdc-redistribute/index.md
      - Reference:
          - Redistribute: packages/sdc-redistribute/reference/redistribute.md
```

- [ ] **Step 4: Build the docs strictly**

Run: `uv run --group docs mkdocs build --strict 2>&1 | grep -E "WARNING|ERROR|Aborted|Documentation built"`
Expected: `Documentation built in N seconds`, no warnings (the `::: sdc_redistribute` reference resolves).

- [ ] **Step 5: Commit**

```bash
git add docsite/packages/sdc-redistribute mkdocs.yml
git commit -m "docs: add sdc-redistribute umbrella docs section"
```

---

## Task 3: Publish workflow

**Files:**
- Create: `.github/workflows/publish-redistribute.yml`

- [ ] **Step 1: Create the workflow**

`.github/workflows/publish-redistribute.yml`:

```yaml
name: Publish sdc-redistribute to PyPI

on:
  push:
    tags:
      - "redistribute-v*"

jobs:
  publish:
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/sdc-redistribute
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
        working-directory: packages/sdc-redistribute
        run: |
          python -m pip install --upgrade build
          python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: packages/sdc-redistribute/dist/
```

- [ ] **Step 2: Validate the workflow YAML**

Run: `uv run --group docs python -c "import yaml; yaml.safe_load(open('.github/workflows/publish-redistribute.yml')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/publish-redistribute.yml
git commit -m "ci(publish): add sdc-redistribute PyPI workflow"
```

---

## Task 4: Final verification + release handoff

**Files:** none (verification + handoff).

- [ ] **Step 1: Tag-derived build produces exactly 0.1.0**

```bash
git tag redistribute-v0.1.0
cd packages/sdc-redistribute && rm -rf dist && uvx --from build pyproject-build 2>&1 | tail -1 && ls dist/
cd /Users/ads7fg/git/social-data-commons
```

Expected: `Successfully built sdc_redistribute-0.1.0.tar.gz and sdc_redistribute-0.1.0-py3-none-any.whl`. A `.dev`/`+d<date>` suffix means a dirty tree or the tag isn't on HEAD — fix before continuing.

- [ ] **Step 2: twine check the metadata**

```bash
uv run --no-project --with twine python -m twine check packages/sdc-redistribute/dist/*
```

Expected: both sdist and wheel `PASSED`.

- [ ] **Step 3: Delete the temp tag and clean artifacts**

```bash
git tag -d redistribute-v0.1.0
rm -rf packages/sdc-redistribute/dist
```

Expected: `Deleted tag 'redistribute-v0.1.0'`.

- [ ] **Step 4: Finish the development branch**

Use the **superpowers:finishing-a-development-branch** skill to merge
`feat/sdc-redistribute-split` to `main`, verify tests on the merged result, and
push. Merging/pushing does NOT publish (only a `redistribute-v*` tag triggers the
workflow).

- [ ] **Step 5: User completes Trusted Publishing setup (manual, one-time)**

Tell the user to register a **pending publisher** at
<https://pypi.org/manage/account/publishing/>:
- PyPI Project Name: `sdc-redistribute`
- Owner: `dads2busy`
- Repository name: `Social-Data-Commons`
- Workflow name: `publish-redistribute.yml`
- Environment name: `pypi`

(The GitHub `pypi` environment already exists from the census10to20 release and
is reused.) Do not push the release tag until the pending publisher is registered.

- [ ] **Step 6: Cut the release (after Step 5 confirmed)**

```bash
git checkout main && git pull
git tag redistribute-v0.1.0
git push origin redistribute-v0.1.0
gh run watch "$(gh run list --workflow=publish-redistribute.yml --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status --interval 15
```

Expected: green run.

- [ ] **Step 7: Verify live on PyPI**

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" https://pypi.org/pypi/sdc-redistribute/0.1.0/json
cd /tmp && uv run --no-project --refresh-package sdc-redistribute --with sdc-redistribute \
  python -c "import sdc_redistribute as m; print(m.__version__)"
```

Expected: `HTTP 200`, then `0.1.0`. (Run the install from `/tmp` so uv resolves
from PyPI, not the local workspace.)

---

## Self-Review

- **Spec coverage:** package layout + `__init__` eager imports → Task 1 §1,§6. pyproject (deps geopandas/pandas/pyarrow, hatch-vcs + `root=../..` + `redistribute-v` pattern, urls) → Task 1 §2. README/CHANGELOG → Task 1 §3,§4. `git mv` code + tests + import update → Task 1 §5,§7. shim → Task 1 §8. sdc-core + root wiring → Task 1 §9,§10. consumer unbroken → Task 1 §13. docs section + nav + mkdocstrings path → Task 2. publish workflow → Task 3. build/twine/release/PyPI verification → Task 4. All spec sections covered.
- **Placeholder scan:** none — every code step has full content; every command has expected output. The `"0.0.0"` fallback is intentional.
- **Consistency:** package import name `sdc_redistribute` and PyPI/dist name `sdc-redistribute` used consistently; the three public functions `redistribute_direct` / `redistribute_parcels` / `run_redistribution` match across `__init__`, shim, tests, README, and docs; tag prefix `redistribute-v` identical across pyproject `tag-pattern`, `--match`, workflow trigger, and every tag command; environment `pypi` and workflow filename `publish-redistribute.yml` match between the workflow and the Trusted Publishing fields.
- **Tag hygiene:** the only tag created before Task 4 §6 is the temp one in §1, deleted in §3.
