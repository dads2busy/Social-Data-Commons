## Overview
Fixed and mobile broadband speed measures from Ookla Speedtest Open Data, derived from quarterly speed test tiles spatially joined to Census 2020 block groups. Fixed tiles include all wired connection types (cable, fiber, DSL, fixed wireless, and satellite). Measures include device-weighted average download and upload speeds (Mb/s) and percentage of devices exceeding broadband thresholds (25/3 Mb/s and 100/20 Mb/s). Block group values are aggregated to Census tracts and counties using simple means. This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Ookla Speed** data pipeline.

## Provenance
Derived from Ookla Speedtest Open Data quarterly speed test tiles (both fixed-line and mobile). Tiles are spatially joined to Census 2020 block groups using intersection. Per-tile average speeds (avg_d_kbps, avg_u_kbps) are aggregated to block groups using device-weighted means. Threshold percentages are computed as the device-weighted share of tiles meeting minimum speed criteria. Quarterly values are averaged within each year. Tract and county values are simple means of constituent block groups.

## Coverage
- **Temporal coverage:** 2019–2025 (quarterly Ookla Open Data)
- **Geographic levels:** Block Group, Tract, County
- **Coverage areas:** National Capital Region (DC metro), Virginia (statewide)

## Methodology
Speed test tiles from Ookla's S3 bucket are downloaded quarterly for both fixed and mobile service types. Each tile represents a ~610m × 610m area and contains average download/upload speeds and device/test counts. Tiles are spatially joined to Census 2020 block group boundaries using geometric intersection. Within each block group, tile-level speeds are aggregated using device-weighted means (each tile's speed is weighted by its number of unique devices). Threshold percentages (25/3 Mb/s and 100/20 Mb/s) represent the share of devices in tiles whose average speeds meet or exceed the threshold. Quarterly block group values are averaged within each calendar year. Tract and county values are simple means of their constituent block groups.

## Source Tables
- [Ookla Speedtest Open Data — Fixed-line performance tiles](https://github.com/teamookla/ookla-open-data)
- [Ookla Speedtest Open Data — Mobile performance tiles](https://github.com/teamookla/ookla-open-data)
- [U.S. Census Bureau — TIGER/Line Shapefiles, Census 2020 Block Groups](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html)

## Measures (8)
*Note on naming conventions: Measures containing `_geo20` are computed using 2020 Census geographic boundaries.*

### Fixed broadband
- **avg_down_speed_geo20**: Average download speed (Mb/s), device-weighted
  Average download speed weighted by number of devices.
- **avg_up_speed_geo20**: Average upload speed (Mb/s), device-weighted
  Average upload speed weighted by number of devices.
- **perc_above_25_3_geo20**: Percent of devices above 25/3 Mb/s broadband threshold
  Percent of devices with speeds above 25/3 Mb/s (FCC broadband threshold).
- **perc_above_100_20_geo20**: Percent of devices above 100/20 Mb/s broadband threshold
  Percent of devices with speeds above 100/20 Mb/s (fast broadband threshold).

### Mobile broadband
- **mobile_avg_down_speed_geo20**: Average mobile download speed (Mb/s), device-weighted
  Average mobile download speed weighted by number of devices.
- **mobile_avg_up_speed_geo20**: Average mobile upload speed (Mb/s), device-weighted
  Average mobile upload speed weighted by number of devices.
- **mobile_perc_above_25_3_geo20**: Percent of mobile devices above 25/3 Mb/s broadband threshold
  Percent of mobile devices with speeds above 25/3 Mb/s.
- **mobile_perc_above_100_20_geo20**: Percent of mobile devices above 100/20 Mb/s broadband threshold
  Percent of mobile devices with speeds above 100/20 Mb/s.

## Data Sources
- [Ookla Speedtest Open Data (accessed 2025)](https://www.ookla.com/ookla-for-good/open-data)
- [U.S. Census Bureau (accessed 2025)](https://www.census.gov/geographies.html)

## File Format
Data files are provided as xz-compressed CSV (`.csv.xz`) with the following columns: `geoid`, `region_type`, `region_name`, `year`, `measure`, `value`, `moe` (margin of error, where available). A `measure_info.json` file provides per-measure metadata.
