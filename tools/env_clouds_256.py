#!/usr/bin/env python3
"""Downsample the seamless cloud density map to 256x256.

Why 256: 1.20.1 LevelRenderer#buildClouds hardcodes the cloud UVs at 1/256 with a
12-unit quad per texel — the mesh assumes a 256x256 texture where **one pixel is
one cloud cell**. The 6.1.0 cloud map was baked at 1024x1024, so its top-left 256
region got stretched over the whole sky (giant blocky clouds — the in-game report
that shipped with 6.3.1). The texture slot override was already working; the size
was never vanilla-compatible.

Method: 4x box downsample (1024/4=256 keeps the tiling period, so the four-way
seamlessness survives), then a contrast ramp on alpha so cells read as cloud /
no-cloud instead of half-transparent mush after averaging.

Idempotent: reads from the same file it writes; re-running converges (the ramp
saturates and a 4x box downsample of a 256 image is itself). To restore the
1024 bake, re-run the 6.1.0 generator in art/sky/.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: python -m pip install pillow")

TARGET = Path("src/main/resources/assets/apocalypse_zombies/textures/environment/clouds.png")
SIZE = 256
# Alpha remap: below LOW = clear sky, above HIGH = full cloud, linear in between.
LOW, HIGH = 46, 200


def main() -> None:
    src = Image.open(TARGET).convert("RGBA")
    if src.size[0] != src.size[1] or src.size[0] % SIZE != 0:
        sys.exit(f"unexpected cloud canvas {src.size}, want a square multiple of {SIZE}")
    factor = src.size[0] // SIZE
    # Box average each 4x4 block: a cell is "how much cloud covers it" on average.
    small = src.resize((SIZE, SIZE), Image.BOX)

    # Contrast ramp on alpha; RGB (grey cloud colour) is kept as-is.
    r, g, b, a = small.split()
    lut = []
    for v in range(256):
        if v <= LOW:
            lut.append(0)
        elif v >= HIGH:
            lut.append(255)
        else:
            lut.append(round((v - LOW) * 255 / (HIGH - LOW)))
    a = a.point(lut)
    out = Image.merge("RGBA", (r, g, b, a))
    out.save(TARGET, format="PNG")
    alpha = out.getchannel("A")
    hist = alpha.histogram()
    covered = sum(hist[64:])
    print(f"clouds.png -> {SIZE}x{SIZE}, cells >=25% cloud: {covered} / {SIZE * SIZE} "
          f"({covered / (SIZE * SIZE):.1%})")


if __name__ == "__main__":
    main()
