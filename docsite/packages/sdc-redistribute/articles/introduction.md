# Introduction

`sdc-redistribute` moves **count** measures from one set of geographies onto
another by areal interpolation — the area-weighted way to push a value recorded
for a larger unit (a census tract) down onto smaller units (block groups) that
partition it. This is the spatial analogue of the disaggregation example in the
R package: a value on a source frame is distributed across a target frame.

## Setup

```bash
pip install sdc-redistribute
```

```python
import tempfile, pathlib
import geopandas as gpd
import pandas as pd
from shapely.geometry import box
from sdc_redistribute import redistribute_direct
```

## Redistributing a count

`redistribute_direct` takes long-format source data, a GeoJSON for the source
geometries, and a `{region_type: geojson}` mapping for each target geography.
Here a single tract holding 100 people is split into two equal-area block groups.
We generate the tiny geometries at runtime so the example is self-contained.

```python
tmp = pathlib.Path(tempfile.mkdtemp())

# One source tract (T1) covering a 2x2 square.
source = gpd.GeoDataFrame({"geoid": ["T1"]}, geometry=[box(0, 0, 2, 2)], crs="EPSG:4326")
src_path = tmp / "tract.geojson"
source.to_file(src_path, driver="GeoJSON")

# Two block groups splitting the tract into left/right halves.
bg = gpd.GeoDataFrame(
    {"geoid": ["BG1", "BG2"]},
    geometry=[box(0, 0, 1, 2), box(1, 0, 2, 2)],
    crs="EPSG:4326",
)
bg_path = tmp / "bg.geojson"
bg.to_file(bg_path, driver="GeoJSON")

# Long-format source data: 100 people in T1 in 2020.
source_df = pd.DataFrame(
    {"geoid": ["T1"], "year": [2020], "measure": ["pop"], "value": [100.0]}
)

out = redistribute_direct(
    source_df,
    source_geo=src_path,
    target_geos={"block_group": bg_path},
    count_cols=["pop"],
)
print(out.to_string(index=False))
```

```text
geoid    measure  value  year region_type  moe
  BG1 pop_direct   50.0  2020 block_group <NA>
  BG2 pop_direct   50.0  2020 block_group <NA>
```

The tract's 100 people are split in proportion to each block group's share of the
tract's area. Because the two block groups are equal in area, each receives 50.
The output is long-format, one row per target geoid, and the measure is suffixed
`_direct` to record the method used.

Area-weighting assumes the count is spread evenly across the source geometry.
When that assumption is poor — population clusters in part of a tract — use
parcel-weighted redistribution instead (see the method comparison).

## See also

- [redistribute reference](../reference/redistribute.md)
- [Method comparison](method-comparison.md)
