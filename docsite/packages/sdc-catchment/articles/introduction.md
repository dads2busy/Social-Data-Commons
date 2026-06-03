# Introduction to floating catchment areas

Floating catchment area (FCA) methods measure how much **supply** (clinics, jobs,
services) is accessible to each unit of **demand** (population), accounting for
the travel cost between them. `catchment_ratio` is the single entry point: you
give it consumer and provider tables, a travel-cost matrix, and a rule for how
cost turns into a weight — a hard distance bound, a decay kernel, or both. Every
FCA variant (2SFCA, E2SFCA, gravity, …) is a choice of those parameters.

## Setup

```bash
pip install sdc-catchment
```

```python
import numpy as np
import pandas as pd
from sdc_catchment import catchment_ratio, euclidean_cost
```

## A tiny catchment

Three equally-populated consumers sit in a line; two equal-capacity providers sit
at the ends. We build the travel-cost matrix from coordinates, then compute access
two ways.

```python
# 3 consumers (demand, value = population), 2 providers (supply, value = capacity).
consumers = pd.DataFrame({"geoid": ["c1", "c2", "c3"], "value": [100.0, 100.0, 100.0]})
providers = pd.DataFrame({"geoid": ["p1", "p2"], "value": [10.0, 10.0]})
consumers_xy = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
providers_xy = np.array([[0.0, 0.0], [2.0, 0.0]])
cost = euclidean_cost(consumers_xy, providers_xy)

# Binary catchment: everyone within max_cost=3.0 counts equally.
binary = catchment_ratio(consumers, providers, cost, max_cost=3.0)
# Distance-decay catchment: gaussian kernel.
decay = catchment_ratio(consumers, providers, cost, weight="gaussian", scale=1.0)

print("cost matrix:\n", cost)
print("\nbinary access:\n", binary.to_string())
print("\ngaussian-decay access:\n", decay.to_string())
```

```text
cost matrix:
 [[0. 2.]
 [1. 1.]
 [2. 0.]]

binary access:
 c1    0.066667
c2    0.066667
c3    0.066667

gaussian-decay access:
 c1    0.065179
c2    0.069641
c3    0.065179
```

With a generous binary bound, every consumer reaches both providers and receives
the region-wide supply-to-demand ratio — total supply 20 over total demand 300,
or about `0.0667` units of capacity per person. Switching to a **gaussian decay**
differentiates by distance: the central consumer `c2`, closest on average to both
providers, gets the highest access, and the two ends get slightly less.

Decay behaviour is set by the `weight` kernel and its `scale`. `KERNELS` provides
`linear`, `gaussian`, `gravity`, `exponential`, `logistic`, and `logarithmic`;
`max_cost` adds a hard travel bound on top of any kernel.

## See also

- [catchment reference](../reference/catchment.md)
- [Case study](case-study.md)
