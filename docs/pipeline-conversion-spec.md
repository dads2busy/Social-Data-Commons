# SDC Pipeline Conversion Spec

A guide for converting dataset pipelines from R to Python, following the patterns established in the `demographics/` and `education/` topics.

---

## Completion gate

**A pipeline conversion is incomplete and must not be committed until every item below is present and verified.** Do not commit until every deliverable in this checklist is present. Verify each one explicitly before staging.

| # | Required artifact | Verify by |
|---|---|---|
| 1 | `pipeline.yaml` exists in topic directory | File exists with all sources, years, variables |
| 2 | `code/distribution/ingest.py` exists and runs | `uv run python ingest.py` exits 0, output files appear in `data/distribution/` with reasonable row counts |
| 3 | `code/distribution/prepare.py` exists and runs | `uv run python prepare.py` exits 0, per-level files appear in `dashboard_data/` |
| 4 | Validation comparison passes | Old vs new output compared, mean diff within tolerance (see section 13) |
| 5 | `docs/validation_report.md` written | File exists in topic directory documenting comparison results |
| 6 | Old R files moved to `legacy/` | `git mv` used, originals no longer in topic directory |
| 7 | Dashboard files committed | Per-level `.csv.xz` files present in `dashboard_data/{site}/` |

If a pipeline is **deferred** (fails qualification checklist in section 0), write a deferred-pipeline report instead — no code artifacts are required.

---

## 0. Dataset qualification checklist

Run through this checklist **before** starting a conversion. A single **No** answer on the required questions means the dataset is not ready to convert using this spec — investigate the blocker first or defer the dataset.

### 0.1 Data source is automatable

| Question | Required? |
|---|---|
| Can the data be fetched programmatically (Census API, HTTP download, local file read)? | **Yes** |
| If manual download is needed, is the URL stable and process documented? | **Yes** |
| Does fetching require a running external service (OSRM server, spatial database, etc.)? | Must be **No** |

> **Why this matters:** The Daycare pipeline was deferred because it requires an OSRM routing server and the R `catchment` package for a floating catchment area model. There is no Python equivalent and the server is not part of the standard dev environment.

### 0.2 The R code is a complete, production pipeline

| Question | Required? |
|---|---|
| Does the R script actually run end-to-end and produce output files? | **Yes** |
| Are the output files committed in `data/distribution/`? | **Yes** |
| Is the code generalized (not hardcoded to a single county, year, or local path)? | **Yes** |
| Is the methodology clear enough to re-implement (not just exploratory analysis)? | **Yes** |

> **Why this matters:** Some R files in the repo are incomplete explorations (e.g. Fairfax-only household simulations, half-finished PDF scrapers). Converting them would produce a pipeline that doesn't match any real data and can't be validated.

### 0.3 Output can be validated

| Question | Required? |
|---|---|
| Do reference output files exist (old R output or source data) to spot-check against? | **Yes** |
| Is the measure definition clear enough to know what "correct" looks like? | **Yes** |

### 0.4 Data source fits the long-format schema

| Question | Required? |
|---|---|
| Can the data be expressed as (geoid, year, measure, value, moe) rows? | **Yes** |
| Does each row represent a single geographic unit at a single point in time? | **Yes** |
| Is there a usable geography identifier that maps to Census FIPS codes? | **Yes** |

### 0.5 Spatial complexity

| Question | Required? |
|---|---|
| Does the pipeline require spatial joins, routing, or catchment area calculations? | Must be **No** |
| Does it require raster processing or network analysis? | Must be **No** |

If spatial operations are needed, assess whether Python equivalents (`geopandas`, `shapely`, etc.) can replace the R logic without requiring external servers. If yes, document the approach and get agreement before proceeding.

### 0.6 Quick verdict

If all required questions are **Yes** and all "Must be No" questions are **No**: proceed with the conversion.

If any required question is **No** or any "Must be No" question is **Yes**: document the blocker in the topic's README or in the deferred section of the project tracker, and do not start the conversion.

---

## 1. Goals

- Every dataset topic has a reproducible Python pipeline runnable with `uv run python <script>.py`
- All pipelines share the same long-format data schema and file naming convention
- `sdc_core` provides all shared infrastructure; pipelines contain only topic-specific logic
- Dashboard-ready output files are committed directly to the repo alongside source code

---

## 2. Repository layout

