# Social Data Commons (SDC)

Unified monorepo for Social Data Commons data pipelines. This repo contains domain-specific pipelines plus a shared Python core.

## Purpose (for AI coding agents)

- **Goal**: ingest, standardize, and distribute SDC datasets across domains (demographics, health, housing, etc.).
- **Primary runtime**: Python, with shared utilities in `packages/sdc-core/`.
- **Outputs**: standardized long-form CSVs (usually `.csv.xz`) in `data/distribution/`.

## Tech Stack

- **Python** (primary runtime)
- **uv** for environment and dependency management
- **pandas** for data manipulation
- **httpx** for API access
- **Geo tooling** via `sdc-core` utilities (crosswalks, aggregation, standardization)

## Structure

- `packages/sdc-core/` — Shared Python framework (Census API, I/O, geo aggregation, naming, logging).
- `geographies/` — Crosswalks and geographic reference data.
- `demographics/` — Demographic pipelines (age, gender, race, language, veteran, etc.).
- `education/`, `health/`, `housing/`, etc. — Domain-specific pipelines.
- `meta/` — Infrastructure, metadata, and supporting utilities.

## Directory Structure

Typical topic layout:

- `code/` — ingest/prepare scripts
- `data/original/` — raw source extracts
- `data/working/` — intermediate datasets
- `data/distribution/` — final outputs (compressed `.csv.xz`)
- `docs/` — supporting documentation

## Current status (important)

- **Demographics**: actively converting R pipelines to Python.
- **Naming**: `sdc_core.naming.build_file_name(...)` now builds output filenames using available metadata and inferred resolution.
  - Resolution order: `hd, ct, tr, bg, bl, nb, pl, bz, pr`.
  - Coverage defaults: `("dc","md","va") -> ncr`, plus single-state defaults.
- **Legacy R**: remaining R scripts under `demographics/` have been moved to `demographics/legacy/`.

## Setup

```bash
uv sync
```

Creates a single `.venv` with `sdc-core` installed in editable mode.

## Usage

```bash
uv run python demographics/Gender/code/ingest.py
```

(Each pipeline has its own `pipeline.yaml` and writes to `data/distribution/`.)
