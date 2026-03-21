"""Generate publication-quality figures for the Technical Validation section."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import pandas as pd
import numpy as np
import geopandas as gpd
from scipy import stats
from pathlib import Path

# Paths
BASE = Path.home() / "git" / "sdc-monorepo" / "education" / "Daycare Accessibility"
OUT = BASE / "docs" / "figures"
DATA = BASE / "data" / "distribution" / "va_hdcttrbg_vdss_2021_2025_daycare_access.csv.xz"
LOC_2021 = BASE / "data" / "working" / "locations_2021.csv"
LOC_2025 = BASE / "data" / "working" / "locations_2025.csv"
GEO = (
    Path.home()
    / "git"
    / "sdc-monorepo"
    / "geographies"
    / "VA"
    / "Census Geographies"
    / "County"
    / "2020"
    / "data"
    / "distribution"
    / "va_geo_census_cb_2020_counties.geojson"
)

# Global style
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "DejaVu Sans"],
        "font.size": 10,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
    }
)

# Load main data
df = pd.read_csv(DATA)

# ── Figure 1: Summary statistics table ──────────────────────────────────────

print("Generating Figure 1: Summary statistics table...")
bg = df[df["region_type"] == "block_group"].copy()

measure_labels = {
    "daycare_capacity": "Capacity",
    "daycare_min_drivetime": "Min drive time",
    "daycare_ratio": "Ratio (all ages)",
    "daycare_ratio_over_4": "Ratio (over 4)",
    "daycare_ratio_under_10": "Ratio (under 10)",
}
measure_order = list(measure_labels.keys())

rows = []
for m in measure_order:
    for y in [2021, 2025]:
        vals = bg[(bg["measure"] == m) & (bg["year"] == y)]["value"]
        n_total = len(vals)
        vals_nn = vals.dropna()
        rows.append(
            {
                "Measure": measure_labels[m],
                "Year": y,
                "N": len(vals_nn),
                "Mean": vals_nn.mean(),
                "Median": vals_nn.median(),
                "SD": vals_nn.std(),
                "Min": vals_nn.min(),
                "Max": vals_nn.max(),
                "% Zero": 100 * (vals_nn == 0).sum() / len(vals_nn) if len(vals_nn) > 0 else np.nan,
            }
        )

tab = pd.DataFrame(rows)

# Format numbers
fmt = tab.copy()
fmt["N"] = fmt["N"].apply(lambda x: f"{x:,}")
fmt["Year"] = fmt["Year"].astype(str)
for c in ["Mean", "Median", "SD", "Min", "Max", "% Zero"]:
    fmt[c] = fmt[c].apply(lambda x: f"{x:.1f}")

fig, ax = plt.subplots(figsize=(7.5, 3.2))
ax.axis("off")

col_names = list(fmt.columns)
cell_text = fmt.values.tolist()

table = ax.table(
    cellText=cell_text,
    colLabels=col_names,
    cellLoc="center",
    loc="center",
)
table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1.0, 1.35)

# Set custom column widths — wider for the Measure column
col_widths = [0.18, 0.07, 0.09, 0.09, 0.09, 0.09, 0.09, 0.09, 0.09]
for j, w in enumerate(col_widths):
    for i in range(len(cell_text) + 1):  # +1 for header
        table[i, j].set_width(w)

# Left-align the Measure column
for i in range(len(cell_text) + 1):
    table[i, 0].set_text_props(ha="left")
    table[i, 0]._loc = "left"

# Style header
for j in range(len(col_names)):
    cell = table[0, j]
    cell.set_text_props(fontweight="bold", color="white")
    cell.set_facecolor("#4C72B0")
    cell.set_edgecolor("white")

# Alternating row shading
for i in range(len(cell_text)):
    for j in range(len(col_names)):
        cell = table[i + 1, j]
        cell.set_edgecolor("white")
        if i % 2 == 0:
            cell.set_facecolor("#F0F0F0")
        else:
            cell.set_facecolor("white")

fig.savefig(OUT / "fig_summary_table.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("  Saved fig_summary_table.png")

# ── Figure 2: Capacity distribution histograms ─────────────────────────────

print("Generating Figure 2: Capacity distribution histograms...")

loc21 = pd.read_csv(LOC_2021)
loc25 = pd.read_csv(LOC_2025)

# Exclude default capacity of 4
cap21 = loc21.loc[loc21["capacity"] != 4, "capacity"].clip(upper=300)
cap25 = loc25.loc[loc25["capacity"] != 4, "capacity"].clip(upper=300)

fig, axes = plt.subplots(1, 2, figsize=(7, 3), sharey=True)

for ax, cap, year, color in zip(
    axes, [cap21, cap25], [2021, 2025], ["#4C72B0", "#DD8452"]
):
    ax.hist(cap, bins=30, range=(0, 300), color=color, edgecolor="white", linewidth=0.5)
    med = cap.median()
    mn = cap.mean()
    ax.axvline(med, color="black", ls="--", lw=1)
    ax.axvline(mn, color="black", ls="-", lw=1)
    ax.set_title(str(year), fontsize=11, fontweight="bold")
    ax.set_xlabel("Licensed capacity")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlim(0, 300)
    # annotations
    ymax = ax.get_ylim()[1]
    ax.text(
        0.97,
        0.92,
        f"N = {len(cap):,}\nMedian = {med:.0f}\nMean = {mn:.0f}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8),
    )

axes[0].set_ylabel("Number of facilities")

# Synchronize y-axis after drawing
ymax = max(axes[0].get_ylim()[1], axes[1].get_ylim()[1])
for ax in axes:
    ax.set_ylim(0, ymax)

fig.tight_layout()
fig.savefig(OUT / "fig_capacity_distribution.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("  Saved fig_capacity_distribution.png")

# ── Figure 3: 2021 vs 2025 scatter plots ───────────────────────────────────

print("Generating Figure 3: Temporal scatter plots...")

scatter_measures = [
    "daycare_min_drivetime",
    "daycare_ratio",
    "daycare_ratio_over_4",
    "daycare_ratio_under_10",
]
scatter_labels = {
    "daycare_min_drivetime": "Min drive time (min)",
    "daycare_ratio": "Ratio (all ages)",
    "daycare_ratio_over_4": "Ratio (over 4)",
    "daycare_ratio_under_10": "Ratio (under 10)",
}

bg_wide = bg.pivot_table(index=["geoid", "measure"], columns="year", values="value").reset_index()

fig, axes = plt.subplots(2, 2, figsize=(7, 6.5))

for ax, m in zip(axes.flat, scatter_measures):
    sub = bg_wide[bg_wide["measure"] == m].dropna(subset=[2021, 2025])
    ax.scatter(sub[2021], sub[2025], s=3, alpha=0.15, color="#4C72B0", rasterized=True)
    lo = min(sub[2021].min(), sub[2025].min())
    hi = max(sub[2021].max(), sub[2025].max())
    ax.plot([lo, hi], [lo, hi], color="gray", ls="--", lw=0.8, zorder=0)
    r, _ = stats.pearsonr(sub[2021], sub[2025])
    ax.text(
        0.05,
        0.95,
        f"r = {r:.3f}",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8),
    )
    label = scatter_labels[m]
    ax.set_xlabel(f"{label} (2021)", fontsize=9)
    ax.set_ylabel(f"{label} (2025)", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)

fig.tight_layout()
fig.savefig(OUT / "fig_temporal_scatter.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("  Saved fig_temporal_scatter.png")

# ── Figure 4: Choropleth maps ──────────────────────────────────────────────

print("Generating Figure 4: Choropleth maps...")

counties = gpd.read_file(GEO)

county_data = df[(df["region_type"] == "county") & (df["measure"] == "daycare_ratio")].copy()
county_data["geoid"] = county_data["geoid"].astype(str)
counties["geoid"] = counties["geoid"].astype(str)

fig, axes = plt.subplots(1, 2, figsize=(7, 3))

# Shared color scale
vmin = county_data["value"].min()
vmax = county_data["value"].quantile(0.98)  # clip outliers for better color spread

for ax, year in zip(axes, [2021, 2025]):
    sub = county_data[county_data["year"] == year]
    merged = counties.merge(sub[["geoid", "value"]], on="geoid", how="left")
    merged.plot(
        column="value",
        ax=ax,
        cmap="YlOrRd",
        vmin=vmin,
        vmax=vmax,
        edgecolor="gray",
        linewidth=0.3,
        missing_kwds={"color": "lightgray", "edgecolor": "gray", "linewidth": 0.3},
    )
    ax.set_title(str(year), fontsize=11, fontweight="bold")
    ax.set_axis_off()

# Shared colorbar
sm = plt.cm.ScalarMappable(cmap="YlOrRd", norm=plt.Normalize(vmin=vmin, vmax=vmax))
sm._A = []
cbar = fig.colorbar(sm, ax=axes, orientation="horizontal", fraction=0.05, pad=0.05, shrink=0.6)
cbar.set_label("Day care seats per 1,000 children under 15", fontsize=9)
cbar.ax.tick_params(labelsize=8)

fig.savefig(OUT / "fig_ratio_choropleth.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("  Saved fig_ratio_choropleth.png")

print("\nAll figures saved to:", OUT)
