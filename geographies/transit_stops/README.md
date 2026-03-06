# Transit Stops Archive

National archive of transit stop locations extracted from GTFS feeds, covering
multiple years. Used as an input to the walkability index (D4A component) and
potentially other transit-proximity measures.

## Data sources

- **Mobility Database** (<https://mobilitydatabase.org>): catalog of ~1,600 US GTFS
  schedule feeds with direct download URLs.
  Catalog CSV: `https://files.mobilitydatabase.org/feeds_v2.csv`

- **Transitland** (<https://www.transit.land>): archive of 105,000+ historical GTFS
  feed versions going back to ~2008. Free Hobbyist/Academic plan available for
  non-commercial access to historical feed versions.
  API docs: <https://www.transit.land/documentation/rest-api/feed_versions>

## Pipeline

1. **`code/fetch_catalog.py`** — Download the Mobility Database catalog CSV,
   filter to US GTFS schedule feeds, and save as `data/feeds_catalog.csv`.

2. **`code/fetch_feeds.py`** — For each feed in the catalog, download the GTFS
   zip for a target year. Uses Transitland API for historical versions,
   Mobility Database `urls.latest` for current year. Caches zips in
   `data/gtfs_cache/{year}/`.

3. **`code/extract_stops.py`** — Extract `stops.txt` from each downloaded GTFS
   zip, deduplicate by location (snap to ~10m grid), and write a consolidated
   parquet per year to `data/stops/`.

## Output

```
data/stops/
├── us_transit_stops_2017.parquet
├── us_transit_stops_2018.parquet
├── ...
└── us_transit_stops_2024.parquet
```

Each parquet contains:

| Column | Type | Description |
|---|---|---|
| stop_lat | float | Latitude |
| stop_lon | float | Longitude |
| feed_id | str | Mobility Database feed ID (e.g., `mdb-1846`) |
| agency_name | str | Transit agency name |
| stop_name | str | Stop name from GTFS |

## Downstream consumers

- **Walkability Index** (`transportation/Walkability (HOI)/`): D4A component —
  distance from block group centroid to nearest transit stop.
- **Employment Access**: potential future transit accessibility measures.

## Notes

- GTFS feeds vary in quality. Some agencies publish stops that are not
  currently in service. Filtering to stops referenced by active `stop_times.txt`
  entries would improve accuracy but adds complexity.
- The national dataset is large (~1,600 feeds × multiple years). Budget disk
  space for cached GTFS zips (~50–100 GB for all years).
- Transitland API requires an API key. Store in `.env` as `TRANSITLAND_API_KEY`.
