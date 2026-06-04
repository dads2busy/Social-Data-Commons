"""Ingest cooperative extension measures from ACS and County Health Rankings.

Combines ACS-based measures with County Health Rankings data:
- perc_male: ACS S0101 (percentage male)
- perc_children_raised_by_GPs: ACS B10001 (children with grandparents)
- disconnectedYouth: County Health Rankings Excel downloads
- voterTurnout: County Health Rankings Excel downloads
"""

import time
from pathlib import Path

import pandas as pd
import yaml
from sdc_core.census import CensusClient
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.profiles import resolve_states
from sdc_core.result import RunResult
from sdc_core.sources.chr import ingest_chr
from tqdm import tqdm

TOPIC_DIR = Path(__file__).resolve().parents[2]
MEASURE_INFO = TOPIC_DIR / "data/distribution/measure_info.json"
DIST_DIR = TOPIC_DIR / "data/distribution"

log = get_logger("cooperative_extension.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def ingest_perc_male(client: CensusClient, source_cfg: dict) -> pd.DataFrame:
    """Fetch male percentage from ACS S0101 subject table."""
    pm_config = source_cfg["perc_male"]
    state = source_cfg["state"]
    geographies = source_cfg["geographies"]
    cache_dir = TOPIC_DIR / "data/working/acs_cache"

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
                table_type="subject",
                cache_dir=cache_dir,
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


def ingest_children_gp(client: CensusClient, source_cfg: dict) -> pd.DataFrame:
    """Fetch children raised by grandparents from ACS B10001."""
    gp_config = source_cfg["children_gp"]
    state = source_cfg["state"]
    geographies = source_cfg["geographies"]
    cache_dir = TOPIC_DIR / "data/working/acs_cache"

    dfs = []
    for year in tqdm(gp_config["years"], desc="children_gp"):
        for geo in geographies:
            df = client.get_acs_wide(
                variables=gp_config["variables"],
                geography=geo,
                state=state,
                year=year,
                show_progress=False,
                cache_dir=cache_dir,
            )
            if df.empty:
                continue
            df["value"] = 100 * df["children_gp"] / df["total_pop"]
            df["measure"] = "perc_children_raised_by_GPs"
            df["moe"] = pd.NA
            dfs.append(df[["geoid", "year", "measure", "value", "moe", "region_type"]])

    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def run_source(name: str, source_cfg: dict, out_cfg: dict, title: str | None) -> RunResult:
    """Ingest all data for a single source (ncr or va)."""
    t0 = time.time()
    try:
        log.info("Ingesting cooperative extension for source '%s'", name)

        client = CensusClient()
        parts = []

        log.info("Ingesting perc_male from ACS S0101")
        parts.append(ingest_perc_male(client, source_cfg))

        log.info("Ingesting children raised by grandparents from ACS B10001")
        parts.append(ingest_children_gp(client, source_cfg))

        log.info("Ingesting County Health Rankings")
        parts.append(
            ingest_chr(
                source_cfg["county_health_rankings"],
                working_dir=TOPIC_DIR / "data" / "working",
                state_fips_prefix="51",
            )
        )

        result = pd.concat([p for p in parts if not p.empty], ignore_index=True)

        out_dir = TOPIC_DIR / out_cfg["path"]
        out_dir.mkdir(parents=True, exist_ok=True)
        states = resolve_states(source_cfg)
        auto_name = build_file_name(
            df=result,
            states=states,
            years=source_cfg["perc_male"].get("years"),
            source_type=source_cfg.get("type"),
            title=title,
        )
        filename = f"{auto_name}.csv.xz" if auto_name else out_cfg["filename"]
        out_path = write_data(
            result,
            out_dir / filename,
            census_standardize=out_cfg.get("standardize", False),
            measure_info=MEASURE_INFO if MEASURE_INFO.exists() else None,
        )
        log.info("Wrote %d rows to %s", len(result), out_path)

        return RunResult(
            success=True,
            rows=len(result),
            output_path=str(out_path),
            duration_sec=time.time() - t0,
        )
    except Exception as e:
        log.error(
            "Ingest failed for source '%s': %s", name, e, exc_info=True,
        )
        return RunResult(
            success=False,
            error=str(e),
            duration_sec=time.time() - t0,
        )


def run() -> list[RunResult]:
    config = load_config()
    out_cfg = config["output"]
    sources = config.get("sources")
    if sources is None:
        sources = {"default": config["source"]}

    return [
        run_source(name, source_cfg, out_cfg, config.get("name"))
        for name, source_cfg in sources.items()
    ]


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
