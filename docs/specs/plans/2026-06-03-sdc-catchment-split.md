# Split sdc-catchment Into Its Own Package — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract `catchment.py` from `sdc-core` into a standalone, PyPI-publishable `sdc-catchment` package, with a full-surface re-export shim, migrated tests, a docs section, and a publish workflow.

**Architecture:** New package owns the canonical code (`git mv`); `sdc-core/catchment.py` becomes a shim re-exporting all 7 public names, so `sdc_core/__init__.py` (which re-exports catchment) needs no change and all three consumer pipelines keep working. Tag-derived hatch-vcs versioning (tag prefix `catchment-v`), one publish workflow, one umbrella docs section. Mirrors the `sdc-redistribute` split exactly, minus geopandas.

**Tech Stack:** uv workspace, hatchling + hatch-vcs, numpy/scipy/pandas, MkDocs + mkdocstrings, GitHub Actions OIDC, pytest.

**Spec:** `docs/specs/2026-06-03-sdc-catchment-split-design.md`

**Branch:** `feat/sdc-catchment-split` (already created).

**Verification note:** Run all commands from the repo root
`/Users/ads7fg/git/social-data-commons`. Build verification uses a **temporary**
`catchment-v0.1.0` tag (deleted in the same step); the real release tag is pushed
later, after merge + Trusted Publishing setup.

---

## File Structure

**Create:**
- `packages/sdc-catchment/pyproject.toml`
- `packages/sdc-catchment/README.md`
- `packages/sdc-catchment/CHANGELOG.md`
- `packages/sdc-catchment/src/sdc_catchment/__init__.py`
- `.github/workflows/publish-catchment.yml`
- `docsite/packages/sdc-catchment/index.md`
- `docsite/packages/sdc-catchment/reference/catchment.md`

**Move (git mv):**
- `packages/sdc-core/src/sdc_core/catchment.py` → `packages/sdc-catchment/src/sdc_catchment/catchment.py`
- `packages/sdc-core/tests/test_catchment.py` → `packages/sdc-catchment/tests/test_catchment.py`

**Recreate (as shim):**
- `packages/sdc-core/src/sdc_core/catchment.py` (new file at old path, shim body)

**Modify:**
- `packages/sdc-catchment/tests/test_catchment.py` — imports `sdc_catchment`
- `packages/sdc-core/pyproject.toml` — add `sdc-catchment` dep + source
- `pyproject.toml` (root) — add `sdc-catchment` dep + source
- `mkdocs.yml` — nav block + mkdocstrings path

**Untouched:** `sdc_core/__init__.py` (re-exports through the shim), the three
consumer pipelines, `sdc-core`'s `[geo]` extra.

---

## Task 1: Create the package, move the code, add the shim

Atomic — the move + shim + dependency wiring must land together (an intermediate
state with `catchment.py` gone and no shim would break `sdc_core/__init__.py` and
all three consumers). One commit at the end.

**Files:** see File Structure (everything except docs + workflow).

- [ ] **Step 1: Create the package directory tree**

```bash
mkdir -p packages/sdc-catchment/src/sdc_catchment packages/sdc-catchment/tests
```

- [ ] **Step 2: Write `packages/sdc-catchment/pyproject.toml`**

```toml
[project]
name = "sdc-catchment"
dynamic = ["version"]
description = "Floating catchment area spatial accessibility (2SFCA, E2SFCA, and variants)"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [
    { name = "Aaron Schroeder", email = "ads7fg@virginia.edu" },
]
keywords = ["accessibility", "2sfca", "e2sfca", "catchment", "spatial", "gis"]
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
    "numpy>=1.26",
    "scipy>=1.11",
    "pandas>=2.0",
]

[project.urls]
Homepage = "https://dads2busy.github.io/Social-Data-Commons/packages/sdc-catchment/"
Documentation = "https://dads2busy.github.io/Social-Data-Commons/packages/sdc-catchment/"
Repository = "https://github.com/dads2busy/Social-Data-Commons"
Issues = "https://github.com/dads2busy/Social-Data-Commons/issues"
Changelog = "https://github.com/dads2busy/Social-Data-Commons/blob/main/packages/sdc-catchment/CHANGELOG.md"

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
tag-pattern = "catchment-v(?P<version>.+)"

[tool.hatch.version.raw-options]
# Package lives in a monorepo subdir; point setuptools_scm at the repo root.
root = "../.."
git_describe_command = ["git", "describe", "--dirty", "--tags", "--long", "--match", "catchment-v*"]

[tool.hatch.build.targets.wheel]
packages = ["src/sdc_catchment"]

[tool.ruff]
line-length = 100
```