```
sdc-monorepo/
├── packages/sdc-core/           # Shared library
│   └── src/sdc_core/
│       ├── census.py            # CensusClient (ACS fetching)
│       ├── geo.py               # Aggregation, crosswalks
│       ├── io.py                # read_data, write_data, data_reformat_for_site
│       ├── naming.py            # build_file_name
│       ├── profiles.py          # NCR / VA geo profiles
│       ├── result.py            # RunResult dataclass
│       ├── log.py               # get_logger
│       └── sources/
│           └── chr.py           # County Health Rankings ingestion
│
├── demographics/
│   └── <Topic>/
│       ├── pipeline.yaml
│       ├── code/distribution/
│       │   ├── ingest.py
│       │   └── prepare.py
│       └── data/distribution/   # committed output files
│
├── education/
│   └── <Topic>/                 # same structure as demographics
│
└── dashboard_data/
    ├── virginia_public_health_data/   # per-level VA dashboard files
    └── national_capital_region_data/  # per-level NCR dashboard files
```

---

## 3. Pipeline anatomy

Every topic has exactly three files.

### 3.1 `pipeline.yaml`

Declares sources, variables, years, geographies, and crosswalk paths. No code.

**Minimal structure:**
```yaml
name: topic_name
description: "Human-readable description"

sources:
  ncr:                         # or "va", or both
    type: census_acs           # census_acs | county_health_rankings | vdoe | mixed
    profile: NCR               # NCR or VA — used by CensusClient.get_acs_multi
    years: [2010, ..., 2024]
    geographies: [tract, county]
    variables:                 # ACS variable IDs, keyed by short name
      total: "B06009_001"
      in_college: "B06009_004"

crosswalks:
  va_county_to_hd: "geographies/VA/State Geographies/Health Districts/2020/data/distribution/va_ct_to_hd_crosswalk.csv"

output:
  path: data/distribution
  standardize: true            # set true for Census tract data to standardize to 2020 boundaries
```

**For non-ACS sources** (e.g. CHR), the source block holds source-specific config under a named key:
```yaml
sources:
  va:
    type: county_health_rankings
    county_health_rankings:
      urls:
        2022: "https://..."
        2023: "https://..."
      measures:
        - name: myMeasure
          column: "Column Name"           # fixed name across all years
          # OR:
          columns:                        # name varies by year
            2022: "Old Column Name"
            2023: "New Column Name"
```

### 3.2 `ingest.py`

Fetches raw data, computes derived measures, writes one `.csv.xz` per source to `data/distribution/`.

**Responsibilities:**
- Read `pipeline.yaml`
- Fetch/parse raw data (API calls, file reads, downloads)
- Compute derived measures (ratios, weighted averages, etc.)
- Write long-format output via `write_data()`
- Return `RunResult` (or list of `RunResult`)
- Exit with code 1 on failure when run as `__main__`

**Template:**
```python
"""One-line description of what this ingests and from where."""

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

TOPIC_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = TOPIC_DIR / "data/distribution"

log = get_logger("topic_name.ingest")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def compute_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Transform wide ACS/source data to long format with measure/value/moe columns."""
    ...


def run_source(name: str, src: dict, out_dir: Path, client: CensusClient) -> RunResult:
    t0 = time.time()
    try:
        log.info("Ingesting source '%s'", name)
        df = client.get_acs_multi(
            variables=src["variables"],
            years=src["years"],
            geographies=src["geographies"],
            profile=src.get("profile"),
            states=src.get("states"),
            estimate_only=False,       # set True if MOE not needed
        )
        if df.empty:
            return RunResult(success=False, error=f"No data for '{name}'", duration_sec=time.time() - t0)

        result = compute_measures(df)

        states = resolve_states(src)
        auto_name = build_file_name(df=result, states=states, years=src.get("years"),
                                    source_type=src.get("type"), title="topic_name")
        out_path = write_data(result, out_dir / f"{auto_name}.csv.xz", census_standardize=True)
        log.info("Wrote %d rows to %s", len(result), out_path)
        return RunResult(success=True, rows=len(result), output_path=str(out_path), duration_sec=time.time() - t0)
    except Exception as e:
        log.error("Ingest failed for source '%s': %s", name, e, exc_info=True)
        return RunResult(success=False, error=str(e), duration_sec=time.time() - t0)


def run() -> list[RunResult]:
    config = load_config()
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    client = CensusClient()
    return [run_source(name, src, DIST_DIR, client) for name, src in config["sources"].items()]


if __name__ == "__main__":
    results = run()
    if any(not r.success for r in results):
        raise SystemExit(1)
```

