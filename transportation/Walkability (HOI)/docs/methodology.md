# Walkability Index Methodology

## Motivation

The EPA National Walkability Index (NatWalkInd) from the Smart Location Database V3 is a widely used measure of community walkability. However, it is a static snapshot based on ACS 2015–2019 data on 2010-vintage census block groups. Employment patterns, transit service, and land use mix change over time — notably during and after the COVID-19 pandemic — yet the EPA index does not capture these shifts.

We replicate the EPA's walkability formula using annually updated data sources so that our index reflects year-over-year changes in employment composition and transit accessibility. This produces a multi-year walkability index (2017–2023) that retains the structure and interpretability of the original EPA measure while capturing temporal dynamics.

## EPA Walkability Formula

The EPA National Walkability Index combines four ranked sub-indicators:

```
NatWalkInd = D2A_Ranked/6 + D2B_Ranked/6 + D3B_Ranked/3 + D4_Ranked/3
```

| Component | Weight | Description |
|---|---|---|
| D2A_Ranked | 1/6 | Employment and household entropy (land use diversity) |
| D2B_Ranked | 1/6 | Employment entropy across 5 sectors |
| D3B_Ranked | 1/3 | Street intersection density (pedestrian-oriented) |
| D4A_Ranked | 1/3 | Aggregate transit service frequency per sq mi |

Each component is ranked nationally into 20 quantile bins (1 = least walkable, 20 = most walkable). The resulting index ranges from approximately 1 to 20.

## Our Replication

We replicate three of the four components with annually updated data. The fourth (D3B, street connectivity) is held constant from the EPA SLD because road networks change very slowly.

| Component | Our Source | Updated Annually? |
|---|---|---|
| D2A (land use entropy) | LODES WAC + ACS B11001 | Yes |
| D2B (employment entropy) | LODES WAC | Yes |
| D3B (street connectivity) | EPA SLD V3 (fixed) | No |
| D4C (transit proximity) | GTFS transit stop locations | Yes |

Our D4C component is a proxy for the EPA's D4A. The EPA's D4A measures aggregate transit service frequency per square mile, which requires detailed stop_times.txt data. Our D4C measures distance to the nearest transit stop in miles, ranked into 20 quantile bins (inverted so that shorter distance = higher rank). This simpler measure correlates at r = 0.78 with the EPA's walkability index at the block group level.

## Data Sources

### LODES 8 Workplace Area Characteristics (D2A, D2B)

Employment counts by NAICS sector at the census block level from the Longitudinal Employer-Household Dynamics (LEHD) program.

- **URL**: `https://lehd.ces.census.gov/data/lodes/LODES8/{state}/wac/{state}_wac_S000_JT00_{year}.csv.gz`
- **Job type**: JT00 (all jobs), S000 (all workers)
- **Years available**: 2010–2023
- **Geography**: Census blocks (2020 vintage), aggregated to block groups (first 12 characters of 15-character block GEOID)

We aggregate CNS01–CNS20 employment codes into five tiers following the EPA methodology:

| Tier | Label | LODES CNS Codes |
|---|---|---|
| E5_Ret | Retail | CNS07 |
| E5_Off | Office | CNS09, CNS10, CNS11, CNS13, CNS20 |
| E5_Ind | Industrial | CNS01, CNS02, CNS03, CNS04, CNS05, CNS06, CNS08 |
| E5_Svc | Service | CNS12, CNS14, CNS15, CNS16, CNS19 |
| E5_Ent | Entertainment | CNS17, CNS18 |

### ACS Household Counts (D2A)

Household counts from ACS 5-year estimates, table B11001, variable B11001_001 (total households), at the block group level. Used as the sixth category in D2A land use entropy alongside the five employment tiers.

### EPA Smart Location Database V3 (D3B)

Street intersection density (D3B_Ranked) from the EPA SLD V3 (January 2021 release), based on ACS 2015–2019 on 2010-vintage census block groups. This component measures the density of pedestrian-oriented intersections (3+ legs) per square mile and is held constant across all years.

- **URL**: `https://edg.epa.gov/EPADataCommons/public/OA/EPA_SmartLocationDatabase_V3_Jan_2021_Final.csv`
- **Columns used**: STATEFP, COUNTYFP, TRACTCE, BLKGRPCE, D3B_Ranked, TotPop

