"""Mergent Intellect business & employment metrics.

Python equivalent of utils/distribution/functions.R.
Reads block-group-level feature files and computes business dynamics,
employment dynamics, industry concentration (HHI), and location quotient
metrics at block_group / tract / county levels.
"""

import pandas as pd

NAICS_RECODE = {
    "31": "31_33", "32": "31_33", "33": "31_33",
    "44": "44_45", "45": "44_45",
    "48": "48_49", "49": "48_49",
}

TOPIC_MAP = {
    "Total": ["aggregate"],
    "Minority_owned": ["minority"],
    "Industry": ["industry"],
    "Industry_Minority_owned": ["industry", "minority"],
}

GEO_LEVELS = {
    "county": 5,
    "tract": 11,
    "blockgroup": 12,
}

FEATURE_FILES = {
    "va059": "mi_fairfax_features_bg.csv.xz",
    "ncr": "mi_ncr_features_bg.csv.xz",
    "rva": "mi_subva_features_bg.csv.xz",
}


def load_features(path) -> pd.DataFrame:
    """Read a Mergent Intellect feature file with correct dtypes."""
    df = pd.read_csv(path, dtype={"geoid": str})
    df["geoid"] = df["geoid"].astype(str).str.zfill(12)
    return df


def recode_naics(df: pd.DataFrame) -> pd.DataFrame:
    """Group 2-digit NAICS codes (31-33→31_33, 44-45→44_45, 48-49→48_49)."""
    df = df.copy()
    df["naics_indu"] = df["naics2"].astype(str).map(
        lambda x: NAICS_RECODE.get(x, x)
    )
    return df


def _prepare_data(df: pd.DataFrame, topics: list[str]) -> pd.DataFrame:
    """Add geo columns and topic column for grouping."""
    df = df.copy()
    df["geoid"] = df["geoid"].astype(str).str.zfill(12)
    df["geoid_blockgroup"] = df["geoid"]
    df["geoid_tract"] = df["geoid"].str[:11]
    df["geoid_county"] = df["geoid"].str[:5]
    df["industry"] = "NAICS" + df["naics_indu"] + "_"
    df["minority"] = df["minority"].apply(
        lambda x: "minority_owned_" if x == 1 else "non_minority_owned_"
    )
    df["aggregate"] = ""
    # Build topic column by concatenating the relevant topic columns
    df["topic"] = ""
    for t in topics:
        df["topic"] = df["topic"] + df[t]
    return df


