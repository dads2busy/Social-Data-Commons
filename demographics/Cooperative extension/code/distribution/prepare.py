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

import pandas as pd
import yaml
from sdc_core.census import CensusClient
from sdc_core.geo import aggregate_with_crosswalk
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.profiles import resolve_states
from sdc_core.result import RunResult
from sdc_core.sources.chr import ingest_chr
from tqdm import tqdm

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("cooperative_extension.prepare")


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



def run_source(
    name: str,
    source_cfg: dict,
    out: dict,
    title: str | None,
) -> RunResult:
    t0 = time.time()
    try:
        log.info("Starting cooperative extension prepare for source '%s'", name)

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

        out_dir = TOPIC_DIR / out["path"]
        states = resolve_states(source_cfg)
        auto_name = build_file_name(
            df=result,
            states=states,
            years=source_cfg["perc_male"].get("years"),
            source_type=source_cfg.get("type"),
            title=title,
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
        log.error(
            "Cooperative extension prepare failed for source '%s': %s",
            name,
            e,
            exc_info=True,
        )
        return RunResult(
            success=False,
            error=str(e),
            duration_sec=time.time() - t0,
        )


def _build_va_dashboard(source_path: Path, config: dict) -> None:
    """Aggregate county rows to health districts, then reformat for VA dashboard."""
    log.info("Reading combined source for VA dashboard: %s", source_path)
    df = read_data(source_path)

    counties = df[df["region_type"] == "county"].copy()
    non_counties = df[df["region_type"] != "county"].copy()

    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})

    # All cooperative extension measures are percentages — aggregate with mean
    hd = aggregate_with_crosswalk(
        counties,
        crosswalk=xwalk,
        source_col="ct_geoid",
        target_col="hd_geoid",
        method="mean",
        value_col="value",
        target_region_type="health_district",
    )
    hd["moe"] = pd.NA

    combined = pd.concat([non_counties, counties, hd], ignore_index=True)
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

    combined_path = write_data(combined, source_path)
    log.info("Wrote %d rows (with health districts) to %s", len(combined), combined_path)

    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None
    paths = data_reformat_for_site(
        source_path=combined_path,
        output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
        levels=["health_district", "county", "tract"],
        coverage_area="va",
        data_source="mixed",
        title="cooperative_extension",
        measure_info_path=measure_info,
    )
    for p in paths:
        log.info("Wrote %s", p)


def run(pipeline=None) -> RunResult:
    t0 = time.time()
    config = load_config()
    out = config["output"]
    sources = config.get("sources")
    if sources is None:
        sources = {"default": config["source"]}

    results = []
    for name, source_cfg in sources.items():
        results.append(run_source(name, source_cfg, out, config.get("name")))

    success = all(r.success for r in results)
    rows = sum(r.rows or 0 for r in results)
    output_path = next(
        (r.output_path for r in reversed(results) if r.output_path), None
    )

    if success and output_path:
        try:
            _build_va_dashboard(Path(output_path), config)
        except Exception as e:
            log.error("VA dashboard reformat failed: %s", e, exc_info=True)
            success = False

    return RunResult(
        success=success,
        rows=rows,
        output_path=output_path,
        error=None if success else "One or more sources failed",
        duration_sec=time.time() - t0,
    )


if __name__ == "__main__":
    result = run()
    if not result.success:
        raise SystemExit(1)