### GTFS Transit Stop Locations (D4C)

National transit stop locations extracted from GTFS (General Transit Feed Specification) schedule feeds, covering 2017–2024.

**Catalog**: The Mobility Database (`mobilitydatabase.org`) provides a catalog of ~1,600 active US GTFS schedule feeds with direct download URLs.

**Historical feeds**: For years prior to the current year, historical feed versions are retrieved from the Transitland API (`transit.land/api/v2/rest`). A crosswalk between Mobility Database feed IDs and Transitland onestop IDs is built using:
- Exact URL matching (comparing download URLs across both databases): ~921 matches
- Fuzzy provider name matching (SequenceMatcher similarity ≥ 0.80): ~101 additional matches
- Total: ~1,022 of 1,400 active feeds matched (73%)

The Transitland Atlas repository (`github.com/transitland/transitland-atlas`) provides the feed definitions used to build this crosswalk.

**Historical version selection**: For each feed and target year, we query Transitland for feed versions fetched within a ±1 year window, then select the version whose service calendar dates (earliest_calendar_date to latest_calendar_date) best overlap with July 1 of the target year.

**Stop extraction and deduplication**: Stops are extracted from each GTFS zip's `stops.txt` file. Invalid coordinates (non-numeric, out of range, or at 0/0) are dropped. Stops are deduplicated by snapping to a ~10-meter grid (rounding lat/lon to 4 decimal places), keeping one record per grid cell. This removes duplicates from overlapping feed coverage areas (e.g., a bus stop served by both a local and regional agency).

**Typical results per year**: ~400,000–600,000 unique stops from ~800–900 feeds, covering all 50 states, DC, and territories.

## Entropy Computation (D2A, D2B)

Both D2A and D2B use the same normalized entropy formula:

```
H = -sum(p_i * ln(p_i)) / ln(N)
```

where:
- p_i = proportion of activity in category i (e.g., share of employment in retail)
- N = number of non-zero categories in that block group
- 0 × ln(0) is treated as 0
- Result is in [0, 1], where 0 = all activity in one category, 1 = perfectly even distribution

**D2B_E5MIX** (employment entropy): Computed over the 5 employment tiers (Retail, Office, Industrial, Service, Entertainment). N ranges from 1 to 5.

**D2A_EPHHM** (land use entropy): Computed over 6 categories — the 5 employment tiers plus household count (from ACS B11001). N ranges from 1 to 6. This captures the balance between residential and commercial land uses.

## Distance Computation (D4C)

For each block group, we compute the haversine distance (in miles) from the block group centroid to the nearest transit stop.

**Block group centroids** are computed as the arithmetic mean of all exterior ring vertex coordinates from the census block group GeoJSON boundary files. For MultiPolygons, vertices from all outer rings are combined.

**Haversine formula** (Earth radius = 3,958.8 miles):

```
a = sin(dlat/2)^2 + cos(lat1) * cos(lat2) * sin(dlon/2)^2
c = 2 * arcsin(sqrt(a))
distance = 3958.8 * c
```

Stops are pre-filtered to a bounding box (coverage area extent ± 0.5 degrees) and processed in chunks of 2,000 to manage the (N_block_groups × N_stops) distance matrix.

## Ranking

Each component (D2A, D2B, D4C) is ranked within the coverage area into 20 quantile bins using rank-based quantiles:

1. Assign a rank to each value using `rank(method="first")`
2. Divide ranks into 20 equal-sized bins via `pd.qcut`
3. Bins are numbered 1–20

For D2A and D2B, higher values (more diverse) receive higher ranks. For D4C, lower values (closer to transit) receive higher ranks (bins are inverted: rank = 21 − bin).

D3B_Ranked is taken directly from the EPA SLD (already ranked 1–20 nationally).

## Geographic Vintage Reconciliation

The walkability computation merges data across two census geographies:

- **2010 vintage**: EPA SLD D3B_Ranked and D4C (computed on 2010 block group centroids)
- **2020 vintage**: LODES employment data and ACS households (on 2020 block groups)

