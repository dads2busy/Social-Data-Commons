"""
Validation Analyses for Virginia Daycare Accessibility Dataset
Analysis A: Convergent Validity (3SFCA vs Simple Ratio)
Analysis B: Urban vs Rural Disaggregation
"""

import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
from scipy import stats
from shapely.geometry import shape, Point
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE / "data"
FIG_DIR = BASE / "docs" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────
# Load all data
# ──────────────────────────────────────────────

print("=" * 70)
print("LOADING DATA")
print("=" * 70)

# Main dataset
main_df = pd.read_csv(DATA_DIR / "distribution" / "va_hdcttrbg_vdss_2021_2025_daycare_access.csv.xz")
main_df["geoid"] = main_df["geoid"].astype(str)
print(f"Main dataset: {main_df.shape[0]:,} rows")

# Locations 2021
locations = pd.read_csv(DATA_DIR / "working" / "locations_2021.csv")
print(f"Locations 2021: {locations.shape[0]:,} facilities")

# ACS population at block group level
acs = pd.read_csv(DATA_DIR / "working" / "acs_cache" / "acs_detail_2021_block_group_b1acf14f.csv")
acs["geoid"] = acs["geoid"].astype(str)
acs["under_15"] = (
    acs["male_under_5"] + acs["female_under_5"] +
    acs["male_5_9"] + acs["female_5_9"] +
    acs["male_10_14"] + acs["female_10_14"]
)
# County FIPS = first 5 digits of block group geoid
acs["county_fips"] = acs["geoid"].str[:5]
county_pop = acs.groupby("county_fips")["under_15"].sum().reset_index()
county_pop.columns = ["county_fips", "pop_under_15"]
print(f"ACS block groups: {acs.shape[0]:,}, counties with pop: {county_pop.shape[0]}")

# County GeoJSON
geo_path = Path("/Users/ads7fg/git/sdc-monorepo/geographies/VA/Census Geographies/County/2020/data/distribution/va_geo_census_cb_2020_counties.geojson")
with open(geo_path) as f:
    counties_gj = json.load(f)
print(f"County geometries: {len(counties_gj['features'])} counties")

# Build county geometry lookup and compute areas
county_geoms = {}
county_areas_sqkm = {}
county_names = {}
for feat in counties_gj["features"]:
    fips = feat["properties"]["geoid"]
    geom = shape(feat["geometry"])
    county_geoms[fips] = geom
    county_names[fips] = feat["properties"]["region_name"]
    # Approximate area in sq km using a simple lat/lon projection
    # For Virginia (~37-39N), 1 deg lat ~ 111 km, 1 deg lon ~ 88 km
    bounds = geom.bounds  # minx, miny, maxx, maxy
    centroid = geom.centroid
    # Use pyproj-free approximation: convert to equal area via cos(lat)
    lat_rad = np.radians(centroid.y)
    # Area in sq degrees * conversion
    # Better: use the actual polygon area with scaling
    coords_factor = 111.0 * 111.0 * np.cos(lat_rad)  # sq deg -> sq km approx
    area_sqdeg = geom.area
    county_areas_sqkm[fips] = area_sqdeg * coords_factor
county_area_df = pd.DataFrame([
    {"county_fips": k, "area_sqkm": v, "county_name": county_names[k]}
    for k, v in county_areas_sqkm.items()
])

# Spatial join: assign each facility to a county
print("\nSpatial joining facilities to counties...")
facility_county = []
for _, row in locations.iterrows():
    pt = Point(row["long"], row["lat"])
    matched = None
    for fips, geom in county_geoms.items():
        if geom.contains(pt):
            matched = fips
            break
    facility_county.append(matched)
locations["county_fips"] = facility_county
unmatched = locations["county_fips"].isna().sum()
print(f"  Matched: {locations['county_fips'].notna().sum()}, Unmatched: {unmatched}")

# Capacity by county from locations (simple containment)
cap_by_county = (
    locations[locations["county_fips"].notna()]
    .groupby("county_fips")["capacity"]
    .sum()
    .reset_index()
)
cap_by_county.columns = ["county_fips", "facility_capacity"]

