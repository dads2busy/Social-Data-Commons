# sdc-census10to20

Redistribute 2010-2019 census data onto 2020 census boundaries.

This package is the Python port of the R package
[`sdc.census10to20`](https://uva-bi-sdad.github.io/sdc.censes10to20/). It is
used by the [Social Data Commons](https://github.com/dads2busy/Social-Data-Commons) pipelines to
make tract- and block-group-level data comparable across the boundary changes
that occurred between the 2010 and 2020 decennial censuses.

## Install

```bash
pip install sdc-census10to20
```

## What it does

Census tract and block-group boundaries change between decennial censuses.
A single 2010 tract may become a single 2020 tract with the same boundary
(*same*), be split into several 2020 tracts whose union equals the original
(*split*), or have its boundary shift so it only partially overlaps with one
or more 2020 tracts (*moved*).

For each case this package can:

1. Build a crosswalk from the official Census relationship files
   ([`get_2010_2020_bound_changes`][sdc_census10to20.get_2010_2020_bound_changes],
   [`create_crosswalk`][sdc_census10to20.create_crosswalk]).
2. Redistribute values from 2010 boundaries onto 2020 boundaries — pass-through
   for *same*/*split*, area-proportional for *moved*
   ([`convert_2010_to_2020_bounds`][sdc_census10to20.convert_2010_to_2020_bounds]).
3. Take a long-format dataset spanning multiple years and emit both the
   original `_geo10`-suffixed measure and the redistributed `_geo20`-suffixed
   measure ([`standardize_all`][sdc_census10to20.standardize_all]).

See the [Getting Started](getting-started.md) article for a worked
Virginia example.
