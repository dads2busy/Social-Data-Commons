"""Ingest daycare accessibility measures for Virginia.

Uses VDSS daycare locations, ACS child population at block-group level,
and pre-computed BG-to-BG travel times to compute:
  - daycare_min_drivetime: minutes to nearest daycare
  - daycare_capacity: total seats within the block group
  - daycare_ratio: 3SFCA seats per 1k children under 15
  - daycare_ratio_over_4: 3SFCA seats per 1k children 5-14
  - daycare_ratio_under_10: 3SFCA seats per 1k children under 10
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sdc_core.catchment import catchment_ratio
from sdc_core.census import CensusClient
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
TRAVEL_TIMES_DIR = REPO_DIR / "geographies/osrm/travel_times"
CENTROIDS_PATH = REPO_DIR / "geographies/osrm/bg_centroids_2020.csv"

# States with pre-computed BG travel time parquets
TRAVEL_TIME_FIPS = ["10", "21", "24", "37", "47", "51", "54"]

# ACS B01001 (Sex by Age) variables for child population
POP_VARIABLES = {
    "male_under_5": "B01001_003",
    "female_under_5": "B01001_027",
    "male_5_9": "B01001_004",
    "female_5_9": "B01001_028",
    "male_10_14": "B01001_005",
    "female_10_14": "B01001_029",
}

GAUSSIAN_SCALE = 18  # Gaussian decay scale parameter (minutes)

log = get_logger("daycare.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Step 1: Load and geocode daycare locations to block groups
# ---------------------------------------------------------------------------

def _haversine_km(lat1: np.ndarray, lon1: np.ndarray, lat2: float, lon2: float) -> np.ndarray:
    """Vectorized haversine distance in km."""
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def load_locations(year: int) -> pd.DataFrame:
    """Load daycare locations for a given year and assign each to nearest block group."""
    loc_path = TOPIC_DIR / f"data/working/locations_{year}.csv"
    if not loc_path.exists():
        raise FileNotFoundError(f"No locations file for {year}: {loc_path}")
    locs = pd.read_csv(loc_path)
    locs = locs[locs["lat"].notna() & locs["long"].notna()].copy()

    # Fill defaults (matching R code)
    locs["capacity"] = locs["capacity"].fillna(4).astype(int)
    locs["age_min"] = locs["age_min"].fillna(0).astype(int)
    locs["age_max"] = locs["age_max"].fillna(12).astype(int)

    # Create unique location ID if missing
    if "lid" not in locs.columns:
        locs["lid"] = (
            locs["long"].round(6).astype(str) + locs["lat"].round(6).astype(str)
        ).apply(lambda x: hash(x))

    # Assign to nearest BG centroid
    centroids = pd.read_csv(CENTROIDS_PATH, dtype={"geoid": str})
    bg_lats = centroids["lat"].values
    bg_lons = centroids["lon"].values
    bg_geoids = centroids["geoid"].values

    assigned_bgs = []
    for _, row in locs.iterrows():
        dists = _haversine_km(bg_lats, bg_lons, row["lat"], row["long"])
        assigned_bgs.append(bg_geoids[np.argmin(dists)])
    locs["bg_geoid"] = assigned_bgs

    log.info(
        "Loaded %d daycare locations assigned to %d unique block groups",
        len(locs), locs["bg_geoid"].nunique(),
    )
    return locs[["lid", "lat", "long", "capacity", "age_min", "age_max", "bg_geoid"]]


# ---------------------------------------------------------------------------
# Step 2: Load child population
# ---------------------------------------------------------------------------

def load_population(year: int, states: list[str]) -> pd.DataFrame:
    """Fetch block-group child population from ACS."""
    client = CensusClient()
    cache_dir = TOPIC_DIR / "data/working/acs_cache"

    df = client.get_acs_multi(
        variables=POP_VARIABLES,
        years=[year],
        geographies=["block_group"],
        states=states,
        cache_dir=cache_dir,
    )
    log.info("Fetched %d block group rows for population", len(df))

    df["pop_under_15"] = (
        df["male_under_5"] + df["female_under_5"]
        + df["male_5_9"] + df["female_5_9"]
        + df["male_10_14"] + df["female_10_14"]
    )
    df["pop_5_14"] = df["male_5_9"] + df["female_5_9"] + df["male_10_14"] + df["female_10_14"]
    df["pop_under_10"] = df["male_under_5"] + df["female_under_5"] + df["male_5_9"] + df["female_5_9"]

    return df[["geoid", "pop_under_15", "pop_5_14", "pop_under_10"]]


# ---------------------------------------------------------------------------
# Step 3: Load travel times
# ---------------------------------------------------------------------------

def load_travel_times() -> pd.DataFrame:
    """Load all available BG-to-BG travel time parquets."""
    frames = []
    for fips in TRAVEL_TIME_FIPS:
        path = TRAVEL_TIMES_DIR / f"bg2bg_{fips}.parquet"
        if path.exists():
            df = pd.read_parquet(path, columns=["bg_orig", "bg_dest", "time_mins"])
            frames.append(df)
            log.info("Loaded %d travel time rows from %s", len(df), path.name)
    if not frames:
        raise RuntimeError("No travel time parquet files found")
    tt = pd.concat(frames, ignore_index=True)
    # Deduplicate (same pair may appear in multiple state files)
    tt = tt.drop_duplicates(subset=["bg_orig", "bg_dest"]).reset_index(drop=True)
    log.info("Total travel time pairs: %d", len(tt))
    return tt


# ---------------------------------------------------------------------------
# Step 4 & 5: Compute measures
# ---------------------------------------------------------------------------

def compute_min_drivetime(
    pop_geoids: np.ndarray,
    provider_bgs: set[str],
    travel_times: pd.DataFrame,
) -> pd.Series:
    """Min drive time from each consumer BG to any provider BG."""
    # Filter travel times to only those ending at a provider BG
    tt_to_providers = travel_times[travel_times["bg_dest"].isin(provider_bgs)]

    # Also add self-pairs for BGs that contain providers
    consumer_set = set(pop_geoids)
    self_provider = provider_bgs & consumer_set
    if self_provider:
        self_df = pd.DataFrame({
            "bg_orig": list(self_provider),
            "bg_dest": list(self_provider),
            "time_mins": 0.0,
        })
        tt_to_providers = pd.concat([tt_to_providers, self_df], ignore_index=True)

    min_times = tt_to_providers.groupby("bg_orig")["time_mins"].min()
    result = pd.Series(np.nan, index=pop_geoids)
    matched = result.index.isin(min_times.index)
    result.loc[matched] = min_times.reindex(result.index[matched]).values
    return result


def compute_capacity(pop_geoids: np.ndarray, locations: pd.DataFrame) -> pd.Series:
    """Total daycare capacity within each block group."""
    cap_by_bg = locations.groupby("bg_geoid")["capacity"].sum()
    result = pd.Series(0, index=pop_geoids, dtype=int)
    matched = result.index.isin(cap_by_bg.index)
    result.loc[matched] = cap_by_bg.reindex(result.index[matched]).values
    return result


def compute_3sfca(
    pop: pd.DataFrame,
    locations: pd.DataFrame,
    travel_times: pd.DataFrame,
    pop_col: str,
    age_filter_mask: pd.Series,
) -> pd.Series:
    """Compute 3-step floating catchment area ratio via sdc_core.catchment.

    Uses ``catchment_ratio`` with Gaussian kernel and quadratic selection-weight
    normalization (``normalize_weight=True``).  The inline code previously used
    simple row normalization (w / row_sum); the module uses quadratic
    normalization (w * w / row_sum).  This is an intentional methodological
    upgrade to the 3SFCA formulation from Wan, Zou & Sternberg (2012).

    The Gaussian scale is passed as ``GAUSSIAN_SCALE / sqrt(2)`` so that the
    module kernel ``exp(-t^2 / (2*s^2))`` produces the same weights as the
    former inline kernel ``exp(-(t/GAUSSIAN_SCALE)^2)``.

    Returns seats per 1,000 children for each consumer block group.
    """
    # Filter providers by age range
    filtered_locs = locations[age_filter_mask].copy()
    consumer_geoids = pop["geoid"].values
    if filtered_locs.empty:
        return pd.Series(0.0, index=consumer_geoids)

    # Aggregate providers by lid (same location hash = same physical location)
    prov_info = (
        filtered_locs.groupby("lid")
        .agg({"bg_geoid": "first", "capacity": "sum"})
        .reset_index()
    )
    provider_bgs = prov_info["bg_geoid"].values
    provider_lids = prov_info["lid"].values

    # --- Build cost matrix (consumers × providers) from travel_times ---
    # Create lookup: (bg_orig, bg_dest) -> time_mins for relevant pairs
    provider_bg_set = set(prov_info["bg_geoid"].unique())
    tt_relevant = travel_times[travel_times["bg_dest"].isin(provider_bg_set)]

    # Build a dict for fast lookup: bg_dest -> {bg_orig: time_mins}
    # Then map provider lids through their bg_geoid
    tt_dict: dict[tuple[str, str], float] = {}
    for orig, dest, t in zip(
        tt_relevant["bg_orig"].values,
        tt_relevant["bg_dest"].values,
        tt_relevant["time_mins"].values,
    ):
        key = (orig, dest)
        if key not in tt_dict or t < tt_dict[key]:
            tt_dict[key] = t

    # Build dense cost matrix: rows = consumer BGs, cols = provider lids
    n_consumers = len(consumer_geoids)
    n_providers = len(provider_lids)
    # Use a large default cost so that unreachable pairs get zero weight
    cost_matrix = np.full((n_consumers, n_providers), 1e6, dtype=float)

    consumer_idx = {g: i for i, g in enumerate(consumer_geoids)}
    for j, (lid, bg) in enumerate(zip(provider_lids, provider_bgs)):
        for orig, i in consumer_idx.items():
            if orig == bg:
                # Self-pair: zero travel time
                cost_matrix[i, j] = 0.0
            else:
                t = tt_dict.get((orig, bg))
                if t is not None:
                    cost_matrix[i, j] = t

    # Build consumer and provider DataFrames for catchment_ratio
    consumers_df = pd.DataFrame({
        "geoid": consumer_geoids,
        "value": pop[pop_col].values.astype(float),
    })
    providers_df = pd.DataFrame({
        "lid": provider_lids,
        "value": prov_info["capacity"].values.astype(float),
    })

    # Call catchment_ratio with 3SFCA (normalize_weight=True)
    # Scale equivalence: inline exp(-(t/18)^2) == module exp(-t^2/(2*s^2)) when s=18/sqrt(2)
    access = catchment_ratio(
        consumers=consumers_df,
        providers=providers_df,
        cost=cost_matrix,
        weight="gaussian",
        scale=GAUSSIAN_SCALE / np.sqrt(2),
        normalize_weight=True,
        consumers_id="geoid",
        consumers_value="value",
        providers_id="lid",
        providers_value="value",
        return_type=1000,
    )

    # Map back to full consumer list (catchment_ratio returns Series indexed by geoid)
    result = pd.Series(0.0, index=consumer_geoids)
    matched = result.index.isin(access.index)
    result.loc[matched] = access.reindex(result.index[matched]).values
    return result


# ---------------------------------------------------------------------------
# Step 6: Aggregate and output
# ---------------------------------------------------------------------------

def aggregate_bg_to_higher(
    bg_data: pd.DataFrame,
    crosswalk_path: Path,
    year: int,
) -> pd.DataFrame:
    """Aggregate block group measures to tract, county, health district."""
    bg = bg_data.copy()

    # Tract: first 11 digits of BG geoid
    bg["tract_geoid"] = bg["geoid"].str[:11]
    # County: first 5 digits
    bg["county_geoid"] = bg["geoid"].str[:5]

    # Load crosswalk for health districts
    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})
    county_to_hd = dict(zip(xwalk["ct_geoid"], xwalk["hd_geoid"]))
    bg["hd_geoid"] = bg["county_geoid"].map(county_to_hd)

    measures_config = {
        "daycare_min_drivetime": {"agg": "mean", "pop_weight": None},
        "daycare_capacity": {"agg": "sum", "pop_weight": None},
        "daycare_ratio": {"agg": "weighted_mean", "pop_weight": "pop_under_15"},
        "daycare_ratio_over_4": {"agg": "weighted_mean", "pop_weight": "pop_5_14"},
        "daycare_ratio_under_10": {"agg": "weighted_mean", "pop_weight": "pop_under_10"},
    }

    all_frames = []

    # BG level
    for measure in measures_config:
        frame = pd.DataFrame({
            "geoid": bg["geoid"],
            "year": year,
            "measure": measure,
            "value": bg[measure],
            "moe": pd.NA,
        })
        all_frames.append(frame)

    # Aggregate to each higher level
    for level, geoid_col in [("tract", "tract_geoid"), ("county", "county_geoid"), ("hd", "hd_geoid")]:
        valid = bg[bg[geoid_col].notna()]
        for measure, cfg in measures_config.items():
            if cfg["agg"] == "mean":
                agged = valid.groupby(geoid_col)[measure].mean().reset_index()
            elif cfg["agg"] == "sum":
                agged = valid.groupby(geoid_col)[measure].sum().reset_index()
            elif cfg["agg"] == "weighted_mean":
                pop_col = cfg["pop_weight"]
                grouped = valid.groupby(geoid_col).apply(
                    lambda g: np.average(g[measure], weights=g[pop_col]) if g[pop_col].sum() > 0 else 0.0,
                    include_groups=False,
                ).reset_index(name=measure)
                agged = grouped
            else:
                continue

            frame = pd.DataFrame({
                "geoid": agged[geoid_col] if geoid_col in agged.columns else agged.iloc[:, 0],
                "year": year,
                "measure": measure,
                "value": agged[measure],
                "moe": pd.NA,
            })
            all_frames.append(frame)

    result = pd.concat(all_frames, ignore_index=True)
    # Set region_type based on geoid format
    result["region_type"] = "block_group"
    result.loc[result["geoid"].str.len() == 11, "region_type"] = "tract"
    result.loc[result["geoid"].str.len() == 5, "region_type"] = "county"
    result.loc[result["geoid"].str.contains("_hd_", na=False), "region_type"] = "health_district"

    return result


def _compute_year(
    year: int,
    acs_year: int,
    states: list[str],
    travel_times: pd.DataFrame,
    crosswalk_path: Path,
) -> pd.DataFrame:
    """Compute all daycare measures for a single year."""
    log.info("=== Processing year %d (ACS %d) ===", year, acs_year)

    # Step 1: Load locations
    log.info("Loading daycare locations for %d...", year)
    locations = load_locations(year)

    # Step 2: Load population
    log.info("Loading child population from ACS %d...", acs_year)
    pop = load_population(acs_year, states)

    # Step 4-5: Compute measures
    log.info("Computing daycare_min_drivetime...")
    all_provider_bgs = set(locations["bg_geoid"].unique())
    pop["daycare_min_drivetime"] = compute_min_drivetime(
        pop["geoid"].values, all_provider_bgs, travel_times,
    ).values

    log.info("Computing daycare_capacity...")
    pop["daycare_capacity"] = compute_capacity(pop["geoid"].values, locations).values

    log.info("Computing daycare_ratio (under 15)...")
    mask_under_15 = (locations["age_min"] < 5) & (locations["age_max"] > 9)
    pop["daycare_ratio"] = compute_3sfca(
        pop, locations, travel_times, "pop_under_15", mask_under_15,
    ).values

    log.info("Computing daycare_ratio_over_4...")
    mask_over_4 = locations["age_min"] > 4
    pop["daycare_ratio_over_4"] = compute_3sfca(
        pop, locations, travel_times, "pop_5_14", mask_over_4,
    ).values

    log.info("Computing daycare_ratio_under_10...")
    mask_under_10 = locations["age_max"] < 10
    pop["daycare_ratio_under_10"] = compute_3sfca(
        pop, locations, travel_times, "pop_under_10", mask_under_10,
    ).values

    # Step 6: Filter to VA and aggregate
    log.info("Filtering to VA block groups and aggregating...")
    va_pop = pop[pop["geoid"].str.startswith("51")].copy()
    log.info("VA block groups for %d: %d", year, len(va_pop))

    return aggregate_bg_to_higher(va_pop, crosswalk_path, year)


def run() -> RunResult:
    t0 = time.time()
    config = load_config()
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    years = config["sources"]["va"]["years"]
    states = config["sources"]["va"]["states"]

    try:
        # Step 3: Load travel times (shared across years)
        log.info("Loading travel times...")
        travel_times = load_travel_times()

        crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
        acs_year_map = config["sources"]["va"].get("acs_year_map", {})

        # Process each year
        all_results = []
        for year in years:
            loc_path = TOPIC_DIR / f"data/working/locations_{year}.csv"
            if not loc_path.exists():
                log.warning("Skipping year %d: no locations file at %s", year, loc_path)
                continue
            acs_year = acs_year_map.get(year, year)
            result = _compute_year(year, acs_year, states, travel_times, crosswalk_path)
            all_results.append(result)

        if not all_results:
            raise RuntimeError("No years with location data found")

        combined = pd.concat(all_results, ignore_index=True)

        # Write output
        filename = build_file_name(
            coverage_area="va",
            geographies=["health_district", "county", "tract", "block_group"],
            data_source="vdss",
            years=years,
            title="daycare_access",
        )
        out_path = write_data(combined, DIST_DIR / filename, census_standardize=False)
        log.info("Wrote %d rows (%d years) to %s", len(combined), len(all_results), out_path)

        return RunResult(
            success=True,
            rows=len(combined),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
