"""Prepare cooperative extension measures.

Configuration is read from cooperative_extension/pipeline.yaml.
Combines ACS-based measures with County Health Rankings data:
- perc_male: ACS S0101 (percentage male)
- perc_children_raised_by_GPs: ACS B10001 (children with grandparents)
- disconnectedYouth: County Health Rankings Excel downloads
- voterTurnout: County Health Rankings Excel downloads
"""

import time
from pathlib import Path

import httpx
import pandas as pd
import yaml
from sdc_core.census import CensusClient
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.profiles import resolve_states
from sdc_core.result import RunResult
from tqdm import tqdm

TOPIC_DIR = Path(__file__).resolve().parents[1]
log = get_logger("cooperative_extension.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def ingest_perc_male(client: CensusClient, config: dict) -> pd.DataFrame:
    """Fetch male percentage from ACS S0101 subject table."""
    pm_config = config["source"]["perc_male"]
    state = config["source"]["state"]
    geographies = config["source"]["geographies"]

    records = []
    for year in tqdm(pm_config["years"], desc="perc_male"):
        var_id = (
            pm_config["variable_2017_plus"]
            if year >= 2017
            else pm_config["variable_pre_2017"]
        )
        total_id = pm_config["total_variable"]
        for geo in geographies:
            df = client.get_acs_wide(
                variables={"male_pct_or_count": var_id, "total_pop": total_id},
                geography=geo,
                state=state,
                year=year,
                show_progress=False,
            )
            if df.empty:
                continue
            if year >= 2017:
                df["value"] = df["male_pct_or_count"]
            else:
                df["value"] = 100 * df["male_pct_or_count"] / df["total_pop"]
            df["measure"] = "perc_male"
            df["moe"] = pd.NA
            records.append(
                df[["geoid", "year", "measure", "value", "moe", "region_type"]]
            )

    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()


def ingest_children_gp(client: CensusClient, config: dict) -> pd.DataFrame:
    """Fetch children raised by grandparents from ACS B10001."""
    gp_config = config["source"]["children_gp"]
    state = config["source"]["state"]
    geographies = config["source"]["geographies"]

    dfs = []
    for year in tqdm(gp_config["years"], desc="children_gp"):
        for geo in geographies:
            df = client.get_acs_wide(
                variables=gp_config["variables"],
                geography=geo,
                state=state,
                year=year,
                show_progress=False,
            )
            if df.empty:
                continue
            df["value"] = 100 * df["children_gp"] / df["total_pop"]
            df["measure"] = "perc_children_raised_by_GPs"
            df["moe"] = pd.NA
            dfs.append(df[["geoid", "year", "measure", "value", "moe", "region_type"]])

    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def ingest_county_health_rankings(config: dict) -> pd.DataFrame:
    """Download and parse County Health Rankings data for VA."""
    chr_config = config["source"]["county_health_rankings"]
    url_template = chr_config["url_template"]
    measures = chr_config["measures"]

    records = []
    for year in tqdm(chr_config["years"], desc="County Health Rankings"):
        url = url_template.format(year=year)
        try:
            resp = httpx.get(url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("Could not download CHR %d: %s", year, e)
            continue

        tmp = TOPIC_DIR / "data" / "working" / f"chr_{year}.xlsx"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(resp.content)

        try:
            df = pd.read_excel(tmp, sheet_name="Ranked Measure Data", header=1)
        except Exception as e:
            log.warning("Could not parse CHR %d: %s", year, e)
            continue

        if "FIPS" not in df.columns:
            log.warning("No FIPS column in CHR %d, skipping", year)
            continue

        df["geoid"] = df["FIPS"].astype(str).str.zfill(5)

        for measure_def in measures:
            col_name = measure_def["column"]
            measure_name = measure_def["name"]
            if col_name in df.columns:
                subset = df[["geoid"]].copy()
                subset["year"] = year
                subset["measure"] = measure_name
                subset["value"] = pd.to_numeric(df[col_name], errors="coerce")
                subset["moe"] = pd.NA
                subset["region_type"] = "county"
                records.append(subset.dropna(subset=["value"]))

    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()


def run(pipeline=None) -> RunResult:
    t0 = time.time()
    try:
        config = load_config()
        out = config["output"]

        log.info("Starting cooperative extension prepare")

        client = CensusClient()
        parts = []

        log.info("Ingesting perc_male from ACS S0101")
        parts.append(ingest_perc_male(client, config))

        log.info("Ingesting children raised by grandparents from ACS B10001")
        parts.append(ingest_children_gp(client, config))

        log.info("Ingesting County Health Rankings")
        parts.append(ingest_county_health_rankings(config))

        result = pd.concat([p for p in parts if not p.empty], ignore_index=True)

        out_dir = TOPIC_DIR / out["path"]
        states = resolve_states(config["source"])
        auto_name = build_file_name(
            df=result,
            states=states,
            years=config["source"]["perc_male"].get("years"),
            source_type=config["source"].get("type"),
            title=config.get("name"),
        )
        filename = f"{auto_name}.csv.xz" if auto_name else out["filename"]
        out_path = write_data(
            result,
            out_dir / filename,
            census_standardize=out.get("standardize", False),
        )
        log.info("Wrote %d rows to %s", len(result), out_path)

        return RunResult(
            success=True,
            rows=len(result),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error("Cooperative extension prepare failed: %s", e, exc_info=True)
        return RunResult(
            success=False,
            error=str(e),
            duration_sec=time.time() - t0,
        )


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