# ══════════════════════════════════════════════
# ANALYSIS A: Convergent Validity
# ══════════════════════════════════════════════

print("\n" + "=" * 70)
print("ANALYSIS A: CONVERGENT VALIDITY — 3SFCA vs Simple Ratio")
print("=" * 70)

# Get county-level 3SFCA ratio for 2021
county_2021 = main_df[
    (main_df["region_type"] == "county") & (main_df["year"] == 2021)
].copy()

sfca_ratio = county_2021[county_2021["measure"] == "daycare_ratio"][["geoid", "value"]].copy()
sfca_ratio.columns = ["county_fips", "sfca_ratio"]

# Merge all county-level data
analysis_a = (
    sfca_ratio
    .merge(cap_by_county, on="county_fips", how="inner")
    .merge(county_pop, on="county_fips", how="inner")
    .merge(county_area_df[["county_fips", "county_name"]], on="county_fips", how="left")
)

# Simple ratio: facility capacity within county / county pop * 1000
analysis_a["simple_ratio"] = analysis_a["facility_capacity"] / analysis_a["pop_under_15"] * 1000

# Drop counties with zero population or zero capacity
analysis_a = analysis_a[(analysis_a["pop_under_15"] > 0) & (analysis_a["facility_capacity"] > 0)].copy()

print(f"\nCounties in analysis: {len(analysis_a)}")
print(f"\nSimple ratio stats:")
print(f"  Mean: {analysis_a['simple_ratio'].mean():.1f}")
print(f"  SD:   {analysis_a['simple_ratio'].std():.1f}")
print(f"  Range: {analysis_a['simple_ratio'].min():.1f} – {analysis_a['simple_ratio'].max():.1f}")

print(f"\n3SFCA ratio stats:")
print(f"  Mean: {analysis_a['sfca_ratio'].mean():.1f}")
print(f"  SD:   {analysis_a['sfca_ratio'].std():.1f}")
print(f"  Range: {analysis_a['sfca_ratio'].min():.1f} – {analysis_a['sfca_ratio'].max():.1f}")

# Correlations
r_pearson, p_pearson = stats.pearsonr(analysis_a["simple_ratio"], analysis_a["sfca_ratio"])
r_spearman, p_spearman = stats.spearmanr(analysis_a["simple_ratio"], analysis_a["sfca_ratio"])

print(f"\nPearson r  = {r_pearson:.4f}  (p = {p_pearson:.2e})")
print(f"Spearman ρ = {r_spearman:.4f}  (p = {p_spearman:.2e})")

# Identify biggest divergences
analysis_a["ratio_diff"] = analysis_a["sfca_ratio"] - analysis_a["simple_ratio"]
analysis_a["abs_diff"] = analysis_a["ratio_diff"].abs()
top_divergent = analysis_a.nlargest(5, "abs_diff")[
    ["county_fips", "county_name", "simple_ratio", "sfca_ratio", "ratio_diff"]
]
print(f"\nTop 5 counties with largest divergence (3SFCA minus simple):")
for _, row in top_divergent.iterrows():
    print(f"  {row['county_name']:40s}  simple={row['simple_ratio']:7.1f}  3SFCA={row['sfca_ratio']:7.1f}  diff={row['ratio_diff']:+7.1f}")

# Scatter plot
fig, ax = plt.subplots(figsize=(8, 7))
ax.scatter(analysis_a["simple_ratio"], analysis_a["sfca_ratio"], alpha=0.6, s=40, edgecolors="k", linewidth=0.3)

# 1:1 reference line
lims = [0, max(analysis_a["simple_ratio"].max(), analysis_a["sfca_ratio"].max()) * 1.05]
ax.plot(lims, lims, "k--", alpha=0.4, linewidth=1, label="1:1 line")

# Regression line
slope, intercept, _, _, _ = stats.linregress(analysis_a["simple_ratio"], analysis_a["sfca_ratio"])
x_fit = np.linspace(lims[0], lims[1], 100)
ax.plot(x_fit, slope * x_fit + intercept, "r-", alpha=0.7, linewidth=1.5, label="OLS fit")

