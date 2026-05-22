# Changelog

All notable changes to this project will be documented in this file. The format
is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-05-22

### Added
- Initial Python port of the R `sdc.census10to20` package.

### Fixed
- `get_2010_2020_bound_changes` now matches the R `case_when` first-match-wins
  ordering. A previous Python port in `sdc_core.geo` applied masks sequentially,
  causing one-to-one unchanged tracts to be labelled `"split"` instead of
  `"same"`. Downstream behaviour of `convert_2010_to_2020_bounds` is unaffected
  because it treats `"same"` and `"split"` identically.
- `get_2010_2020_bound_changes`: load Census relationship file with `type_change` classification.
- `create_crosswalk`: build a combined crosswalk for tract- and block-group-level GEOIDs.
- `convert_2010_to_2020_bounds`: redistribute a single year/measure onto 2020 boundaries.
- `standardize_all`: convenience wrapper for long-format SDC data (`geoid`, `year`, `measure`, `value`, `moe`).
