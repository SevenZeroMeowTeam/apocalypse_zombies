#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-A1 太空舞台原创贴图生成器 —— 地球 / 星云 / 卫星三件套。

全部像素由本脚本用确定性程序化噪声画出来，**不读取、不采样、不缩放、不裁切任何参考图**。
参考图（仓库根的 小地球.png / 宇宙.png / 卫星.png）只用来对构图/配色语言做人工取舍；
生成脚本里没有任何文件读取，随机性全部来自整数哈希（无 random 熵，重复跑逐字节一致）。

产出（覆盖）：
    textures/environment/earth.png      512x512  RGBA  圆形地球圆盘（大气边缘 + 云带 + 夜面城市灯）
    textures/environment/nebula.png     1024x512 RGB   深空星云色带 + 星点（水平可环绕）
    textures/environment/sat_body.png   256x256  RGBA  金色多层隔热膜舱体
    textures/environment/sat_panel.png  256x256  RGBA  深蓝太阳能电池片阵列
    textures/environment/sat_dish.png   256x256  RGBA  白色抛物面天线（圆形透明底）

用法：
    python tools/orbital_art.py
    python tools/orbital_art.py --preview <仓库外的目录>   # 另出 2x 放大预览

资产门禁见 tools/check_orbital_art.py（尺寸/格式 + 与参考图的 dHash 汉明距离 ≥ 18）。
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_DIR = os.path.join(
    ROOT, "src", "main", "resources", "assets", "apocalypse_zombies", "textures", "environment")

EARTH = os.path.join(ENV_DIR, "earth.png")
NEBULA = os.path.join(ENV_DIR, "nebula.png")
SAT_BODY = os.path.join(ENV_DIR, "sat_body.png")
SAT_PANEL = os.path.join(ENV_DIR, "sat_panel.png")
SAT_DISH = os.path.join(ENV_DIR, "sat_dish.png")


# ================================================================ 确定性噪声
_U32 = 0xFFFFFFFF


def _hash_u32(*values: int) -> int:
    """整数哈希（不依赖 random / 时间 / 环境），同参数恒等。"""
    h = 0x9E3779B9
    for value in values:
        h = (h ^ (int(value) & _U32)) * 0x85EBCA6B & _U32
        h ^= h >> 13
        h = h * 0xC2B2AE35 & _U32
        h ^= h >> 16
    return h & _U32


def _hash01(*values: int) -> float:
    return _hash_u32(*values) / 4294967295.0


def _lattice_float(gx: int, gy: int, seed: int) -> Image.Image:
    """gx*gy 的浮点值噪声格点图（值域 0..1）。"""
    img = Image.new("F", (gx, gy))
    img.putdata([_hash01(x, y, seed) for y in range(gy) for x in range(gx)])
    return img


def _fbm(seed: int, width: int, height: int, gx0: int, gy0: int,
         octaves: int = 5, persistence: float = 0.55) -> list[float]:
    """普通分形噪声（值域约 0..1）：低分辨率格点逐级放大叠加。"""
    total: list[float] | None = None
    amp, norm = 1.0, 0.0
    for octave in range(octaves):
        gx = gx0 * (1 << octave)
        gy = gy0 * (1 << octave)
        big = _lattice_float(gx, gy, seed + 101 * octave).resize(
            (width, height), Image.Resampling.BILINEAR)
        values = list(big.getdata())
        if total is None:
            total = [v * amp for v in values]
        else:
            total = [a + v * amp for a, v in zip(total, values)]
        norm += amp
        amp *= persistence
    inverse = 1.0 / norm
    return [v * inverse for v in total]


def _fbm_periodic_x(seed: int, width: int, height: int, gx0: int, gy0: int,
                    octaves: int = 5, persistence: float = 0.55) -> list[float]:
    """水平周期分形噪声：天球 1024x512 贴图左右自然环绕，没有接缝。"""
    total: list[float] | None = None
    amp, norm = 1.0, 0.0
    for octave in range(octaves):
        gx = gx0 * (1 << octave)
        gy = gy0 * (1 << octave)
        small = _lattice_float(gx, gy, seed + 101 * octave)
        tile = Image.new("F", (gx * 2, gy))
        tile.paste(small, (0, 0))
        tile.paste(small, (gx, 0))
        big = tile.resize((width * 2, height), Image.Resampling.BILINEAR)
        values = list(big.crop((0, 0, width, height)).getdata())
        if total is None:
            total = [v * amp for v in values]
        else:
            total = [a + v * amp for a, v in zip(total, values)]
        norm += amp
        amp *= persistence
    inverse = 1.0 / norm
    return [v * inverse for v in total]


