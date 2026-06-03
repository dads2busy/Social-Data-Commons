"""Render the redistribute introduction map (tract count -> block groups)."""
import pathlib
import tempfile

import geopandas as gpd
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sdc_redistribute import redistribute_direct

HERE = pathlib.Path(__file__).resolve().parent
asset = HERE.parent / "data" / "tract_bgs.geojson"
img = HERE.parent / "img" / "redistribute-tract-to-bg.png"
img.parent.mkdir(parents=True, exist_ok=True)

bgs = gpd.read_file(asset)
bgs["geoid"] = bgs["geoid"].astype(str)
tract_id = bgs["geoid"].str[:11].iloc[0]
tract = bgs.dissolve().assign(geoid=tract_id)[["geoid", "geometry"]]

tmp = pathlib.Path(tempfile.mkdtemp())
tract.to_file(tmp / "tract.geojson", driver="GeoJSON")
bgs[["geoid", "geometry"]].to_file(tmp / "bgs.geojson", driver="GeoJSON")

source_df = pd.DataFrame({"geoid": [tract_id], "year": [2020], "measure": ["pop"], "value": [1000.0]})
out = redistribute_direct(
    source_df, source_geo=tmp / "tract.geojson",
    target_geos={"block_group": tmp / "bgs.geojson"}, count_cols=["pop"],
)
bgs["pop_direct"] = bgs["geoid"].map(out.set_index("geoid")["value"])

tract_p = tract.to_crs(32618)
bgs_p = bgs.to_crs(32618)
fig, ax = plt.subplots(1, 2, figsize=(11, 5))
tract_p.plot(ax=ax[0], color="#cbd5e1", edgecolor="black")
ax[0].set_title(f"Tract {tract_id}\n1,000 people"); ax[0].axis("off")
bgs_p.plot(ax=ax[1], column="pop_direct", cmap="Blues", edgecolor="black",
           legend=True, legend_kwds={"label": "people (pop_direct)"})
ax[1].set_title("Redistributed to block groups\n(area-weighted)"); ax[1].axis("off")
fig.tight_layout()
fig.savefig(img, dpi=130, bbox_inches="tight")
print("wrote", img)
print(out[["geoid", "measure", "value"]].to_string(index=False))