### 3.3 `prepare.py`

Reads ingest output, aggregates counties → health districts (VA only), calls `data_reformat_for_site` to write dashboard files.

**Responsibilities:**
- Find ingest output in `data/distribution/` using a specific glob pattern
- Aggregate county rows to health districts using `aggregate_with_crosswalk`
- Write combined distribution file (county + HD + tracts) back to `data/distribution/`
- Call `data_reformat_for_site` for each dashboard (VA and/or NCR)
- Does **not** return `RunResult` — runs unconditionally, raises on failure

**Template:**
```python
"""Prepare <topic> for dashboard sites."""

from pathlib import Path

import pandas as pd
import yaml
from sdc_core.geo import aggregate_with_crosswalk
from sdc_core.io import data_reformat_for_site, read_data, write_data
from sdc_core.log import get_logger
from sdc_core.naming import build_file_name

TOPIC_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = TOPIC_DIR.parents[1]
DIST_DIR = TOPIC_DIR / "data/distribution"
MEASURE_INFO = DIST_DIR / "measure_info.json"

log = get_logger("topic_name.prepare")


def load_config() -> dict:
    with open(TOPIC_DIR / "pipeline.yaml") as f:
        return yaml.safe_load(f)


def find_source(dist_dir: Path, prefix: str) -> Path | None:
    # Pattern must match ingest output but NOT prepare output.
    # Ingest writes {prefix}_cttr_* (county+tract); prepare writes {prefix}_hdcttr_* (adds HD).
    candidates = sorted(dist_dir.glob(f"{prefix}_cttr_census_acs*topic_name*.csv.xz"))
    return candidates[-1] if candidates else None


def build_va_with_health_districts(va_source: Path, crosswalk_path: Path) -> Path:
    df = read_data(va_source)
    counties = df[df["geoid"].str.len() == 5].copy()
    non_counties = df[df["geoid"].str.len() != 5].copy()

    xwalk = pd.read_csv(crosswalk_path, dtype={"ct_geoid": str, "hd_geoid": str})
    hd = aggregate_with_crosswalk(
        counties, crosswalk=xwalk,
        source_col="ct_geoid", target_col="hd_geoid",
        method="mean",           # use "sum" for counts, "mean" for rates/percents
        value_col="value", target_region_type="health_district",
    )
    hd["moe"] = pd.NA

    combined = pd.concat([non_counties, counties, hd], ignore_index=True)
    combined = combined.sort_values(["geoid", "year", "measure"]).reset_index(drop=True)

    filename = build_file_name(
        coverage_area="va", data_source="census_acs", years=combined["year"].unique().tolist(),
        title="topic_name", geographies=["health_district", "county", "tract"],
    ) + ".csv.xz"
    out_path = write_data(combined, DIST_DIR / filename)
    log.info("Wrote %d rows to %s", len(combined), out_path)
    return out_path


def run() -> None:
    config = load_config()
    crosswalk_path = REPO_DIR / config["crosswalks"]["va_county_to_hd"]
    measure_info = MEASURE_INFO if MEASURE_INFO.exists() else None

    va_source = find_source(DIST_DIR, "va")
    if va_source:
        va_dist = build_va_with_health_districts(va_source, crosswalk_path)
        for p in data_reformat_for_site(
            source_path=va_dist,
            output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
            levels=["health_district", "county", "tract"],
            coverage_area="va", data_source="census_acs", title="topic_name",
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)

    ncr_source = find_source(DIST_DIR, "ncr")
    if ncr_source:
        for p in data_reformat_for_site(
            source_path=ncr_source,
            output_dir=REPO_DIR / "dashboard_data/national_capital_region_data",
            levels=["county", "tract"],
            coverage_area="ncr", data_source="census_acs", title="topic_name",
            measure_info_path=measure_info,
        ):
            log.info("Wrote %s", p)


if __name__ == "__main__":
    run()
```

---

## 4. Long-format data schema

All distribution files use this schema:

| Column        | Type     | Description |
|---------------|----------|-------------|
| `geoid`       | `str`    | Census FIPS (5-digit county, 11-digit tract, HD code, etc.) |
| `year`        | `int`    | Reference year (ACS: survey end year; VDOE: school year start year) |
| `measure`     | `str`    | Snake-case measure name (e.g. `acs_postsecondary_percent`) |
| `value`       | `float`  | Measure value |
| `moe`         | `float`  | Margin of error at 90% CI, or `pd.NA` if not available |
| `region_type` | `str`    | One of: `county`, `tract`, `block_group`, `health_district` |

