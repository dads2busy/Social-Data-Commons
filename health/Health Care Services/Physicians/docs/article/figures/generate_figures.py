"""Generate Technical Validation figures for physician accessibility data paper."""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parents[6]
FIG_DIR = Path(__file__).resolve().parent

# --- Load data ---
SPECIALTIES = {
    "Primary Care": {
        "va": REPO / "health/Health Care Services/Physicians/Primary Care/Service Access Scores/data/distribution/va_hdcttrbg_cms_2018_2025_access_scores_primcare.csv.xz",
        "prefix": "primcare",
        "years": list(range(2018, 2026)),
    },
    "OB-GYN": {
        "va": REPO / "health/Health Care Services/Physicians/OB-GYN/Service Access Scores/data/distribution/va_hdcttrbg_cms_2017_2025_access_scores_obgyn.csv.xz",
        "prefix": "obgyn",
        "years": list(range(2017, 2026)),
    },
    "Pediatric": {
        "va": REPO / "health/Health Care Services/Physicians/Pediatric/Service Access Scores/data/distribution/va_hdcttrbg_cms_2018_2025_access_scores_peds.csv.xz",
        "prefix": "peds",
        "years": list(range(2018, 2026)),
    },
}

COLORS = {"Primary Care": "#2166ac", "OB-GYN": "#b2182b", "Pediatric": "#1b7837"}


def load_va_bg(spec):
    """Load VA block-group-level data."""
    df = pd.read_csv(spec["va"], dtype={"geoid": str})
    return df[df["region_type"] == "block_group"]


def fig1_distribution(data_dict):
    """Figure 1: E2SFCA distribution histograms for each specialty (2025)."""
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)
    for ax, (name, spec) in zip(axes, SPECIALTIES.items()):
        df = data_dict[name]
        vals = df[(df["year"] == 2025) & (df["measure"] == f"{spec['prefix']}_e2sfca")]["value"].dropna()
        mean_val = vals.mean()
        med_val = vals.median()
        upper = mean_val + 2 * vals.std()
        clipped = vals.clip(upper=upper)
        ax.hist(clipped, bins=50, color=COLORS[name], alpha=0.7, edgecolor="white", linewidth=0.3)
        ax.axvline(med_val, color="black", linestyle="--", linewidth=1, label=f"Median={med_val:.3f}")
        ax.axvline(mean_val, color="black", linestyle="-", linewidth=1, label=f"Mean={mean_val:.3f}")
        ax.set_xlabel("E2SFCA (physicians per 1,000 pop.)", fontsize=9)
        ax.set_title(name, fontsize=11, fontweight="bold")
        ax.legend(fontsize=7, loc="upper right")
    axes[0].set_ylabel("Number of block groups", fontsize=9)
    fig.suptitle("Distribution of E2SFCA Scores (Virginia, 2025)", fontsize=12, y=1.02)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_e2sfca_distribution.png", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("Saved fig_e2sfca_distribution.png")


