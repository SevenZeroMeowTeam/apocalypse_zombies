#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轨道卫星 GeckoLib 模型生成器（通道 A：唯一真相源）。

产出：
  src/main/resources/assets/apocalypse_zombies/geo/satellite.geo.json
  src/main/resources/assets/apocalypse_zombies/textures/entity/facility/satellite.png

单位：16 u = 1 方块（遵守《美术规范》§一）。模型约 14 格长 / 11 格宽 / 7.5 格高，
形态对应参考图「卫星.jpg」的三件套：金箔舱体 + 两侧三片太阳能翼 + 前置抛物面天线，
外加天线杆与尾部推进器。逐面 UV：512² 图集，每个面独占 32×32 格，带 1px 边距。

用法：
    python tools/facility_model.py
    python tools/facility_model.py --check   # 只校验已生成资源
"""
import argparse
import json
import os
import struct
import sys
import zlib

# ---------------------------------------------------------------- 常数
SIZE = 512
CELL = 32
PAD = 1
OUT_GEO = os.path.join('src', 'main', 'resources', 'assets', 'apocalypse_zombies',
                       'geo', 'satellite.geo.json')
OUT_TEX = os.path.join('src', 'main', 'resources', 'assets', 'apocalypse_zombies',
                       'textures', 'entity', 'facility', 'satellite.png')

# 纯黑/纯白是规范禁区（§六.7），底色全部带色相
C_GOLD   = (196, 158, 54)    # 金箔
C_GOLD_D = (148, 116, 36)    # 金箔暗部/框
C_PANEL  = (205, 210, 214)   # 白色仪器板
C_PANEL_D= (168, 174, 180)   # 仪器板暗部
C_SOLAR  = (30, 58, 104)     # 太阳能电池
C_SOLAR_D= (24, 46, 84)
C_FRAME  = (72, 78, 86)      # 深灰结构框
C_DISH   = (214, 218, 222)   # 抛物面白
C_DISH_D = (186, 190, 196)
C_DARK   = (44, 48, 55)      # 深色部件
C_CYAN   = (118, 236, 255)   # 自发光青
C_ORANGE = (255, 146, 62)    # 自发光橙

# ---------------------------------------------------------------- 画笔


def _hash(x, y, seed=0):
    h = (x * 374761393 + y * 668265263 + seed * 1442695040888963407) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFFFFFFFF


def _noise(x, y, seed, amp=8):
    return int((_hash(x, y, seed) % 1000) / 1000.0 * 2 * amp) - amp


class Atlas:
    """512² RGBA 图集 + 布局器：每面独占 CELL×CELL 格（§一.4 逐面 UV）。"""

    def __init__(self, size=SIZE):
        self.size = size
        self.px = [[(0, 0, 0, 255) for _ in range(size)] for _ in range(size)]
        self._grid = 0  # 16×16 = 256 格，够 43 面 ×6

    def claim_cell(self):
        idx = self._grid
        self._grid += 1
        if idx >= (self.size // CELL) ** 2:
            raise RuntimeError('atlas full')
        cx = idx % (self.size // CELL)
        cy = idx // (self.size // CELL)
        return (cx * CELL, cy * CELL)

    def fill_face(self, cell, color, style, seed):
        """把一种材质画进一格；返回 uv（几何原点在左下，图像 y 向下，翻转交给 u/v 记号）。"""
        x0, y0 = cell
        s = CELL - PAD * 2  # 内容区
        for yy in range(s):
            for xx in range(s):
                r, g, b = color
                n = _noise(x0 + xx, y0 + yy, seed, 7)
                if style == 'foil':          # 金箔折痕
                    if (xx + yy) % 11 == 0:
                        n += 18
                    if (xx - yy + 64) % 13 == 0:
                        n -= 14
                elif style == 'panel':       # 拼缝 + 铆钉
                    if xx % 14 == 0 or yy % 14 == 0:
                        n -= 22
                    if (xx % 14 in (4, 10)) and (yy % 14 in (4, 10)):
                        n += 26
                elif style == 'solar':       # 电池格
                    if xx % 8 == 0 or yy % 8 == 0:
                        r, g, b = 186, 150, 58
                    elif (xx + yy) % 19 == 0:
                        r, g, b = min(255, r + 40), min(255, g + 55), min(255, b + 70)
                elif style == 'dish':        # 放射拼缝
                    import math
                    ang = math.atan2(yy - s / 2, xx - s / 2)
                    if abs(math.sin(ang * 6.0)) < 0.10:
                        n -= 24
                elif style == 'glow':        # 自发光：中心更亮
                    import math
                    d = math.hypot(xx - s / 2, yy - s / 2) / (s / 2)
                    k = 1.0 - d * 0.45
                    r, g, b = int(r * k), int(g * k), int(b * k)
                elif style == 'armor':
                    if xx % 10 == 0 or yy % 10 == 0:
                        n -= 18
                px = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)), 255)
                self.px[y0 + PAD + yy][x0 + PAD + xx] = px
        # 面边框压暗一圈，方便读出体积
        for i in range(CELL):
            for (xx, yy) in ((i, 0), (i, CELL - 1), (0, i), (CELL - 1, i)):
                base = self.px[y0 + yy][x0 + xx]
                self.px[y0 + yy][x0 + xx] = (base[0] * 80 // 100, base[1] * 80 // 100,
                                             base[2] * 80 // 100, 255)
        # uv：Bedrock 的 v 向下，与图像行一致；返回 (u, v, w, h)
        return (x0 + PAD, y0 + PAD, s, s)

    def save_png(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        raw = bytearray()
        for row in self.px:
            raw.append(0)
            for (r, g, b, a) in row:
                raw += bytes((r, g, b, a))
        def chunk(tag, data):
            c = struct.pack('>I', len(data)) + tag + data
            return c + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)
        png = b'\x89PNG\r\n\x1a\n'
        png += chunk(b'IHDR', struct.pack('>IIBBBBB', SIZE, SIZE, 8, 6, 0, 0, 0))
        png += chunk(b'IDAT', zlib.compress(bytes(raw), 9))
        png += chunk(b'IEND', b'')
        with open(path, 'wb') as f:
            f.write(png)


# ---------------------------------------------------------------- 几何构造

BONES = {}   # name -> {name, pivot, parent, cubes:[]}
_ORDER = []


def bone(name, pivot, parent=None):
    if name not in BONES:
        BONES[name] = {'name': name, 'pivot': [float(v) for v in pivot],
                       'parent': parent, 'cubes': []}
        _ORDER.append(name)
    return name


def box(b, origin, size, material, style, seed):
    """加一个 cube：origin/size 单位=u，material=(color,...)，6 面逐面占格。"""
    atlas = box.atlas
    faces = {}
    for i, face in enumerate(('north', 'south', 'east', 'west', 'up', 'down')):
        cell = atlas.claim_cell()
        color, style_face = material[i] if isinstance(material[0], (list, tuple)) else (material, style)
        faces[face] = {'uv': list(atlas.fill_face(cell, color, style_face, seed + i)),
                       'uv_size': None}
        # fill_face 返回 (u,v,w,h)；geo 需要 uv=[u,v], uv_size=[w,h]
        u, v, w, h = faces[face]['uv']
        faces[face] = {'uv': [u, v], 'uv_size': [w, h]}
    cube = {'origin': [float(v) for v in origin], 'size': [float(v) for v in size],
            'uv': faces}
    BONES[b]['cubes'].append(cube)


def run():
    atlas = Atlas()
    box.atlas = atlas

    # 朝向：舱体长轴 = Z（§一.2），+Z = 天线侧；单位 u，16u = 1 格
    body = bone('body', [0, 0, 0])
    bone('body_shell', [0, 0, 0], body)
    bone('panel_front', [0, 16, -44], body)
    bone('dish_arm', [0, 14, -52], body)
    bone('dish', [0, 14, -60], 'dish_arm')
    bone('antenna', [0, 44, 0], body)
    bone('engine', [0, -14, 34], body)
    bone('wing_l', [-40, 14, 0], body)
    bone('wing_r', [40, 14, 0], body)

    # —— 舱体：金箔主体 5×5.5×8.5 格（80×88×136u），深色框收边
    box('body_shell', [-40, -44, -68], [80, 88, 136], C_GOLD, 'foil', 11)
    # 框架：4 根立柱 + 上下框
    for x in (-40, 40):
        for z in (-68, 68):
            box('body_shell', [x - 6 if x > 0 else x, -44, z - 6 if z > 0 else z],
                [12, 88, 12], C_FRAME, 'armor', 21)
    for y in (-44, 44):
        box('body_shell', [-34, y if y > 0 else y, -62], [68, 12, 124], C_GOLD_D, 'foil', 31)

    # —— 前面板（-Z 端）：白色仪器板 + 青色观察窗
    box('panel_front', [-46, -30, -6], [92, 66, 8], C_PANEL, 'panel', 41)
    box('panel_front', [-24, -12, -8], [48, 30, 6], C_CYAN, 'glow', 43)

    # —— 抛物面天线：两层收缩环 + 中心馈源（-Z 方向悬挂）
    box('dish_arm', [-7, -7, -18], [14, 14, 30], C_DARK, 'armor', 51)
    box('dish', [-96, -96, -8], [192, 192, 8], C_DISH, 'dish', 61)      # 主盘 12×12 格
    box('dish', [-60, -60, -14], [120, 120, 6], C_DISH_D, 'dish', 63)    # 内盘
    box('dish', [-16, -16, -20], [32, 32, 12], C_FRAME, 'armor', 65)     # 馈源座
    box('dish', [-6, -6, -30], [12, 12, 14], C_CYAN, 'glow', 67)         # 馈源尖

    # —— 天线杆（顶部，+Y）
    box('antenna', [-5, 0, -5], [10, 70, 10], C_DARK, 'armor', 71)
    box('antenna', [-9, 70, -9], [18, 12, 18], C_CYAN, 'glow', 73)

    # —— 推进器（尾部，+Z）
    box('engine', [-30, -24, 0], [60, 34, 40], C_FRAME, 'armor', 81)
    for x in (-18, 18):
        box('engine', [x - 11, -34, 40], [22, 22, 26], C_DARK, 'armor', 83)
        box('engine', [x - 8, -31, 66], [16, 16, 8], C_ORANGE, 'glow', 85)

    # —— 两侧太阳能翼：每侧三片 1.4×0.16×2.4 格，深灰框 + 金色压条
    for side, root in ((-1, 'wing_l'), (1, 'wing_r')):
        box(root, [0 if side > 0 else -46, -5, -10], [46, 10, 20], C_FRAME, 'armor', 91)
        for k in range(3):
            z0 = -46 + k * 54
            box(root, [(46 if side > 0 else -116), -7, z0], [70, 14, 46], C_SOLAR, 'solar', 93 + k * 2)
            box(root, [(46 if side > 0 else -116), 7, z0], [70, 6, 46], C_GOLD_D, 'foil', 94 + k * 2)
            box(root, [(46 if side > 0 else -116), -7, z0 - 6], [70, 14, 6], C_FRAME, 'armor', 95 + k * 2)

    # —— 校验
    cubes = sum(len(b['cubes']) for b in BONES.values())
    faces = cubes * 6
    painted = atlas._grid
    assert cubes <= 600, cubes
    assert len(BONES) <= 40, len(BONES)
    assert painted == faces, (painted, faces)

    geo = {
        'format_version': '1.12.0',
        'minecraft:geometry': [{
            'description': {
                'identifier': 'geometry.satellite',
                'texture_width': SIZE,
                'texture_height': SIZE,
                'visible_bounds_width': 4.0,
                'visible_bounds_height': 3.0,
                'visible_bounds_offset': [0.0, 1.2, 0.0],
            },
            'bones': [dict(BONES[n]) for n in _ORDER],
        }],
    }
    os.makedirs(os.path.dirname(OUT_GEO), exist_ok=True)
    with open(OUT_GEO, 'w', encoding='utf-8') as f:
        json.dump(geo, f, ensure_ascii=False, indent=2)
        f.write('\n')
    atlas.save_png(OUT_TEX)

    # PNG 尺寸自检
    with open(OUT_TEX, 'rb') as f:
        head = f.read(24)
    w, h = struct.unpack('>II', head[16:24])
    assert (w, h) == (SIZE, SIZE), (w, h)
    print(f'OK geo={OUT_GEO} bones={len(BONES)} cubes={cubes} faces={faces}')
    print(f'OK tex={OUT_TEX} {w}x{h} cells={painted}/{(SIZE // CELL) ** 2}')
    return 0


def check():
    ok = True
    for p in (OUT_GEO, OUT_TEX):
        if not os.path.isfile(p):
            print('MISSING', p)
            ok = False
    if os.path.isfile(OUT_GEO):
        g = json.load(open(OUT_GEO, encoding='utf-8'))
        d = g['minecraft:geometry'][0]['description']
        with open(OUT_TEX, 'rb') as f:
            head = f.read(24)
        w, h = struct.unpack('>II', head[16:24])
        ok &= (d['texture_width'] == w and d['texture_height'] == h)
        print('texture match:', d['texture_width'], '==', w, ok)
        # 每面 uv 必须非空且落在图集内
        bad = 0
        for b in g['minecraft:geometry'][0]['bones']:
            for c in b.get('cubes', []):
                for face, uv in c['uv'].items():
                    u, v = uv['uv']
                    uw, uh = uv['uv_size']
                    if uw <= 0 or uh <= 0 or u + uw > w or v + uh > h:
                        bad += 1
        print('bad uvs:', bad)
        ok &= bad == 0
    print('RESULT:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    sys.exit(check() if args.check else run())
