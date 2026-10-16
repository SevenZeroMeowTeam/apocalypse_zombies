# -*- coding: utf-8 -*-
"""把参考图的某个区域裁出来放大，用于逐像素判读（环的轮廓、管厚、相对位置）。

用法：
  python tools/_ref_zoom.py <图> <x0> <y0> <x1> <y1> [--scale=6] [--out=path]
"""
import sys
from pathlib import Path

from PIL import Image

args = [a for a in sys.argv[1:] if not a.startswith('--')]
opts = dict(a[2:].split('=', 1) for a in sys.argv[1:] if a.startswith('--'))
src = Path(args[0])
x0, y0, x1, y1 = (int(v) for v in args[1:5])
scale = int(opts.get('scale', 6))
out = Path(opts.get('out') or (src.parent / f'{src.stem}_zoom.png'))

im = Image.open(src).convert('RGB')
print('src size =', im.size, ' crop =', (x0, y0, x1, y1))
crop = im.crop((x0, y0, x1, y1))
big = crop.resize((crop.width * scale, crop.height * scale), Image.NEAREST)
big.save(out)
print(f'{out}  ({crop.width}x{crop.height} -> {big.width}x{big.height}, x{scale})')