def _build_long(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Combine frames into final long format."""
    result = pd.concat(frames, ignore_index=True)
    result["moe"] = pd.NA
    result = result[["geoid", "year", "measure", "value", "moe"]]
    result = result.dropna(subset=["value"])
    result = result.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)
    return result


def _geo_col(geo: str) -> str:
    return f"geoid_{geo.replace(' ', '')}"


# ---------------------------------------------------------------------------
# Business metrics
# ---------------------------------------------------------------------------

def compute_entry(df: pd.DataFrame, geolevels: list[str], topics: list[str]) -> pd.DataFrame:
    data = _prepare_data(df, topics)
    frames = []
    for geo in geolevels:
        gcol = _geo_col(geo)
        grp = data.groupby([gcol, "year", "topic"])
        agg = grp.agg(
            total_business=("duns", "count"),
            new_business=("entry", lambda x: x.sum(skipna=True)),
        ).reset_index()
        agg["entry_rate"] = 100 * agg["new_business"] / agg["total_business"]
        melted = agg.melt(
            id_vars=[gcol, "year", "topic"],
            value_vars=["new_business", "entry_rate"],
            var_name="measure", value_name="value",
        )
        melted["measure"] = melted["topic"] + melted["measure"]
        melted = melted.rename(columns={gcol: "geoid"})
        frames.append(melted[["geoid", "year", "measure", "value"]])
    return pd.concat(frames, ignore_index=True)


def compute_exit(df: pd.DataFrame, geolevels: list[str], topics: list[str]) -> pd.DataFrame:
    data = _prepare_data(df, topics)
    frames = []
    for geo in geolevels:
        gcol = _geo_col(geo)
        grp = data.groupby([gcol, "year", "topic"])
        agg = grp.agg(
            total_business=("duns", "count"),
            exit_business=("exit", lambda x: x.sum(skipna=True)),
        ).reset_index()
        agg["exit_rate"] = 100 * agg["exit_business"] / agg["total_business"]
        melted = agg.melt(
            id_vars=[gcol, "year", "topic"],
            value_vars=["exit_business", "exit_rate"],
            var_name="measure", value_name="value",
        )
        melted["measure"] = melted["topic"] + melted["measure"]
        melted = melted.rename(columns={gcol: "geoid"})
        frames.append(melted[["geoid", "year", "measure", "value"]])
    return pd.concat(frames, ignore_index=True)


def compute_count(df: pd.DataFrame, geolevels: list[str], topics: list[str]) -> pd.DataFrame:
    data = _prepare_data(df, topics)
    frames = []
    for geo in geolevels:
        gcol = _geo_col(geo)
        agg = data.groupby([gcol, "year", "topic"]).agg(
            value=("duns", "count"),
        ).reset_index()
        agg["measure"] = agg["topic"] + "number_business"
        agg = agg.rename(columns={gcol: "geoid"})
        frames.append(agg[["geoid", "year", "measure", "value"]])
    return pd.concat(frames, ignore_index=True)


def compute_size(df: pd.DataFrame, geolevels: list[str], topics: list[str]) -> pd.DataFrame:
    """Compute small/sole-proprietor business metrics. Note: R code computes
    these but never includes them in the output file (dead code)."""
    data = _prepare_data(df, topics)
    frames = []
    for geo in geolevels:
        gcol = _geo_col(geo)
        agg = data.groupby([gcol, "year", "topic"]).agg(
            total_business=("duns", "count"),
            small_business=("small", lambda x: x.sum(skipna=True)),
            soloproprio_business=("sole_proprietor", lambda x: x.sum(skipna=True)),
        ).reset_index()
        agg["perc_small"] = 100 * agg["small_business"] / agg["total_business"]
        agg["perc_soloproprio"] = 100 * agg["soloproprio_business"] / agg["total_business"]
        melted = agg.melt(
            id_vars=[gcol, "year", "topic"],
            value_vars=["small_business", "soloproprio_business", "perc_small", "perc_soloproprio"],
            var_name="measure", value_name="value",
        )
        melted["measure"] = melted["topic"] + melted["measure"]
        melted = melted.rename(columns={gcol: "geoid"})
        frames.append(melted[["geoid", "year", "measure", "value"]])
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Employment metrics
# ---------------------------------------------------------------------------

def _add_employment_diff(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-firm employment change: sort by (duns, desc(year)), then
    employment_diff = -diff(employment). Positive diff = firm grew."""
    df = df.sort_values(["duns", "year"], ascending=[True, False])
    df["employment_diff"] = -df.groupby("duns")["employment"].diff()
    return df


def compute_job_creation(df: pd.DataFrame, geolevels: list[str], topics: list[str]) -> pd.DataFrame:
    data = recode_naics(df)
    data = _add_employment_diff(data)
    data = _prepare_data(data, topics)
    # Filter: new firms or growing firms
    data = data[(data["entry"] == 1) | (data["employment_diff"] > 0)].copy()
    # Compute intermediate columns
    data["_jc_new"] = data["entry"] * data["employment"]
    data["_jc_active"] = (1 - data["entry"]) * data["employment_diff"]

    frames = []
    for geo in geolevels:
        gcol = _geo_col(geo)
        grp = data.groupby([gcol, "year", "topic"])
        agg = grp.agg(
            business_create_job=("duns", "count"),
            job_creation_new=("_jc_new", lambda x: x.sum(skipna=True)),
            job_creation_active=("_jc_active", lambda x: x.sum(skipna=True)),
        ).reset_index()
        agg["total_job_creation"] = agg["job_creation_new"] + agg["job_creation_active"]
        agg["perc_job_creation_new"] = 100 * agg["job_creation_new"] / agg["total_job_creation"]
        agg["perc_job_creation_active"] = 100 * agg["job_creation_active"] / agg["total_job_creation"]

        melted = agg.melt(
            id_vars=[gcol, "year", "topic"],
            value_vars=[
                "business_create_job", "job_creation_new", "job_creation_active",
                "total_job_creation", "perc_job_creation_new", "perc_job_creation_active",
            ],
            var_name="measure", value_name="value",
        )
        melted["measure"] = melted["topic"] + melted["measure"]
        melted = melted.rename(columns={gcol: "geoid"})
        frames.append(melted[["geoid", "year", "measure", "value"]])
    return pd.concat(frames, ignore_index=True)


def compute_job_destruction(df: pd.DataFrame, geolevels: list[str], topics: list[str]) -> pd.DataFrame:
    data = recode_naics(df)
    data = _add_employment_diff(data)
    data = _prepare_data(data, topics)
    # Filter: exited firms or shrinking firms
    data = data[(data["exit"] == 1) | (data["employment_diff"] < 0)].copy()

    # Compute intermediate columns
    data["_jd_exit"] = data["exit"] * data["employment"]
    data["_jd_active"] = -((1 - data["exit"]) * data["employment_diff"])

    frames = []
    for geo in geolevels:
        gcol = _geo_col(geo)
        grp = data.groupby([gcol, "year", "topic"])
        agg = grp.agg(
            business_destruction_job=("duns", "count"),
            job_destruction_exit=("_jd_exit", lambda x: x.sum(skipna=True)),
            job_destruction_active=("_jd_active", lambda x: x.sum(skipna=True)),
        ).reset_index()
        agg["total_job_destruction"] = agg["job_destruction_exit"] + agg["job_destruction_active"]
        agg["perc_job_destruction_exit"] = 100 * agg["job_destruction_exit"] / agg["total_job_destruction"]
        agg["perc_job_destruction_active"] = 100 * agg["job_destruction_active"] / agg["total_job_destruction"]

        melted = agg.melt(
            id_vars=[gcol, "year", "topic"],
            value_vars=[
                "business_destruction_job", "job_destruction_exit", "job_destruction_active",
                "total_job_destruction", "perc_job_destruction_exit", "perc_job_destruction_active",
            ],
            var_name="measure", value_name="value",
        )
        melted["measure"] = melted["topic"] + melted["measure"]
        melted = melted.rename(columns={gcol: "geoid"})
        frames.append(melted[["geoid", "year", "measure", "value"]])
    return pd.concat(frames, ignore_index=True)


def compute_job_count(df: pd.DataFrame, geolevels: list[str], topics: list[str]) -> pd.DataFrame:
    data = _prepare_data(df, topics)
    frames = []
    for geo in geolevels:
        gcol = _geo_col(geo)
        agg = data.groupby([gcol, "year", "topic"]).agg(
            value=("employment", lambda x: x.sum(skipna=True)),
        ).reset_index()
        agg["measure"] = agg["topic"] + "total_employment"
        agg = agg.rename(columns={gcol: "geoid"})
        frames.append(agg[["geoid", "year", "measure", "value"]])
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Industry-specific metrics
# ---------------------------------------------------------------------------

def compute_hhi(df: pd.DataFrame) -> pd.DataFrame:
    """Herfindahl-Hirschman Index at county level per industry."""
    data = recode_naics(df)
    data = data.copy()
    data["geoid"] = data["geoid"].astype(str).str.zfill(12).str[:5]
    data["industry"] = "NAICS" + data["naics_indu"] + "_"

    # For each (county, year, industry): HHI = sum((100 * emp_i / emp_total)^2)
    grp = data.groupby(["geoid", "year", "industry"])
    emp_total = grp["employment"].transform("sum")
    data["share_sq"] = ((100 * data["employment"] / emp_total) ** 2)

    agg = data.groupby(["geoid", "year", "industry"]).agg(
        value=("share_sq", lambda x: round(x.sum(skipna=True), 2)),
    ).reset_index()
    agg["measure"] = agg["industry"] + "Herfindalh_Hirschman_index"
    agg["moe"] = pd.NA
    result = agg[["geoid", "year", "measure", "value", "moe"]]
    return result.dropna(subset=["value"]).reset_index(drop=True)


def compute_lq(df: pd.DataFrame, geolevels: list[str]) -> pd.DataFrame:
    """Location Quotient: industry share in geo relative to parent county."""
    data = recode_naics(df)
    data = data.copy()
    data["geoid"] = data["geoid"].astype(str).str.zfill(12)
    data["geoid_blockgroup"] = data["geoid"]
    data["geoid_tract"] = data["geoid"].str[:11]
    data["geoid_county"] = data["geoid"].str[:5]
    data["industry"] = "NAICS" + data["naics_indu"] + "_"

    # Pre-compute county-level totals
    county_emp = data.groupby(["geoid_county", "year"])["employment"].sum().rename("emp_cnty")
    county_ind_emp = data.groupby(["geoid_county", "industry", "year"])["employment"].sum().rename("emp_cnty_ind")

    frames = []
    for geo in geolevels:
        gcol = _geo_col(geo)

        # Geo-level totals
        geo_emp = data.groupby([gcol, "year"])["employment"].sum().rename("emp_geo")
        geo_ind_emp = data.groupby([gcol, "industry", "year"])["employment"].sum().rename("emp_geo_ind")

        lq_df = geo_ind_emp.reset_index()
        lq_df = lq_df.merge(geo_emp.reset_index(), on=[gcol, "year"])

        # Map to parent county
        lq_df["geoid_county"] = lq_df[gcol].str[:5]
        lq_df = lq_df.merge(county_emp.reset_index(), on=["geoid_county", "year"])
        lq_df = lq_df.merge(county_ind_emp.reset_index(), on=["geoid_county", "industry", "year"])

        lq_df["share_ind_geo"] = lq_df["emp_geo_ind"] / lq_df["emp_geo"]
        lq_df["share_ind_cnty"] = lq_df["emp_cnty_ind"] / lq_df["emp_cnty"]
        lq_df["value"] = (lq_df["share_ind_geo"] / lq_df["share_ind_cnty"]).round(2)
        lq_df["measure"] = lq_df["industry"] + "Location_quotient"

        lq_df = lq_df.rename(columns={gcol: "geoid"})
        frames.append(lq_df[["geoid", "year", "measure", "value"]])

    result = pd.concat(frames, ignore_index=True)
    result["moe"] = pd.NA
    result = result[["geoid", "year", "measure", "value", "moe"]]
    return result.dropna(subset=["value"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Orchestrators
# ---------------------------------------------------------------------------

GEOLEVELS = ["tract", "block group", "county"]


def business_dynamics(
    df: pd.DataFrame, topic: str, prefix: str,
) -> tuple[pd.DataFrame, str]:
    """Compute business characteristic metrics. Returns (DataFrame, filename)."""
    topics = TOPIC_MAP[topic]
    data = recode_naics(df)

    parts = [
        compute_entry(data, GEOLEVELS, topics),
        compute_exit(data, GEOLEVELS, topics),
        compute_count(data, GEOLEVELS, topics),
    ]
    output = _build_long(parts)

    geo_abbr = "cttrbg"
    yr_min, yr_max = int(output["year"].min()), int(output["year"].max())
    filename = f"{prefix}_{geo_abbr}_mi_{yr_min}_{yr_max}_business_metrics_by_{topic}.csv.xz"
    return output, filename


def employment_dynamics(
    df: pd.DataFrame, topic: str, prefix: str,
) -> tuple[pd.DataFrame, str]:
    """Compute employment metrics. Returns (DataFrame, filename)."""
    topics = TOPIC_MAP[topic]

    parts = [
        compute_job_creation(df, GEOLEVELS, topics),
        compute_job_destruction(df, GEOLEVELS, topics),
        compute_job_count(recode_naics(df), GEOLEVELS, topics),
    ]
    output = _build_long(parts)

    geo_abbr = "cttrbg"
    yr_min, yr_max = int(output["year"].min()), int(output["year"].max())
    filename = f"{prefix}_{geo_abbr}_mi_{yr_min}_{yr_max}_employment_metrics_by_{topic}.csv.xz"
    return output, filename
