"""Sensitivity analysis: Gaussian scale parameter for 3SFCA daycare accessibility."""

import sys
import time

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import pearsonr, spearmanr

from ingest import load_locations, load_population, load_travel_times
from sdc_core.catchment import catchment_ratio

# ── Load shared data ────────────────────────────────────────────────────
print("Loading locations for 2021...")
t0 = time.time()
locations = load_locations(2021)
print(f"  {len(locations)} rows in {time.time()-t0:.1f}s")

print("Loading population (ACS 2019)...")
t0 = time.time()
pop = load_population(2019, ["VA", "MD", "DC", "DE", "KY", "NC", "TN", "WV"])
print(f"  {len(pop)} block groups in {time.time()-t0:.1f}s")

print("Loading travel times...")
t0 = time.time()
travel_times = load_travel_times()
print(f"  {len(travel_times)} pairs in {time.time()-t0:.1f}s")

# Filter to VA consumers
va_pop = pop[pop["geoid"].str.startswith("51")].copy().reset_index(drop=True)
print(f"VA block groups: {len(va_pop)}")

# Filter providers for primary ratio (under 15, accepting ages 4-10)
mask_under_15 = (locations["age_min"] < 5) & (locations["age_max"] > 9)
filtered_locs = locations[mask_under_15].copy()
print(f"Providers matching age filter: {len(filtered_locs)}")

# Aggregate providers by lid
prov_info = (
    filtered_locs.groupby("lid")
    .agg({"bg_geoid": "first", "capacity": "sum"})
    .reset_index()
)
provider_bgs = prov_info["bg_geoid"].values
provider_lids = prov_info["lid"].values
print(f"Unique provider locations: {len(prov_info)}")

# ── Build cost matrix (vectorized) ─────────────────────────────────────
print("Building cost matrix...")
t0 = time.time()

consumer_geoids = va_pop["geoid"].values
n_consumers = len(consumer_geoids)
n_providers = len(provider_lids)

# Create index mappings
consumer_idx_map = pd.Series(np.arange(n_consumers), index=consumer_geoids)
# provider index by bg_geoid -> list of provider column indices
prov_bg_to_cols = {}
for j, bg in enumerate(provider_bgs):
    prov_bg_to_cols.setdefault(bg, []).append(j)

provider_bg_set = set(prov_info["bg_geoid"].unique())
consumer_set = set(consumer_geoids)

# Start with large default cost
cost_matrix = np.full((n_consumers, n_providers), 1e6, dtype=np.float32)

# Handle self-pairs: consumer BG == provider BG -> cost = 0
for bg, cols in prov_bg_to_cols.items():
    if bg in consumer_set:
        i = consumer_idx_map[bg]
        for j in cols:
            cost_matrix[i, j] = 0.0

# Filter travel times to relevant pairs
tt_relevant = travel_times[
    travel_times["bg_dest"].isin(provider_bg_set)
    & travel_times["bg_orig"].isin(consumer_set)
].copy()
print(f"  Relevant travel time pairs: {len(tt_relevant)}")

# Map orig -> consumer row index
tt_relevant["c_idx"] = consumer_idx_map.reindex(tt_relevant["bg_orig"].values).values

# For each dest BG, fill in all provider columns at that BG
for bg, cols in prov_bg_to_cols.items():
    subset = tt_relevant[tt_relevant["bg_dest"] == bg]
    if subset.empty:
        continue
    c_idxs = subset["c_idx"].values.astype(int)
    times = subset["time_mins"].values.astype(np.float32)
    for j in cols:
        cost_matrix[c_idxs, j] = np.minimum(cost_matrix[c_idxs, j], times)

elapsed = time.time() - t0
print(f"  Cost matrix shape: {cost_matrix.shape}, built in {elapsed:.1f}s")
print(f"  Reachable pairs (cost < 1e6): {(cost_matrix < 1e6).sum():,}")

# Build consumer and provider DataFrames
consumers_df = pd.DataFrame({
    "geoid": consumer_geoids,
    "value": va_pop["pop_under_15"].values.astype(float),
})
providers_df = pd.DataFrame({
    "lid": provider_lids,
    "value": prov_info["capacity"].values.astype(float),
})

# ── Compute 3SFCA for different Gaussian scale values ──────────────────
test_scales = [10, 14, 18, 22, 26, 30]
results = {}

for gs in test_scales:
    s = gs / np.sqrt(2)
    print(f"Computing 3SFCA with GAUSSIAN_SCALE={gs} (s={s:.2f})...")
    t0 = time.time()
    access = catchment_ratio(
        consumers=consumers_df,
        providers=providers_df,
        cost=cost_matrix,
        weight="gaussian",
        scale=s,
        normalize_weight=True,
        consumers_id="geoid",
        consumers_value="value",
        providers_id="lid",
        providers_value="value",
        return_type=1000,
    )
    elapsed = time.time() - t0
    vals = access.reindex(consumer_geoids).fillna(0).values
    results[gs] = vals
    nonzero = (vals > 0).sum()
    print(f"  Done in {elapsed:.1f}s | mean={vals.mean():.2f} | median={np.median(vals):.2f} | nonzero={nonzero}")

# ── Analysis ───────────────────────────────────────────────────────────
baseline = results[18]

print("\n" + "=" * 85)
print("Sensitivity Analysis: Gaussian Scale Parameter for 3SFCA Daycare Accessibility")
print("=" * 85)
print(f"\nBaseline: GAUSSIAN_SCALE = 18 (s = {18/np.sqrt(2):.2f})")
print(f"Consumer block groups (VA): {n_consumers}")
print(f"Provider locations: {n_providers}")
print(f"Population column: pop_under_15")
print()

