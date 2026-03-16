"""Ingest prenatal care adequacy data (Kotelchuck Index / APNCU).

Two data sources, combined:

1. **NCHS Natality microdata** (2014-2020): Individual birth records with exact
   month prenatal care began, number of visits, and gestational age. Covers all
   VA counties with no suppression. Exact Kotelchuck computation.

2. **CDC WONDER Natality Expanded** (D149, 2016-2024): Aggregated data queried
   as County × Trimester Prenatal Care Began. Only 5 cells per county so minimal
   suppression — most VA counties appear. Used as a trend proxy for 2021-2024.

For 2021-2024, each county's 2020 microdata Kotelchuck proportions are projected
forward using the year-over-year change in "% births with 1st trimester care"
from WONDER as a scaling signal. Counties without WONDER trend data use the
statewide VA trend.

Output is long-format (geoid, year, measure, value, moe, region_type).
"""

from __future__ import annotations

import csv
import gzip
import re
import subprocess
import time
from collections import Counter, defaultdict
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
ORIGINAL_DIR = TOPIC_DIR / "data/original"

log = get_logger("prenatal_care.ingest")

WONDER_URL = "https://wonder.cdc.gov/controller/datarequest/D149"
QUERY_DELAY_SEC = 5

# Years covered by each source
MICRODATA_YEARS = list(range(2014, 2021))  # 2014-2020
WONDER_YEARS = list(range(2016, 2025))  # 2016-2024
PROJECTION_YEARS = list(range(2021, 2025))  # 2021-2024

CATEGORIES = ["inadequate", "intermediate", "adequate", "adequateplus"]


# ---------------------------------------------------------------------------
# Kotelchuck Index computation
# ---------------------------------------------------------------------------


def kotelchuck_category(month: int, visits: int, gest: int) -> str | None:
    """Classify a birth into Kotelchuck APNCU categories.

    Parameters
    ----------
    month : Month prenatal care began (0=no care, 1-10, 99=unknown)
    visits : Number of prenatal visits (0-98, 99=unknown)
    gest : Gestational age in weeks

    Returns one of: inadequate, intermediate, adequate, adequateplus, or None.
    """
    if month in (98, 99) or visits in (98, 99) or gest in (98, 99):
        return None

    # No care or late care (month 5+) is always inadequate
    if month == 0 or month >= 5:
        return "inadequate"

    # Compute expected visits (ACOG schedule)
    if gest >= 28:
        v1 = 7 - (month - 1)
    else:
        v1 = round(gest / 4) - (month - 1)

    v2 = 4 if gest >= 36 else (round((gest - 28) / 2) if gest > 28 else 0)
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


# ---------------------------------------------------------------------------
# NCHS Microdata processing (2014-2020)
# ---------------------------------------------------------------------------


def _open_natal_file(path: Path):
    """Open a natal data file (.csv.gz or .csv.xz)."""
    if path.name.endswith(".csv.xz"):
        import lzma

        return lzma.open(path, "rt")

    with gzip.open(path, "rb") as f:
        header = f.read(6)

    # Check for xz magic bytes inside gzip (double-compressed legacy files)
    if header[:5] == b"\xfd7zXZ\x00":
        proc = subprocess.Popen(
            ["bash", "-c", f"gzip -dc '{path}' | xz -dc"],
            stdout=subprocess.PIPE,
            text=True,
        )
        return proc.stdout

    return gzip.open(path, "rt")


def _find_natal_file(year: int) -> Path | None:
    """Find the best natal microdata file for a given year."""
    candidates = sorted(
        list(ORIGINAL_DIR.glob(f"natal_{year}*.csv.gz"))
        + list(ORIGINAL_DIR.glob(f"natal_{year}*.csv.xz"))
    )
    if not candidates:
        return None
    # Prefer .csv.xz, then non-_init .csv.gz, then first available
    for c in candidates:
        if c.name.endswith(".csv.xz") and "_init" not in c.name:
            return c
    for c in candidates:
        if "_init" not in c.name:
            return c
    return candidates[0]


# Map of state abbreviation → FIPS code
STATE_FIPS = {"VA": "51", "MD": "24", "DC": "11"}


