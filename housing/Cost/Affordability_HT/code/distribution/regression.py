"""CNT H+T regression model with published coefficients.

Implements the three transportation regression models from the CNT H+T
Methods document (November 2022):
- Table 3: Linearization functions per variable per model
- Table 4: Auto Ownership regression (R²=78.76%)
- Table 5: Auto Use / VMT regression (R²=83.23%)
- Table 6: Transit Use regression (R²=77.25%)

Plus cost calculations and H+T Index construction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sdc_core.log import get_logger

log = get_logger("affordability_ht.regression")


# ---------------------------------------------------------------------------
# Linearization transforms (Table 3)
# ---------------------------------------------------------------------------
# Key for variable names used in regression tables:
#   income, commuters, hh_size, gross_hh_density (hh_density),
#   hh_intensity (hh_gravity), frac_rental (percent_rental),
#   rental_gravity (rental_intensity), frac_sfd (sfd_fraction),
#   sfd_gravity (sfd_intensity), emp_intensity, emp_mix_index (job_mix_index),
#   block_size, bus_tci, other_tci, tas_area, tas_jobs, peak_service

# "Safe" versions: ln(1+x) for ln(x), 1/(1+x) for 1/x (footnote 5)
def _x(x):
    return x

def _sqrt(x):
    return np.sqrt(np.maximum(x, 0))

def _x2(x):
    return x ** 2

def _ln1x(x):
    return np.log1p(np.maximum(x, 0))

def _inv_1x(x):
    return 1.0 / (1.0 + np.maximum(x, 0))

def _inv_x(x):
    """1/x with safe minimum."""
    return 1.0 / np.maximum(x, 1e-10)

def _ln_x(x):
    return np.log(np.maximum(x, 1e-10))

def _inv_1_plus_inv_x_6(x):
    """1/(1+1/x)^6 — used for block_size in VMT model."""
    safe_x = np.maximum(x, 1e-10)
    return 1.0 / (1.0 + 1.0 / safe_x) ** 6


# Table 3: Linearization functions per variable per model
# Format: variable_name → (auto_ownership_func, vmt_func, transit_use_func)
LINEARIZATION = {
    "income":           (_inv_1x, _inv_1x, _inv_x),
    "commuters":        (_x, _inv_1x, _sqrt),
    "hh_size":          (_inv_x, _inv_1x, _x),
    "hh_density":       (_x, _sqrt, _sqrt),
    "hh_intensity":     (_x2, _sqrt, _sqrt),
    "frac_rental":      (_x, _x, _x),
    "rental_gravity":   (_ln1x, _ln1x, _x),
    "frac_sfd":         (_sqrt, _sqrt, _inv_1x),
    "sfd_gravity":      (_x2, _ln1x, _x2),
    "emp_intensity":    (_x, _ln_x, _sqrt),
    "job_gravity":      (_x, _ln_x, _sqrt),   # same measure as emp_intensity
    "job_mix_index":    (_x2, _x2, _sqrt),
    "block_size":       (_ln1x, _inv_1_plus_inv_x_6, _ln1x),
    "bus_tci":          (_x, _sqrt, _sqrt),
    "other_tci":        (_x, _sqrt, _ln1x),
    "tas_area":         (_sqrt, _ln1x, _x),
    "tas_jobs":         (_x, _ln1x, _x),
    "peak_service":     (_sqrt, _sqrt, _ln1x),
}

# Map our DataFrame column names to regression variable names
COL_TO_VAR = {
    "income": "income",
    "commuters": "commuters",
    "hh_size": "hh_size",
    "gross_hh_density": "hh_density",
    "hh_intensity": "hh_intensity",
    "frac_rental": "frac_rental",
    "rental_gravity": "rental_gravity",
    "frac_sfd": "frac_sfd",
    "sfd_gravity": "sfd_gravity",
    "emp_intensity": "emp_intensity",
    "emp_mix_index": "job_mix_index",
    "job_gravity": "job_gravity",
    "block_size": "block_size",
    "bus_tci": "bus_tci",
    "other_tci": "other_tci",
    "tas_area": "tas_area",
    "tas_jobs": "tas_jobs",
    "peak_service": "peak_service",
}


# ---------------------------------------------------------------------------
# Regression coefficients from Tables 4-6
# ---------------------------------------------------------------------------
# Each model is a list of terms:
#   ("var1", None, coefficient)  — main effect
#   ("var1", "var2", coefficient) — interaction term

# Table 4: Auto Ownership Regression (R²=78.76%, log-transformed DV)
AUTO_OWNERSHIP_INTERCEPT = 1.10e-01
AUTO_OWNERSHIP_TERMS = [
    ("frac_rental", "rental_gravity", -2.12e-04),
    ("commuters", "frac_rental", 3.40e-04),
    ("tas_jobs", "peak_service", -3.18e-09),
    ("hh_size", "income", 1.01e+04),
    ("job_mix_index", None, 8.20e-05),
    ("frac_sfd", "rental_gravity", 2.39e-02),
    ("commuters", "block_size", -2.39e-02),
    ("hh_intensity", "frac_rental", -6.90e-14),
    ("frac_sfd", "income", 7.91e+02),
    ("job_gravity", "sfd_gravity", 1.74e-15),
    ("sfd_gravity", "peak_service", -3.80e-12),
    ("hh_size", "other_tci", -4.35e-05),
    ("income", "income", 7.88e+07),
    ("income", None, -2.14e+04),
    ("hh_size", "job_mix_index", -7.50e-05),
    ("block_size", "job_mix_index", 1.60e-05),
    ("commuters", "income", 5.06e+03),
    ("commuters", "hh_density", -2.59e-03),
    ("commuters", "rental_gravity", 1.12e-02),
    ("bus_tci", "job_mix_index", -6.00e-10),
    ("block_size", "block_size", -6.80e-03),
    ("block_size", "frac_rental", -3.80e-04),
    ("income", "tas_area", -2.00e+01),
    ("frac_rental", "tas_area", 1.03e-05),
    ("hh_intensity", "sfd_gravity", -1.35e-20),
    ("bus_tci", "hh_intensity", 1.85e-16),
    ("hh_size", "rental_gravity", -2.90e-02),
    ("job_mix_index", "tas_jobs", -3.80e-11),
    ("sfd_gravity", "tas_jobs", 3.40e-16),
    ("bus_tci", "frac_rental", -1.70e-07),
    ("peak_service", "peak_service", 3.00e-05),
    ("block_size", "tas_jobs", 4.40e-08),
    ("hh_density", "hh_density", 2.70e-06),
    ("commuters", "hh_size", 1.09e-01),
]

# Table 5: Auto Use / VMT Regression (R²=83.23%, log-transformed DV)
VMT_INTERCEPT = 1.01e+01
VMT_TERMS = [
    ("hh_size", "hh_intensity", -2.90e-03),
    ("income", "frac_rental", -7.10e+01),
    ("commuters", "commuters", 1.20e+00),
    ("hh_density", "frac_rental", -3.30e-04),
    ("bus_tci", "peak_service", -4.00e-04),
    ("job_mix_index", "sfd_gravity", 1.20e-05),
    ("commuters", "sfd_gravity", -9.00e-02),
    ("block_size", "bus_tci", -3.00e-03),       # Block Density × Bus TCI
    ("commuters", "bus_tci", 7.00e-03),
    ("block_size", "block_size", 1.00e+00),     # Block Density × Block Density
    ("commuters", "hh_size", -4.50e+00),
    ("block_size", "rental_gravity", -8.00e-02),  # Block Density × Renter Gravity
    ("frac_sfd", "hh_intensity", 5.00e-04),
    ("frac_sfd", "other_tci", -2.80e-03),
    ("other_tci", "other_tci", 3.50e-05),
    ("hh_density", "other_tci", -4.40e-04),
    ("other_tci", "frac_rental", -3.20e-05),
    ("hh_density", "hh_density", 7.00e-04),
    ("block_size", "other_tci", 2.80e-03),      # Block Density × Other TCI
    ("block_size", "job_gravity", -6.00e-02),    # Block Density × Job Gravity
    ("income", "sfd_gravity", -1.51e+03),
    ("hh_size", "income", 3.37e+04),
    ("income", "tas_jobs", 1.09e+03),
    ("income", "peak_service", -1.41e+03),
    ("job_mix_index", "tas_jobs", -6.00e-06),
    ("job_gravity", "tas_area", 3.70e-03),
    ("hh_size", "tas_area", 6.00e-02),
    ("job_mix_index", "hh_intensity", 2.20e-07),
    ("hh_intensity", "hh_intensity", -2.00e-06),
    ("commuters", "tas_jobs", -3.00e-02),
]

# Table 6: Transit Use Regression (R²=77.25%, quasibinomial DV)
TRANSIT_INTERCEPT = 8.00e-01
TRANSIT_TERMS = [
    ("job_mix_index", "hh_intensity", 1.79e-03),
    ("other_tci", "peak_service", -2.28e-02),
    ("peak_service", "peak_service", 3.65e-02),
    ("hh_intensity", "tas_area", -1.38e-07),
    ("job_mix_index", "job_mix_index", -8.90e-02),
    ("job_gravity", "peak_service", -8.10e-04),
    ("job_mix_index", "other_tci", 2.81e-02),
    ("other_tci", "tas_jobs", 4.10e-05),
    ("job_mix_index", "rental_gravity", -3.48e-06),
    ("job_mix_index", "income", 3.17e+03),
    ("commuters", "frac_sfd", 5.90e-01),
    ("hh_size", "tas_jobs", -1.65e-07),
    ("job_gravity", "rental_gravity", 2.43e-08),
    ("block_size", "sfd_gravity", -1.90e-10),
    ("commuters", "hh_intensity", 5.00e-04),
    ("job_mix_index", "tas_jobs", 1.32e-07),
    ("rental_gravity", "tas_area", 4.10e-10),
    ("rental_gravity", "tas_jobs", -5.00e-12),
    ("frac_rental", "peak_service", 1.74e-03),
    ("commuters", "frac_rental", 3.90e-03),
    ("income", "income", -1.43e+08),
    ("income", "other_tci", -1.64e+03),
    ("frac_rental", "sfd_gravity", -6.80e-12),
    ("sfd_gravity", "peak_service", 1.70e-10),
    ("job_gravity", "sfd_gravity", -3.70e-12),
    ("hh_density", "sfd_gravity", 9.40e-11),
    ("commuters", "income", -2.19e+04),
    ("frac_rental", None, -1.70e-02),
    ("job_gravity", "income", 4.00e+00),
    ("bus_tci", "peak_service", -8.50e-04),
    ("commuters", "bus_tci", 6.90e-03),
    ("income", "tas_area", 3.30e-01),
    ("income", "frac_rental", 2.22e+02),
]


# ---------------------------------------------------------------------------
# Model application
# ---------------------------------------------------------------------------


def _get_transform(var_name: str, model_idx: int):
    """Get the linearization function for a variable and model.

    model_idx: 0=auto_ownership, 1=vmt, 2=transit_use
    """
    if var_name in LINEARIZATION:
        return LINEARIZATION[var_name][model_idx]
    raise KeyError(f"No linearization function for variable '{var_name}'")


def _apply_model(
    df: pd.DataFrame,
    intercept: float,
    terms: list[tuple[str, str | None, float]],
    model_idx: int,
) -> np.ndarray:
    """Apply a regression model to compute the linearized dependent variable D.

    D = I + Σ Ci × fi(xi) + ΣΣ Cij × fi(xi) × fj(xj)
    """
    n = len(df)
    D = np.full(n, intercept)

    # Pre-compute transformed values
    transformed = {}
    for col, var_name in COL_TO_VAR.items():
        if col in df.columns:
            vals = df[col].values.astype(float)
            vals = np.nan_to_num(vals, nan=0.0)
            func = _get_transform(var_name, model_idx)
            transformed[var_name] = func(vals)

    for var1, var2, coeff in terms:
        if var1 not in transformed:
            continue
        t1 = transformed[var1]
        if var2 is None:
            D += coeff * t1
        else:
            if var2 not in transformed:
                continue
            t2 = transformed[var2]
            D += coeff * t1 * t2

    return D


def predict_auto_ownership(df: pd.DataFrame) -> np.ndarray:
    """Predict autos per household (log-transformed → exp)."""
    D = _apply_model(df, AUTO_OWNERSHIP_INTERCEPT, AUTO_OWNERSHIP_TERMS, 0)
    # Clip D to prevent overflow (exp(10) ≈ 22000, reasonable max)
    D = np.clip(D, -10, 3)  # exp(3) ≈ 20 autos, generous upper bound
    return np.exp(D)


def predict_vmt(df: pd.DataFrame) -> np.ndarray:
    """Predict annual VMT per household (log-transformed → exp).

    Includes empirical calibration offset of -0.341 in D space. CNT's
    published coefficients produce ~40% VMT overprediction when applied to
    BG-level variables (vs CNT's proprietary block-level computation).
    Calibrated against CNT's 2022 tract-level vmt_per_hh_ami for VA.
    """
    VMT_CALIBRATION_OFFSET = -0.341  # ln(0.711), median ratio vs CNT
    D = _apply_model(df, VMT_INTERCEPT, VMT_TERMS, 1)
    D += VMT_CALIBRATION_OFFSET
    # Clip D to prevent overflow (exp(12) ≈ 163000 miles, generous max)
    D = np.clip(D, 0, 12)
    vmt = np.exp(D)
    # Apply 8% adjustment for vehicle age (CNT methods, p.7)
    return vmt * 1.08


def predict_transit_use(df: pd.DataFrame) -> np.ndarray:
    """Predict fraction of commuters using transit (quasibinomial → logistic).

    Includes:
    - Calibration offset of -2.35 in logit space (CNT's block-level gravity
      computation yields different variable scales than our BG-level approach)
    - Zero override for BGs with no transit service (bus_tci=0, other_tci=0,
      peak_service=0) — matching CNT's treatment of non-transit areas
    """
    TRANSIT_CALIBRATION_OFFSET = -2.35
    D = _apply_model(df, TRANSIT_INTERCEPT, TRANSIT_TERMS, 2)
    D += TRANSIT_CALIBRATION_OFFSET
    # Clip to prevent overflow in logistic function
    D = np.clip(D, -20, 20)
    transit_frac = np.exp(D) / (1 + np.exp(D))

    # Zero out transit for BGs with no transit service
    no_transit = (
        (df.get("bus_tci", 0) == 0) &
        (df.get("other_tci", 0) == 0) &
        (df.get("peak_service", 0) == 0)
    )
    if hasattr(no_transit, "values"):
        no_transit = no_transit.values
    transit_frac = np.where(no_transit, 0.0, transit_frac)

    return transit_frac


# ---------------------------------------------------------------------------
# Cost calculation
# ---------------------------------------------------------------------------

# Auto ownership cost per vehicle per year (2022 dollars).
# Derived from CNT's 2022 H+T published costs: $11,698 median auto cost
# for 1.91 median autos = ~$6,125/vehicle. Includes insurance, depreciation,
# finance charges, maintenance (excludes fuel, which is in VMT cost).
AUTO_COST_PER_VEHICLE = 6125

# VMT cost per mile (2022 dollars).
# CNT 2022: $3,300 median VMT cost / 18,244 median VMT = $0.181/mile.
# Covers fuel and oil costs per mile driven.
VMT_COST_PER_MILE = 0.181

# Average transit fare per trip (2019 NTD national average)
TRANSIT_COST_PER_TRIP = 1.50
# Average annual transit trips per transit commuter
# (251 work days × 2 trips/day × 1.2 factor for non-work trips)
TRANSIT_TRIPS_PER_COMMUTER = 603


def compute_transportation_costs(
    df: pd.DataFrame,
    autos: np.ndarray,
    vmt: np.ndarray,
    transit_frac: np.ndarray,
) -> pd.DataFrame:
    """Compute annual transportation costs per household.

    Parameters
    ----------
    df : variables DataFrame (needs income, commuters, hh_total columns)
    autos : predicted autos per household
    vmt : predicted annual VMT per household
    transit_frac : predicted fraction of commuters using transit

    Returns
    -------
    DataFrame with auto_cost, vmt_cost, transit_cost, total_transport_cost
    """
    income = df["income"].values.astype(float)

    # Auto ownership cost
    auto_ownership_cost = autos * AUTO_COST_PER_VEHICLE

    # VMT cost
    vmt_cost = vmt * VMT_COST_PER_MILE

    # Transit cost
    commuters = df["commuters"].values.astype(float)
    hh_total = df["hh_total"].values.astype(float)
    transit_commuters_per_hh = np.nan_to_num(commuters * transit_frac, nan=0)
    transit_cost = transit_commuters_per_hh * TRANSIT_TRIPS_PER_COMMUTER * TRANSIT_COST_PER_TRIP

    total = auto_ownership_cost + vmt_cost + transit_cost

    return pd.DataFrame({
        "auto_ownership_cost": auto_ownership_cost,
        "vmt_cost": vmt_cost,
        "transit_cost": transit_cost,
        "total_transport_cost": total,
    }, index=df.index)


# ---------------------------------------------------------------------------
# Housing costs
# ---------------------------------------------------------------------------


def compute_housing_costs(df: pd.DataFrame) -> np.ndarray:
    """Compute annual housing cost per household.

    Weighted average of median owner cost (with mortgage) and median gross
    rent, weighted by tenure ratio.

    Annual = monthly cost × 12
    """
    owner_cost = df["median_owner_cost"].values.astype(float)
    rent = df["median_gross_rent"].values.astype(float)
    owner_n = df["owner_occ"].values.astype(float)
    renter_n = df["renter_occ"].values.astype(float)
    total = np.maximum(owner_n + renter_n, 1)

    # Weighted monthly cost
    monthly = (owner_cost * owner_n + rent * renter_n) / total
    monthly = np.nan_to_num(monthly, nan=0)
    return monthly * 12


# ---------------------------------------------------------------------------
# H+T Index construction
# ---------------------------------------------------------------------------


def compute_ht_index(
    df: pd.DataFrame,
    use_typical_household: bool = True,
) -> pd.DataFrame:
    """Compute the full H+T Affordability Index per block group.

    Parameters
    ----------
    df : variables DataFrame from variables.compute_all_variables()
    use_typical_household : if True, set household variables to regional
        medians (CNT "Regional Typical Household" approach)

    Returns
    -------
    DataFrame with columns: geoid, ht_index, housing_cost_pct, transport_cost_pct,
                           autos_per_hh, vmt_per_hh, transit_frac, ...
    """
    model_df = df.copy()

    if use_typical_household:
        # Set household variables to regional medians
        med_income = model_df["income"].median()
        med_hh_size = model_df["hh_size"].median()
        med_commuters = model_df["commuters"].median()

        log.info(
            "Regional Typical Household: income=%.0f, hh_size=%.2f, commuters=%.2f",
            med_income, med_hh_size, med_commuters,
        )

        model_df["income"] = med_income
        model_df["hh_size"] = med_hh_size
        model_df["commuters"] = med_commuters

    # Predict transportation behavior
    autos = predict_auto_ownership(model_df)
    vmt = predict_vmt(model_df)
    transit_frac = predict_transit_use(model_df)

    # Clip to reasonable ranges
    autos = np.clip(autos, 0, 5)
    vmt = np.clip(vmt, 0, 50000)
    transit_frac = np.clip(transit_frac, 0, 1)

    # Compute costs
    transport_costs = compute_transportation_costs(
        model_df, autos, vmt, transit_frac,
    )
    housing_cost = compute_housing_costs(df)  # Use actual housing costs, not typical

    # Compute H+T Index
    income = df["income"].values.astype(float)
    income_safe = np.maximum(income, 1)  # avoid division by zero

    housing_pct = (housing_cost / income_safe) * 100
    transport_pct = (transport_costs["total_transport_cost"].values / income_safe) * 100
    ht_index = housing_pct + transport_pct

    # Clip to reasonable range
    ht_index = np.clip(ht_index, 0, 200)
    housing_pct = np.clip(housing_pct, 0, 100)
    transport_pct = np.clip(transport_pct, 0, 100)

    result = pd.DataFrame({
        "geoid": df.index,
        "ht_index": ht_index,
        "housing_cost_pct": housing_pct,
        "transport_cost_pct": transport_pct,
        "housing_cost_annual": housing_cost,
        "transport_cost_annual": transport_costs["total_transport_cost"].values,
        "auto_ownership_cost": transport_costs["auto_ownership_cost"].values,
        "vmt_cost": transport_costs["vmt_cost"].values,
        "transit_cost": transport_costs["transit_cost"].values,
        "autos_per_hh": autos,
        "vmt_per_hh": vmt,
        "transit_frac": transit_frac,
    })

    log.info(
        "H+T Index: median=%.1f%%, mean=%.1f%%, range=[%.1f, %.1f]",
        np.nanmedian(ht_index), np.nanmean(ht_index),
        np.nanmin(ht_index), np.nanmax(ht_index),
    )
    return result
