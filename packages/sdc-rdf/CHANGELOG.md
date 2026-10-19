# Changelog

All notable changes to this project will be documented in this file. The format
is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-10-19

### Added
- `cube_to_long_format(graph, dataset)`: rebuilds the long-format frame from the graph (inverse
  of `long_format_to_cube`), so pipeline CSVs can be generated from RDF.
- Datasets record `sdc:periodConvention` (year / datetime / year anchor / hour-of-day profile)
  so the inverse knows how to rebuild `year` / `datetime`.
- `default_scenario=` on `long_format_to_cube` → `sdc:defaultScenario` on the dataset.
- `read_csv_exact(path)`: reads distribution CSVs with round-trip float parsing and text IDs.
  pandas' default float parser can be off by one ULP, which would break CSV regeneration.

### Changed
- Observation values and margins of error are written as plain-notation `xsd:decimal`
  (`5e-06` → `0.000005`); exponent forms are not valid `xsd:decimal` lexicals.

## [0.3.0] - 2026-10-19

### Added
- `year_anchor=True` option on `long_format_to_cube` for static energy scenario files whose
  `datetime = YYYY-01-01` marks the scenario year: emits refPeriod = the year (xsd:gYear)
  instead of a literal 1 January date.

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
