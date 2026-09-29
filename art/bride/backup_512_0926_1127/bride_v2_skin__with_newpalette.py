#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""美女僵尸 Phase 2 贴图生成器 —— 读 art/bride/bride_atlas.json，画出 512×512 的 bride_zombie.png。

管线位置：tools/bride_v2.py（几何/动画/图集） → 本脚本（贴图） → Blender 预览 → Blockbench 校验。

每个 UV 矩形由「画家函数」独立作画；左右成对的部位带 flip 标记，矩形视图会自动水平镜像，
所以内襟肤色 / 外侧发丝这类方向性细节在两侧是对称正确的。
纯标准库（zlib + struct）手写 PNG，保证可重复：同一份输入两次运行 sha256 完全一致。
"""

import hashlib
import json
import pathlib
import struct
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = ROOT / "art" / "bride"
MANIFEST = ART / "bride_atlas.json"
SRC_TEX = ROOT / "src/main/resources/assets/apocalypse_zombies/textures/entity/bride/bride_zombie.png"
ART_TEX = ART / "bride_zombie.png"

# ---------------------------------------------------------------------------
# 调色板
# ---------------------------------------------------------------------------
# 调色板 —— 取自参考皮肤 C:\Users\Administrator\Downloads\custom (5).png 的精确取色
# （雪白礼服 + 冰蓝花边 + 薰衣草灰长发，冷调；常量名保持不变，48 个画家函数无需改动）
SKIN = (246, 236, 247)          # #F6ECF7 淡紫白肤
SKIN_HI = (253, 244, 246)       # #FDF4F6 高光
SKIN_SH = (233, 227, 239)       # #E9E3EF 浅紫影
SKIN_COOL = (205, 215, 235)     # #CDD7EB 冷调影
SKIN_DEEP = (188, 197, 224)     # #BCC5E0 深冷影
BLOOD = (141, 137, 160)         # #8D89A0 冷重色（原血红 → 灰紫重色）
BLOOD_D = (133, 116, 149)       # #857495 深冷重色
SILK = (255, 255, 255)          # #FFFFFF 白纱
SILK_HI = (255, 249, 255)       # #FFF9FF 纱高光
SILK_SH = (210, 208, 219)       # #D2D0DB 纱影
SILK_D = (186, 182, 208)        # #BAB6D0 纱深影
LINING = (157, 158, 183)        # #9D9EB7 内衬
CLOTH_D = (193, 190, 207)       # #C1BECF 布料暗
CLOTH_T = (204, 202, 214)       # #CCCAD6 布料亮
GOLD = (205, 231, 247)          # #CDE7F7 金属 → 冰蓝饰件
GOLD_HI = (232, 246, 255)       # #E8F6FF 冰蓝高光
GOLD_D = (168, 198, 232)        # #A8C6E8 冰蓝暗
HAIR = (204, 202, 214)          # #CCCAD6 灰紫发基色
HAIR_HI = (217, 215, 226)       # #D9D7E2 发高光
HAIR_MID = (170, 172, 196)      # #AAACC4 发影
HAIR_SIL = (242, 240, 246)      # #F2F0F6 银白发丝
LACE = (255, 255, 255)          # #FFFFFF 蕾丝
LACE_SH = (220, 218, 228)       # #DCDAE4 蕾丝影
LIP = (244, 227, 239)           # #F4E3EF 唇（柔粉）
LIP_HI = (253, 244, 250)        # #FDF4FA 唇高光
TOOTH = (255, 255, 255)         # #FFFFFF
EYE_WHITE = (246, 236, 247)     # #F6ECF7 眼白
IRIS = (141, 137, 160)          # #8D89A0 灰紫瞳
IRIS_HI = (188, 197, 224)       # #BCC5E0 瞳高光
PUPIL = (133, 116, 149)         # #857495 瞳孔（柔，不用黑）
SHOE = (186, 182, 208)          # #BAB6D0 鞋
SHOE_HI = (210, 208, 219)       # #D2D0DB 鞋高光
SEAM = (157, 158, 183)          # #9D9EB7 缝线
STOCK = (255, 249, 255)         # #FFF9FF 袜
STOCK_SH = (228, 224, 236)      # #E4E0EC 袜影
GEM = (205, 231, 247)           # #CDE7F7 宝石 → 冰蓝
GEM_HI = (232, 246, 255)        # #E8F6FF 宝石高光


# ---------------------------------------------------------------------------
# 画布
# ---------------------------------------------------------------------------
class Canvas:
    def __init__(self, w, h, bg=(0, 0, 0, 0)):
        self.w, self.h = w, h
        self.buf = bytearray(w * h * 4)
        for i in range(w * h):
            self.buf[i * 4:i * 4 + 4] = bytes(bg)

    def set(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 4
            self.buf[i:i + 4] = bytes((int(c[0]), int(c[1]), int(c[2]),
                                      int(c[3]) if len(c) > 3 else 255))

    def get(self, x, y):
        i = (int(y) * self.w + int(x)) * 4
        return tuple(self.buf[i:i + 4])

    def blend(self, x, y, c, a):
        x, y = int(x), int(y)
        if a <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        a = min(1.0, a)
        r, g, b, ca = self.get(x, y)
        na = c[3] / 255.0 if len(c) > 3 else 1.0
        self.set(x, y, (int(r + (c[0] - r) * a), int(g + (c[1] - g) * a),
                        int(b + (c[2] - b) * a), max(ca, int(255 * na * a))))


def frac(x, y, seed=0):
    """确定性哈希噪声（不用 random，保证跨次运行一致）。"""
    n = (x * 73856093) ^ (y * 19349663) ^ (seed * 83492791)
    n &= 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


class Rect:
    """UV 矩形视图：画家用相对坐标作画，flip 时自动水平镜像。"""

    def __init__(self, canvas, rect, flip):
        self.c = canvas
        self.u, self.v, self.w, self.h = rect
        self.flip = flip

    def x(self, x):
        return self.u + (self.w - 1 - x if self.flip else x)

    def set(self, x, y, col):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.c.set(self.x(x), self.v + y, col)

    def get(self, x, y):
        return self.c.get(self.x(max(0, min(self.w - 1, x))), self.v + max(0, min(self.h - 1, y)))

    def blend(self, x, y, col, a):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.c.blend(self.x(x), self.v + y, col, a)

    def fill(self, x, y, w, h, col):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.set(xx, yy, col)

    def wipe(self, col):
        self.fill(0, 0, self.w, self.h, col)

    def vgrad(self, col0, col1, x=0, y=0, w=None, h=None):
        w = self.w if w is None else w
        h = self.h if h is None else h
        for yy in range(h):
            f = yy / float(max(1, h - 1))
            col = tuple(int(col0[i] + (col1[i] - col0[i]) * f) for i in range(3))
            for xx in range(w):
                self.set(x + xx, y + yy, col)

    def band(self, y, h, col, a=1.0):
        for yy in range(y, y + h):
            for xx in range(self.w):
                self.blend(xx, yy, col, a)

    def col_band(self, x, w, col, a):
        for xx in range(x, x + w):
            for yy in range(self.h):
                self.blend(xx, yy, col, a)

    def disc(self, cx, cy, r, col, a=1.0, squash=1.0):
        for yy in range(int(cy - r * squash) - 1, int(cy + r * squash) + 2):
            for xx in range(int(cx - r) - 1, int(cx + r) + 2):
                dx = (xx - cx) / float(r)
                dy = (yy - cy) / float(max(0.01, r * squash))
                if dx * dx + dy * dy <= 1.0:
                    self.blend(xx, yy, col, a)

    def vline(self, x, y0, y1, col, a=1.0):
        for yy in range(min(y0, y1), max(y0, y1) + 1):
            self.blend(x, yy, col, a)

    def hline(self, y, x0, x1, col, a=1.0):
        for xx in range(min(x0, x1), max(x0, x1) + 1):
            self.blend(xx, y, col, a)

    def noise(self, col, seed, amount=0.06, step=1):
        for yy in range(0, self.h, step):
            for xx in range(0, self.w, step):
                if frac(xx, yy, seed) < amount * 4:
                    self.blend(xx, yy, col, frac(xx, yy, seed + 7) * 0.5)


# ---------------------------------------------------------------------------
# 画家函数
# ---------------------------------------------------------------------------

def p_flat(P, sample):
    R = P.R
    base = {
        "lining": LINING, "cloth_dark": CLOTH_D, "cloth_top": CLOTH_T,
        "skin_dark": SKIN_DEEP, "hair_dark": (20, 16, 26), "silk_mid": (204, 194, 180),
    }[sample]
    R.wipe(base)
    R.noise((max(0, base[0] - 22), max(0, base[1] - 22), max(0, base[2] - 22)), hash(sample) & 0xFF, 0.10)


def grain(R, col, seed, amount=0.10):
    for yy in range(R.h):
        for xx in range(R.w):
            f = frac(xx, yy, seed)
            if f < amount:
                R.blend(xx, yy, col, (f / amount) * 0.35)


def p_skin(P):
    """体表皮肤：冷调象牙白 + 由上到下的明暗 + 淤青/血痕。"""
    R = P.R
    R.vgrad(SKIN_HI, SKIN_SH)
    grain(R, SKIN_DEEP, 11, 0.14)
    # 上缘提亮、下缘压暗
    R.band(0, max(1, R.h // 6), SKIN_HI, 0.35)
    R.band(R.h - max(1, R.h // 5), max(1, R.h // 5), SKIN_COOL, 0.35)
    R.disc(R.w * 0.3, R.h * 0.3, max(1, R.w * 0.28), SKIN_HI, 0.22, 1.0)


def p_leg_skin(P):
    p_skin(P)
    R = P.R
    if P.part.endswith("_r") or "thigh_low" in P.part:
        R.disc(R.w * 0.72, R.h * 0.62, max(1.0, R.w * 0.22), SKIN_COOL, 0.5)   # 尸斑
        R.disc(R.w * 0.7, R.h * 0.66, max(1.0, R.w * 0.12), (120, 92, 118), 0.35)


def p_neck_skin(P):
    p_skin(P)
    R = P.R
    R.band(R.h - max(2, R.h // 4), max(2, R.h // 4), BLOOD, 0.55)   # 颈口血
    R.band(R.h - 2, 2, BLOOD_D, 0.7)


def p_hand(P):
    p_skin(P)
    R = P.R
    for i in range(1, 4):        # 指缝阴影
        R.hline(int(R.h * i / 4.0), 1, R.w - 2, SKIN_SH, 0.35)
    R.band(0, 2, SKIN_HI, 0.4)
    R.band(R.h - 2, 2, SKIN_COOL, 0.4)
    R.disc(R.w * 0.22, R.h * 0.35, max(1.0, R.w * 0.16), BLOOD, 0.35)


def p_silk(P):
    """象牙缎面：中间一道高光脊，两侧压暗，像裙子的一道褶。"""
    R = P.R
    R.wipe(SILK)
    for xx in range(R.w):
        f = xx / float(max(1, R.w - 1))
        # 双峰折光：0.35 处最亮
        d = abs(f - 0.34)
        sh = min(1.0, d * 1.9)
        col = tuple(int(SILK_HI[i] + (SILK_D[i] - SILK_HI[i]) * sh) for i in range(3))
        for yy in range(R.h):
            R.set(xx, yy, col)
    grain(R, SILK_SH, 23, 0.05)
    R.band(R.h - max(1, R.h // 5), max(1, R.h // 5), CLOTH_D, 0.22)


def p_bodice_lower(P):
    """下胸衣：缎面 + 竖向鱼骨缝 + 金色滚边 + 血渍。"""
    p_silk(P)
    R = P.R
    for i in range(1, 7):
        x = int(R.w * i / 7.0)
        R.vline(x, 0, R.h - 1, SILK_D, 0.5)
        R.vline(x + 1, 0, R.h - 1, SILK_HI, 0.28)
    R.band(R.h - max(2, R.h // 6), 2, GOLD, 0.9)
    R.band(R.h - 2, 1, GOLD_D, 0.8)
    for i in range(3):
        x = int(R.w * (0.2 + 0.3 * i))
        R.disc(x, int(R.h * 0.28), max(1.0, R.h * 0.09), BLOOD, 0.55)
    if R.w >= 6:
        R.disc(R.w * 0.72, R.h * 0.18, max(1.0, R.w * 0.1), GOLD_HI, 0.5)


def p_bodice_belt(P):
    """胸衣下摆过渡带：一道金线 + 缎面。"""
    p_silk(P)
    R = P.R
    R.band(int(R.h * 0.55), max(1, int(R.h * 0.22)), GOLD, 0.55)
    R.band(int(R.h * 0.55) + max(1, int(R.h * 0.22)) - 1, 1, GOLD_D, 0.7)


def p_bodice_back(P):
    """后背：缎面 + 交叉系带 + 蝴蝶结眼。"""
    p_silk(P)
    R = P.R
    x0, x1 = int(R.w * 0.22), int(R.w * 0.78)
    for yy in range(1, R.h - 1):
        off = int((yy / 3.0)) % 4
        for xx in range(x0 + off, x1, 4):
            R.blend(xx, yy, (232, 220, 200), 0.55)
        R.blend(x0 + ((yy // 2) % 3), yy, GOLD_D, 0.5)
    for ey in range(2, R.h - 2, max(3, R.h // 4)):
        R.disc(x0, ey, 1.0, GOLD, 0.85)
        R.disc(x1, ey, 1.0, GOLD, 0.85)
    R.band(R.h - max(2, R.h // 6), max(2, R.h // 6), CLOTH_D, 0.3)


def p_bodice_back_low(P):
    p_bodice_back(P)
    R = P.R
    R.band(R.h - 2, 2, GOLD, 0.6)


def p_bodice_side(P):
    """侧片：缎面 + 一条侧缝。"""
    p_silk(P)
    R = P.R
    R.vline(int(R.w * 0.18), 0, R.h - 1, SILK_D, 0.45)
    R.vline(int(R.w * 0.82), 0, R.h - 1, SILK_D, 0.45)


def p_decollete(P):
    """领口：上半皮肤，V 形蕾丝压边，下半缎面。"""
    R = P.R
    outer = CLOTH_T if P.face in ("u", "d") else None
    if outer:
        R.wipe(outer)
        return
    R.vgrad(SKIN_HI, SKIN)
    R.band(int(R.h * 0.55), R.h, SILK, 0.85)
    # V 字蕾丝：从两肩往中间收
    for yy in range(0, int(R.h * 0.62)):
        f = yy / float(max(1, int(R.h * 0.62)))
        inset = int((1.0 - f) * R.w * 0.42)
        R.blend(inset, yy, LACE, 0.9)
        R.blend(inset + 1, yy, LACE_SH, 0.7)
        R.blend(R.w - 1 - inset, yy, LACE, 0.9)
        R.blend(R.w - 2 - inset, yy, LACE_SH, 0.7)
    for yy in range(0, int(R.h * 0.62), 3):     # 蕾丝齿
        f = yy / float(max(1, int(R.h * 0.62)))
        inset = int((1.0 - f) * R.w * 0.42)
        R.blend(inset + 2, yy, LACE, 0.55)
        R.blend(R.w - 3 - inset, yy, LACE, 0.55)
    R.band(R.h - 3, 3, CLOTH_D, 0.35)
    R.disc(R.w * 0.5, int(R.h * 0.30), max(1.0, R.w * 0.08), SKIN_SH, 0.35)   # 锁骨阴影


def p_bodice_strap(P):
    p_silk(P)
    R = P.R
    for i in range(0, R.w, 3):
        R.vline(i, 0, R.h - 1, LACE, 0.35)


def p_bust_front(P):
    """胸瓣正面：缎面胸衣 + 内侧领口肤色（镜像后左右对称）+ 外侧一线发丝。"""
    R = P.R
    side = P.kwargs.get("side", "r")
    R.wipe(SILK)
    for yy in range(R.h):
        f = yy / float(max(1, R.h - 1))
        # 上方受光、下方收暗，做出球面感
        for xx in range(R.w):
            g = xx / float(max(1, R.w - 1))
            shade = 0.45 * abs(g - 0.55) + 0.55 * f
            col = tuple(int(SILK_HI[i] + (SILK_D[i] - SILK_HI[i]) * min(1.0, shade)) for i in range(3))
            R.set(xx, yy, col)
    grain(R, SILK_D, 31, 0.12)
    # 内侧（靠近中线）领口：一条渐隐的肤色 + 蕾丝边
    inner_w = max(2, int(R.w * 0.28))
    for yy in range(R.h):
        f = yy / float(max(1, R.h - 1))
        wdt = int(inner_w * (0.35 + 0.65 * f))
        for xx in range(wdt):
            R.blend(xx, yy, SKIN, 0.55 * (1.0 - xx / float(max(1, wdt))))
        R.blend(wdt, yy, LACE, 0.8)
        R.blend(wdt + 1, yy, LACE_SH, 0.5)
    # 外侧：一缕头发搭在胸衣上（半透明 + 到腰就淡出，别做成两条黑杠）
    xs = int(R.w * 0.80)
    for yy in range(R.h):
        f = yy / float(max(1, R.h - 1))
        a = 0.55 * (1.0 - 0.75 * f)
        wob = int(1.2 * (frac(yy, 0, 5) - 0.5))
        R.blend(xs + wob, yy, HAIR_MID, a)
        R.blend(xs + wob, yy, HAIR_HI, a * 0.4)
    R.band(R.h - 2, 2, CLOTH_D, 0.45)
    R.band(0, 1, SILK_HI, 0.5)


def p_bust_edge(P):
    """胸瓣侧缘：外侧是肩（发丝垂落），内侧是领口（肤色 + 蕾丝）。"""
    R = P.R
    R.vgrad(SILK, SILK_SH)
    for yy in range(R.h):
        f = yy / float(max(1, R.h - 1))
        for xx in range(R.w):
            # 球面感：贴躯干的一侧压暗一点，但绝不用深色
            R.blend(xx, yy, SILK_D, 0.18 + 0.22 * f)
    if P.kwargs.get("outer"):
        for yy in range(R.h):
            a = 0.5 * (1.0 - 0.6 * yy / float(max(1, R.h - 1)))
            wob = int(1.0 * (frac(yy, 3, 9) - 0.5))
            R.blend(R.w // 2 + wob, yy, HAIR_MID, a)
    else:
        for yy in range(R.h):
            R.blend(0, yy, SKIN, 0.55)
            R.blend(1, yy, LACE, 0.6)


def p_bust_soft(P):
    """下缘补瓣：更暗的缎面 + 一道阴影收尾，让两瓣看起来是圆润下垂的。"""
    R = P.R
    R.vgrad(SILK_SH, SILK_D)
    grain(R, SILK_D, 41, 0.12)
    R.band(0, 1, SILK, 0.4)


def p_face(P):
    """脸：整张画。矩形上边 = 头顶(31.6u)，下边 = 下巴(24.4u)，宽 5.2u（31×43 px @TPU6）。

    做法：先铺底（象牙冷调 + 脸型明暗），再把「左半边」的眉眼五官画好，
    最后整块镜像到右半边 —— 手工逐像素描左右两只眼必然差一两像素，
    镜像一次就完全对称了；不对称的尸斑/缝合疤在镜像之后再单独补。
    """
    R = P.R
    w, h = R.w, R.h
    nx = w // 2
    R.vgrad(SKIN_HI, SKIN)
    grain(R, SKIN_DEEP, 3, 0.045)
    for xx in range(w):                       # 脸型：两侧收暗
        g = abs(xx / float(max(1, w - 1)) - 0.5) * 2.0
        for yy in range(h):
            R.blend(xx, yy, SKIN_COOL, 0.40 * max(0.0, g - 0.32) / 0.68)
    R.band(0, max(1, h // 7), SKIN_HI, 0.30)
    R.band(h - max(2, h // 5), max(2, h // 5), SKIN_DEEP, 0.30)

    def blur_band(y0, y1, col, a0):
        for yy in range(y0, y1):
            f = (yy - y0) / float(max(1, y1 - y0 - 1))
            R.band(yy, 1, col, a0 * (1.0 - f))

    blur_band(0, max(1, int(h * 0.18)), (126, 104, 114), 0.5)     # 刘海投影

    # ---- 左半边五官（x < nx）----
    # 眉：外淡内浓的柔和拱形
    by = int(h * 0.295)
    for k in range(0, int(w * 0.30)):
        x = w * 0.44 - k                      # 从外向内
        y = by + int((k / float(max(1, int(w * 0.30) - 1))) ** 2 * 2.0)
        a = 0.9 - 0.55 * (k / float(max(1, int(w * 0.30) - 1)))
        R.blend(x, y, (60, 42, 50), a)
        R.blend(x, y + 1, (60, 42, 50), a * 0.5)
    # 眼窝 + 眼白 + 瞳孔
    ey = int(h * 0.425)
    cx = nx - w * 0.205
    ez = max(2.6, w * 0.115)
    R.disc(cx, ey, ez * 1.7, (150, 128, 150), 0.40, 0.70)
    R.disc(cx, ey, ez * 1.35, (250, 248, 244), 0.92, 0.78)
    R.disc(cx, ey, ez * 0.78, IRIS, 1.0, 1.0)
    for dy in (-1, 0, 1):                     # 干净的方瞳（像素尺度下比圆的好看）
        for dx in (-1, 0, 1):
            if abs(dx) + abs(dy) <= 1:
                R.set(round(cx) + dx, ey + dy, PUPIL)
    R.set(round(cx) - 1, ey - 2, (255, 255, 255))          # 高光
    R.blend(round(cx) + 1, ey + 1, IRIS_HI, 0.8)
    for k in range(-int(ez * 1.3), int(ez * 1.3) + 1):     # 上睫毛
        R.blend(cx + k, ey - ez * 0.95, (26, 18, 26), 0.92)
    R.blend(cx, ey + ez * 0.9, (36, 26, 34), 0.5)
    R.disc(cx, ey - ez * 0.6, ez * 1.6, (152, 118, 158), 0.16, 0.6)   # 淡眼影
    R.disc(w * 0.24, int(h * 0.585), max(1.2, w * 0.075), (212, 126, 134), 0.24)   # 腮红
    for yy in range(0, int(h * 0.30)):                     # 额角碎发
        f = yy / float(max(1, int(h * 0.30)))
        x = w * 0.07 + yy * 0.30
        R.blend(x, yy, HAIR_MID, 0.82)
        R.blend(x + 1, yy, HAIR, 0.7)
        R.blend(x - 1, yy, HAIR_HI, 0.25)

    # ---- 整块镜像到右半边 ----
    for yy in range(h):
        for xx in range(nx):
            R.set(w - 1 - xx, yy, R.get(xx, yy))

    # ---- 中线结构：鼻与唇（本身左右对称）----
    ny = int(h * 0.575)
    for yy in range(int(h * 0.35), ny):                     # 鼻梁：中亮侧暗（只画鼻子这一小段，别拉通整行）
        f = (yy - int(h * 0.35)) / float(max(1, ny - int(h * 0.35)))
        R.blend(nx, yy, SKIN_HI, 0.35 + 0.35 * f)
        R.blend(nx - 1, yy, SKIN_HI, 0.22 + 0.2 * f)
        R.blend(nx + 1, yy, SKIN_HI, 0.22 + 0.2 * f)
        R.blend(nx - 2, yy, SKIN_SH, 0.30 + 0.2 * f)
        R.blend(nx + 2, yy, SKIN_SH, 0.30 + 0.2 * f)
        R.blend(nx - 3, yy, SKIN_COOL, 0.14)
        R.blend(nx + 3, yy, SKIN_COOL, 0.14)
    for xx in range(nx - 2, nx + 3):                        # 鼻头
        R.blend(xx, ny, SKIN_HI, 0.55)
        R.blend(xx, ny + 1, (150, 122, 134), 0.75)          # 鼻底
    for sgn in (-1, 1):
        R.blend(nx + sgn * 2, ny + 2, (118, 92, 108), 0.8)  # 鼻孔
        R.blend(nx + sgn * 3, ny + 1, SKIN_COOL, 0.25)
    ly = int(h * 0.745)
    lw = max(4, int(w * 0.28))
    for k in range(-lw, lw + 1):
        f = abs(k) / float(max(1, lw))
        R.blend(nx + k, ly - 1 + int(f * f * 2.0), LIP, 0.95)         # 上唇
        R.blend(nx + k, ly + 1 + int(f * f * 2.4), LIP, 0.95)         # 下唇
        R.blend(nx + k, ly + 2 + int(f * f * 2.4), (104, 18, 32), 0.75)
    R.hline(ly, nx - lw + 1, nx + lw - 1, (56, 8, 16), 0.9)           # 唇缝
    R.hline(ly + 2, nx - max(1, lw // 2), nx + max(1, lw // 2), LIP_HI, 0.35)
    R.blend(nx, ly - 2, (74, 12, 24), 0.8)                            # 唇峰
    R.blend(nx - lw + 1, ly, (56, 8, 16), 0.9)
    R.blend(nx + lw - 1, ly, (56, 8, 16), 0.9)

    # ---- 不对称细节（镜像之后补，免得两边一样假）----
    R.disc(w * 0.76, int(h * 0.63), max(1.2, w * 0.08), (152, 124, 152), 0.28)   # 尸斑
    for k in range(3):
        R.blend(w * 0.735 + (k % 2), int(h * 0.655) + k, (74, 46, 62), 0.78)
    R.blend(nx - lw + 1, ly + 3, BLOOD, 0.8)                                      # 嘴角往下淌的一道血
    R.blend(nx - lw + 1, ly + 4, BLOOD, 0.65)
    R.blend(nx - lw + 1, ly + 5, BLOOD_D, 0.5)


def p_head_side(P):
    """头侧：上 2/3 是头发，下 1/3 是耳朵与脸颊。"""
    R = P.R
    w, h = R.w, R.h
    R.vgrad(HAIR, HAIR_MID)
    grain(R, (12, 10, 16), 17, 0.18)
    for xx in range(w):        # 发丝
        for yy in range(h):
            f = frac(xx, yy // 3, 21)
            if f > 0.72:
                R.blend(xx, yy, HAIR_HI, 0.5)
            elif f < 0.12:
                R.blend(xx, yy, (10, 8, 14), 0.6)
    cut = int(h * 0.62)
    for yy in range(cut, h):   # 脸颊/耳
        f = (yy - cut) / float(max(1, h - cut))
        col = tuple(int(SKIN[i] + (SKIN_COOL[i] - SKIN[i]) * f) for i in range(3))
        for xx in range(w):
            R.set(xx, yy, col)
    R.disc(w * 0.45, cut + 1, max(1.2, w * 0.2), SKIN_DEEP, 0.45, 1.0)   # 耳
    R.disc(w * 0.45, cut + 1, max(1.0, w * 0.12), (168, 138, 148), 0.5, 1.0)
    R.hline(cut, 0, w - 1, HAIR, 0.9)
    R.hline(cut + 1, 0, w - 1, HAIR_MID, 0.5)


def _hair(R, seed=5, tip_dark=True):
    R.vgrad(HAIR, HAIR_MID)
    grain(R, (12, 10, 16), seed, 0.20)
    for xx in range(R.w):
        for yy in range(R.h):
            f = frac(xx, yy // 3, seed + 3)
            if f > 0.70:
                R.blend(xx, yy, HAIR_HI, 0.55)
            elif f < 0.13:
                R.blend(xx, yy, (10, 8, 14), 0.6)
    # 高光带（发丝受光）
    hx = int(R.w * 0.34)
    for yy in range(R.h):
        wob = int(1.5 * (frac(yy, 0, seed + 11) - 0.5))
        R.blend(hx + wob, yy, HAIR_HI, 0.5)
        R.blend(hx + wob + 1, yy, HAIR_HI, 0.28)
    # 几根银丝
    for k in range(2):
        xs = int(R.w * (0.6 + 0.2 * k))
        for yy in range(R.h):
            if yh := (yy % 5 < 3):
                R.blend(xs, yy, HAIR_SIL, 0.5)
    if tip_dark:
        R.band(R.h - max(1, R.h // 4), max(1, R.h // 4), (12, 10, 18), 0.45)


def p_hair_back(P):
    _hair(P.R, 13)


def p_hair_top(P):
    _hair(P.R, 19, tip_dark=False)


def p_hair_fall(P):
    _hair(P.R, 29)


def p_hair_fall_tip(P):
    _hair(P.R, 37, tip_dark=False)
    R = P.R
    for xx in range(R.w):      # 发梢分叉
        f = xx / float(max(1, R.w - 1))
        cut = int(abs(f - 0.5) * R.h * 1.1)
        for yy in range(R.h - cut, R.h):
            R.blend(xx, yy, (0, 0, 0), 1.0)


def p_hair_fringe(P):
    _hair(P.R, 43, tip_dark=False)
    R = P.R
    R.band(0, max(1, R.h // 5), HAIR_HI, 0.35)
    R.band(R.h - 2, 2, (12, 10, 18), 0.7)


def p_hair_fringe_side(P):
    _hair(P.R, 47, tip_dark=False)
    R = P.R
    for xx in range(R.w):      # 鬓发斜下
        for yy in range(R.h):
            if frac(xx, yy, 51) > 0.5:
                R.blend(xx, yy, HAIR, 0.5)


def p_hair_side(P):
    _hair(P.R, 53, tip_dark=False)
    R = P.R
    for xx in range(R.w):
        f = xx / float(max(1, R.w - 1))
        cut = int(f * R.h * 0.75)
        for yy in range(cut, R.h):
            R.blend(xx, yy, (0, 0, 0), 1.0)


def p_hair_side_tip(P):
    _hair(P.R, 59, tip_dark=False)
    R = P.R
    for yy in range(R.h):        # 卷发尾：波浪
        wob = int(R.w * 0.25 * (1 + (1 if yy % 6 < 3 else -1)))
        for xx in range(R.w):
            if abs(xx - wob) > R.w * 0.55:
                R.blend(xx, yy, (0, 0, 0), 1.0)


def p_hair_bun(P):
    _hair(P.R, 61, tip_dark=False)
    R = P.R
    cx, cy = R.w * 0.5, R.h * 0.5
    for k in range(max(2, R.w // 2)):     # 盘发的螺旋
        ang = k * 0.9
        rr = (k / float(max(2, R.w // 2))) * min(R.w, R.h) * 0.55
        R.disc(cx + rr * 0.9 * (1 if k % 2 else -1) * 0.6, cy + rr * 0.35, max(1.0, R.w * 0.1),
               HAIR_HI, 0.25, 1.0)
        R.disc(cx - rr * 0.5, cy - rr * 0.3, max(1.0, R.w * 0.08), (12, 10, 18), 0.35, 1.0)


def p_hair_bun_top(P):
    _hair(P.R, 67, tip_dark=False)
    R = P.R
    R.disc(R.w * 0.5, R.h * 0.5, min(R.w, R.h) * 0.42, HAIR_HI, 0.3, 1.0)


def p_veil(P):
    """蕾丝面纱：网格 + alpha 镂空 + 扇形花边。"""
    R = P.R
    band = P.kwargs.get("band", 0)
    R.wipe((250, 246, 238, 0))     # 全透明起手
    step = 3 if band == 0 else 4
    for yy in range(R.h):
        for xx in range(R.w):
            keep = (xx % step != 0) and (yy % step != 0)
            if keep:
                a = 205 if (xx + yy) % 7 else 235
                R.set(xx, yy, (250, 246, 238, a))
            else:
                R.set(xx, yy, (250, 246, 238, 0))
    # 斜向网格线加亮
    for yy in range(R.h):
        for xx in range(R.w):
            if (xx + yy) % step == 1:
                R.blend(xx, yy, (255, 253, 248, 255), 0.4)
    # 上下压边
    if band == 0:
        R.band(0, 1, (240, 234, 226, 255), 0.9)
    else:
        R.band(R.h - 2, 2, (236, 230, 222, 255), 0.95)
        for xx in range(R.w):      # 扇形花边
            d = abs(((xx % 6) - 3))
            if d <= 1:
                R.set(xx, R.h - 2, (250, 246, 238, 0))
            R.set(xx, R.h - 1, (250, 246, 238, 230 if d <= 2 else 0))


def p_neck_lace(P):
    """领口蕾丝压边：白蕾丝 + 齿状边。"""
    R = P.R
    R.wipe(LACE)
    for yy in range(R.h):
        for xx in range(R.w):
            f = frac(xx, yy, 71)
            if f > 0.8:
                R.blend(xx, yy, LACE_SH, 0.6)
    R.band(0, 1, (255, 255, 250), 0.7)
    R.band(R.h - 1, 1, LACE_SH, 0.8)
    for xx in range(0, R.w, 2):
        R.set(xx, R.h - 1, LACE if xx % 4 == 0 else LACE_SH)


def p_cuff_lace(P):
    p_neck_lace(P)
    R = P.R
    R.band(0, max(1, R.h // 4), (255, 255, 252), 0.5)


def p_gold(P):
    R = P.R
    R.vgrad(GOLD_HI, GOLD_D)
    R.band(0, max(1, R.h // 4), GOLD_HI, 0.5)
    R.vline(max(1, R.w // 3), 0, R.h - 1, GOLD_HI, 0.5)
    grain(R, GOLD_D, 73, 0.15)


def p_gem(P):
    R = P.R
    R.wipe(GEM)
    R.vgrad(GEM_HI, GEM)
    R.disc(R.w * 0.35, R.h * 0.32, max(1.0, min(R.w, R.h) * 0.22), (255, 240, 248), 0.8)
    R.disc(R.w * 0.7, R.h * 0.72, max(1.0, min(R.w, R.h) * 0.18), (110, 40, 70), 0.6)


def p_gold_belt(P):
    p_gold(P)
    R = P.R
    for i in range(0, R.w, 4):
        R.disc(i + 2, R.h // 2, max(1.0, R.h * 0.18), GEM, 0.8)
    R.band(R.h - 1, 1, GOLD_D, 0.8)


def p_bow(P):
    R = P.R
    R.vgrad((176, 52, 60), (120, 26, 36))
    for xx in range(R.w):
        f = abs(xx / float(max(1, R.w - 1)) - 0.5) * 2
        for yy in range(R.h):
            R.blend(xx, yy, (60, 12, 20), 0.5 * f)
    R.hline(R.h // 2, 0, R.w - 1, (210, 96, 100), 0.4)
    R.hline(R.h // 2 + 1, 0, R.w - 1, (70, 14, 22), 0.4)
    grain(R, (90, 20, 28), 79, 0.15)


def p_bow_tail(P):
    R = P.R
    R.vgrad((168, 48, 56), (104, 22, 32))
    for xx in range(R.w):
        for yy in range(R.h):
            if frac(xx, yy // 2, 83) > 0.75:
                R.blend(xx, yy, (200, 92, 96), 0.35)
    R.band(R.h - 2, 2, (72, 16, 24), 0.6)


def p_sleeve(P):
    """袖子：缎面 + 几道褶。"""
    p_silk(P)
    R = P.R
    for i in range(1, 4):
        x = int(R.w * i / 4.0)
        R.vline(x, 1, R.h - 2, SILK_D, 0.35)
    R.band(R.h - 2, 2, CLOTH_D, 0.35)


def p_forearm_silk(P):
    p_sleeve(P)
    R = P.R
    R.band(0, 2, SILK_HI, 0.4)


def p_sleeve_puff(P):
    """泡泡袖：横向鼓起的明暗 + 上缘缝线。"""
    R = P.R
    R.vgrad(SILK_HI, SILK_SH)
    for yy in range(R.h):
        f = yy / float(max(1, R.h - 1))
        for xx in range(R.w):
            g = abs(xx / float(max(1, R.w - 1)) - 0.5) * 2
            sh = 0.5 * g + 0.4 * f
            R.blend(xx, yy, SILK_D, min(0.75, sh * 0.7))
    grain(R, SILK_D, 89, 0.12)
    R.band(0, 1, (255, 255, 250), 0.5)
    R.band(R.h - 2, 2, CLOTH_D, 0.4)
    for i in range(0, R.w, 3):
        R.blend(i, 1, SILK_D, 0.3)


def p_skirt_front(P):
    """前裙板：一道褶的缎面 + 中央刺绣 + 下摆蕾丝 + 血。"""
    p_silk(P)
    R = P.R
    # 刺绣：藤蔓 + 花
    cx = R.w // 2
    for yy in range(2, int(R.h * 0.72)):
        off = int(2.2 * (1 if (yy // 4) % 2 else -1))
        R.blend(cx + off, yy, GOLD_D, 0.55)
        if yy % 5 == 0:
            R.disc(cx + off + 2, yy, 1.0, GOLD_HI, 0.7)
    for k in range(3):
        yr = int(R.h * (0.16 + 0.26 * k))
        R.disc(cx + (4 if k % 2 else -4), yr, max(1.0, R.w * 0.07), GOLD, 0.6)
        R.disc(cx + (4 if k % 2 else -4), yr, max(1.0, R.w * 0.03), GOLD_HI, 0.8)
    R.band(R.h - max(2, int(R.h * 0.16)), max(2, int(R.h * 0.16)), LACE, 0.75)
    R.band(R.h - 1, 1, LACE_SH, 0.8)
    for i in range(2):
        x0 = int(R.w * (0.24 + 0.5 * i))
        top = int(R.h * (0.22 + 0.1 * i))
        for yy in range(top, R.h):
            a = 0.75 * (1.0 - (yy - top) / float(max(1, R.h - top)))
            R.blend(x0, yy, BLOOD, a)
            R.blend(x0 + 1, yy, BLOOD, a * 0.45)
        R.disc(x0, top, max(1.0, R.w * 0.07), BLOOD, 0.6)


def p_skirt_back(P):
    p_silk(P)
    R = P.R
    for i in range(1, 5):
        R.vline(int(R.w * i / 5.0), 1, R.h - 2, SILK_D, 0.3)
    R.band(R.h - max(2, int(R.h * 0.16)), max(2, int(R.h * 0.16)), LACE, 0.6)
    R.band(R.h - 1, 1, LACE_SH, 0.7)
    x0 = int(R.w * 0.3)
    for yy in range(int(R.h * 0.34), R.h):
        R.blend(x0, yy, BLOOD, 0.45 * (1.0 - (yy - int(R.h * 0.34)) / float(max(1, R.h)) * 0.6))
        R.blend(x0 + 1, yy, BLOOD, 0.2)
    R.disc(x0, int(R.h * 0.34), max(1.0, R.w * 0.08), BLOOD, 0.5)


def p_skirt_side(P):
    p_silk(P)
    R = P.R
    R.vline(int(R.w * 0.5), 0, R.h - 1, SILK_HI, 0.3)
    R.vline(int(R.w * 0.15), 0, R.h - 1, SILK_D, 0.35)
    R.vline(int(R.w * 0.85), 0, R.h - 1, SILK_D, 0.35)
    R.band(R.h - max(2, int(R.h * 0.16)), max(2, int(R.h * 0.16)), LACE, 0.6)
    R.band(R.h - 1, 1, LACE_SH, 0.7)


def p_skirt_corner(P):
    p_silk(P)
    R = P.R
    R.vline(1, 0, R.h - 1, SILK_D, 0.4)
    R.band(R.h - max(2, int(R.h * 0.14)), max(2, int(R.h * 0.14)), LACE, 0.5)
    for yy in range(R.h):        # 转角处的暗部
        R.blend(R.w - 1, yy, SILK_D, 0.4)


def p_stocking(P):
    R = P.R
    R.vgrad(STOCK, STOCK_SH)
    grain(R, STOCK_SH, 97, 0.10)
    for xx in range(0, R.w, 3):   # 蕾丝竖纹
        for yy in range(R.h):
            if frac(xx, yy, 101) > 0.6:
                R.blend(xx, yy, (255, 253, 248), 0.35)
    R.band(0, 2, (255, 255, 252), 0.4)


def p_shoe(P):
    """鞋：深红漆皮 + 高光 + 系带。"""
    R = P.R
    R.vgrad(SHOE_HI, SHOE)
    R.disc(R.w * 0.35, R.h * 0.3, max(1.0, min(R.w, R.h) * 0.3), (206, 130, 130), 0.4, 0.8)
    R.hline(int(R.h * 0.62), 0, R.w - 1, SEAM, 0.7)
    for xx in range(1, R.w - 1, 4):      # 系带
        R.vline(xx, int(R.h * 0.2), int(R.h * 0.55), (232, 216, 200), 0.5)
    R.band(R.h - 1, 1, SEAM, 0.8)


def p_sole(P):
    R = P.R
    R.wipe((58, 40, 44))
    grain(R, (30, 20, 24), 103, 0.2)
    R.band(R.h - 1, 1, (24, 16, 20), 0.8)


def p_heel(P):
    R = P.R
    R.vgrad((52, 34, 38), (30, 20, 24))
    R.vline(R.w // 2, 0, R.h - 1, (86, 60, 64), 0.5)


PAINTERS = {
    "skin": p_skin, "leg_skin": p_leg_skin, "neck_skin": p_neck_skin, "hand": p_hand,
    "silk": p_silk, "bodice_lower": p_bodice_lower, "bodice_belt": p_bodice_belt,
    "bodice_back": p_bodice_back, "bodice_back_low": p_bodice_back_low,
    "bodice_side": p_bodice_side, "bodice_strap": p_bodice_strap,
    "decollete": p_decollete, "neck_lace": p_neck_lace, "cuff_lace": p_cuff_lace,
    "bust_front": p_bust_front, "bust_edge": p_bust_edge, "bust_soft": p_bust_soft,
    "face_full": p_face, "head_side": p_head_side,
    "hair_back": p_hair_back, "hair_top": p_hair_top, "hair_fall": p_hair_fall,
    "hair_fall_tip": p_hair_fall_tip, "hair_fringe": p_hair_fringe,
    "hair_fringe_side": p_hair_fringe_side, "hair_side": p_hair_side,
    "hair_side_tip": p_hair_side_tip, "hair_bun": p_hair_bun, "hair_bun_top": p_hair_bun_top,
    "veil_lace": p_veil, "gold": p_gold, "gem": p_gem, "gold_belt": p_gold_belt,
    "bow": p_bow, "bow_tail": p_bow_tail, "sleeve": p_sleeve, "sleeve_puff": p_sleeve_puff,
    "forearm_silk": p_forearm_silk, "skirt_front": p_skirt_front, "skirt_back": p_skirt_back,
    "skirt_side": p_skirt_side, "skirt_corner": p_skirt_corner,
    "stocking": p_stocking, "shoe": p_shoe, "sole": p_sole, "heel": p_heel,
}


class Pctx:
    def __init__(self, canvas, m):
        self.c = canvas
        self.m = m
        self.R = Rect(canvas, tuple(m["rect"]), m["flip"])
        self.w, self.h = m["rect"][2], m["rect"][3]
        self.fw, self.fh = m["fw"], m["fh"]
        self.tpu = m["tpu"]
        self.face = m["face"]
        self.part = m["part"]
        self.kwargs = m["kwargs"]
        self.CUBE = None


def write_png(path, w, h, buf):
    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)
        raw += buf[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    return png


def main():
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    W, H = man["size"]
    canvas = Canvas(W, H)
    painted = [[False] * H for _ in range(W)]
    unknown = set()
    for m in man["faces"]:
        u, v, w, h = m["rect"]
        P = Pctx(canvas, m)
        name = m["painter"]
        if name.startswith("@"):
            p_flat(P, name[1:])
        else:
            fn = PAINTERS.get(name)
            if fn is None:
                unknown.add(name)
                p_flat(P, "silk_mid")
            else:
                import inspect
                ok_kw = {k: v for k, v in m["kwargs"].items()
                         if k in inspect.signature(fn).parameters}
                fn(P, **ok_kw)
        for yy in range(v, v + h):
            for xx in range(u, u + w):
                painted[yy][xx] = True
    # 边缘外扩 1px（防 MIP/过滤把相邻矩形渗进来；蕾丝镂空面尤其需要）
    for m in man["faces"]:
        u, v, w, h = m["rect"]
        for yy in range(v - 1, v + h + 1):
            for xx in range(u - 1, u + w + 1):
                if 0 <= xx < W and 0 <= yy < H and not painted[yy][xx]:
                    sx = min(max(xx, u), u + w - 1)
                    sy = min(max(yy, v), v + h - 1)
                    canvas.set(xx, yy, canvas.get(sx, sy))
                    painted[yy][xx] = True

    # 基础层强制不透明：双层皮肤只有覆盖层允许镂空，上半区一旦漏成透明就会在模型上开洞。
    # 兜底填内衬色并计数上报（数字应为 0；不为 0 说明某个基础层画家没画满）。
    op_fix = 0
    for m in man["faces"]:
        if m.get("layer", "base") != "base":
            continue
        u, v, w, h = m["rect"]
        for yy in range(v, v + h):
            for xx in range(u, u + w):
                if canvas.get(xx, yy)[3] == 0:
                    canvas.set(xx, yy, LINING)
                    op_fix += 1

    # 覆盖层镂空统计（可透气的像素：蕾丝孔、薄纱）
    holes = 0
    for m in man["faces"]:
        if m.get("layer", "base") != "overlay":
            continue
        u, v, w, h = m["rect"]
        for yy in range(v, v + h):
            for xx in range(u, u + w):
                if canvas.get(xx, yy)[3] == 0:
                    holes += 1

    unused = sum(1 for y in range(H) for x in range(W) if not painted[y][x])
    used = sum(1 for m in man["faces"] for _ in range(m["rect"][2] * m["rect"][3]))
    png = write_png(ART_TEX, W, H, canvas.buf)
    SRC_TEX.parent.mkdir(parents=True, exist_ok=True)
    SRC_TEX.write_bytes(png)
    a = hashlib.sha256(ART_TEX.read_bytes()).hexdigest()
    b = hashlib.sha256(SRC_TEX.read_bytes()).hexdigest()
    n_art = sum(1 for m in man["faces"] if not m["painter"].startswith("@"))
    print(f"贴图 {W}x{H}  作画矩形 {n_art} / 共享图元 {len(man['faces']) - n_art}")
    print(f"art : {ART_TEX}\n      sha256={a}")
    print(f"src : {SRC_TEX}\n      sha256={b}")
    print(f"art == src: {a == b}")
    print(f"矩形覆盖 {used} texels + 1px 外扩，剩余空白 {unused} texels（{unused / float(W * H) * 100:.1f}%，图集预留区）")
    nb = sum(1 for m in man["faces"] if m.get("layer") != "overlay")
    no = len(man["faces"]) - nb
    print(f"双层皮肤：基础层 {nb} 面（不透明，兜底补 {op_fix} px） / 覆盖层 {no} 面（其中 {holes} px 镂空可透气）")
    if op_fix:
        print(f"⚠ 基础层有 {op_fix} px 原本透明，已用内衬色补上——检查对应画家函数有没有画满")
    if unknown:
        print(f"未知画家（用了兜底）: {sorted(unknown)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())