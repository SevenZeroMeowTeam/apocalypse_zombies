#!/usr/bin/env python3
"""Bake the radial glow texture used by SkyWeatherEffects' sun/moon halos.

Why: the halo quad used to sample sun.png / the moon's full-moon cell and stretch
it over a quad twice the size of the real body — in game that stacked a huge
additive disc (with a hard rim) on top of the actual sun/moon, reading as a
"giant ring around a small disc" (6.3.1 field report). A halo is not a second
celestial body; it is a smooth radial falloff.

This bakes `halo.png`: 256x256 RGBA, neutral white, alpha = 0.9 * (1 - d)^2.2
(d = normalized distance from centre). The Java side already tints it per body
(warm white for the sun, cold blue for the moon) via setShaderColor, and the
quads keep their sizes (sun 62, moon 44 half-extent) — only the texture changes.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: python -m pip install pillow")

TARGET = Path("src/main/resources/assets/apocalypse_zombies/textures/environment/halo.png")
SIZE = 256
PEAK = 0.90
FALLOFF = 2.2


def main() -> None:
    img = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    px = img.load()
    centre = (SIZE - 1) / 2.0
    max_d = math.hypot(centre, centre)
    for y in range(SIZE):
        for x in range(SIZE):
            d = math.hypot(x - centre, y - centre) / max_d
            a = PEAK * max(0.0, 1.0 - d) ** FALLOFF
            px[x, y] = (255, 255, 255, round(a * 255))
    img.save(TARGET, format="PNG")
    print(f"wrote {TARGET} ({SIZE}x{SIZE}, alpha peak {PEAK}, falloff {FALLOFF})")


if __name__ == "__main__":
    main()
