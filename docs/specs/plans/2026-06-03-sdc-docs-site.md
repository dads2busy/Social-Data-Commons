# SDC Umbrella Documentation Site — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one MkDocs Material site at the monorepo root that documents the SDC Python packages (initially `sdc-core` + `sdc-census10to20`), served from `https://dads2busy.github.io/Social-Data-Commons/`.

**Architecture:** A single root `mkdocs.yml` with `docs_dir: docsite/`. mkdocstrings introspects all workspace packages from the one uv venv. Existing `sdc-census10to20` docs are migrated into the umbrella; their nested standalone config and inert docs workflow are deleted. PyPI publishing stays per-package and is untouched.

**Tech Stack:** MkDocs, Material theme, mkdocstrings[python] (numpy docstrings), uv workspace, GitHub Actions + Pages.

**Spec:** `docs/specs/2026-06-03-sdc-docs-site-design.md`

**Verification note:** This is a docs site — there is no application logic to unit-test. The "test" for every task is `uv run mkdocs build --strict` succeeding (it fails on missing nav files, broken internal links, and unresolved mkdocstrings references) plus targeted `grep` gates. Run all commands from the repo root: `/Users/ads7fg/git/social-data-commons`.

---

## File Structure

**Create:**
- `mkdocs.yml` — root site config (theme, plugins, nav, `docs_dir: docsite`)
- `docsite/index.md` — umbrella landing page
- `docsite/packages/sdc-core/index.md` — sdc-core overview
- `docsite/packages/sdc-core/reference/{census,geo,io,naming,pipeline,versioning,zenodo,spatial}.md` — per-module reference (8 pages)
- `.github/workflows/docs.yml` — root Pages deploy workflow

**Move (git mv, preserve history):**
- `packages/sdc-census10to20/docs/index.md` → `docsite/packages/sdc-census10to20/index.md`
- `packages/sdc-census10to20/docs/articles/getting-started.md` → `docsite/packages/sdc-census10to20/getting-started.md`
- `packages/sdc-census10to20/docs/reference/*.md` → `docsite/packages/sdc-census10to20/reference/*.md` (4 files)

**Modify:**
- `pyproject.toml` (root) — add `docs` dependency group
- `.gitignore` (root) — add `/site/`
- `docsite/packages/sdc-census10to20/index.md` — fix stale SDC org link

**Delete (git rm):**
- `packages/sdc-census10to20/mkdocs.yml`
- `packages/sdc-census10to20/.github/workflows/docs.yml`

**Untouched:** `packages/sdc-census10to20/.github/workflows/publish.yml` (PyPI stays per-package).

---

## Task 1: Scaffold root site + landing page

**Files:**
- Modify: `pyproject.toml` (root, `[dependency-groups]`)
- Modify: `.gitignore` (root)
- Create: `mkdocs.yml`
- Create: `docsite/index.md`

- [ ] **Step 1: Add the `docs` dependency group to the root `pyproject.toml`**

Find the existing `[dependency-groups]` block and add a `docs` group alongside `dev`:

```toml
[dependency-groups]
dev = [
    "matplotlib>=3.10.8",
    "pytest>=9.0.2",
    "seaborn>=0.13.2",
]
docs = [
    "mkdocs>=1.6",
    "mkdocs-material>=9.5",
    "mkdocstrings[python]>=0.24",
]
```

- [ ] **Step 2: Add the build artifact to root `.gitignore`**

Append to `.gitignore`:

```
# MkDocs build output
/site/
```

- [ ] **Step 3: Create the root `mkdocs.yml`**

Create `mkdocs.yml` (note `docs_dir: docsite` and the mkdocstrings `paths` pointing at both package `src` dirs; nav starts with only Home and grows in later tasks):

```yaml
site_name: Social Data Commons
site_description: Python packages for the Social Data Commons data pipelines
site_url: https://dads2busy.github.io/Social-Data-Commons/
repo_url: https://github.com/dads2busy/Social-Data-Commons
repo_name: dads2busy/Social-Data-Commons
edit_uri: edit/main/docsite/

docs_dir: docsite

theme:
  name: material
  features:
    - navigation.sections
    - navigation.expand
    - navigation.top
    - content.code.copy
    - content.code.annotate
    - search.suggest
    - search.highlight
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          paths: [packages/sdc-core/src, packages/sdc-census10to20/src]
          options:
            docstring_style: numpy
            show_source: true
            show_root_heading: true
            show_signature_annotations: true
            separate_signature: true
            merge_init_into_class: true

markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.superfences
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - toc:
      permalink: true

nav:
  - Home: index.md
```

