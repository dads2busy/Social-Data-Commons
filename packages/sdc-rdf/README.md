# sdc-rdf

RDF knowledge-graph output for Social Data Commons pipelines. **Exploratory (0.1.0).**

- **Core ontology** (`src/sdc_rdf/ontology/core.ttl`, prefix `sdc:`): regions,
  scenarios, `data_method` values, and the RDF Data Cube components shared by every
  pipeline.
- **`long_format_to_cube`**: maps a long-format distribution frame (either the
  standard `year` variant or the energy `datetime` + `scenario` variant) to one
  `qb:DataSet` plus one `qb:Observation` per row. It mints a `qb:MeasureProperty`
  for each measure and carries the `measure_info.json` text over.
- **`write_turtle` / `read_turtle`**: Turtle I/O; `.ttl.xz` paths are lzma-compressed,
  matching the `.csv.xz` distribution convention.
- **SHACL shapes** (`src/sdc_rdf/shapes/core.ttl`) for the cube output.

Pipeline-specific entities (e.g. energy facilities) are pipeline-level ontology
extensions that build on these namespaces. See
`energy/PowerInfrastructure/rdf/` for the first one.

```python
from rdflib import Graph
from sdc_core.io import read_data
from sdc_rdf import bind_prefixes, long_format_to_cube, write_turtle

g = bind_prefixes(Graph())
long_format_to_cube(g, read_data(path), dataset_id=path.name.removesuffix(".csv.xz"),
                    label="…", measure_info=json.loads(measure_info_path.read_text()))
write_turtle(g, out_path)
```

## IRIs

All bases are placeholders under `https://w3id.org/sdc/` (not registered):

| Prefix | Base | Holds |
|---|---|---|
| `sdc:` | `…/ns#` | core vocabulary |
| `sdcm:` | `…/measure/` | one measure per `measure_info.json` key |
| `sdcid:` | `…/id/` | `county/{geoid}`, `tract/{geoid}`, `scenario/{label}`, `dataset/{file stem}`, `obs/{file stem}/{region_type}/{geoid}/{period}[/{scenario}]/{measure}` |

Measure IRIs assume measure names are unique across the commons.

## Tests

```bash
uv run --extra dev pytest packages/sdc-rdf/tests -v
```
