"""Render the census10to20 introduction map (county population, 2010 vs 2020 boundaries)."""
import pathlib

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt

from sdc_census10to20 import convert_2010_to_2020_bounds

HERE = pathlib.Path(__file__).resolve().parent
data = HERE.parent / "data"
img = HERE.parent / "img" / "census10to20-boundary-change.png"
img.parent.mkdir(parents=True, exist_ok=True)

t10 = gpd.read_file(data / "tracts_2010.geojson"); t10["geoid"] = t10["geoid"].astype(str)
t20 = gpd.read_file(data / "tracts_2020.geojson"); t20["geoid"] = t20["geoid"].astype(str)
t10 = t10.sort_values("geoid").reset_index(drop=True)

# Synthetic 2010 populations (fixed seed for reproducibility).
rng = np.random.default_rng(0)
t10["pop"] = rng.integers(800, 5000, len(t10)).astype(float)

inp = pd.DataFrame({"geoid": t10["geoid"], "value": t10["pop"]})
out = convert_2010_to_2020_bounds(inp, state_fips="51")
t20["pop"] = t20["geoid"].map(out.set_index("geoid")["value"])

a = t10.to_crs(32618)
b = t20.to_crs(32618)
vmax = float(max(a["pop"].max(), np.nanmax(b["pop"].values)))
norm = mpl.colors.Normalize(vmin=0, vmax=vmax)

fig, ax = plt.subplots(1, 2, figsize=(12, 6))
a.plot(ax=ax[0], column="pop", cmap="Oranges", norm=norm, edgecolor="black")
ax[0].set_title("2010 tract boundaries"); ax[0].axis("off")
b.plot(ax=ax[1], column="pop", cmap="Oranges", norm=norm, edgecolor="black",
       missing_kwds={"color": "lightgrey", "label": "no in-sample source"})
ax[1].set_title("2020 tract boundaries"); ax[1].axis("off")
sm = mpl.cm.ScalarMappable(cmap="Oranges", norm=norm); sm.set_array([])
fig.colorbar(sm, ax=ax, fraction=0.025, pad=0.02, label="population")
fig.suptitle("Montgomery County, VA — population on 2010 vs 2020 tract boundaries", y=0.98)
fig.savefig(img, dpi=130, bbox_inches="tight")
print("wrote", img)
print("input total:", round(float(inp["value"].sum()), 1))
print("2020 in-county total:", round(float(np.nansum(t20["pop"].values)), 1))
print("2020 tracts with no in-sample value:", int(t20["pop"].isna().sum()))
print(out.head().to_string(index=False))