- [ ] **Step 4: Create the umbrella landing page `docsite/index.md`**

```markdown
# Social Data Commons

Python packages powering the [Social Data Commons](https://github.com/dads2busy/Social-Data-Commons)
data pipelines — the Python ports of the SDAD R toolkit for census geography
standardization, spatial accessibility, value redistribution, and shared
pipeline utilities.

## Packages

| Package | What it does | Status |
| --- | --- | --- |
| [`sdc-core`](packages/sdc-core/index.md) | Shared pipeline utilities — Census API, file naming, versioning, Zenodo upload, geography aggregation. | Available |
| [`sdc-census10to20`](packages/sdc-census10to20/index.md) | Redistribute 2010–2019 census data onto 2020 boundaries. | Available |
| `sdc-redistribute` | General value redistribution between geographies (currently `sdc_core.redistribute`). | Coming soon |
| `sdc-catchment` | Floating catchment area spatial accessibility (currently `sdc_core.catchment`). | Coming soon |

## Install

```bash
# uv (recommended)
uv add sdc-census10to20

# pip
pip install sdc-census10to20
```

## Links

- Source: [github.com/dads2busy/Social-Data-Commons](https://github.com/dads2busy/Social-Data-Commons)
```

- [ ] **Step 5: Build and verify**

Run: `uv run --group docs mkdocs build --strict`
Expected: `Documentation built in N seconds` with exit 0, no `WARNING`/`ERROR`. (First run also installs the docs group.)

- [ ] **Step 6: Verify no stale org references in config**

