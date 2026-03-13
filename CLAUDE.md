# SDC Monorepo — Claude Instructions

## Project

This is a data pipeline monorepo (Python/uv) that produces standardized indicator datasets covering demographics, education, financial well-being, health, housing, environment, food, public safety, and transportation for Virginia and the National Capital Region (NCR).

Pipelines fetch from sources like the Census API (ACS), CDC WONDER, CMS, VDH, EPA, USDA, and others, then output long-format compressed CSVs (`data/distribution/`) with census-standardized 2020 geographies. A `prepare.py` step aggregates to county and health district levels and reformats output for two Next.js dashboard sites:

- `/Users/ads7fg/git/virginia_public_health_data` — VA dashboard
- `/Users/ads7fg/git/national_capital_region_data` — NCR dashboard

Shared pipeline utilities live in `packages/sdc-core/`.

## Memory

Read the memory index at `/Users/ads7fg/.claude/projects/-Users-ads7fg-git-national-capital-region-data/memory/MEMORY.md` at the start of every conversation. Load specific memory files as needed based on the task.

## Pipeline Conversion Spec

**`docs/pipeline-conversion-spec.md` is the authoritative reference for all data pipeline work.**

- When converting old R code (or non-conforming Python) to the standard Python pipeline pattern: read and follow the spec exactly. Every step, every artifact, every naming convention. No shortcuts.
- When creating new datasets from scratch: follow the spec wherever it applies — directory layout, `pipeline.yaml`, `ingest.py`/`prepare.py` structure, long-format schema, file naming via `build_file_name()`, `measure_info.json` fields, census standardization, health district aggregation, logging, and validation.
- Always read `docs/pipeline-conversion-spec.md` before starting any pipeline work. Do not rely on memory of what the spec says — re-read it every time.
