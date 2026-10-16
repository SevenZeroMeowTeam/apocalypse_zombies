#!/usr/bin/env python3
"""把 Blockbench 截图裁到模型外框并放大（nearest），便于人眼查细节。

用法：
  python tools/_bb_zoom.py <in.png> [out.png] [--scale=3] [--split=2]
    --scale  放大倍数（默认 3，nearest 保像素）
    --split  横向切成 N 段分别放大（长枪查细节用，默认 1 不切）
"""
import sys
from pathlib import Path

from PIL import Image


def bbox_of(img, bg_tol=12):
    """找非背景区域。截图背景是纯白或浅灰，取四角像素的中位色作为背景色。"""
    rgb = img.convert('RGB')
    w, h = rgb.size
    corners = [rgb.getpixel(p) for p in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3))]
    bg = tuple(sorted(c[i] for c in corners)[len(corners) // 2] for i in range(3))
    px = rgb.load()
    minx, miny, maxx, maxy = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            p = px[x, y]
            if abs(p[0] - bg[0]) > bg_tol or abs(p[1] - bg[1]) > bg_tol or abs(p[2] - bg[2]) > bg_tol:
                if x < minx:
                    minx = x
                if y < miny:
                    miny = y
                if x > maxx:
                    maxx = x
                if y > maxy:
                    maxy = y
    if maxx <= minx or maxy <= miny:
        return None
    return minx, miny, maxx + 1, maxy + 1


def main():
    src = Path(sys.argv[1])
    args = [a for a in sys.argv[2:] if not a.startswith('--')]
    scale = 3
    split = 1
    for a in sys.argv[2:]:
        if a.startswith('--scale='):
            scale = int(a.split('=', 1)[1])
        if a.startswith('--split='):
            split = int(a.split('=', 1)[1])
    out = Path(args[0]) if args else src.with_name(src.stem + '_zoom.png')

    img = Image.open(src)
    bb = bbox_of(img)
    if not bb:
        print('没找到非背景内容')
        return 1
    pad = 4
    x0, y0, x1, y1 = bb
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(img.width, x1 + pad), min(img.height, y1 + pad)
    crop = img.crop((x0, y0, x1, y1))
    print(f'bbox={bb} crop={crop.size} scale={scale} split={split}')

    if split <= 1:
        big = crop.resize((crop.width * scale, crop.height * scale), Image.NEAREST)
        big.save(out)
        print(out, big.size)
        return 0

    step = crop.width // split
    for i in range(split):
        sx0 = i * step
        sx1 = crop.width if i == split - 1 else (i + 1) * step
        seg = crop.crop((sx0, 0, sx1, crop.height))
        seg = seg.resize((seg.width * scale, seg.height * scale), Image.NEAREST)
        p = out.with_name(f'{out.stem}_{i}{out.suffix}')
        seg.save(p)
        print(p, seg.size)
    return 0


if __name__ == '__main__':
    sys.exit(main())
