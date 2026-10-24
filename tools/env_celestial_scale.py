#!/usr/bin/env python3
"""Rescale the visible sun/moon discs in the environment textures.

Currently CELESTIAL_SCALE = 0.75 (6.3.1: 75% of the 6.1.0 / 6.0.0 disc). Set it to 1.0
to restore the pristine textures byte-for-byte; lower shrinks the discs.

Why this exists
---------------
Vanilla draws the sun and the moon as fixed-size quads inside LevelRenderer
(30 and 20 units, LevelRenderer#renderSky / renderMoon). A texture cannot make
those quads smaller; the only lever is *what is painted inside the quad*. So the
disc is scaled down here and re-centred onto a canvas of exactly the same size,
which leaves transparent margin around it -- the quad keeps its vanilla size and
the celestial body on screen shrinks to CELESTIAL_SCALE of its former size.

    sun.png          1024x1024   single sprite
    moon_phases.png  2048x1024   4x2 phase atlas, one 512x512 cell per phase

Per-cell note for the moon atlas
--------------------------------
Each phase only paints *part* of the same disc (the unlit limb is transparent),
so a per-cell alpha bounding box would differ per phase and re-centring each of
them individually would make the moon jump around as the phase changes. The disc
box is therefore derived once from the union of all non-empty cells and reused
for every cell, so all eight phases keep their relative alignment inside the
cell. The new-moon cell is fully transparent and is left alone.

Idempotency
-----------
The first run copies the pristine textures to tools/_backup_env/ and never
touches that backup again; every run reads from the backup, so running the
script twice yields byte-identical output.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - explicit, never a silent fallback
    sys.exit("Pillow is required: python -m pip install pillow")

# Must match SkyWeatherEffects#CELESTIAL_SCALE on the Java side.
# 0.75 = 75% disc (6.3.1); 1.0 restores the 6.1.0 / 6.0.0 disc byte-for-byte.
# It is NOT allowed to be multiplied into the quad constants on the Java side —
# screen size is quad_scale x disc_fraction, and the quad side must stay at vanilla
# (sun 30, moon 20) so ClientEvents' custom moon keeps covering the vanilla one it
# is drawn on top of.
CELESTIAL_SCALE = 0.75
# A pixel counts as visible above this alpha; below it the sprite is pure margin.
ALPHA_VISIBLE = 8
# Luminance threshold for the "bright disc" statistic (the sun sprite is a fully
# opaque square, its visible body is only the bright part, not the whole canvas).
LUMA_BRIGHT = 96

ENV_DIR = Path("src/main/resources/assets/apocalypse_zombies/textures/environment")
BACKUP_DIR = Path("tools/_backup_env")
# file name -> (columns, rows) of its sprite grid
TARGETS = {"sun.png": (1, 1), "moon_phases.png": (4, 2)}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def visible_box(cell: Image.Image) -> tuple[int, int, int, int] | None:
    """Alpha bounding box of one cell, or None when the cell paints nothing."""
    alpha = cell.getchannel("A").point(lambda v: 255 if v > ALPHA_VISIBLE else 0)
    return alpha.getbbox()


def union_box(boxes: list[tuple[int, int, int, int] | None]) -> tuple[int, int, int, int]:
    live = [b for b in boxes if b is not None]
    if not live:
        raise SystemExit("no visible pixels found")
    return (
        min(b[0] for b in live),
        min(b[1] for b in live),
        max(b[2] for b in live),
        max(b[3] for b in live),
    )


def stats(img: Image.Image) -> tuple[int, int]:
    """(alpha-visible pixels, bright-disc pixels) for one cell."""
    alpha = img.getchannel("A")
    r, g, b = img.convert("RGB").split()
    visible = bright = 0
    for a, rr, gg, bb in zip(alpha.getdata(), r.getdata(), g.getdata(), b.getdata()):
        if a > ALPHA_VISIBLE:
            visible += 1
            if 0.299 * rr + 0.587 * gg + 0.114 * bb >= LUMA_BRIGHT:
                bright += 1
    return visible, bright


def scale_texture(name: str, cols: int, rows: int, source: Path, dest: Path) -> list[str]:
    src = Image.open(source).convert("RGBA")
    width, height = src.size
    cell_w, cell_h = width // cols, height // rows
    cells = [
        src.crop((c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h))
        for r in range(rows)
        for c in range(cols)
    ]
    boxes = [visible_box(cell) for cell in cells]
    box = union_box(boxes)

    # Same canvas, same grid; only the painted disc moves inwards.
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    new_w = max(1, round((box[2] - box[0]) * CELESTIAL_SCALE))
    new_h = max(1, round((box[3] - box[1]) * CELESTIAL_SCALE))
    centre_x = (box[0] + box[2]) / 2.0
    centre_y = (box[1] + box[3]) / 2.0

    lines = []
    index = 0
    for row in range(rows):
        for col in range(cols):
            cell = cells[index]
            origin_x, origin_y = col * cell_w, row * cell_h
            index += 1
            if boxes[index - 1] is None:
                lines.append(f"  cell {row},{col}: empty (new moon), left untouched")
                continue
            disc = cell.crop(box).resize((new_w, new_h), Image.LANCZOS)
            # Re-centre the scaled disc on the box centre it used to occupy,
            # expressed in canvas coordinates (cell origin + local offset).
            dst_x = origin_x + round(centre_x - new_w / 2.0)
            dst_y = origin_y + round(centre_y - new_h / 2.0)
            out.alpha_composite(disc, (dst_x, dst_y))
            lines.append(
                f"  cell {row},{col}: box {box} -> {new_w}x{new_h} at ({dst_x},{dst_y})"
            )

    if out.size != (width, height):
        raise SystemExit(f"canvas size changed for {name}: {out.size} != {(width, height)}")
    out.save(dest, format="PNG")
    return lines


def report(name: str, cols: int, rows: int, before: Path, after: Path) -> None:
    a = Image.open(before).convert("RGBA")
    b = Image.open(after).convert("RGBA")
    if a.size != b.size:
        raise SystemExit(f"canvas size changed for {name}: {a.size} -> {b.size}")
    cell_w, cell_h = a.size[0] // cols, a.size[1] // rows
    tot_visible = [0, 0]
    tot_bright = [0, 0]
    print(f"{name}  canvas {a.size[0]}x{a.size[1]}  grid {cols}x{rows}")
    for r in range(rows):
        for c in range(cols):
            box = (c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h)
            va, ba = stats(a.crop(box))
            vb, bb = stats(b.crop(box))
            tot_visible[0] += va
            tot_visible[1] += vb
            tot_bright[0] += ba
            tot_bright[1] += bb
            print(
                f"  cell {r},{c}: visible {va:>8} -> {vb:>7} ({vb / va:.4f}×)" if va
                else f"  cell {r},{c}: visible {va:>8} -> {vb:>7} (empty)"
            )
    print(
        f"  TOTAL visible {tot_visible[0]} -> {tot_visible[1]} "
        f"ratio {tot_visible[1] / tot_visible[0]:.4f} (ideal {CELESTIAL_SCALE ** 2:.4f})"
    )
    if tot_bright[0]:
        print(
            f"  TOTAL bright  {tot_bright[0]} -> {tot_bright[1]} "
            f"ratio {tot_bright[1] / tot_bright[0]:.4f}"
        )


def main() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for name, (cols, rows) in TARGETS.items():
        current = ENV_DIR / name
        pristine = BACKUP_DIR / name
        if not current.is_file():
            raise SystemExit(f"missing texture: {current}")
        # First run: keep the original. Later runs: the backup is the source of truth,
        # so repeated execution always produces the same bytes.
        if not pristine.is_file():
            shutil.copy2(current, pristine)
            print(f"backed up {name} -> {pristine}")
        else:
            print(f"backup {pristine} already present, rescaling from it")
        if CELESTIAL_SCALE == 1.0:
            # Nothing to scale: copy the pristine file through untouched, so the restore is
            # byte-exact. A 1.0 LANCZOS resize would keep the pixels but re-encode the PNG.
            shutil.copy2(pristine, current)
            print(f"  SCALE 1.0 -> restored {name} byte-for-byte from backup")
            print(f"  wrote {current}  sha256 {sha256(current)}")
            report(name, cols, rows, pristine, current)
            continue
        for line in scale_texture(name, cols, rows, pristine, current):
            print(line)
        print(f"  wrote {current}  sha256 {sha256(current)}")
        report(name, cols, rows, pristine, current)


if __name__ == "__main__":
    main()