Rules:
- One row per (geoid, year, measure) combination
- Values are numeric; suppressed/missing cells are dropped (not zeroed)
- `moe` is `pd.NA` when the source doesn't provide uncertainty estimates
- Files are `.csv.xz` (lzma-compressed CSV)

---

## 5. File naming convention

```
{coverage_area}_{resolution}_{data_source}_{time_period}_{title}.csv.xz
```

| Part | Examples |
|------|---------|
| `coverage_area` | `va`, `ncr` |
| `resolution` | `ct` (county), `tr` (tract), `hd` (health district), `cttr`, `hdcttr` |
| `data_source` | `census_acs`, `county_health_rankings`, `vdoe` |
| `time_period` | `2015_2024`, `2010_2024` |
| `title` | `postsecondary`, `years_of_schooling`, `school_funding_adequacy` |

**Ingest output** (county + tract only): `va_cttr_census_acs_2015_2024_topic.csv.xz`
**Prepare output** (adds health district): `va_hdcttr_census_acs_2015_2024_topic.csv.xz`
**Dashboard file** (single level): `va_ct_census_acs_2015_2024_topic.csv.xz`

Use `build_file_name()` to generate names — do not construct them by hand.

---

## 6. `sdc_core` API reference

### `CensusClient` (`sdc_core.census`)

```python
client = CensusClient()   # reads CENSUS_API_KEY from env

# Fetch one state/geography/year at a time (low-level)
df = client.get_acs_wide(
    variables={"name": "B06009_001"},
    geography="county",           # "tract", "county", "block_group"
    state="VA",
    year=2022,
    table_type="detail",          # "detail" (B/C tables) or "subject" (S tables)
    estimate_only=True,
)

# Fetch across multiple years, states, and geographies (preferred)
df = client.get_acs_multi(
    variables={"total": "B06009_001", "count": "B06009_004"},
    years=[2015, 2016, ..., 2024],
    geographies=["tract", "county"],
    profile="NCR",                # OR states=["VA", "MD", "DC"]
    estimate_only=False,          # True = no MOE columns, False = adds {name}_moe columns
)
```

**Output columns:** `geoid`, `year`, `region_type`, + one column per variable name (+ `{name}_moe` if `estimate_only=False`).

**Key rules:**
- Always use `get_acs_multi` for multi-year fetches — it handles looping and progress bars
- `get_acs_wide` does **not** accept `profile=` — pass `state=` instead
- `estimate_only=False` adds `{variable_name}_moe` columns (90% CI)
- `census_standardize=True` in `write_data()` triggers 2010→2020 boundary standardization (see section 7.1)

### `aggregate_with_crosswalk` (`sdc_core.geo`)

```python
hd = aggregate_with_crosswalk(
    counties,                          # DataFrame with county-level rows
    crosswalk=xwalk,                   # DataFrame with ct_geoid, hd_geoid columns
    source_col="ct_geoid",
    target_col="hd_geoid",
    method="mean",                     # "mean" for rates/percents, "sum" for counts
    value_col="value",
    target_region_type="health_district",
)
```

Groups by (hd_geoid, year, measure) and applies `method` to `value_col`. Returns a DataFrame with the same schema as input, with `geoid` = HD code and `region_type` = `"health_district"`.

### `write_data` / `read_data` (`sdc_core.io`)

```python
out_path = write_data(
    df,
    DIST_DIR / "filename.csv.xz",
    census_standardize=True,    # standardize tract GEOIDs to 2020; set False for non-Census data
)

df = read_data(path)            # reads .csv.xz, infers dtypes
```

### `data_reformat_for_site` (`sdc_core.io`)

```python
paths = data_reformat_for_site(
    source_path=combined_path,
    output_dir=REPO_DIR / "dashboard_data/virginia_public_health_data",
    levels=["health_district", "county", "tract"],   # which region_types to split out
    coverage_area="va",
    data_source="census_acs",
    title="topic_name",
    measure_info_path=measure_info,    # optional path to measure_info.json
)
```

Reads the combined distribution file, filters to each level, and writes one file per level to `output_dir`. Returns list of written paths.

### `build_file_name` (`sdc_core.naming`)

Two calling styles:

