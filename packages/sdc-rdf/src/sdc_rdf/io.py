"""Load bundled ontology/shape files and write graphs."""

from __future__ import annotations

import lzma
from importlib.resources import files
from pathlib import Path

from rdflib import Graph


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
        raise ValueError(f"{path.name}: expected a .ttl, .ttl.xz, .nt or .nt.xz path")
    return FORMATS[suffix], compressed


def write_graph(g: Graph, path: str | Path) -> Path:
    """Serialize ``g`` in the format named by the suffix (``.ttl``/``.nt``, optionally ``.xz``).

    Prefer N-Triples for large graphs: rdflib's Turtle writer slows down
    quadratically on IRIs whose last segment starts with a digit (GEOIDs,
    numeric facility IDs), while N-Triples is linear. N-Triples lines are
    sorted so regenerated files diff cleanly.
    """
    path = Path(path)
    fmt, compressed = _format(path)
    if fmt == "turtle":
        return write_turtle(g, path)
    lines = g.serialize(format="nt", encoding="utf-8").splitlines(keepends=True)
    data = b"".join(sorted(line for line in lines if line.strip()))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(lzma.compress(data) if compressed else data)
    return path


def read_graph(path: str | Path) -> Graph:
    """Parse a ``.ttl``/``.nt`` file, optionally ``.xz``-compressed."""
    path = Path(path)
    fmt, compressed = _format(path)
    data = path.read_bytes()
    return Graph().parse(data=lzma.decompress(data) if compressed else data, format=fmt)


def write_turtle(g: Graph, path: str | Path) -> Path:
    """Serialize ``g`` as Turtle, creating parent directories. ``.xz`` paths are lzma-compressed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = g.serialize(format="turtle", encoding="utf-8")
    if path.suffix == ".xz":
        data = lzma.compress(data)
    path.write_bytes(data)
    return path


def read_turtle(path: str | Path) -> Graph:
    """Parse a ``.ttl`` or lzma-compressed ``.ttl.xz`` file."""
    path = Path(path)
    data = path.read_bytes()
    if path.suffix == ".xz":
        data = lzma.decompress(data)
    return Graph().parse(data=data, format="turtle")
