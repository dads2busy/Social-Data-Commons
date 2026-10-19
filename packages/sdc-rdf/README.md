# sdc-rdf

RDF knowledge-graph output for Social Data Commons pipelines. **Exploratory (0.3.0).**

- **Core ontology** (`src/sdc_rdf/ontology/core.ttl`, prefix `sdc:`): regions,
  scenarios, `data_method` values, and the RDF Data Cube components shared by every
  pipeline.
- **`long_format_to_cube`**: maps a long-format distribution frame (either the
  standard `year` variant or the energy `datetime` + `scenario` variant) to one
  `qb:DataSet` plus one `qb:Observation` per row. It mints a `qb:MeasureProperty`
  for each measure and carries the `measure_info.json` text over. Pass
  `hour_of_day_profile=True` for typical-day hourly files: they get refPeriod = the year
  plus an `sdc:hourOfDay` dimension, not a fake 1 January timestamp. Pass
  `year_anchor=True` for static scenario files whose `datetime` is a `YYYY-01-01`
  marker: refPeriod becomes the year.
- **`write_graph` / `read_graph`**: the format comes from the suffix (`.nt`, `.ttl`, either
  optionally `.xz`). **Pipeline outputs are sorted, xz-compressed N-Triples (`.nt.xz`)**,
  matching the `.csv.xz` convention. They are linear to write, byte-stable across
  regenerations, and diff one triple per line. Turtle is for hand-written files
  (ontologies, shapes) and small ad-hoc exports: rdflib's Turtle writer slows down
  quadratically on IRIs ending in digit-led segments (GEOIDs, numeric IDs).
- **SHACL shapes** (`src/sdc_rdf/shapes/core.ttl`) for the cube output.

Pipeline-specific entities (e.g. energy facilities) are pipeline-level ontology
extensions that build on these namespaces. See `energy/rdf/` (power facilities, EV
charging) for the first one.

```python
from rdflib import Graph
from sdc_core.io import read_data
from sdc_rdf import bind_prefixes, long_format_to_cube, write_graph

g = bind_prefixes(Graph())
long_format_to_cube(g, read_data(path), dataset_id=path.name.removesuffix(".csv.xz"),
                    label="…", measure_info=json.loads(measure_info_path.read_text()))
write_graph(g, out_path)  # e.g. va_ct_..._title.nt.xz
```

## IRIs

All bases are placeholders under `https://w3id.org/sdc/` (not registered):

| Prefix | Base | Holds |
|---|---|---|
| `sdc:` | `…/ns#` | core vocabulary |
| `sdcm:` | `…/measure/` | one measure per `measure_info.json` key |
| `sdcid:` | `…/id/` | `county/{geoid}`, `tract/{geoid}`, `scenario/{label}`, `dataset/{file stem}`, `obs/{file stem}/{region_type}/{geoid}/{period}[/h{HH}][/{scenario}]/{measure}` |

Measure IRIs assume measure names are unique across the commons.

## Tests

```bash
uv run --extra dev pytest packages/sdc-rdf/tests -v
```
