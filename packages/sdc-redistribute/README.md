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
