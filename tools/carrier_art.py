#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-A2/A3 天基载体电影板 —— 原创程序化 2.5D 块面化重绘。

用户明确要求：天基炮 / 天基矛发射器 / 引力奇点 / 等离子发射器 / 小行星 这五张电影板
不能再使用参考图（仓库根 天基炮.png 等），必须自行绘制。本脚本用确定性整数哈希噪声 +
一个极简块面 3D 渲染器（箱体 / 桁架 / 圆柱 / 加速环 / 太阳能板）画出**块面化**的载体，
背景统一为深空星野 + 底部地球弧面 + 镜头光晕；不读取、不采样、不缩放、不裁切任何参考图。

产出（覆盖）：
    textures/environment/carrier_cannon.png        1408x768 RGB  天基炮（炮口朝左下）
    textures/environment/carrier_lance.png         1408x768 RGB  天基矛（长发射轨朝左）
    textures/environment/carrier_singularity.png   1408x768 RGB  引力奇点（环站左中，开口朝右）
    textures/environment/carrier_plasma.png        1408x768 RGB  等离子（舰体左上，光束射向右下）
    textures/environment/carrier_asteroid.png      1408x768 RGB  小行星（岩体居中，地球在下）
    textures/environment/carrier_asteroid_cutout.png 600x600 RGBA 小行星抠图（轮廓外 alpha=0）

构图锚点来自 client/renderer/OrbitalCarrierPlates.spec()（Java 在这些归一化坐标叠充能 /
炮口 / 引擎光）：
    CANNON       muzzle(0.455,0.515) focus(0.70,0.33) impact(0.205,0.795)
                 engines(0.84,0.28)(0.91,0.34)(0.83,0.45)(0.78,0.20)
    LANCE        muzzle/charge(0.600,0.530) focus(0.36,0.38) impact-out(0.970,0.760)
                 engines(0.12,0.30)(0.46,0.58)(0.43,0.66)(0.55,0.62)
    SINGULARITY  muzzle/charge(0.835,0.490) focus(0.44,0.47)
                 engines(0.15,0.22)(0.14,0.70)(0.62,0.83)(0.28,0.10)
    PLASMA       muzzle(0.478,0.352) charge(0.300,0.300) impact(0.820,0.700)
                 engines(0.12,0.22)(0.49,0.31)(0.15,0.45)
                 + STORM_IMPACTS 七个落点
    ASTEROID     centre(0.49,0.47) impact(0.49,0.58)

用法：
    python tools/carrier_art.py
    python tools/carrier_art.py --preview <仓库外的目录>   # 另出 1x 预览

资产门禁见 tools/check_carrier_art.py（尺寸/格式 + 与本模式参考图的 dHash 距离 >= 18）。
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_DIR = os.path.join(
    ROOT, "src", "main", "resources", "assets", "apocalypse_zombies", "textures", "environment")

W, H = 1408, 768
CUT = 600

OUTPUTS = {
    "cannon": os.path.join(ENV_DIR, "carrier_cannon.png"),
    "lance": os.path.join(ENV_DIR, "carrier_lance.png"),
    "singularity": os.path.join(ENV_DIR, "carrier_singularity.png"),
    "plasma": os.path.join(ENV_DIR, "carrier_plasma.png"),
    "asteroid": os.path.join(ENV_DIR, "carrier_asteroid.png"),
    "asteroid_cutout": os.path.join(ENV_DIR, "carrier_asteroid_cutout.png"),
}

# ---------------------------------------------------------------- 调色板
HULL_DARK = (44, 50, 58)
HULL = (72, 80, 90)
HULL_MID = (96, 106, 118)
HULL_LIGHT = (138, 150, 162)
HULL_WHITE = (206, 214, 222)
GOLD = (182, 138, 64)
GOLD_LIGHT = (232, 196, 120)
COPPER = (146, 92, 48)
SOLAR_DARK = (14, 24, 48)
SOLAR = (26, 46, 88)
SOLAR_LIGHT = (44, 76, 136)
EMIT_ORANGE = (255, 150, 58)
EMIT_AMBER = (255, 196, 110)
EMIT_CYAN = (120, 235, 255)
EMIT_BLUE = (120, 180, 255)
EMIT_VIOLET = (178, 140, 255)
EMIT_RED = (255, 92, 72)
WHITE_HOT = (255, 252, 244)


# ================================================================ 确定性噪声
_U32 = 0xFFFFFFFF


def _hash_u32(*values: int) -> int:
    h = 0x9E3779B9
    for value in values:
        h = (h ^ (int(value) & _U32)) * 0x85EBCA6B & _U32
        h ^= h >> 13
        h = h * 0xC2B2AE35 & _U32
        h ^= h >> 16
    return h & _U32


def _hash01(*values: int) -> float:
    return _hash_u32(*values) / 4294967295.0


def _lattice(gx: int, gy: int, seed: int) -> Image.Image:
    img = Image.new("F", (gx, gy))
    img.putdata([_hash01(x, y, seed) for y in range(gy) for x in range(gx)])
    return img