ax.set_xlabel("Simple Containment Ratio (seats per 1,000 children under 15)", fontsize=11)
ax.set_ylabel("3SFCA Accessibility Ratio (seats per 1,000 children under 15)", fontsize=11)
ax.set_title("Convergent Validity: 3SFCA vs Simple Provider-to-Child Ratio\nVirginia Counties, 2021", fontsize=13)

# Annotate
textstr = f"Pearson r = {r_pearson:.3f}\nSpearman ρ = {r_spearman:.3f}\nn = {len(analysis_a)} counties"
props = dict(boxstyle="round", facecolor="wheat", alpha=0.8)
ax.text(0.05, 0.95, textstr, transform=ax.transAxes, fontsize=10, verticalalignment="top", bbox=props)

ax.legend(loc="lower right", fontsize=10)
ax.set_xlim(lims)
ax.set_ylim(lims)
plt.tight_layout()
plt.savefig(FIG_DIR / "fig_convergent_validity.png", dpi=300, bbox_inches="tight")
plt.close()
print(f"\nSaved: {FIG_DIR / 'fig_convergent_validity.png'}")


# ══════════════════════════════════════════════
# ANALYSIS B: Urban vs Rural Disaggregation
# ══════════════════════════════════════════════

print("\n" + "=" * 70)
print("ANALYSIS B: URBAN vs RURAL DISAGGREGATION")
print("=" * 70)

# Get all county-level measures for 2021
measures_of_interest = ["daycare_ratio", "daycare_min_drivetime", "daycare_capacity",
                        "daycare_ratio_over_4", "daycare_ratio_under_10"]
county_wide = county_2021[county_2021["measure"].isin(measures_of_interest)].pivot_table(
    index="geoid", columns="measure", values="value", aggfunc="first"
).reset_index()
county_wide.columns.name = None
county_wide.rename(columns={"geoid": "county_fips"}, inplace=True)

# Merge with area and population
analysis_b = (
    county_wide
    .merge(county_area_df, on="county_fips", how="inner")
    .merge(county_pop, on="county_fips", how="inner")
)

# Compute population density (children per sq km) as urbanity proxy
analysis_b["child_density"] = analysis_b["pop_under_15"] / analysis_b["area_sqkm"]

# Classify by quartiles of child density
q25 = analysis_b["child_density"].quantile(0.25)
q75 = analysis_b["child_density"].quantile(0.75)

def classify(d):
    if d <= q25:
        return "Rural"
    elif d <= q75:
        return "Suburban"
    else:
        return "Urban"

analysis_b["classification"] = analysis_b["child_density"].apply(classify)

print(f"\nClassification thresholds (children under 15 per sq km):")
print(f"  Rural:    <= {q25:.2f}")
print(f"  Suburban: {q25:.2f} – {q75:.2f}")
print(f"  Urban:    > {q75:.2f}")

print(f"\nCounty counts by classification:")
print(analysis_b["classification"].value_counts().to_string())

# Summary statistics
print(f"\n{'─' * 80}")
print(f"{'Measure':<30s} {'Group':<12s} {'N':>4s} {'Mean':>10s} {'SD':>10s} {'Median':>10s}")
print(f"{'─' * 80}")

summary_rows = []
for measure in ["daycare_ratio", "daycare_min_drivetime", "daycare_ratio_over_4", "daycare_ratio_under_10"]:
    for group in ["Rural", "Suburban", "Urban"]:
        subset = analysis_b[analysis_b["classification"] == group][measure].dropna()
        n = len(subset)
        mean = subset.mean()
        sd = subset.std()
        med = subset.median()
        summary_rows.append({
            "measure": measure, "group": group, "n": n,
            "mean": mean, "sd": sd, "median": med
        })
        print(f"{measure:<30s} {group:<12s} {n:>4d} {mean:>10.1f} {sd:>10.1f} {med:>10.1f}")

# Statistical tests (Kruskal-Wallis for each measure)
print(f"\n{'─' * 80}")
print("Kruskal-Wallis H tests (Rural vs Suburban vs Urban):")
print(f"{'─' * 80}")
for measure in ["daycare_ratio", "daycare_min_drivetime", "daycare_ratio_over_4", "daycare_ratio_under_10"]:
    groups = [
        analysis_b[analysis_b["classification"] == g][measure].dropna()
        for g in ["Rural", "Suburban", "Urban"]
    ]
    if all(len(g) > 0 for g in groups):
        H, p = stats.kruskal(*groups)
        print(f"  {measure:<30s}  H = {H:8.2f},  p = {p:.2e}")