- [ ] **Step 3: Write `packages/sdc-catchment/README.md`**

```markdown
# sdc-catchment

Floating catchment area (FCA) spatial-accessibility metrics — 2SFCA, E2SFCA,
KD2SFCA, 3SFCA, modified-2SFCA, balanced FCA, and commute-based FCA, all as
parameter variations of a single `catchment_ratio()`.

Part of the [Social Data Commons](https://github.com/dads2busy/Social-Data-Commons)
toolkit. Extracted from `sdc_core.catchment`; the Python replacement for the R
`catchment` package.

## Install

```bash
uv add sdc-catchment   # or: pip install sdc-catchment
```

## Public API

- `catchment_ratio` — accessibility ratio under a chosen FCA variant.
- `catchment_weight` — distance-decay weight matrix builder.
- `catchment_connections` / `catchment_network` — provider/consumer connectivity.
- `euclidean_cost` — pairwise Euclidean cost matrix.
- `KERNELS`, `WeightSpec` — kernel registry and weight-spec type.

See the [documentation](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-catchment/).
```

- [ ] **Step 4: Write `packages/sdc-catchment/CHANGELOG.md`**

```markdown
# Changelog

All notable changes to this project will be documented in this file. The format
is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-03

### Added
- Initial release. Extracted from `sdc_core.catchment`: `catchment_ratio`,
  `catchment_weight`, `catchment_connections`, `catchment_network`,
  `euclidean_cost`, plus the `KERNELS` kernel registry and `WeightSpec` type.
- Tag-derived versioning (hatch-vcs) and PyPI Trusted Publishing on a
  `catchment-v*` tag.
```

- [ ] **Step 5: Move the implementation into the package**

```bash
git mv packages/sdc-core/src/sdc_core/catchment.py packages/sdc-catchment/src/sdc_catchment/catchment.py
```

(The moved file is self-contained — no `sdc_core` imports — so its body needs no edits.)

- [ ] **Step 6: Write the package `__init__.py`**

`packages/sdc-catchment/src/sdc_catchment/__init__.py`:

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

- [ ] **Step 7: Move the tests**

```bash
git mv packages/sdc-core/tests/test_catchment.py packages/sdc-catchment/tests/test_catchment.py
```

- [ ] **Step 8: Repoint the test imports to `sdc_catchment`**

The test imports `from sdc_core.catchment import ...` in several places (some
inside test methods). Replace every occurrence in
`packages/sdc-catchment/tests/test_catchment.py`:

```bash
sed -i '' 's/from sdc_core\.catchment import/from sdc_catchment import/g' packages/sdc-catchment/tests/test_catchment.py
```

Then verify none remain:

```bash
grep -c "sdc_core.catchment" packages/sdc-catchment/tests/test_catchment.py
```

Expected: `0`.

- [ ] **Step 9: Recreate `sdc_core/catchment.py` as a full-surface shim**

Create a new `packages/sdc-core/src/sdc_core/catchment.py` with exactly:

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

All 7 names are re-exported so `sdc_core/__init__.py` (which imports them from
`sdc_core.catchment`) is unchanged.

- [ ] **Step 10: Wire `sdc-catchment` into `sdc-core`'s dependencies**

In `packages/sdc-core/pyproject.toml`, add `"sdc-catchment"` to `dependencies`
(after `"sdc-redistribute"`):

```toml
    "sdc-census10to20",
    "sdc-redistribute",
    "sdc-catchment",
]
```

and add the workspace source under `[tool.uv.sources]`:

```toml
[tool.uv.sources]
sdc-census10to20 = { workspace = true }
sdc-redistribute = { workspace = true }
sdc-catchment = { workspace = true }
```

- [ ] **Step 11: Wire `sdc-catchment` into the root workspace**

In the root `pyproject.toml`, add `"sdc-catchment"` to the `sdc` `dependencies`
(after `"sdc-redistribute"`):

```toml
    "sdc-census10to20",
    "sdc-redistribute",
    "sdc-catchment",
    "xlrd>=2.0.2",
```

and add the source under the root `[tool.uv.sources]`:

```toml
[tool.uv.sources]
sdc-core = { workspace = true }
sdc-census10to20 = { workspace = true }
sdc-redistribute = { workspace = true }
sdc-catchment = { workspace = true }
```

- [ ] **Step 12: Re-lock the workspace**

