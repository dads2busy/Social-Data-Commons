"""Ingest prenatal care adequacy data from CDC WONDER Natality database.

Queries the WONDER Natality Expanded (D149) web form for county-level data
grouped by Month Prenatal Care Began × Number of Prenatal Visits, then
computes the Kotelchuck Index (APNCU) for each county.

WONDER suppresses counties with insufficient births (< ~1,000/year), so
only large counties appear. All NCR counties except the smallest VA
independent cities are covered.

Output is long-format (geoid, year, measure, value, moe, region_type).
"""

from __future__ import annotations

import csv
import re
import time
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path

import httpx
import pandas as pd
import yaml
from sdc_core.io import write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name
from sdc_core.result import RunResult

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"
CACHE_DIR = TOPIC_DIR / "data/original"

log = get_logger("prenatal_care.ingest")

WONDER_URL = "https://wonder.cdc.gov/controller/datarequest/D149"

# D149 covers 2016-2024; years available
YEARS = list(range(2016, 2025))

# Assumed gestational age (weeks) for Kotelchuck formula.
# ~90% of births are 37-42 weeks; using 39 as median.
# Eliminates a dimension from the WONDER query (reduces suppression).
GEST_ASSUMED = 39

# Query rate limit: WONDER requests max 1 query per minute
QUERY_DELAY_SEC = 5


# ---------------------------------------------------------------------------
# WONDER session and form parsing
# ---------------------------------------------------------------------------


