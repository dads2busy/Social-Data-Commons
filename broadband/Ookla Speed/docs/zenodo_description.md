## Overview
Fixed and mobile broadband speed measures from Ookla Speedtest Open Data, derived from quarterly speed test tiles spatially joined to Census 2020 block groups. Fixed tiles include all wired connection types (cable, fiber, DSL, fixed wireless, and satellite). Measures include device-weighted average download and upload speeds (Mb/s) and percentage of devices exceeding broadband thresholds (25/3 Mb/s and 100/20 Mb/s). Block group values are aggregated to Census tracts and counties using simple means. This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Ookla Speed** data pipeline.

## Provenance
Derived from Ookla Speedtest Open Data quarterly fixed-line speed test tiles. Tiles are spatially joined to Census 2020 block groups using intersection. Per-tile average download speed (avg_d_kbps field) is aggregated to block groups using device-weighted means. Quarterly values are averaged within each year. Tract and county values are simple means of constituent block groups.

Derived from Ookla Speedtest Open Data quarterly fixed-line speed test tiles. Tiles are spatially joined to Census 2020 block groups using intersection. Per-tile average upload speed (avg_u_kbps field) is aggregated to block groups using device-weighted means. Quarterly values are averaged within each year. Tract and county values are simple means of constituent block groups.

Derived from Ookla Speedtest Open Data quarterly tiles. A tile qualifies if avg_d_kbps >= 25,000 and avg_u_kbps >= 3,000. The percentage is the device-weighted share of qualifying tiles within each block group. Quarterly values are averaged within each year.

Derived from Ookla Speedtest Open Data quarterly tiles. A tile qualifies if avg_d_kbps >= 100,000 and avg_u_kbps >= 20,000. The percentage is the device-weighted share of qualifying tiles within each block group. Quarterly values are averaged within each year.

Derived from Ookla Speedtest Open Data quarterly mobile speed test tiles. Tiles are spatially joined to Census 2020 block groups using intersection. Per-tile average download speed (avg_d_kbps field) is aggregated to block groups using device-weighted means. Quarterly values are averaged within each year. Tract and county values are simple means of constituent block groups.

Derived from Ookla Speedtest Open Data quarterly mobile speed test tiles. Tiles are spatially joined to Census 2020 block groups using intersection. Per-tile average upload speed (avg_u_kbps field) is aggregated to block groups using device-weighted means. Quarterly values are averaged within each year. Tract and county values are simple means of constituent block groups.

Derived from Ookla Speedtest Open Data quarterly mobile tiles. A tile qualifies if avg_d_kbps >= 25,000 and avg_u_kbps >= 3,000. The percentage is the device-weighted share of qualifying tiles within each block group. Quarterly values are averaged within each year.

Derived from Ookla Speedtest Open Data quarterly mobile tiles. A tile qualifies if avg_d_kbps >= 100,000 and avg_u_kbps >= 20,000. The percentage is the device-weighted share of qualifying tiles within each block group. Quarterly values are averaged within each year.

## Coverage
- **Temporal coverage:** 2019–2025 (quarterly Ookla Open Data)
- **Geographic levels:** Block Group, County, Tract
- **Coverage areas:** National Capital Region (DC metro), Virginia (statewide)

## Methodology
Device-weighted average fixed broadband download speed in megabits per second (Mb/s), derived from Ookla Speedtest Open Data quarterly fixed-line speed test tiles spatially joined to Census 2020 block groups. Each tile's average download speed (avg_d_kbps) is weighted by the number of unique devices tested. Quarterly block group values are averaged within each year. Tract and county values are simple means of their constituent block groups.

Device-weighted average fixed broadband upload speed in megabits per second (Mb/s), derived from Ookla Speedtest Open Data quarterly fixed-line speed test tiles spatially joined to Census 2020 block groups. Each tile's average upload speed (avg_u_kbps) is weighted by the number of unique devices tested. Quarterly block group values are averaged within each year. Tract and county values are simple means of their constituent block groups.

Percentage of tested devices with download speed at or above 25 Mb/s and upload speed at or above 3 Mb/s, the FCC's former broadband threshold. Derived from Ookla Speedtest Open Data quarterly fixed-line speed test tiles spatially joined to Census 2020 block groups. At the tile level, a tile meets the threshold if its average download speed >= 25,000 kbps and average upload speed >= 3,000 kbps. The percentage is calculated as the share of devices in qualifying tiles relative to total devices in each block group.

