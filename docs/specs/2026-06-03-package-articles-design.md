# Documentation Articles for the Python Packages — Design

## Overview

Create a reusable **article template** and author **introduction + one deeper
article** for each of the three published Python packages, mirroring the topics
of their R-package vignettes but written natively against the (canonical) Python
API. Wire the articles into the umbrella docs site, enrich each package README to
the same introduction level, and patch-release all three so the improved READMEs
reach PyPI.

R-site precedent: `redistribute` (Introduction · Method Comparisons · Household
Estimates), `catchment` (Introduction to FCA · Case Study NCR · Case Study VA),
`sdc.census10to20` (single core-functionality article).

## Direction settled in brainstorming

- **Python is canonical.** Examples mirror the R vignette *scenarios* as closely
  as the current Python API allows, written natively in Python. They become the
  canonical shared examples; when the R packages are later rebuilt, they reuse
  these. We do NOT expand the Python API to match R in this effort, and we do NOT
  frame Python as deficient.
- **Scope: the 3 published packages** (census10to20, redistribute, catchment).
  `sdc-core` (internal) keeps reference-only docs.
- **Lean set:** every package gets an Introduction; redistribute and catchment
  each get one deeper article. census10to20's existing Getting Started IS its
  Introduction.
- **Examples are runnable and verified** — every code block is executed during
  authoring and the shown output is the real output. Small/inline/synthetic data,
  self-contained (no external files).
- **READMEs enriched to Introduction level; patch-release all three** (`v0.1.1`)
  so PyPI shows the richer README.
- **Out of scope:** unified bilingual (R+Python) site; rebuilding R packages;
  automated execution of doc examples in CI; real-data (downloaded/shipped)
  case studies.

## The article template (reusable artifact)

Stored as an internal contributor doc at `docs/article-template.md` (NOT on the
public site). It contains a copy-paste skeleton plus the conventions below.

Standard article structure:
1. **Title + one-paragraph "what & why."**
2. **Setup** — install line + imports.
3. **Worked example(s)** — runnable Python with the real captured output shown
   in an output block/comment.
4. **Type-specific body:**
   - *Method comparison:* run the methods on the same input, show results
     side-by-side, and a short "when to use which."
   - *Case study:* a realistic (synthetic) scenario, the computation, and an
     interpretation of the result.
5. **See also** — links to the package's Reference pages and sibling articles.

The guide also documents the README standard (below) and the file/nav
conventions (below).

## Per-package articles

File layout: `docsite/packages/<pkg>/articles/<name>.md`.

### census10to20
- **`articles/introduction.md`** — the current `docsite/packages/sdc-census10to20/getting-started.md`
  moved and conformed to the template (it already walks the
  `standardize_all` workflow with a runnable example). Content largely unchanged;
  add a "See also" section.

### redistribute
- **`articles/introduction.md`** — adapted from the R 5-region intro: a small
  long-format frame redistributed from a source geography to a target with
  `redistribute_direct` (area-proportional). Shows input, call, output.
- **`articles/method-comparison.md`** — `redistribute_direct` (area-weighted) vs
  `redistribute_parcels` (parcel-centroid-weighted) on the same source measure +
  target geography, with a small inline parcel-centroid frame; compares the two
  result columns and explains when each is appropriate.

### catchment
- **`articles/introduction.md`** — adapted from the R FCA intro: toy providers +
  consumers, `catchment_ratio` first with binary weights, then a distance-decay
  weight (via `catchment_weight`/`KERNELS`), showing how access scores change.
- **`articles/case-study.md`** — a compact, realistic synthetic scenario (e.g. a
  handful of clinics and demand points with coordinates and capacities) computing
  an accessibility ratio with `euclidean_cost` + a decay kernel, and interpreting
  the result. No external/real data.

> Each article's example code must run against the **current** package API.
> During implementation, read the actual function signatures
> (`redistribute_direct`, `redistribute_parcels`, `run_redistribution`;
> `catchment_ratio`, `catchment_weight`, `euclidean_cost`, `KERNELS`) before
> writing examples — do not assume parameter names from the R packages.

## README standard (PyPI long_description)

Each package README is brought to the template's Introduction level:
- Tightened "what & why" paragraph.
- A **single runnable Quickstart** — the smallest example from the Introduction
  article.
- A **Documentation** section linking to the umbrella-site articles (Introduction,
  the deeper article) and the Reference pages.
- Existing install + public-API summary retained.

## Docs wiring (mkdocs.yml)

Each package nav block becomes:

```yaml
  - <pkg>:
      - Overview: packages/<pkg>/index.md
      - Articles:
          - Introduction: packages/<pkg>/articles/introduction.md
          - <Deeper>: packages/<pkg>/articles/<name>.md   # redistribute, catchment
      - Reference:
          - ...
```

census10to20's current top-level `Getting Started` entry moves under an
`Articles` group as `Introduction`. No mkdocstrings `paths` changes.

## Release plan

- Add a `## [0.1.1] - 2026-06-03` entry to each package CHANGELOG (Added: docs
  articles; Changed: enriched README).
- These are README/docs-only changes; bump is a patch.
- Cut releases by pushing `census10to20-v0.1.1`, `redistribute-v0.1.1`,
  `catchment-v0.1.1`. Trusted Publishing + the `pypi` environment already exist
  for all three, so **no new manual setup** — the tag pushes publish directly.
- Done after the branch is merged to `main` (the publish workflows trigger on the
  version tags, independent of the merge commit).

## Verification / success criteria

- `docs/article-template.md` exists with the skeleton + conventions.
- Five article files exist under the three packages' `articles/` dirs; each
  code block was executed and shows real output.
- `mkdocs build --strict` is clean; nav shows `Articles` groups for all three.
- Each enriched README renders cleanly (covered by the per-release `twine check`).
- After release: `pypi.org/project/<pkg>/0.1.1/` returns 200 for all three, and
  each PyPI page shows the enriched README.

## Out of scope (restated)

- Unified bilingual R+Python documentation site (separate future project).
- Rebuilding the R packages from the Python ones.
- CI execution / doctest of article examples.
- Real (downloaded or shipped) datasets in any article.
- Articles for `sdc-core`.
