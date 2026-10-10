#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""猫耳娘（cat_girl）128x128 贴图生成器 —— 与 Blockbench 工程 art/cat_girl/cat_girl.bbmodel 的
box UV 布局一一对应（uv_offset 见下表）。

box UV 矩形规则（Bedrock/GeckoLib，立方体 (w,h,d) @ (u,v)）：
    up    = (u+d,     v,   w, d)
    down  = (u+d+w,   v,   w, d)
    east  = (u,       v+d, d, h)     east = +X = 角色右手边
    north = (u+d,     v+d, w, h)     north = -Z = 正面（脸）
    west  = (u+d+w,   v+d, d, h)
    south = (u+2d+w,  v+d, w, h)     后脑/后背

约定（与 tools/bride_v2.py 一致）：+X = 右手边、-Z = 正面、16u = 1 格。
产物：src/main/resources/assets/apocalypse_zombies/textures/entity/cat_girl.png
"""

import pathlib

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "src/main/resources/assets/apocalypse_zombies/textures/entity/cat_girl.png"

# ---- 配色 -----------------------------------------------------------------
SKIN = (247, 205, 176, 255)
SKIN_SHADE = (230, 184, 155, 255)
HAIR = (238, 240, 246, 255)
HAIR_SHADE = (214, 219, 232, 255)
HAIR_TIP = (244, 195, 212, 255)
PINK = (244, 166, 191, 255)
NAVY = (47, 66, 115, 255)
NAVY_DARK = (35, 50, 96, 255)
WHITE = (245, 246, 250, 255)
RED_TIE = (200, 58, 74, 255)
SKIRT = (51, 58, 94, 255)
SKIRT_PLAID = (69, 78, 125, 255)
SKIRT_HEM = (38, 43, 71, 255)
BOOT = (43, 43, 53, 255)
BOOT_TOP = (58, 58, 72, 255)
SOLE = (30, 30, 38, 255)
EYE = (76, 189, 127, 255)
EYE_DARK = (43, 58, 47, 255)
GLINT = (255, 255, 255, 255)
BLUSH = (246, 160, 160, 255)
MOUTH = (176, 106, 90, 255)

# ---- box UV 布局：name = (w, h, d, u, v) -----------------------------------
LAYOUT = {
    "head":       (8, 8, 8, 0, 0),
    "body":       (8, 12, 4, 32, 0),
    "left_arm":   (4, 12, 4, 56, 0),
    "right_arm":  (4, 12, 4, 72, 0),
    "left_leg":   (4, 12, 4, 88, 0),
    "right_leg":  (4, 12, 4, 104, 0),
    "skirt":      (10, 3, 6, 0, 18),
    "back_hair":  (8, 8, 2, 34, 18),
    "twintail_l": (2, 9, 2, 56, 18),
    "twintail_r": (2, 9, 2, 66, 18),
    "left_ear":   (2, 3, 1, 76, 18),
    "right_ear":  (2, 3, 1, 84, 18),
    "tail1":      (2, 2, 2, 92, 18),
    "tail2":      (2, 2, 2, 102, 18),
    "tail3":      (2, 2, 1, 112, 18),
}


def faces(name):
    w, h, d, u, v = LAYOUT[name]
    return {
        "up":    (u + d, v, w, d),
        "down":  (u + d + w, v, w, d),
        "east":  (u, v + d, d, h),
        "north": (u + d, v + d, w, h),
        "west":  (u + d + w, v + d, d, h),
        "south": (u + 2 * d + w, v + d, w, h),
    }


def fill(d, rect, color):
    x, y, w, h = rect
    d.rectangle([x, y, x + w - 1, y + h - 1], fill=color)


def rows(d, rect, row_colors):
    """row_colors: {相对行号: 颜色}"""
    x, y, w, h = rect
    for r, c in row_colors.items():
        d.rectangle([x, y + r, x + w - 1, y + r], fill=c)


def cols(d, rect, col_colors):
    x, y, w, h = rect
    for c_i, c in col_colors.items():
        d.rectangle([x + c_i, y, x + c_i, y + h - 1], fill=c)


def main():
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ---- 头：脸 + 头发刘海 ----------------------------------------------
    f = faces("head")
    for r in f.values():
        fill(d, r, SKIN)
    fill(d, f["up"], HAIR)                      # 天灵盖
    fill(d, f["down"], SKIN_SHADE)              # 下巴阴影
    fill(d, f["south"], HAIR)                   # 后脑
    # 正面：刘海 3 行 + 眼睛 + 腮红 + 嘴
    x, y, w, h = f["north"]
    rows(d, f["north"], {0: HAIR, 1: HAIR, 2: HAIR})
    for ex in (x + 1, x + 5):                   # 眼白框
        d.rectangle([ex, y + 3, ex + 1, y + 4], fill=EYE_DARK)
        d.rectangle([ex, y + 3, ex + 1, y + 3], fill=EYE)
        d.point((ex, y + 3), fill=GLINT)
    d.point((x, y + 6), fill=BLUSH)
    d.point((x + 1, y + 6), fill=BLUSH)
    d.point((x + w - 1, y + 6), fill=BLUSH)
    d.point((x + w - 2, y + 6), fill=BLUSH)
    d.rectangle([x + 3, y + 6, x + 4, y + 7], fill=MOUTH)
    # 侧脸：鬓角头发（上 3 行 + 靠后 1 列）
    for side in ("east", "west"):
        x, y, w, h = f[side]
        rows(d, f[side], {0: HAIR, 1: HAIR, 2: HAIR})
        d.rectangle([x, y + 3, x, y + h - 1], fill=HAIR_SHADE)

    # ---- 身体：水手服上衣 -----------------------------------------------
    f = faces("body")
    for r in f.values():
        fill(d, r, NAVY)
    fill(d, f["up"], WHITE)                     # 肩部海军领
    fill(d, f["down"], NAVY_DARK)
    x, y, w, h = f["north"]
    rows(d, f["north"], {0: WHITE, 1: WHITE})   # 领口
    d.rectangle([x + 3, y + 2, x + 4, y + 3], fill=RED_TIE)   # 领巾
    d.rectangle([x + 2, y + 2, x + 5, y + 2], fill=WHITE)
    for side in ("east", "west"):
        rows(d, f[side], {0: WHITE, 1: WHITE})
    # 后背：X 型交叉海军领
    x, y, w, h = f["south"]
    d.rectangle([x, y, x + w - 1, y + 1], fill=WHITE)
    for i in range(w):
        d.point((x + i, y + 2 + i % 3), fill=WHITE if i % 4 else NAVY_DARK)

    # ---- 裙子：格纹 ------------------------------------------------------
    f = faces("skirt")
    for name, rect in f.items():
        fill(d, rect, SKIRT)
        x, y, w, h = rect
        for cx in range(0, w, 4):               # 竖条纹
            d.rectangle([x + cx, y, x + cx, y + h - 1], fill=SKIRT_PLAID)
        if name != "up":
            d.rectangle([x, y + h - 1, x + w - 1, y + h - 1], fill=SKIRT_HEM)  # 裙摆

    # ---- 手臂：及肘水手袖 -----------------------------------------------
    for arm in ("left_arm", "right_arm"):
        f = faces(arm)
        for rect in f.values():
            fill(d, rect, SKIN)
        fill(d, f["up"], NAVY)
        fill(d, f["down"], SKIN)
        for side in ("east", "north", "west", "south"):
            x, y, w, h = f[side]
            rows(d, f[side], {0: NAVY, 1: NAVY, 2: NAVY, 3: NAVY, 4: NAVY, 5: WHITE})

    # ---- 腿部：过膝长靴 --------------------------------------------------
    for leg in ("left_leg", "right_leg"):
        f = faces(leg)
        fill(d, f["up"], SKIN)
        fill(d, f["down"], SOLE)
        for side in ("east", "north", "west", "south"):
            x, y, w, h = f[side]
            rows(d, f[side], {i: SKIN for i in range(0, 6)})
            rows(d, f[side], {6: BOOT_TOP, 7: BOOT, 8: BOOT, 9: BOOT, 10: BOOT, 11: SOLE})

    # ---- 后脑头发 --------------------------------------------------------
    f = faces("back_hair")
    for rect in f.values():
        fill(d, rect, HAIR)
    x, y, w, h = f["south"]
    for cx in range(0, w, 3):                   # 发丝明暗
        d.rectangle([x + cx, y, x + cx, y + h - 1], fill=HAIR_SHADE)
    d.rectangle([x, y + h - 1, x + w - 1, y + h - 1], fill=HAIR_SHADE)
    fill(d, f["down"], HAIR_SHADE)

    # ---- 双马尾：发白 → 粉渐变发梢 --------------------------------------
    for tw in ("twintail_l", "twintail_r"):
        f = faces(tw)
        for rect in f.values():
            fill(d, rect, HAIR)
        for side in ("east", "north", "west", "south"):
            x, y, w, h = f[side]
            d.rectangle([x, y + h - 2, x + w - 1, y + h - 2], fill=HAIR_TIP)
            d.rectangle([x, y + h - 1, x + w - 1, y + h - 1], fill=PINK)
        fill(d, f["up"], HAIR)
        fill(d, f["down"], PINK)

    # ---- 猫耳：外白内粉 --------------------------------------------------
    for ear in ("left_ear", "right_ear"):
        f = faces(ear)
        for rect in f.values():
            fill(d, rect, HAIR)
        fill(d, f["north"], PINK)               # 正面 = 内耳
        fill(d, f["up"], HAIR_SHADE)

    # ---- 尾巴 ------------------------------------------------------------
    for t in ("tail1", "tail2"):
        f = faces(t)
        for rect in f.values():
            fill(d, rect, HAIR)
        fill(d, f["down"], HAIR_SHADE)
    f = faces("tail3")
    for rect in f.values():
        fill(d, rect, PINK)                     # 尾尖全粉

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(f"written {OUT} {img.size}")


if __name__ == "__main__":
    main()
