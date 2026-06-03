# SDC Umbrella Documentation Site — Design

## Overview

A single MkDocs Material documentation site for the Social Data Commons Python
packages, served from the monorepo's own GitHub Pages. One umbrella site with a
section per package — not per-package standalone sites.

This replaces the inert, standalone-repo-oriented docs scaffolding currently
nested under `packages/sdc-census10to20/` (which targets the old `uva-bi-sdad`
org and a repo-root layout it does not actually have here).

## Decisions settled in brainstorming

- **Repo topology: Topology A (monorepo).** Packages stay as uv-workspace
  members under `packages/`. They remain individually PyPI-publishable via
  per-package `publish.yml`; git-repo count and PyPI-project count stay
  decoupled. Chosen because the `sdc-core` ↔ sub-package coupling
  (`[tool.uv.sources] <pkg> = { workspace = true }` re-export shims) only works
  cleanly in one repo, and independent per-package governance does not pay off
  for a solo maintainer. Preserves the option to peel a package into its own
  repo later.
- **Tooling: MkDocs + Material + mkdocstrings** (NumPy docstrings), the
  org-standard stack already proven in `sdc-census10to20`. Not re-litigated.
- **Initial scope: shell + `sdc-census10to20` + `sdc-core`.** `redistribute`
  and `catchment` currently live inside `sdc-core` and are not yet separate
  packages; they get their own sections later, when/if split.
- **Full consolidation.** The nested per-package `mkdocs.yml` is deleted, not
  kept as standalone-build optionality. A standalone config can be regenerated
  later if a package graduates to its own repo.

## Hosting

- **URL:** `https://dads2busy.github.io/Social-Data-Commons/`
- **`site_url`:** `https://dads2busy.github.io/Social-Data-Commons/`
- **`repo_url`:** `https://github.com/dads2busy/Social-Data-Commons`

These fix the stale `uva-bi-sdad` references in the current
`packages/sdc-census10to20/mkdocs.yml`.

## Build topology

- **One `mkdocs.yml` at the repo root.**
- **Public-site source lives in a new `docsite/` directory.** `docs/` at the
  repo root is reserved for internal material (specs, data-paper-rubrics,
  pipeline-conversion-spec.md) and stays OUT of the public site.
- **mkdocstrings introspects all packages from the one workspace venv.**
  `::: sdc_core.census`, `::: sdc_census10to20.convert`, etc. all resolve
  because CI installs the whole uv workspace before building.
- **Eager imports required.** mkdocstrings uses griffe static analysis, so each
  package `__init__.py` must expose public names via eager
  `from pkg.mod import name` (no `__getattr__` lazy loading). `sdc-census10to20`
  already does this; verify `sdc-core` does too.

## Directory structure

```
mkdocs.yml                              # repo root
docsite/
  index.md                              # SDC umbrella landing
  packages/
    sdc-core/
      index.md                          # overview + install
      reference/<module>.md             # one page PER MODULE: "::: sdc_core.census"
    sdc-census10to20/
      index.md
      getting-started.md                # migrated from the package's docs/articles/
      reference/<func>.md               # migrated as-is (per-function, already exist)
.github/workflows/
  docs.yml                              # ONE root workflow (Pages deploy)
```

## sdc-core section — per-module pages

`sdc-core` has 15 modules. Hand-writing a page per public function (as
`sdc-census10to20` did) does not scale. Instead, one page per logical module
group, each body just `::: sdc_core.<module>` so mkdocstrings auto-renders every
public member. Low maintenance, stays in sync automatically.

Proposed module grouping (one reference page each):

- **Census** — `census` (`CensusClient`)
- **Geographies** — `geo` (aggregation, region inference; note: this module also
  re-exports the `sdc-census10to20` boundary functions via the shim)
- **IO** — `io` (read/export helpers, point-layer schemas)
- **Naming** — `naming` (`build_file_name`, etc.)
- **Pipeline** — `pipeline` (`load_pipeline`), `profiles`, `result`
- **Versioning** — `versioning`
- **Zenodo** — `zenodo`
- **Spatial** — `catchment`, `redistribute`, `parcels` (documented here for now,
  as they live in `sdc-core`; promoted to their own sections when split)

Note the overlap: `sdc-core.__all__` re-exports census10to20 + catchment names.
The `sdc-census10to20` section is the canonical home for the boundary functions;
the `sdc-core` Geographies page renders them too via the shim — acceptable
duplication, or suppress with mkdocstrings `members:` filters if it reads poorly.

## Migration & cleanup of existing census10to20 docs

- Move `packages/sdc-census10to20/docs/*` → `docsite/packages/sdc-census10to20/`.
- **Delete** `packages/sdc-census10to20/mkdocs.yml`.
- **Delete** `packages/sdc-census10to20/.github/workflows/docs.yml` (inert where
  it sits — workflows only run from repo-root `.github/workflows/`).
- **Keep** `packages/sdc-census10to20/.github/workflows/publish.yml` — PyPI stays
  per-package; only docs consolidate.
- The package's local `site/` build artifact stays gitignored (unchanged).

## Landing page (`docsite/index.md`)

1. What the Social Data Commons packages are (Python ports of the SDAD R
   toolkit: census geography standardization, spatial accessibility, value
   redistribution, shared pipeline utilities).
2. Package matrix:
   - `sdc-core` — shared pipeline utilities (Census API, file naming,
     versioning, Zenodo, geography aggregation).
   - `sdc-census10to20` — redistribute 2010–2019 census data onto 2020
     boundaries.
   - `sdc-redistribute` — *coming soon* (currently `sdc_core.redistribute`).
   - `sdc-catchment` — *coming soon* (currently `sdc_core.catchment`).
3. Install snippet (uv / pip).
4. Links to PyPI projects + the GitHub repo.

## CI — root `docs.yml`

One workflow at `.github/workflows/docs.yml`:

- **Trigger:** push to `main` touching `docsite/**`, `mkdocs.yml`, or
  `packages/*/src/**`.
- **Permissions:** `contents: read`, `pages: write`, `id-token: write`.
- **Steps:** checkout → setup Python 3.12 → install the uv workspace + docs
  deps → `mkdocs build --strict` → `upload-pages-artifact` → `deploy-pages`.
- **One-time manual setup (user):** enable GitHub Pages for the repo with the
  "GitHub Actions" source. No PyPI/token setup needed for docs.

## Out of scope (this iteration)

- Splitting `redistribute` or `catchment` into standalone packages.
- Any PyPI publishing changes (`publish.yml` files unchanged).
- Versioned docs (mike) — single `latest` site only.
- Custom domain.

## Success criteria

- `mkdocs build --strict` succeeds from the repo root with all packages
  installed.
- The built site has a landing page, a `sdc-core` section (per-module reference
  pages), and a migrated `sdc-census10to20` section (overview, getting-started,
  per-function reference).
- No remaining `uva-bi-sdad` references in published docs config.
- The nested `packages/sdc-census10to20/mkdocs.yml` and nested `docs.yml` are
  gone; `publish.yml` remains.
- On push to `main`, the root `docs.yml` deploys to
  `https://dads2busy.github.io/Social-Data-Commons/`.
