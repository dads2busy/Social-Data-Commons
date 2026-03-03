"""Ingest poverty rates by race and sex from ACS B17001 tables.

Produces three outputs:
  1. NCR adults poverty by race/sex (B17001A-I, rows 10-16/24-30/39-45/53-59)
  2. NCR children poverty by race/sex (B17001A-I, rows 4-9/18-23/33-38/47-52)
  3. Fairfax County demographics poverty by race/sex (B17001, summary totals)
"""

import time
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.census import CensusClient
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"

log = get_logger("poverty.ingest")

# NCR county FIPS prefixes (tracts starting with these are in NCR)
NCR_PREFIXES = (
    "24021", "24031", "24033", "24017",  # MD counties
    "11001",                              # DC
    "51107", "51059", "51153", "51013",  # VA counties
    "51510", "51683", "51600", "51610", "51685",  # VA independent cities
)

# ACS B17001 row definitions for adults
ADULT_POV_ROWS = list(range(10, 17))      # men in poverty (rows 10-16)
ADULT_NO_POV_ROWS = list(range(39, 46))   # men not in poverty (rows 39-45)
ADULT_WPOV_ROWS = list(range(24, 31))     # women in poverty (rows 24-30)
ADULT_WNO_POV_ROWS = list(range(53, 60))  # women not in poverty (rows 53-59)

# ACS B17001 row definitions for children
CHILD_POV_ROWS = list(range(4, 10))       # boys in poverty (rows 4-9)
CHILD_NO_POV_ROWS = list(range(33, 39))   # boys not in poverty (rows 33-38)
CHILD_WPOV_ROWS = list(range(18, 24))     # girls in poverty (rows 18-23)
CHILD_WNO_POV_ROWS = list(range(47, 53))  # girls not in poverty (rows 47-52)


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def _var_ids(table_letter: str, rows: list[int]) -> list[str]:
    """Generate ACS variable IDs like B17001A_010."""
    return [f"B17001{table_letter}_{r:03d}" for r in rows]


def _build_table_variables(race: str, letter: str,
                           pov_rows: list[int], no_pov_rows: list[int],
                           wpov_rows: list[int], wno_pov_rows: list[int]) -> dict[str, str]:
    """Build the variable dict for a single race table letter (~28 vars)."""
    variables = {}
    for suffix, rows in [("mpov", pov_rows), ("mnopov", no_pov_rows),
                         ("wpov", wpov_rows), ("wnopov", wno_pov_rows)]:
        for var_id in _var_ids(letter, rows):
            key = f"{race}_{suffix}_{var_id}"
            variables[key] = var_id
    return variables


def compute_ncr_measures(df: pd.DataFrame, config: dict,
                         pov_rows: list[int], no_pov_rows: list[int],
                         wpov_rows: list[int], wno_pov_rows: list[int],
                         male_label: str, female_label: str) -> pd.DataFrame:
    """Compute poverty count and percent measures for NCR data."""
    race_tables = config["sources"]["ncr"]["race_tables"]
    other_tables = config["sources"]["ncr"]["other_tables"]
    records = []

    for _, row in df.iterrows():
        geoid = row["geoid"]
        year = row["year"]

        for race, letter in race_tables.items():
            _compute_race_measures(
                row, geoid, year, race, [letter],
                pov_rows, no_pov_rows, wpov_rows, wno_pov_rows,
                male_label, female_label, records,
            )

        # "othr" combines C, E, F, G tables
        _compute_race_measures(
            row, geoid, year, "othr", other_tables,
            pov_rows, no_pov_rows, wpov_rows, wno_pov_rows,
            male_label, female_label, records,
        )

    return pd.DataFrame(records)


