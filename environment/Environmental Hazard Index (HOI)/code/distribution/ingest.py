"""Ingest EPA EJScreen data and compute Environmental Hazard Index.

Replaces: meta/all/data/sdc.environment/environmental_justice/code/distribution/
          ingest_EJSCREEN.R, prepare_ehi_bg.R, prepare_ehi_tract.R

Steps:
1. Read EJScreen block-group CSVs (2016-2024) from data/original/
2. Filter to target block groups by state/county FIPS
3. Extract 12 environmental variables (backfill UST from 2021 for 2016-2020)
4. Run PCA (1 component) per year on the filtered variables
5. Standardize PC1 scores to z-scores = environmental_hazard_index
6. Aggregate block groups to tracts via population-weighted mean
7. Write tract-level output to data/distribution/

Note: 2024 EJScreen dropped CANCER and RESP columns, so 2024 uses 10 variables.
"""

import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from sdc_core.geo import convert_2010_to_2020_bounds
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
ORIG_DIR = TOPIC_DIR / "data/original"
DIST_DIR = TOPIC_DIR / "data/distribution"

# The 12 EJScreen environmental indicator variables used in legacy R pipeline
PCA_VARS_FULL = [
    "CANCER",       # Air toxics cancer risk
    "RESP",         # Air toxics respiratory hazard index
    "PTRAF",        # Traffic proximity and volume
    "PWDIS",        # Wastewater discharge indicator
    "PNPL",         # Proximity to NPL (Superfund) sites
    "PRMP",         # Proximity to RMP facilities
    "PTSDF",        # Proximity to TSDF facilities
    "OZONE",        # Ozone level
    "PM25",         # PM2.5 level
    "PRE1960PCT",   # Pre-1960 housing percentage
    "DSLPM",        # Diesel particulate matter
    "UST",          # Underground storage tanks
]

# 2024 dropped CANCER and RESP
PCA_VARS_REDUCED = [v for v in PCA_VARS_FULL if v not in ("CANCER", "RESP")]

YEARS = list(range(2016, 2025))
MEASURE_NAME = "environmental_hazard_index"

# Map year to the CSV filename inside the zip (or bare CSV)
EJSCREEN_FILES = {
    2016: ("EJSCREEN_2016.csv.zip", "EJSCREEN_Full_V3_USPR_TSDFupdate.csv"),
    2017: ("EJSCREEN_2017.csv", None),  # not zipped
    2018: ("EJSCREEN_2018.csv.zip", "EJSCREEN_Full_USPR_2018.csv"),
    2019: ("EJSCREEN_2019.csv.zip", "EJSCREEN_2019_USPR.csv"),
    2020: ("EJSCREEN_2020.csv.zip", "EJSCREEN_2020_USPR.csv"),
    2021: ("EJSCREEN_2021.csv.zip", "EJSCREEN_2021_USPR.csv"),
    2022: ("EJSCREEN_2022.csv.zip", "EJSCREEN_2022_Full_with_AS_CNMI_GU_VI.csv"),
    2023: ("EJSCREEN_2023.csv.zip", "EJSCREEN_2023_BG_with_AS_CNMI_GU_VI.csv"),
    2024: ("EJSCREEN_2024.csv.zip", "EJSCREEN_2024_BG_with_AS_CNMI_GU_VI.csv"),
}

# NCR county FIPS (5-digit) for filtering
NCR_COUNTY_FIPS = {
    "51059", "51600", "51610", "51107", "51013", "51510", "51683", "51685", "51153",
    "24021", "24031", "24033", "24017",
    "11001",
}

log = get_logger("env_hazard.ingest")


