# Changelog

All notable changes to this project will be documented in this file. The format
is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-10-19

### Added
- `hour_of_day_profile=True` option on `long_format_to_cube` for energy files that follow the
  typical-day convention (`datetime = YYYY-01-01THH:00:00`): emits refPeriod = the year
  plus a new `sdc:hourOfDay` dimension instead of a literal 1 January timestamp.
- `sdc:hourOfDay` in the core ontology and SHACL shapes.
- `write_graph` / `read_graph`: format from suffix (`.nt`, `.ttl`, either optionally `.xz`).
  Sorted, xz-compressed N-Triples (`.nt.xz`) is the standard for pipeline outputs: linear to
  write and byte-stable. rdflib's Turtle writer is quadratic on digit-leading IRI segments
  such as GEOIDs.

### Removed
- `write_turtle` / `read_turtle`, superseded by `write_graph` / `read_graph`.

## [0.1.0] - 2026-10-19

### Added
- Core ontology (regions, scenarios, data methods, Data Cube components) and SHACL shapes.
- `long_format_to_cube` for standard (`year`) and energy (`datetime` + `scenario`) long-format files.
- Region IRIs and GeoJSON-label helpers; shared namespaces.
- `write_turtle` / `read_turtle` with transparent `.ttl.xz` compression.
