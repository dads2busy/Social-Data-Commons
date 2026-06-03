# sdc-redistribute

Redistribute values between geographies — direct area-weighted interpolation and
parcel-weighted redistribution.

Part of the [Social Data Commons](https://github.com/dads2busy/Social-Data-Commons)
toolkit. Extracted from `sdc_core.redistribute`; used by SDC pipelines to move
measures from one geographic vintage/level onto another (e.g. 2010 tracts → 2020
block groups), producing `_geo10`/`_geo20`-suffixed measures.

## Install

```bash
uv add sdc-redistribute   # or: pip install sdc-redistribute
```

## Quickstart

Split a tract's count onto two equal-area block groups (geometries generated
inline so the example is self-contained):

```python
import tempfile, pathlib
import geopandas as gpd
import pandas as pd
from shapely.geometry import box
from sdc_redistribute import redistribute_direct

tmp = pathlib.Path(tempfile.mkdtemp())
gpd.GeoDataFrame({"geoid": ["T1"]}, geometry=[box(0, 0, 2, 2)], crs="EPSG:4326").to_file(tmp / "tract.geojson", driver="GeoJSON")
gpd.GeoDataFrame({"geoid": ["BG1", "BG2"]}, geometry=[box(0, 0, 1, 2), box(1, 0, 2, 2)], crs="EPSG:4326").to_file(tmp / "bg.geojson", driver="GeoJSON")

source_df = pd.DataFrame({"geoid": ["T1"], "year": [2020], "measure": ["pop"], "value": [100.0]})
out = redistribute_direct(source_df, source_geo=tmp / "tract.geojson",
                          target_geos={"block_group": tmp / "bg.geojson"}, count_cols=["pop"])
print(out[["geoid", "measure", "value"]].to_string(index=False))
#  geoid    measure  value
#    BG1 pop_direct   50.0
#    BG2 pop_direct   50.0
```

## Public API

- `redistribute_direct` — area-proportional redistribution between two geographies.
- `redistribute_parcels` — parcel-centroid-weighted redistribution.
- `run_redistribution` — high-level wrapper driven by a pipeline.yaml config block.

## Documentation

- [Introduction](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-redistribute/articles/introduction/)
- [Method comparison](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-redistribute/articles/method-comparison/)
- [API reference](https://dads2busy.github.io/Social-Data-Commons/packages/sdc-redistribute/reference/redistribute/)