def _compute_race_measures(row, geoid, year, race, letters,
                           pov_rows, no_pov_rows, wpov_rows, wno_pov_rows,
                           male_label, female_label, records):
    """Compute count/percent measures for one race across one or more table letters."""
    mpov = sum(row.get(f"{race}_mpov_{v}", 0) or 0 for l in letters for v in _var_ids(l, pov_rows))
    mnopov = sum(row.get(f"{race}_mnopov_{v}", 0) or 0 for l in letters for v in _var_ids(l, no_pov_rows))
    wpov = sum(row.get(f"{race}_wpov_{v}", 0) or 0 for l in letters for v in _var_ids(l, wpov_rows))
    wnopov = sum(row.get(f"{race}_wnopov_{v}", 0) or 0 for l in letters for v in _var_ids(l, wno_pov_rows))

    m_total = mpov + mnopov
    w_total = wpov + wnopov

    base = {"geoid": geoid, "year": year, "moe": pd.NA, "region_type": "tract"}

    records.append({**base, "measure": f"{race}_{male_label}_pov_cnt", "value": mpov})
    records.append({**base, "measure": f"{race}_{female_label}_pov_cnt", "value": wpov})

    m_pct = (100 * mpov / m_total) if m_total > 0 else None
    w_pct = (100 * wpov / w_total) if w_total > 0 else None
    records.append({**base, "measure": f"{race}_{male_label}_pov_pct", "value": m_pct})
    records.append({**base, "measure": f"{race}_{female_label}_pov_pct", "value": w_pct})


