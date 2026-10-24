#!/usr/bin/env python3
"""Bake the sky cloud map from a real reference photo (user-supplied), full 1024 res.

Goal (6.3.1, after two field reports): puffy cumulus like the reference photo,
not a mosaic of 12-unit blocks.

Resolution matters and 256 was a wrong constraint: LevelRenderer#buildClouds maps
the whole texture over a fixed 3072-unit period (UV = grid_coord / 256), so
**one texel = 3072 / texture_width units**. At 256 the photo's fluffy wisps
(1-5 px in the source) collapse into blocky 12-unit cells; at 1024 each texel is
3 units and the wisps survive. Vanilla samples the mesh quads with linear
filtering, so the alpha gradient renders smoothly inside each quad.

Pipeline (deterministic, no seed):
  1. cloudness field from the photo: clouds are bright and colour-neutral while
     the gaps (sky/sea) are darker and blue-shifted, so
     cloudness = lum - 0.8 * blueness, stretched to the 2%..98% percentile range.
  2. make it tileable at full res: cross-fade with the half-period shift
     (128 px edge band — the field is smooth, the band is invisible).
  3. threshold with a soft band: the cut is chosen automatically so the covered
     fraction lands on TARGET (thick cores keep, thin haze drops).
  4. RGB = flat white; vanilla's buildClouds shades top/bottom/sides via vertex
     colours; the alpha soft edge gives the fluffy borders.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: python - m pip install pillow")

PHOTO = Path("dsh-image-gen/image-a516f86e.png")   # user's reference #2
TARGET = Path("src/main/resources/assets/apocalypse_zombies/textures/environment/clouds.png")
SIZE = 1024               # full photo resolution: 1 texel = 3 world units
TARGET_COVERAGE = 0.30    # scattered puffs: enough blue sky between clouds
SOFT_BAND = 0.12          # wide alpha ramp = fluffy feathered edges
BLUE_BIAS = 0.8           # how strongly blue gaps are pushed out of the cloud field
TILE_BAND = 128           # cross-fade band for tileability (1/8 of the canvas)
BRIGHTEN = 1.08           # photo RGB is kept (real cloud shading!) and lifted a
                          # little to compensate for vanilla's vertex dimming


def cloudness_field(photo: Image.Image) -> Image.Image:
    img = photo.convert("RGB")
    px = list(img.getdata())
    vals = [0.299 * r + 0.587 * g + 0.114 * b - BLUE_BIAS * (b - (r + g) / 2.0)
            for r, g, b in px]
    order = sorted(vals)                       # 分位数用排序副本；空间结构留在 vals
    lo = order[int(len(order) * 0.02)]
    hi = order[int(len(order) * 0.98)]
    span = max(1e-6, hi - lo)
    field = Image.new("L", img.size)
    field.putdata([max(0, min(255, round((v - lo) * 255.0 / span))) for v in vals])
    return field


def make_tileable(field: Image.Image, band: int) -> Image.Image:
    """Cross-fade with the half-period shift so opposite edges agree.

    Weight = 1 at the canvas edges (use the shifted copy there — that is what
    makes out(0) meet out(width-1)), fading to 0 in the interior (keep the
    original photo)."""
    width, height = field.size
    f = field.load()
    out = Image.new("L", (width, height))
    o = out.load()
    half_x, half_y = width // 2, height // 2
    for y in range(height):
        wy = min(1.0, min(y, height - 1 - y) / band)
        for x in range(width):
            wx = min(1.0, min(x, width - 1 - x) / band)
            w = 1.0 - max(wx, wy)          # 边缘 1（用平移图衔接），内部 0（保原片）
            base = f[x, y]
            shifted = f[(x + half_x) % width, (y + half_y) % height]
            o[x, y] = round(base * (1.0 - w) + shifted * w)
    return out


def main() -> None:
    if not PHOTO.is_file():
        sys.exit(f"missing reference photo: {PHOTO}")
    photo = Image.open(PHOTO)
    if photo.size[0] != SIZE or photo.size[1] != SIZE:
        photo = photo.resize((SIZE, SIZE), Image.LANCZOS)
    field = cloudness_field(photo)
    tiled = make_tileable(field, TILE_BAND)

    vals = sorted(tiled.getdata())
    cut = vals[int(len(vals) * (1.0 - TARGET_COVERAGE))]
    low, high = cut - 255 * SOFT_BAND / 2.0, cut + 255 * SOFT_BAND / 2.0

    lut = []
    for v in range(256):
        if v <= low:
            lut.append(0)
        elif v >= high:
            lut.append(255)
        else:
            lut.append(round((v - low) * 255.0 / (high - low)))
    alpha = tiled.point(lut)

    # Puffy shading from two aligned sources (both already tileable):
    #   * the cloudness field: thick cores read bright, thin edges read grey;
    #   * the alpha itself: the soft skirt is darker, like the shaded underside
    #     of a puff. Vanilla multiplies vertex colours on top (top 0.7 / sides
    #     0.8 / bottom 1.0), so keep the texture bright overall.
    f_px = tiled.load()
    a_px = alpha.load()
    out = Image.new("RGBA", (SIZE, SIZE))
    o = out.load()
    for y in range(SIZE):
        for x in range(SIZE):
            a = a_px[x, y]
            shade = (0.86 + 0.14 * a / 255.0) * (0.80 + 0.20 * f_px[x, y] / 255.0)
            r = min(255, round(252 * BRIGHTEN * shade))
            g = min(255, round(252 * BRIGHTEN * shade))
            b = min(255, round(255 * BRIGHTEN * shade))
            o[x, y] = (r, g, b, a)
    out.save(TARGET, format="PNG")

    hist = alpha.histogram()
    solid = sum(hist[192:])
    soft = sum(hist[32:192])
    print(f"clouds.png baked from {PHOTO.name}: {SIZE}x{SIZE} "
          f"(1 texel = {3072 // SIZE} world units, period 3072)")
    print(f"  threshold {cut}/255, coverage {TARGET_COVERAGE:.0%} target")
    print(f"  solid px {solid} ({solid / (SIZE * SIZE):.1%}), soft-edge px {soft}")


if __name__ == "__main__":
    main()
