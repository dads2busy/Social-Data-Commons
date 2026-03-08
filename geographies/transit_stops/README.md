# Transit Stops & Walkability Components

National archive of transit stop locations extracted from GTFS feeds, plus
derived walkability components (D2A/D2B employment entropy, D4C transit
proximity, and the composite walkability index). Covers 2017–2024 for transit
stops and 2017–2023 for walkability.

## Data Sources

- **Mobility Database** (<https://mobilitydatabase.org>): catalog of ~1,600 US GTFS
  schedule feeds with direct download URLs.
  Catalog CSV: `https://files.mobilitydatabase.org/feeds_v2.csv`

- **Transitland** (<https://www.transit.land>): archive of 105,000+ historical GTFS
  feed versions going back to ~2008. Free Hobbyist/Academic plan available for
  non-commercial access to historical feed versions.
  API docs: <https://www.transit.land/documentation/rest-api/feed_versions>

- **Transitland Atlas** (<https://github.com/transitland/transitland-atlas>):
  open-source registry of feed definitions with onestop IDs, used to build the
  crosswalk between Mobility Database and Transitland.

- **LODES 8 WAC** (<https://lehd.ces.census.gov/data/lodes/LODES8/>): Workplace
  Area Characteristics with employment by NAICS sector at the census block
  level. Used for D2A/D2B employment entropy. Available 2010–2023.

- **ACS 5-Year Estimates, Table B11001**: Household counts at the block group
  level from the Census Bureau API. Used as the sixth category in D2A land use
  entropy.

- **EPA Smart Location Database V3** (`transportation/Walkability (HOI)/data/working/sld_v3.csv`):
  D3B_Ranked (street intersection density) and TotPop (population weights)
  on 2010-vintage block groups. Used as a fixed component in the walkability
  formula.

## Pipeline

### Step 1: Fetch GTFS catalog

```bash
uv run python code/fetch_catalog.py
```

Downloads the Mobility Database catalog CSV, filters to US GTFS schedule feeds,
and saves as `data/feeds_catalog.csv` (~1,600 active feeds).

### Step 2: Build MDB–Transitland crosswalk (for historical years)

```bash
git clone --depth 1 https://github.com/transitland/transitland-atlas.git data/transitland-atlas
uv run python code/build_crosswalk.py
```

Matches Mobility Database feed IDs to Transitland onestop IDs using:
- Exact URL matching (~921 feeds matched)
- Fuzzy provider name matching with SequenceMatcher ≥ 0.80 (~101 additional)
- Total: ~1,022 of 1,400 active feeds matched (73%)

Output: `data/mdb_transitland_crosswalk.csv`

### Step 3: Download GTFS feeds

```bash
# Current year (no API key needed, uses Mobility Database latest URLs)
uv run python code/fetch_feeds.py --year 2024

# Historical year (requires Transitland API key)
uv run python code/fetch_feeds.py --year 2019 --transitland-key $TRANSITLAND_API_KEY
```

For historical years, queries Transitland for the feed version whose service
dates best cover July 1 of the target year. Falls back to Mobility Database
latest URL if no Transitland match is found.

- 20 concurrent download workers (5 when using Transitland API)
- Streaming downloads with 64KB chunks, 30s timeout, 100MB size limit
- Caches zips in `data/gtfs_cache/{year}/`

### Step 4: Extract and deduplicate stops

```bash
uv run python code/extract_stops.py --year 2024
```

Extracts `stops.txt` from each GTFS zip, validates coordinates (drops
non-numeric, out-of-range, and 0/0 values), and deduplicates by snapping to
a ~10m grid (4 decimal places). Writes a consolidated parquet per year.

Output: `data/stops/us_transit_stops_{year}.parquet`

### Step 5: Compute D4C (transit proximity)

```bash
uv run python code/compute_d4c.py --geo-vintage 2010 --coverage ncr
uv run python code/compute_d4c.py --geo-vintage 2010 --coverage va
```

Computes haversine distance (miles) from each block group centroid to the
nearest transit stop. Block group centroids are computed as the mean of
exterior ring vertices from census GeoJSON boundary files. Stops are
pre-filtered to a bounding box (coverage area ± 0.5°) and processed in
chunks of 2,000 to manage memory.

Output: `data/d4c/{coverage}_d4c_bg{vintage}_{year}.parquet`

### Step 6: Compute D2A/D2B (employment & land use entropy)

```bash
uv run python code/compute_d2.py --coverage ncr --years 2017 2018 2019 2020 2021 2022 2023
uv run python code/compute_d2.py --coverage va --years 2017 2018 2019 2020 2021 2022 2023
```

Downloads LODES 8 WAC files for each state, aggregates block-level employment
to block groups, computes 5-tier employment categories, fetches ACS household
counts, and calculates:

- **D2B_E5MIX**: Employment entropy across 5 tiers (Retail, Office, Industrial,
  Service, Entertainment)
- **D2A_EPHHM**: Land use entropy across 6 categories (households + 5
  employment tiers)

Entropy formula: `H = -sum(p_i * ln(p_i)) / ln(N)`, normalized to [0, 1].

LODES data is cached as parquet in `data/lodes_cache/`. Output:
`data/d2/{coverage}_d2_bg2020_{year}.parquet`

### Step 7: Compute walkability index

```bash
uv run python code/compute_walkability.py --coverage ncr
uv run python code/compute_walkability.py --coverage va
```

Combines all components using the EPA walkability formula:

```
NatWalkInd = D2A_Ranked/6 + D2B_Ranked/6 + D3B_Ranked/3 + D4C_Ranked/3
```

D2A, D2B, and D4C are ranked within the coverage area into 20 quantile bins.
D3B_Ranked is taken directly from the EPA SLD (fixed). D4C ranking is inverted
so that shorter distance (better transit access) gets a higher rank.

Output: `data/walkability/{coverage}_walkability_{year}.parquet`

## Full Rebuild

```bash
# 1. Catalog and crosswalk (one-time setup)
uv run python code/fetch_catalog.py
git clone --depth 1 https://github.com/transitland/transitland-atlas.git data/transitland-atlas
uv run python code/build_crosswalk.py

# 2. Download and extract stops for all years
for year in 2017 2018 2019 2020 2021 2022 2023 2024; do
  uv run python code/fetch_feeds.py --year $year --transitland-key $TRANSITLAND_API_KEY
  uv run python code/extract_stops.py --year $year
done

# 3. Compute D4C (transit proximity)
uv run python code/compute_d4c.py --geo-vintage 2010 --coverage ncr
uv run python code/compute_d4c.py --geo-vintage 2010 --coverage va

# 4. Compute D2A/D2B (employment entropy)
uv run python code/compute_d2.py --coverage ncr --years 2017 2018 2019 2020 2021 2022 2023
uv run python code/compute_d2.py --coverage va --years 2017 2018 2019 2020 2021 2022 2023

# 5. Compute walkability index
uv run python code/compute_walkability.py --coverage ncr
uv run python code/compute_walkability.py --coverage va
```

## Output Summary

### Transit stops

```
data/stops/
├── us_transit_stops_2017.parquet
├── ...
└── us_transit_stops_2024.parquet
```

| Column | Type | Description |
|---|---|---|
| stop_lat | float | Latitude |
| stop_lon | float | Longitude |
| feed_id | str | Mobility Database feed ID (e.g., `mdb-1846`) |
| agency_name | str | Transit agency name |
| stop_name | str | Stop name from GTFS |

### D4C (transit proximity)

```
data/d4c/
├── ncr_d4c_bg2010_{year}.parquet
└── va_d4c_bg2010_{year}.parquet
```

| Column | Type | Description |
|---|---|---|
| geoid | str | 12-char block group GEOID |
| year | int | Data year |
| d4c_dist_mi | float | Distance to nearest transit stop (miles) |
| nearest_stop_name | str | Name of nearest stop |
| nearest_stop_agency | str | Agency operating nearest stop |

### D2 (employment & land use entropy)

```
data/d2/
├── ncr_d2_bg2020_{year}.parquet
└── va_d2_bg2020_{year}.parquet
```

| Column | Type | Description |
|---|---|---|
| geoid | str | 12-char block group GEOID (2020 vintage) |
| TotEmp | int | Total employment |
| HH | int | Household count (ACS B11001) |
| D2A_EPHHM | float | Land use entropy (0–1) |
| D2B_E5MIX | float | Employment entropy (0–1) |
| E5_Ret, E5_Off, E5_Ind, E5_Svc, E5_Ent | int | 5-tier employment counts |

### Walkability index

```
data/walkability/
├── ncr_walkability_{year}.parquet
└── va_walkability_{year}.parquet
```

| Column | Type | Description |
|---|---|---|
| geoid | str | 12-char block group GEOID (2010 vintage) |
| walkability_index | float | Composite score (1–20 scale) |
| d2a_ephhm | float | Land use entropy |
| d2b_e5mix | float | Employment entropy |
| d2a_ranked | int | D2A quantile bin (1–20) |
| d2b_ranked | int | D2B quantile bin (1–20) |
| d3b_ranked | int | Street connectivity from EPA SLD (1–20) |
| d4c_dist_mi | float | Distance to nearest stop (miles) |
| d4c_ranked | int | D4C quantile bin (1–20, inverted) |
| epa_d4a_ranked | int | EPA original D4A rank (for comparison) |
| epa_walkability | float | EPA original NatWalkInd (for comparison) |
| tot_pop | int | Block group population |
| year | int | Data year |

## Current Results

### Transit stops (2024)

- 897 active feeds in catalog
- 838 GTFS zips processed from 763 feeds
- 445,127 raw stops → 401,424 unique after deduplication
- Coverage: all 50 states + DC + territories

### Walkability (2017–2023)

| Coverage | Block Groups | Correlation with EPA | RMSE |
|---|---|---|---|
| NCR | ~3,245 | r = 0.77 | 2.5 |
| VA | ~5,327 | r = 0.78 | 3.0 |

Year-over-year variation at block group level (NCR 2019→2020):
- 638 BGs shifted by 1+ points, 174 by 2+ points (on 1–20 scale)

## Downstream Consumer

**Walkability Index** (`transportation/Walkability (HOI)/`): reads walkability
parquets, aggregates block groups to tract/county/health district using
population-weighted mean, applies 2010→2020 boundary conversion, and writes
dashboard files for NCR and VA.

## Notes

- GTFS feeds vary in quality. Some agencies publish stops not currently in
  service. Filtering to stops referenced by active `stop_times.txt` entries
  would improve accuracy.
- D4C (distance to nearest stop) is a proxy for the EPA's D4A (aggregate
  transit service frequency). True D4A would require parsing `stop_times.txt`.
- D3B (street connectivity) is held constant from the EPA SLD. Road networks
  change slowly, making this the least impactful component to update.
- D2 data uses 2020-vintage block groups (from LODES) while D3B/D4C use
  2010-vintage (from EPA SLD). Values are reconciled at the tract level.
- LODES WAC is available through 2023. ACS B11001 is capped at 2023.
- Transitland API requires an API key. Sign up at <https://www.transit.land>
  (free plan: 10,000 queries/month). Store in `.env` as `TRANSITLAND_API_KEY`.
- Budget ~50–100 GB disk space for cached GTFS zips across all years.