```python
# Ingest style — infers coverage/resolution from data
name = build_file_name(
    df=result,                      # infers resolution from region_type column
    states=resolve_states(src),     # infers coverage from states list
    years=src.get("years"),
    source_type=src.get("type"),
    title="topic_name",
)

# Prepare style — explicit overrides
name = build_file_name(
    coverage_area="va",
    data_source="census_acs",
    years=[2015, ..., 2024],
    title="topic_name",
    geographies=["health_district", "county", "tract"],  # determines resolution string
)
```

**Gotcha:** `resolve_states(src)` reads `profile:` or `states:` keys from the source config dict. If the config uses `state:` (singular), it returns `[]`, and the coverage prefix will be missing. Use explicit `coverage_area=` in that case.

### `ingest_chr` (`sdc_core.sources.chr`)

```python
from sdc_core.sources.chr import ingest_chr

df = ingest_chr(
    source_cfg["county_health_rankings"],   # the chr sub-block from pipeline.yaml
    working_dir=TOPIC_DIR / "data" / "working",
    state_fips_prefix="51",                 # keep only VA rows; None = keep all
)
```

Handles downloading, caching, parsing "Additional Measure Data" sheet (header=1), float FIPS conversion, and both `column:` (fixed) and `columns:` (year-keyed) measure formats.

---

## 7. Source-specific patterns

### 7.1 Census ACS

