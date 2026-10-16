# -*- coding: utf-8 -*-
"""win94 贴图 v3 —— 按 tools/win94_gen2.py 的 UV 货架逐面绘制 512² 贴图。

读 build/bbmcp/win94_uvmap.json（每个面的矩形 + 材质），逐面：
  1) 铺材质底色 × 面朝向明暗（上亮下暗，立体感）
  2) 按材质加纹理：胡桃木木纹、发蓝钢拉丝、抛光钢渐变、黄铜氧化、镜片反光
  3) 四周 1px 收暗，让相邻面在低分辨率下仍有轮廓

输出：
  src/main/resources/assets/apocalypse_zombies/textures/item/win94.png   （交付资源）
  build/bbmcp/win94_tex_preview.png                                      （放大 3 倍自查）
"""
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
UVMAP = ROOT / 'build' / 'bbmcp' / 'win94_uvmap.json'
OUT_TEX = ROOT / 'src' / 'main' / 'resources' / 'assets' / 'apocalypse_zombies' / 'textures' / 'item' / 'win94.png'
OUT_PREV = ROOT / 'build' / 'bbmcp' / 'win94_tex_preview.png'
W = H = 512

BASE = {
    'blued': (44, 49, 57),
    'blued_dark': (26, 29, 34),
    'steel': (126, 133, 142),
    'walnut': (104, 68, 38),
    'walnut_dark': (68, 43, 21),
    'brass': (172, 138, 84),
    'brass_dark': (124, 94, 50),
    'copper': (152, 92, 48),
    'lens': (66, 88, 112),
}
FACE_LIGHT = {'up': 1.18, 'down': 0.70, 'north': 0.95, 'south': 1.05,
              'east': 0.86, 'west': 1.10}


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def jitter(c, amt, rnd):
    return tuple(max(0, min(255, v + rnd.randint(-amt, amt))) for v in c)


def draw_wood(d, box, base, rnd):
    """胡桃木：底色 + 沿长轴的深色木纹 + 少量高光丝。"""
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    horiz = w >= h
    n = 1 + (h if horiz else w) // 3
    for i in range(min(6, n)):
        t = rnd.random()
        c = shade(base, 1.18 if t > 0.72 else (0.74 if t < 0.34 else 1.0))
        if horiz:
            yy = y1 + rnd.randrange(h)
            d.line([(x1, yy), (x2 - 1, yy + rnd.choice([-1, 0, 0, 1]))], fill=c + (255,))
        else:
            xx = x1 + rnd.randrange(w)
            d.line([(xx, y1), (xx + rnd.choice([-1, 0, 0, 1]), y2 - 1)], fill=c + (255,))
    # 木料孔隙
    for _ in range(max(1, (w * h) // 90)):
        px, py = rnd.randrange(x1, x2), rnd.randrange(y1, y2)
        d.point((px, py), fill=shade(base, 0.62) + (255,))


def draw_blued(d, box, base, rnd):
    """发蓝钢：竖向微渐变 + 拉丝横线。"""
    x1, y1, x2, y2 = box
    h = y2 - y1
    for yy in range(y1, y2):
        t = (yy - y1) / max(1, h - 1)
        c = shade(base, 1.14 - 0.22 * t)
        d.line([(x1, yy), (x2 - 1, yy)], fill=c + (255,))
    for _ in range(max(1, (x2 - x1) // 4)):
        yy = rnd.randrange(y1, y2)
        d.line([(x1, yy), (x2 - 1, yy)], fill=shade(base, 1.28) + (255,))


def draw_steel(d, box, base, rnd):
    """抛光钢：中心亮带。"""
    x1, y1, x2, y2 = box
    h = max(1, y2 - y1)
    for yy in range(y1, y2):
        t = abs((yy - y1) / h - 0.5) * 2.0
        d.line([(x1, yy), (x2 - 1, yy)], fill=shade(base, 1.30 - 0.45 * t) + (255,))


def draw_metal_colored(d, box, base, rnd, hi=1.22, lo=0.78):
    x1, y1, x2, y2 = box
    h = max(1, y2 - y1)
    for yy in range(y1, y2):
        t = (yy - y1) / h
        d.line([(x1, yy), (x2 - 1, yy)], fill=shade(base, hi - (hi - lo) * t) + (255,))


def draw_lens(d, box, base, rnd):
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    for yy in range(y1, y2):
        for xx in range(x1, x2):
            dx = (xx + 0.5 - cx) / max(1e-6, (x2 - x1) / 2)
            dy = (yy + 0.5 - cy) / max(1e-6, (y2 - y1) / 2)
            r = min(1.0, (dx * dx + dy * dy) ** 0.5)
            d.point((xx, yy), fill=shade(base, 1.45 - 0.75 * r) + (255,))


def main():
    uvmap = json.loads(UVMAP.read_text(encoding='utf-8'))
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rnd = random.Random(94)

    n_faces = 0
    for f in uvmap['faces']:
        u1, v1, u2, v2 = f['uv']
        if u2 <= u1 or v2 <= v1:
            continue
        base = BASE.get(f['mat'], BASE['blued'])
        box = (u1, v1, u2, v2)
        mat = f['mat']
        col = shade(base, FACE_LIGHT.get(f['face'], 1.0))
        d.rectangle([u1, v1, u2 - 1, v2 - 1], fill=col + (255,))
        if mat.startswith('walnut'):
            draw_wood(d, box, col, rnd)
        elif mat == 'steel':
            draw_steel(d, box, col, rnd)
        elif mat in ('brass', 'brass_dark', 'copper'):
            draw_metal_colored(d, box, col, rnd, hi=1.20, lo=0.74)
        elif mat == 'lens':
            draw_lens(d, box, col, rnd)
        elif mat == 'blued_dark':
            draw_metal_colored(d, box, col, rnd, hi=1.05, lo=0.80)
        else:
            draw_blued(d, box, col, rnd)
        # 不画四周收暗线：枪托是 16 段拼的，逐段描边会在侧面上形成"栅栏"竖纹
        n_faces += 1

    OUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT_TEX)
    prev = img.resize((W * 2, H * 2), Image.NEAREST)
    prev.save(OUT_PREV)
    print(f'faces painted = {n_faces}')
    print('tex  ->', OUT_TEX, OUT_TEX.stat().st_size, 'bytes')
    print('prev ->', OUT_PREV)


if __name__ == '__main__':
    main()
