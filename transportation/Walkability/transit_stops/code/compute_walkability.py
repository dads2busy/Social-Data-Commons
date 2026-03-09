"""Compute multi-year walkability index for NCR block groups.

Uses time-varying D2A/D2B from LODES + ACS (computed by compute_d2.py),
EPA SLD D3B_Ranked (stable street connectivity), and our transit proximity
ranking (D4C distance to nearest stop, ranked into 20 quantiles).

Formula: NatWalkInd = D2A_Ranked/6 + D2B_Ranked/6 + D3B_Ranked/3 + D4_Ranked/3

Usage:
    uv run python compute_walkability.py --coverage ncr

Output: data/walkability/{coverage}_walkability_{year}.parquet
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sdc_core.log import get_logger

BASE_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BASE_DIR.parents[1]
D4C_DIR = BASE_DIR / "data/d4c"
D2_DIR = BASE_DIR / "data/d2"
OUT_DIR = BASE_DIR / "data/walkability"

SLD_PATH = REPO_DIR / "transportation/Walkability/data/working/sld_v3.csv"

log = get_logger("transit_stops.compute_walkability")

# Walkability formula weights
W_D2A = 1 / 6
W_D2B = 1 / 6
W_D3B = 1 / 3
W_D4 = 1 / 3


def load_sld_d3b() -> pd.DataFrame:
    """Load EPA SLD D3B_Ranked (street connectivity) for block groups (2010 vintage)."""
    sld = pd.read_csv(
        SLD_PATH,
        usecols=["STATEFP", "COUNTYFP", "TRACTCE", "BLKGRPCE",
                 "D3B_Ranked", "D4A_Ranked", "NatWalkInd", "TotPop"],
        dtype={"STATEFP": str, "COUNTYFP": str, "TRACTCE": str, "BLKGRPCE": str},
    )
    sld["STATEFP"] = sld["STATEFP"].str.zfill(2)
    sld["COUNTYFP"] = sld["COUNTYFP"].str.zfill(3)
    sld["TRACTCE"] = sld["TRACTCE"].str.zfill(6)
    sld["BLKGRPCE"] = sld["BLKGRPCE"].str.zfill(1)
    sld["geoid"] = sld["STATEFP"] + sld["COUNTYFP"] + sld["TRACTCE"] + sld["BLKGRPCE"]
    return sld


def rank_into_quantiles(values: pd.Series, n_bins: int = 20,
                        ascending: bool = True) -> pd.Series:
    """Rank values into quantile bins (1-20).

    Args:
        values: Series to rank
        n_bins: Number of quantile bins
        ascending: If True, highest values get rank 20.
                   If False, lowest values get rank 20 (for distance-type measures).
    """
    ranks = values.rank(method="first", ascending=True)
    bins = pd.qcut(ranks, q=n_bins, labels=False) + 1  # 1-20
    if not ascending:
        bins = n_bins + 1 - bins
    return bins


def run(coverage: str):
    if not SLD_PATH.exists():
        raise FileNotFoundError(
            f"SLD CSV not found at {SLD_PATH}. "
            "Run walkability ingest first to download the EPA SLD."
        )

    log.info("Loading EPA SLD D3B component")
    sld = load_sld_d3b()

    state_fips = {
        "ncr": ["11", "24", "51"],
        "va": ["51"],
        "us": None,  # All states — no filtering
    }
    states = state_fips[coverage]

    # Filter SLD to coverage area
    if states is None:
        sld_area = sld.copy()
    else:
        sld_area = sld[sld["geoid"].str[:2].isin(states)].copy()
    log.info("SLD block groups in %s: %d", coverage.upper(), len(sld_area))

    # Find available D4C files (2010 vintage to match SLD)
    d4c_files = sorted(D4C_DIR.glob(f"{coverage}_d4c_bg2010_*.parquet"))
    if not d4c_files:
        raise FileNotFoundError(
            f"No D4C files found. Run compute_d4c.py --geo-vintage 2010 --coverage {coverage} first."
        )

    d4c_years = {int(f.stem.split("_")[-1]): f for f in d4c_files}

    # Find available D2 files
    d2_files = sorted(D2_DIR.glob(f"{coverage}_d2_bg2020_*.parquet"))
    d2_years = {int(f.stem.split("_")[-1]): f for f in d2_files}

    # Process years that have both D4C and D2
    common_years = sorted(set(d4c_years) & set(d2_years))
    if not common_years:
        raise FileNotFoundError("No years with both D4C and D2 data.")
    log.info("Computing walkability for years: %s", common_years)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for year in common_years:
        d4c = pd.read_parquet(d4c_years[year])
        d2 = pd.read_parquet(d2_years[year])

        # Start with SLD (2010 vintage BGs) for D3B
        merged = sld_area[["geoid", "D3B_Ranked", "D4A_Ranked", "NatWalkInd", "TotPop"]].copy()

        # Merge D4C (also 2010 vintage)
        merged = merged.merge(d4c[["geoid", "d4c_dist_mi"]], on="geoid", how="inner")

        # D2 is on 2020 vintage BGs — crosswalk by truncating to tract (11 chars)
        # and using tract-level D2 values for each BG within that tract.
        # This is a reasonable approximation since LODES BGs are 2020 but SLD is 2010.
        d2["tract_geoid"] = d2["geoid"].str[:11]
        d2_tract = d2.groupby("tract_geoid").agg(
            D2A_EPHHM=("D2A_EPHHM", "mean"),
            D2B_E5MIX=("D2B_E5MIX", "mean"),
        ).reset_index()

        merged["tract_geoid"] = merged["geoid"].str[:11]
        merged = merged.merge(d2_tract, on="tract_geoid", how="left")
        merged = merged.drop(columns=["tract_geoid"])

        # Fill missing D2 values with 0 (block groups with no employment data)
        merged["D2A_EPHHM"] = merged["D2A_EPHHM"].fillna(0)
        merged["D2B_E5MIX"] = merged["D2B_E5MIX"].fillna(0)

        n_with_d2 = (merged["D2A_EPHHM"] > 0).sum()
        log.info("Year %d: %d BGs with SLD+D4C, %d with D2 data",
                 year, len(merged), n_with_d2)

        # Rank our D2A, D2B, and D4C into 20 quantile bins
        merged["d2a_ranked"] = rank_into_quantiles(merged["D2A_EPHHM"], ascending=True)
        merged["d2b_ranked"] = rank_into_quantiles(merged["D2B_E5MIX"], ascending=True)
        merged["d4c_ranked"] = rank_into_quantiles(merged["d4c_dist_mi"], ascending=False)

        # Compute walkability index
        merged["walkability_index"] = (
            W_D2A * merged["d2a_ranked"]
            + W_D2B * merged["d2b_ranked"]
            + W_D3B * merged["D3B_Ranked"]
            + W_D4 * merged["d4c_ranked"]
        ).round(1)

        # Output
        out = merged[[
            "geoid", "walkability_index", "D2A_EPHHM", "D2B_E5MIX",
            "d2a_ranked", "d2b_ranked", "D3B_Ranked", "d4c_dist_mi", "d4c_ranked",
            "D4A_Ranked", "NatWalkInd", "TotPop",
        ]].copy()
        out.columns = [
            "geoid", "walkability_index", "d2a_ephhm", "d2b_e5mix",
            "d2a_ranked", "d2b_ranked", "d3b_ranked", "d4c_dist_mi", "d4c_ranked",
            "epa_d4a_ranked", "epa_walkability", "tot_pop",
        ]
        out["year"] = year

        out_path = OUT_DIR / f"{coverage}_walkability_{year}.parquet"
        out.to_parquet(out_path, index=False)

        # Validation stats
        corr = out["walkability_index"].corr(out["epa_walkability"])
        rmse = np.sqrt(((out["walkability_index"] - out["epa_walkability"]) ** 2).mean())

        log.info(
            "Year %d: mean=%.1f, median=%.1f (EPA: mean=%.1f) | "
            "corr=%.3f, RMSE=%.2f → %s",
            year,
            out["walkability_index"].mean(),
            out["walkability_index"].median(),
            out["epa_walkability"].mean(),
            corr, rmse, out_path.name,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute multi-year walkability index")
    parser.add_argument("--coverage", required=True, choices=["ncr", "va", "us"])
    args = parser.parse_args()
    run(args.coverage)
