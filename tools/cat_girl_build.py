#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""猫耳娘（cat_girl）构建器 v3 —— 单一数据源，重写版（贴身裙 + 纤细四肢 + 圆润脸）。

产物：
  art/cat_girl/cat_girl_spec.json                骨骼/方块/UV/材质 规格（供 Blockbench 装载）
  src/.../textures/entity/cat_girl.png           128x128 贴图（与 spec 的 UV 严格对应）

坐标约定（与 soldier_zombie.geo.json / tools/bride_v2.py 一致）：
  +X = 角色右手边，-Z = 正面，+Y = 上，16u = 1 格，脚底 y=0。
  方块旋转一律为 22.5° 的整数倍（Bedrock 限制）；方块各轴尺寸不小于 1u。

配色取自参考图（Meshy_AI_straight_standing_cat_girl_front.png）的区域采样：
  粉灰发、粉外套、白上衣+浅蓝点缀、蓝白格裙、白袜、蓝白厚底鞋、粉眼。

尺寸速览（单位 u，16u = 1 格）：
  头 7×8×7（窄头显圆润）· 躯干最宽 7 · 手臂袖 3.4/3.6（纤细）· 腿 3.0 ·
  裙三层贴身：臀层椭圆 rx3.6/rz2.3 → 摆层 rx4.2/rz2.7 → 蕾丝层 rx4.5/rz2.95
