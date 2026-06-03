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