def filter_ncr(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only tracts in NCR counties."""
    mask = df["geoid"].str[:5].isin(NCR_PREFIXES)
    return df[mask].copy()


def run_ncr_source(client: CensusClient, config: dict,
                   pov_rows, no_pov_rows, wpov_rows, wno_pov_rows,
                   male_label, female_label, title) -> RunResult:
    """Run one NCR source (adults or children).

    Fetches each race table separately (~28 vars each) to stay under the
    Census API's per-request variable limit, then merges results.
    """
    t0 = time.time()
    try:
        src = config["sources"]["ncr"]
        race_tables = src["race_tables"]
        other_tables = src["other_tables"]

        # Build list of (race_label, table_letter) pairs
        all_tables = list(race_tables.items()) + [("othr", t) for t in other_tables]

        merged = None
        merge_keys = ["geoid", "year", "region_type"]

        for race, letter in all_tables:
            variables = _build_table_variables(
                race, letter, pov_rows, no_pov_rows, wpov_rows, wno_pov_rows,
            )
            log.info("Fetching table B17001%s (%d vars) for NCR %s", letter, len(variables), title)

            df = client.get_acs_multi(
                variables=variables,
                years=src["years"],
                geographies=src["geographies"],
                profile=src.get("profile"),
                estimate_only=True,
                table_type="detail",
            )

            if df.empty:
                log.warning("No data for table B17001%s", letter)
                continue

            # Keep only the variable columns + merge keys
            var_cols = [c for c in df.columns if c not in merge_keys and c != "NAME"]
            df = df[merge_keys + var_cols]

            if merged is None:
                merged = df
            else:
                merged = merged.merge(df, on=merge_keys, how="outer")

        if merged is None or merged.empty:
            return RunResult(success=False, error=f"No data for NCR {title}", duration_sec=time.time() - t0)

        merged = filter_ncr(merged)
        result = compute_ncr_measures(merged, config, pov_rows, no_pov_rows, wpov_rows, wno_pov_rows,
                                      male_label, female_label)
        result = result.dropna(subset=["value"])

        filename = build_file_name(
            coverage_area="ncr", data_source="census_acs", years=src["years"],
            title=title, geographies=["tract"],
        ) + ".csv.xz"
        out_path = write_data(result, DIST_DIR / filename, census_standardize=False)
        log.info("Wrote %d rows to %s", len(result), out_path)

        return RunResult(success=True, rows=len(result), output_path=str(out_path), duration_sec=time.time() - t0)
    except Exception as e:
        log.error("Ingest failed for NCR %s: %s", title, e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


def compute_ffx_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Compute Fairfax County poverty measures by race and sex."""
    records = []
    races = {
        "wht": ("wht", True),
        "afr_amer": ("afr_amer", True),
        "asian": ("asian", True),
    }

    for _, row in df.iterrows():
        geoid = row["geoid"]
        year = row["year"]
        base = {"geoid": geoid, "year": year, "moe": pd.NA, "region_type": "tract"}

        # Compute "other" = total - white - black - asian
        below_m_other = (row.get("below_m", 0) or 0) - (row.get("below_m_wht", 0) or 0) - (row.get("below_m_afr_amer", 0) or 0) - (row.get("below_m_asian", 0) or 0)
        below_f_other = (row.get("below_f", 0) or 0) - (row.get("below_f_wht", 0) or 0) - (row.get("below_f_afr_amer", 0) or 0) - (row.get("below_f_asian", 0) or 0)
        above_m_other = (row.get("above_m", 0) or 0) - (row.get("above_m_wht", 0) or 0) - (row.get("above_m_afr_amer", 0) or 0) - (row.get("above_m_asian", 0) or 0)
        above_f_other = (row.get("above_f", 0) or 0) - (row.get("above_f_wht", 0) or 0) - (row.get("above_f_afr_amer", 0) or 0) - (row.get("above_f_asian", 0) or 0)

        all_races = {
            "wht": {"below_m": row.get("below_m_wht", 0), "below_f": row.get("below_f_wht", 0),
                     "above_m": row.get("above_m_wht", 0), "above_f": row.get("above_f_wht", 0)},
            "afr_amer": {"below_m": row.get("below_m_afr_amer", 0), "below_f": row.get("below_f_afr_amer", 0),
                         "above_m": row.get("above_m_afr_amer", 0), "above_f": row.get("above_f_afr_amer", 0)},
            "asian": {"below_m": row.get("below_m_asian", 0), "below_f": row.get("below_f_asian", 0),
                      "above_m": row.get("above_m_asian", 0), "above_f": row.get("above_f_asian", 0)},
            "other": {"below_m": below_m_other, "below_f": below_f_other,
                      "above_m": above_m_other, "above_f": above_f_other},
        }

        for race, vals in all_races.items():
            for sex in ["m", "f"]:
                below = vals[f"below_{sex}"] or 0
                above = vals[f"above_{sex}"] or 0
                total = below + above
                pov_pct = below / total if total > 0 else None

                records.append({**base, "measure": f"tot_{sex}_{race}", "value": total})
                records.append({**base, "measure": f"below_pov_{sex}_{race}", "value": below})
                records.append({**base, "measure": f"pov_pct_{sex}_{race}", "value": pov_pct})

    return pd.DataFrame(records)


def run_ffx_source(client: CensusClient, config: dict) -> RunResult:
    """Run Fairfax County demographics source."""
    t0 = time.time()
    try:
        src = config["sources"]["ffx"]
        log.info("Fetching FFX poverty variables")

        df = client.get_acs_multi(
            variables=src["variables"],
            years=src["years"],
            geographies=src["geographies"],
            states=["VA"],
            estimate_only=True,
            table_type="detail",
        )

        if df.empty:
            return RunResult(success=False, error="No data for FFX", duration_sec=time.time() - t0)

        # Filter to Fairfax County tracts only
        df = df[df["geoid"].str.startswith("51059")].copy()

        result = compute_ffx_measures(df)
        result = result.dropna(subset=["value"])

        filename = f"va059_tr_census_acs_{src['years'][0]}_{src['years'][-1]}_poverty_demographics.csv.xz"
        out_path = write_data(result, DIST_DIR / filename, census_standardize=False)
        log.info("Wrote %d rows to %s", len(result), out_path)

        return RunResult(success=True, rows=len(result), output_path=str(out_path), duration_sec=time.time() - t0)
    except Exception as e:
        log.error("Ingest failed for FFX: %s", e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


def run() -> list[RunResult]:
    config = load_config()
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    client = CensusClient()

    results = []

    # NCR adults
    results.append(run_ncr_source(
        client, config,
        ADULT_POV_ROWS, ADULT_NO_POV_ROWS, ADULT_WPOV_ROWS, ADULT_WNO_POV_ROWS,
        "men", "women", "poverty_adults",
    ))

    # NCR children
    results.append(run_ncr_source(
        client, config,
        CHILD_POV_ROWS, CHILD_NO_POV_ROWS, CHILD_WPOV_ROWS, CHILD_WNO_POV_ROWS,
        "boys", "girls", "poverty_children",
    ))

    # Fairfax demographics
    results.append(run_ffx_source(client, config))

    return results


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