"""

import json
import math
import pathlib

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = ROOT / "art" / "cat_girl"
TEX_OUT = ROOT / "src/main/resources/assets/apocalypse_zombies/textures/entity/cat_girl.png"
SPEC_OUT = ART / "cat_girl_spec.json"
TEX_SIZE = 128
STEP = 22.5  # Bedrock 方块旋转步进

# ---------------------------------------------------------------- 调色板
C = {
    "skin":         (248, 220, 200, 255),
    "skin_shade":   (232, 196, 172, 255),
    "hair":         (228, 192, 192, 255),
    "hair_light":   (242, 214, 210, 255),
    "hair_shade":   (206, 166, 166, 255),
    "hair_inner":   (238, 160, 178, 255),
    "jacket":       (246, 200, 204, 255),
    "jacket_shade": (228, 172, 180, 255),
    "cuff":         (253, 246, 244, 255),
    "top":          (253, 246, 244, 255),
    "skirt":        (176, 202, 232, 255),
    "skirt_dark":   (146, 174, 208, 255),
    "plaid":        (236, 242, 250, 255),
    "frill":        (251, 251, 253, 255),
    "sock":         (246, 234, 234, 255),
    "sock_shade":   (226, 210, 214, 255),
    "shoe":         (178, 196, 224, 255),
    "shoe_white":   (238, 241, 246, 255),
    "sole":         (247, 248, 250, 255),
    "ribbon":       (168, 188, 216, 255),
    "bell":         (232, 192, 96, 255),
    "plush":        (253, 253, 253, 255),
    "eye":          (198, 134, 154, 255),
    "eye_dark":     (110, 68, 86, 255),
    "eye_light":    (255, 248, 248, 255),
    "blush":        (246, 172, 168, 255),
    "mouth":        (188, 116, 118, 255),
    "lash":         (122, 98, 106, 255),
}

# ---------------------------------------------------------------- 骨骼
BONES = [
    ("root", None, (0, 0, 0)),
    ("left_leg", "root", (-2, 12, 0)),
    ("left_shin", "left_leg", (-2, 6, 0)),
    ("left_foot", "left_shin", (-2, 1.4, 0)),
    ("right_leg", "root", (2, 12, 0)),
    ("right_shin", "right_leg", (2, 6, 0)),
    ("right_foot", "right_shin", (2, 1.4, 0)),
    ("body", "root", (0, 12, 0)),
    ("skirt", "body", (0, 13, 0)),
    ("plush", "skirt", (-4.5, 13.0, -1.6)),
    ("tail1", "body", (0, 13.6, 2.0)),
    ("tail2", "tail1", (0, 15.0, 4.2)),
    ("tail3", "tail2", (0, 16.6, 6.6)),
    ("tail4", "tail3", (0, 18.4, 8.8)),
    ("left_arm", "root", (-5.2, 23.8, 0)),
    ("left_forearm", "left_arm", (-5.2, 18.2, 0)),
    ("left_hand", "left_forearm", (-5.4, 12.4, 0)),
    ("right_arm", "root", (5.2, 23.8, 0)),
    ("right_forearm", "right_arm", (5.2, 18.2, 0)),
    ("right_hand", "right_forearm", (5.4, 12.4, 0)),
    ("item_righthand", "right_hand", (5.4, 9.8, 0)),
    ("head", "root", (0, 24, 0)),
    ("bangs", "head", (0, 30, -4)),
    ("side_lock_l", "head", (-4.4, 28, 0)),
    ("side_lock_r", "head", (4.4, 28, 0)),
    ("hair_back", "head", (0, 30, 4)),
    ("left_ear", "head", (-3.1, 30.8, 0)),
    ("right_ear", "head", (3.1, 30.8, 0)),
    ("left_ribbon", "head", (-4.4, 30.4, 2.6)),
    ("right_ribbon", "head", (4.4, 30.4, 2.6)),
    ("ahoge", "head", (0, 32, 0.6)),
]

CUBES = []


def cube(bone, name, frm, size, mat, rot=None, pivot=None, detail=None):
    if rot:
        for a in rot:
            assert abs(a / STEP - round(a / STEP)) < 1e-6, f"旋转 {a} 不是 22.5 的整数倍：{name}"
    CUBES.append({
        "bone": bone, "name": name,
        "from": [round(v, 2) for v in frm],
        "size": [round(v, 2) for v in size],
        "mat": mat, "rot": rot, "pivot": pivot, "detail": detail,
    })


def pair(bone_fmt, name_fmt, out_x, y, z, size, mat, **kw):
    """镜像对：右侧从 +out_x 起，左侧从 -(out_x+w) 起（w = 尺寸宽）。"""
    w, h, d = size
    cube(bone_fmt.format("right"), name_fmt.format("right"), (out_x, y, z), size, mat, **kw)
    cube(bone_fmt.format("left"), name_fmt.format("left"), (-(out_x + w), y, z), size, mat, **kw)


def ellipse_r(theta_deg, rx, rz):
    """角度方向的椭圆半径：左右方向为 rx，正面/背面方向为 rz。"""
    t = math.radians(theta_deg)
    s, c = abs(math.sin(t)), abs(math.cos(t))
    return 1.0 / math.sqrt((s / rx) ** 2 + (c / rz) ** 2)


# ================================================================ 头 / 脸
cube("head", "head", (-3.5, 24, -3.5), (7, 8, 7), "skin", detail="face")
cube("bangs", "bangs_mid", (-1.6, 28.2, -4.5), (3.2, 3.8, 1.0), "hair")
cube("bangs", "bangs_l", (-3.9, 28.6, -4.5), (2.6, 3.4, 1.0), "hair")
cube("bangs", "bangs_r", (1.3, 28.6, -4.5), (2.6, 3.4, 1.0), "hair")
# 长鬓发（垂到腰）+ 发梢内卷
cube("side_lock_l", "side_lock_l", (-4.35, 16.6, -3.0), (1.1, 12.0, 3.0), "hair")
cube("side_lock_l", "side_lock_l_wave", (-4.55, 13.4, -2.6), (1.3, 3.4, 2.6), "hair")
cube("side_lock_r", "side_lock_r", (3.25, 16.6, -3.0), (1.1, 12.0, 3.0), "hair")
cube("side_lock_r", "side_lock_r_wave", (3.25, 13.4, -2.6), (1.3, 3.4, 2.6), "hair")
# 后发（三段垂到腰 + 顶层波浪）
cube("hair_back", "hair_back_up", (-4.3, 22.4, 3.45), (8.6, 9.8, 1.6), "hair")
cube("hair_back", "hair_back_wave", (-3.9, 23.2, 4.1), (7.8, 3.4, 1.2), "hair")
cube("hair_back", "hair_back_mid", (-4.1, 16.4, 3.2), (8.2, 6.4, 1.5), "hair")
cube("hair_back", "hair_back_low", (-3.5, 11.6, 3.0), (7.0, 5.0, 1.3), "hair")
# 猫耳（外粉灰、内粉，22.5° 外张）
cube("left_ear", "left_ear_out", (-4.4, 30.7, -1.35), (2.6, 3.6, 1.8), "hair",
     rot=(0, 0, STEP), pivot=(-3.1, 30.7, -0.45))
cube("left_ear", "left_ear_in", (-3.85, 31.15, -2.0), (1.7, 2.6, 1.0), "hair_inner",
     rot=(0, 0, STEP), pivot=(-3.1, 30.7, -0.45))
cube("right_ear", "right_ear_out", (1.8, 30.7, -1.35), (2.6, 3.6, 1.8), "hair",
     rot=(0, 0, -STEP), pivot=(3.1, 30.7, -0.45))
cube("right_ear", "right_ear_in", (2.15, 31.15, -2.0), (1.7, 2.6, 1.0), "hair_inner",
     rot=(0, 0, -STEP), pivot=(3.1, 30.7, -0.45))
# 蓝色缎带（发侧蝴蝶结）
cube("left_ribbon", "left_ribbon_knot", (-4.75, 30.0, 2.1), (1.0, 1.1, 1.0), "ribbon")
cube("left_ribbon", "left_ribbon_w1", (-6.15, 29.85, 2.15), (1.5, 1.4, 1.0), "ribbon",
     rot=(0, 0, STEP), pivot=(-4.75, 30.55, 2.6))
cube("left_ribbon", "left_ribbon_w2", (-3.85, 29.85, 2.15), (1.5, 1.4, 1.0), "ribbon",
     rot=(0, 0, -STEP), pivot=(-3.85, 30.55, 2.6))
cube("right_ribbon", "right_ribbon_knot", (3.75, 30.0, 2.1), (1.0, 1.1, 1.0), "ribbon")
cube("right_ribbon", "right_ribbon_w1", (2.35, 29.85, 2.15), (1.5, 1.4, 1.0), "ribbon",
     rot=(0, 0, -STEP), pivot=(2.35, 30.55, 2.6))
cube("right_ribbon", "right_ribbon_w2", (4.65, 29.85, 2.15), (1.5, 1.4, 1.0), "ribbon",
     rot=(0, 0, STEP), pivot=(6.15, 30.55, 2.6))
cube("ahoge", "ahoge", (-0.5, 31.9, 0.1), (1.0, 2.6, 1.0), "hair",
     rot=(-STEP, 0, 0), pivot=(0, 31.9, 0.6))

# ================================================================ 颈 / 躯干
cube("body", "neck", (-1.1, 23.0, -1.1), (2.2, 1.2, 2.2), "skin")
cube("body", "choker", (-1.45, 22.9, -1.45), (2.9, 1.0, 2.9), "ribbon")
cube("body", "bell", (-0.5, 22.5, -2.4), (1.0, 1.0, 1.0), "bell")
cube("body", "chest", (-3.4, 18.2, -1.9), (6.8, 5.8, 3.8), "top")
# 胸部：白色背心下的自然曲线（左右各一块，中间留出领结位的浅沟）
cube("body", "bust_l", (-3.05, 19.6, -3.2), (2.7, 2.6, 1.8), "top", detail="bust")
cube("body", "bust_r", (0.35, 19.6, -3.2), (2.7, 2.6, 1.8), "top", detail="bust")
cube("body", "chest_bow_knot", (-0.5, 20.6, -2.7), (1.0, 1.0, 1.0), "ribbon")
cube("body", "chest_bow_w1", (-2.0, 20.45, -2.6), (1.5, 1.4, 1.0), "ribbon",
     rot=(0, 0, STEP), pivot=(-2.0, 21.15, -2.3))
cube("body", "chest_bow_w2", (0.5, 20.45, -2.6), (1.5, 1.4, 1.0), "ribbon",
     rot=(0, 0, -STEP), pivot=(2.0, 21.15, -2.3))
cube("body", "waist", (-3.0, 15.0, -1.7), (6.0, 3.4, 3.4), "skin")
cube("body", "hips", (-3.5, 12.0, -2.0), (7.0, 3.2, 4.0), "skin")
cube("body", "jacket_back", (-4.0, 16.8, 2.0), (8.0, 7.2, 1.0), "jacket", detail="jacket_back")
cube("body", "lapel_l", (-4.4, 19.6, -2.9), (1.5, 4.2, 1.0), "jacket")
cube("body", "lapel_r", (2.9, 19.6, -2.9), (1.5, 4.2, 1.0), "jacket")
cube("body", "frill_f", (-3.5, 10.3, -2.85), (7.0, 1.5, 1.0), "frill")
cube("body", "frill_b", (-3.5, 10.3, 1.85), (7.0, 1.5, 1.0), "frill")
cube("body", "frill_l", (-4.3, 10.3, -2.3), (1.0, 1.5, 4.6), "frill")
cube("body", "frill_r", (3.3, 10.3, -2.3), (1.0, 1.5, 4.6), "frill")

# ================================================================ 贴身三层裙
#   臀层（最贴身，椭圆半径贴着 hips 盒）→ 摆层（外扩一档）→ 蕾丝层（再外扩、最白）
SKIRT_TIERS = [
    ("hip", 3.6, 2.3, 11.2, 2.4, 0.0, "skirt", "plaid"),
    ("flare", 4.2, 2.7, 9.9, 1.6, 22.5, "skirt", "plaid"),
    ("lace", 4.5, 2.95, 8.8, 1.3, 0.0, "frill", None),
]
for tier_name, rx, rz, top_y, height, offset, mat, detail in SKIRT_TIERS:
    for i in range(8):
        th = i * 45.0 + offset
        r = ellipse_r(th, rx, rz)
        dx, dz = math.sin(math.radians(th)), -math.cos(math.radians(th))
        cx, cz = dx * r, dz * r
        width = round(2.0 * math.pi * ((rx + rz) / 2.0) / 8.0 * 1.05, 2)
        cube("skirt", f"{tier_name}_{i}", (cx - width / 2.0, top_y, cz - 0.5), (width, height, 1.0), mat,
             rot=(0, -th, 0), pivot=(cx, top_y, cz), detail=detail)

# ================================================================ 挂饰小猫（左髋外侧）
cube("plush", "plush_body", (-5.8, 10.5, -2.4), (2.2, 2.6, 1.7), "plush", detail="plush")
cube("plush", "plush_ear_l", (-5.75, 12.9, -2.2), (1.0, 1.0, 1.0), "plush")
cube("plush", "plush_ear_r", (-4.55, 12.9, -2.2), (1.0, 1.0, 1.0), "plush")
cube("plush", "plush_bow", (-5.15, 12.0, -2.9), (1.0, 1.0, 1.0), "ribbon")

# ================================================================ 尾巴（细→蓬松）
cube("tail1", "tail1", (-0.9, 13.0, 2.0), (1.8, 1.8, 2.6), "hair")
cube("tail2", "tail2", (-0.8, 14.4, 4.2), (1.6, 1.6, 2.8), "hair")
cube("tail3", "tail3", (-1.5, 15.4, 6.4), (3.0, 3.0, 4.4), "hair_light", detail="fluff")
cube("tail4", "tail4", (-1.1, 17.0, 8.4), (2.2, 2.2, 3.6), "frill", detail="fluff")

# ================================================================ 手臂（粉色泡泡袖，纤细）
pair("{}_arm", "{}_sleeve_up", 3.5, 18.4, -2.0, (3.4, 5.8, 4.0), "jacket", detail="sleeve")
pair("{}_forearm", "{}_sleeve_low", 3.6, 12.2, -2.1, (3.4, 6.4, 4.2), "jacket", detail="sleeve")
pair("{}_forearm", "{}_cuff", 3.5, 11.3, -2.15, (3.6, 1.0, 4.3), "cuff")
pair("{}_hand", "{}_hand", 4.5, 9.9, -1.0, (1.8, 2.0, 2.0), "skin")

# ================================================================ 腿（纤细 + 白袜 + 厚底鞋 + 右腿袜带）
pair("{}_leg", "{}_thigh", 0.4, 6.2, -1.5, (3.0, 6.0, 3.0), "skin")
cube("right_leg", "right_garter", (0.35, 8.35, -1.55), (3.1, 1.0, 3.1), "frill")
cube("right_leg", "right_garter_bow", (2.4, 8.3, -1.75), (1.0, 1.0, 1.0), "ribbon")
pair("{}_shin", "{}_sock", 0.5, 1.6, -1.4, (2.8, 4.8, 2.8), "sock", detail="sock")
pair("{}_shin", "{}_sock_bow_knot", 0.65, 4.3, -1.95, (1.0, 1.0, 1.0), "ribbon")
pair("{}_shin", "{}_sock_bow_w1", -0.1, 4.1, -1.9, (1.0, 1.0, 1.0), "ribbon",
     rot=(0, 0, -STEP), pivot=(0.4, 4.6, -1.5))
pair("{}_shin", "{}_sock_bow_w2", 1.35, 4.1, -1.9, (1.0, 1.0, 1.0), "ribbon",
     rot=(0, 0, STEP), pivot=(1.2, 4.6, -1.5))
pair("{}_foot", "{}_shoe", 0.15, 1.4, -2.8, (3.5, 2.0, 5.2), "shoe", detail="shoe")
pair("{}_foot", "{}_sole", -0.1, 0.0, -2.95, (3.8, 1.4, 5.5), "sole")


# ================================================================ UV 排布与校验
def pack_uv(cubes, tex_size):
    boxes = []
    for c in cubes:
        w, h, d = c["size"]
        boxes.append([int(round(h + d)) + 1, int(round(2 * (w + d))) + 1, c])
    boxes.sort(key=lambda b: (-b[0], -b[1]))
    x = y = shelf_h = 0
    for bh, bw, c in boxes:
        if x + bw > tex_size:
            x = 0
            y += shelf_h
            shelf_h = 0
        c["uv"] = [x, y]
        x += bw
        shelf_h = max(shelf_h, bh)
    if y + shelf_h > tex_size:
        raise RuntimeError(f"UV 放不下：{y + shelf_h} > {tex_size}")


def uv_rects(c):
    u, v = c["uv"]
    w, h, d = c["size"]
    return {
        "up":    (u + d, v, w, d),
        "down":  (u + d + w, v, w, d),
        "east":  (u, v + d, d, h),
        "north": (u + d, v + d, w, h),
        "west":  (u + d + w, v + d, d, h),
        "south": (u + 2 * d + w, v + d, w, h),
    }


pack_uv(CUBES, TEX_SIZE)


def check_overlap():
    occ = {}
    for c in CUBES:
        for name, (x, y, w, h) in uv_rects(c).items():
            for px in range(int(round(x)), int(round(x + w))):
                for py in range(int(round(y)), int(round(y + h))):
                    if (px, py) in occ:
                        raise RuntimeError(f"UV 重叠：{c['name']}.{name} 与 {occ[(px, py)]} @ {(px, py)}")
                    occ[(px, py)] = f"{c['name']}.{name}"


check_overlap()


# ================================================================ 贴图绘制
def fill(dr, rect, color):
    x, y, w, h = (int(round(n)) for n in rect)
    if w <= 0 or h <= 0:
        return
    dr.rectangle([x, y, x + w - 1, y + h - 1], fill=color)


def shade(color, f):
    return tuple(max(0, min(255, int(ch * f))) for ch in color[:3]) + (color[3],)


def paint_face(dr, rects):
    """正面 7x8：刘海 3 行、大眼 3 行（睫线 + 渐变虹膜 + 双高光）、腮红、小嘴。"""
    nx, ny, nw, nh = (int(round(n)) for n in rects["north"])
    fill(dr, rects["north"], C["skin"])
    fill(dr, (nx, ny, nw, 3), C["hair"])
    fill(dr, (nx, ny, 1, 4), C["hair_light"])
    fill(dr, (nx + nw - 1, ny, 1, 4), C["hair_shade"])
    fill(dr, (nx + 2, ny + 3, 1, 2), C["hair"])
    fill(dr, (nx + nw - 3, ny + 3, 1, 2), C["hair"])
    for ex in (nx + 1, nx + 4):
        fill(dr, (ex, ny + 3, 2, 1), C["lash"])
        fill(dr, (ex, ny + 4, 2, 1), C["eye_dark"])
        fill(dr, (ex, ny + 5, 2, 1), C["eye"])
        fill(dr, (ex, ny + 4, 1, 1), C["eye_light"])
        fill(dr, (ex + 1, ny + 5, 1, 1), C["eye_light"])
        fill(dr, (ex - 1, ny + 4, 1, 2), C["skin_shade"])
    fill(dr, (nx + 1, ny + 6, 1, 1), C["blush"])
    fill(dr, (nx + nw - 2, ny + 6, 1, 1), C["blush"])
    fill(dr, (nx + 3, ny + 6, 1, 1), C["mouth"])
    for fname in ("east", "west"):
        rx, ry, rw, rh = (int(round(n)) for n in rects[fname])
        fill(dr, (rx, ry, rw, 3), C["hair"])
        fill(dr, (rx, ry + 3, rw, 1), C["hair_shade"])
    rx, ry, rw, rh = (int(round(n)) for n in rects["south"])
    fill(dr, (rx, ry, rw, rh), C["hair"])
    for i in range(0, rw, 3):
        fill(dr, (rx + i, ry, 1, rh), C["hair_shade"])
    fill(dr, (rx, ry + rh - 1, rw, 1), C["hair_shade"])
    fill(dr, rects["down"], C["skin_shade"])
    fill(dr, rects["up"], C["hair"])


def paint_cube(dr, c):
    base = C[c["mat"]]
    rects = uv_rects(c)
    for rect in rects.values():
        fill(dr, rect, base)
    fill(dr, rects["up"], shade(base, 1.07))
    fill(dr, rects["down"], shade(base, 0.84))
    fill(dr, rects["east"], shade(base, 0.95))
    fill(dr, rects["west"], shade(base, 0.95))

    det = c.get("detail")
    if det == "face":
        paint_face(dr, rects)
    elif det == "plaid":
        for rect in rects.values():
            rx, ry, rw, rh = (int(round(n)) for n in rect)
            for cx in range(1, rw, 4):
                fill(dr, (rx + cx, ry, 1, rh), C["plaid"])
            for cy in range(2, rh, 4):
                fill(dr, (rx, ry + cy, rw, 1), C["skirt_dark"])
    elif det == "fluff":
        for rect in rects.values():
            rx, ry, rw, rh = (int(round(n)) for n in rect)
            for cy in range(0, rh, 3):
                fill(dr, (rx, ry + cy, rw, 1), shade(base, 0.9))
    elif det == "sleeve":
        for fname in ("north", "east", "west", "south"):
            rx, ry, rw, rh = (int(round(n)) for n in rects[fname])
            fill(dr, (rx, ry + rh - 1, rw, 1), C["jacket_shade"])
    elif det == "jacket_back":
        rx, ry, rw, rh = (int(round(n)) for n in rects["south"])
        for i in range(0, rw, 4):
            fill(dr, (rx + i, ry, 1, rh), C["jacket_shade"])
    elif det == "sock":
        for fname in ("north", "east", "west", "south"):
            rx, ry, rw, rh = (int(round(n)) for n in rects[fname])
            fill(dr, (rx, ry, rw, 1), C["sock_shade"])
            fill(dr, (rx, ry + rh - 2, rw, 1), C["sock_shade"])
    elif det == "shoe":
        for fname in ("north", "east", "west"):
            rx, ry, rw, rh = (int(round(n)) for n in rects[fname])
            fill(dr, (rx, ry + rh // 2, rw, max(1, rh // 3)), C["shoe_white"])
    elif det == "bust":
        # 正面：上缘提亮、下缘压暗，做出圆润的体积暗示
        for fname in ("north", "east", "west"):
            rx, ry, rw, rh = (int(round(n)) for n in rects[fname])
            fill(dr, (rx, ry, rw, 1), shade(base, 1.05))
            fill(dr, (rx, ry + rh - 2, rw, 1), shade(base, 0.93))
            fill(dr, (rx, ry + rh - 1, rw, 1), shade(base, 0.87))
    elif det == "plush":
        rx, ry, rw, rh = (int(round(n)) for n in rects["north"])
        fill(dr, (rx + rw // 2 - 1, ry + rh // 2 - 1, 1, 1), (60, 60, 70, 255))
        fill(dr, (rx + rw // 2 + 1, ry + rh // 2 - 1, 1, 1), (60, 60, 70, 255))
        fill(dr, (rx + rw // 2, ry + rh // 2 + 1, 1, 1), C["blush"])


def paint_texture():
    img = Image.new("RGBA", (TEX_SIZE, TEX_SIZE), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    for c in CUBES:
        paint_cube(dr, c)
    # 发丝竖纹：后发 / 鬓发 / 尾根
    for c in CUBES:
        if c["name"].startswith("hair_back") or c["name"].startswith("side_lock") or c["name"] in ("tail1", "tail2"):
            rects = uv_rects(c)
            for fname in ("north", "east", "west", "south"):
                rx, ry, rw, rh = (int(round(n)) for n in rects[fname])
                for i in range(0, rw, 3):
                    fill(dr, (rx + i, ry, 1, rh), C["hair_shade"])
                fill(dr, (rx, ry, rw, 1), C["hair_light"])
    img.save(TEX_OUT)
    print(f"texture -> {TEX_OUT}")


def write_spec():
    ART.mkdir(parents=True, exist_ok=True)
    spec = {
        "texture_size": TEX_SIZE,
        "bones": [{"name": n, "parent": p, "pivot": list(pv)} for n, p, pv in BONES],
        "cubes": CUBES,
    }
    SPEC_OUT.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"spec -> {SPEC_OUT} ({len(CUBES)} cubes, {len(BONES)} bones)")


if __name__ == "__main__":
    paint_texture()
    write_spec()
