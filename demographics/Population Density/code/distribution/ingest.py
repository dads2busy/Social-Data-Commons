"""Ingest population density data from ACS + TIGER land area.

Configuration is read from population_density/pipeline.yaml.
"""

import time
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd
import yaml
from sdc_core.census import CensusClient
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.profiles import resolve_states
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
log = get_logger("population_density.ingest")

TIGER_URLS = (
    "https://tigerweb.geo.census.gov/arcrest/tigerweb/tigerWMS_ACS2020/MapServer/{layer}/query",
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2020/MapServer/{layer}/query",
)
TIGER_LINE_YEAR = 2023
TIGER_LINE_BASE = f"https://www2.census.gov/geo/tiger/TIGER{TIGER_LINE_YEAR}"
CACHE_DIR = TOPIC_DIR / "data" / "working" / "tiger_line_cache"
SQ_METERS_PER_SQ_MILE = 2_589_988.11


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def _fetch_land_area_tigerweb(tiger_config: dict) -> pd.DataFrame:
    """Fetch land area for block groups, tracts, and counties from TIGERweb API."""
    state_fips = tiger_config["state_fips"]
    layers = [
        (tiger_config["tract_layer"], "tract"),
        (tiger_config["block_group_layer"], "block_group"),
        (tiger_config["county_layer"], "county"),
    ]

    records = []
    for layer, geo_type in layers:
        log.info("Fetching %s land area from TIGERweb (layer %d)", geo_type, layer)
        params = {
            "where": f"STATE='{state_fips}'",
            "outFields": "GEOID,AREALAND",
            "returnGeometry": "false",
            "f": "json",
        }
        last_error = None
        for base_url in TIGER_URLS:
            resp = httpx.get(base_url.format(layer=layer), params=params, timeout=60)
            if resp.status_code != 200:
                log.warning(
                    "TIGERweb request failed (status=%s) url=%s",
                    resp.status_code,
                    base_url,
                )
                last_error = RuntimeError(f"status {resp.status_code}")
                continue
            try:
                data = resp.json()
            except ValueError:
                log.error(
                    "TIGERweb response not JSON (status=%s) url=%s body=%s",
                    resp.status_code,
                    base_url,
                    resp.text[:500],
                )
                last_error = ValueError("non-JSON response")
                continue
            for feat in data.get("features", []):
                attrs = feat["attributes"]
                records.append(
                    {
                        "geoid": str(attrs["GEOID"]),
                        "land_area_sqmi": attrs["AREALAND"] / SQ_METERS_PER_SQ_MILE,
                        "region_type": geo_type,
                    }
                )
            break
        else:
            raise RuntimeError(
                f"TIGERweb failed for {geo_type} layer {layer}: {last_error}"
            )

    log.info("Fetched land area for %d geographies from TIGERweb", len(records))
    return pd.DataFrame(records)


def _fetch_land_area_tigerline(tiger_config: dict) -> pd.DataFrame:
    """Fetch land area from TIGER/Line shapefiles as a fallback."""
    state_fips = tiger_config["state_fips"]
    urls = {
        "tract": f"{TIGER_LINE_BASE}/TRACT/tl_{TIGER_LINE_YEAR}_{state_fips}_tract.zip",
        "block_group": f"{TIGER_LINE_BASE}/BG/tl_{TIGER_LINE_YEAR}_{state_fips}_bg.zip",
        "county": f"{TIGER_LINE_BASE}/COUNTY/tl_{TIGER_LINE_YEAR}_us_county.zip",
    }

    frames = []
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for geo_type, url in urls.items():
        log.info("Fetching %s land area from TIGER/Line (%s)", geo_type, url)
        local_path = CACHE_DIR / Path(url).name
        if local_path.exists():
            log.info("Using cached TIGER/Line zip for %s (%s)", geo_type, local_path)
        else:
            log.info("Downloading TIGER/Line zip for %s (%s)", geo_type, url)
            resp = httpx.get(url, timeout=120)
            resp.raise_for_status()
            local_path.write_bytes(resp.content)
        gdf = gpd.read_file(local_path)
        if "STATEFP" in gdf.columns:
            gdf = gdf[gdf["STATEFP"] == state_fips]
        gdf = gdf[["GEOID", "ALAND"]].copy()
        gdf["land_area_sqmi"] = gdf["ALAND"] / SQ_METERS_PER_SQ_MILE
        gdf["region_type"] = geo_type
        frames.append(
            gdf[["GEOID", "land_area_sqmi", "region_type"]].rename(
                columns={"GEOID": "geoid"}
            )
        )

    result = pd.concat(frames, ignore_index=True)
    log.info("Fetched land area for %d geographies from TIGER/Line", len(result))
    return result


def fetch_land_area(tiger_config: dict) -> pd.DataFrame:
    """Fetch land area for block groups, tracts, and counties with fallback."""
    try:
        df = _fetch_land_area_tigerweb(tiger_config)
        if df.empty:
            raise RuntimeError("TIGERweb returned no land-area records")
        return df
    except Exception as e:
        log.warning(
            "TIGERweb land area fetch failed: %s. Falling back to TIGER/Line shapefiles.",
            e,
        )
        return _fetch_land_area_tigerline(tiger_config)


def run_source(
    name: str, src: dict, out_dir: Path, tiger: dict, standardize: bool
) -> RunResult:
    t0 = time.time()
    try:
        log.info("Ingesting source '%s' (profile=%s)", name, src.get("profile"))

        client = CensusClient()
        pop = client.get_acs_multi(
            variables=src["variables"],
            years=src["years"],
            geographies=src["geographies"],
            profile=src.get("profile"),
            states=src.get("states"),
            cache_dir=TOPIC_DIR / "data/working/acs_cache",
        )
        log.info("Fetched %d raw rows for '%s'", len(pop), name)

        area = fetch_land_area(tiger)

        pop = pop.merge(area[["geoid", "land_area_sqmi"]], on="geoid", how="left")
        pop["value"] = pop["total_pop"] / pop["land_area_sqmi"]
        pop["measure"] = "population_density"
        pop["moe"] = pd.NA

        result = pop[["geoid", "year", "measure", "value", "moe", "region_type"]]
        result = result.dropna(subset=["value"])

        states = resolve_states(src)
        auto_name = build_file_name(
            df=result,
            states=states,
            years=src.get("years"),
            source_type=src.get("type"),
            title="population_density",
        )
        filename = f"{auto_name}.csv.xz"
        out_path = write_data(
            result,
            out_dir / filename,
            census_standardize=standardize,
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
            "Population density ingest failed for source '%s': %s",
            name,
            e,
            exc_info=True,
        )
        return RunResult(
            success=False,
            error=str(e),
            duration_sec=time.time() - t0,
        )


def run() -> list[RunResult]:
    config = load_config()
    tiger = config["tiger"]
    out = config["output"]
    out_dir = TOPIC_DIR / out["path"]
    standardize = out.get("standardize", False)

    sources = config.get("sources")
    if sources is None:
        sources = {"default": config["source"]}

    results = []
    for name, src in sources.items():
        results.append(run_source(name, src, out_dir, tiger, standardize))
    return results


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