# Winsorize at 99th percentile to handle extreme outliers from tiny-population BGs
p99 = np.percentile(np.concatenate(list(results.values())), 99)
print(f"Note: Winsorizing at p99={p99:.1f} for Pearson r and trimmed mean.\n")

results_w = {}
for gs in test_scales:
    results_w[gs] = np.clip(results[gs], 0, p99)
baseline_w = results_w[18]

header = f"{'Scale':>6} {'s=GS/√2':>8} {'Pearson r':>10} {'Pearson(w)':>11} {'Spearman ρ':>11} {'Mean':>8} {'TrMean':>8} {'Median':>8} {'P10':>8} {'P90':>8} {'Mean %Δ':>9}"
print(header)
print("-" * len(header))

for gs in test_scales:
    v = results[gs]
    vw = results_w[gs]
    s = gs / np.sqrt(2)
    r_p, _ = pearsonr(baseline, v)
    r_pw, _ = pearsonr(baseline_w, vw)
    r_s, _ = spearmanr(baseline, v)
    mean_val = v.mean()
    trimmed_mean = vw.mean()
    median_val = np.median(v)
    p10 = np.percentile(v, 10)
    p90 = np.percentile(v, 90)
    pct_diff = (trimmed_mean - baseline_w.mean()) / baseline_w.mean() * 100 if baseline_w.mean() != 0 else 0
    marker = " <--" if gs == 18 else ""
    print(f"{gs:>6} {s:>8.2f} {r_p:>10.6f} {r_pw:>11.6f} {r_s:>11.6f} {mean_val:>8.2f} {trimmed_mean:>8.2f} {median_val:>8.2f} {p10:>8.2f} {p90:>8.2f} {pct_diff:>8.1f}%{marker}")

# Rank concordance: how many BGs change quintile?
print("\n\nQuintile migration from baseline (scale=18):")
baseline_quintiles = pd.qcut(baseline, 5, labels=False, duplicates="drop")
print(f"{'Scale':>6} {'Same quintile':>14} {'±1 quintile':>12} {'±2+ quintile':>13}")
print("-" * 50)
for gs in test_scales:
    if gs == 18:
        continue
    alt_quintiles = pd.qcut(results[gs], 5, labels=False, duplicates="drop")
    diff = np.abs(baseline_quintiles - alt_quintiles)
    same = (diff == 0).sum() / n_consumers * 100
    one = (diff == 1).sum() / n_consumers * 100
    two_plus = (diff >= 2).sum() / n_consumers * 100
    print(f"{gs:>6} {same:>13.1f}% {one:>11.1f}% {two_plus:>12.1f}%")

# ── Figure ─────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))

means = [results_w[gs].mean() for gs in test_scales]
medians = [np.median(results[gs]) for gs in test_scales]
p10s = [np.percentile(results[gs], 10) for gs in test_scales]
p90s = [np.percentile(results[gs], 90) for gs in test_scales]
pearsons = [pearsonr(baseline_w, results_w[gs])[0] for gs in test_scales]
spearmans = [spearmanr(baseline, results[gs])[0] for gs in test_scales]

# Panel 1: ratio magnitude
ax1 = axes[0]
ax1.fill_between(test_scales, p10s, p90s, alpha=0.15, color="#2166ac")
ax1.plot(test_scales, means, "o-", color="#2166ac", label="Trimmed mean", linewidth=2, markersize=7)
ax1.plot(test_scales, medians, "s--", color="#b2182b", label="Median", linewidth=2, markersize=7)
ax1.axvline(x=18, color="gray", linestyle=":", alpha=0.7, label="Default (18)")
ax1.set_xlabel("Gaussian scale parameter (minutes)", fontsize=11)
ax1.set_ylabel("daycare_ratio (seats per 1,000 children)", fontsize=11)
ax1.set_title("Effect on ratio magnitude", fontsize=12)
ax1.legend(fontsize=9)

# Panel 2: correlation
ax2 = axes[1]
ax2.plot(test_scales, pearsons, "o-", color="#2166ac", label="Pearson r (winsorized)", linewidth=2, markersize=7)
ax2.plot(test_scales, spearmans, "s--", color="#b2182b", label="Spearman \u03c1", linewidth=2, markersize=7)
ax2.axvline(x=18, color="gray", linestyle=":", alpha=0.7, label="Default (18)")
ax2.set_xlabel("Gaussian scale parameter (minutes)", fontsize=11)
ax2.set_ylabel("Correlation with default (scale=18)", fontsize=11)
ax2.set_title("Rank stability across parameter values", fontsize=12)
ax2.set_ylim(0.85, 1.005)
ax2.legend(fontsize=9)

# Panel 3: scatter of most extreme vs baseline (winsorized)
ax3 = axes[2]
extreme_gs = test_scales[0]  # scale=10 is most different
ax3.scatter(baseline_w, results_w[extreme_gs], s=3, alpha=0.3, color="#2166ac", edgecolors="none")
max_val = max(baseline_w.max(), results_w[extreme_gs].max()) * 1.05
ax3.plot([0, max_val], [0, max_val], "k--", alpha=0.5, linewidth=1)
ax3.set_xlabel(f"daycare_ratio (scale=18)", fontsize=11)
ax3.set_ylabel(f"daycare_ratio (scale={extreme_gs})", fontsize=11)
ax3.set_title(f"BG-level comparison: scale={extreme_gs} vs 18", fontsize=12)
ax3.set_xlim(0, max_val)
ax3.set_ylim(0, max_val)

plt.tight_layout()
out_path = "/Users/ads7fg/git/sdc-monorepo/education/Daycare Accessibility/docs/figures/fig_sensitivity_analysis.png"
plt.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
print(f"\nFigure saved to {out_path}")
print("\nDone.")
