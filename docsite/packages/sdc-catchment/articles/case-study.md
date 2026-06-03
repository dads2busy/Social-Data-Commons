# Case study

A worked accessibility analysis for a small synthetic county: five residential
neighborhoods (with populations) and three clinics (with bed capacities). We
compute, for each neighborhood, how many clinic beds are accessible per 1,000
residents under distance decay — the same computation SDC health-access pipelines
run at full scale, here on data small enough to read.

## Setup

```bash
pip install sdc-catchment
```

```python
import numpy as np
import pandas as pd
from sdc_catchment import catchment_ratio, euclidean_cost
```

## Computing accessibility

```python
# 5 demand neighborhoods (population) and 3 clinics (capacity, beds).
demand = pd.DataFrame({
    "geoid": ["n1", "n2", "n3", "n4", "n5"],
    "value": [1200.0, 800.0, 1500.0, 600.0, 2000.0],
})
demand_xy = np.array([[0, 0], [3, 1], [6, 0], [1, 4], [5, 5]], dtype=float)
clinics = pd.DataFrame({"geoid": ["A", "B", "C"], "value": [20.0, 15.0, 30.0]})
clinics_xy = np.array([[1, 1], [5, 1], [4, 5]], dtype=float)

cost = euclidean_cost(demand_xy, clinics_xy)
# E2SFCA-style: gaussian decay within a 4-unit travel bound.
access = catchment_ratio(demand, clinics, cost, weight="gaussian", scale=2.0, max_cost=4.0)
result = demand.assign(access_per_1000=(access.values * 1000).round(3))
print(result.to_string(index=False))
```

```text
geoid  value  access_per_1000
   n1 1200.0            9.647
   n2  800.0           12.242
   n3 1500.0            6.071
   n4  600.0            8.459
   n5 2000.0           14.724
```

## Interpreting the result

The score is beds accessible per 1,000 residents, after discounting each clinic's
capacity by travel distance (gaussian decay) and ignoring clinics beyond the
4-unit bound.

- **`n5` is best served (14.7)** — it sits right next to clinic C, the largest
  (30 beds), so even its big population is well covered.
- **`n3` is worst served (6.1)** — it's in the far corner `[6, 0]`, distant from
  all three clinics, while carrying a large population (1,500). This is the
  neighborhood a planner would flag.
- **`n2` (12.2)** benefits from sitting between clinics A and B; **`n1` (9.6)** and
  **`n4` (8.5)** are moderate — near one clinic but not the largest.

Changing the kernel (`weight=`), its `scale`, or the `max_cost` bound shifts these
scores: a wider bound or gentler decay raises access for the peripheral
neighborhoods like `n3`.

## See also

- [Introduction to floating catchment areas](introduction.md)
- [catchment reference](../reference/catchment.md)