Run: `uv lock`
Expected: resolves successfully; `Added sdc-catchment (dynamic)` appears.

- [ ] **Step 13: Verify all three import paths resolve and tests pass**

```bash
uv run --group dev python -c "from sdc_catchment import catchment_ratio; from sdc_core.catchment import catchment_ratio as a; from sdc_core import catchment_ratio as b; print('ok', catchment_ratio is a is b)"
uv run --group dev pytest packages/sdc-catchment/tests packages/sdc-core/tests -q 2>&1 | tail -5
```

Expected: `ok True` (shim and top-level re-export are the same object), and all
tests pass.

- [ ] **Step 14: Confirm all three real consumers still import cleanly**

```bash
for f in \
  "health/Health Care Services/code/compute_service_access.py" \
  "education/Daycare Accessibility/code/distribution/script.py" \
  "education/Daycare Accessibility/code/distribution/ingest.py"; do
  uv run --group dev python -c "import ast; ast.parse(open('$f').read()); print('parses: $f')"
done
uv run --group dev python -c "from sdc_core.catchment import catchment_ratio; print('shim resolves to', catchment_ratio.__module__)"
```

Expected: all three print `parses: ...`, and the shim resolves to `sdc_catchment.catchment`.

- [ ] **Step 15: Commit**

```bash
git add -A
git commit -m "feat: extract sdc-catchment package with sdc-core shim"
```

---

## Task 2: Docs section

**Files:**
- Create: `docsite/packages/sdc-catchment/index.md`, `docsite/packages/sdc-catchment/reference/catchment.md`
- Modify: `mkdocs.yml`

- [ ] **Step 1: Create the overview page**

`docsite/packages/sdc-catchment/index.md`:

```markdown
# sdc-catchment

Floating catchment area (FCA) spatial-accessibility metrics. Extracted from
`sdc_core.catchment`; the Python replacement for the R `catchment` package.

## Install

```bash
uv add sdc-catchment   # or: pip install sdc-catchment
```

## Methods

2SFCA, E2SFCA, KD2SFCA, 3SFCA, modified-2SFCA, balanced FCA, and commute-based
FCA are all parameter variations of a single `catchment_ratio()`.

## Public API

| Symbol | What it does |
| --- | --- |
| `catchment_ratio` | Accessibility ratio under a chosen FCA variant. |
| `catchment_weight` | Distance-decay weight-matrix builder. |
| `catchment_connections` / `catchment_network` | Provider/consumer connectivity. |
| `euclidean_cost` | Pairwise Euclidean cost matrix. |
| `KERNELS`, `WeightSpec` | Kernel registry and weight-spec type. |

See the **Reference** page for the full API.
```

- [ ] **Step 2: Create the reference page**

`docsite/packages/sdc-catchment/reference/catchment.md`:

```markdown
# Catchment

::: sdc_catchment
```

- [ ] **Step 3: Add the mkdocstrings path and nav block to `mkdocs.yml`**

Change the mkdocstrings `paths` line to include `sdc-catchment` (current value is
`[packages/sdc-core/src, packages/sdc-redistribute/src, packages/sdc-census10to20/src]`):

```yaml
          paths: [packages/sdc-core/src, packages/sdc-catchment/src, packages/sdc-redistribute/src, packages/sdc-census10to20/src]
```

and insert a nav block immediately after the `sdc-core` block (before the
`sdc-redistribute` block):

```yaml
  - sdc-catchment:
      - Overview: packages/sdc-catchment/index.md
      - Reference:
          - Catchment: packages/sdc-catchment/reference/catchment.md
```

- [ ] **Step 4: Build the docs strictly**

Run: `uv run --group docs mkdocs build --strict 2>&1 | grep -E "WARNING|ERROR|Aborted|Documentation built"`
Expected: `Documentation built in N seconds`, no warnings (`::: sdc_catchment` resolves).

- [ ] **Step 5: Commit**

```bash
git add docsite/packages/sdc-catchment mkdocs.yml
git commit -m "docs: add sdc-catchment umbrella docs section"
```

---

## Task 3: Publish workflow

**Files:**
- Create: `.github/workflows/publish-catchment.yml`

- [ ] **Step 1: Create the workflow**

`.github/workflows/publish-catchment.yml`:

```yaml
name: Publish sdc-catchment to PyPI

on:
  push:
    tags:
      - "catchment-v*"

jobs:
  publish:
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/sdc-catchment
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
        working-directory: packages/sdc-catchment
        run: |
          python -m pip install --upgrade build
          python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: packages/sdc-catchment/dist/
```