def fig2_temporal(data_dict):
    """Figure 2: Temporal consistency — consecutive-year Pearson r for E2SFCA."""
    fig, ax = plt.subplots(figsize=(8, 5))
    for name, spec in SPECIALTIES.items():
        df = data_dict[name]
        measure = f"{spec['prefix']}_e2sfca"
        years = spec["years"]
        correlations = []
        labels = []
        for i in range(len(years) - 1):
            y1, y2 = years[i], years[i + 1]
            v1 = df[(df["year"] == y1) & (df["measure"] == measure)].set_index("geoid")["value"]
            v2 = df[(df["year"] == y2) & (df["measure"] == measure)].set_index("geoid")["value"]
            common = v1.index.intersection(v2.index)
            r, _ = stats.pearsonr(v1.loc[common], v2.loc[common])
            correlations.append(r)
            labels.append(f"{y1}-{y2}")
        ax.plot(range(len(correlations)), correlations, marker="o", color=COLORS[name],
                label=name, linewidth=2, markersize=6)
    ax.axhline(0.9, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.set_xticks(range(max(len(spec["years"]) - 1 for spec in SPECIALTIES.values())))
    # Use the longest label set (OB-GYN has 8 pairs)
    obgyn_years = SPECIALTIES["OB-GYN"]["years"]
    tick_labels = [f"{obgyn_years[i]}-\n{obgyn_years[i+1]}" for i in range(len(obgyn_years) - 1)]
    ax.set_xticks(range(len(tick_labels)))
    ax.set_xticklabels(tick_labels, fontsize=8)
    ax.set_ylabel("Pearson r (consecutive years)", fontsize=10)
    ax.set_xlabel("Year pair", fontsize=10)
    ax.set_ylim(0.5, 1.02)
    ax.legend(fontsize=9)
    ax.set_title("Temporal Consistency of E2SFCA Scores (Virginia Block Groups)", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_temporal_consistency.png", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("Saved fig_temporal_consistency.png")


def fig3_convergent(data_dict):
    """Figure 3: Convergent validity — county E2SFCA vs provider count (2022)."""
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, (name, spec) in zip(axes, SPECIALTIES.items()):
        df_full = pd.read_csv(spec["va"], dtype={"geoid": str})
        county = df_full[(df_full["region_type"] == "county") & (df_full["year"] == 2022)]
        e2sfca = county[county["measure"] == f"{spec['prefix']}_e2sfca"].set_index("geoid")["value"]
        cnt = county[county["measure"] == f"{spec['prefix']}_cnt"].set_index("geoid")["value"]
        common = e2sfca.index.intersection(cnt.index)
        x, y = cnt.loc[common], e2sfca.loc[common]
        rho, _ = stats.spearmanr(x, y)
        r, _ = stats.pearsonr(x, y)
        ax.scatter(x, y, s=15, alpha=0.6, color=COLORS[name], edgecolors="none")
        ax.set_xlabel("Provider count", fontsize=9)
        ax.set_ylabel("Mean E2SFCA", fontsize=9)
        ax.set_title(name, fontsize=11, fontweight="bold")
        ax.annotate(f"Spearman ρ = {rho:.3f}\nPearson r = {r:.3f}",
                    xy=(0.95, 0.95), xycoords="axes fraction", fontsize=8,
                    ha="right", va="top",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="gray", alpha=0.8))
    fig.suptitle("Convergent Validity: E2SFCA vs. Provider Count (Virginia Counties, 2022)",
                 fontsize=11, y=1.02)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_convergent_validity.png", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("Saved fig_convergent_validity.png")


def fig4_urbanrural(data_dict):
    """Figure 4: Urban-rural disaggregation — E2SFCA and travel time by quartile."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    spec = SPECIALTIES["Primary Care"]
    df = data_dict["Primary Care"]
    yr = 2022
    prefix = spec["prefix"]

    # Get block group data for 2022
    e2sfca = df[(df["year"] == yr) & (df["measure"] == f"{prefix}_e2sfca")].set_index("geoid")["value"]
    near10 = df[(df["year"] == yr) & (df["measure"] == f"{prefix}_near_10_mean")].set_index("geoid")["value"]
    cnt = df[(df["year"] == yr) & (df["measure"] == f"{prefix}_cnt")].set_index("geoid")["value"]

    common = e2sfca.index.intersection(cnt.index).intersection(near10.index)
    merged = pd.DataFrame({"e2sfca": e2sfca.loc[common], "near10": near10.loc[common], "cnt": cnt.loc[common]})
    # Many block groups have zero providers, so use rank-based quartiles
    merged["rank"] = merged["cnt"].rank(method="first")
    merged["quartile"] = pd.qcut(merged["rank"], 4, labels=["Q1\n(lowest)", "Q2", "Q3", "Q4\n(highest)"])

    quartile_stats = merged.groupby("quartile", observed=True).agg(
        e2sfca_mean=("e2sfca", "mean"),
        e2sfca_se=("e2sfca", lambda x: x.std() / np.sqrt(len(x))),
        near10_mean=("near10", "mean"),
        near10_se=("near10", lambda x: x.std() / np.sqrt(len(x))),
    )

    x = range(len(quartile_stats))
    axes[0].bar(x, quartile_stats["e2sfca_mean"], yerr=quartile_stats["e2sfca_se"],
                color=COLORS["Primary Care"], alpha=0.7, capsize=4, edgecolor="white")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(quartile_stats.index, fontsize=9)
    axes[0].set_ylabel("Mean E2SFCA", fontsize=10)
    axes[0].set_xlabel("Provider count quartile", fontsize=10)
    axes[0].set_title("E2SFCA by Provider Quartile", fontsize=11)

    axes[1].bar(x, quartile_stats["near10_mean"], yerr=quartile_stats["near10_se"],
                color=COLORS["Primary Care"], alpha=0.7, capsize=4, edgecolor="white")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(quartile_stats.index, fontsize=9)
    axes[1].set_ylabel("Mean travel time (minutes)", fontsize=10)
    axes[1].set_xlabel("Provider count quartile", fontsize=10)
    axes[1].set_title("Travel Time by Provider Quartile", fontsize=11)

    fig.suptitle("Urban-Rural Disaggregation: Primary Care (Virginia, 2022)", fontsize=12, y=1.02)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_urban_rural.png", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("Saved fig_urban_rural.png")


def main():
    print("Loading data...")
    data_dict = {}
    for name, spec in SPECIALTIES.items():
        data_dict[name] = load_va_bg(spec)
        print(f"  {name}: {len(data_dict[name])} rows")

    print("\nGenerating figures...")
    fig1_distribution(data_dict)
    fig2_temporal(data_dict)
    fig3_convergent(data_dict)
    fig4_urbanrural(data_dict)
    print("\nDone. All figures saved to", FIG_DIR)


if __name__ == "__main__":
    main()
