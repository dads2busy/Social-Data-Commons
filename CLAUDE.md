# SDC Monorepo — Claude Instructions

## Project (GOAL)

This is a data pipeline monorepo (Python/uv) that produces standardized indicator datasets covering demographics, education, financial well-being, health, housing, environment, food, public safety, and transportation for Virginia and the National Capital Region (NCR).

Pipelines fetch from sources like the Census API (ACS), CDC WONDER, CMS, VDH, EPA, USDA, and others, then output long-format compressed CSVs (`data/distribution/`) with census-standardized 2020 geographies. A `prepare.py` step aggregates to county and health district levels and reformats output for two Next.js dashboard sites:

- `/Users/ads7fg/git/virginia_public_health_data` — VA dashboard
- `/Users/ads7fg/git/national_capital_region_data` — NCR dashboard

Shared pipeline utilities live in `packages/sdc-core/`.

Success = `ingest.py` exits 0 with correct row counts in `data/distribution/`, `prepare.py` exits 0 with per-level `.csv.xz` files in `dashboard_data/`, and validation comparison passes against reference data.

## Memory

Read the memory index at `/Users/ads7fg/.claude/projects/-Users-ads7fg-git-national-capital-region-data/memory/MEMORY.md` at the start of every conversation. Load specific memory files as needed based on the task.

## Pipeline Conversion Spec (CONSTRAINTS — authoritative reference)

**`docs/pipeline-conversion-spec.md` is the authoritative reference for all data pipeline work.**

- Always read `docs/pipeline-conversion-spec.md` before starting any pipeline work. Do not rely on memory of what the spec says — re-read it every time.
- When converting R pipelines or creating new ones: follow the spec exactly. Every step, artifact, naming convention. No shortcuts.

## Stack (CONSTRAINTS — non-negotiable)

- **Language**: Python 3.12+
- **Package manager**: uv (workspace layout). Never use pip, conda, or poetry.
- **Core library**: `sdc-core` (packages/sdc-core/) — Census API helpers, file naming, versioning, Zenodo upload. Always use these utilities instead of rolling custom.
- **Key deps**: pandas, geopandas, scipy, scikit-learn, pyarrow, openpyxl, xlrd
- **Testing**: pytest
- **Versioning**: Semantic versioning via `sdc_core/versioning.py`. `update_version(TOPIC_DIR)` called in every `prepare.py` `__main__` block.

## Hard Rules (CONSTRAINTS)

- **Dashboard parity**: Both dashboards (NCR + VA) must stay architecturally in sync. When pipeline changes affect dashboard data format, build process, or geography sourcing, apply the change to both dashboards. Flag any divergence explicitly.
- Never install a new dependency without asking first.
- Never modify `sdc-core` without understanding downstream impacts on all pipelines.
- Use `get_acs_multi()` for Census ACS data (keys = friendly names, values = Census codes). It accepts `profile=` and `estimate_only=False`. `get_acs_wide()` does NOT accept `profile=`.
- Use `build_file_name()` for all output file naming. Pass `coverage_area="va"` when source config uses `state:` key.
- CMS PUF CSV files need `encoding="latin-1"`.
- `prepare.py` glob patterns must distinguish ingest from prepare output (e.g. `cttr` vs `hdcttr`).
- Every pipeline needs `pipeline.yaml`, `ingest.py`, `prepare.py`, `measure_info.json`.
- `data_method` column is required on all distribution files (values: observed, modeled, scaled, interpolated, extrapolated).
- `measure_info.json` must include `long_description`, `short_description`, and `provenance` fields (see spec section 5.1).
- `_geo10` variants get the same text as `_geo20` plus "Values on original 2010 census tract boundaries."

## Output Format (FORMAT)

- Directory layout: `{domain}/{TopicName}/` (e.g. `demographics/Population/`)
  - `pipeline.yaml` — source config, variables, years
  - `code/distribution/ingest.py` — fetch + transform → `data/distribution/*.csv.xz`
  - `code/distribution/prepare.py` — aggregate → `dashboard_data/{site}/*.csv.xz`
  - `measure_info.json` — variable metadata for dashboards
  - `docs/validation_report.md` — comparison against reference data
  - `legacy/` — old R code (git mv, never delete)
- Long-format schema: `(geoid, year, measure, value, moe, data_method)` rows
- One row = one geographic unit at one point in time
- Census-standardized 2020 FIPS geographies

## Failure Conditions (what makes output unacceptable)

- Pipeline committed without all 7 items in the completion gate (spec section top).
- Output files with wrong schema (missing columns, wrong types, duplicate geoid+year+measure rows).
- Using pip/conda/poetry instead of uv.
- Rolling custom Census API calls instead of using `sdc-core` helpers.
- Hardcoded file paths, FIPS codes, or year ranges that should come from `pipeline.yaml`.
- `prepare.py` that doesn't call `update_version(TOPIC_DIR)`.
- Missing `data_method` column or missing `measure_info.json` fields.
- Spatial operations that require external servers (OSRM, spatial databases) without prior approval.
- Deleting old R code instead of moving to `legacy/`.
- Starting a conversion without first reading `docs/pipeline-conversion-spec.md`.
