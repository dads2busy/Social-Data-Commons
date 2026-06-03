# Introduction

This article walks through the standard workflow: take a long-format dataset
covering years before and after the 2020 census, and produce a unified frame
where every pre-2020 sub-county measure exists in both its original 2010
boundary form (`_geo10` suffix) and a redistributed 2020 boundary form
(`_geo20` suffix).

## Input format

`standardize_all` expects an SDC long-format DataFrame:

| column        | type   | description                                  |
| ------------- | ------ | -------------------------------------------- |
| `geoid`       | str    | 11-char tract or 12-char block-group GEOID   |
| `year`        | int    | observation year                             |
| `measure`     | str    | measure name (e.g. `"material_deprivation"`) |
| `value`       | float  | measure value                                |
| `moe`         | float  | margin of error (may be `pd.NA`)             |
| `region_type` | str    | optional; `"tract"` or `"block_group"`       |

## Example

```python
import pandas as pd
from sdc_census10to20 import standardize_all

df = pd.DataFrame(
    {
        "geoid":   ["51059450100", "51059450200", "51059450100"],
        "year":    [2018,          2018,          2020         ],
        "measure": ["population",  "population",  "population" ],
        "value":   [3000.0,        4500.0,        3100.0       ],
        "moe":     [pd.NA,         pd.NA,         pd.NA        ],
        "region_type": ["tract",   "tract",       "tract"      ],
    }
)

standardized = standardize_all(df)
```

The 2018 rows are duplicated: once as `population_geo10` (original boundaries)
and once as `population_geo20` (redistributed onto 2020 boundaries). The 2020
row is emitted as `population_geo20` only.

## What "redistribute" actually does

For each pre-2020 row, `standardize_all` calls
[`convert_2010_to_2020_bounds`][sdc_census10to20.convert_2010_to_2020_bounds],
which:

1. Loads the Census 2010↔2020 relationship file for the appropriate resolution
   (tract or block group).
2. Classifies each row of the crosswalk as `same`, `split`, or `moved` based
   on counts and area overlap.
3. For `same` and `split` rows, passes the source value through to each target
   geoid.
4. For `moved` rows, multiplies the source value by `area_part / area20` and
   sums across all source contributors to each target geoid.

This area-weighted approach is suitable for counts and densities. For rates,
ratios, and indices, redistribute the numerator and denominator separately and
recompute the ratio at the 2020 level.

## Working with a single year/measure

If you have just one slice and want to redistribute it directly without the
suffix logic:

```python
from sdc_census10to20 import convert_2010_to_2020_bounds

slice_df = df[(df["year"] == 2018) & (df["measure"] == "population")]
on_2020_bounds = convert_2010_to_2020_bounds(slice_df)
```

The input must contain one row per GEOID; if you have multiple years or
measures, slice first or use `standardize_all`.

## Inspecting the crosswalk

To examine the underlying 2010↔2020 mapping:

```python
from sdc_census10to20 import get_2010_2020_bound_changes

cw = get_2010_2020_bound_changes(res="tract", geoids=["51059450100"])
print(cw)
```

`type_change` will tell you which case applies for each pairing.

## See also

- [standardize_all reference](../reference/standardize_all.md)
- [convert_2010_to_2020_bounds reference](../reference/convert_2010_to_2020_bounds.md)