# ── Figure: Grouped bar chart ──
fig, axes = plt.subplots(1, 2, figsize=(13, 6))

colors = {"Rural": "#7fc97f", "Suburban": "#beaed4", "Urban": "#fdc086"}
group_order = ["Rural", "Suburban", "Urban"]

# Panel 1: daycare_ratio
ax = axes[0]
means = []
sds = []
for g in group_order:
    subset = analysis_b[analysis_b["classification"] == g]["daycare_ratio"].dropna()
    means.append(subset.mean())
    sds.append(subset.std())
x = np.arange(len(group_order))
bars = ax.bar(x, means, yerr=sds, capsize=5, color=[colors[g] for g in group_order],
              edgecolor="k", linewidth=0.5, alpha=0.85)
ax.set_xticks(x)
ax.set_xticklabels(group_order, fontsize=11)
ax.set_ylabel("Seats per 1,000 children under 15", fontsize=11)
ax.set_title("3SFCA Daycare Ratio by Urbanicity", fontsize=12)
# Add value labels
for i, (m, s) in enumerate(zip(means, sds)):
    ax.text(i, m + s + 5, f"{m:.0f}", ha="center", va="bottom", fontsize=10, fontweight="bold")

# Panel 2: daycare_min_drivetime
ax = axes[1]
means = []
sds = []
for g in group_order:
    subset = analysis_b[analysis_b["classification"] == g]["daycare_min_drivetime"].dropna()
    means.append(subset.mean())
    sds.append(subset.std())
bars = ax.bar(x, means, yerr=sds, capsize=5, color=[colors[g] for g in group_order],
              edgecolor="k", linewidth=0.5, alpha=0.85)
ax.set_xticks(x)
ax.set_xticklabels(group_order, fontsize=11)
ax.set_ylabel("Minutes", fontsize=11)
ax.set_title("Minimum Drive Time to Daycare by Urbanicity", fontsize=12)
for i, (m, s) in enumerate(zip(means, sds)):
    ax.text(i, m + s + 0.3, f"{m:.1f}", ha="center", va="bottom", fontsize=10, fontweight="bold")

fig.suptitle("Virginia Counties, 2021 — Classified by Child Population Density Quartiles",
             fontsize=13, y=1.02)
plt.tight_layout()
plt.savefig(FIG_DIR / "fig_urban_rural_disaggregation.png", dpi=300, bbox_inches="tight")
plt.close()
print(f"\nSaved: {FIG_DIR / 'fig_urban_rural_disaggregation.png'}")

# ── Figure: Box plots for all measures ──
fig, axes = plt.subplots(2, 2, figsize=(13, 10))

for ax, measure, title in zip(
    axes.flat,
    ["daycare_ratio", "daycare_min_drivetime", "daycare_ratio_over_4", "daycare_ratio_under_10"],
    ["3SFCA Ratio (all ages)", "Min Drive Time (min)", "3SFCA Ratio (over 4)", "3SFCA Ratio (under 10)"]
):
    data = [analysis_b[analysis_b["classification"] == g][measure].dropna().values for g in group_order]
    bp = ax.boxplot(data, labels=group_order, patch_artist=True, widths=0.6)
    for patch, g in zip(bp["boxes"], group_order):
        patch.set_facecolor(colors[g])
        patch.set_alpha(0.7)
    ax.set_title(title, fontsize=11)
    ax.set_ylabel("Value", fontsize=10)

fig.suptitle("Distribution of Daycare Accessibility Measures by Urbanicity\nVirginia Counties, 2021",
             fontsize=13)
plt.tight_layout()
plt.savefig(FIG_DIR / "fig_urban_rural_boxplots.png", dpi=300, bbox_inches="tight")
plt.close()
print(f"Saved: {FIG_DIR / 'fig_urban_rural_boxplots.png'}")

print("\n" + "=" * 70)
print("VALIDATION ANALYSES COMPLETE")
print("=" * 70)
