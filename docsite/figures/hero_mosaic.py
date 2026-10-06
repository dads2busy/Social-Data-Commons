"""Render the home-page hero mosaic from real census block-group geometry.

Reads the Arlington County block groups that ship with the sdc-catchment
article and writes ``docsite/assets/hero-mosaic.svg``: each block group is a
polygon filled from the site's sequential ramp by area quantile (smaller block
groups, which are the denser ones, get the darker steps), so the graphic reads
as a choropleth of the site's own subject matter.

Run from the repo root::

    uv run python docsite/figures/hero_mosaic.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "packages" / "sdc-catchment" / "articles" / "data" / "county_bgs.geojson"
OUT = ROOT / "assets" / "hero-mosaic.svg"

RAMP = ["#CFF0E5", "#7FD1B9", "#2FA48E", "#1F6F8B", "#1D4F7A", "#14233A"]
WIDTH = 640  # SVG user units; height follows the geometry's aspect ratio


def ring_area(ring: list[list[float]]) -> float:
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:]))) / 2


def main() -> None:
    features = json.loads(SRC.read_text())["features"]
    polys = [f["geometry"]["coordinates"] for f in features]  # MultiPolygon: [[ring, ...], ...]

    xs = [c[0] for mp in polys for poly in mp for ring in poly for c in ring]
    ys = [c[1] for mp in polys for poly in mp for ring in poly for c in ring]
    lat0 = math.radians((min(ys) + max(ys)) / 2)
    kx = math.cos(lat0)  # equirectangular correction so shapes are not stretched

    def proj(c: list[float]) -> tuple[float, float]:
        return ((c[0] - min(xs)) * kx, (max(ys) - c[1]))

    span_x = (max(xs) - min(xs)) * kx
    span_y = max(ys) - min(ys)
    scale = WIDTH / span_x
    height = round(span_y * scale)

    areas = [sum(ring_area([proj(c) for c in poly[0]]) for poly in mp) for mp in polys]
    order = sorted(range(len(areas)), key=lambda i: -areas[i])  # largest first -> lightest
    step = {i: min(len(RAMP) - 1, rank * len(RAMP) // len(order)) for rank, i in enumerate(order)}

    paths = []
    for i, mp in enumerate(polys):
        d = []
        for poly in mp:
            for ring in poly:
                pts = [proj(c) for c in ring]
                d.append("M" + " L".join(f"{x * scale:.1f} {y * scale:.1f}" for x, y in pts) + "Z")
        paths.append(f'<path fill="{RAMP[step[i]]}" d="{"".join(d)}"/>')

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" role="img" '
        f'aria-label="Census block groups of Arlington County, Virginia, shaded by density">'
        f'<g stroke="#F6F8FA" stroke-opacity="0.7" stroke-width="1.2" stroke-linejoin="round">'
        + "".join(paths)
        + "</g></svg>\n"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg)
    print(f"wrote {OUT} ({len(paths)} block groups, {OUT.stat().st_size // 1024} KB, {WIDTH}x{height})")


if __name__ == "__main__":
    main()
