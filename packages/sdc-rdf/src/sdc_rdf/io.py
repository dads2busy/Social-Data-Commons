"""Load bundled ontology/shape files and write graphs."""

from __future__ import annotations

import lzma
from importlib.resources import files
from pathlib import Path

import pandas as pd
from rdflib import Graph

# Identifier columns that must stay text (leading zeros, mixed numeric/alpha IDs).
ID_COLUMNS = ["geoid", "facility_id", "source_id", "station_id"]


def load_core_ontology() -> Graph:
    """The commons core ontology (``sdc_rdf/ontology/core.ttl``)."""
    return Graph().parse(files("sdc_rdf") / "ontology" / "core.ttl", format="turtle")


def load_core_shapes() -> Graph:
    """SHACL shapes for cube output (``sdc_rdf/shapes/core.ttl``)."""
    return Graph().parse(files("sdc_rdf") / "shapes" / "core.ttl", format="turtle")


FORMATS = {".ttl": "turtle", ".nt": "nt"}


def _format(path: Path) -> tuple[str, bool]:
    """(rdflib format, xz-compressed?) from a ``.ttl[.xz]`` / ``.nt[.xz]`` suffix."""
    compressed = path.suffix == ".xz"
    suffix = Path(path.stem).suffix if compressed else path.suffix
    if suffix not in FORMATS:
        raise ValueError(f"{path.name}: expected a .nt, .nt.xz, .ttl or .ttl.xz path")
    return FORMATS[suffix], compressed


def write_graph(g: Graph, path: str | Path) -> Path:
    """Serialize ``g`` in the format named by the suffix (``.nt``/``.ttl``, optionally ``.xz``).

    Pipeline outputs use sorted, xz-compressed N-Triples (``.nt.xz``): linear to
    write, byte-stable across regenerations, and one triple per line for clean
    diffs. rdflib's Turtle writer is quadratic on IRIs whose last segment starts
    with a digit (GEOIDs, numeric IDs), so keep ``.ttl`` for small ad-hoc exports.
    """
    path = Path(path)
    fmt, compressed = _format(path)
    if fmt == "turtle":
        data = g.serialize(format="turtle", encoding="utf-8")
    else:
        lines = g.serialize(format="nt", encoding="utf-8").splitlines(keepends=True)
        data = b"".join(sorted(line for line in lines if line.strip()))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(lzma.compress(data) if compressed else data)
    return path


def read_graph(path: str | Path) -> Graph:
    """Parse a ``.nt``/``.ttl`` file, optionally ``.xz``-compressed."""
    path = Path(path)
    fmt, compressed = _format(path)
    data = path.read_bytes()
    return Graph().parse(data=lzma.decompress(data) if compressed else data, format=fmt)


def read_csv_exact(path: str | Path) -> pd.DataFrame:
    """Read a distribution CSV for RDF conversion without losing information.

    Unlike ``sdc_core.io.read_data`` / ``read_point_data``, floats are parsed with
    ``float_precision="round_trip"``. pandas' default parser can be off by one ULP
    (e.g. "36.685957525459116" → 36.68595752545912), which would then be baked
    into the graph and break CSV regeneration. ID columns are read as text.
    """
    return pd.read_csv(path, dtype={c: str for c in ID_COLUMNS}, float_precision="round_trip")


def csv_rows(path: str | Path) -> tuple[str, list[str]]:
    """(header, sorted data lines) of a .csv or .csv.xz file."""
    path = Path(path)
    data = path.read_bytes()
    if path.suffix == ".xz":
        data = lzma.decompress(data)
    header, *rows = data.decode("utf-8").splitlines()
    return header, sorted(rows)


def assert_same_csv_rows(regenerated: str | Path, original: str | Path) -> None:
    """Fail unless two CSVs have the same header and the same rows (in any order).

    Used when staging dashboard files from a graph, to prove the graph-derived
    CSV matches the distribution CSV it was built from.
    """
    (h1, r1), (h2, r2) = csv_rows(regenerated), csv_rows(original)
    if h1 != h2:
        raise ValueError(f"{Path(regenerated).name}: header differs from {Path(original).name}")
    if r1 != r2:
        diff = len(set(r1) ^ set(r2))
        raise ValueError(f"{Path(regenerated).name}: {diff} rows differ from {Path(original).name}")
