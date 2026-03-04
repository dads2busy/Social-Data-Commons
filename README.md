# Social Data Commons (SDC)

Unified monorepo for Social Data Commons data pipelines. This repo contains domain-specific pipelines plus a shared Python core for ingesting, standardizing, and distributing datasets across multiple social impact domains.

## Purpose

- **Goal**: ingest, standardize, and distribute SDC datasets across domains (demographics, health, housing, etc.).
- **Primary runtime**: Python, with shared utilities in `packages/sdc-core/`.
- **Outputs**: standardized long-form CSVs (usually `.csv.xz`) in `data/distribution/`.

## Tech Stack

- **Python** (primary runtime)
- **uv** for environment and dependency management
- **pandas** for data manipulation
- **httpx** for API access
- **Geo tooling** via `sdc-core` utilities (crosswalks, aggregation, standardization)

## Setup

```bash
uv sync
```

Creates a single `.venv` with `sdc-core` installed in editable mode.

## Usage

```bash
uv run python demographics/Gender/code/ingest.py
```

Each pipeline has its own `pipeline.yaml` and writes to `data/distribution/`.

## Repository Structure

### Typical Topic Layout

Each data topic follows a consistent directory structure:

- `code/` — ingest/prepare scripts
- `data/original/` — raw source extracts
- `data/working/` — intermediate datasets
- `data/distribution/` — final outputs (compressed `.csv.xz`)
- `docs/` — supporting documentation

### Core Infrastructure

| Directory | Description |
|-----------|-------------|
| `packages/sdc-core/` | Shared Python framework (Census API, I/O, geo aggregation, naming, logging) |
| `geographies/` | Authoritative source for all geography files (crosswalks, reference data) |
| `meta/` | Infrastructure, metadata, and supporting utilities |
| `dashboard_data/` | Dashboard-ready data files |

### Data Domains

| Directory | Description |
|-----------|-------------|
| `broadband/` | Broadband access and pricing data |
| `business_climate/` | Business activity metrics and employment data |
| `demographics/` | Demographic pipelines (age, gender, race, language, veteran, etc.) |
| `education/` | Education-related measures from multiple sources |
| `financial_well_being/` | Employment, pay, benefits, and personal income data |
| `food/` | Food access and security data |
| `health/` | Health data and measures |
| `housing/` | Housing stock, programs, and survey data |
| `public_safety/` | Public safety data |
| `transportation/` | Transit, safety, and commuting data |

---

## Data Domains

### Broadband

Broadband access, speed, and pricing data at the census block level.

- **Measure selection**: cheapest plan above 100 Mb/s download speed per block, using a randomly selected address per block. Aggregation uses the median of the minimum in the group.
- **Data sources**:
  - **BroadbandNow** — scraped pricing and provider data (speed, price, provider name, type, address). Uses a strategy of randomly sampling points within shapefiles and reverse-geocoding to query addresses.
  - **Ookla** — open speed test data (average download/upload speeds in Mbps, test counts, device counts, latency, by quarter).

### Business Climate

Business activity metrics at census geographic levels (block group, tract, county), segmented by industry and minority-ownership status.

- **Employment**: number of businesses, entry/exit rates, small business counts and percentages, sole proprietor counts and percentages. Broken down by total, industry type, and minority type.
- **Business Characteristics**: job creation/destruction metrics (active/new/exit), job creation/destruction rates. Broken down by total, industry type, and minority type.
- **Industry Specific (Agriculture)**: land in farms, farm size, farm sales, market value of farms, livestock and poultry, crops harvested.

### Demographics

Demographic data and measures from the American Community Survey (ACS), covering age, gender, race, language, veteran status, and more. Pipelines estimate demographics at the parcel level and various geographic levels.

### Education

Education-related measures from multiple sources:

- **Daycare locations** from Virginia Department of Social Services (VDSS)
- **Secondary education locations** from National Center for Education Statistics (NCES)
- **Secondary education attendance** from the American Community Survey (ACS)
- **Reading test pass rates** from the Virginia Department of Education (VDOE)

### Financial Well-being

Data and metrics related to financial well-being:

- **Employment**
- **Pay and Benefits** (including personal income)

### Food

Food-related data and measures for the Social Impact Data Commons, covering food access and food security.

### Health

Health data and measures for the Social Impact Data Commons.

### Housing

Housing-related data organized into three categories:

- **Operations and Planning** — data for assessing housing stock and planning development: rent data, vacant addresses, homelessness (including evictions), taxes, household characteristics, and prices.
- **Program Participation** — federal and local housing programs: assisted/subsidized/affordable housing, mortgages (Freddie Mac, Fannie Mae), Low-Income Tax Credit.
- **Housing Surveys** — American Housing Survey, Survey of Construction.

### Public Safety

Public safety data and metrics for the Social Data Commons.

### Transportation

Transportation-related data organized into multiple categories:

- **Infrastructure**: public transit (WMATA and non-WMATA bus/rail stops), vehicle shares (carshare/bikeshare locations), biking and walking (bike lanes, national walkability index).
- **Safety**: traffic fatalities, traffic accidents involving bikes or pedestrians.
- **Population Characteristics**: commuting (mean travel time, carpool percentage), vehicle availability, transportation burden.

---

## Supporting Infrastructure

### Geographies (`geographies/`)

Authoritative source for all geography files used by the Social Data Commons. Includes Census GeoJSON files for 2010 and 2020 at multiple levels (block groups, tracts, counties) for DC, MD, VA, NCR (National Capital Region), and US, plus specialized Virginia geography files (health districts, civic associations, human services regions, planning districts, supervisor districts, zip codes).

Data files are organized in parallel `/data`, `/docs`, and `/src` folders. A distribution file manifest with MD5 checksums is available at `/data/distribution_file_manifest.csv`.

### sdc-core (`packages/sdc-core/`)

Shared Python framework providing Census API access, I/O utilities, geographic aggregation, naming conventions, and logging.

- **Naming**: `sdc_core.naming.build_file_name(...)` builds output filenames using available metadata and inferred resolution.
  - Resolution order: `hd, ct, tr, bg, bl, nb, pl, bz, pr`.
  - Coverage defaults: `("dc","md","va") -> ncr`, plus single-state defaults.

### Meta (`meta/`)

Supporting infrastructure and utilities:

- **`meta/all/`** — combined data from all domain repositories.
- **`meta/intro/`** — introduction website for the Social Data Commons.
- **`meta/metadata/`** — tools for retrieving metadata from the SDC.
- **`meta/census10to20/`** — standardizes data from 2010 census tract boundaries to 2020 boundaries for consistent time-series analysis.
- **`meta/life_expectancy_calculator/`** — React application for calculating life expectancy.

---

## Current Status

- **Demographics**: actively converting R pipelines to Python.
- **Legacy R**: remaining R scripts have been moved to `legacy/` subdirectories within their respective domains.
- **Pipeline conversions**: SNAP, Feeding America (food), Mergent Intellect (business climate), Worker Diversity/LODES, and Agriculture/NASS pipelines have been converted to Python.
