# Ookla Speed — Validation Report

This topic was built natively in Python (no R conversion), so this report records data refreshes
rather than a conversion comparison.

## Data refresh — 2026-10-13 (v2.0.0 → v2.1.0)

Extended `years` in `pipeline.yaml` from 2019–2025 to 2019–2026 after `sdc sources check`
reported 2026 tiles in Ookla's S3 bucket. 2026 covers Q1–Q3 only (Q4 tiles are not yet published;
the ingest skips a missing quarter and averages the quarters it has). Re-run the pipeline after
Q4 2026 lands to complete the year.

| File | Rows | Years |
|---|---|---|
| `ncr_cttrbg_ookla_2019_2026_broadband_speed.csv.xz` | 317,800 | 2019–2026 |
| `va_hdcttr_ookla_2019_2026_broadband_speed.csv.xz` | 150,420 | 2019–2026 |

Overlap check (2019–2025) against the previous files: NCR 278,192 of 278,192 rows matched with
zero difference; VA county+tract 129,672 of 129,672 matched with zero difference (quarterly
block-group aggregates are cached in `data/working/bg_cache/`, so prior years are reproduced
bit-for-bit). The previous `*_2019_2025_*` distribution and dashboard files were removed.

2026 sanity check (NCR county medians): fixed download 363.5 Mb/s (2025: 331.1), fixed upload
172.6 (155.0), mobile download 298.4 (300.5); share of devices above 25/3 Mb/s 99.6% (99.6%).

Code change in the same refresh: `ingest.py` now sets `data_method = "observed"`. The committed
files had this column populated by a one-off repo-wide patch (commit cb1b331), so a plain re-run
had dropped it.