class _FormParser(HTMLParser):
    """Extract default hidden/radio/select values from WONDER request form."""

    def __init__(self) -> None:
        super().__init__()
        self.inputs: dict[str, str] = {}
        self.selects: dict[str, list[str]] = {}
        self._current_select: str | None = None
        self._selected_options: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = dict(attrs)
        if tag == "input":
            name = d.get("name", "")
            if not name or name.startswith("finder-action") or name.startswith("tab-"):
                return
            typ = d.get("type", "text")
            if typ == "radio" and "checked" in d:
                self.inputs[name] = d.get("value", "")
            elif typ == "hidden":
                self.inputs[name] = d.get("value", "")
        elif tag == "select":
            self._current_select = d.get("name", "")
            self._selected_options = []
        elif tag == "option" and self._current_select:
            if "selected" in d:
                self._selected_options.append(d.get("value", ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "select" and self._current_select:
            if self._selected_options:
                self.selects[self._current_select] = self._selected_options
            self._current_select = None


class WonderSession:
    """Manages a CDC WONDER web session for the Natality Expanded database."""

    def __init__(self) -> None:
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=600,
            headers={"User-Agent": "Mozilla/5.0 (research; prenatal care adequacy)"},
        )
        self._base_url: str | None = None
        self._defaults: dict = {}

    def connect(self) -> None:
        """Agree to terms and parse form defaults."""
        resp = self._client.post(
            WONDER_URL,
            data={"stage": "about", "action-I Agree": "I Agree"},
        )
        resp.raise_for_status()

        m = re.search(r"jsessionid=([A-F0-9]+)", resp.text)
        if not m:
            raise RuntimeError("Failed to obtain WONDER session ID")

        jsessionid = m.group(1)
        self._base_url = f"{WONDER_URL};jsessionid={jsessionid}"
        log.info("WONDER session: %s", jsessionid)

        parser = _FormParser()
        parser.feed(resp.text)
        self._defaults = dict(parser.inputs)
        for k, v in parser.selects.items():
            self._defaults[k] = v

    def query(self, state_fips: list[str], year: int) -> str:
        """Query county × month × visits for a state/year, return TSV data."""
        if not self._base_url:
            raise RuntimeError("Call connect() first")

        query = dict(self._defaults)

        # Group by: County × Month Prenatal Care Began × Number of Visits
        query["B_1"] = "D149.V21-level2"  # County of Residence
        query["B_2"] = "D149.V8"  # Month Prenatal Care Began
        query["B_3"] = "D149.V64"  # Number of Prenatal Visits
        query["B_4"] = "*None*"
        query["B_5"] = "*None*"

        # Enable radio buttons for our variables
        query["O_prenatal"] = "D149.V8"  # Month (not Trimester)
        query["O_prenatal2"] = "D149.V64"  # Raw visits (not Recode)

        # State filter
        query["F_D149.V21"] = state_fips
        query["I_D149.V21"] = " ".join(state_fips)

        # Year filter
        query["V_D149.V20"] = [str(year)]

        # Output settings
        query["O_show_suppressed"] = "true"
        query["O_show_zeros"] = "false"
        query["O_show_totals"] = "false"
        query["O_precision"] = "0"

        # Submit query
        query["action-Send"] = "Send"
        query["stage"] = "request"
        query.pop("action-Reset", None)
        query.pop("action-Save", None)

        resp = self._client.post(self._base_url, data=query)
        log.debug("Query %s/%d: status %d", state_fips, year, resp.status_code)

        # Export as TSV
        query.pop("action-Send", None)
        query["action-Export"] = "Download"
        query["O_export-format"] = "tsv"
        query["stage"] = "results"
        query["O_change_action-Send-Export Results"] = (
            "O_change_action-Send-Export Results"
        )

        resp2 = self._client.post(self._base_url, data=query)
        return resp2.text

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# Kotelchuck Index computation
# ---------------------------------------------------------------------------


def kotelchuck_category(month: int, visits: int, gest: int = GEST_ASSUMED) -> str | None:
    """Classify a birth into Kotelchuck APNCU categories.

    Parameters
    ----------
    month : Month prenatal care began (0=no care, 1-10, 99=unknown)
    visits : Number of prenatal visits (0-98, 99=unknown)
    gest : Gestational age in weeks

    Returns one of: inadequate, intermediate, adequate, adequateplus, or None.
    """
    if month == 99 or visits == 99 or month == 98 or visits == 98:
        return None

    # No care or late care (month 5+) is always inadequate
    if month == 0 or month >= 5:
        return "inadequate"

    # Compute ideal visits (ACOG schedule)
    if gest >= 28:
        v1 = 7 - (month - 1)
    else:
        v1 = round(gest / 4) - (month - 1)

    if gest >= 36:
        v2 = 4
    elif gest > 28:
        v2 = round((gest - 28) / 2)
    else:
        v2 = 0

    v3 = max(0, gest - 36)
    ideal = v1 + v2 + v3

    if ideal <= 0:
        return None

    ratio = visits / ideal
    if ratio < 0.5:
        return "inadequate"
    elif ratio < 0.8:
        return "intermediate"
    elif ratio < 1.1:
        return "adequate"
    else:
        return "adequateplus"


def parse_wonder_tsv(tsv_data: str) -> pd.DataFrame:
    """Parse WONDER TSV export into a DataFrame of (county_fips, month, visits, births)."""
    lines = tsv_data.split("\n")

    # Find notes section
    notes_start = len(lines)
    for i, line in enumerate(lines):
        if line.startswith('"---'):
            notes_start = i
            break

    data_lines = [l for l in lines[1:notes_start] if l.strip()]
    if not data_lines:
        return pd.DataFrame(columns=["county_fips", "month", "visits", "births"])

    reader = csv.reader(
        StringIO("\n".join([lines[0]] + data_lines)), delimiter="\t"
    )
    _header = next(reader)

    records = []
    for row in reader:
        if len(row) < 8:
            continue
        county_fips = row[2]
        month_code = row[4]
        visits_code = row[6]
        births_str = row[7]

        if births_str == "Suppressed" or not births_str.strip():
            continue
        try:
            births = int(births_str.replace(",", ""))
        except ValueError:
            continue
        if births == 0:
            continue

        try:
            month = int(month_code)
            visits = int(visits_code)
        except ValueError:
            continue

        records.append(
            {
                "county_fips": county_fips,
                "month": month,
                "visits": visits,
                "births": births,
            }
        )

    return pd.DataFrame(records)


def compute_kotelchuck(df: pd.DataFrame) -> pd.DataFrame:
    """Compute Kotelchuck categories per county from birth-level WONDER data.

    Input: DataFrame with (county_fips, month, visits, births).
    Output: DataFrame with (geoid, measure, value) for counts and proportions.
    """
    # Classify each row
    df = df.copy()
    df["category"] = df.apply(
        lambda r: kotelchuck_category(r["month"], r["visits"]), axis=1
    )

    # Drop unclassifiable
    df = df.dropna(subset=["category"])

    # Aggregate: births per county × category
    agg = df.groupby(["county_fips", "category"])["births"].sum().reset_index()
    totals = df.groupby("county_fips")["births"].sum().reset_index()
    totals.columns = ["county_fips", "total"]

    agg = agg.merge(totals, on="county_fips")
    agg["proportion"] = agg["births"] / agg["total"]

    # Build long-format output
    records = []
    for fips, grp in agg.groupby("county_fips"):
        # Skip "unidentified" counties
        if fips.endswith("999"):
            continue

        total = grp["total"].iloc[0]
        records.append({"geoid": fips, "measure": "total", "value": total})

        for _, row in grp.iterrows():
            cat = row["category"]
            records.append({"geoid": fips, "measure": cat, "value": row["births"]})
            records.append(
                {
                    "geoid": fips,
                    "measure": f"{cat}_pc",
                    "value": round(row["proportion"], 4),
                }
            )

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def run() -> RunResult:
    t0 = time.time()
    try:
        config = load_config()

        session = WonderSession()
        session.connect()

        all_parts: list[pd.DataFrame] = []

        for source_name, source_cfg in config["sources"].items():
            state_fips = source_cfg["state_fips"]
            years = source_cfg.get("years", YEARS)

            for year in years:
                log.info("Querying %s/%d (states: %s)...", source_name, year, state_fips)

                # Query each state separately (multi-state queries sometimes fail)
                year_frames = []
                for fips in state_fips:
                    tsv = session.query([fips], year)
                    df = parse_wonder_tsv(tsv)
                    if not df.empty:
                        year_frames.append(df)
                    time.sleep(QUERY_DELAY_SEC)

                if not year_frames:
                    log.warning("  No data for %s/%d", source_name, year)
                    continue

                combined = pd.concat(year_frames, ignore_index=True)
                result = compute_kotelchuck(combined)
                result["year"] = year
                result["region_type"] = "county"
                result["moe"] = pd.NA

                n_counties = result["geoid"].nunique()
                log.info(
                    "  %s/%d: %d counties, %d rows",
                    source_name, year, n_counties, len(result),
                )
                all_parts.append(result)

        session.close()

        if not all_parts:
            return RunResult(
                success=False,
                error="No data retrieved from WONDER",
                duration_sec=time.time() - t0,
            )

        df = pd.concat(all_parts, ignore_index=True)
        df = df[["geoid", "year", "measure", "value", "moe", "region_type"]]

        # Write per-source output
        for source_name, source_cfg in config["sources"].items():
            coverage = source_cfg.get("profile", source_name).lower()
            source_fips = set(source_cfg["state_fips"])

            mask = df["geoid"].str[:2].isin(source_fips)
            subset = df[mask].copy()

            if subset.empty:
                log.warning("No data for %s", source_name)
                continue

            source_years = sorted(subset["year"].unique().tolist())
            auto_name = build_file_name(
                df=subset,
                coverage_area=coverage,
                years=source_years,
                source_type=source_cfg.get("type", "nchs"),
                title="kotelchuck",
            )
            out_path = write_data(
                subset, DIST_DIR / f"{auto_name}.csv.xz"
            )
            log.info("Wrote %s: %d rows", out_path.name, len(subset))

        return RunResult(
            success=True,
            rows=len(df),
            output_path=str(DIST_DIR),
            duration_sec=time.time() - t0,
        )

    except Exception as e:
        log.error("Ingest failed: %s", e, exc_info=True)
        return RunResult(
            success=False,
            error=str(e),
            duration_sec=time.time() - t0,
        )


if __name__ == "__main__":
    result = run()
    log.info("Result: %s", result.to_dict())
    if not result.success:
        raise SystemExit(1)