def ingest_microdata(states: list[str] | None = None) -> pd.DataFrame:
    """Compute exact Kotelchuck proportions from NCHS natality microdata.

    Parameters
    ----------
    states : List of state abbreviations to include (e.g. ["VA", "MD", "DC"]).
             Defaults to ["VA"] if not specified.

    Returns DataFrame with columns:
        geoid, year, measure, value, moe, region_type, data_method
    """
    if states is None:
        states = ["VA"]
    state_set = set(states)

    all_records = []

    for year in MICRODATA_YEARS:
        path = _find_natal_file(year)
        if not path:
            log.warning("No microdata file for %d", year)
            continue

        log.info("Processing microdata: %s (states: %s)", path.name, states)
        county_cats: dict[str, Counter] = defaultdict(Counter)

        f = _open_natal_file(path)
        try:
            reader = csv.DictReader(f)
            for row in reader:
                # Use mother's residence state (not occurrence state)
                mrstate = row.get("MRSTATEPSTL", "")
                if mrstate not in state_set:
                    continue

                state_fips = STATE_FIPS.get(mrstate)
                if not state_fips:
                    continue

                try:
                    county_fips = row["MRCNTYFIPS"].strip()
                    precare = int(row["PRECARE"])
                    previs = int(row["PREVIS"])
                    # COMBGEST column name varies across years
                    combgest_raw = (
                        row.get("COMBGEST ")
                        or row.get("COMBGEST.")
                        or row.get("COMBGEST", "")
                    )
                    combgest = int(combgest_raw.strip())
                except (ValueError, KeyError):
                    continue

                cat = kotelchuck_category(precare, previs, combgest)
                if cat:
                    geoid = f"{state_fips}{county_fips.zfill(3)}"
                    county_cats[geoid][cat] += 1
        finally:
            f.close()

        # Convert to long format
        for geoid, cats in county_cats.items():
            if geoid.endswith("999"):
                continue
            total = sum(cats.values())
            if total < 10:
                continue

            all_records.append(
                {
                    "geoid": geoid,
                    "year": year,
                    "measure": "total",
                    "value": total,
                }
            )
            for cat in CATEGORIES:
                count = cats.get(cat, 0)
                all_records.append(
                    {
                        "geoid": geoid,
                        "year": year,
                        "measure": cat,
                        "value": count,
                    }
                )
                all_records.append(
                    {
                        "geoid": geoid,
                        "year": year,
                        "measure": f"{cat}_pc",
                        "value": round(count / total, 4),
                    }
                )

        n_counties = len(county_cats)
        log.info("  %d: %d counties", year, n_counties)

    df = pd.DataFrame(all_records)
    if not df.empty:
        df["moe"] = pd.NA
        df["region_type"] = "county"
        df["data_method"] = "observed"
    return df


def compute_microdata_trimester(
    states: list[str] | None = None,
) -> pd.DataFrame:
    """Compute % 1st trimester care per county-year from microdata.

    Used to validate WONDER trimester data during the overlap period.

    Returns DataFrame: geoid, year, tri1_pct
    """
    if states is None:
        states = ["VA"]
    state_set = set(states)
    records = []

    for year in MICRODATA_YEARS:
        path = _find_natal_file(year)
        if not path:
            continue

        county_tri: dict[str, list[int]] = defaultdict(lambda: [0, 0])

        f = _open_natal_file(path)
        try:
            reader = csv.DictReader(f)
            for row in reader:
                # Use mother's residence state (not occurrence state)
                mrstate = row.get("MRSTATEPSTL", "")
                if mrstate not in state_set:
                    continue

                state_fips = STATE_FIPS.get(mrstate)
                if not state_fips:
                    continue

                try:
                    county_fips = row["MRCNTYFIPS"].strip()
                    precare5 = int(row["PRECARE5"])
                except (ValueError, KeyError):
                    continue

                if precare5 == 5:  # unknown
                    continue

                geoid = f"{state_fips}{county_fips.zfill(3)}"
                county_tri[geoid][1] += 1
                if precare5 == 1:  # 1st trimester
                    county_tri[geoid][0] += 1
        finally:
            f.close()

        for geoid, (tri1, total) in county_tri.items():
            if total < 10 or geoid.endswith("999"):
                continue
            records.append(
                {"geoid": geoid, "year": year, "tri1_pct": tri1 / total}
            )

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# WONDER session and queries (for trimester trends 2016-2024)
# ---------------------------------------------------------------------------


