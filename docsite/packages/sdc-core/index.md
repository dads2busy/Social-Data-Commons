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
