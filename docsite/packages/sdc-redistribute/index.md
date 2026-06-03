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
