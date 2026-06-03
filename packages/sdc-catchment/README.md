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

## Quickstart

Access of three consumers to two providers, under a gaussian distance-decay:

```python
import numpy as np
import pandas as pd
from sdc_catchment import catchment_ratio, euclidean_cost

consumers = pd.DataFrame({"geoid": ["c1", "c2", "c3"], "value": [100.0, 100.0, 100.0]})
providers = pd.DataFrame({"geoid": ["p1", "p2"], "value": [10.0, 10.0]})
cost = euclidean_cost(np.array([[0, 0], [1, 0], [2, 0]]), np.array([[0, 0], [2, 0]]))

access = catchment_ratio(consumers, providers, cost, weight="gaussian", scale=1.0)
print(access.to_string())
# c1    0.065179
# c2    0.069641
# c3    0.065179
```

The central consumer (`c2`) has the highest access; decay weights each provider
by distance.

## Public API

- `catchment_ratio` — accessibility ratio under a chosen FCA variant.
- `catchment_weight` — distance-decay weight matrix builder.
- `catchment_connections` / `catchment_network` — provider/consumer connectivity.
- `euclidean_cost` — pairwise Euclidean cost matrix.
- `KERNELS`, `WeightSpec` — kernel registry and weight-spec type.

## Documentation

- [Introduction to floating catchment areas](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-catchment/articles/introduction/)
- [Case study](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-catchment/articles/case-study/)
- [API reference](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-catchment/reference/catchment/)
