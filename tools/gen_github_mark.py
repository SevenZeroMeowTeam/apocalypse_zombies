#!/usr/bin/env python3
"""Bake the GitHub octocat mark into a GUI texture (white on transparent).

Source of truth: the official Primer octicon ``mark-github-16`` SVG path
(vendored from @primer/octicons 19.8.0, MIT). The repo network is flaky, so the
path data is kept inline here instead of being fetched at bake time.

Rendering: matplotlib rasterizes the path (the octicon uses only M/c/a/A/Z
commands — cubics are flattened to polylines, arcs via the SVG endpoint
parameterization), then a LANCZOS downscale to 16x16 — the classic favicon
size. In-game it is blitted at 8x8 GUI units: at GUI scale 2 that is a 1:1
texel mapping (crisp); scales 1 and 3 stay acceptable.

Re-run after touching the path data:  python tools/gen_github_mark.py
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: python -m pip install pillow")

try:
    import matplotlib.path as mpath
    import numpy as np
except ImportError:  # pragma: no cover
    sys.exit("matplotlib + numpy required: python -m pip install matplotlib numpy")

TARGET = Path("src/main/resources/assets/apocalypse_zombies/textures/gui/github_mark.png")
HIRES = 512             # rasterize here, then LANCZOS down
OUT_SIZE = 16           # favicon-size bake; blitted at 8x8 GUI units
ALPHA_FLOOR = 24        # drop the faintest AA halo, keep the 1-2 px ear/leg detail

# @primer/octicons 19.8.0 — build/svg/mark-github-16.svg (viewBox 0 0 16 16)
OCTICON_PATH = (
    "M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 "
    "0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 "
    "0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18"
    "-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 "
    "1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44"
    ".55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38"
    ".01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21"
    "-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"
)

# SVG compact notation packs numbers tightly ("-.4.08-.55" = -.4, .08, -.55),
# so a number may never span two dots: int part OR fractional-only form.
TOKEN = re.compile(r"([MmCcAaZzLlHhVvSs])|(-?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?)")


def arc_points(p0, rx, ry, xrot_deg, large, sweep, p1, steps=48):
    """SVG arc -> polyline (endpoint parameterization per the SVG spec)."""
    if abs(rx) < 1e-9 or abs(ry) < 1e-9:
        return [p0, p1]
    (x1, y1), (x2, y2) = p0, p1
    phi = math.radians(xrot_deg)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    x1p = cos_p * dx + sin_p * dy
    y1p = -sin_p * dx + cos_p * dy
    rx, ry = abs(rx), abs(ry)
    lam = x1p * x1p / (rx * rx) + y1p * y1p / (ry * ry)
    if lam > 1.0:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    if den == 0:
        return [p0, p1]
    c = math.sqrt(max(0.0, num) / den)
    if large == sweep:
        c = -c
    cxp = c * rx * y1p / ry
    cyp = -c * ry * x1p / rx
    cx = cos_p * cxp - sin_p * cyp + (x1 + x2) / 2.0
    cy = sin_p * cxp + cos_p * cyp + (y1 + y2) / 2.0

    def signed_angle(ux, uy, vx, vy):
        dot = ux * vx + uy * vy
        n = math.hypot(ux, uy) * math.hypot(vx, vy)
        a = math.acos(max(-1.0, min(1.0, dot / n))) if n else 0.0
        if (sweep and a < 0.0) or (not sweep and a > 0.0):
            a = -a
        return a

    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    a0 = signed_angle(ux, uy, vx, vy)
    pts = []
    for i in range(1, steps):
        t = a0 * i / (steps - 1)
        px = cx + rx * (cos_p * math.cos(t) - sin_p * math.sin(t))
        py = cy + ry * (sin_p * math.cos(t) + cos_p * math.sin(t))
        pts.append((px, py))
    return [p0] + pts + [p1]


def flatten_path(d: str):
    """SVG path -> list of vertex lists (one per subpath)."""
    toks = [(m.group(1), m.group(2)) for m in TOKEN.finditer(d)]
    i = 0
    cur = start = (0.0, 0.0)
    subpaths = []
    pts: list = []
    cmd = None

    def read(n):
        nonlocal i
        vals = []
        while len(vals) < n and i < len(toks):
            kind, _raw = toks[i]
            if kind:            # a new command letter ends the number run
                break
            vals.append(float(toks[i][1]))
            i += 1
        if len(vals) < n:
            raise ValueError(f"path truncated, need {n} numbers, got {vals}")
        return vals

    while i < len(toks):
        kind, _raw = toks[i]
        if kind:
            cmd = kind
            i += 1
        if cmd in ("Z", "z"):
            if pts:
                subpaths.append(pts)
                pts = []
            cur = start
        elif cmd in ("M", "m"):
            x, y = read(2)
            if pts:
                subpaths.append(pts)
                pts = []
            cur = (start[0] + x, start[1] + y) if cmd == "m" else (x, y)
            start = cur
            pts.append(cur)
            cmd = "L" if cmd == "M" else "l"   # implicit lineto afterwards
        elif cmd in ("L", "l"):
            x, y = read(2)
            cur = (cur[0] + x, cur[1] + y) if cmd == "l" else (x, y)
            pts.append(cur)
        elif cmd in ("C", "c"):
            x1, y1, x2, y2, x, y = read(6)
            if cmd == "c":
                x1 += cur[0]; y1 += cur[1]; x2 += cur[0]; y2 += cur[1]; x += cur[0]; y += cur[1]
            for k in range(1, 25):
                t = k / 24.0
                mt = 1.0 - t
                px = mt**3 * cur[0] + 3 * mt**2 * t * x1 + 3 * mt * t**2 * x2 + t**3 * x
                py = mt**3 * cur[1] + 3 * mt**2 * t * y1 + 3 * mt * t**2 * y2 + t**3 * y
                pts.append((px, py))
            cur = (x, y)
        elif cmd in ("A", "a"):
            rx, ry, rot, large, sweep, x, y = read(7)
            if cmd == "a":
                x += cur[0]; y += cur[1]
            pts.extend(arc_points(cur, rx, ry, rot, int(large), int(sweep), (x, y)))
            cur = (x, y)
        else:
            raise ValueError(f"unsupported command {cmd!r} in octicon path")
    if pts:
        subpaths.append(pts)
    return subpaths


def main() -> None:
    subs = flatten_path(OCTICON_PATH)
    print(f"subpaths: {len(subs)}, vertices: {sum(len(s) for s in subs)}")
    if len(subs) != 1:
        raise SystemExit("expected a single closed outline, got " + str(len(subs)))
    xs = [p[0] for p in subs[0]]
    ys = [p[1] for p in subs[0]]
    print(f"  bbox x {min(xs):.2f}..{max(xs):.2f}  y {min(ys):.2f}..{max(ys):.2f}")

    path = mpath.Path(subs[0])
    grid = np.mgrid[0:HIRES, 0:HIRES]
    # sample at pixel centers, mapped into the 16x16 viewBox
    pts = np.stack([(grid[1].ravel() + 0.5) * 16.0 / HIRES,
                    (grid[0].ravel() + 0.5) * 16.0 / HIRES], axis=-1)
    mask = path.contains_points(pts).reshape(HIRES, HIRES)

    img = np.zeros((HIRES, HIRES, 4), dtype="uint8")
    img[..., 0] = 255
    img[..., 1] = 255
    img[..., 2] = 255
    img[..., 3] = mask * 255
    # BOX = exact per-cell area coverage of the mask; LANCZOS would ring on a
    # hard-edge mask and wash out the 1-2 px ear/leg features.
    small = Image.fromarray(img).resize((OUT_SIZE, OUT_SIZE), Image.BOX)

    px = small.load()
    for y in range(OUT_SIZE):
        for x in range(OUT_SIZE):
            r, g, b, a = px[x, y]
            a = 0 if a < ALPHA_FLOOR else a
            px[x, y] = (255, 255, 255, a)
    small.save(TARGET, format="PNG")
    print(f"wrote {TARGET} ({OUT_SIZE}x{OUT_SIZE})")


if __name__ == "__main__":
    main()
