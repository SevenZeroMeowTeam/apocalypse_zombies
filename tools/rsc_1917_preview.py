#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 注意：本脚本 import numpy —— Windows 的 py 启动器会按 shebang 选解释器，
# 上面那行 `/usr/bin/env python3` 会挑到 PATH 里的 python3（本机是 graalpy，没有 numpy）。
# 所以**别用 `py tools/rsc_1917_preview.py` 直接跑**，用：
#     py -3.13 tools/rsc_1917_preview.py
# 或者先把 numpy 装到 graalpy 那边。其它 tools/*.py 只用标准库，不受影响。
"""RSC M1917 侧视预览渲染器 —— 把 geo.json + 512² 贴图按**正交侧视**画成 PNG，
用来和参考照片 art/rsc_1917/ref_rsc1917_side.png 直接对照（同 mm/px、可叠图）。

为什么自己画：Blockbench 的 app screenshot 超时、offscreen view 这版插件没有出图接口，
而 CLI 侧要的是一个**确定性、可重跑、能进 CI** 的对照工具。

做法（正交侧视下只有朝向相机的那个面可见，所以只画 ±X 面，画师算法按 X 排序）：
  1. 读 geo.json：每根骨、每个方块（origin=最小角 + size + 逐面 uv/uv_size）；
  2. 选相机在 −X（看 west 面）或 +X（看 east 面），按 X 从小到大画（远的先画）；
  3. 面内像素 → 贴图坐标：横向沿 Z、纵向沿 −Y（Bedrock 的 u 右增 / v 下增），
     再按 uv_size 的正负做镜像 —— 见 --flip-u / --flip-v / --flip-x 三个开关，
     用来在“看不出纹理朝向”时快速试正（正确朝向的判据：木托是木纹、机匣是金属灰）。

用法：
    py tools/rsc_1917_preview.py                        # 输出 art/rsc_1917/preview_side.png
    py tools/rsc_1917_preview.py --view east --out x.png
    py tools/rsc_1917_preview.py --overlay              # 同时输出与参考图的上下对照长图
"""

import argparse
import json
import math
import os

import numpy as np
from PIL import Image

GEO = 'art/rsc_1917/rsc_1917.geo.json'
TEX = 'src/main/resources/assets/apocalypse_zombies/textures/item/rsc_1917.png'
REF = 'art/rsc_1917/ref_rsc1917_side.png'
# 参考图量取口径（profile.json）：1 采样 = 1.0242 mm = 1 px（1331 宽的版本）
REF_MM_PER_PX = 0.51212
MM = 16 / 1000                      # 1 u = 62.5 mm
FACES = ('north', 'east', 'south', 'west', 'up', 'down')


def load(path=GEO):
    geo = json.load(open(path, encoding='utf-8'))['minecraft:geometry'][0]
    out = []
    for b in geo['bones']:
        for c in b.get('cubes', []):
            o, s = c['origin'], c['size']
            out.append({
                'bone': b['name'],
                'lo': np.array(o, float),
                'hi': np.array(o, float) + np.array(s, float),
                'uv': c.get('uv', {}),
            })
    return geo['description'], out


def face_rect(cube, face):
    """返回面的 (z0, z1, y0, y1) + 该面的 uv 矩形（u0, v0, du, dv）"""
    lo, hi = cube['lo'], cube['hi']
    u = cube['uv'].get(face)
    if face == 'west':
        axis = (lo[2], hi[2], lo[1], hi[1])
    elif face == 'east':
        axis = (hi[2], lo[2], lo[1], hi[1])
    else:
        return None
    if u is None:
        return None
    try:
        uv, sz = u['uv'], u['uv_size']
    except (TypeError, KeyError):
        return None
    return axis, (uv[0], uv[1], sz[0], sz[1])


def render(view='west', mm_per_px=REF_MM_PER_PX, pad=6, bg=(255, 255, 255, 0), flip_x=False):
    desc, cubes = load()
    tex = np.array(Image.open(TEX).convert('RGBA'))
    tw, th = tex.shape[1], tex.shape[0]

    xs = np.concatenate([c['lo'] for c in cubes] + [c['hi'] for c in cubes])
    lo = xs.reshape(-1, 3).min(axis=0)
    hi = xs.reshape(-1, 3).max(axis=0)
    z0u, z1u, y0u, y1u = lo[2], hi[2], lo[1], hi[1]

    u_per_px = mm_per_px / 62.5                # 每像素多少 u
    W = int(math.ceil((z1u - z0u) / u_per_px)) + 2 * pad
    H = int(math.ceil((y1u - y0u) / u_per_px)) + 2 * pad
    img = np.zeros((H, W, 4), np.uint8)
    if bg[3] > 0:
        img[:, :] = bg
    zbuf = np.full((H, W), -1e9)

    order = sorted(cubes, key=lambda c: c['lo'][0] if view == 'west' else -c['hi'][0])
    for c in order:
        r = face_rect(c, view)
        if r is None:
            continue
        (za, zb, ya, yb), (u0, v0, du, dv) = r
        # 面的 4 角 → 像素范围
        px0 = pad + (min(za, zb) - z0u) / u_per_px
        px1 = pad + (max(za, zb) - z0u) / u_per_px
        py0 = pad + (y1u - max(ya, yb)) / u_per_px
        py1 = pad + (y1u - min(ya, yb)) / u_per_px
        x0, x1 = int(math.floor(px0)), int(math.ceil(px1))
        y0, y1 = int(math.floor(py0)), int(math.ceil(py1))
        x0, x1 = max(0, x0), min(W, x1)
        y0, y1 = max(0, y0), min(H, y1)
        if x1 <= x0 or y1 <= y0:
            continue
        # 面内归一化坐标网格
        fx = (np.arange(x0, x1) + 0.5 - px0) / max(1e-9, (px1 - px0))
        fy = (np.arange(y0, y1) + 0.5 - py0) / max(1e-9, (py1 - py0))
        if view == 'east':
            fx = 1.0 - fx                        # east 面的 u 沿 −Z
        if flip_x:
            fx = 1.0 - fx
        uu = u0 + du * fx[None, :]
        vv = v0 + dv * fy[:, None]
        if flip_x is False and False:
            pass
        col = tex[np.clip(vv.astype(int), 0, th - 1), np.clip(uu.astype(int), 0, tw - 1)]
        depth = c['lo'][0] if view == 'west' else -c['hi'][0]
        region = img[y0:y1, x0:x1]
        vis = col[..., 3] > 0
        region[vis] = col[vis]
        zbuf[y0:y1, x0:x1][vis] = depth
    return Image.fromarray(img)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--view', choices=('west', 'east'), default='west')
    ap.add_argument('--out', default='art/rsc_1917/preview_side.png')
    ap.add_argument('--scale', type=float, default=REF_MM_PER_PX)
    ap.add_argument('--overlay', action='store_true')
    args = ap.parse_args()
    im = render(view=args.view, mm_per_px=args.scale)
    im.save(args.out)
    print('%s %dx%d (%.4f mm/px)' % (args.out, im.width, im.height, args.scale))
    if args.overlay:
        ref = Image.open(REF).convert('RGBA')
        W = max(ref.width, im.width)
        out = Image.new('RGBA', (W, ref.height + im.height + 12), (255, 255, 255, 255))
        out.paste(ref, (0, 0), ref)
        out.paste(im, (0, ref.height + 12), im)
        p = args.out.replace('.png', '_vs_ref.png')
        out.save(p)
        print('%s %dx%d（上=参考照片，下=本模型）' % (p, out.width, out.height))


if __name__ == '__main__':
    main()
