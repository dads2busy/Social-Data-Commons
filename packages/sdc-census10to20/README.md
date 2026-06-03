# sdc-census10to20

Redistribute 2010-2019 census data onto 2020 census boundaries.

This is the Python port of the R package
[`sdc.census10to20`](https://uva-bi-sdad.github.io/sdc.census10to20/), used by
the Social Data Commons pipelines to standardize tract- and block-group-level
data across the 2020 decennial census boundary changes.

## Install

```bash
pip install sdc-census10to20
```

## Quick start

```python
import pandas as pd
from sdc_census10to20 import standardize_all

df = pd.DataFrame({
    "geoid": ["51059450100", "51059450200"],
    "year": [2018, 2018],
    "measure": ["population", "population"],
    "value": [3000, 4500],
    "moe": [pd.NA, pd.NA],
})

standardized = standardize_all(df)
```

## Documentation

- [Introduction](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-census10to20/articles/introduction/)
- [API reference](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-census10to20/reference/standardize_all/)

## License

MIT