def _fbm_list(width: int, height: int, gx0: int, gy0: int, octaves: int,
              persistence: float, seed: int) -> list[float]:
    total: list[float] | None = None
    amp, norm = 1.0, 0.0
    for octave in range(octaves):
        gx = gx0 * (1 << octave)
        gy = gy0 * (1 << octave)
        big = _lattice(gx, gy, seed + 101 * octave).resize(
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


def _fbm_image(width: int, height: int, gx0: int, gy0: int, octaves: int,
               persistence: float, seed: int) -> Image.Image:
    img = Image.new("F", (width, height))
    img.putdata(_fbm_list(width, height, gx0, gy0, octaves, persistence, seed))
    return img


# ================================================================ 小工具
def _clamp(value: float, low: float = 0.0, high: float = 255.0) -> float:
    return low if value < low else high if value > high else value


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    t = _clamp((x - edge0) / (edge1 - edge0) if edge1 != edge0 else 0.0, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _mix(a, b, t: float):
    t = max(0.0, min(1.0, t))
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _rgb(color):
    return (int(_clamp(color[0])), int(_clamp(color[1])), int(_clamp(color[2])))


def _posterize(color, step: int = 16):
    """把颜色量化到固定档位：块面化配色（Minecraft 地图色阶的感觉）。"""
    return (int(_clamp(color[0], 0, 255) // step) * step,
            int(_clamp(color[1], 0, 255) // step) * step,
            int(_clamp(color[2], 0, 255) // step) * step)


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ================================================================ 加法光层
class LightLayer:
    """把若干光斑/光束/爆点累加进一张 RGB 画布（加法混合 + 高斯模糊晕开）。"""

    def __init__(self, width: int, height: int):
        self.w, self.h = width, height
        self.channels = [Image.new("L", (width, height), 0) for _ in range(3)]

    def _accumulate(self, mask: Image.Image, color, strength: float) -> None:
        for index in range(3):
            factor = (color[index] / 255.0) * strength
            contribution = mask.point(lambda v, f=factor: int(min(255.0, v * f)))
            self.channels[index] = ImageChops.add(self.channels[index], contribution)

    def _mask(self) -> Image.Image:
        return Image.new("L", (self.w, self.h), 0)

    def radial(self, cx: float, cy: float, radius: float, color, strength: float,
               power: float = 2.0, blur: float = 0.0) -> None:
        size = 96
        sprite = Image.new("L", (size, size), 0)
        sprite_pixels = sprite.load()
        half = size / 2.0
        for y in range(size):
            for x in range(size):
                d = math.hypot(x + 0.5 - half, y + 0.5 - half) / half
                if d < 1.0:
                    sprite_pixels[x, y] = int(255 * (1.0 - d) ** power)
        radius = max(2.0, radius)
        big = sprite.resize((int(radius * 2), int(radius * 2)),
                            Image.Resampling.BILINEAR)
        if blur > 0.0:
            big = big.filter(ImageFilter.GaussianBlur(blur))
        mask = self._mask()
        mask.paste(big, (int(cx - radius), int(cy - radius)))
        self._accumulate(mask, color, strength)

    def line(self, p0, p1, width: float, color, strength: float,
             blur: float = 0.0) -> None:
        mask = self._mask()
        draw = ImageDraw.Draw(mask)
        draw.line([(int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1]))],
                  fill=255, width=max(1, int(width)))
        if blur > 0.0:
            mask = mask.filter(ImageFilter.GaussianBlur(blur))
        self._accumulate(mask, color, strength)

    def ring(self, cx: float, cy: float, radius: float, width: float, color, strength: float,
             blur: float = 0.0) -> None:
        mask = self._mask()
        draw = ImageDraw.Draw(mask)
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                     outline=255, width=max(1, int(width)))
        if blur > 0.0:
            mask = mask.filter(ImageFilter.GaussianBlur(blur))
        self._accumulate(mask, color, strength)

    def apply(self, base: Image.Image) -> Image.Image:
        base_r, base_g, base_b = base.split()
        channels = [ImageChops.add(base_r, self.channels[0]),
                    ImageChops.add(base_g, self.channels[1]),
                    ImageChops.add(base_b, self.channels[2])]
        return Image.merge("RGB", channels)


# ================================================================ 星野 / 地球背景
def _space_base(seed: int, nebula_strength: float, nebula_warm) -> Image.Image:
    """低分辨率星云画布（8 倍最近邻放大 => 块面化）。"""
    lw, lh = W // 8, H // 8
    n1 = _fbm_list(lw, lh, 3, 2, 5, 0.55, seed)
    n2 = _fbm_list(lw, lh, 5, 3, 4, 0.52, seed + 31)
    n3 = _fbm_list(lw, lh, 9, 5, 4, 0.50, seed + 61)
    small = Image.new("RGB", (lw, lh), (0, 0, 0))
    pixels = small.load()
    warm_x, warm_y = nebula_warm
    for y in range(lh):
        for x in range(lw):
            index = y * lw + x
            v1, v2, v3 = n1[index], n2[index], n3[index]
            color = _mix((3, 4, 10), (7, 14, 30), _smoothstep(0.25, 0.85, v1))
            teal = _smoothstep(0.52, 0.80, v1) * (0.5 + 0.5 * _smoothstep(0.3, 0.8, v2))
            color = _mix(color, (26, 104, 128), teal * 0.55 * nebula_strength)
            violet = _smoothstep(0.56, 0.82, v2) * (0.4 + 0.6 * _smoothstep(0.35, 0.8, v1))
            color = _mix(color, (74, 52, 132), violet * 0.50 * nebula_strength)
            core = math.exp(-(((x / lw - warm_x) / 0.20) ** 2
                              + ((y / lh - warm_y) / 0.14) ** 2))
            color = _mix(color, (156, 112, 70), core * 0.65 * nebula_strength)
            color = _mix(color, (206, 170, 128), core * core * 0.35 * nebula_strength)
            dust = _smoothstep(0.30, 0.58, v3)
            color = (color[0] * (0.45 + 0.55 * dust), color[1] * (0.45 + 0.55 * dust),
                     color[2] * (0.50 + 0.50 * dust))
            pixels[x, y] = _rgb(color)
    return small.resize((W, H), Image.Resampling.NEAREST)


def _stars(base: Image.Image, seed: int, density: float = 0.30,
           earth=None) -> Image.Image:
    draw = ImageDraw.Draw(base)
    earth_guard = None
    if earth is not None:
        cx, cy, radius = earth
        earth_guard = (cx, cy, radius * 1.01)
    for gy in range(0, H, 12):
        for gx in range(0, W, 12):
            if _hash01(gx, gy, seed) > density:
                continue
            x = gx + 2 + int(_hash01(gx, gy, seed + 1) * 8)
            y = gy + 2 + int(_hash01(gx, gy, seed + 2) * 8)
            if x >= W or y >= H:
                continue
            if earth_guard is not None:
                if math.hypot(x - earth_guard[0], y - earth_guard[1]) < earth_guard[2]:
                    continue
            roll = _hash01(gx, gy, seed + 3)
            bright = int(90 + 165 * roll)
            if _hash01(gx, gy, seed + 4) < 0.90:
                draw.point((x, y), fill=(bright, bright, min(255, bright + 20)))
            else:
                size = 2 if roll > 0.55 else 1
                draw.rectangle([x, y, x + size, y + size],
                               fill=(bright, bright, min(255, bright + 30)))
                if roll > 0.97:
                    draw.line([(x - 3, y), (x + 4, y)], fill=(120, 140, 170), width=1)
                    draw.line([(x, y - 3), (x, y + 4)], fill=(120, 140, 170), width=1)
    return base


def _earth_layer(cx: float, cy: float, radius: float, seed: int) -> Image.Image:
    """低分辨率（1/8）块面地球：硬阈值海岸线 + 分档配色 + 块状云，放大后是 8px 方块。"""
    scale = 8
    lw, lh = W // scale, H // scale
    cxl, cyl, rl = cx / scale, cy / scale, radius / scale
    base = _fbm_list(lw, lh, 3, 2, 4, 0.55, seed)
    detail = _fbm_list(lw, lh, 6, 4, 4, 0.50, seed + 17)
    cloud = _fbm_list(lw, lh, 4, 3, 4, 0.55, seed + 41)
    layer = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    pixels = layer.load()
    light = (-0.42, -0.52, 0.74)
    for y in range(lh):
        for x in range(lw):
            dx = (x + 0.5 - cxl) / rl
            dy = (y + 0.5 - cyl) / rl
            d2 = dx * dx + dy * dy
            if d2 > 1.0:
                continue  # 硬边圆形遮罩 => 放大后是 8px 方块轮廓
            d = math.sqrt(d2)
            z = math.sqrt(max(0.0, 1.0 - d2))
            index = y * lw + x
            b, de, cl = base[index], detail[index], cloud[index]
            elevation = 0.70 * b + 0.30 * de
            latitude = -dy
            lambert = light[0] * dx + light[1] * dy + light[2] * z
            day = _clamp(lambert * 1.7, 0.0, 1.0)

            # 陆地/海洋：硬阈值 + 3 档色，海岸线是方块台阶
            if elevation > 0.535:
                if elevation > 0.66:
                    color = (126, 132, 96)
                elif elevation > 0.60:
                    color = (96, 124, 72)
                else:
                    color = (58, 104, 58)
                if de > 0.62:
                    color = (140, 128, 104)
                dry = _smoothstep(0.55, 0.82, 0.5 + 0.5 * math.sin(latitude * 3.1))
                if dry > 0.62:
                    color = (172, 152, 108)
            else:
                depth = _clamp((0.535 - elevation) / 0.30, 0.0, 1.0)
                if depth < 0.30:
                    color = (48, 124, 176)
                elif depth < 0.65:
                    color = (28, 88, 148)
                else:
                    color = (10, 38, 88)
            if abs(latitude) > 0.76:
                color = (226, 236, 244)

            # 云：硬阈值 + 两级色块（云体 / 云影）
            cloud_value = 0.60 * cl + 0.40 * de
            if cloud_value > 0.62:
                color = (238, 244, 248)
            elif cloud_value > 0.56:
                color = (196, 214, 228)

            shade = (0.28 + 0.85 * day) * (0.70 + 0.30 * z)
            color = (color[0] * shade, color[1] * shade, color[2] * shade)
            # 大气：两档硬边，不做大范围模糊
            if d > 0.94:
                color = _mix(color, (96, 176, 236), 0.55)
            elif d > 0.90:
                color = _mix(color, (70, 140, 210), 0.28)
            pixels[x, y] = _posterize(color, 16) + (255,)
    return layer.resize((W, H), Image.Resampling.NEAREST)


def _vignette(base: Image.Image, strength: float = 0.42) -> Image.Image:
    lw, lh = 88, 48
    small = Image.new("L", (lw, lh), 255)
    pixels = small.load()
    for y in range(lh):
        for x in range(lw):
            u = (x + 0.5) / lw - 0.5
            v = (y + 0.5) / lh - 0.5
            d = math.hypot(u, v) / 0.707
            pixels[x, y] = int(255 * (1.0 - strength * min(1.0, d) ** 2.2))
    mask = small.resize((W, H), Image.Resampling.BICUBIC)
    return ImageChops.multiply(base, Image.merge("RGB", (mask, mask, mask)))


def _space_background(seed: int, earth, nebula_strength: float = 0.7,
                      warm=(0.72, 0.30), sun=None) -> Image.Image:
    """深空星野 + 地球弧面 + 镜头光晕。earth=None 表示不画地球。"""
    base = _space_base(seed, nebula_strength, warm)
    if earth is not None:
        cx, cy, radius = earth
        layer = _earth_layer(cx, cy, radius, seed + 5)
        base.paste(layer, (0, 0), layer.getchannel("A"))
        # 大气外辉光（细窄一圈，避免大面积高斯模糊把地球糊掉）
        glow = LightLayer(W, H)
        glow.ring(cx, cy, radius * 0.998, radius * 0.020,
                  (120, 190, 245), 0.38, blur=radius * 0.006)
        base = glow.apply(base)
    base = _stars(base, seed + 101, earth=earth)
    if sun is not None:
        sx, sy, size, color = sun
        flare = LightLayer(W, H)
        flare.radial(sx, sy, size * 2.6, color, 0.55, power=2.4, blur=size * 0.25)
        flare.radial(sx, sy, size * 0.8, (255, 250, 235), 0.75, power=2.0)
        flare.line((sx - size * 2.2, sy), (sx + size * 2.2, sy), size * 0.05,
                   color, 0.55, blur=size * 0.06)
        flare.line((sx, sy - size * 2.2), (sx, sy + size * 2.2), size * 0.05,
                   color, 0.45, blur=size * 0.06)
        base = flare.apply(base)
    return base


# ================================================================ 块面 3D 渲染器
def _rotate(x: float, y: float, z: float, yaw: float, pitch: float, roll: float,
            flip_y: bool = False):
    if flip_y:
        y = -y
    cp, sp = math.cos(pitch), math.sin(pitch)
    y, z = y * cp - z * sp, y * sp + z * cp
    cy, sy = math.cos(yaw), math.sin(yaw)
    x, z = x * cy + z * sy, -x * sy + z * cy
    cr, sr = math.cos(roll), math.sin(roll)
    x, y = x * cr - y * sr, x * sr + y * cr
    return x, y, z


def _frame_from_axis(axis):
    """由轴向量得到环面基向量 (axis, u, v)，三者单位正交。"""
    length = math.sqrt(axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2)
    ax = (axis[0] / length, axis[1] / length, axis[2] / length)
    ref = (0.0, 1.0, 0.0) if abs(ax[1]) < 0.9 else (1.0, 0.0, 0.0)
    u = (ax[1] * ref[2] - ax[2] * ref[1], ax[2] * ref[0] - ax[0] * ref[2],
         ax[0] * ref[1] - ax[1] * ref[0])
    ul = math.sqrt(u[0] ** 2 + u[1] ** 2 + u[2] ** 2)
    u = (u[0] / ul, u[1] / ul, u[2] / ul)
    v = (ax[1] * u[2] - ax[2] * u[1], ax[2] * u[0] - ax[0] * u[2],
         ax[0] * u[1] - ax[1] * u[0])
    return ax, u, v


def _torus_ring(model, center, axis, radius: float, sides: int,
                axial_half: float, radial_half: float,
                color_a, color_b, emit_color=None, emit_radius_offset: float = 1.9,
                emit_half: float = 0.16) -> None:
    """用一圈有厚度的方块拼 3D 环体（内外径 + 轴向厚度 + 明暗交错 + 发光环带）。"""
    ax, u, v = _frame_from_axis(axis)
    seg = math.pi * radius / sides * 1.08
    for i in range(sides):
        angle = 2.0 * math.pi * i / sides
        direction = (u[0] * math.cos(angle) + v[0] * math.sin(angle),
                     u[1] * math.cos(angle) + v[1] * math.sin(angle),
                     u[2] * math.cos(angle) + v[2] * math.sin(angle))
        tangent = (ax[1] * direction[2] - ax[2] * direction[1],
                   ax[2] * direction[0] - ax[0] * direction[2],
                   ax[0] * direction[1] - ax[1] * direction[0])
        pos = (center[0] + direction[0] * radius,
               center[1] + direction[1] * radius,
               center[2] + direction[2] * radius)
        color = color_a if i % 2 == 0 else color_b
        model.obox(pos, direction, ax, tangent,
                   (radial_half, axial_half, seg), color)
        if emit_color is not None:
            emit_pos = (center[0] + direction[0] * (radius + emit_radius_offset),
                        center[1] + direction[1] * (radius + emit_radius_offset),
                        center[2] + direction[2] * (radius + emit_radius_offset))
            model.obox(emit_pos, direction, ax, tangent,
                       (emit_half, axial_half * 0.72, seg), emit_color, emissive=True)


class Model:
    """块面模型：一串多边形面（局部 3D 坐标 + 颜色 + 是否自发光）。"""

    def __init__(self):
        self.faces: list[tuple[tuple, tuple, bool]] = []

    def face(self, points, color, emissive: bool = False) -> None:
        if len(points) >= 3:
            self.faces.append((tuple(points), tuple(color), emissive))

    def box(self, center, size, color, emissive: bool = False) -> None:
        cx, cy, cz = center
        hx, hy, hz = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
        v = [
            (cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
            (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
            (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz),
            (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz),
        ]
        for quad in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
                     (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
            self.face([v[i] for i in quad], color, emissive)

    def obox(self, center, ex, ey, ez, half, color, emissive: bool = False) -> None:
        """任意朝向的方块：ex/ey/ez 为单位轴，half 是三个半长。"""
        corners = []
        for sx, sy, sz in ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
                           (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)):
            corners.append((
                center[0] + ex[0] * sx * half[0] + ey[0] * sy * half[1] + ez[0] * sz * half[2],
                center[1] + ex[1] * sx * half[0] + ey[1] * sy * half[1] + ez[1] * sz * half[2],
                center[2] + ex[2] * sx * half[0] + ey[2] * sy * half[1] + ez[2] * sz * half[2],
            ))
        for quad in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
                     (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
            self.face([corners[i] for i in quad], color, emissive)

    def _basis(self, p0, p1):
        dx, dy, dz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length < 1e-6:
            return None
        d = (dx / length, dy / length, dz / length)
        ref = (0.0, 1.0, 0.0) if abs(d[1]) < 0.9 else (1.0, 0.0, 0.0)
        u = (d[1] * ref[2] - d[2] * ref[1], d[2] * ref[0] - d[0] * ref[2],
             d[0] * ref[1] - d[1] * ref[0])
        ul = math.sqrt(u[0] ** 2 + u[1] ** 2 + u[2] ** 2)
        u = (u[0] / ul, u[1] / ul, u[2] / ul)
        v = (d[1] * u[2] - d[2] * u[1], d[2] * u[0] - d[0] * u[2],
             d[0] * u[1] - d[1] * u[0])
        return d, u, v

    def beam(self, p0, p1, half_width: float, color, emissive: bool = False) -> None:
        basis = self._basis(p0, p1)
        if basis is None:
            return
        _, u, v = basis
        hw = half_width
        corners0 = [(p0[0] + u[0] * su * hw + v[0] * sv * hw,
                     p0[1] + u[1] * su * hw + v[1] * sv * hw,
                     p0[2] + u[2] * su * hw + v[2] * sv * hw)
                    for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        corners1 = [(p1[0] + u[0] * su * hw + v[0] * sv * hw,
                     p1[1] + u[1] * su * hw + v[1] * sv * hw,
                     p1[2] + u[2] * su * hw + v[2] * sv * hw)
                    for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        for i in range(4):
            j = (i + 1) % 4
            self.face([corners0[i], corners0[j], corners1[j], corners1[i]], color, emissive)
        self.face(corners0, color, emissive)
        self.face(list(reversed(corners1)), color, emissive)

    def cyl(self, p0, p1, radius: float, sides: int, color, emissive: bool = False) -> None:
        basis = self._basis(p0, p1)
        if basis is None:
            return
        _, u, v = basis
        ring0, ring1 = [], []
        for i in range(sides):
            angle = 2.0 * math.pi * i / sides
            cu, sv = math.cos(angle) * radius, math.sin(angle) * radius
            ring0.append((p0[0] + u[0] * cu + v[0] * sv,
                          p0[1] + u[1] * cu + v[1] * sv,
                          p0[2] + u[2] * cu + v[2] * sv))
            ring1.append((p1[0] + u[0] * cu + v[0] * sv,
                          p1[1] + u[1] * cu + v[1] * sv,
                          p1[2] + u[2] * cu + v[2] * sv))
        for i in range(sides):
            j = (i + 1) % sides
            self.face([ring0[i], ring0[j], ring1[j], ring1[i]], color, emissive)
        self.face(list(reversed(ring0)), color, emissive)
        self.face(ring1, color, emissive)

    def ring(self, center, axis, r_out: float, r_in: float, thickness: float,
             sides: int, color, emissive: bool = False) -> None:
        ax = axis[0], axis[1], axis[2]
        length = math.sqrt(ax[0] ** 2 + ax[1] ** 2 + ax[2] ** 2)
        ax = (ax[0] / length, ax[1] / length, ax[2] / length)
        ref = (0.0, 1.0, 0.0) if abs(ax[1]) < 0.9 else (1.0, 0.0, 0.0)
        u = (ax[1] * ref[2] - ax[2] * ref[1], ax[2] * ref[0] - ax[0] * ref[2],
             ax[0] * ref[1] - ax[1] * ref[0])
        ul = math.sqrt(u[0] ** 2 + u[1] ** 2 + u[2] ** 2)
        u = (u[0] / ul, u[1] / ul, u[2] / ul)
        v = (ax[1] * u[2] - ax[2] * u[1], ax[2] * u[0] - ax[0] * u[2],
             ax[0] * u[1] - ax[1] * u[0])
        front = [(center[0] + ax[0] * thickness / 2, center[1] + ax[1] * thickness / 2,
                  center[2] + ax[2] * thickness / 2)]
        back = [(center[0] - ax[0] * thickness / 2, center[1] - ax[1] * thickness / 2,
                 center[2] - ax[2] * thickness / 2)]
        outer_f, outer_b, inner_f, inner_b = [], [], [], []
        for i in range(sides):
            angle = 2.0 * math.pi * i / sides
            cu, sv = math.cos(angle), math.sin(angle)
            for radius, ring_front, ring_back in ((r_out, outer_f, outer_b),
                                                  (r_in, inner_f, inner_b)):
                px = u[0] * cu * radius + v[0] * sv * radius
                py = u[1] * cu * radius + v[1] * sv * radius
                pz = u[2] * cu * radius + v[2] * sv * radius
                ring_front.append((front[0][0] + px, front[0][1] + py, front[0][2] + pz))
                ring_back.append((back[0][0] + px, back[0][1] + py, back[0][2] + pz))
        for i in range(sides):
            j = (i + 1) % sides
            self.face([outer_f[i], outer_f[j], inner_f[j], inner_f[i]], color, emissive)
            self.face([inner_b[i], inner_b[j], outer_b[j], outer_b[i]], color, emissive)
            self.face([outer_b[i], outer_b[j], outer_f[j], outer_f[i]], color, emissive)
            self.face([inner_f[i], inner_f[j], inner_b[j], inner_b[i]], color, emissive)

    def panel(self, center, size, frame=GOLD, cell=SOLAR) -> None:
        self.box(center, size, frame, emissive=False)
        inset = (size[0] * 0.86, size[1] + 0.05, size[2] * 0.86)
        self.box(center, inset, cell, emissive=False)
        step = size[0] * 0.22
        for k in (-1, 1):
            self.box((center[0] + k * step, center[1], center[2]),
                     (size[0] * 0.03, size[1] + 0.08, size[2] * 0.92),
                     (26, 40, 66), emissive=False)


def _local_from_screen(dx: float, dy: float, z: float, scale: float,
                       yaw: float, pitch: float, roll: float,
                       flip_y: bool = False):
    """反投影：给定屏幕偏移（像素）与深度 z，求模型局部坐标，保证部件落在锚点上。"""
    ex = _rotate(1.0, 0.0, 0.0, yaw, pitch, roll, flip_y)
    ey = _rotate(0.0, 1.0, 0.0, yaw, pitch, roll, flip_y)
    ez = _rotate(0.0, 0.0, 1.0, yaw, pitch, roll, flip_y)
    tx = dx / scale
    ty = -dy / scale
    rx = tx - z * ez[0]
    ry = ty - z * ez[1]
    det = ex[0] * ey[1] - ex[1] * ey[0]
    if abs(det) < 1e-6:
        return (0.0, 0.0, z)
    x = (rx * ey[1] - ry * ey[0]) / det
    y = (ex[0] * ry - ex[1] * rx) / det
    if flip_y:
        y = -y
    return (x, y, z)


def draw_model(base: Image.Image, model: Model, anchor, scale: float,
               yaw: float, pitch: float, roll: float, flip_y: bool = False,
               light=(-0.35, -0.58, 0.73), outline: bool = True) -> Image.Image:
    draw = ImageDraw.Draw(base)
    items = []
    lx, ly, lz = light
    ll = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / ll, ly / ll, lz / ll
    for points, color, emissive in model.faces:
        rotated = [_rotate(p[0], p[1], p[2], yaw, pitch, roll, flip_y) for p in points]
        depth = sum(p[2] for p in rotated) / len(rotated)
        ax = rotated[1][0] - rotated[0][0]
        ay = rotated[1][1] - rotated[0][1]
        az = rotated[1][2] - rotated[0][2]
        bx = rotated[2][0] - rotated[0][0]
        by = rotated[2][1] - rotated[0][1]
        bz = rotated[2][2] - rotated[0][2]
        nx = ay * bz - az * by
        ny = az * bx - ax * bz
        nz = ax * by - ay * bx
        nl = math.sqrt(nx * nx + ny * ny + nz * nz)
        if nl < 1e-6:
            continue
        nx, ny, nz = nx / nl, ny / nl, nz / nl
        if nz < 0.0:
            nx, ny, nz = -nx, -ny, -nz
        diffuse = max(0.0, nx * lx + ny * ly + nz * lz)
        shade = 1.22 if emissive else 0.42 + 0.72 * diffuse
        screen = [(anchor[0] + p[0] * scale, anchor[1] - p[1] * scale) for p in rotated]
        items.append((depth, screen, color, shade, emissive))
    items.sort(key=lambda item: item[0])
    for _depth, screen, color, shade, emissive in items:
        fill = (_rgb((color[0] * shade, color[1] * shade, color[2] * shade)))
        draw.polygon(screen, fill=fill)
        if outline and not emissive:
            edge = _rgb((color[0] * 0.42, color[1] * 0.42, color[2] * 0.44))
            draw.line(screen + [screen[0]], fill=edge, width=2)
    return base


# ================================================================ 通用光效
def _beam(light: LightLayer, p0, p1, width: float, color, core=WHITE_HOT) -> None:
    light.line(p0, p1, width * 3.4, color, 0.55, blur=width * 2.4)
    light.line(p0, p1, width * 1.5, color, 1.1, blur=width * 0.9)
    light.line(p0, p1, max(2.0, width * 0.45), core, 1.35, blur=1.2)


def _impact(light: LightLayer, cx: float, cy: float, radius: float, color,
            core=WHITE_HOT, sparks: int = 9) -> None:
    light.radial(cx, cy, radius * 1.25, color, 0.85, power=2.2, blur=radius * 0.2)
    light.radial(cx, cy, radius * 0.42, core, 1.25, power=1.8)
    light.ring(cx, cy, radius * 0.72, max(1.5, radius * 0.05), color, 0.75,
               blur=radius * 0.04)
    for k in range(sparks):
        angle = 2.0 * math.pi * k / sparks + 0.4
        length = radius * (0.55 + 0.35 * _hash01(k, 3, 0x5A))
        light.line((cx, cy), (cx + math.cos(angle) * length, cy + math.sin(angle) * length),
                   max(1.0, radius * 0.022), color, 0.55, blur=radius * 0.02)


def _engine_glows(light: LightLayer, positions, color, scale_factor: float = 1.0) -> None:
    for x, y in positions:
        light.radial(x, y, 30.0 * scale_factor, color, 0.55, power=2.4, blur=6.0)
        light.radial(x, y, 12.0 * scale_factor, WHITE_HOT, 0.9, power=1.8)


def _charge_glow(light: LightLayer, center, color, radius: float = 46.0) -> None:
    light.radial(center[0], center[1], radius, color, 0.8, power=2.2, blur=radius * 0.2)
    light.radial(center[0], center[1], radius * 0.35, WHITE_HOT, 1.0, power=1.8)


# ================================================================ 载体模型
def _engine_nozzle(model: Model, pos, emit_color, up=HULL_DARK, length: float = 1.8,
                   radius: float = 0.62) -> None:
    x, y, z = pos
    model.cyl((x - 0.3, y, z), (x + length, y, z), radius, 8, up)
    model.cyl((x - 0.55, y, z), (x - 0.3, y, z), radius * 0.82, 8, HULL_MID)
    model.cyl((x - 0.62, y, z), (x - 0.5, y, z), radius * 0.60, 8, emit_color,
              emissive=True)


def _gun_barrel(model: Model, length: float, radius: float, emit_color) -> None:
    """沿 -x 的炮管：muzzle 在模型原点，向 +x 是舰体。"""
    model.cyl((0.0, 0.0, 0.0), (length, 0.0, 0.0), radius, 10, HULL_DARK)
    model.cyl((0.0, 0.0, 0.0), (-0.7, 0.0, 0.0), radius * 1.25, 10, HULL)
    for k in range(1, 4):
        cx = length * k / 4.0
        model.cyl((cx - 0.18, 0.0, 0.0), (cx + 0.18, 0.0, 0.0),
                  radius * 1.18, 10, HULL_MID)
    model.cyl((-0.72, 0.0, 0.0), (-0.80, 0.0, 0.0), radius * 0.72, 10, emit_color,
              emissive=True)


def build_cannon_model(anchors, scale, yaw, pitch, roll, flip_y):
    model = Model()
    emit = EMIT_ORANGE
    _gun_barrel(model, 3.4, 0.62, emit)
    # 前段机械舱
    model.box((4.6, 0.15, 0.0), (3.2, 2.6, 3.2), HULL_DARK)
    model.box((4.6, 1.65, 0.0), (2.2, 0.7, 2.0), HULL_MID)
    # 主体
    model.box((8.4, 0.55, 0.0), (5.2, 2.8, 3.6), HULL)
    model.box((8.4, 2.15, 0.0), (4.2, 0.6, 2.6), HULL_LIGHT)
    model.box((9.6, 0.55, 0.0), (2.6, 2.0, 3.8), HULL_DARK)
    # 侧翼 + 太阳能板
    for side in (-1, 1):
        model.box((7.6, 0.1, side * 2.4), (4.4, 0.7, 1.0), HULL_DARK)
        model.panel((6.4, 1.1, side * 3.3), (4.4, 0.16, 1.9))
        model.beam((8.8, 0.4, side * 2.4), (11.4, 0.9, side * 2.0), 0.28, HULL_MID)
    # 尾部上层建筑 + 天线
    model.box((11.6, 1.7, 0.0), (2.8, 2.2, 2.8), HULL_MID)
    model.box((11.6, 3.0, 0.0), (1.6, 0.6, 1.6), HULL_LIGHT)
    model.beam((11.8, 3.2, 0.4), (13.2, 5.4, 0.9), 0.10, HULL_WHITE)
    model.beam((11.2, 3.2, -0.3), (12.0, 4.6, -0.6), 0.08, HULL_LIGHT)
    # 顶部炮塔/散热片
    model.box((7.0, 2.5, -1.1), (1.8, 0.6, 1.1), HULL_DARK)
    model.box((9.4, 2.0, 1.3), (1.4, 0.5, 1.0), HULL)
    for k in range(3):
        model.box((5.6 + k * 1.4, 2.55, 0.9), (0.24, 0.9, 1.2), HULL_MID)
    # 发光线：舱段接缝 / 侧舷窗
    model.box((8.4, 1.55, 1.82), (2.4, 0.18, 0.06), emit, emissive=True)
    model.box((8.4, 1.55, -1.82), (2.4, 0.18, 0.06), emit, emissive=True)
    model.box((4.6, 0.15, 1.62), (1.2, 0.16, 0.05), emit, emissive=True)
    # 引擎：按 Java 锚点摆放
    glows = []
    for index, (u, v) in enumerate(anchors):
        dx = (u - 0.455) * W
        dy = (v - 0.515) * H
        z = -1.4 + 0.9 * index
        pos = _local_from_screen(dx, dy, z, scale, yaw, pitch, roll, flip_y)
        _engine_nozzle(model, pos, emit)
        # 尾部吊舱用一段短桁架接回舰体（宽度加粗，远看不会消失）
        model.beam((pos[0], pos[1], pos[2]),
                   (12.6, pos[1] * 0.55, pos[2] * 0.55), 0.32, HULL_MID)
        glows.append((0.455 * W + dx, 0.515 * H + dy))
    return model, glows


def build_lance_model(anchors, scale, yaw, pitch, roll, flip_y):
    model = Model()
    emit = EMIT_BLUE
    # 加长发射轨（沿 -x 方向伸出炮口）：双导轨 + 横撑 + 尾端设备段
    model.box((8.6, 0.0, 0.0), (16.8, 1.4, 2.0), HULL)
    model.box((8.6, 0.90, 0.0), (16.8, 0.4, 0.6), HULL_LIGHT)
    model.box((1.6, 0.0, 0.0), (3.0, 2.1, 3.2), HULL_DARK)
    model.box((16.2, 0.0, 0.0), (1.6, 1.9, 2.5), HULL_DARK)
    for side in (-1, 1):
        model.box((8.6, 0.52, side * 0.95), (16.2, 0.13, 0.10), emit, emissive=True)
        for k in range(5):
            bx = 2.6 + k * 3.0
            model.beam((bx, -1.05, side * 1.0), (bx + 1.8, 1.05, side * 1.0),
                       0.11, HULL_MID)
        model.beam((15.4, -1.0, side * 1.0), (16.4, 1.0, side * 1.0), 0.16, HULL_LIGHT)
    # 前段磁轨加速环
    for k in range(3):
        model.ring((1.0 + k * 1.3, 0.0, 0.0), (1, 0, 0), 1.55, 1.18, 0.55, 12,
                   HULL_MID)
        model.ring((1.0 + k * 1.3, 0.0, 0.0), (1, 0, 0), 1.42, 1.30, 0.20, 12,
                   emit, emissive=True)
    # 主体 + 尾部设备段
    model.box((7.0, 0.7, 0.0), (5.8, 2.6, 3.4), HULL)
    model.box((11.2, 1.0, 0.0), (3.2, 2.8, 3.2), HULL_DARK)
    model.box((7.0, 2.1, 0.0), (4.6, 0.5, 2.4), HULL_LIGHT)
    # 上方太阳能板与桁架
    for side in (-1, 1):
        model.beam((6.6, 1.1, side * 1.6), (6.6, 2.7, side * 2.6), 0.24, HULL_MID)
        model.panel((7.0, 2.9, side * 3.1), (4.8, 0.16, 2.0))
        model.box((9.4, 1.2, side * 2.2), (2.6, 0.2, 0.7), HULL_LIGHT)
    # 天线 / 传感器
    model.beam((11.4, 2.1, 0.4), (12.6, 4.4, 1.1), 0.10, HULL_WHITE)
    model.beam((10.8, 2.1, -0.6), (11.6, 3.8, -1.2), 0.08, HULL_LIGHT)
    model.box((11.8, 2.4, -0.9), (0.7, 0.7, 0.7), HULL_MID)
    # 白色/蓝色点缀
    model.box((7.0, 1.7, 1.72), (2.6, 0.16, 0.06), emit, emissive=True)
    model.box((7.0, 1.7, -1.72), (2.6, 0.16, 0.06), emit, emissive=True)
    model.box((4.4, 0.75, 0.0), (0.5, 0.18, 2.0), emit, emissive=True)
    # 引擎（锚点）
    glows = []
    for index, (u, v) in enumerate(anchors):
        dx = (u - 0.600) * W
        dy = (v - 0.530) * H
        z = -1.2 + 0.8 * index
        pos = _local_from_screen(dx, dy, z, scale, yaw, pitch, roll, flip_y)
        _engine_nozzle(model, pos, emit, length=1.5)
        # 外挂吊舱用一段桁架接回发射轨尾端（宽度加粗）
        model.beam((pos[0], pos[1], pos[2]),
                   (16.0, 0.0, pos[2] * 0.4), 0.30, HULL_MID)
        glows.append((0.600 * W + dx, 0.530 * H + dy))
    return model, glows


def build_singularity_model(anchors, scale, yaw, pitch, roll, flip_y):
    model = Model()
    emit = EMIT_VIOLET
    # 加速管：从环站（-x）伸向炮口（0）
    for k in range(4):
        model.cyl((-11.2 + k * 2.8, 0.0, 0.0), (-11.2 + (k + 1) * 2.8, 0.0, 0.0),
                  1.05, 10, HULL if k % 2 else HULL_DARK)
    for x in (-8.4, -5.6, -2.8):
        model.ring((x, 0.0, 0.0), (1, 0, 0), 1.9, 1.25, 0.7, 14, HULL_MID)
        model.ring((x, 0.0, 0.0), (1, 0, 0), 1.72, 1.52, 0.22, 14, emit, emissive=True)
    # 炮口
    model.cyl((-0.5, 0.0, 0.0), (0.6, 0.0, 0.0), 1.45, 12, HULL_DARK)
    model.cyl((0.5, 0.0, 0.0), (0.75, 0.0, 0.0), 1.05, 12, emit, emissive=True)
    # 环站：3D 椭圆环。环面斜对镜头（轴 ≈ (0.55,0,0.84)），用一圈有厚度的方块拼出
    # 内外径 + 轴向厚度 + 明暗交错；外缘一圈发光环带，环心用 6 根辐条接到暗核心。
    station_x = -13.4
    station_axis = _frame_from_axis((0.55, 0.0, 0.835))[0]
    # 环整体投影后上下各留 ~5% 边距（之前 6.5 会让底部外挂件贴到画框下沿）。
    ring_radius = 6.0
    _torus_ring(model, (station_x, 0.0, 0.0), station_axis, ring_radius, 24,
                1.55, 1.70, HULL, HULL_MID, emit_color=emit,
                emit_radius_offset=1.82, emit_half=0.18)
    _torus_ring(model, (station_x, 0.0, 0.0), station_axis, ring_radius - 2.6, 24,
                1.15, 0.85, HULL_DARK, HULL_DARK)
    ax = station_axis
    su = (-ax[2], 0.0, ax[0])
    sv = (0.0, -1.0, 0.0)
    for k in range(6):
        angle = 2.0 * math.pi * k / 6 + 0.15
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        direction = (su[0] * cos_a + sv[0] * sin_a,
                     su[1] * cos_a + sv[1] * sin_a,
                     su[2] * cos_a + sv[2] * sin_a)
        p_ring = (station_x + direction[0] * (ring_radius - 2.2),
                  direction[1] * (ring_radius - 2.2),
                  direction[2] * (ring_radius - 2.2))
        model.beam(p_ring, (station_x + ax[0] * 1.1, ax[1] * 1.1, ax[2] * 1.1),
                   0.30, HULL_MID)
    # 中央核心：沿环轴方向的短圆柱（暗核心，Java 会额外叠充能光）
    model.cyl((station_x - ax[0] * 1.5, -ax[1] * 1.5, -ax[2] * 1.5),
              (station_x + ax[0] * 1.5, ax[1] * 1.5, ax[2] * 1.5),
              2.6, 18, (20, 20, 30))
    model.cyl((station_x + ax[0] * 0.5, ax[1] * 0.5, ax[2] * 0.5),
              (station_x + ax[0] * 1.0, ax[1] * 1.0, ax[2] * 1.0),
              1.7, 18, (40, 44, 70))
    model.cyl((station_x + ax[0] * 1.0, ax[1] * 1.0, ax[2] * 1.0),
              (station_x + ax[0] * 1.2, ax[1] * 1.2, ax[2] * 1.2),
              0.9, 18, emit, emissive=True)
    # 环外挂块 / 太阳能板：挂架接到环体，不飘
    for k in range(6):
        angle = 2.0 * math.pi * k / 6 + 0.45
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        direction = (su[0] * cos_a + sv[0] * sin_a,
                     su[1] * cos_a + sv[1] * sin_a,
                     su[2] * cos_a + sv[2] * sin_a)
        ox = station_x + direction[0] * (ring_radius + 1.1)
        oy = direction[1] * (ring_radius + 1.1)
        oz = direction[2] * (ring_radius + 1.1)
        model.box((ox, oy, oz), (1.5, 1.1, 1.1), HULL)
        model.beam((ox, oy, oz),
                   (station_x + direction[0] * (ring_radius - 0.6),
                    direction[1] * (ring_radius - 0.6),
                    direction[2] * (ring_radius - 0.6)), 0.20, HULL_MID)
        if k % 2 == 0:
            model.panel((ox + ax[0] * 1.0, oy + ax[1] * 1.0, oz + ax[2] * 1.0),
                        (0.9, 1.8, 1.8))
    # 加速管与环之间的桁架
    for k in range(4):
        angle = 2.0 * math.pi * k / 4 + 0.2
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        direction = (su[0] * cos_a + sv[0] * sin_a,
                     su[1] * cos_a + sv[1] * sin_a,
                     su[2] * cos_a + sv[2] * sin_a)
        model.beam((station_x + direction[0] * (ring_radius - 2.8),
                    direction[1] * (ring_radius - 2.8),
                    direction[2] * (ring_radius - 2.8)),
                   (-8.0, direction[1] * 0.8, direction[2] * 0.8), 0.22, HULL_MID)
    # 引擎（锚点）
    glows = []
    for index, (u, v) in enumerate(anchors):
        dx = (u - 0.835) * W
        dy = (v - 0.490) * H
        z = -2.0 + 1.2 * index
        pos = _local_from_screen(dx, dy, z, scale, yaw, pitch, roll, flip_y)
        _engine_nozzle(model, pos, emit, length=1.5)
        # 吊舱用挂架接到环体（投影到环面方向，保证不会看着像断开）
        rel = (pos[0] - station_x, pos[1], pos[2])
        axial = rel[0] * ax[0] + rel[1] * ax[1] + rel[2] * ax[2]
        radial = (rel[0] - ax[0] * axial, rel[1] - ax[1] * axial, rel[2] - ax[2] * axial)
        radial_len = math.hypot(radial[0], radial[1], radial[2]) or 1.0
        target = (station_x + radial[0] / radial_len * (ring_radius - 1.4)
                  + ax[0] * axial * 0.8,
                  radial[1] / radial_len * (ring_radius - 1.4) + ax[1] * axial * 0.8,
                  radial[2] / radial_len * (ring_radius - 1.4) + ax[2] * axial * 0.8)
        model.beam((pos[0], pos[1], pos[2]), target, 0.32, HULL_MID)
        glows.append((0.835 * W + dx, 0.490 * H + dy))
    return model, glows


def build_plasma_model(anchors, scale, yaw, pitch, roll, flip_y):
    model = Model()
    emit = EMIT_CYAN
    # 等离子炮口
    model.cyl((0.4, 0.0, 0.0), (1.9, 0.0, 0.0), 0.95, 12, HULL_DARK)
    model.cyl((-0.15, 0.0, 0.0), (0.4, 0.0, 0.0), 1.15, 12, HULL)
    model.ring((0.2, 0.0, 0.0), (1, 0, 0), 1.3, 1.05, 0.55, 12, HULL_MID)
    model.ring((0.2, 0.0, 0.0), (1, 0, 0), 1.18, 1.08, 0.18, 12, emit, emissive=True)
    # 主舰体
    model.box((4.8, 0.2, 0.0), (5.2, 2.6, 3.4), HULL)
    model.box((7.4, 0.4, 0.0), (4.2, 2.9, 3.2), HULL_DARK)
    model.box((4.8, 1.9, 0.0), (3.8, 0.6, 2.4), HULL_LIGHT)
    # 两侧武器舱
    for side in (-1, 1):
        model.box((5.4, 0.0, side * 2.5), (4.2, 1.4, 1.3), HULL_DARK)
        model.box((5.4, 0.75, side * 2.5), (3.0, 0.25, 0.9), HULL_MID)
        model.box((5.4, 0.0, side * 2.62), (2.2, 0.14, 0.06), emit, emissive=True)
    # 顶部散热鳍
    for side in (-1, 1):
        model.box((8.0, 2.4, side * 2.0), (4.4, 0.9, 0.24), HULL_LIGHT)
        model.box((8.0, 1.9, side * 2.0), (3.6, 0.6, 0.18), HULL_MID)
    # 小炮塔 / 传感器（贴着舰体顶部，别做成飘散件）
    model.box((3.2, 1.7, -1.4), (1.2, 0.8, 1.1), HULL_DARK)
    model.box((3.2, 2.15, -1.4), (0.7, 0.3, 0.7), HULL_MID)
    model.beam((8.4, 2.9, 1.2), (9.2, 4.0, 1.5), 0.10, HULL_WHITE)
    model.beam((6.6, 2.9, -1.2), (7.0, 3.7, -1.5), 0.08, HULL_LIGHT)
    model.box((7.8, 0.2, 1.85), (1.8, 0.18, 0.06), emit, emissive=True)
    model.box((7.8, 0.2, -1.85), (1.8, 0.18, 0.06), emit, emissive=True)
    # 引擎（锚点）
    glows = []
    for index, (u, v) in enumerate(anchors):
        dx = (u - 0.478) * W
        dy = (v - 0.352) * H
        z = -1.4 + 0.9 * index
        pos = _local_from_screen(dx, dy, z, scale, yaw, pitch, roll, flip_y)
        _engine_nozzle(model, pos, emit, length=1.4)
        # 外挂吊舱用一段桁架接回舰体尾部（宽度加粗）
        model.beam((pos[0], pos[1], pos[2]),
                   (8.6, 0.6, pos[2] * 0.3), 0.30, HULL_MID)
        glows.append((0.478 * W + dx, 0.352 * H + dy))
    return model, glows


# ================================================================ 小行星
def _rock_outline(seed: int, vertices: int = 17) -> tuple:
    """不规则多边形轮廓（归一化半径）：低频起伏 + 两个大缺口 + 一个凸起。

    plate 与 cutout 都调用同一个函数（同 seed / 同顶点数），所以两者的剪影是同一个形状。
    """
    radii = []
    for i in range(vertices):
        base = 0.90 + 0.12 * _hash01(i // 2, 0, seed) + 0.04 * _hash01(i, 1, seed)
        radii.append(base)
    notch_a = int(_hash01(0, 2, seed) * vertices) % vertices
    notch_b = (notch_a + 5 + int(_hash01(1, 2, seed) * 4)) % vertices
    bump = (notch_b + 4) % vertices
    for index, scale in ((notch_a, 0.70), ((notch_a + 1) % vertices, 0.82),
                         (notch_b, 0.74), ((notch_b - 1) % vertices, 0.84),
                         (bump, 1.16), ((bump + 1) % vertices, 1.08)):
        radii[index] *= scale
    return tuple(radii)


def _outline_radius(theta: float, radii: tuple) -> float:
    """沿 theta 方向的轮廓半径（多边形边的精确交点，所以边缘是直的棱）。"""
    count = len(radii)
    segment = 2.0 * math.pi / count
    theta = theta % (2.0 * math.pi)
    index = int(theta // segment) % count
    start = index * segment
    frac = theta - start
    r1 = radii[index]
    r2 = radii[(index + 1) % count]
    denominator = r2 * math.sin(frac) + r1 * math.sin(segment - frac)
    if denominator < 1e-6:
        return r1
    return r1 * r2 * math.sin(segment) / denominator


def _point_polyline_distance(px: float, py: float, points) -> float:
    best = 1e9
    for i in range(len(points) - 1):
        ax, ay = points[i]
        bx, by = points[i + 1]
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        if length2 < 1e-9:
            t = 0.0
        else:
            t = _clamp(((px - ax) * dx + (py - ay) * dy) / length2, 0.0, 1.0)
        qx, qy = ax + dx * t, ay + dy * t
        best = min(best, math.hypot(px - qx, py - qy))
    return best


def _rock_art(sw: int, sh: int, cx: float, cy: float, radius: float, seed: int,
              transparent: bool = True) -> Image.Image:
    """低分辨率块面小行星：不规则多边形剪影 + 硬分界受光/暗面 + 裂缝 + 棱角 + 陨石坑。"""
    frequency = max(4, int(round(sw / 30.0)))
    h1 = _fbm_list(sw, sh, frequency, frequency, 4, 0.55, seed)
    h2 = _fbm_list(sw, sh, frequency * 2, frequency * 2, 4, 0.50, seed + 23)
    radii = _rock_outline(seed)
    # 裂缝：5 条折线（归一化坐标，plate / cutout 一致）
    cracks = []
    for k in range(5):
        angle = 2.0 * math.pi * _hash01(k, 3, seed + 31)
        distance = 0.18 + 0.45 * _hash01(k, 4, seed + 33)
        points = [(math.cos(angle) * distance, math.sin(angle) * distance)]
        for step in range(3):
            angle += (_hash01(k, step, seed + 35) - 0.5) * 1.15
            distance = min(0.92, distance + 0.14 + 0.14 * _hash01(k, step, seed + 37))
            points.append((math.cos(angle) * distance, math.sin(angle) * distance))
        cracks.append(points)
    # 陨石坑：归一化坐标，两个分辨率之间位置一致
    craters = []
    for k in range(8):
        angle = 2.0 * math.pi * _hash01(k, 5, seed + 51)
        distance = 0.66 * math.sqrt(_hash01(k, 6, seed + 53))
        craters.append((math.cos(angle) * distance, math.sin(angle) * distance,
                        0.06 + 0.10 * _hash01(k, 7, seed + 55)))
    light = (-0.46, -0.52, 0.72)
    ll = math.sqrt(sum(c * c for c in light))
    light = (light[0] / ll, light[1] / ll, light[2] / ll)
    layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    pixels = layer.load()
    for y in range(sh):
        for x in range(sw):
            u = (x + 0.5 - cx) / radius
            v = (y + 0.5 - cy) / radius
            distance = math.sqrt(u * u + v * v)
            theta = 0.0 if distance < 1e-6 else (math.atan2(v, u) + 2.0 * math.pi) % (
                2.0 * math.pi)
            boundary = _outline_radius(theta, radii)
            coverage = _clamp((boundary - distance) * radius * 0.6 + 0.5, 0.0, 1.0)
            if coverage <= 0.0:
                continue
            index = y * sw + x
            # 高度梯度 -> 碎块面法线（不是球面法线，避免像行星地表图）
            gx = (h1[y * sw + min(sw - 1, x + 1)] - h1[y * sw + max(0, x - 1)]) * 2.6
            gy = (h1[min(sh - 1, y + 1) * sw + x] - h1[max(0, y - 1) * sw + x]) * 2.6
            nx = 0.32 * u + gx * 2.6
            ny = 0.32 * v + gy * 2.6
            nz = 1.0
            nl = math.sqrt(nx * nx + ny * ny + nz * nz)
            nx, ny, nz = nx / nl, ny / nl, nz / nl
            lambert = max(0.0, nx * light[0] + ny * light[1] + nz * light[2])

            # 碎块面：按角度/半径量化成小块，每块亮度有固定偏移
            facet_angle = int(theta / (2.0 * math.pi / 14.0)) % 14
            facet_ring = int(min(3.0, distance * 4.0))
            shade = 0.12 + 0.95 * lambert
            shade *= 0.88 + 0.24 * _hash01(facet_angle, facet_ring, seed + 41)
            # 硬分界：明暗量化成 5 档，边界是硬台阶
            shade = round(shade * 5.0) / 5.0

            # 陨石坑：坑内压暗 + 边缘亮环
            for crater_u, crater_v, crater_r in craters:
                cdu = (u - crater_u) / crater_r
                cdv = (v - crater_v) / crater_r
                cd = math.sqrt(cdu * cdu + cdv * cdv)
                if cd < 1.0:
                    shade *= 0.62 + 0.38 * cd
                    if 0.72 < cd < 1.0:
                        shade *= 1.18

            # 裂缝：靠近折线就压暗成硬黑缝
            for crack in cracks:
                if _point_polyline_distance(u, v, crack) < 0.042:
                    shade *= 0.30
                    break

            # 边缘棱角：迎光侧亮棱、背光侧暗棱
            if distance > boundary - 0.09:
                shade *= 1.20 if lambert > 0.55 else 0.58

            color = _mix((26, 23, 20), (124, 114, 98), _clamp(shade))
            color = _mix(color, (198, 184, 160), max(0.0, shade - 0.66) * 1.3)
            color = _posterize(color, 16)
            pixels[x, y] = (color[0], color[1], color[2], int(coverage * 255))
    return layer


def _asteroid_plate(seed: int) -> Image.Image:
    base = _space_background(seed, earth=(0.50 * W, 2.30 * H, 1.55 * H),
                             nebula_strength=0.55, warm=(0.30, 0.62),
                             sun=(0.24 * W, 0.14 * H, 90, (200, 220, 255)))
    sw, sh = W // 4, H // 4
    # 与 cutout 同 seed/同轮廓（_rock_outline 只依赖 seed）
    rock = _rock_art(sw, sh, (0.49 * W) / 4, (0.47 * H) / 4, (0.195 * W) / 4, seed)
    rock_big = rock.resize((W, H), Image.Resampling.NEAREST)
    base.paste(rock_big, (0, 0), rock_big.getchannel("A"))
    light = LightLayer(W, H)
    # 岩体边缘轮廓光 + 小碎屑 + 顶部辉光
    light.radial(0.49 * W, 0.47 * H, 0.24 * W, (120, 150, 220), 0.10, power=2.4)
    for k in range(9):
        angle = 2.0 * math.pi * k / 9 + 0.3
        dist = 0.30 * W * (0.8 + 0.4 * _hash01(k, 1, seed + 9))
        px = 0.49 * W + math.cos(angle) * dist
        py = 0.47 * H + math.sin(angle) * dist * 0.7
        size = 3.0 + 6.0 * _hash01(k, 2, seed + 11)
        light.radial(px, py, size, (150, 140, 120), 0.25, power=2.0)
    base = light.apply(base)
    return _vignette(base, 0.38)


def _asteroid_cutout(seed: int) -> Image.Image:
    sw, sh = CUT // 4, CUT // 4
    # 同 seed => 与 carrier_asteroid.png 完全一致的轮廓；半径留 3px(低分辨率) 边距
    rock = _rock_art(sw, sh, CUT / 8.0, CUT / 8.0, 58.0, seed, True)
    return rock.resize((CUT, CUT), Image.Resampling.NEAREST)


# ================================================================ 五张电影板
def build_cannon() -> Image.Image:
    base = _space_background(1201, earth=(0.10 * W, 1.85 * H, 1.55 * H),
                             nebula_strength=0.65, warm=(0.30, 0.20),
                             sun=(0.13 * W, 0.24 * H, 70, (180, 210, 255)))
    muzzle = (0.455 * W, 0.515 * H)
    impact = (0.205 * W, 0.795 * H)
    light = LightLayer(W, H)
    _beam(light, muzzle, impact, 16.0, EMIT_ORANGE)
    _impact(light, impact[0], impact[1], 86.0, EMIT_ORANGE, sparks=12)
    base = light.apply(base)

    model, engines = build_cannon_model(
        ((0.84, 0.28), (0.91, 0.34), (0.83, 0.45), (0.78, 0.20)),
        46.0, yaw=0.30, pitch=0.20, roll=0.34, flip_y=False)
    base = draw_model(base, model, muzzle, 46.0, 0.30, 0.20, 0.34, False)

    glow = LightLayer(W, H)
    _engine_glows(glow, engines, EMIT_AMBER, 1.1)
    _charge_glow(glow, muzzle, EMIT_ORANGE, 52.0)
    base = glow.apply(base)
    return _vignette(base, 0.40)


def build_lance() -> Image.Image:
    base = _space_background(2202, earth=(0.58 * W, 1.55 * H, 1.35 * H),
                             nebula_strength=0.55, warm=(0.82, 0.18),
                             sun=(0.06 * W, 0.10 * H, 90, (210, 225, 255)))
    muzzle = (0.600 * W, 0.530 * H)
    exit_point = (0.970 * W, 0.760 * H)
    light = LightLayer(W, H)
    _beam(light, muzzle, exit_point, 13.0, EMIT_BLUE)
    # 命中在画外：只在束流离开画面的方向点留一点余辉，不画爆炸（Java 的 impactVisible=false）
    light.radial(exit_point[0], exit_point[1], 52.0, EMIT_BLUE, 0.45, power=2.6,
                 blur=16.0)
    light.radial(exit_point[0], exit_point[1], 18.0, WHITE_HOT, 0.35, power=2.0)
    base = light.apply(base)

    model, engines = build_lance_model(
        ((0.12, 0.30), (0.46, 0.58), (0.43, 0.66), (0.55, 0.62)),
        42.0, yaw=0.26, pitch=0.22, roll=math.pi - 0.30, flip_y=True)
    base = draw_model(base, model, muzzle, 42.0, 0.26, 0.22,
                      math.pi - 0.30, True)

    glow = LightLayer(W, H)
    _engine_glows(glow, engines, EMIT_BLUE, 1.0)
    _charge_glow(glow, muzzle, EMIT_BLUE, 56.0)
    base = glow.apply(base)
    return _vignette(base, 0.40)


def build_singularity() -> Image.Image:
    base = _space_background(3303, earth=(0.86 * W, 2.05 * H, 1.30 * H),
                             nebula_strength=0.95, warm=(0.66, 0.72),
                             sun=(0.90 * W, 0.20 * H, 60, (200, 205, 255)))
    muzzle = (0.835 * W, 0.490 * H)
    light = LightLayer(W, H)
    _beam(light, muzzle, (1.10 * W, 0.500 * H), 15.0, EMIT_VIOLET)
    base = light.apply(base)

    model, engines = build_singularity_model(
        ((0.15, 0.22), (0.14, 0.70), (0.62, 0.83), (0.28, 0.10)),
        42.0, yaw=0.22, pitch=0.16, roll=0.03, flip_y=False)
    base = draw_model(base, model, muzzle, 42.0, 0.22, 0.16, 0.03, False)

    glow = LightLayer(W, H)
    _engine_glows(glow, engines, EMIT_VIOLET, 1.0)
    _charge_glow(glow, muzzle, EMIT_VIOLET, 58.0)
    # 环站核心的冷光 + 加速环泛光
    glow.radial(0.44 * W, 0.47 * H, 150.0, (90, 120, 255), 0.30, power=2.2, blur=24.0)
    glow.radial(0.44 * W, 0.47 * H, 60.0, (180, 200, 255), 0.45, power=2.0)
    base = glow.apply(base)
    return _vignette(base, 0.42)


def build_plasma() -> Image.Image:
    base = _space_background(4404, earth=(0.62 * W, 1.42 * H, 1.20 * H),
                             nebula_strength=0.60, warm=(0.20, 0.70),
                             sun=(0.92 * W, 0.12 * H, 80, (190, 220, 255)))
    muzzle = (0.478 * W, 0.352 * H)
    main_impact = (0.820 * W, 0.700 * H)
    light = LightLayer(W, H)
    _beam(light, muzzle, main_impact, 17.0, EMIT_CYAN)
    storm = ((0.820, 0.700), (0.725, 0.660), (0.885, 0.735), (0.765, 0.715),
             (0.925, 0.675), (0.690, 0.700), (0.845, 0.635))
    for index, (u, v) in enumerate(storm):
        _impact(light, u * W, v * H, 34.0 + 14.0 * (1 if index == 0 else 0),
                EMIT_CYAN, sparks=6)
    # 落点之间的电弧
    for index in range(len(storm) - 1):
        p0 = (storm[index][0] * W, storm[index][1] * H)
        p1 = (storm[index + 1][0] * W, storm[index + 1][1] * H)
        light.line(p0, p1, 2.0, (150, 235, 255), 0.55, blur=2.0)
    base = light.apply(base)

    model, engines = build_plasma_model(
        ((0.12, 0.22), (0.49, 0.31), (0.15, 0.45)),
        45.0, yaw=0.28, pitch=0.20, roll=math.pi - 0.50, flip_y=True)
    base = draw_model(base, model, muzzle, 45.0, 0.28, 0.20,
                      math.pi - 0.50, True)

    glow = LightLayer(W, H)
    _engine_glows(glow, engines, EMIT_CYAN, 1.0)
    _charge_glow(glow, (0.300 * W, 0.300 * H), EMIT_CYAN, 64.0)
    _charge_glow(glow, muzzle, EMIT_CYAN, 40.0)
    base = glow.apply(base)
    return _vignette(base, 0.40)


def build_asteroid_plate_image() -> Image.Image:
    return _asteroid_plate(7707)


def build_asteroid_cutout_image() -> Image.Image:
    return _asteroid_cutout(7707)


# ================================================================ 输出
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
    parser = argparse.ArgumentParser(description="生成 P4-A2 天基载体原创电影板")
    parser.add_argument("--preview", metavar="DIR",
                        help="可选的 1x 预览输出目录（必须在仓库之外，不写进模组资源）")
    args = parser.parse_args()

    os.makedirs(ENV_DIR, exist_ok=True)
    builders = (
        ("cannon", build_cannon, (1408, 768), "RGB"),
        ("lance", build_lance, (1408, 768), "RGB"),
        ("singularity", build_singularity, (1408, 768), "RGB"),
        ("plasma", build_plasma, (1408, 768), "RGB"),
        ("asteroid", build_asteroid_plate_image, (1408, 768), "RGB"),
        ("asteroid_cutout", build_asteroid_cutout_image, (600, 600), "RGBA"),
    )
    written = []
    for name, builder, size, mode in builders:
        image = builder()
        path = OUTPUTS[name]
        image.save(path, "PNG")
        written.append((name, path, image))
        print("wrote %-16s %s  (%dx%d %s, %d bytes, sha256=%s)"
              % (name, os.path.relpath(path, ROOT), image.width, image.height,
                 image.mode, os.path.getsize(path), _sha256(path)[:16]))

    if args.preview:
        preview_dir = _guard_preview_dir(args.preview)
        os.makedirs(preview_dir, exist_ok=True)
        for name, _path, image in written:
            preview_path = os.path.join(preview_dir, name + ".png")
            image.save(preview_path, "PNG")
            print("preview", preview_path)

    failures = []
    for name, _path, image in written:
        expected = dict((n, (s, m)) for n, _b, s, m in builders)[name]
        if image.size != expected[0] or image.mode != expected[1]:
            failures.append("%s: got %s %s, expected %s %s"
                            % (name, image.size, image.mode, expected[0], expected[1]))
    if failures:
        print("FAIL")
        for line in failures:
            print("  -", line)
        return 1
    print("OK: 5 张 1408x768 RGB + 1 张 600x600 RGBA 尺寸/模式符合预期")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
