#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轨道设施装饰方块贴图（32×32，程序化原创）。

给可传送轨道维度里的卫星/发射台/环站/陨石用：hull（深灰装甲板）、gold（金箔）、
panel（白色仪器板）、solar（太阳能电池）、dish（抛物面白板）、glow_cyan / glow_orange
（自发光条）、dark（深色结构件）。全部确定性生成，不依赖随机数。

用法：
    python tools/facility_art.py
"""
import math
import os

from PIL import Image

BASE = os.path.join('src', 'main', 'resources', 'assets', 'apocalypse_zombies', 'textures', 'block')
SIZE = 32


def _hash(x, y, seed=0):
    h = (x * 374761393 + y * 668265263 + seed * 1442695040888963407) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFFFFFFFF


def _clamp(v):
    return max(0, min(255, int(v)))


def _save(name, pixels):
    os.makedirs(BASE, exist_ok=True)
    image = Image.new('RGBA', (SIZE, SIZE))
    image.putdata(pixels)
    image.save(os.path.join(BASE, name + '.png'), format='PNG')
    print('wrote', os.path.join(BASE, name + '.png'))


def _noise(x, y, amp, seed=0):
    return (int(_hash(x, y, seed) % 1000) / 1000.0 - 0.5) * 2.0 * amp


def hull():
    px = []
    for y in range(SIZE):
        for x in range(SIZE):
            base = 58 + _noise(x, y, 10, 1)
            # 面板缝：每 16 像素一条
            if x % 16 == 0 or y % 16 == 0:
                base -= 18
            if x % 16 == 1 or y % 16 == 1:
                base += 8
            # 四角铆钉
            if (x % 16 in (4, 11)) and (y % 16 in (4, 11)):
                base += 26
            # 顶部受光
            base += (16 - y) * 0.6
            px.append((_clamp(base), _clamp(base + 5), _clamp(base + 10), 255))
    return px


def gold():
    px = []
    for y in range(SIZE):
        for x in range(SIZE):
            r = 196 + _noise(x, y, 16, 3) + ((x * 3 + y * 5) % 7 - 3)
            g = 158 + _noise(x, y, 14, 4) + ((x + y) % 5 - 2)
            b = 54 + _noise(x, y, 10, 5)
            # 斜向折痕
            if (x + y) % 11 == 0:
                r += 18
                g += 12
            if (x - y) % 13 == 0:
                r -= 14
                g -= 10
            px.append((_clamp(r), _clamp(g), _clamp(b), 255))
    return px


def panel():
    px = []
    for y in range(SIZE):
        for x in range(SIZE):
            base = 198 + _noise(x, y, 5, 7) + (16 - y) * 0.5
            if x % 8 == 0 or y % 8 == 0:
                base -= 16
            # 散热栅格
            if 20 <= y <= 27 and 6 <= x <= 25 and (x % 3 == 0):
                base -= 30
            px.append((_clamp(base), _clamp(base + 3), _clamp(base + 7), 255))
    return px


def solar():
    px = []
    for y in range(SIZE):
        for x in range(SIZE):
            r, g, b = 22 + _noise(x, y, 4, 9), 48 + _noise(x, y, 6, 10), 92 + _noise(x, y, 8, 11)
            # 电池格 8×8，金色栅线
            if x % 8 == 0 or y % 8 == 0:
                r, g, b = 186, 150, 58
            elif x % 8 == 4 or y % 8 == 4:
                r, g, b = 30, 70, 128
            # 高光斜带
            if (x + y) % 19 == 0:
                r += 40
                g += 55
                b += 70
            px.append((_clamp(r), _clamp(g), _clamp(b), 255))
    return px


def dish():
    px = []
    cx = cy = (SIZE - 1) / 2.0
    for y in range(SIZE):
        for x in range(SIZE):
            dx = x - cx
            dy = y - cy
            dist = math.hypot(dx, dy)
            base = 212 + _noise(x, y, 4, 13) - dist * 1.8
            ang = math.atan2(dy, dx)
            # 放射状拼缝
            if abs(math.sin(ang * 6.0)) < 0.06:
                base -= 22
            if abs(dist - 9.5) < 0.7:
                base -= 14
            px.append((_clamp(base), _clamp(base + 3), _clamp(base + 6), 255))
    return px


def glow(r, g, b, seed):
    px = []
    cx = cy = (SIZE - 1) / 2.0
    for y in range(SIZE):
        for x in range(SIZE):
            d = math.hypot(x - cx, y - cy) / 22.0
            k = max(0.0, 1.0 - d) * 0.55 + 0.45
            n = _noise(x, y, 8, seed)
            px.append((_clamp(r * k + n), _clamp(g * k + n), _clamp(b * k + n), 255))
    return px


def dark():
    px = []
    for y in range(SIZE):
        for x in range(SIZE):
            base = 26 + _noise(x, y, 6, 17)
            if x % 8 == 0 or y % 8 == 0:
                base += 7
            px.append((_clamp(base), _clamp(base + 2), _clamp(base + 5), 255))
    return px


def main():
    _save('facility_hull', hull())
    _save('facility_gold', gold())
    _save('facility_panel', panel())
    _save('facility_solar', solar())
    _save('facility_dish', dish())
    _save('facility_glow_cyan', glow(110, 240, 255, 21))
    _save('facility_glow_orange', glow(255, 140, 50, 22))
    _save('facility_dark', dark())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
