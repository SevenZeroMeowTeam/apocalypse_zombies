#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""天陨指挥终端（v4.0 P1）原创贴图生成器 —— 全部像素由本脚本绘制，不读取任何参考图。

产出 7 张 16x16 PNG：
    textures/block/skyfall_terminal.png        深色金属机柜 + 青色能量槽 + 橙色指示灯
    textures/item/skyfall_core_cinder.png      橙金：熔核 / 裂纹余烬
    textures/item/skyfall_core_fault.png       金色：贯穿裂痕
    textures/item/skyfall_core_quarantine.png  冷白蓝：封锁环
    textures/item/skyfall_core_swarm.png       孢子绿：孢子群
    textures/item/skyfall_core_dawn.png        白金光：日出射线
    textures/item/skyfall_core_black_rain.png  毒紫：黑雨

设计约定
--------
* 方块贴图是**手排像素稿**：16x16 逐像素上色，纯色块 + 有限的明暗过渡，
  和 MC 方块贴图一样靠 1px 结构读形；cube_all 六面共用，所以画面四边都要收口。
* 六张核心是**同一款能量模块**（同一副深色金属外壳、同一颗四角螺丝、同一个中央能量
  球窝），只换能量球颜色与内部纹样 —— 玩家一眼看出「这是同一族道具」，又能靠颜色
  与纹样区分是哪个协议。先在 16 倍超采样画布上画，再 BOX 缩小到 16x16，边缘自带
  抗锯齿（与项目里 orbital_strike_remote 等图标观感一致）。
