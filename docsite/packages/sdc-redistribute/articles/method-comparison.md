# Method comparison

`sdc-redistribute` offers two ways to push a source count onto target geographies:

- **`redistribute_direct`** — *area-weighted*. Each target gets a share of the
  source value proportional to the area it covers. Assumes the count is spread
  evenly across the source geometry.
- **`redistribute_parcels`** — *parcel-weighted* (dasymetric). Each target gets a
  share proportional to the number of parcel centroids that fall inside it. Uses
  where development actually is, not just raw area.

This article runs both on the same input so the difference is visible.

## Setup

```bash
pip install sdc-redistribute
```

```python
import tempfile, pathlib
import geopandas as gpd
import pandas as pd
from shapely.geometry import box
from sdc_redistribute import redistribute_direct, redistribute_parcels
```

## Same input, two methods

A tract of 100 people is split into two equal-area block groups — but the parcels
(where people actually live) are concentrated in the left half: four parcels in
BG1, one in BG2.

```python
tmp = pathlib.Path(tempfile.mkdtemp())
source = gpd.GeoDataFrame({"geoid": ["T1"]}, geometry=[box(0, 0, 2, 2)], crs="EPSG:4326")
src_path = tmp / "tract.geojson"; source.to_file(src_path, driver="GeoJSON")
bg = gpd.GeoDataFrame(
    {"geoid": ["BG1", "BG2"]},
    geometry=[box(0, 0, 1, 2), box(1, 0, 2, 2)], crs="EPSG:4326",
)
bg_path = tmp / "bg.geojson"; bg.to_file(bg_path, driver="GeoJSON")
source_df = pd.DataFrame({"geoid": ["T1"], "year": [2020], "measure": ["pop"], "value": [100.0]})

# Parcels concentrated in the LEFT half (BG1): 4 parcels left, 1 right.
parcels = pd.DataFrame({"lon": [0.2, 0.4, 0.6, 0.8, 1.8], "lat": [1.0, 1.0, 1.0, 1.0, 1.0]})

direct = redistribute_direct(source_df, source_geo=src_path,
                             target_geos={"block_group": bg_path}, count_cols=["pop"])
parcel = redistribute_parcels(source_df, parcel_centroids=parcels, source_geo=src_path,
                              target_geos={"block_group": bg_path}, count_cols=["pop"])

cmp = (direct.rename(columns={"value": "direct"})[["geoid", "direct"]]
       .merge(parcel.rename(columns={"value": "parcels"})[["geoid", "parcels"]], on="geoid"))
print(cmp.to_string(index=False))
```

```text
geoid  direct  parcels
  BG1    50.0     80.0
  BG2    50.0     20.0
```

Area-weighting splits the 100 people 50/50, because the two block groups are
equal in area. Parcel-weighting splits them 80/20, following the 4-to-1 parcel
density — a much better estimate when settlement is uneven. Note the two methods
suffix their measures differently (`pop_direct` vs `pop_parcels`), so they can
coexist in the same long-format frame.

## When to use which

- **`redistribute_direct`** — when you have no parcel data, or population is
  roughly uniform across the source unit. Simplest and dependency-light.
- **`redistribute_parcels`** — when settlement is uneven (most tracts) and parcel
  centroids are available. More faithful, at the cost of needing the parcel layer.

## See also

- [Introduction](introduction.md)
- [redistribute reference](../reference/redistribute.md)
