# Changelog

All notable changes to this project will be documented in this file. The format
is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-19

### Added
- Core ontology (regions, scenarios, data methods, Data Cube components) and SHACL shapes.
- `long_format_to_cube` for standard (`year`) and energy (`datetime` + `scenario`) long-format files.
- Region IRIs and GeoJSON-label helpers; shared namespaces.
- `write_turtle` / `read_turtle` with transparent `.ttl.xz` compression.