def _read_ejscreen_raw(year: int) -> pd.DataFrame:
    """Read the full EJScreen CSV for a given year (all US block groups)."""
    filename, inner_name = EJSCREEN_FILES[year]
    path = ORIG_DIR / filename

    log.info("Reading EJScreen %d: %s", year, path.name)

    def _read_csv(source):
        """Read CSV, trying utf-8-sig first (handles BOM), then latin-1."""
        try:
            return pd.read_csv(source, dtype={"ID": str}, low_memory=False, encoding="utf-8-sig")
        except UnicodeDecodeError:
            if hasattr(source, "seek"):
                source.seek(0)
            return pd.read_csv(source, dtype={"ID": str}, low_memory=False, encoding="latin-1")

    if inner_name is None:
        df = _read_csv(path)
    else:
        with zipfile.ZipFile(path) as zf:
            with zf.open(inner_name) as f:
                df = _read_csv(f)

    # Strip any remaining BOM from column names
    df.columns = [c.lstrip("\ufeff").strip() for c in df.columns]
    df["ID"] = df["ID"].astype(str).str.strip()

    return df


def filter_ejscreen(df: pd.DataFrame, state_fips: set[str] | None = None,
                     county_fips: set[str] | None = None) -> pd.DataFrame:
    """Filter EJScreen data to block groups matching state or county FIPS."""
    # Only keep 12-digit block group GEOIDs
    mask = df["ID"].str.len() == 12

    if county_fips:
        mask = mask & df["ID"].str[:5].isin(county_fips)
    elif state_fips:
        mask = mask & df["ID"].str[:2].isin(state_fips)

    result = df[mask].copy()
    return result


def extract_pca_vars(df: pd.DataFrame, year: int, ust_backfill: pd.Series | None = None) -> pd.DataFrame:
    """Extract the PCA input variables, handling missing columns."""
    # Determine which variables to use
    if year == 2024:
        pca_vars = PCA_VARS_REDUCED
    else:
        pca_vars = PCA_VARS_FULL

    result = df[["ID"]].copy()

    for var in pca_vars:
        if var in df.columns:
            result[var] = pd.to_numeric(df[var], errors="coerce")
        elif var == "UST" and ust_backfill is not None:
            # UST not available before 2021; backfill from 2021
            result = result.merge(
                ust_backfill.rename("UST"), left_on="ID", right_index=True, how="left"
            )
            log.info("  Backfilled UST from 2021 for %d", year)
        else:
            log.warning("  Variable %s missing in %d, filling with 0", var, year)
            result[var] = 0.0

    # Fill NAs with 0 (matching legacy R behavior)
    for var in pca_vars:
        result[var] = result[var].fillna(0.0)

    return result, pca_vars


def compute_ehi(df: pd.DataFrame, pca_vars: list[str]) -> pd.Series:
    """Compute Environmental Hazard Index via PCA on the given variables.

    R's psych::principal() uses the correlation matrix (standardized variables).
    We replicate this by standardizing before PCA.

    Returns standardized PC1 z-scores (higher = more environmental hazard).
    """
    from sklearn.preprocessing import StandardScaler

    X = df[pca_vars].values

    # Standardize variables (matching R's principal() which uses correlation matrix)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # PCA with 1 component
    pca = PCA(n_components=1)
    scores = pca.fit_transform(X_scaled).ravel()

    # Standardize to z-scores
    z = (scores - scores.mean()) / scores.std()

    log.info("  PCA: explained variance ratio = %.4f", pca.explained_variance_ratio_[0])
    log.info("  Top loadings: %s", ", ".join(
        f"{v}={w:.3f}" for v, w in
        sorted(zip(pca_vars, pca.components_[0]), key=lambda x: abs(x[1]), reverse=True)[:5]
    ))
    log.info("  EHI z-scores: mean=%.4f, std=%.4f, range=[%.3f, %.3f]",
             z.mean(), z.std(), z.min(), z.max())

    return pd.Series(z, index=df.index)


