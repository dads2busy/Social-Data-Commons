"""Render the catchment introduction map (accessibility across a real county)."""
import pathlib

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sdc_catchment import catchment_ratio, euclidean_cost

HERE = pathlib.Path(__file__).resolve().parent
asset = HERE.parent / "data" / "county_bgs.geojson"
img = HERE.parent / "img" / "catchment-county-access.png"
img.parent.mkdir(parents=True, exist_ok=True)

bgs = gpd.read_file(asset).to_crs(32618).reset_index(drop=True)
bgs["geoid"] = bgs["geoid"].astype(str)
cent = bgs.geometry.centroid
bg_xy = np.c_[cent.x.values, cent.y.values]

rng = np.random.default_rng(0)
consumers = pd.DataFrame({"geoid": bgs["geoid"], "value": rng.integers(500, 2500, len(bgs)).astype(float)})

# 3 clinics at the centroids of 3 evenly-spaced block groups (guaranteed inside the county).
idx = np.linspace(0, len(bgs) - 1, 3).astype(int)
clinic_xy = bg_xy[idx]
clinics = pd.DataFrame({"geoid": ["A", "B", "C"], "value": [20.0, 15.0, 30.0]})

cost = euclidean_cost(bg_xy, clinic_xy)
access = catchment_ratio(consumers, clinics, cost, weight="gaussian", scale=2000.0, max_cost=8000.0)
bgs["access"] = access.values * 1000.0  # beds per 1,000 people

fig, ax = plt.subplots(figsize=(7, 7))
bgs.plot(ax=ax, column="access", cmap="viridis", edgecolor="white", linewidth=0.2,
         legend=True, legend_kwds={"label": "clinic beds per 1,000 people"})
ax.scatter(clinic_xy[:, 0], clinic_xy[:, 1], c="red", s=clinics["value"] * 8,
           marker="*", edgecolor="black", zorder=5, label="clinics")
ax.set_title("Accessibility to clinics — Arlington County, VA\n(gaussian distance decay)")
ax.axis("off"); ax.legend(loc="upper right")
fig.tight_layout()
fig.savefig(img, dpi=130, bbox_inches="tight")
print("wrote", img)
print("access stats — min/median/max:",
      round(float(bgs["access"].min()), 3),
      round(float(bgs["access"].median()), 3),
      round(float(bgs["access"].max()), 3))
print(bgs[["geoid", "access"]].head().to_string(index=False))
