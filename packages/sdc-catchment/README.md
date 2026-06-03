# sdc-catchment

Floating catchment area (FCA) spatial-accessibility metrics — 2SFCA, E2SFCA,
KD2SFCA, 3SFCA, modified-2SFCA, balanced FCA, and commute-based FCA, all as
parameter variations of a single `catchment_ratio()`.

Part of the [Social Data Commons](https://github.com/dads2busy/Social-Data-Commons)
toolkit. Extracted from `sdc_core.catchment`; the Python replacement for the R
`catchment` package.

## Install

```bash
uv add sdc-catchment   # or: pip install sdc-catchment
```

## Public API

- `catchment_ratio` — accessibility ratio under a chosen FCA variant.
- `catchment_weight` — distance-decay weight matrix builder.
- `catchment_connections` / `catchment_network` — provider/consumer connectivity.
- `euclidean_cost` — pairwise Euclidean cost matrix.
- `KERNELS`, `WeightSpec` — kernel registry and weight-spec type.

See the [documentation](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-catchment/).