def aggregate_bg_to_tract(
    bg_df: pd.DataFrame, pop_df: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Aggregate block-group EHI to tract level.

    Uses population-weighted mean if population data available, otherwise simple mean.
    """
    bg_df = bg_df.copy()
    bg_df["tract_geoid"] = bg_df["geoid"].str[:11]

    if pop_df is not None and len(pop_df) > 0:
        bg_df = bg_df.merge(pop_df[["geoid", "pop"]], on="geoid", how="left")
        bg_df["pop"] = bg_df["pop"].fillna(0)
        bg_df["weighted_value"] = bg_df["value"] * bg_df["pop"]

        tracts = bg_df.groupby("tract_geoid").agg(
            weighted_sum=("weighted_value", "sum"),
            pop_sum=("pop", "sum"),
        ).reset_index()

        # Avoid division by zero
        tracts["value"] = np.where(
            tracts["pop_sum"] > 0,
            tracts["weighted_sum"] / tracts["pop_sum"],
            np.nan,
        )
        method = "population-weighted"
    else:
        tracts = bg_df.groupby("tract_geoid")["value"].mean().reset_index()
        method = "simple mean"

    tracts = tracts.rename(columns={"tract_geoid": "geoid"})[["geoid", "value"]]
    log.info("  Aggregated %d BGs → %d tracts (%s)", len(bg_df), len(tracts), method)
    return tracts


def load_bg_populations(year: int, coverage: str = "va") -> pd.DataFrame | None:
    """Try to load block-group population data for weighting."""
    demo_dir = REPO_DIR / "demographics/Population/data/distribution"
    if not demo_dir.exists():
        return None

    # Try coverage-specific file first, then fall back to any population file
    for prefix in (coverage, "va", "ncr"):
        candidates = list(demo_dir.glob(f"{prefix}_*population*.csv.xz"))
        if candidates:
            break
    else:
        return None

    path = max(candidates, key=lambda p: p.stat().st_mtime)
    log.info("  Loading BG populations from: %s", path.name)

    df = pd.read_csv(path, dtype={"geoid": str})
    # Filter to block groups for the requested year
    bg_pop = df[
        (df["region_type"] == "block_group")
        & (df["year"] == year)
        & (df["measure"].str.contains("population", case=False))
    ].copy()

    if len(bg_pop) == 0:
        return None

    bg_pop = bg_pop[["geoid", "value"]].rename(columns={"value": "pop"})
    bg_pop["pop"] = pd.to_numeric(bg_pop["pop"], errors="coerce").fillna(0)
    log.info("  Found %d BG population records for %d", len(bg_pop), year)
    return bg_pop


def _process_coverage(
    coverage: str,
    state_fips: set[str] | None,
    county_fips: set[str] | None,
    raw_cache: dict[int, pd.DataFrame],
    ust_backfill: pd.Series,
) -> pd.DataFrame:
    """Process EJScreen data for a single coverage area (VA or NCR)."""
    log.info("=== Processing %s ===", coverage.upper())

    all_frames = []

    for year in YEARS:
        log.info("--- %s %d ---", coverage.upper(), year)

        # Filter cached raw data
        filtered = filter_ejscreen(raw_cache[year], state_fips=state_fips, county_fips=county_fips)
        log.info("  %s block groups: %d", coverage.upper(), len(filtered))

        if len(filtered) == 0:
            log.warning("  No block groups for %s in %d, skipping", coverage, year)
            continue

        # Extract PCA variables
        pca_df, pca_vars = extract_pca_vars(filtered, year, ust_backfill=ust_backfill)

        # Compute EHI via PCA
        pca_df["value"] = compute_ehi(pca_df, pca_vars)
        pca_df["geoid"] = pca_df["ID"]

        # Load population weights for BG→tract aggregation
        pop_df = load_bg_populations(year, coverage=coverage)

        # Aggregate to tracts
        tracts = aggregate_bg_to_tract(pca_df[["geoid", "value"]], pop_df)
        tracts["year"] = year
        tracts["data_method"] = "observed"

        if year == 2024:
            tracts["data_method"] = "observed_reduced_vars"

        all_frames.append(tracts)

    if not all_frames:
        return pd.DataFrame()

    combined = pd.concat(all_frames, ignore_index=True)

    # --- Geography standardization ---
    GEO_2010_YEARS = list(range(2016, 2022))  # 2016-2021 on 2010 boundaries
    output_frames = []

    for year in YEARS:
        year_data = combined[combined["year"] == year].copy()
        if year_data.empty:
            continue

        if year in GEO_2010_YEARS:
            # Keep original 2010 geo rows as _geo10
            geo10 = year_data.copy()
            geo10["measure"] = f"{MEASURE_NAME}_geo10"
            geo10["moe"] = pd.NA
            geo10["region_type"] = "tract"
            output_frames.append(geo10[["geoid", "year", "measure", "value", "moe", "region_type"]])

            # Crosswalk to 2020 geo
            converted = convert_2010_to_2020_bounds(
                year_data[["geoid", "value"]],
                geoid_col="geoid",
                val_col="value",
            )
            converted["year"] = year
            converted["measure"] = f"{MEASURE_NAME}_geo20"
            converted["moe"] = pd.NA
            converted["region_type"] = "tract"
            output_frames.append(converted[["geoid", "year", "measure", "value", "moe", "region_type"]])
            log.info("  %d: crosswalked %d tracts (geo10) → %d tracts (geo20)",
                     year, len(geo10), len(converted))
        else:
            geo20 = year_data.copy()
            geo20["measure"] = f"{MEASURE_NAME}_geo20"
            geo20["moe"] = pd.NA
            geo20["region_type"] = "tract"
            output_frames.append(geo20[["geoid", "year", "measure", "value", "moe", "region_type"]])
            log.info("  %d: %d tracts (already geo20)", year, len(geo20))

    result = pd.concat(output_frames, ignore_index=True)
    result = result.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

    log.info(
        "%s final: %d rows, %d unique tracts, years %s",
        coverage.upper(),
        len(result),
        result["geoid"].nunique(),
        sorted(result["year"].unique()),
    )
    return result


def run() -> list[RunResult]:
    t0 = time.time()
    results = []

    try:
        # Read all EJScreen files once (they're large, avoid re-reading)
        log.info("Pre-loading all EJScreen files...")
        raw_cache: dict[int, pd.DataFrame] = {}
        for year in YEARS:
            raw_cache[year] = _read_ejscreen_raw(year)

        # Get UST backfill from 2021 (all US, then filter will apply per-coverage)
        ust_2021 = raw_cache[2021]
        ust_backfill = pd.to_numeric(ust_2021.set_index("ID")["UST"], errors="coerce").fillna(0.0)
        log.info("UST backfill: %d block groups", len(ust_backfill))

        DIST_DIR.mkdir(parents=True, exist_ok=True)

        # --- VA ---
        va_result = _process_coverage(
            coverage="va",
            state_fips={"51"},
            county_fips=None,
            raw_cache=raw_cache,
            ust_backfill=ust_backfill,
        )
        if not va_result.empty:
            va_name = build_file_name(
                coverage_area="va",
                data_source="epa",
                years=sorted(va_result["year"].unique().tolist()),
                title="environmental_hazard",
                geographies=["tract"],
            )
            va_path = write_data(va_result, DIST_DIR / f"{va_name}.csv.xz")
            log.info("Wrote VA: %s", va_path)
            results.append(RunResult(
                success=True, rows=len(va_result),
                output_path=str(va_path), duration_sec=time.time() - t0,
            ))

        # --- NCR ---
        ncr_result = _process_coverage(
            coverage="ncr",
            state_fips=None,
            county_fips=NCR_COUNTY_FIPS,
            raw_cache=raw_cache,
            ust_backfill=ust_backfill,
        )
        if not ncr_result.empty:
            ncr_name = build_file_name(
                coverage_area="ncr",
                data_source="epa",
                years=sorted(ncr_result["year"].unique().tolist()),
                title="environmental_hazard",
                geographies=["tract"],
            )
            ncr_path = write_data(ncr_result, DIST_DIR / f"{ncr_name}.csv.xz")
            log.info("Wrote NCR: %s", ncr_path)
            results.append(RunResult(
                success=True, rows=len(ncr_result),
                output_path=str(ncr_path), duration_sec=time.time() - t0,
            ))

        if not results:
            results.append(RunResult(success=False, error="No output produced", duration_sec=time.time() - t0))

    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        results.append(RunResult(success=False, error=str(e), duration_sec=time.time() - t0))

    return results


if __name__ == "__main__":
    results = run()
    for r in results:
        if r.success:
            log.info("OK: %d rows → %s (%.1fs)", r.rows, r.output_path, r.duration_sec)
        else:
            log.error("FAIL: %s (%.1fs)", r.error, r.duration_sec)
    if any(not r.success for r in results):
        raise SystemExit(1)