class _FormParser(HTMLParser):
    """Extract default hidden/radio/select values from WONDER request form."""

    def __init__(self) -> None:
        super().__init__()
        self.inputs: dict[str, str] = {}
        self.selects: dict[str, list[str]] = {}
        self._current_select: str | None = None
        self._selected_options: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        d = dict(attrs)
        if tag == "input":
            name = d.get("name", "")
            if not name or name.startswith("finder-action") or name.startswith(
                "tab-"
            ):
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
            headers={
                "User-Agent": "Mozilla/5.0 (research; prenatal care adequacy)"
            },
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

    def query_trimester(self, state_fips: list[str], year: int) -> str:
        """Query County × Trimester for a state/year, return TSV.

        Uses D149.V63 (Trimester) instead of D149.V8 (Month) to minimize
        the number of cells per county and reduce WONDER suppression.
        """
        if not self._base_url:
            raise RuntimeError("Call connect() first")

        query = dict(self._defaults)

        # Group by: County × Trimester Prenatal Care Began
        query["B_1"] = "D149.V21-level2"  # County of Residence
        query["B_2"] = "D149.V63"  # Trimester Prenatal Care Began
        query["B_3"] = "*None*"
        query["B_4"] = "*None*"
        query["B_5"] = "*None*"

        # Enable trimester radio button
        query["O_prenatal"] = "D149.V63"  # Trimester (not Month)

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

        # Submit
        query["action-Send"] = "Send"
        query["stage"] = "request"
        query.pop("action-Reset", None)
        query.pop("action-Save", None)

        resp = self._client.post(self._base_url, data=query)
        log.debug(
            "Trimester query %s/%d: status %d",
            state_fips,
            year,
            resp.status_code,
        )

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


def parse_trimester_tsv(tsv_data: str) -> pd.DataFrame:
    """Parse WONDER trimester TSV into (county_fips, trimester, births)."""
    lines = tsv_data.split("\n")

    notes_start = len(lines)
    for i, line in enumerate(lines):
        if line.startswith('"---'):
            notes_start = i
            break

    data_lines = [l for l in lines[1:notes_start] if l.strip()]
    if not data_lines:
        return pd.DataFrame(columns=["county_fips", "trimester", "births"])

    reader = csv.reader(
        StringIO("\n".join([lines[0]] + data_lines)), delimiter="\t"
    )
    _header = next(reader)

    records = []
    for row in reader:
        if len(row) < 6:
            continue
        county_fips = row[2]
        trimester_label = row[3]  # e.g. "1st trimester"
        births_str = row[5]

        if births_str == "Suppressed" or not births_str.strip():
            continue
        try:
            births = int(births_str.replace(",", ""))
        except ValueError:
            continue
        if births == 0:
            continue

        records.append(
            {
                "county_fips": county_fips,
                "trimester": trimester_label.strip().lower(),
                "births": births,
            }
        )

    return pd.DataFrame(records)


def query_wonder_trimester_trends(
    state_fips_list: list[str],
) -> pd.DataFrame:
    """Query WONDER for County × Trimester data, compute % 1st trimester.

    Returns DataFrame: geoid, year, tri1_pct
    """
    session = WonderSession()
    session.connect()

    records = []
    for year in WONDER_YEARS:
        for fips in state_fips_list:
            log.info("WONDER trimester query: state=%s year=%d", fips, year)
            tsv = session.query_trimester([fips], year)
            df = parse_trimester_tsv(tsv)

            if df.empty:
                log.warning("  No trimester data for %s/%d", fips, year)
                time.sleep(QUERY_DELAY_SEC)
                continue

            # Compute % 1st trimester per county
            for county, grp in df.groupby("county_fips"):
                total = grp["births"].sum()
                tri1 = grp.loc[
                    grp["trimester"].str.contains("1st"), "births"
                ].sum()

                if total < 10:
                    continue

                records.append(
                    {
                        "geoid": county,
                        "year": year,
                        "tri1_pct": tri1 / total,
                    }
                )

            time.sleep(QUERY_DELAY_SEC)

    session.close()
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Projection: apply trimester trends to 2020 baseline
# ---------------------------------------------------------------------------