Run: `grep -rn "uva-bi-sdad" mkdocs.yml docsite/`
Expected: no output (exit 1).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore mkdocs.yml docsite/index.md
git commit -m "feat(docs): scaffold SDC umbrella docs site + landing page"
```

---

## Task 2: Migrate sdc-census10to20 docs into the umbrella

**Files:**
- Move: 6 files from `packages/sdc-census10to20/docs/` → `docsite/packages/sdc-census10to20/`
- Delete: `packages/sdc-census10to20/mkdocs.yml`, `packages/sdc-census10to20/.github/workflows/docs.yml`
- Modify: `docsite/packages/sdc-census10to20/index.md` (fix org link), `mkdocs.yml` (add nav section)

- [ ] **Step 1: Create the destination directory and move the docs with git mv**

```bash
mkdir -p docsite/packages/sdc-census10to20/reference
git mv packages/sdc-census10to20/docs/index.md docsite/packages/sdc-census10to20/index.md
git mv packages/sdc-census10to20/docs/articles/getting-started.md docsite/packages/sdc-census10to20/getting-started.md
git mv packages/sdc-census10to20/docs/reference/standardize_all.md docsite/packages/sdc-census10to20/reference/standardize_all.md
git mv packages/sdc-census10to20/docs/reference/convert_2010_to_2020_bounds.md docsite/packages/sdc-census10to20/reference/convert_2010_to_2020_bounds.md
git mv packages/sdc-census10to20/docs/reference/create_crosswalk.md docsite/packages/sdc-census10to20/reference/create_crosswalk.md
git mv packages/sdc-census10to20/docs/reference/get_2010_2020_bound_changes.md docsite/packages/sdc-census10to20/reference/get_2010_2020_bound_changes.md
```

- [ ] **Step 2: Delete the nested standalone config and inert docs workflow**

```bash
git rm packages/sdc-census10to20/mkdocs.yml
git rm packages/sdc-census10to20/.github/workflows/docs.yml
```

(Leave `packages/sdc-census10to20/.github/workflows/publish.yml` in place.)

- [ ] **Step 3: Fix the stale SDC org link in the migrated overview**

In `docsite/packages/sdc-census10to20/index.md`, the "What it does" intro links the Social Data Commons to the old org. Update only the SDC org link (keep the R-package link, which genuinely lives at uva-bi-sdad):

Replace:
```markdown
used by the [Social Data Commons](https://github.com/uva-bi-sdad) pipelines to
```
With:
```markdown
used by the [Social Data Commons](https://github.com/dads2busy/Social-Data-Commons) pipelines to
```

- [ ] **Step 4: Fix the relative getting-started link in the migrated overview**

The migrated `index.md` ends with a link to `articles/getting-started.md`, but the article now sits beside it. Replace:
```markdown
See the [Getting Started](articles/getting-started.md) article for a worked
```
With:
```markdown
See the [Getting Started](getting-started.md) article for a worked
```

- [ ] **Step 5: Add the sdc-census10to20 nav section to `mkdocs.yml`**

Append under the existing `nav:` block (after `- Home: index.md`):

```yaml
  - sdc-census10to20:
      - Overview: packages/sdc-census10to20/index.md
      - Getting Started: packages/sdc-census10to20/getting-started.md
      - Reference:
          - standardize_all: packages/sdc-census10to20/reference/standardize_all.md
          - convert_2010_to_2020_bounds: packages/sdc-census10to20/reference/convert_2010_to_2020_bounds.md
          - create_crosswalk: packages/sdc-census10to20/reference/create_crosswalk.md
          - get_2010_2020_bound_changes: packages/sdc-census10to20/reference/get_2010_2020_bound_changes.md
```

- [ ] **Step 6: Build and verify**

Run: `uv run --group docs mkdocs build --strict`
Expected: exit 0, no warnings. mkdocstrings resolves `sdc_census10to20.*` symbols (the `[sdc_census10to20.create_crosswalk][...]` cross-refs in index.md must resolve — `--strict` fails if not).

- [ ] **Step 7: Verify the nested config is gone**

Run: `ls packages/sdc-census10to20/mkdocs.yml packages/sdc-census10to20/docs 2>&1`
Expected: "No such file or directory" for both.

Run: `ls packages/sdc-census10to20/.github/workflows/`
Expected: only `publish.yml`.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(docs): migrate sdc-census10to20 docs into umbrella site"
```

---

## Task 3: sdc-core section (per-module reference)

**Files:**
- Create: `docsite/packages/sdc-core/index.md`
- Create: `docsite/packages/sdc-core/reference/{census,geo,io,naming,pipeline,versioning,zenodo,spatial}.md`
- Modify: `mkdocs.yml` (add nav section)

- [ ] **Step 1: Create the sdc-core overview `docsite/packages/sdc-core/index.md`**

```markdown
# sdc-core

Shared utilities for the Social Data Commons data pipelines. Every pipeline's
`ingest.py` and `prepare.py` builds on these helpers instead of rolling its own.

## Install

```bash
uv add sdc-core   # or: pip install sdc-core
```

## What's inside

| Area | Module | Highlights |
| --- | --- | --- |
| Census | `sdc_core.census` | `CensusClient` for ACS fetches |
| Geographies | `sdc_core.geo` | aggregation, region-type inference, 2010↔2020 boundary helpers |
| IO | `sdc_core.io` | long-format read/export, point-layer schemas |
| Naming | `sdc_core.naming` | `build_file_name` and friends |
| Pipeline | `sdc_core.pipeline` | `load_pipeline`, profiles, run results |
| Versioning | `sdc_core.versioning` | semantic version bumps for distribution files |
| Zenodo | `sdc_core.zenodo` | dataset upload/publish |
| Spatial | `sdc_core.catchment`, `sdc_core.redistribute`, `sdc_core.parcels` | accessibility, redistribution, parcel weighting |

See the **Reference** pages in the nav for the full API of each module.
```

- [ ] **Step 2: Create the eight reference pages**

Each page is a heading plus mkdocstrings module directives. Create them exactly:

`docsite/packages/sdc-core/reference/census.md`:
```markdown
# Census

::: sdc_core.census
```

`docsite/packages/sdc-core/reference/geo.md`:
```markdown
# Geographies

::: sdc_core.geo
```

`docsite/packages/sdc-core/reference/io.md`:
```markdown
# IO

::: sdc_core.io
```

`docsite/packages/sdc-core/reference/naming.md`:
```markdown
# Naming

::: sdc_core.naming
```

`docsite/packages/sdc-core/reference/pipeline.md`:
```markdown
# Pipeline

::: sdc_core.pipeline

::: sdc_core.profiles

::: sdc_core.result
```

`docsite/packages/sdc-core/reference/versioning.md`:
```markdown
# Versioning

::: sdc_core.versioning
```

`docsite/packages/sdc-core/reference/zenodo.md`:
```markdown
# Zenodo

::: sdc_core.zenodo
```

`docsite/packages/sdc-core/reference/spatial.md`:
```markdown
# Spatial

::: sdc_core.catchment

::: sdc_core.redistribute

::: sdc_core.parcels
```

- [ ] **Step 3: Add the sdc-core nav section to `mkdocs.yml`**

Insert this block in `nav:` **before** the `- sdc-census10to20:` block (so sdc-core lists first):

```yaml
  - sdc-core:
      - Overview: packages/sdc-core/index.md
      - Reference:
          - Census: packages/sdc-core/reference/census.md
          - Geographies: packages/sdc-core/reference/geo.md
          - IO: packages/sdc-core/reference/io.md
          - Naming: packages/sdc-core/reference/naming.md
          - Pipeline: packages/sdc-core/reference/pipeline.md
          - Versioning: packages/sdc-core/reference/versioning.md
          - Zenodo: packages/sdc-core/reference/zenodo.md
          - Spatial: packages/sdc-core/reference/spatial.md
```

- [ ] **Step 4: Build and verify mkdocstrings resolves every sdc-core module**

Run: `uv run --group docs mkdocs build --strict`
Expected: exit 0, no warnings. If a module fails to resolve, `--strict` reports `Could not collect "sdc_core.<x>"`; if that happens, confirm `sdc_core/__init__.py` uses eager imports (spec §"Eager imports required") and that `geopandas` installed (it's a root workspace dep).

- [ ] **Step 5: Smoke-check the rendered output exists**

Run: `ls site/packages/sdc-core/reference/`
Expected: directories for `census`, `geo`, `io`, `naming`, `pipeline`, `versioning`, `zenodo`, `spatial`.

- [ ] **Step 6: Commit**

```bash
git add docsite/packages/sdc-core mkdocs.yml
git commit -m "feat(docs): add sdc-core per-module reference section"
```

---

## Task 4: Root Pages deploy workflow

**Files:**
- Create: `.github/workflows/docs.yml`

- [ ] **Step 1: Create the workflow `.github/workflows/docs.yml`**

```yaml
name: Deploy docs

on:
  push:
    branches: [main]
    paths:
      - "docsite/**"
      - "mkdocs.yml"
      - "packages/*/src/**"
      - ".github/workflows/docs.yml"

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.12"
      - name: Install docs deps
        run: uv sync --group docs
      - name: Build docs
        run: uv run mkdocs build --strict
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site
      - uses: actions/deploy-pages@v4
        id: deployment
```

- [ ] **Step 2: Validate the workflow YAML parses**

Run: `uv run --group docs python -c "import yaml; yaml.safe_load(open('.github/workflows/docs.yml')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/docs.yml
git commit -m "ci(docs): deploy umbrella site to GitHub Pages on main"
```

---

## Task 5: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Clean full build**

Run: `rm -rf site && uv run --group docs mkdocs build --strict`
Expected: exit 0, no warnings.

- [ ] **Step 2: Confirm no stale org refs in config (content R-package links may remain)**

Run: `grep -rn "uva-bi-sdad" mkdocs.yml .github/workflows/docs.yml`
Expected: no output (exit 1).

- [ ] **Step 3: Confirm all top-level sections rendered**

Run: `ls site/ && ls site/packages/`
Expected: `index.html` present in `site/`; `sdc-core` and `sdc-census10to20` present in `site/packages/`.

- [ ] **Step 4: Local serve smoke test (manual)**

Run: `uv run --group docs mkdocs serve`
Open `http://127.0.0.1:8000/Social-Data-Commons/` — confirm landing page, both package sections in the nav, and that a sdc-core reference page (e.g. Census) renders the API. Stop the server when done.

- [ ] **Step 5: One-time GitHub setup (user action — note in handoff)**

In the GitHub repo settings → Pages, set **Source = GitHub Actions**. No PyPI/token setup is needed for docs. After this and a push to `main`, the site deploys to `https://dads2busy.github.io/Social-Data-Commons/`.

---

## Self-Review

- **Spec coverage:** Hosting/URLs → Task 1 §3. `docsite/` dir + `docs/` reserved → Tasks 1–3. mkdocstrings multi-package → Task 1 §3 `paths`. Per-module sdc-core pages → Task 3. census10to20 migration + delete nested config (keep publish.yml) → Task 2. Landing page → Task 1 §4. Root CI workflow → Task 4. Success criteria (build --strict, no uva-bi-sdad in config, nested config gone, deploy) → Task 5. All covered.
- **Placeholders:** none — every step has concrete file content or an exact command + expected output.
- **Consistency:** `docs_dir: docsite`, nav paths, and the `git mv` destinations all agree on `docsite/packages/<pkg>/...`. mkdocstrings `paths` and module directives use the real installed module names (`sdc_core.*`, `sdc_census10to20.*`). Nav ordering (sdc-core before sdc-census10to20) is consistent between Task 2 (appends census10to20) and Task 3 (inserts sdc-core before it).
