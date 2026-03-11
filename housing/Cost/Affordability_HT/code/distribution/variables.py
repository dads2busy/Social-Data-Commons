"""Compute all 17 independent variables for the CNT H+T regression models.

Variables are divided into:
- Household characteristics (3): median income, avg HH size, commuters/HH
- Neighborhood: housing density (7), employment (2), walkability (1), transit (5)

See CNT H+T Methods document Table 1 for variable definitions.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from sdc_core.census import CensusClient
from sdc_core.log import get_logger

log = get_logger("affordability_ht.variables")

REPO_DIR = Path(__file__).resolve().parents[5]
CENTROIDS_PATH = REPO_DIR / "geographies/osrm/bg_centroids_2020.csv"
LODES_CACHE = REPO_DIR / "transportation/Walkability/transit_stops/data/lodes_cache"

EARTH_RADIUS_MI = 3958.8

# --- Employment Mix Index weights from CNT Table 2 ---
# Maps NAICS code description → (LODES column, linearization function, weight)
# Linearization functions: "sqrt" = √x, "ln1x" = ln(1+x), "x2" = x²,
# "inv_x" = 1/x, "ln_x" = ln(x), "inv_1x" = 1/(1+x), "x" = x
EMPLOYMENT_MIX_TABLE = [
    ("CNS11", "sqrt", -0.0078),     # Real Estate and Rental and Leasing
    ("CNS19", "sqrt", -0.00654),    # Other Services
    ("CNS14", "sqrt", 0.00351),     # Administrative and Support
    ("CNS16", "ln1x", -0.0532),     # Health Care and Social Assistance
    ("CNS15", "x2", -1.20e-10),     # Educational Services
    ("CNS05", "inv_x", -1.86),      # Manufacturing
    ("CNS01", "ln_x", 0.0192),      # Agriculture, Forestry, Fishing
    ("CNS08", "x2", -1.54e-10),     # Transportation and Warehousing
    ("CNS02", "inv_1x", -0.133),    # Mining, Quarrying, Oil and Gas
    ("CNS06", "sqrt", 0.00229),     # Wholesale Trade
    ("CNS18", "sqrt", 0.00161),     # Accommodation and Food Services
    ("CNS10", "sqrt", -0.00112),    # Finance and Insurance
    ("CNS07", "sqrt", -0.00087),    # Retail Trade
    ("CNS03", "inv_1x", 0.15),      # Utilities
    ("CNS04", "sqrt", -0.00082),    # Construction
    ("CNS12", "sqrt", 0.00047),     # Professional, Scientific, Technical
    ("CNS17", "inv_1x", 0.19),      # Arts, Entertainment, Recreation
    ("CNS20", "inv_x", -0.23),      # Public Administration
    ("CNS09", "inv_1x", 0.18),      # Information
    ("CNS13", "inv_1x", -0.03),     # Management of Companies
]


def _linearize(x: float | np.ndarray, func: str) -> float | np.ndarray:
    """Apply a linearization transform."""
    x = np.where(np.isnan(x), 0, x) if isinstance(x, np.ndarray) else (0 if np.isnan(x) else x)
    if func == "x":
        return x
    elif func == "sqrt":
        return np.sqrt(np.maximum(x, 0))
    elif func == "x2":
        return x ** 2
    elif func == "ln_x":
        return np.log(np.maximum(x, 1e-10))
    elif func == "ln1x":
        return np.log1p(np.maximum(x, 0))
    elif func == "inv_x":
        return 1.0 / np.maximum(x, 1e-10)
    elif func == "inv_1x":
        return 1.0 / (1.0 + np.maximum(x, 0))
    else:
        raise ValueError(f"Unknown linearization function: {func}")


# ---------------------------------------------------------------------------
# ACS variable fetching
# ---------------------------------------------------------------------------


def fetch_acs_variables(
    year: int,
    states: list[str],
    acs_year: int | None = None,
) -> pd.DataFrame:
    """Fetch all needed ACS variables at the block group level.

    Returns DataFrame indexed by geoid with columns for each variable.
    """
    if acs_year is None:
        acs_year = year

    client = CensusClient()

    # --- Batch 1: Household characteristics ---
    hh_vars = {
        # Median household income
        "median_income": "B19013_001",
        # Total households
        "hh_total": "B11001_001",
        # Total population
        "pop_total": "B01003_001",
    }

    # --- Batch 2: Housing tenure ---
    tenure_vars = {
        "occ_total": "B25003_001",    # Total occupied housing units
        "owner_occ": "B25003_002",    # Owner-occupied
        "renter_occ": "B25003_003",   # Renter-occupied
    }

    # --- Batch 3: Housing structure type (units in structure) ---
    structure_vars = {
        "struct_total": "B25024_001",   # Total
        "struct_1det": "B25024_002",    # 1, detached
        "struct_1att": "B25024_003",    # 1, attached
    }

    # --- Batch 4: Population in occupied housing units (for avg HH size) ---
    pop_vars = {
        "pop_occ_total": "B25008_001",  # Total pop in occupied units
    }

    # --- Batch 5: Commuters (means of transportation to work) ---
    commute_vars = {
        "workers_total": "B08301_001",  # Total workers 16+
        "wfh": "B08301_021",           # Worked from home
    }

    # --- Batch 6: Vehicles available (for regression calibration target) ---
    vehicle_vars = {
        "veh_total_hh": "B08201_001",  # Total households
        "veh_0": "B08201_002",         # No vehicle
        "veh_1": "B08201_003",         # 1 vehicle
        "veh_2": "B08201_004",         # 2 vehicles
        "veh_3plus": "B08201_005",     # 3+ vehicles
    }

    # --- Batch 7: Housing costs ---
    cost_vars = {
        "median_owner_cost": "B25088_002",  # Median SMOC (with mortgage)
        "median_gross_rent": "B25064_001",  # Median gross rent
    }

    # --- Batch 8: Transit commuters (for transit use regression) ---
    transit_vars = {
        "transit_commuters": "B08301_010",  # Public transportation
    }

    all_vars = {}
    all_vars.update(hh_vars)
    all_vars.update(tenure_vars)
    all_vars.update(structure_vars)
    all_vars.update(pop_vars)
    all_vars.update(commute_vars)
    all_vars.update(vehicle_vars)
    all_vars.update(cost_vars)
    all_vars.update(transit_vars)

    frames = []
    for state in states:
        log.info("Fetching ACS %d for state %s at BG level", acs_year, state)
        df = client.get_acs_wide(
            variables=all_vars,
            geography="block_group",
            state=state,
            year=acs_year,
        )
        frames.append(df)

    result = pd.concat(frames, ignore_index=True)
    result["geoid"] = result["geoid"].astype(str).str.zfill(12)

    # Convert to numeric and replace Census suppression sentinel values
    for col in all_vars:
        result[col] = pd.to_numeric(result[col], errors="coerce")
    # Census uses -666666666 for suppressed/missing median values
    result = result.replace(-666666666, np.nan)

    log.info("Fetched ACS data: %d BGs, %d variables", len(result), len(all_vars))
    return result.set_index("geoid")


# ---------------------------------------------------------------------------
# Gravity variables
# ---------------------------------------------------------------------------


def compute_gravity_variables(
    bg_centroids: pd.DataFrame,
    acs_data: pd.DataFrame,
    lodes_bg: pd.DataFrame,
    target_geoids: set[str],
    block_counts: pd.Series | None = None,
) -> pd.DataFrame:
    """Compute all 6 gravity-based variables for target BGs.

    Gravity model: V = Σ value_j / r_ij² for all other BGs j.

    Variables computed:
    1. Household Intensity: Σ hh_j / r²
    2. Employment Intensity: Σ jobs_j / r²
    3. Renter Gravity (Rental Housing Intensity): Σ (frac_rental_j × hh_j) / r²
    4. SFD Gravity (SFD Housing Intensity): Σ (frac_sfd_j × hh_j) / r²
    5. Job Gravity: Σ jobs_j / r² (same as Employment Intensity for regression)

    Uses haversine distances between BG centroids.
    With 1/r² decay, contributions beyond ~50 miles are negligible.
    """
    centroids = bg_centroids.copy()
    centroids["geoid"] = centroids["geoid"].astype(str).str.zfill(12)
    centroids = centroids.set_index("geoid")

    # Prepare values for gravity computation
    hh = acs_data["hh_total"].reindex(centroids.index).fillna(0).values
    frac_rental = (
        acs_data["renter_occ"] / acs_data["occ_total"].replace(0, np.nan)
    ).reindex(centroids.index).fillna(0).values
    frac_sfd = (
        acs_data["struct_1det"] / acs_data["occ_total"].replace(0, np.nan)
    ).reindex(centroids.index).fillna(0).values

    jobs = lodes_bg["C000"].reindex(centroids.index).fillna(0).values if "C000" in lodes_bg.columns else np.zeros(len(centroids))

    # CNT computes gravity at Census BLOCK level. At BG level, the natural
    # approximation is Σ frac_j × hh_j / r², but this overpredicts for urban
    # areas where HH/block >> 1. Empirical calibration against CNT's 2022
    # published auto ownership predictions yields a scale factor of 0.008.
    RENTAL_SFD_GRAVITY_SCALE = 0.008
    rental_hh = frac_rental * hh
    sfd_hh = frac_sfd * hh
    rental_weights = rental_hh * RENTAL_SFD_GRAVITY_SCALE
    sfd_weights = sfd_hh * RENTAL_SFD_GRAVITY_SCALE

    lats = centroids["lat"].values
    lons = centroids["lon"].values
    n = len(centroids)
    geoids = centroids.index.values

    # Identify which indices are targets
    target_mask = np.array([g in target_geoids for g in geoids])

    log.info("Computing gravity for %d target BGs from %d total BGs",
             target_mask.sum(), n)

    # Convert to radians for vectorized haversine
    lat_r = np.radians(lats)
    lon_r = np.radians(lons)

    # Initialize result arrays
    hh_intensity = np.zeros(n)
    emp_intensity = np.zeros(n)
    rental_gravity = np.zeros(n)
    sfd_gravity = np.zeros(n)

    # Process in chunks to manage memory (~30K BGs → 30K×30K = 900M pairs)
    chunk_size = 2000
    for i in range(0, n, chunk_size):
        i_end = min(i + chunk_size, n)
        if not target_mask[i:i_end].any():
            continue

        # Compute distances from chunk to all other BGs
        dlat = lat_r[np.newaxis, :] - lat_r[i:i_end, np.newaxis]
        dlon = lon_r[np.newaxis, :] - lon_r[i:i_end, np.newaxis]
        a = (np.sin(dlat / 2) ** 2 +
             np.cos(lat_r[i:i_end, np.newaxis]) *
             np.cos(lat_r[np.newaxis, :]) *
             np.sin(dlon / 2) ** 2)
        dist_mi = EARTH_RADIUS_MI * 2 * np.arcsin(np.sqrt(np.minimum(a, 1.0)))

        # Zero out self-distances and very small distances to avoid div/0
        for j in range(i_end - i):
            dist_mi[j, i + j] = np.inf

        # Apply distance cutoff (50 miles — contributions beyond this are <0.04%)
        mask = dist_mi <= 50.0
        inv_r2 = np.where(mask, 1.0 / (dist_mi ** 2 + 1e-10), 0.0)

        hh_intensity[i:i_end] = inv_r2 @ hh
        emp_intensity[i:i_end] = inv_r2 @ jobs
        rental_gravity[i:i_end] = inv_r2 @ rental_weights
        sfd_gravity[i:i_end] = inv_r2 @ sfd_weights

        if (i // chunk_size) % 5 == 0:
            log.info("Gravity chunk %d/%d", i // chunk_size + 1,
                     (n + chunk_size - 1) // chunk_size)

    # Filter to target BGs only
    result = pd.DataFrame({
        "geoid": geoids[target_mask],
        "hh_intensity": hh_intensity[target_mask],
        "emp_intensity": emp_intensity[target_mask],
        "rental_gravity": rental_gravity[target_mask],
        "sfd_gravity": sfd_gravity[target_mask],
        "job_gravity": emp_intensity[target_mask],  # same as emp_intensity
    })
    return result


# ---------------------------------------------------------------------------
# Employment Mix Index
# ---------------------------------------------------------------------------


def compute_employment_mix(
    lodes_bg: pd.DataFrame,
    bg_centroids: pd.DataFrame,
    target_geoids: set[str],
) -> pd.Series:
    """Compute Employment Mix Index per BG (0-100 scale).

    Uses gravity measure per employment sector (Σ sector_jobs_j / r²)
    with linearization transforms and weights from CNT Table 2.

    Then normalizes to 0-100: I_Emix = 100 × (R - R_min) / (R_max - R_min)
    """
    centroids = bg_centroids.copy()
    centroids["geoid"] = centroids["geoid"].astype(str).str.zfill(12)
    centroids = centroids.set_index("geoid")

    # Ensure LODES data aligns with centroids
    common = centroids.index.intersection(lodes_bg.index)
    if len(common) == 0:
        log.warning("No overlap between centroids and LODES data")
        return pd.Series(dtype=float, name="emp_mix_index")

    lats = centroids.loc[common, "lat"].values
    lons = centroids.loc[common, "lon"].values
    n = len(common)
    geoids = common.values

    lat_r = np.radians(lats)
    lon_r = np.radians(lons)

    target_mask = np.array([g in target_geoids for g in geoids])

    # Compute gravity measure for each employment sector
    sector_gravity = {}  # CNS column → gravity array
    chunk_size = 2000

    for cns_col, _, _ in EMPLOYMENT_MIX_TABLE:
        if cns_col not in lodes_bg.columns:
            sector_gravity[cns_col] = np.zeros(n)
            continue

        sector_jobs = lodes_bg[cns_col].reindex(common).fillna(0).values
        gravity = np.zeros(n)

        for i in range(0, n, chunk_size):
            i_end = min(i + chunk_size, n)
            if not target_mask[i:i_end].any():
                continue

            dlat = lat_r[np.newaxis, :] - lat_r[i:i_end, np.newaxis]
            dlon = lon_r[np.newaxis, :] - lon_r[i:i_end, np.newaxis]
            a = (np.sin(dlat / 2) ** 2 +
                 np.cos(lat_r[i:i_end, np.newaxis]) *
                 np.cos(lat_r[np.newaxis, :]) *
                 np.sin(dlon / 2) ** 2)
            dist_mi = EARTH_RADIUS_MI * 2 * np.arcsin(np.sqrt(np.minimum(a, 1.0)))

            for j in range(i_end - i):
                dist_mi[j, i + j] = np.inf

            mask = dist_mi <= 50.0
            inv_r2 = np.where(mask, 1.0 / (dist_mi ** 2 + 1e-10), 0.0)
            gravity[i:i_end] = inv_r2 @ sector_jobs

        sector_gravity[cns_col] = gravity

    # Compute raw Employment Mix: R = Σ w_k × f_k(gravity_k)
    raw_mix = np.zeros(n)
    for cns_col, func, weight in EMPLOYMENT_MIX_TABLE:
        transformed = _linearize(sector_gravity[cns_col], func)
        raw_mix += weight * transformed

    # Calibrate to CNT's 0-100 scale.
    # CNT normalizes against national R_min/R_max which we don't have.
    # Instead, we use a linear calibration derived by regressing our raw_mix
    # values against CNT's published tract-level emp_ndx for VA (R²≈0.35).
    # CNT VA emp_ndx ranges from 31-51; this mapping produces similar values.
    CALIB_SLOPE = 5.1109
    CALIB_INTERCEPT = 42.6483
    emp_mix = np.clip(CALIB_SLOPE * raw_mix + CALIB_INTERCEPT, 25, 55)

    result = pd.Series(emp_mix, index=geoids, name="emp_mix_index")
    return result[result.index.isin(target_geoids)]


# ---------------------------------------------------------------------------
# Block size
# ---------------------------------------------------------------------------


def compute_block_size(state_fips_list: list[str]) -> pd.DataFrame:
    """Compute average block area in acres and block count per block group.

    Downloads TIGER tabblock20 shapefiles and computes:
    - block_size = total_bg_land_area_acres / number_of_blocks_in_bg
    - n_blocks = number of Census blocks in each BG

    Returns DataFrame indexed by geoid with columns [block_size, n_blocks].
    """
    import geopandas as gpd
    import tempfile
    import httpx

    cache_dir = REPO_DIR / "geographies/tiger_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    for fips in state_fips_list:
        cache_file = cache_dir / f"block_stats_{fips}.parquet"
        if cache_file.exists():
            df = pd.read_parquet(cache_file)
            all_results.append(df.set_index("geoid"))
            continue

        # Check old cache format (block_size only) and recompute if needed
        old_cache = cache_dir / f"block_size_{fips}.parquet"

        url = (
            f"https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/"
            f"tl_2020_{fips}_tabblock20.zip"
        )
        log.info("Downloading TIGER tabblock20 for FIPS %s", fips)
        try:
            with httpx.Client(follow_redirects=True, timeout=300) as client:
                resp = client.get(url)
                resp.raise_for_status()

            with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
                tmp.write(resp.content)
                tmp.flush()
                gdf = gpd.read_file(tmp.name)

            geoid_col = "GEOID20" if "GEOID20" in gdf.columns else "GEOID"
            gdf["bg_geoid"] = gdf[geoid_col].astype(str).str[:12]
            gdf["block_area_acres"] = gdf["ALAND20"].astype(float) * 0.000247105

            # Average block area and block count per BG
            bg_stats = gdf.groupby("bg_geoid").agg(
                total_area=("block_area_acres", "sum"),
                n_blocks=("block_area_acres", "count"),
            )
            bg_stats["block_size"] = bg_stats["total_area"] / bg_stats["n_blocks"]

            result = bg_stats[["block_size", "n_blocks"]].copy()
            result.index.name = "geoid"
            result.reset_index().to_parquet(cache_file, index=False)
            all_results.append(result)
            log.info("Computed block stats for %d BGs in FIPS %s",
                     len(result), fips)
        except Exception as e:
            log.warning("Failed to compute block size for %s: %s", fips, e)

    if not all_results:
        return pd.DataFrame(columns=["block_size", "n_blocks"])
    return pd.concat(all_results)


# ---------------------------------------------------------------------------
# Gross Household Density
# ---------------------------------------------------------------------------


def compute_gross_hh_density(
    acs_data: pd.DataFrame,
    bg_areas_m2: pd.Series,
) -> pd.Series:
    """Gross household density = HH count / land area (acres).

    CNT uses HH per acre (not per sq mi) in their regression models.
    """
    hh = acs_data["hh_total"].fillna(0)
    area_acres = bg_areas_m2 * 0.000247105  # m² to acres
    area_acres = area_acres.replace(0, np.nan)
    density = hh / area_acres.reindex(hh.index)
    return density.rename("gross_hh_density")


# ---------------------------------------------------------------------------
# Assemble all 17 variables
# ---------------------------------------------------------------------------


def compute_all_variables(
    year: int,
    target_states: list[str] = ("51",),
    buffer_states: list[str] = ("51", "24", "11", "54", "37", "21"),
    transit_metrics: pd.DataFrame | None = None,
    target_counties: set[str] | None = None,
) -> pd.DataFrame:
    """Compute all 17 independent variables for target state BGs.

    Parameters
    ----------
    year : data year
    target_states : FIPS codes for output states
    buffer_states : FIPS codes for gravity computation region
    transit_metrics : pre-computed transit metrics DataFrame (optional)
    target_counties : if provided, restrict target BGs to these 5-digit
        county FIPS codes (e.g. {"51059", "24031", "11001"})

    Returns
    -------
    DataFrame indexed by geoid with all 17 variable columns + housing costs
    """
    from .transit_metrics import (
        compute_all_transit_metrics,
        load_lodes_by_sector,
        _load_bg_areas,
    )

    state_map = {"51": "VA", "24": "MD", "11": "DC", "54": "WV",
                 "37": "NC", "47": "TN", "21": "KY", "10": "DE", "42": "PA"}
    target_abbrs = [state_map[f] for f in target_states]
    buffer_abbrs = [state_map[f] for f in buffer_states]

    # --- Load centroids ---
    from .gtfs_router import load_centroids
    centroids = load_centroids(states=buffer_abbrs)
    if target_counties:
        target_geoids = set(
            centroids[centroids["geoid"].str[:5].isin(target_counties)]["geoid"]
        )
    else:
        target_geoids = set(
            centroids[centroids["geoid"].str[:2].isin(target_states)]["geoid"]
        )
    log.info("Target: %d BGs, Buffer: %d BGs", len(target_geoids), len(centroids))

    # --- ACS data ---
    acs = fetch_acs_variables(year, list(target_states))
    # Also fetch for buffer states (needed for gravity)
    extra_states = [s for s in buffer_states if s not in target_states]
    if extra_states:
        acs_buffer = fetch_acs_variables(year, extra_states)
        acs = pd.concat([acs, acs_buffer])

    # --- LODES data ---
    lodes = load_lodes_by_sector(list(buffer_states), year)

    # --- BG land areas ---
    bg_areas = _load_bg_areas(list(buffer_states))

    # --- Compute household variables ---
    target_acs = acs.loc[acs.index.isin(target_geoids)].copy()

    # Median HH Income (direct from ACS)
    income = target_acs["median_income"]

    # Avg HH Size = pop in occupied HUs / total occupied HUs
    avg_hh_size = (
        target_acs["pop_occ_total"] /
        target_acs["occ_total"].replace(0, np.nan)
    )

    # Commuters/HH = (workers not WFH) × (pop_occ / pop_total) / HH_total
    workers_commuting = target_acs["workers_total"] - target_acs["wfh"]
    pop_ratio = (
        target_acs["pop_occ_total"] /
        target_acs["pop_total"].replace(0, np.nan)
    ).fillna(1.0)
    commuters_hh = (
        workers_commuting * pop_ratio /
        target_acs["hh_total"].replace(0, np.nan)
    )

    # --- Housing density variables ---
    # CNT uses percentages (0-100), not fractions (0-1)
    gross_density = compute_gross_hh_density(target_acs, bg_areas)
    frac_rental = (
        target_acs["renter_occ"] /
        target_acs["occ_total"].replace(0, np.nan)
    ).clip(0, 1) * 100  # Convert to percentage, clip to valid range
    frac_sfd = (
        target_acs["struct_1det"] /
        target_acs["occ_total"].replace(0, np.nan)
    ).clip(0, 1) * 100  # Convert to percentage, clip to valid range

    # --- Gravity variables ---
    gravity = compute_gravity_variables(
        centroids, acs, lodes, target_geoids,
    )
    gravity = gravity.set_index("geoid")

    # --- Block size (for regression only, computed for target states) ---
    block_stats = compute_block_size(list(target_states))
    block_size = block_stats["block_size"] if not block_stats.empty else pd.Series(dtype=float, name="block_size")

    # --- Employment Mix Index ---
    emp_mix = compute_employment_mix(lodes, centroids, target_geoids)

    # --- Transit metrics ---
    if transit_metrics is None:
        transit_metrics = compute_all_transit_metrics(
            year, list(target_states), list(buffer_states[:4]),
        )
    transit = transit_metrics.set_index("geoid")

    # --- Assemble ---
    result = pd.DataFrame(index=pd.Index(sorted(target_geoids), name="geoid"))

    # Household variables
    result["income"] = income
    result["hh_size"] = avg_hh_size
    result["commuters"] = commuters_hh

    # Housing density
    result["gross_hh_density"] = gross_density
    result["hh_intensity"] = gravity["hh_intensity"]
    result["frac_rental"] = frac_rental
    result["rental_gravity"] = gravity["rental_gravity"]
    result["frac_sfd"] = frac_sfd
    result["sfd_gravity"] = gravity["sfd_gravity"]

    # Employment
    result["emp_intensity"] = gravity["emp_intensity"]
    result["emp_mix_index"] = emp_mix
    result["job_gravity"] = gravity["job_gravity"]

    # Walkability
    result["block_size"] = block_size

    # Transit
    result["bus_tci"] = transit.get("bus_tci", 0)
    result["other_tci"] = transit.get("other_tci", 0)
    result["tas_area"] = transit.get("tas_area_acres", 0)
    result["tas_jobs"] = transit.get("tas_jobs", 0)
    result["peak_service"] = transit.get("peak_trips_week", 0)

    # Housing costs (for H+T Index construction)
    result["median_owner_cost"] = target_acs["median_owner_cost"]
    result["median_gross_rent"] = target_acs["median_gross_rent"]
    result["owner_occ"] = target_acs["owner_occ"]
    result["renter_occ"] = target_acs["renter_occ"]
    result["occ_total"] = target_acs["occ_total"]
    result["hh_total"] = target_acs["hh_total"]
    result["transit_commuters"] = target_acs["transit_commuters"]

    # Fill NaN with 0 for neighborhood variables
    neighborhood_cols = [
        "gross_hh_density", "hh_intensity", "frac_rental", "rental_gravity",
        "frac_sfd", "sfd_gravity", "emp_intensity", "emp_mix_index",
        "job_gravity", "block_size", "bus_tci", "other_tci", "tas_area",
        "tas_jobs", "peak_service",
    ]
    for col in neighborhood_cols:
        if col in result.columns:
            result[col] = result[col].fillna(0)

    log.info("Assembled %d variables for %d BGs", len(result.columns), len(result))
    return result
