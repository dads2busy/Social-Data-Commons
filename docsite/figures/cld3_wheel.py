"""Draw the CLD3 process wheel in the site's ramp palette.

Redraws the Social and Decision Analytics Division's Community Learning
through Data-Driven Discovery diagram with the same structure and labels:
an outer wheel of stakeholder interaction, a middle wheel of the data-driven
learning cycle, and the Data Science Framework at the centre. Written to
``docsite/assets/cld3-wheel.svg`` and inlined into the approach page with a
snippet so the page's own typeface applies.

Run from the repo root::

    uv run python docsite/figures/cld3_wheel.py
"""

from __future__ import annotations

import math
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "assets" / "cld3-wheel.svg"

INK = "#14233a"
PAPER = "#f6f8fa"
RAMP = ["#cff0e5", "#7fd1b9", "#2fa48e", "#1f6f8b", "#1d4f7a"]

SIZE = 640
CX = CY = SIZE / 2
OUTER = (312, 250)  # outer wheel radii (outside, inside)
MIDDLE = (238, 166)  # middle wheel radii
INNER = 150  # centre circle radius
GAP_DEG = 2.5  # breathing room between segments
CHEVRON_DEG = 4  # how far each segment's point reaches into the next

OUTER_LABELS = [
    "Engage community stakeholders to identify issues",
    "Partner with subject experts",
    "Provide data insight for decision makers",
    "Share learnings to drive change",
    "Support the community in next steps",
]
MIDDLE_LABELS = ["Discover data", "Integrate data", "Act", "Measure and evaluate", "Redirect"]
START_DEG = -90  # first segment begins at nine o'clock and the cycle runs clockwise


def pt(r: float, deg: float) -> tuple[float, float]:
    """Point on a circle; 0° is twelve o'clock, degrees increase clockwise."""
    a = math.radians(deg - 90)
    return (CX + r * math.cos(a), CY + r * math.sin(a))


def arc(r: float, a1: float, a2: float, sweep: int) -> str:
    x, y = pt(r, a2)
    large = 1 if abs(a2 - a1) > 180 else 0
    return f"A{r:.1f} {r:.1f} 0 {large} {sweep} {x:.1f} {y:.1f}"


def chevron(r_out: float, r_in: float, a1: float, a2: float, fill: str, cls: str = "") -> str:
    """A ring segment whose leading edge is a point and trailing edge a notch."""
    r_mid = (r_out + r_in) / 2
    x0, y0 = pt(r_out, a1)
    d = (
        f"M{x0:.1f} {y0:.1f} {arc(r_out, a1, a2, 1)} "
        f"L{pt(r_mid, a2 + CHEVRON_DEG)[0]:.1f} {pt(r_mid, a2 + CHEVRON_DEG)[1]:.1f} "
        f"L{pt(r_in, a2)[0]:.1f} {pt(r_in, a2)[1]:.1f} {arc(r_in, a2, a1, 0)} "
        f"L{pt(r_mid, a1 + CHEVRON_DEG)[0]:.1f} {pt(r_mid, a1 + CHEVRON_DEG)[1]:.1f} Z"
    )
    klass = f' class="{cls}"' if cls else ''
    return f'<path{klass} d="{d}" fill="{fill}"/>'


def label(idx: str, r: float, a1: float, a2: float, text: str, color: str, size: float, weight: int) -> str:
    """Text along an arc, flipped on the lower half so it always reads upright."""
    mid = ((a1 + a2) / 2) % 360
    upright = not (90 < mid < 270)
    if upright:
        x, y = pt(r, a1)
        d = f"M{x:.1f} {y:.1f} {arc(r, a1, a2, 1)}"
    else:
        x, y = pt(r, a2)
        d = f"M{x:.1f} {y:.1f} {arc(r, a2, a1, 0)}"
    return (
        f'<path id="{idx}" d="{d}" fill="none"/>'
        f'<text font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="middle" dominant-baseline="middle">'
        f'<textPath href="#{idx}" startOffset="50%">{text}</textPath></text>'
    )


def main() -> None:
    n = len(OUTER_LABELS)
    step = 360 / n
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" role="img" '
        'aria-labelledby="cld3-title" font-family="Public Sans, system-ui, sans-serif">',
        "<title id=\"cld3-title\">The CLD3 process: an outer wheel of continuous stakeholder interaction, "
        "a middle wheel of discover, integrate, act, measure and evaluate, and redirect, "
        "and the Data Science Framework at the centre</title>",
    ]
    for i in range(n):
        a1 = START_DEG + i * step + GAP_DEG / 2
        a2 = START_DEG + (i + 1) * step - GAP_DEG / 2
        parts.append(chevron(*OUTER, a1, a2, INK, "cld3-outer"))
        parts.append(label(f"o{i}", (OUTER[0] + OUTER[1]) / 2, a1 + 5, a2 - 1, OUTER_LABELS[i], PAPER, 12, 500))
        parts.append(chevron(*MIDDLE, a1, a2, RAMP[i]))
        text_color = INK if i < 2 else PAPER
        parts.append(label(f"m{i}", (MIDDLE[0] + MIDDLE[1]) / 2, a1 + 5, a2 - 1, MIDDLE_LABELS[i], text_color, 16, 700))
    parts.append(f'<circle class="cld3-inner" cx="{CX}" cy="{CY}" r="{INNER}" fill="{PAPER}" stroke="{INK}" stroke-width="2"/>')
    parts.append(
        f'<text class="cld3-inner-text" x="{CX}" y="{CY}" fill="{INK}" font-size="22" font-weight="700" text-anchor="middle">'
        f'<tspan x="{CX}" dy="-0.3em">Data Science</tspan><tspan x="{CX}" dy="1.25em">Framework</tspan></text>'
    )
    parts.append("</svg>\n")
    OUT.write_text("".join(parts))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