- Use `get_acs_multi` with `profile=` for multi-geography, multi-year fetches
- Set `estimate_only=False` when MOE is needed (adds `{name}_moe` columns)
- Always set `census_standardize=True` in `write_data()` for tract data (see below)
- **Supported table types:** `"detail"` (B/C tables), `"subject"` (S tables), `"profile"` (DP tables)
- **Year range:** 2010–2024 (2020 ACS 5-year is available; use it, don't skip)
- **Compute derived measures** (ratios, weighted averages) in a `compute_measures()` function that takes the wide ACS DataFrame and returns long format

#### 2010 → 2020 census geography standardization

The US Census redrew tract boundaries in 2020. Data collected before 2020 uses 2010 tract GEOIDs; data from 2020 onward uses 2020 GEOIDs. Dashboards need consistent boundaries to compare across years.

`write_data(census_standardize=True)` calls `standardize_all()`, which does the following:

**1. Renames measure values to flag boundary version:**

| Data | Measure renamed to |
|---|---|
| `year < 2020`, tract-level | `{measure}_geo10` (original 2010 boundaries) |
| `year < 2020`, tract-level | `{measure}_geo20` (redistributed to 2020 boundaries) |
| `year >= 2020`, tract-level | `{measure}_geo20` (already on 2020 boundaries) |
| county / HD | unchanged (boundaries are stable) |

Pre-2020 tract rows appear **twice** in the output — once as `_geo10` and once as `_geo20`.

**2. Area-weighted redistribution for `_geo20`:**

For tracts where boundaries changed between 2010 and 2020, values are redistributed using `convert_2010_to_2020_bounds()`, which applies a crosswalk with three change types:

- `same` — tract unchanged; value copied as-is
- `split` — 2010 tract split into multiple 2020 tracts; value copied to each (the parent value, not prorated — appropriate for rates)
- `moved` — boundaries shifted; value weighted by `area_part / area20` (area overlap fraction)

MOE is set to `pd.NA` for all `_geo20` converted rows because the area-weighting introduces uncertainty that is not propagated.

**3. When to use it:**

```python
# Tract data with multi-year time series spanning 2010–2024 → always standardize
out_path = write_data(result, path, census_standardize=True)

# County-only data, or non-Census sources → do NOT standardize
out_path = write_data(result, path, census_standardize=False)
```

**4. Effect on prepare.py:**

`prepare.py` reads the already-standardized ingest output. The `_geo10` and `_geo20` measure names flow through unchanged into dashboard files. The dashboard expects this naming — do not strip the suffixes.

### 7.2 County Health Rankings (CHR)

- Use `sdc_core.sources.ingest_chr` — do not rewrite the download/parse logic
- Files are downloaded fresh each run and cached to `data/working/chr_{year}.xlsx`
- The "Additional Measure Data" sheet uses `header=1` (row 0 is the title)
- FIPS values in 2024+ files are floats (`51001.0`) — `ingest_chr` handles this
- Column names for a measure may change across years — use `columns:` (year-keyed dict) in `pipeline.yaml`
- CHR files are Virginia-specific; use `state_fips_prefix="51"` for safety

### 7.3 VDOE SOL data

- Files must be downloaded manually from the VDOE site (403 to automated requests)
- Store in `data/working/` and list filenames in `pipeline.yaml` under `working_files:`
- Each file covers ~3 school years; later files override earlier ones for the same (division, year)
- **Year convention:** school year start (2015-2016 → year 2015)
- Division name → county FIPS mapping: fetch from Census decennial API, fall back to `DIVISION_EXCEPTIONS` dict for combined/town divisions
- Normalize division names: replace hyphens with spaces *before* stripping punctuation (else "Williamsburg-James City" → "williamsburgjames" not "williamsburg james")

### 7.4 Non-automatable sources

Some datasets require manual downloads or one-time data preparation that can't be scripted (VDOE, some DHSS sources). For these:
- Document the download URL and steps clearly in the module docstring
- `ingest.py` reads from `data/working/` and logs a clear error if files are missing
- List expected filenames in `pipeline.yaml`

---

## 8. Health district aggregation rules

Counties aggregate to health districts (VA only) using `aggregate_with_crosswalk` with the crosswalk at:
```
geographies/VA/State Geographies/Health Districts/2020/data/distribution/va_ct_to_hd_crosswalk.csv
```

**Aggregation method by measure type:**

| Measure type | Method |
|---|---|
| Rate, percent, ratio, average | `mean` |
| Count, total | `sum` |
| Index | depends on construction — document explicitly |

When a topic has mixed measure types, aggregate each group separately and concatenate results (see `education/Postsecondary/code/distribution/prepare.py` for the pattern).

---

## 9. Glob patterns in `prepare.py`

`find_source()` must return the **ingest output**, not previous prepare outputs. Ingest writes `{prefix}_cttr_*` (county+tract); prepare writes `{prefix}_hdcttr_*` (adds health district). Use the geography prefix to distinguish them:

```python
# Good — matches only ingest output
dist_dir.glob(f"{prefix}_cttr_census_acs*topic*.csv.xz")

# Bad — also matches the prepare output file
dist_dir.glob(f"{prefix}_*topic*.csv.xz")
```

When in doubt, make the glob as specific as the data source name allows.

---

## 10. `TOPIC_DIR` and `REPO_DIR`

Scripts locate themselves relative to the file:

```python
# For code/distribution/ingest.py and code/distribution/prepare.py:
TOPIC_DIR = Path(__file__).resolve().parents[2]   # e.g. education/Postsecondary
REPO_DIR  = TOPIC_DIR.parents[1]                  # sdc-monorepo root

# For Cooperative Extension (code/ is one level deep):
TOPIC_DIR = Path(__file__).resolve().parents[1]
REPO_DIR  = TOPIC_DIR.parents[1]
```

---

## 11. Logging

```python
from sdc_core.log import get_logger
log = get_logger("topic_name.ingest")   # or "topic_name.prepare"

log.info("Ingesting source '%s'", name)
log.warning("Column '%s' not found in year %d, skipping", col, year)
log.error("Failed: %s", e, exc_info=True)
```

Logger name format: `{topic_slug}.{step}` (e.g. `postsecondary.ingest`, `reading_scores.prepare`).

---

## 12. Conversion checklist

> **Before committing, verify every item in the [Completion gate](#completion-gate) at the top of this spec.** A pipeline missing any required artifact is not ready to commit.

This checklist applies whether you are starting from R code or from existing Python that doesn't yet conform to the standard pattern.

**Step 1: Understand what exists**

- [ ] Check the topic directory for any existing Python files — a partial Python conversion may already be in progress
- [ ] If Python files exist, compare them against the standard pattern (section 3):
  - Is there a `pipeline.yaml`? Does it contain all sources, years, variables, and crosswalk paths?
  - Is there an `ingest.py` that fetches data, computes measures, and writes long-format `.csv.xz` to `data/distribution/`?
  - Is there a `prepare.py` that aggregates to health districts and calls `data_reformat_for_site`?
- [ ] If the structure diverges from the pattern (e.g. a single monolithic script, inline config, no `pipeline.yaml`, or `ingest.py` that also writes dashboard files), **refactor it to conform** — do not layer the standard pattern on top of non-conforming code
- [ ] Read the existing R (or Python) code and any output in `data/distribution/` to understand what the pipeline is supposed to produce

**Step 2: Build the pipeline**

- [ ] Identify the data source type (ACS, CHR, VDOE, manual download, other API)
- [ ] Check if a shared `sdc_core.sources.*` module covers the source; use it if so
- [ ] Write (or refactor) `pipeline.yaml` with all source configs, years, variables, and crosswalk paths
- [ ] Write (or refactor) `ingest.py` — fetches and writes county/tract long-format to `data/distribution/`
- [ ] Run `ingest.py` and verify row counts are reasonable
- [ ] Write (or refactor) `prepare.py` — aggregates to health districts, writes dashboard files
- [ ] Run `prepare.py` and verify dashboard files appear in `dashboard_data/`

**Step 3: Validate and commit**

- [ ] Run the output comparison script (section 13) for each source with an existing R output file
- [ ] Confirm matched row count ≥ 90% of old row count for overlapping years
- [ ] Confirm mean absolute difference is within a reasonable tolerance for the measure type
- [ ] Write a validation report to `docs/validation_report.md` in the topic directory (section 15)
- [ ] Delete any stale intermediate files left by non-conforming scripts (old naming, old format)
- [ ] Stage only the final output files (not stale intermediates from failed runs)
- [ ] Commit and push

---

## 13. Output validation

After running `ingest.py`, validate the new output by comparing it to the previously produced distribution files for overlapping years. This catches regressions in measure computation, wrong variable IDs, or unexpected schema changes before committing.

### 13.1 Identify the comparison file

Look in `data/distribution/` for old R-output files. They typically lack `census_acs` in the name or use older naming conventions:

```
data/distribution/
├── ncr_cttr_2015_2023_income_inequality_gini_index.csv.xz   ← old R output (reference)
└── ncr_cttr_census_acs_2015_2024_income_inequality.csv.xz   ← new Python output
```

Restrict the comparison to years that appear in **both** files. For example, if the new file covers 2015–2024 but the old file covers 2015–2023, compare only 2015–2023.

### 13.2 Comparison script

Run a quick comparison in Python — no special library needed:

```python
import pandas as pd
from pathlib import Path

dist_dir = Path("data/distribution")

# Load old and new files
old = pd.read_csv(sorted(dist_dir.glob("ncr_cttr_2015_*income_inequality*.csv.xz"))[-1])
new = pd.read_csv(sorted(dist_dir.glob("ncr_cttr_census_acs*income_inequality*.csv.xz"))[-1])

# Normalize old file column names if needed (old R output often uses different schema)
# e.g. old.rename(columns={"GEOID": "geoid", "estimate": "value", "variable": "measure"}, inplace=True)

# Keep only overlapping years
overlap_years = set(old["year"].unique()) & set(new["year"].unique())
old = old[old["year"].isin(overlap_years)]
new = new[new["year"].isin(overlap_years)]

# Join on common keys
merged = old.merge(new, on=["geoid", "year", "measure"], suffixes=("_old", "_new"))

# Coverage check
print(f"Old rows (overlap years): {len(old)}")
print(f"New rows (overlap years): {len(new)}")
print(f"Matched rows:             {len(merged)}")

# Value check
merged["diff"] = (merged["value_new"] - merged["value_old"]).abs()
print(f"Mean absolute diff: {merged['diff'].mean():.4f}")
print(f"Max absolute diff:  {merged['diff'].max():.4f}")
print(f"Rows within 0.01:  {(merged['diff'] < 0.01).sum()} / {len(merged)}")
```

### 13.3 What to expect

| Outcome | Likely cause | Action |
|---|---|---|
| 0 matched rows | Column name mismatch in old file | Rename columns before merging; check `measure` values match |
| High mean diff | Wrong variable ID, different normalization, year offset | Review `ingest.py` variable mapping |
| Small systematic bias | Rounding difference (e.g. different decimal precision) | Acceptable if well under 1 unit |
| Matched rows < 90% of old | New pipeline drops rows the old one kept | Investigate `dropna` and suppression logic |
| Near-exact match | — | Proceed to commit |

> **Note:** The old R output often uses a different column schema (e.g. `GEOID`, `estimate`, `variable` instead of `geoid`, `value`, `measure`). Normalize the old file's columns before merging, and verify that `measure` values align (the old file may use a verbose name like `"gini_index"` while the new one uses a short slug).

### 13.4 Reasonable tolerances by measure type

| Measure type | Tolerance |
|---|---|
| Proportions / percentages (0–100) | < 0.1 mean absolute diff |
| Indices (0–1) | < 0.01 mean absolute diff |
| Dollar amounts | < $100 mean absolute diff |
| Counts | < 1% of mean value |

Larger differences need a documented explanation (e.g. "old R code used 2010 boundaries; new code standardizes to 2020").

---

## 14. What not to port

Some R pipelines use infrastructure that has no straightforward Python equivalent:

- **Spatial accessibility (catchment ratios)** — requires OSRM server + `catchment` R package. Defer until a Python spatial access library or custom implementation is ready.
- **Incomplete/exploratory R scripts** — if the R code is a one-off analysis rather than a production pipeline (e.g. hardcoded single-county paths, no generalizable output), clarify the intended scope before porting.
- **Pipelines with no distribution data** and unclear methodology — investigate whether the pipeline ever ran successfully before converting.

---

## 15. Validation report

After completing validation (section 13), write a report to `docs/validation_report.md` inside the topic directory. This creates a permanent record of what was compared, what matched, and what differences are expected.

### 15.1 Location

```
<topic>/
├── docs/
│   └── validation_report.md    ← new
├── pipeline.yaml
├── code/distribution/
│   ├── ingest.py
│   └── prepare.py
└── data/distribution/
```

### 15.2 Template

````markdown
# <Topic Name> — Conversion Validation Report

**Date:** YYYY-MM-DD
**Converted from:** `code/distribution/<old_script>.R`
**New pipeline:** `pipeline.yaml` + `code/distribution/ingest.py` + `code/distribution/prepare.py`

## Data source

- **Source:** <source name and URL>
- **Type:** <census_acs | county_health_rankings | mixed | etc.>
- **Coverage:** <VA | NCR | both>
- **Years:** <year range>

## Output files

| File | Rows | Years | Measures | Region types |
|---|---|---|---|---|
| `<new_ingest_output>.csv.xz` | N | YYYY–YYYY | measure1, measure2 | county, tract |
| `<new_prepare_output>.csv.xz` | N | YYYY–YYYY | measure1, measure2 | health_district, county, tract |

## Validation against old R output

### <Source / level name>

| Comparison | Old file | New file |
|---|---|---|
| File | `<old_filename>.csv.xz` | `<new_filename>.csv.xz` |
| Rows | N | N |
| Overlap years | YYYY–YYYY | — |
| Matched rows | N | — |

| Measure | Matched | Mean diff | Max diff | Result |
|---|---|---|---|---|
| measure_name | N | 0.0000 | 0.0000 | PASS |

### Known differences

> Document any expected differences here. Each entry should explain:
> 1. What differs (which level, measure, years)
> 2. Why it differs (bug fix, methodology change, boundary standardization)
> 3. Which output is correct

Example:
- **County 2021 values:** Old R code had an extrapolation bug — `max(year)` in a
  `mutate()` evaluated to the newly assigned 2021 instead of source year 2020,
  producing `rate × 0`. New Python output correctly extrapolates. New is correct.

## Dashboard files

| File | Rows | Location |
|---|---|---|
| `va_ct_<source>_<years>_<topic>.csv.xz` | N | `dashboard_data/virginia_public_health_data/` |
| `va_hd_<source>_<years>_<topic>.csv.xz` | N | `dashboard_data/virginia_public_health_data/` |
| `va_tr_<source>_<years>_<topic>.csv.xz` | N | `dashboard_data/virginia_public_health_data/` |

## Schema changes

| Aspect | Old (R) | New (Python) |
|---|---|---|
| Columns | geoid, year, measure, value, moe | geoid, year, measure, value, moe, region_type |
| Measure names | `<old_name>` | `<new_name>_geo10`, `<new_name>_geo20` |
| Precision | 2 decimals | 4 decimals |
````

### 15.3 Guidelines

- **Be specific.** Include exact filenames, row counts, and diff values — not vague summaries.
- **Document every known difference.** If a value changed, explain why and which is correct.
- **Include R bugs found.** If the old R code had a bug (wrong variable recycling, extrapolation error, etc.), describe it precisely so future readers understand the discrepancy.
- **Keep it factual.** The report is a reference document, not a narrative. Use tables over prose where possible.
- **One report per topic.** If the topic has multiple sources (e.g. VA + NCR), cover all of them in a single report.
- **Deferred pipelines.** If a pipeline was evaluated and deferred, write a brief report explaining which qualification checklist items failed and why.