* 六色的出处是 assets/apocalypse_zombies/strike/*.xml 里各协议的 color，
  和游戏内打击演出、GUI 协议色完全一致。
* 全脚本无随机熵：纹样用固定种子的 random.Random，重复跑输出逐字节一致。

用法：
    python tools/skyfall_art.py                      # 生成 7 张贴图
    python tools/skyfall_art.py --preview <dir>      # 额外写 16x 放大预览 + 总览图
"""

from __future__ import annotations

import argparse
import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "src", "main", "resources", "assets", "apocalypse_zombies")
TEXTURES = os.path.join(RES, "textures")
BLOCK_PNG = os.path.join(TEXTURES, "block", "skyfall_terminal.png")
ITEM_DIR = os.path.join(TEXTURES, "item")

SIZE = 16
SS = 16  # 核心图标的超采样倍率（16 倍画布 -> BOX 缩到 16x16）


# ---------------------------------------------------------------- 颜色小工具
def rgb(text: str) -> tuple[int, int, int]:
    """'#RRGGBB' -> (r, g, b)。"""
    text = text.lstrip("#")
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def mix(a, b, t: float):
    """线性混色，t=0 取 a，t=1 取 b。"""
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def shade(c, factor: float):
    """整体明暗缩放。"""
    return tuple(max(0, min(255, int(round(v * factor)))) for v in c)


WHITE = (255, 255, 255)


# ---------------------------------------------------------------- 方块贴图
# 深色金属机柜：外描边 / 边框 / 内板 / 竖向导轨 / 青能量槽 / 橙指示灯
PALETTE = {
    "OUTER": (8, 10, 14),
    "FRAME": (32, 40, 50),
    "FRAME_HI": (66, 80, 95),
    "FRAME_LO": (17, 21, 27),
    "PLATE": (28, 36, 45),
    "PLATE_HI": (44, 54, 66),
    "PLATE_LO": (18, 23, 29),
    "RAIL": (46, 58, 71),
    "RAIL_DK": (21, 27, 34),
    "VENT": (10, 13, 17),
    "CHAMBER": (12, 16, 21),
    "CYAN_DEEP": (12, 40, 48),
    "CYAN_LO": (18, 64, 76),
    "CYAN_MID": (32, 150, 166),
    "CYAN_HI": (88, 226, 240),
    "CYAN_CORE": (186, 250, 255),
    "ORANGE": (232, 138, 46),
    "ORANGE_HI": (255, 200, 108),
    "RIVET": (96, 112, 128),
}


def make_terminal_texture() -> Image.Image:
    """16x16 手排像素稿：对称的机柜正面。"""
    P = dict(PALETTE)
    # 顶部格栅在 16px 上对比过强会像「断齿」，用低对比的深浅两档
    P["VENT"] = (16, 20, 26)
    grid = [[(*P["OUTER"], 255) for _ in range(SIZE)] for _ in range(SIZE)]

    def put(x, y, c):
        grid[y][x] = (*c, 255)

    def rect(x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                put(x, y, c)

    # 1) 外描边 + 边框 + 左上受光的斜面
    rect(0, 0, 15, 15, P["OUTER"])
    rect(1, 1, 14, 14, P["FRAME"])
    for x in range(2, 14):
        put(x, 1, P["FRAME_HI"])
        put(x, 14, P["FRAME_LO"])
    for y in range(2, 14):
        put(1, y, P["FRAME_HI"])
        put(14, y, P["FRAME_LO"])

    # 2) 内板 + 板自身的内斜边
    rect(2, 2, 13, 13, P["PLATE"])
    for x in range(3, 13):
        put(x, 2, P["PLATE_HI"])
        put(x, 13, P["PLATE_LO"])
    for y in range(3, 13):
        put(2, y, P["PLATE_HI"])
        put(13, y, P["PLATE_LO"])

    # 3) 四角铆钉
    for x, y in ((2, 2), (13, 2), (2, 13), (13, 13)):
        put(x, y, P["RIVET"])

    # 4) 左右竖向导轨（x=3/12 亮，x=4/11 深缝）
    for y in range(3, 13):
        put(3, y, P["RAIL"])
        put(12, y, P["RAIL"])
        put(4, y, P["RAIL_DK"])
        put(11, y, P["RAIL_DK"])

    # 5) 顶部散热格栅：两行交错的竖槽，读起来像金属网
    for x in range(5, 11):
        if x % 2 == 1:
            put(x, 3, P["VENT"])
            put(x, 4, P["PLATE"])
        else:
            put(x, 3, P["PLATE"])
            put(x, 4, P["VENT"])

    # 6) 中央能量槽腔体（x=5..10, y=5..11）。槽口四列：暗边 / 亮芯 / 亮芯 / 暗边。
    rect(5, 5, 10, 11, P["CHAMBER"])
    slot_rows = {
        5: (P["CYAN_DEEP"], P["CYAN_MID"], P["CYAN_MID"], P["CYAN_DEEP"]),
        6: (P["CYAN_LO"], P["CYAN_HI"], P["CYAN_HI"], P["CYAN_LO"]),
        7: (P["CYAN_LO"], P["CYAN_HI"], P["CYAN_HI"], P["CYAN_LO"]),
        8: (P["CYAN_LO"], P["CYAN_CORE"], P["CYAN_CORE"], P["CYAN_LO"]),
        9: (P["CYAN_LO"], P["CYAN_HI"], P["CYAN_HI"], P["CYAN_LO"]),
        10: (P["CYAN_DEEP"], P["CYAN_MID"], P["CYAN_MID"], P["CYAN_DEEP"]),
    }
    for y, row in slot_rows.items():
        for i, color in enumerate(row):
            put(6 + i, y, color)
    # 腔体两侧被槽光照亮的窄边（y=6..9）
    for y in range(6, 10):
        put(5, y, P["CYAN_DEEP"])
        put(10, y, P["CYAN_DEEP"])
    # 槽底溢光
    for x in range(6, 10):
        put(x, 11, P["CYAN_DEEP"])

    # 7) 底部橙色指示灯：两侧常亮、中间高亮（少量，3 颗）
    put(4, 12, P["ORANGE"])
    put(7, 12, P["ORANGE_HI"])
    put(10, 12, P["ORANGE"])

    img = Image.new("RGBA", (SIZE, SIZE))
    img.putdata([grid[y][x] for y in range(SIZE) for x in range(SIZE)])
    return img


# ---------------------------------------------------------------- 核心图标
# 六协议主色 —— 取自 assets/apocalypse_zombies/strike/<id>.xml 的 color 属性
CORE_THEME = {
    "cinder": rgb("#FF7A2E"),       # 焚城：橙金 / 熔核
    "fault": rgb("#E0C070"),        # 断层：金色 / 贯穿裂痕
    "quarantine": rgb("#D8F4FF"),   # 隔离：冷白蓝 / 封锁环
    "swarm": rgb("#8DFF7A"),        # 蜂群：孢子绿 / 孢子群
    "dawn": rgb("#FFF2C4"),         # 黎明：白金光 / 日出
    "black_rain": rgb("#B08CFF"),   # 黑雨：毒紫 / 雨滴
}

# 能量球体色：在协议色上再压深一档色相。协议色本身偏白（隔离/黎明），
# 直接用会在 16px 下都糊成一团白光；球体压出蓝/金倾向后，六张一眼能分。
CORE_DISC = {
    "cinder": mix(CORE_THEME["cinder"], rgb("#FF5A14"), 0.35),
    "fault": mix(CORE_THEME["fault"], rgb("#C89632"), 0.40),
    "quarantine": mix(CORE_THEME["quarantine"], rgb("#5AB4FF"), 0.55),
    "swarm": mix(CORE_THEME["swarm"], rgb("#3CD246"), 0.45),
    "dawn": mix(CORE_THEME["dawn"], rgb("#FFBE50"), 0.45),
    "black_rain": mix(CORE_THEME["black_rain"], rgb("#8246E6"), 0.50),
}

# 外壳配色：偏蓝的深灰金属，和方块贴图同一族
CHASSIS_TOP = (54, 62, 74)
CHASSIS_BOTTOM = (18, 21, 26)
CHASSIS_EDGE = (90, 103, 118)
CHASSIS_INNER = (6, 8, 11)
SCREW_LIGHT = (104, 116, 130)
SCREW_DARK = (38, 44, 52)
SOCKET_BLACK = (4, 6, 9)

CENTRE = (8.0, 8.4)


def _c(v: float) -> float:
    """逻辑像素 -> 设备像素。"""
    return v * SS


def _line(d, pts, width_logical: float, fill):
    d.line([(_c(x), _c(y)) for x, y in pts],
           width=max(1, int(round(width_logical * SS))), fill=fill, joint="curve")


def _circ(d, cx, cy, r, **kw):
    d.ellipse([_c(cx - r), _c(cy - r), _c(cx + r), _c(cy + r)], **kw)


def _rrect(d, x0, y0, x1, y1, radius, **kw):
    d.rounded_rectangle([_c(x0), _c(y0), _c(x1), _c(y1)], radius=_c(radius), **kw)


def _rounded_mask(size, x0, y0, x1, y1, radius) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [_c(x0), _c(y0), _c(x1), _c(y1)], radius=_c(radius), fill=255)
    return mask


def _ellipse_mask(size, cx, cy, r) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    _circ(ImageDraw.Draw(mask), cx, cy, r, fill=255)
    return mask


def _gradient_lut(stops, steps: int = 256):
    """stops = [(pos0, color0), (pos1, color1), ...]，pos 递增到 1。"""
    lut = []
    for i in range(steps):
        t = i / (steps - 1)
        left, right = stops[0], stops[-1]
        for a, b in zip(stops, stops[1:]):
            if a[0] <= t <= b[0]:
                left, right = a, b
                break
        span = max(1e-6, right[0] - left[0])
        lut.append(mix(left[1], right[1], (t - left[0]) / span))
    return lut


def _chassis_layer(size: int) -> Image.Image:
    """外壳底色：竖向明暗 + 四角压暗（四角略暗）。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    for y in range(size):
        v = (y + 0.5) / size
        base = mix(CHASSIS_TOP, CHASSIS_BOTTOM, min(1.0, max(0.0, (v - 1 / 16) / (14 / 16))))
        for x in range(size):
            u = (x + 0.5) / size
            dist = math.hypot(u - 0.5, v - 0.5) / math.hypot(0.44, 0.44)
            vignette = 1.0 - 0.34 * min(1.0, dist) ** 2
            c = shade(base, vignette)
            # 左上受光：竖向 + 横向各给一点提亮，右下给一点压暗
            lift = 0.10 * max(0.0, (1.0 - u)) + 0.08 * max(0.0, (1.0 - v))
            dark = 0.10 * max(0.0, u - 0.5) + 0.08 * max(0.0, v - 0.5)
            c = shade(c, 1.0 + lift - dark)
            px[x, y] = (c[0], c[1], c[2], 255)
    return img


def _energy_disc(size: int, disc, radius: float) -> Image.Image:
    """中央能量球：中心白热 -> 球体色 -> 边缘压暗的径向渐变。"""
    stops = [
        (0.00, mix(disc, WHITE, 0.82)),
        (0.22, mix(disc, WHITE, 0.50)),
        (0.52, disc),
        (0.82, shade(disc, 0.55)),
        (1.00, shade(disc, 0.36)),
    ]
    lut = _gradient_lut(stops)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    cx, cy = _c(CENTRE[0]), _c(CENTRE[1])
    r_dev = _c(radius)
    r2 = r_dev * r_dev
    for y in range(size):
        for x in range(size):
            dx = x + 0.5 - cx
            dy = y + 0.5 - cy
            d2 = dx * dx + dy * dy
            if d2 > r2:
                continue
            t = math.sqrt(d2) / r_dev
            c = lut[min(255, int(t * 255))]
            px[x, y] = (c[0], c[1], c[2], 255)
    return img


# ---------------------------------------------------------------- 六种纹样
# 16x16 输出 = 每条纹样只有 1~2 个输出像素宽，所以线宽都按「逻辑像素」给到
# 0.9~1.7（缩小后正好 1px 左右），细线在 BOX 缩小时会被平均成看不见的灰雾。
def _motif_embers(d, disc, rng):
    """焚城：从中心炸开的余烬裂纹 + 几点飞火。"""
    dark = shade(disc, 0.26) + (225,)
    hot = mix(disc, (255, 240, 205), 0.60) + (240,)
    for k in range(5):
        ang = -math.pi / 2 + k * (2 * math.pi / 5) + rng.uniform(-0.18, 0.18)
        pts = [(CENTRE[0], CENTRE[1])]
        r = 0.85
        while r < 3.2:
            ang += rng.uniform(-0.42, 0.42)
            r += rng.uniform(0.55, 0.9)
            pts.append((CENTRE[0] + math.cos(ang) * r, CENTRE[1] + math.sin(ang) * r))
        _line(d, pts, 0.95, dark)
    for _ in range(4):
        ang = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(1.3, 2.8)
        _circ(d, CENTRE[0] + math.cos(ang) * r, CENTRE[1] + math.sin(ang) * r,
              rng.uniform(0.65, 0.85), fill=hot)


def _motif_crack(d, disc, rng):
    """断层：一道贯穿能量球的锯齿裂痕，亮金镶边 + 暗芯。"""
    bright = mix(disc, (255, 252, 235), 0.62) + (215,)
    dark = shade(disc, 0.16) + (245,)
    main = [(5.6, 6.2), (6.5, 7.4), (7.5, 6.7), (8.7, 8.2), (9.5, 7.3), (10.4, 8.7)]
    _line(d, main, 2.1, bright)
    _line(d, main, 1.25, dark)
    for branch in (
        [(7.5, 6.7), (6.9, 5.2)],
        [(9.5, 7.3), (9.9, 9.7)],
        [(8.7, 8.2), (7.6, 9.4)],
    ):
        _line(d, branch, 1.45, bright)
        _line(d, branch, 0.9, dark)


def _motif_contain(d, disc, rng):
    """隔离：冷白蓝的双层封锁环 + 四向定位卡爪。"""
    ring = shade(disc, 0.38) + (225,)
    clamp = mix(disc, WHITE, 0.28) + (235,)
    _circ(d, CENTRE[0], CENTRE[1], 2.45, outline=ring, width=int(0.85 * SS))
    _circ(d, CENTRE[0], CENTRE[1], 1.35, outline=ring, width=int(0.62 * SS))
    for ang in (0.0, math.pi / 2, math.pi, -math.pi / 2):
        _line(d, [(CENTRE[0] + math.cos(ang) * 2.85, CENTRE[1] + math.sin(ang) * 2.85),
                  (CENTRE[0] + math.cos(ang) * 3.45, CENTRE[1] + math.sin(ang) * 3.45)],
              0.85, clamp)
    for k in range(4):
        ang = math.pi / 4 + k * math.pi / 2
        _line(d, [(CENTRE[0] + math.cos(ang) * 1.65, CENTRE[1] + math.sin(ang) * 1.65),
                  (CENTRE[0] + math.cos(ang) * 2.25, CENTRE[1] + math.sin(ang) * 2.25)],
              0.55, shade(disc, 0.26) + (225,))
    _circ(d, CENTRE[0], CENTRE[1], 0.8, fill=mix(disc, WHITE, 0.72) + (245,))


def _motif_spores(d, disc, rng):
    """蜂群：中央母孢 + 六颗环绕孢子 + 几点游离孢子。"""
    dark = shade(disc, 0.30) + (240,)
    bright = mix(disc, WHITE, 0.55) + (245,)
    _circ(d, CENTRE[0], CENTRE[1], 1.35, fill=mix(disc, WHITE, 0.30) + (248,))
    for k in range(6):
        ang = k * math.pi / 3 + 0.28
        _circ(d, CENTRE[0] + math.cos(ang) * 2.1, CENTRE[1] + math.sin(ang) * 2.1,
              0.88, fill=dark)
    for _ in range(3):
        ang = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(1.1, 2.6)
        _circ(d, CENTRE[0] + math.cos(ang) * r, CENTRE[1] + math.sin(ang) * r,
              0.42, fill=bright)


def _motif_sunrise(d, disc, rng):
    """黎明：八向日芒 + 中央日轮 —— 先铺满暗色扇形再叠亮色辐条，16px 下对比拉满。"""
    dark = shade(disc, 0.30) + (235,)
    bright = (255, 255, 248, 245)

    def wedge(ang, da, r_in, r_out, fill):
        pts = [
            (CENTRE[0] + math.cos(ang - da) * r_in, CENTRE[1] + math.sin(ang - da) * r_in),
            (CENTRE[0] + math.cos(ang - da) * r_out, CENTRE[1] + math.sin(ang - da) * r_out),
            (CENTRE[0] + math.cos(ang + da) * r_out, CENTRE[1] + math.sin(ang + da) * r_out),
            (CENTRE[0] + math.cos(ang + da) * r_in, CENTRE[1] + math.sin(ang + da) * r_in),
        ]
        d.polygon([(_c(x), _c(y)) for x, y in pts], fill=fill)

    _circ(d, CENTRE[0], CENTRE[1], 3.35, fill=dark)
    for k in range(8):
        ang = k * math.pi / 4
        r_out = 3.3 if k % 2 == 0 else 3.0
        wedge(ang, 0.11, 1.5, r_out, bright)
    _circ(d, CENTRE[0], CENTRE[1], 1.5, fill=(255, 255, 252, 255))
    _circ(d, CENTRE[0], CENTRE[1], 1.5, outline=mix(disc, WHITE, 0.35) + (235,),
          width=max(1, int(0.45 * SS)))


def _motif_rain(d, disc, rng):
    """黑雨：三条垂落毒雨 + 液滴 + 地面毒潭。"""
    dark = shade(disc, 0.28) + (235,)
    bright = mix(disc, WHITE, 0.55) + (245,)
    for x0, top in ((6.35, 5.6), (8.0, 5.0), (9.65, 5.8)):
        _line(d, [(x0, top), (x0, 8.55)], 0.95, dark)
        _circ(d, x0, 8.85, 0.72, fill=bright)
    for xx, yy, rr in ((7.15, 6.6, 0.34), (8.95, 5.9, 0.30)):
        _circ(d, xx, yy, rr, fill=bright)
    d.ellipse([_c(6.5), _c(9.85), _c(9.5), _c(10.75)], fill=shade(disc, 0.42) + (205,))


MOTIFS = {
    "cinder": _motif_embers,
    "fault": _motif_crack,
    "quarantine": _motif_contain,
    "swarm": _motif_spores,
    "dawn": _motif_sunrise,
    "black_rain": _motif_rain,
}


# ---------------------------------------------------------------- 组装模块图标
def make_core_icon(core_id: str) -> Image.Image:
    theme = CORE_THEME[core_id]
    disc = CORE_DISC[core_id]
    rng = random.Random("skyfall-core-" + core_id)  # 固定种子 => 可复现
    size = SIZE * SS

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # 1) 外壳投影：让模块「浮」在图标里
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    _rrect(ImageDraw.Draw(shadow), 1.2, 1.45, 15.2, 15.5, 2.0, fill=(0, 0, 0, 88))
    img = Image.alpha_composite(img, shadow)

    # 2) 外壳本体（圆角方形 + 四角压暗）
    body = _chassis_layer(size)
    img.paste(body, (0, 0), _rounded_mask(size, 1.0, 1.0, 15.0, 15.0, 2.0))

    # 3) 外壳描边 + 内圈暗缝（金属倒角）
    edge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ed = ImageDraw.Draw(edge)
    _rrect(ed, 1.0, 1.0, 15.0, 15.0, 2.0,
           outline=CHASSIS_EDGE + (205,), width=max(1, int(0.42 * SS)))
    _rrect(ed, 1.5, 1.5, 14.5, 14.5, 1.6,
           outline=CHASSIS_INNER + (150,), width=max(1, int(0.38 * SS)))
    img = Image.alpha_composite(img, edge)

    # 4) 球窝周围的青色/主题色辉光（中心发光）
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    _circ(ImageDraw.Draw(glow), CENTRE[0], CENTRE[1], 5.1, fill=shade(theme, 0.9) + (78,))
    glow = glow.filter(ImageFilter.GaussianBlur(_c(1.35)))
    img = Image.alpha_composite(img, glow)

    # 5) 球窝凹槽（近黑）+ 槽口高光
    socket = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(socket)
    _circ(sd, CENTRE[0], CENTRE[1], 4.62, fill=SOCKET_BLACK + (255,))
    _circ(sd, CENTRE[0], CENTRE[1], 4.62, outline=(78, 90, 104, 210),
          width=max(1, int(0.40 * SS)))
    img = Image.alpha_composite(img, socket)

    # 6) 能量球（径向渐变）
    ball = _energy_disc(size, disc, 3.95)
    img.paste(ball, (0, 0), _ellipse_mask(size, CENTRE[0], CENTRE[1], 3.95))

    # 7) 能量球外圈：一圈亮协议色，封住球体
    rim = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    _circ(ImageDraw.Draw(rim), CENTRE[0], CENTRE[1], 4.08,
          outline=mix(theme, WHITE, 0.45) + (225,), width=max(1, int(0.42 * SS)))
    img = Image.alpha_composite(img, rim)

    # 8) 协议纹样（裁在球体内部）
    motif = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    MOTIFS[core_id](ImageDraw.Draw(motif), disc, rng)
    clip = _ellipse_mask(size, CENTRE[0], CENTRE[1], 3.5)
    motif.putalpha(ImageChops.multiply(motif.getchannel("A"), clip))
    img = Image.alpha_composite(img, motif)

    # 9) 球面高光点：一颗小冷白点，证明是玻璃球而不是贴纸
    spec = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    _circ(ImageDraw.Draw(spec), 6.7, 6.5, 0.62, fill=(235, 248, 255, 62))
    img = Image.alpha_composite(img, spec)

    # 10) 外壳前景细节：四角螺丝、顶部接口卡舌（带协议色灯条）、底部协议色铭条
    fg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fg)
    for sx, sy in ((2.75, 2.75), (13.25, 2.75), (2.75, 13.25), (13.25, 13.25)):
        _circ(fd, sx, sy, 0.72, fill=SCREW_LIGHT + (250,))
        _circ(fd, sx, sy, 0.30, fill=SCREW_DARK + (255,))
    _rrect(fd, 5.9, 0.24, 10.1, 1.98, 0.5,
           fill=(26, 31, 38, 255), outline=CHASSIS_EDGE + (225,),
           width=max(1, int(0.26 * SS)))
    fd.rectangle([_c(6.4), _c(1.05), _c(9.6), _c(1.45)],
                 fill=mix(theme, WHITE, 0.15) + (245,))
    _rrect(fd, 6.8, 13.5, 9.2, 14.15, 0.32,
           fill=shade(theme, 0.85) + (215,))
    img = Image.alpha_composite(img, fg)

    # 11) BOX 缩到 16x16（16 倍超采样 -> 抗锯齿边）
    return img.resize((SIZE, SIZE), Image.Resampling.BOX)


# ---------------------------------------------------------------- 输出
def write_block(preview_dir: str | None) -> Image.Image:
    img = make_terminal_texture()
    os.makedirs(os.path.dirname(BLOCK_PNG), exist_ok=True)
    img.save(BLOCK_PNG, "PNG")
    if preview_dir:
        _write_preview(preview_dir, "block_skyfall_terminal", img)
    return img


def write_cores(preview_dir: str | None) -> list[Image.Image]:
    os.makedirs(ITEM_DIR, exist_ok=True)
    made = []
    for core_id in CORE_THEME:
        img = make_core_icon(core_id)
        path = os.path.join(ITEM_DIR, "skyfall_core_%s.png" % core_id)
        img.save(path, "PNG")
        if preview_dir:
            _write_preview(preview_dir, "item_skyfall_core_" + core_id, img)
        made.append(img)
    return made


def _write_preview(preview_dir: str, stem: str, img: Image.Image, scale: int = 16):
    os.makedirs(preview_dir, exist_ok=True)
    big = img.resize((SIZE * scale, SIZE * scale), Image.Resampling.NEAREST)
    big.save(os.path.join(preview_dir, stem + "_x%d.png" % scale), "PNG")


def write_sheet(preview_dir: str, images: list[Image.Image], scale: int = 8,
                gap: int = 6) -> None:
    """所有图标横排的总览图（游戏内就是最近邻放大的观感）。"""
    tile = SIZE * scale
    width = len(images) * tile + (len(images) + 1) * gap
    height = tile + 2 * gap
    sheet = Image.new("RGBA", (width, height), (26, 30, 36, 255))
    for i, img in enumerate(images):
        big = img.resize((tile, tile), Image.Resampling.NEAREST)
        sheet.alpha_composite(big, (gap + i * (tile + gap), gap))
    os.makedirs(preview_dir, exist_ok=True)
    sheet.save(os.path.join(preview_dir, "_sheet.png"), "PNG")


# ---------------------------------------------------------------- 自检
def _luminance(c) -> float:
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _ball_mean(img: Image.Image, radius: float = 4.0) -> tuple[float, float, float]:
    """能量球区域的平均色（外壳是六张共用的，算进去会把距离压平）。"""
    px = img.load()
    vals = []
    for y in range(SIZE):
        for x in range(SIZE):
            if math.hypot(x + 0.5 - CENTRE[0], y + 0.5 - CENTRE[1]) <= radius:
                p = px[x, y]
                if p[3] > 8:
                    vals.append(p)
    n = max(1, len(vals))
    return (sum(p[0] for p in vals) / n, sum(p[1] for p in vals) / n,
            sum(p[2] for p in vals) / n)


def _region_lum(img: Image.Image, x0, y0, x1, y1) -> float:
    vals = []
    px = img.load()
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            p = px[x, y]
            if p[3] > 8:
                vals.append(_luminance(p))
    return sum(vals) / len(vals) if vals else 0.0


def _ball_signature(img: Image.Image) -> list[float]:
    """能量球区域 4x4 缩略图的 RGB 指纹：把「球色 + 纹样布局」压成 48 维。

    两张图球色可能接近（比如金色系），但纹样布局不同的话这个指纹会拉开 ——
    这正是「一眼能区分」在 16px 下最接近的量化。
    """
    flat = Image.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, 255)), img)
    crop = flat.convert("RGB").crop((4, 4, 12, 12))
    small = crop.resize((4, 4), Image.Resampling.BOX)
    return [float(v) for p in small.getdata() for v in p]


def _sig_distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a))


def validate(block: Image.Image, cores: dict[str, Image.Image]) -> list[str]:
    problems: list[str] = []
    lines: list[str] = []

    # --- 方块贴图 ---
    lines.append("[block] textures/block/skyfall_terminal.png")
    if block.size != (SIZE, SIZE) or block.mode != "RGBA":
        problems.append("block texture size/mode wrong: %s %s" % (block.size, block.mode))
    if any(p[3] != 255 for p in block.getdata()):
        problems.append("block texture has translucent pixels (a block must be opaque)")
    block_colors = set(block.getdata())
    lines.append("  size=%s mode=%s colors=%d" % (block.size, block.mode, len(block_colors)))
    if len(block_colors) < 12:
        problems.append("block texture has too few colors (%d), looks flat" % len(block_colors))
    cyan = sum(1 for p in block.getdata() if p[1] > 110 and p[2] > 130 and p[2] > p[0] + 50)
    orange = sum(1 for p in block.getdata() if p[0] > 170 and p[2] < 110 and p[1] > 70)
    lines.append("  cyan_px=%d orange_px=%d" % (cyan, orange))
    if cyan < 10:
        problems.append("not enough cyan energy-slot pixels (%d)" % cyan)
    if orange < 2:
        problems.append("not enough orange indicator pixels (%d)" % orange)

    # --- 核心图标 ---
    corners = ((0, 0), (15, 0), (0, 15), (15, 15))
    for core_id, img in cores.items():
        if img.size != (SIZE, SIZE) or img.mode != "RGBA":
            problems.append("%s size/mode wrong: %s %s" % (core_id, img.size, img.mode))
        if any(img.getpixel(c)[3] != 0 for c in corners):
            problems.append("%s corners are not transparent (module should be rounded)" % core_id)
        opaque = sum(1 for p in img.getdata() if p[3] > 8)
        ratio = opaque / float(SIZE * SIZE)
        ncolors = len(set(img.getdata()))
        centre_lum = _region_lum(img, 6, 6, 9, 9)
        corner_lum = (_region_lum(img, 1, 1, 2, 2) + _region_lum(img, 13, 1, 14, 2)
                      + _region_lum(img, 1, 13, 2, 14) + _region_lum(img, 13, 13, 14, 14)) / 4.0
        lines.append("  %-10s colors=%3d opaque=%4.2f centre_lum=%5.1f corner_lum=%5.1f"
                     % (core_id, ncolors, ratio, centre_lum, corner_lum))
        if ncolors < 40:
            problems.append("%s has too few colors (%d), not a gradient energy core"
                            % (core_id, ncolors))
        if not 0.55 <= ratio <= 0.95:
            problems.append("%s opaque-pixel ratio out of range (%.2f)" % (core_id, ratio))
        if centre_lum <= corner_lum + 20:
            problems.append("%s centre is not glowing (centre %.1f <= corner %.1f + 20)"
                            % (core_id, centre_lum, corner_lum))

    # --- 两两可区分：能量球平均色距离 + 球区域 4x4 指纹距离 ---
    ids = list(cores)
    means = {cid: _ball_mean(cores[cid]) for cid in ids}
    sigs = {cid: _ball_signature(cores[cid]) for cid in ids}
    lines.append("[distinct] ball colour distance / ball signature distance (min 40 / 25)")
    min_pair, min_dist = None, 1e9
    min_sig_pair, min_sig = None, 1e9
    for a in ids:
        row = []
        for b in ids:
            d = math.dist(means[a], means[b])
            s = _sig_distance(sigs[a], sigs[b])
            row.append("%5.1f/%-5.1f" % (d, s))
            if a != b and d < min_dist:
                min_pair, min_dist = (a, b), d
            if a != b and s < min_sig:
                min_sig_pair, min_sig = (a, b), s
        lines.append("  %-11s %s" % (a, " ".join(row)))
    lines.append("  closest ball colour: %s / %s = %.1f"
                 % (min_pair[0], min_pair[1], min_dist))
    lines.append("  closest ball signature: %s / %s = %.1f"
                 % (min_sig_pair[0], min_sig_pair[1], min_sig))
    if min_dist < 40:
        problems.append("two cores are too close in colour: %s/%s distance %.1f"
                        % (min_pair[0], min_pair[1], min_dist))
    if min_sig < 25:
        problems.append("two cores look too similar: %s/%s signature distance %.1f"
                        % (min_sig_pair[0], min_sig_pair[1], min_sig))

    lines.append("")
    if problems:
        lines.append("FAIL: %d problem(s)" % len(problems))
        for p in problems:
            lines.append("  - " + p)
    else:
        lines.append("PASS: all checks ok")
    return lines, problems


# ---------------------------------------------------------------- main
def main() -> int:
    parser = argparse.ArgumentParser(description="生成天陨指挥终端原创贴图")
    parser.add_argument("--preview", metavar="DIR",
                        help="可选的预览输出目录（16x 放大图 + 总览图，不属于模组资源）")
    args = parser.parse_args()

    block = write_block(args.preview)
    cores_list = write_cores(args.preview)
    cores = dict(zip(CORE_THEME, cores_list))
    if args.preview:
        write_sheet(args.preview, [block] + cores_list)

    files = [BLOCK_PNG] + [
        os.path.join(ITEM_DIR, "skyfall_core_%s.png" % cid) for cid in CORE_THEME]
    print("wrote %d files:" % len(files))
    for path in files:
        rel = os.path.relpath(path, ROOT)
        print("  %s  (%d bytes)" % (rel, os.path.getsize(path)))

    lines, problems = validate(block, cores)
    print("")
    print("self-check:")
    for line in lines:
        print("  " + line if line else "")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