To reconcile, D2 values computed on 2020-vintage block groups are aggregated to the tract level (first 11 characters of GEOID), and the tract-level mean is assigned to all 2010-vintage block groups within that tract. This is a reasonable approximation given that most tract boundaries are stable between 2010 and 2020.

## Aggregation to Higher Geographies

Block-group-level walkability scores are aggregated to tracts, counties, and health districts using **population-weighted mean**, with population from the EPA SLD's TotPop field:

```
walkability_tract = weighted_mean(walkability_bg, weights=tot_pop)
```

Block groups with TotPop = 0 are excluded before aggregation.

### Boundary Conversion

- **_geo10**: Tract and county values computed directly from 2010-vintage block groups
- **_geo20**: Tract values are converted from 2010 to 2020 boundaries using an area-overlap crosswalk (`convert_2010_to_2020_bounds`). County values are unchanged (county boundaries are stable across censuses).

Health districts are computed by aggregating county values using a county-to-health-district crosswalk (VA only).

## Outputs

### Block-group level (intermediate)

`geographies/transit_stops/data/walkability/{coverage}_walkability_{year}.parquet`

| Column | Type | Description |
|---|---|---|
| geoid | string | 12-character block group GEOID (2010 vintage) |
| walkability_index | float | Composite walkability score (1–20 scale) |
| d2a_ephhm | float | Land use entropy (0–1) |
| d2b_e5mix | float | Employment entropy (0–1) |
| d2a_ranked | int | D2A quantile bin (1–20) |
| d2b_ranked | int | D2B quantile bin (1–20) |
| d3b_ranked | int | D3B from EPA SLD (1–20) |
| d4c_dist_mi | float | Distance to nearest transit stop (miles) |
| d4c_ranked | int | D4C quantile bin (1–20, inverted) |
| epa_d4a_ranked | int | EPA's original D4A rank (for comparison) |
| epa_walkability | float | EPA's original NatWalkInd (for comparison) |
| tot_pop | int | Block group population |
| year | int | Data year |

### Dashboard level (final)

Written to `dashboard_data/{site}/` directories:

**Virginia**: health district, county, and tract levels
**NCR**: county and tract levels

Each file contains columns: `ID` (geoid), `time` (year), `walkability_index_geo10`, `walkability_index_geo20`.

Years: 2017–2023.

## Validation

Our walkability index is validated against the EPA's original NatWalkInd at the block group level:

| Coverage | Correlation (r) | RMSE | Block Groups |
|---|---|---|---|
| NCR | 0.77 | 2.5 | ~3,245 |
| VA | 0.78 | 3.0 | ~5,327 |

The moderate (rather than high) correlation is expected because:
1. Our D4C (distance to nearest stop) is a proxy for the EPA's D4A (aggregate service frequency)
2. Our D2A/D2B are computed from different-year LODES data vs. EPA's ACS-derived values
3. We rank within the coverage area, while EPA ranks nationally

At the individual block group level, meaningful year-over-year variation is observed:
- 2019→2020 (COVID impact): 638 of 3,245 NCR block groups shifted by 1+ points, 174 by 2+ points
- 2017→2023 (full span): 918 shifted by 1+ points, 211 by 2+ points

## Pipeline Scripts

| Script | Location | Purpose |
|---|---|---|
| `fetch_catalog.py` | `geographies/transit_stops/code/` | Download Mobility Database GTFS catalog |
| `build_crosswalk.py` | `geographies/transit_stops/code/` | Match MDB feeds to Transitland onestop IDs |
| `fetch_feeds.py` | `geographies/transit_stops/code/` | Download GTFS zips (current + historical) |
| `extract_stops.py` | `geographies/transit_stops/code/` | Extract and deduplicate transit stops |
| `compute_d2.py` | `geographies/transit_stops/code/` | Compute D2A/D2B from LODES + ACS |
| `compute_d4c.py` | `geographies/transit_stops/code/` | Compute distance to nearest transit stop |
| `compute_walkability.py` | `geographies/transit_stops/code/` | Combine components into walkability index |
| `ingest.py` | `transportation/Walkability (HOI)/code/distribution/` | Aggregate BG to tract/county with geo suffixes |
| `prepare.py` | `transportation/Walkability (HOI)/code/distribution/` | Add health districts, write dashboard files |
