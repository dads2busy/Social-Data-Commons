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