Percentage of tested devices with download speed at or above 100 Mb/s and upload speed at or above 20 Mb/s, a higher-tier broadband threshold suitable for multi-device streaming and large file transfers. Derived from Ookla Speedtest Open Data quarterly fixed-line speed test tiles spatially joined to Census 2020 block groups. At the tile level, a tile meets the threshold if its average download speed >= 100,000 kbps and average upload speed >= 20,000 kbps. The percentage is calculated as the share of devices in qualifying tiles relative to total devices in each block group.

Percentage of tested mobile devices with download speed at or above 25 Mb/s and upload speed at or above 3 Mb/s. Derived from Ookla Speedtest Open Data quarterly mobile speed test tiles spatially joined to Census 2020 block groups. At the tile level, a tile meets the threshold if its average download speed >= 25,000 kbps and average upload speed >= 3,000 kbps. The percentage is calculated as the share of devices in qualifying tiles relative to total devices in each block group.

Percentage of tested mobile devices with download speed at or above 100 Mb/s and upload speed at or above 20 Mb/s. Derived from Ookla Speedtest Open Data quarterly mobile speed test tiles spatially joined to Census 2020 block groups. At the tile level, a tile meets the threshold if its average download speed >= 100,000 kbps and average upload speed >= 20,000 kbps. The percentage is calculated as the share of devices in qualifying tiles relative to total devices in each block group.

## Source Tables
- [Quarterly fixed-line performance tiles (S3 bucket)](https://github.com/teamookla/ookla-open-data)
- [TIGER/Line Shapefiles, Census 2020 Block Groups](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html)
- [Quarterly mobile performance tiles (S3 bucket)](https://github.com/teamookla/ookla-open-data)

## Measures (8)
*Note on naming conventions: Measures containing `_geo20` are computed using 2020 Census geographic boundaries.*

- **avg_down_speed_geo20**: Average download speed (Mb/s), device-weighted (device-weighted mean, unit: Mb/s)
  Average download speed weighted by number of devices.
- **avg_up_speed_geo20**: Average upload speed (Mb/s), device-weighted (device-weighted mean, unit: Mb/s)
  Average upload speed weighted by number of devices.
- **perc_above_25_3_geo20**: Percent of devices above 25/3 Mb/s broadband threshold (device-weighted percentage, unit: percent)
  Percent of devices with speeds above 25/3 Mb/s (FCC broadband threshold).
- **perc_above_100_20_geo20**: Percent of devices above 100/20 Mb/s broadband threshold (device-weighted percentage, unit: percent)
  Percent of devices with speeds above 100/20 Mb/s (fast broadband threshold).
- **mobile_avg_down_speed_geo20**: Average mobile download speed (Mb/s), device-weighted (device-weighted mean, unit: Mb/s)
  Average mobile download speed weighted by number of devices.
- **mobile_avg_up_speed_geo20**: Average mobile upload speed (Mb/s), device-weighted (device-weighted mean, unit: Mb/s)
  Average mobile upload speed weighted by number of devices.
- **mobile_perc_above_25_3_geo20**: Percent of mobile devices above 25/3 Mb/s broadband threshold (device-weighted percentage, unit: percent)
  Percent of mobile devices with speeds above 25/3 Mb/s.
- **mobile_perc_above_100_20_geo20**: Percent of mobile devices above 100/20 Mb/s broadband threshold (device-weighted percentage, unit: percent)
  Percent of mobile devices with speeds above 100/20 Mb/s.

## Data Sources
- [Ookla Speedtest Open Data (accessed 2025)](https://www.ookla.com/ookla-for-good/open-data)
- [U.S. Census Bureau (accessed 2025)](https://www.census.gov/geographies.html)

## File Format
Data files are provided as xz-compressed CSVs (`.csv.xz`) with the following columns: `geoid`, `year`, `measure`, `value`, `moe` (margin of error, where available), `region_type`, `data_method` (observed, modeled, scaled, interpolated, or extrapolated). A `measure_info.json` file provides per-measure metadata.