- [ ] **Step 2: Validate the workflow YAML**

Run: `uv run --group docs python -c "import yaml; yaml.safe_load(open('.github/workflows/publish-catchment.yml')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/publish-catchment.yml
git commit -m "ci(publish): add sdc-catchment PyPI workflow"
```

---

## Task 4: Final verification + release handoff

**Files:** none (verification + handoff).

- [ ] **Step 1: Tag-derived build produces exactly 0.1.0**

```bash
git tag catchment-v0.1.0
cd packages/sdc-catchment && rm -rf dist && uvx --from build pyproject-build 2>&1 | tail -1 && ls dist/
cd /Users/ads7fg/git/social-data-commons
```

Expected: `Successfully built sdc_catchment-0.1.0.tar.gz and sdc_catchment-0.1.0-py3-none-any.whl`. A `.dev`/`+d<date>` suffix means a dirty tree or the tag isn't on HEAD — fix before continuing.

- [ ] **Step 2: twine check the metadata**

```bash
uv run --no-project --with twine python -m twine check packages/sdc-catchment/dist/*
```

Expected: both sdist and wheel `PASSED`.

- [ ] **Step 3: Delete the temp tag and clean artifacts**

```bash
git tag -d catchment-v0.1.0
rm -rf packages/sdc-catchment/dist
```

Expected: `Deleted tag 'catchment-v0.1.0'`.

- [ ] **Step 4: Finish the development branch**

Use the **superpowers:finishing-a-development-branch** skill to merge
`feat/sdc-catchment-split` to `main`, verify tests on the merged result, and push.
Merging/pushing does NOT publish (only a `catchment-v*` tag triggers the workflow).

- [ ] **Step 5: User completes Trusted Publishing setup (manual, one-time)**

Tell the user to register a **pending publisher** at
<https://pypi.org/manage/account/publishing/>:
- PyPI Project Name: `sdc-catchment`
- Owner: `dads2busy`
- Repository name: `Social-Data-Commons`
- Workflow name: `publish-catchment.yml`
- Environment name: `pypi`

(The GitHub `pypi` environment already exists and is reused.) Do not push the
release tag until the pending publisher is registered.

- [ ] **Step 6: Cut the release (after Step 5 confirmed)**

```bash
git checkout main && git pull
git tag catchment-v0.1.0
git push origin catchment-v0.1.0
gh run watch "$(gh run list --workflow=publish-catchment.yml --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status --interval 15
```

Expected: green run.

- [ ] **Step 7: Verify live on PyPI**

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" https://pypi.org/pypi/sdc-catchment/0.1.0/json
cd /tmp && uv run --no-project --refresh-package sdc-catchment --with sdc-catchment \
  python -c "import sdc_catchment as m; print(m.__version__)"
```

Expected: `HTTP 200`, then `0.1.0`. (Run the install from `/tmp` so uv resolves
from PyPI, not the local workspace.)

---

## Self-Review

- **Spec coverage:** package layout + `__init__` eager imports (all 7) → Task 1 §1,§6. pyproject (numpy/scipy/pandas, hatch-vcs + `root=../..` + `catchment-v` pattern, urls) → Task 1 §2. README/CHANGELOG → Task 1 §3,§4. `git mv` code + tests + repoint imports → Task 1 §5,§7,§8. full-surface shim (`__init__` unchanged) → Task 1 §9. sdc-core + root wiring → Task 1 §10,§11. all-3-consumers + both import paths unbroken → Task 1 §13,§14. docs section + nav + mkdocstrings path → Task 2. publish workflow → Task 3. build/twine/release/PyPI verification → Task 4. All spec sections covered.
- **Placeholder scan:** none — every code step has full content; every command has expected output. The `"0.0.0"` fallback is intentional.
- **Consistency:** import name `sdc_catchment` and PyPI/dist name `sdc-catchment` used consistently; the 7 public names (`KERNELS`, `WeightSpec`, `catchment_connections`, `catchment_network`, `catchment_ratio`, `catchment_weight`, `euclidean_cost`) match across `__init__`, shim, README, docs, and tests; tag prefix `catchment-v` identical across pyproject `tag-pattern`, `--match`, workflow trigger, and every tag command; environment `pypi` and workflow filename `publish-catchment.yml` match between the workflow and the Trusted Publishing fields.
- **Tag hygiene:** the only tag created before Task 4 §6 is the temp one in §1, deleted in §3.