# ================================================================ 小工具
def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return low if value < low else high if value > high else value


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    t = _clamp((x - edge0) / (edge1 - edge0) if edge1 != edge0 else 0.0)
    return t * t * (3.0 - 2.0 * t)


def _mix(a, b, t: float):
    t = _clamp(t)
    return (a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


def _rgba(color, alpha: float = 1.0):
    return (int(_clamp(color[0], 0, 255)), int(_clamp(color[1], 0, 255)),
            int(_clamp(color[2], 0, 255)), int(_clamp(alpha) * 255))


def _norm3(x: float, y: float, z: float):
    length = math.sqrt(x * x + y * y + z * z)
    return (x / length, y / length, z / length)


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ================================================================ 地球
def build_earth() -> Image.Image:
    """512x512 圆形地球圆盘：海洋/大陆/极冠/云带/大气边缘/夜面灯光。"""
    size = 512
    radius = 250.0
    center = size / 2.0

    base = _fbm(0x0E47A1, size, size, 3, 3, 5, 0.55)       # 大陆骨架
    detail = _fbm(0x051A7D, size, size, 7, 7, 5, 0.52)     # 海岸线细节
    warp = _fbm(0x09E3B1, size, size, 2, 2, 4, 0.60)       # 大陆漂移扰动
    cloud = _fbm(0x0C10D5, size, size, 4, 3, 6, 0.55)      # 云系

    light = _norm3(-0.46, -0.40, 0.79)                      # 太阳在左上偏前
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = image.load()

    for y in range(size):
        row = y * size
        for x in range(size):
            dx = (x + 0.5 - center) / radius
            dy = (y + 0.5 - center) / radius
            d2 = dx * dx + dy * dy
            distance = math.sqrt(d2)
            coverage = _clamp((1.0 - distance) * radius, 0.0, 1.0)  # 1px 抗锯齿圆边
            if coverage <= 0.0:
                continue

            z = math.sqrt(max(0.0, 1.0 - d2))
            index = row + x
            b, de, wp, cl = base[index], detail[index], warp[index], cloud[index]

            elevation = 0.60 * b + 0.24 * de + 0.16 * wp
            latitude = -dy  # +1 = 北极
            lambert = light[0] * dx + light[1] * dy + light[2] * z
            day = _clamp(lambert * 1.55)

            sea = 0.545 + 0.045 * (de - 0.5)
            land = elevation > sea
            if land:
                t = _clamp((elevation - sea) / 0.36)
                color = _mix((52, 100, 56), (120, 144, 84), _smoothstep(0.0, 0.55, t))
                color = _mix(color, (146, 136, 120), _smoothstep(0.55, 0.95, t))
                # 山脉脊线：detail 高的地方压成岩色，让大陆不是一团平色
                color = _mix(color, (118, 108, 94), _smoothstep(0.55, 0.78, de) * 0.45)
                # 副热带干燥带
                dry = (_smoothstep(0.55, 0.82, 0.5 + 0.5 * math.sin(latitude * 3.1))
                       * _smoothstep(0.40, 0.72, 1.0 - de))
                color = _mix(color, (178, 158, 112), dry * 0.60)
                color = _mix(color, (226, 234, 238), _smoothstep(0.90, 1.0, t) * 0.60)
                # 海岸浅滩：贴着海岸线给一圈清亮青绿，海岸线才读得出来
                if elevation < sea + 0.022:
                    color = _mix(color, (62, 156, 168), 0.45)
            else:
                depth = _clamp((sea - elevation) / 0.32)
                color = _mix((34, 128, 166), (4, 20, 58), depth)
                color = _mix((44, 152, 184), color, _smoothstep(0.0, 0.16, depth))
                # 洋流细纹
                color = _mix(color, (26, 96, 140), _smoothstep(0.55, 0.80, de) * 0.30)

            # 极冠：噪声边缘，极区陆地/海面都覆冰
            ice_edge = 0.72 + 0.10 * (de - 0.5) + 0.05 * (wp - 0.5)
            ice = _smoothstep(ice_edge, ice_edge + 0.12, abs(latitude))
            color = _mix(color, (226, 238, 246), ice)
            if not land:
                color = _mix(color, (198, 224, 238), _smoothstep(0.86, 0.97, abs(latitude)) * 0.9)

            # 云带：副热带稀疏、中纬浓密；云团内部薄厚不均，不糊成一片白
            cloud_value = 0.55 * cl + 0.45 * de
            cover = _smoothstep(0.56, 0.76, cloud_value)
            cover *= 0.55 + 0.45 * _smoothstep(0.05, 0.45, abs(latitude))
            cover *= 0.55 + 0.45 * _smoothstep(0.30, 0.75, 1.0 - cl)
            cover *= 1.0 - 0.5 * _smoothstep(0.80, 0.95, abs(latitude))
            if cover > 0.0:
                color = _mix(color, (234, 241, 247), min(0.85, cover * 1.10))

            # 光照 + 球面边缘衰减
            shade = (0.07 + 0.93 * day) * (0.70 + 0.30 * z)
            color = (color[0] * shade, color[1] * shade, color[2] * shade)

            # 海面镜面反光（收小范围、压低强度，避免整颗球像塑料）
            if not land and day > 0.62:
                spec = max(0.0, lambert) ** 14
                color = (color[0] + 70 * spec, color[1] + 95 * spec, color[2] + 120 * spec)

            # 夜面城市灯（陆地上稀疏暖点）
            if day < 0.22 and land and elevation > sea + 0.02:
                if _hash01(x // 2, y // 2, 0x1A5F) > 0.955:
                    k = _clamp((0.22 - day) / 0.22)
                    color = (color[0] + 190 * k, color[1] + 150 * k, color[2] + 70 * k)

            # 大气边缘薄辉（只在内侧，圆形 alpha 之外留空）
            if distance > 0.93:
                atmo = _smoothstep(0.93, 1.0, distance) * (0.35 + 0.65 * day)
                color = _mix(color, (90, 170, 235), atmo * 0.55)

            # 1px 细颗粒：打散插值噪声的「塑料感」
            grain = (_hash01(x, y, 0x1F37) - 0.5) * 0.10
            color = (color[0] * (1.0 + grain), color[1] * (1.0 + grain),
                     color[2] * (1.0 + grain))

            red, green, blue, _unused = _rgba(color, coverage)
            pixels[x, y] = (red, green, blue, _unused)

    return image


# ================================================================ 星云
def _add_star(pixels, width: int, height: int, x: int, y: int, brightness: float,
              tint: tuple[float, float, float], flare: float = 0.0,
              radius: int = 2, tightness: float = 1.2) -> None:
    """在星图上叠加一颗小星点（x 方向环绕，避免天球接缝），可选十字星芒。

    radius / tightness 控制尺寸：暗星给 radius=1（约 1px），亮星才给 radius=2。
    """
    for oy in range(-radius, radius + 1):
        py = y + oy
        if py < 0 or py >= height:
            continue
        for ox in range(-radius, radius + 1):
            px = (x + ox) % width
            falloff = math.exp(-(ox * ox + oy * oy) / tightness)
            if falloff < 0.03:
                continue
            add = brightness * falloff
            r, g, b = pixels[px, py]
            pixels[px, py] = (min(255, int(r + add * tint[0])),
                              min(255, int(g + add * tint[1])),
                              min(255, int(b + add * tint[2])))
    if flare > 0.0:
        for ox, oy in ((1, 0), (-1, 0), (2, 0), (-2, 0), (0, 1), (0, -1), (0, 2), (0, -2)):
            px = (x + ox) % width
            py = y + oy
            if 0 <= py < height:
                r, g, b = pixels[px, py]
                add = brightness * flare * (0.55 if abs(ox) + abs(oy) == 1 else 0.28)
                pixels[px, py] = (min(255, int(r + add * tint[0])),
                                  min(255, int(g + add * tint[1])),
                                  min(255, int(b + add * tint[2])))


def build_nebula() -> Image.Image:
    """1024x512 深空：蓝绿主星云 + 紫红星云 + 暖核 + 尘埃带 + 稀疏星点（水平环绕）。"""
    width, height = 1024, 512
    n1 = _fbm_periodic_x(0x05EED1, width, height, 3, 3, 6, 0.55)   # 主云团
    n2 = _fbm_periodic_x(0x07A11E, width, height, 5, 4, 5, 0.55)   # 副云团
    n3 = _fbm_periodic_x(0x0BAD5E, width, height, 9, 6, 5, 0.50)   # 细丝 / 尘埃
    band = _fbm_periodic_x(0x0C0FFE, width, height, 2, 1, 4, 0.55)  # 银河带

    image = Image.new("RGB", (width, height), (0, 0, 0))
    pixels = image.load()
    core_x, core_y = 0.71 * width, 0.33 * height
    core_sigma = 0.19 * width

    for y in range(height):
        row = y * width
        for x in range(width):
            index = row + x
            v1, v2, v3 = n1[index], n2[index], n3[index]
            milky = band[index]
            density = 0.50 * v1 + 0.30 * v2 + 0.20 * milky

            # 底色：深空黑蓝，随密度抬一点
            color = _mix((2, 4, 11), (10, 22, 46), _smoothstep(0.30, 0.85, density))

            # 蓝绿主云（抬高亮度，远看要有层次）
            teal = _smoothstep(0.50, 0.75, v1) * (0.45 + 0.55 * _smoothstep(0.25, 0.70, v2))
            color = _mix(color, (52, 208, 226), teal * 0.90)

            # 紫红副云
            violet = _smoothstep(0.53, 0.78, v2) * (0.40 + 0.60 * _smoothstep(0.35, 0.80, v1))
            color = _mix(color, (146, 100, 234), violet * 0.82)

            # 暖色核心（构图取参考图最亮区域附近，形状/位置是自画的）
            core = math.exp(-(((x - core_x) / core_sigma) ** 2
                              + ((y - core_y) / (core_sigma * 0.62)) ** 2))
            warm = core * (0.35 + 0.65 * teal) * (0.55 + 0.45 * v3)
            color = _mix(color, (255, 172, 96), warm * 0.95)
            color = _mix(color, (255, 232, 190), core * core * 0.55)

            # 尘埃带：压暗出层次
            dust = _smoothstep(0.30, 0.60, v3)
            color = (color[0] * (0.32 + 0.68 * dust), color[1] * (0.32 + 0.68 * dust),
                     color[2] * (0.38 + 0.62 * dust))

            # 高频丝状亮边
            ridge = _smoothstep(0.62, 0.90, 0.55 * v1 + 0.45 * v3)
            color = (color[0] + 34 * ridge, color[1] + 74 * ridge, color[2] + 96 * ridge)
            pixels[x, y] = _rgba(color)[:3]

    # —— 星点：两层稀疏撒点，绝大多数是 1px 暗星，只有少量亮星带星芒 ——
    # 1) 暗星：10px 网格、~18% 出现率、加色很轻
    for gy in range(0, height, 10):
        for gx in range(0, width, 10):
            if _hash01(gx, gy, 0x0FADE) > 0.18:
                continue
            sx = gx + 2 + int(_hash01(gx, gy, 0x11) * 6)
            sy = gy + 2 + int(_hash01(gx, gy, 0x22) * 6)
            if sy >= height:
                continue
            magnitude = 0.35 + 0.65 * _hash01(gx, gy, 0x33)
            tint_roll = _hash01(gx, gy, 0x44)
            tint = (205.0, 220.0, 255.0) if tint_roll < 0.70 else (255.0, 226.0, 196.0)
            _add_star(pixels, width, height, sx, sy, 26.0 * magnitude, tint,
                      radius=1, tightness=0.7)
    # 2) 亮星：36px 网格、~30% 出现率
    for gy in range(0, height, 36):
        for gx in range(0, width, 36):
            if _hash01(gx, gy, 0x0BEEF) > 0.30:
                continue
            sx = gx + 6 + int(_hash01(gx, gy, 0x55) * 22)
            sy = gy + 6 + int(_hash01(gx, gy, 0x66) * 22)
            if sx >= width or sy >= height:
                continue
            brightness = 70.0 + 90.0 * _hash01(gx, gy, 0x77)
            _add_star(pixels, width, height, sx, sy, brightness,
                      (235.0, 242.0, 255.0), radius=2, tightness=1.1)
    # 3) 十几颗带十字星芒的亮星（位置手动加确定性偏置，避免和网格星重合）
    for k in range(16):
        sx = int(_hash01(k, 0, 0x66) * width) % width
        sy = int(18 + _hash01(k, 1, 0x77) * (height - 36))
        _add_star(pixels, width, height, sx, sy, 190.0 + 60.0 * _hash01(k, 2, 0x88),
                  (255.0, 250.0, 240.0), flare=0.50, radius=2, tightness=1.3)

    return image


# ================================================================ 卫星：金箔舱体
def build_sat_body() -> Image.Image:
    """256x256 金色多层隔热膜（MLI）：三角褶皱面片 + 折痕 + 板缝 + 铆钉。"""
    size = 256
    grid = 9

    # 1) 褶皱面片明暗图（每个三角一个亮度，画出折痕）
    shade = Image.new("L", (size, size), 128)
    pen = ImageDraw.Draw(shade)
    vertices: list[list[tuple[float, float]]] = []
    for j in range(grid):
        row = []
        for i in range(grid):
            jitter = size / (grid - 1)
            vx = i * (size - 1) / (grid - 1) + (_hash01(i, j, 0x20) - 0.5) * jitter * 0.85
            vy = j * (size - 1) / (grid - 1) + (_hash01(i, j, 0x21) - 0.5) * jitter * 0.85
            row.append((vx, vy))
        vertices.append(row)
    for j in range(grid - 1):
        for i in range(grid - 1):
            v00, v10 = vertices[j][i], vertices[j][i + 1]
            v01, v11 = vertices[j + 1][i], vertices[j + 1][i + 1]
            for tri, salt in (((v00, v10, v01), 0), ((v10, v11, v01), 1)):
                value = int(70 + 150 * _hash01(i, j, 0x30 + salt))
                pen.polygon(tri, fill=value)
            for a, b in ((v00, v10), (v00, v01), (v10, v11), (v01, v11), (v10, v01)):
                pen.line([a, b], fill=42, width=1)
    shade = shade.filter(ImageFilter.GaussianBlur(0.8))

    # 2) 金箔底色 + 面片明暗 + 高光 + 细颗粒
    gold_top = (238, 200, 118)
    gold_bottom = (146, 100, 38)
    image = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            t = y / (size - 1)
            base = _mix(gold_top, gold_bottom, t)
            s = shade.getpixel((x, y)) / 255.0
            spec = max(0.0, s - 0.74) ** 1.4 * 1.9
            grain = _hash01(x, y, 0x50)
            color = (base[0] * (0.52 + 0.78 * s) * (0.93 + 0.14 * grain) + 200 * spec,
                     base[1] * (0.52 + 0.78 * s) * (0.93 + 0.14 * grain) + 190 * spec,
                     base[2] * (0.52 + 0.78 * s) * (0.93 + 0.14 * grain) + 150 * spec)
            # 边缘轻微压暗，贴到盒子上时六个面边界更清楚
            edge = min(x, y, size - 1 - x, size - 1 - y) / 10.0
            color = _mix((40, 30, 14), color, _clamp(edge))
            pixels[x, y] = _rgba(color)

    # 3) 板缝 + 铆钉（横两条、竖一条）
    pen = ImageDraw.Draw(image)
    for line_y in (size // 3, size * 2 // 3):
        pen.line([(0, line_y), (size - 1, line_y)], fill=(92, 66, 28, 255), width=2)
        pen.line([(0, line_y + 2), (size - 1, line_y + 2)], fill=(248, 214, 140, 255), width=1)
        for x in range(10, size, 26):
            pen.ellipse([x - 1, line_y - 2, x + 1, line_y + 1], fill=(216, 178, 96, 255))
    pen.line([(size // 2, 0), (size // 2, size - 1)], fill=(104, 74, 30, 255), width=2)
    pen.line([(size // 2 + 2, 0), (size // 2 + 2, size - 1)], fill=(244, 208, 132, 255), width=1)
    return image


# ================================================================ 卫星：太阳能电池片
def build_sat_panel() -> Image.Image:
    """256x256 太阳能电池阵列：4x6 电池片 + 银色栅线 + 金色外框 + 斜向反光。"""
    size = 256
    columns, rows = 4, 6
    margin, gap = 11, 4

    image = Image.new("RGBA", (size, size), (26, 22, 12, 255))
    pen = ImageDraw.Draw(image)
    pen.rectangle([0, 0, size - 1, size - 1], fill=(58, 48, 24, 255))
    pen.rectangle([margin - 4, margin - 4, size - margin + 3, size - margin + 3],
                  fill=(12, 18, 34, 255), outline=(96, 82, 44, 255), width=2)

    cell_w = (size - 2 * margin - (columns - 1) * gap) // columns
    cell_h = (size - 2 * margin - (rows - 1) * gap) // rows
    for r in range(rows):
        for c in range(columns):
            x0 = margin + c * (cell_w + gap)
            y0 = margin + r * (cell_h + gap)
            variant = _hash01(c, r, 0x9A)
            base = (18 + 10 * variant, 36 + 16 * variant, 82 + 34 * variant)
            for yy in range(cell_h):
                f = 1.0 - 0.22 * yy / cell_h
                color = (int(base[0] * f), int(base[1] * f), int(base[2] * f))
                pen.line([(x0, y0 + yy), (x0 + cell_w - 1, y0 + yy)], fill=color)
            pen.rectangle([x0, y0, x0 + cell_w - 1, y0 + cell_h - 1],
                          outline=(104, 122, 150, 255), width=1)
            # 电池片栅线（两根竖向细线 + 一根横向）
            for bx in (x0 + cell_w // 3, x0 + cell_w * 2 // 3):
                pen.line([(bx, y0 + 2), (bx, y0 + cell_h - 3)], fill=(66, 84, 118, 255), width=1)
            pen.line([(x0 + 2, y0 + cell_h // 2), (x0 + cell_w - 3, y0 + cell_h // 2)],
                     fill=(58, 74, 106, 255), width=1)
            # 电池片角上的小反光
            pen.point([(x0 + 2, y0 + 2)], fill=(150, 176, 206, 255))
            pen.point([(x0 + cell_w - 3, y0 + cell_h - 3)], fill=(96, 116, 150, 255))

    # 斜向反光：半透明白色条带，叠一层避免 ImageDraw 直接覆盖 alpha
    sheen = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sheen_draw = ImageDraw.Draw(sheen)
    sheen_draw.polygon([(20, 0), (120, 0), (40, size - 1), (-20, size - 1)],
                       fill=(210, 235, 255, 26))
    sheen_draw.polygon([(140, 0), (178, 0), (96, size - 1), (58, size - 1)],
                       fill=(210, 235, 255, 16))
    image = Image.alpha_composite(image, sheen)

    # 四边金色安装压边
    pen = ImageDraw.Draw(image)
    for x0, y0, x1, y1 in ((margin - 6, margin - 6, size - margin + 5, margin - 2),
                           (margin - 6, size - margin + 1, size - margin + 5, size - margin + 5),
                           (margin - 6, margin - 6, margin - 2, size - margin + 5),
                           (size - margin + 1, margin - 6, size - margin + 5, size - margin + 5)):
        pen.rectangle([x0, y0, x1, y1], fill=(112, 92, 46, 255))
        pen.line([(x0, y0), (x1, y1)], fill=(196, 168, 96, 255), width=1)
    return image


# ================================================================ 卫星：抛物面天线
def build_sat_dish() -> Image.Image:
    """256x256 白色抛物面天线：同心肋环 + 八向拼缝 + 中心馈源 + 圆形透明底。"""
    size = 256
    center = size / 2.0
    radius = 124.0
    light = _norm3(-0.42, -0.50, 0.76)

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            dx = (x + 0.5 - center) / radius
            dy = (y + 0.5 - center) / radius
            d = math.sqrt(dx * dx + dy * dy)
            coverage = _clamp((1.0 - d) * radius * 0.5 + 0.5, 0.0, 1.0)
            if coverage <= 0.0:
                continue
            angle = math.atan2(dy, dx)

            # 抛物面法线：越靠边缘越向外倾
            tilt = d * 0.9
            nz = math.sqrt(max(0.0, 1.0 - tilt * tilt))
            nx = math.cos(angle) * tilt
            ny = math.sin(angle) * tilt
            lambert = _clamp(nx * light[0] + ny * light[1] + nz * light[2])
            color = _mix((150, 160, 170), (246, 248, 250), 0.30 + 0.72 * lambert)

            # 同心肋环：一圈压暗、内侧提亮，读出抛物面层叠感
            rib = (d * 9.2) % 1.0
            if d < 0.965 and rib < 0.10:
                color = _mix(color, (118, 128, 138), 0.55)
            elif d < 0.965 and rib < 0.20:
                color = _mix(color, (255, 255, 255), 0.35)

            # 八向拼缝
            sector = (angle + math.pi) / (math.pi / 4.0)
            if d > 0.10 and abs(sector - round(sector)) < 0.035:
                color = _mix(color, (110, 120, 130), 0.55)

            # 中心馈源：亮灰圆盘 + 暗环 + 中心点
            if d < 0.105:
                color = _mix((198, 204, 210), (238, 242, 246), 0.5 + 0.5 * lambert)
            if 0.085 < d < 0.105:
                color = _mix(color, (120, 130, 140), 0.65)
            if d < 0.022:
                color = (74, 82, 92)

            # 外圈翻边：最外侧 2px 亮边 + 内圈暗缝
            if d > 0.965:
                color = _mix(color, (252, 253, 255), 0.75)
            elif d > 0.95:
                color = _mix(color, (120, 130, 140), 0.45)

            # 高光扫过（左上）
            spec = max(0.0, lambert) ** 6
            color = (color[0] + 60 * spec, color[1] + 70 * spec, color[2] + 80 * spec)
            pixels[x, y] = _rgba(color, coverage)

    return image


# ================================================================ 输出
def _save_preview(preview_dir: str, name: str, image: Image.Image) -> str:
    scale = 2
    big = image.resize((image.width * scale, image.height * scale),
                       Image.Resampling.LANCZOS)
    path = os.path.join(preview_dir, "%s_x%d.png" % (name, scale))
    big.save(path, "PNG")
    return path


def _guard_preview_dir(preview_dir: str) -> str:
    resolved = os.path.abspath(preview_dir)
    root = os.path.abspath(ROOT)
    try:
        common = os.path.commonpath([resolved, root])
    except ValueError:
        common = None
    if common == root:
        raise SystemExit("--preview 目录必须在仓库之外（现在指向 %s）" % resolved)
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 P4-A1 太空舞台原创贴图")
    parser.add_argument("--preview", metavar="DIR",
                        help="可选的放大预览输出目录（必须在仓库之外，不写进模组资源）")
    args = parser.parse_args()

    os.makedirs(ENV_DIR, exist_ok=True)
    builders = (
        ("earth", EARTH, build_earth),
        ("nebula", NEBULA, build_nebula),
        ("sat_body", SAT_BODY, build_sat_body),
        ("sat_panel", SAT_PANEL, build_sat_panel),
        ("sat_dish", SAT_DISH, build_sat_dish),
    )
    written = []
    for name, path, builder in builders:
        image = builder()
        image.save(path, "PNG")
        written.append((name, path, image))
        print("wrote %-9s %s  (%dx%d %s, %d bytes, sha256=%s)"
              % (name, os.path.relpath(path, ROOT), image.width, image.height,
                 image.mode, os.path.getsize(path), _sha256(path)[:16]))

    if args.preview:
        preview_dir = _guard_preview_dir(args.preview)
        os.makedirs(preview_dir, exist_ok=True)
        for name, _path, image in written:
            print("preview", _save_preview(preview_dir, name, image))

    expectations = {
        "earth": ((512, 512), "RGBA"),
        "nebula": ((1024, 512), "RGB"),
        "sat_body": ((256, 256), "RGBA"),
        "sat_panel": ((256, 256), "RGBA"),
        "sat_dish": ((256, 256), "RGBA"),
    }
    failures = []
    for name, _path, image in written:
        size, mode = expectations[name]
        if image.size != size or image.mode != mode:
            failures.append("%s: got %s %s, expected %s %s"
                            % (name, image.size, image.mode, size, mode))
    if failures:
        print("FAIL")
        for line in failures:
            print("  -", line)
        return 1
    print("OK: 5 张贴图尺寸/模式符合预期")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