def project_kotelchuck(
    microdata: pd.DataFrame,
    wonder_trends: pd.DataFrame,
) -> pd.DataFrame:
    """Project 2021-2024 Kotelchuck proportions using WONDER trimester trends.

    For each county, we take the 2020 exact Kotelchuck proportions and adjust
    them using the year-over-year change in % 1st trimester care from WONDER.

    The adjustment logic:
    - If % 1st trimester care increases by X% relative to 2020, we decrease
      inadequate_pc proportionally and redistribute to adequate/adequateplus.
    - If it decreases, we increase inadequate_pc and pull from adequate categories.
    - All proportions are bounded [0, 1] and renormalized.
    """
    # Get 2020 baseline proportions per county
    baseline = microdata[
        (microdata["year"] == 2020) & microdata["measure"].str.endswith("_pc")
    ].copy()
    baseline_wide = baseline.pivot(
        index="geoid", columns="measure", values="value"
    ).reset_index()

    if baseline_wide.empty:
        log.warning("No 2020 baseline data for projection")
        return pd.DataFrame()

    # Get 2020 trimester baseline from WONDER (or microdata if available)
    tri_2020 = wonder_trends[wonder_trends["year"] == 2020].set_index("geoid")[
        "tri1_pct"
    ]

    # Statewide 2020 fallback
    state_tri = wonder_trends.groupby("year")["tri1_pct"].mean()

    records = []
    for year in PROJECTION_YEARS:
        # Year-level trend from WONDER
        if year not in state_tri.index or 2020 not in state_tri.index:
            log.warning("No WONDER trend data for %d", year)
            continue

        state_ratio = state_tri[year] / state_tri[2020]

        year_trends = wonder_trends[wonder_trends["year"] == year].set_index(
            "geoid"
        )["tri1_pct"]

        for _, row in baseline_wide.iterrows():
            geoid = row["geoid"]

            # County-specific trend if available, else statewide
            if geoid in year_trends.index and geoid in tri_2020.index:
                ratio = year_trends[geoid] / tri_2020[geoid]
            else:
                ratio = state_ratio

            # Adjust proportions: more 1st-trimester care → less inadequate
            # ratio > 1 means improvement, ratio < 1 means deterioration
            inad = row.get("inadequate_pc", 0)
            inter = row.get("intermediate_pc", 0)
            adeq = row.get("adequate_pc", 0)
            adeqp = row.get("adequateplus_pc", 0)

            # Scale inadequate inversely with trimester improvement
            # Scale adequate/adequateplus proportionally
            if ratio != 0:
                inad_new = inad / ratio
                inter_new = inter / ratio
                adeq_new = adeq * ratio
                adeqp_new = adeqp * ratio
            else:
                inad_new, inter_new, adeq_new, adeqp_new = (
                    inad,
                    inter,
                    adeq,
                    adeqp,
                )

            # Bound and renormalize
            vals = {
                "inadequate_pc": max(0, inad_new),
                "intermediate_pc": max(0, inter_new),
                "adequate_pc": max(0, adeq_new),
                "adequateplus_pc": max(0, adeqp_new),
            }
            total = sum(vals.values())
            if total > 0:
                vals = {k: round(v / total, 4) for k, v in vals.items()}

            for measure, value in vals.items():
                records.append(
                    {
                        "geoid": geoid,
                        "year": year,
                        "measure": measure,
                        "value": value,
                        "moe": pd.NA,
                        "region_type": "county",
                        "data_method": "modeled",
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

        # Collect all unique states across sources
        all_state_fips = set()
        for source_cfg in config["sources"].values():
            all_state_fips.update(source_cfg.get("state_fips", []))

        # Reverse lookup: FIPS → abbreviation
        fips_to_abbr = {v: k for k, v in STATE_FIPS.items()}
        all_states = [fips_to_abbr[f] for f in all_state_fips if f in fips_to_abbr]

        # Step 1: Compute exact Kotelchuck from NCHS microdata (2014-2020)
        log.info("=== Step 1: NCHS microdata (2014-2020) ===")
        microdata = ingest_microdata(states=all_states)
        if microdata.empty:
            return RunResult(
                success=False,
                error="No microdata found",
                duration_sec=time.time() - t0,
            )
        n_micro = microdata["geoid"].nunique()
        log.info(
            "Microdata: %d counties, %d rows, years %s",
            n_micro,
            len(microdata),
            sorted(microdata["year"].unique()),
        )

        # Step 2: Query WONDER for trimester trends (2016-2024)
        log.info("=== Step 2: WONDER trimester trends (2016-2024) ===")
        state_fips = sorted(all_state_fips)
        wonder_trends = query_wonder_trimester_trends(list(state_fips))

        if wonder_trends.empty:
            log.warning("No WONDER trend data — outputting microdata only")
            projected = pd.DataFrame()
        else:
            n_wonder = wonder_trends["geoid"].nunique()
            log.info(
                "WONDER trends: %d counties, years %s",
                n_wonder,
                sorted(wonder_trends["year"].unique()),
            )

            # Step 3: Project 2021-2024
            log.info("=== Step 3: Projecting 2021-2024 ===")
            projected = project_kotelchuck(microdata, wonder_trends)
            if not projected.empty:
                n_proj = projected["geoid"].nunique()
                log.info(
                    "Projected: %d counties × %d years",
                    n_proj,
                    len(PROJECTION_YEARS),
                )

        # Step 4: Combine and write output
        log.info("=== Step 4: Writing output ===")
        parts = [microdata]
        if not projected.empty:
            parts.append(projected)

        df = pd.concat(parts, ignore_index=True)
        df = df[
            ["geoid", "year", "measure", "value", "moe", "region_type", "data_method"]
        ]

        # Write per-source output
        for source_name, source_cfg in config["sources"].items():
            coverage = source_cfg.get("profile", source_name).lower()
            source_fips_set = set(source_cfg["state_fips"])

            mask = df["geoid"].str[:2].isin(source_fips_set)
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
