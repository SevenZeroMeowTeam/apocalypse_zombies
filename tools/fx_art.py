#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""屏幕级特效贴图：径向速度线 / 镜头光晕 / 冲击帧墨迹。

参考包那种「演出感」很大一部分来自后期：速度线、冲击帧、镜头光晕、色差。
我们不做 shader/FBO，改用**程序化生成的透明贴图 + GuiGraphics 叠加**来近似 ——
贴图本身是原创的、可复现，随包分发。

用法：
    python tools/fx_art.py
    python tools/fx_art.py --preview C:/Temp/fx_preview
"""
import argparse
import math
import os

import numpy as np
from PIL import Image

BASE = os.path.join('src', 'main', 'resources', 'assets', 'apocalypse_zombies', 'textures', 'environment')


def _save(name, rgb, alpha, out_dir):
    arr = np.zeros((alpha.shape[0], alpha.shape[1], 4), np.uint8)
    arr[..., 0] = rgb[..., 0]
    arr[..., 1] = rgb[..., 1]
    arr[..., 2] = rgb[..., 2]
    arr[..., 3] = alpha
    image = Image.fromarray(arr, 'RGBA')
    image.save(os.path.join(BASE, name + '.png'), format='PNG')
    if out_dir:
        image.save(os.path.join(out_dir, name + '.png'), format='PNG')
    print('wrote', os.path.join(BASE, name + '.png'), image.size)


def speed_lines(size=1024, streaks=220):
    """从中心向外放射的白色速度线，中心透明、末端渐隐。"""
    alpha = np.zeros((size, size), np.float32)
    cx = cy = (size - 1) / 2.0
    rng = np.random.default_rng(0x5EED1)
    for _ in range(streaks):
        ang = rng.random() * math.tau
        r0 = (0.34 + 0.22 * rng.random()) * size * 0.5
        r1 = r0 + (0.16 + 0.40 * rng.random()) * size * 0.5
        width = 0.9 + 2.2 * rng.random()
        peak = 0.22 + 0.55 * rng.random()
        steps = int((r1 - r0) * 1.2) + 2
        ca, sa = math.cos(ang), math.sin(ang)
        for i in range(steps):
            t = i / (steps - 1.0)
            r = r0 + (r1 - r0) * t
            x = cx + ca * r
            y = cy + sa * r
            if not (0 <= x < size and 0 <= y < size):
                continue
            a = peak * math.sin(math.pi * t) ** 1.6
            _splat(alpha, x, y, width, a)
    alpha = np.clip(alpha, 0.0, 1.0)
    rgb = np.dstack([np.full((size, size), 255, np.uint8)] * 3)
    return rgb, (alpha * 255).astype(np.uint8)


def _splat(canvas, x, y, radius, value):
    x0 = max(0, int(x - radius) - 1)
    x1 = min(canvas.shape[1] - 1, int(x + radius) + 1)
    y0 = max(0, int(y - radius) - 1)
    y1 = min(canvas.shape[0] - 1, int(y + radius) + 1)
    for yy in range(y0, y1 + 1):
        for xx in range(x0, x1 + 1):
            d = math.hypot(xx - x, yy - y)
            if d <= radius:
                v = value * (1.0 - d / (radius + 1e-6))
                if v > canvas[yy, xx]:
                    canvas[yy, xx] = v


def lens_flare(size=512):
    """横向变形镜头光晕：白热核心 + 水平拉丝 + 一圈淡环 + 细十字星芒。"""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cx = cy = (size - 1) / 2.0
    dx = (xx - cx) / (size * 0.5)
    dy = (yy - cy) / (size * 0.5)
    r = np.sqrt(dx * dx + dy * dy)
    core = np.exp(-(r * r) * 90.0)
    halo = np.exp(-((r - 0.34) ** 2) * 420.0) * 0.35
    streak = np.exp(-(dy * dy) * 380.0) * np.exp(-(dx * dx) * 2.6) * 0.55
    cross = (np.exp(-(dx * dx) * 3200.0) * np.exp(-(dy * dy) * 2.0)
             + np.exp(-(dy * dy) * 3200.0) * np.exp(-(dx * dx) * 2.0)) * 0.22
    a = np.clip(core + halo + streak + cross, 0.0, 1.0)
    rgb = np.dstack([np.full((size, size), 255, np.uint8)] * 3)
    return rgb, (a * 255).astype(np.uint8)


def impact_ink(size=1024):
    """冲击帧墨迹：四周放射状黑墨条 + 边缘白裂纹，中间留透明。"""
    alpha = np.zeros((size, size), np.float32)
    white = np.zeros((size, size), np.float32)
    cx = cy = (size - 1) / 2.0
    rng = np.random.default_rng(0x1A2B3C)
    for _ in range(260):
        ang = rng.random() * math.tau
        r0 = (0.36 + 0.14 * rng.random()) * size * 0.5
        r1 = size * 0.52 + 0.10 * size * rng.random()
        width = 2.0 + 9.0 * rng.random() ** 2
        ca, sa = math.cos(ang), math.sin(ang)
        steps = int((r1 - r0)) + 2
        for i in range(steps):
            t = i / (steps - 1.0)
            r = r0 + (r1 - r0) * t
            x = cx + ca * r
            y = cy + sa * r
            if not (0 <= x < size and 0 <= y < size):
                continue
            a = (0.35 + 0.65 * rng.random()) * min(1.0, t * 1.8)
            _splat(alpha, x, y, width, a)
    # 白裂纹：少量更细、更靠近边缘的线
    for _ in range(46):
        ang = rng.random() * math.tau
        r0 = (0.40 + 0.08 * rng.random()) * size * 0.5
        r1 = r0 + (0.06 + 0.16 * rng.random()) * size * 0.5
        ca, sa = math.cos(ang), math.sin(ang)
        steps = max(8, int(r1 - r0))
        for i in range(steps):
            t = i / (steps - 1.0)
            r = r0 + (r1 - r0) * t
            x = cx + ca * r
            y = cy + sa * r
            if not (0 <= x < size and 0 <= y < size):
                continue
            _splat(white, x, y, 0.8 + 1.4 * t, 0.75 * (1.0 - t))
    rgb = np.dstack([np.full((size, size), 8, np.uint8),
                     np.full((size, size), 8, np.uint8),
                     np.full((size, size), 10, np.uint8)])
    rgb = np.where(white[..., None] > 0.2, np.uint8(255), rgb)
    alpha = np.clip(alpha + white * 0.6, 0.0, 1.0)
    return rgb, (alpha * 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview', default=None)
    args = ap.parse_args()
    if args.preview:
        os.makedirs(args.preview, exist_ok=True)
    _save('fx_speedlines', *speed_lines(), out_dir=args.preview)
    _save('fx_flare', *lens_flare(), out_dir=args.preview)
    _save('fx_ink', *impact_ink(), out_dir=args.preview)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
