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
HAIR = (146, 143, 170)          # #A9A6BC 灰紫发基色（比参考图压低一档：全图都在 0.75+ 亮度时模型会熔成一片白）
HAIR_HI = (178, 175, 200)       # #CCCAD6 发高光（原参考图基色）
HAIR_MID = (116, 113, 140)      # #8B88A4 发影
HAIR_SIL = (242, 240, 246)      # #F2F0F6 银白发丝
LACE = (255, 255, 255)          # #FFFFFF 蕾丝
LACE_SH = (220, 218, 228)       # #DCDAE4 蕾丝影
LIP = (244, 227, 239)           # #F4E3EF 唇（柔粉）
LIP_HI = (253, 244, 250)        # #FDF4FA 唇高光
TOOTH = (255, 255, 255)         # #FFFFFF
EYE_WHITE = (246, 236, 247)     # #F6ECF7 眼白
IRIS = (141, 137, 160)          # #8D89A0 灰紫瞳
IRIS_HI = (188, 197, 224)       # #BCC5E0 瞳高光
PUPIL = (108, 92, 126)           # #6C5C7E 瞳孔（仍是柔紫不用黑；旧值 133,116,149 与虹膜
                                 #   141,137,160 只差 21，眼睛里没有焦点 —— 高光也就跳不出来）
# 脸部专用的三个"能读出来"的颜色：
# 原来的 EYE_WHITE 与 SKIN 同值(246,236,247)、LIP 与肤色只差 2/9/8 —— 在 16×22 的脸上
# 等于没画（眼睛只剩两块紫、嘴只剩唇缝那条灰线）。这三个跟肤色拉开明度/彩度差。
SCLERA = (222, 218, 236)         # #DEDAEC 眼白（冷灰白：比肤色暗一档、比纯白暗得多，
                                 #   这样 1px 纯白高光压在它旁边才跳得出来；亡灵也用得上惨白眼白）
                                 #   注：别只暗一档就停 —— 232,229,242 与 SKIN 的色距只有 14，
                                 #   眼白会跟脸糊在一起、眼睛只剩虹膜那一条，轮廓不脆。
LASH = (88, 80, 106)             # #58506A 睫毛/眉毛（深冷紫，比 BLOOD_D 更沉）
LIP_ROSE = (214, 176, 196)       # #D6B0C4 唇（冷调玫瑰）
LIP_ROSE_D = (176, 136, 158)     # #B0889E 唇缝/唇角
LIP_ROSE_HI = (233, 205, 222)    # #E9CDDE 唇高光
BLUSH = (232, 196, 214)          # #E8C4D6 腮红（冷调粉）
BROW = (120, 112, 138)           # #78708A 眉（比睫毛浅一档，避免"两条黑杠"）
SOFT_SH = (224, 201, 216)        # #E0C9D8 暖调柔影（鼻梁/卧蚕/下唇投影）
SOFT_D = (208, 180, 198)         # #D0B4C6 暖调深影（鼻底/鼻翼）
# 注：SOFT_* 是为脸单独加的暖调影。原来这几处用 SKIN_SH / SKIN_DEEP（冷蓝灰）——
#     在淡紫白肤上叠出来的色距只有 ~8（低于可辨阈，等于没画），叠够了又读成"贴了块胶布"。
#     暖调影在同一基底上的色距是它的 3~4 倍，且与 LIP_ROSE / BLUSH 同族，不突兀。
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
        # 1 行高的面板（发冠 7x1 / 项圈 5x1 / 发簪 9x1 / 腰带 / 蝴蝶结 / 袜口 / 裙摆滚边）纵向没有轴：
        # 原实现 f = yy/max(1,h-1) 恒为 0 ⇒ 整条只落 col0 = **死色**（实测发冠 7x1 整条 #E8F6FF、
        # 蝴蝶结 3x1 整条 #C1D9F1）。这类面板把同一对颜色改沿**长度**铺开，金属/缎面才立得起来。
        if h == 1 and w > 1:
            for xx in range(w):
                f = xx / float(w - 1)
                col = tuple(int(col0[i] + (col1[i] - col0[i]) * f) for i in range(3))
                self.set(x + xx, y, col)
            return
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

def _stable_hash(s):
    """**别用内建 `hash()` 给字符串当种子**：CPython 的 str hash 每个进程带随机盐
    （PYTHONHASHSEED），于是同一份输入每跑一次出来的贴图都不一样 —— 实测同一个种子跑三遍
    三个哈希。差异落在共享补丁（`@lining`/`@cloth_dark` 这类 2×2）上，几十个像素，
    极易被误判成"面板写入顺序造成的混合微调"。这里的实现只依赖字符与其下标，跨进程稳定。
    """
    h = 0
    for i, ch in enumerate(s):
        h = (h * 131 + ord(ch) * (i + 1)) & 0xFFFFFFFF
    return h


def p_flat(P, sample):
    R = P.R
    base = {
        "lining": LINING, "cloth_dark": CLOTH_D, "cloth_top": CLOTH_T,
        "skin_dark": SKIN_DEEP, "hair_dark": (116, 113, 140), "silk_mid": (255, 249, 255),
    }[sample]
    R.wipe(base)
    R.noise((max(0, base[0] - 22), max(0, base[1] - 22), max(0, base[2] - 22)), _stable_hash(sample) & 0xFF, 0.10)


def grain(R, col, seed, amount=0.10):
    for yy in range(R.h):
        for xx in range(R.w):
            f = frac(xx, yy, seed)
            if f < amount:
                R.blend(xx, yy, col, (f / amount) * 0.35)


def p_skin(P):
    """体表皮肤：冷调象牙白 + 由上到下的明暗 + 淤青/血痕。"""
    R = P.R
    # 底渐变原本收在 SKIN_SH(233,227,239) —— 它与 SKIN 的色距上限只有 13（alpha 开到 1.0
    # 都到不了可辨阈），等于整块皮肤没有明暗、一体死白。改收在 SKIN_COOL(205,215,235)，
    # 距 SKIN_HI 48：这才真的画出"上亮下暗"。
    R.vgrad(SKIN_HI, SKIN_COOL)
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
        R.disc(R.w * 0.7, R.h * 0.66, max(1.0, R.w * 0.12), (116, 113, 140), 0.35)


def p_neck_skin(P):
    p_skin(P)
    R = P.R
    R.band(R.h - max(2, R.h // 4), max(2, R.h // 4), BLOOD, 0.55)   # 颈口血
    R.band(R.h - 2, 2, BLOOD_D, 0.7)


def p_hand(P):
    p_skin(P)
    R = P.R
    # 旧版用 `hline(h*i/4, SKIN_SH, 0.35)` 画"指缝" —— 两处都不成立：
    #   ① 手面板只有 1~2 行高（1x1 拇指 / 1x2 / 2x2 / 3x2），`h*i/4` 取整后落在同一行或越界；
    #   ② SKIN_SH 叠出来色距 ≤5，看不见。
    # 改成按行给 1px 可读的体块：上排=指节（亮），下排=掌下阴影（SKIN_COOL 距底 40+，看得见）。
    if R.h >= 2:
        R.band(R.h - 1, 1, SKIN_COOL, 0.45)          # 掌下阴影
    if R.h >= 3:
        R.hline(1, 0, R.w - 1, SKIN_COOL, 0.30)      # 指缝（仅够高的面板才有意义）
    R.band(0, 2, SKIN_HI, 0.4)
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
            R.blend(xx, yy, (253, 244, 246), 0.55)
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
    # 锁骨阴影：旧版是一枚 SKIN_SH 0.35 的 disc —— 色距 ≤5 看不见，而且半径按 w*0.08 算，
    # 在 7x3 的面板上半径=1、圆心落在 y=0.9，会**画到下面的缎面区**上变成一块蓝污。
    # 面板只有顶上 1 行是皮肤，改成贴着上缘的一道可读的横向浅影。
    R.hline(0, 1, R.w - 2, SKIN_COOL, 0.40)      # 颈根/锁骨浅影


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
    """脸：31×43 px 的正面板（tpu=18 ⇒ 6 px/u）。

    这一版重画的触发点是**分辨率被找回来了**：这块面板原来只有 16×22（tpu=9 ⇒ 3 px/u），
    下面那个按 16×22 硬边像素写的旧版就是在这块小画布上迭代了四轮 —— 逐行算到「哪一行放
    睫毛、哪一行放唇缝」。分辨率回到 31×43 之后，那套 22 行的布局不再需要，这一版按
    43 行重排，并把旧版四轮攒下的教训留在注释里（那些是像素级的硬约束，与尺寸无关）：

      * **色距要够**。旧版第一轮把 EYE_WHITE 定成与 SKIN 同值、LIP 与肤只差 2/9/8，
        结果「画了看不见」：眼白是浮着的紫块、嘴唇是一条灰胶布。本版所有五官色
        与肤色的色距都在 25 以上（SCLERA 差 24、LASH 差 130、LIP_ROSE 差 60）。
      * **低于可辨阈的叠色等于没画**。旧版 0.22 的卧蚕、0.35 的下巴影叠在淡紫白肤上
        色距只有 ~8，放大读作空白。本版凡是要读出来的结构，叠色都在 0.35 以上。
      * **下半脸不能空**。旧版下唇以下连着 4 行没信息。本版把下颌两角渐暗 + 下缘收暗
        一路铺到最后一列，把矩形面板「收」成鹅蛋颌。

    画法：先铺底与脸型，再把「左半边」的五官画好，最后整块镜像到右半边 —— 逐像素手描
    左右两只眼必然差一两像素，镜像一次就完全对称；不对称的痕迹（左嘴角那道淡血、右颊
    一点冷斑）在镜像之后单独补，且都压到原来的 1/3 强度：这一版的方向是「精致瓷白」，
    尸斑与疤只留痕迹，不留成主要视觉。
    """
    R = P.R
    w, h = R.w, R.h
    nx = w // 2
    # 暖调结构色：叠在淡紫白肤上必须有足够色距才读得出来。SKIN_SH/SKIN_HI 与肤色的差
    # 只有 13/7 —— 用它们画鼻梁、下颌，放大后就是「什么都没画」（旧版四轮里的第 1、3 条教训）。
    SOFT_SH = (214, 200, 214)      # 与肤差 ~30：结构影
    SOFT_D = (193, 176, 197)       # 与肤差 ~50：鼻孔、下颌线这类要读出来的线

    # ---- 底色与脸型 ----
    R.vgrad(SKIN_HI, SKIN)
    grain(R, (226, 220, 238), 5, 0.03)          # 极淡的颗粒：纯平面会读成塑料
    for xx in range(w):                         # 两侧收暗（脸型轮廓）
        g = abs(xx / float(max(1, w - 1)) - 0.5) * 2.0
        for yy in range(h):
            R.blend(xx, yy, SKIN_COOL, 0.34 * max(0.0, g - 0.34) / 0.66)
    R.band(0, max(2, h // 8), SKIN_HI, 0.32)                       # 额头受光
    for yy in range(int(h * 0.72), h):                              # 下颌：越往下越暗，收成鹅蛋
        f = (yy - h * 0.72) / max(1.0, h * 0.28)
        R.band(yy, 1, SKIN_COOL, 0.10 + 0.30 * f)
    R.band(h - 2, 2, SKIN_DEEP, 0.34)                               # 下缘收暗（下颌线）
    for y0, y1, a0 in ((int(h * 0.155), int(h * 0.30), 0.46),):      # 刘海投影
        span = max(1, y1 - y0)
        for yy in range(y0, y1):
            f = (yy - y0) / float(span - 1)
            R.band(yy, 1, (150, 148, 178), a0 * (1.0 - 0.85 * f))

    # ---- 左半边五官（x < nx）----
    # 眉：细长柔和拱形，中段最重（外重内淡是旧版踩过的反例），两端收到 1px
    bx0, bx1 = 3, 13
    for x in range(bx0, bx1 + 1):
        t = (x - bx0) / float(max(1, bx1 - bx0))
        y = int(h * 0.255) - int(2.4 * (1.0 - abs(t - 0.55) / 0.6) ** 1.3)    # 中段微拱
        a = 0.80 - 0.30 * (abs(t - 0.55) / 0.55) ** 1.6                       # 两端收淡
        R.blend(x, y, LASH, a)
        R.blend(x, y + 1, LASH, a * (0.55 if 0.18 < t < 0.9 else 0.28))       # 连成一条，不是断续的杠
    # 眼：外眼角上挑、上睫毛根根、双眼皮一道浅褶、卧蚕在下
    ex, ey = 8, 17
    R.disc(ex, ey, 3.6, (205, 215, 235), 0.08, 0.62)   # 眼窝淡影（大影会把眼睛读成淤青）
    for k in range(-3, 4):                       # 眼裂：外眼角（x 小）上挑
        x = ex + k
        lift = 1 if k <= -2 else 0
        R.blend(x, ey - 2 + lift, LASH, 0.92)
        if k <= -1:
            R.blend(x, ey - 1 + lift, LASH, 0.86)
        if k >= 3:
            R.blend(x, ey - 1, LASH, 0.55)
    for x in range(ex - 3, ex + 4):              # 眼白
        R.blend(x, ey, SCLERA, 0.95)
        R.blend(x, ey + 1, SCLERA, 0.88)
    R.blend(ex - 3, ey + 1, (233, 231, 244), 0.7)
    for x in range(ex - 1, ex + 3):              # 虹膜：外圈沉、中段亮、下缘反光 ⇒ 渐变
        R.blend(x, ey - 1, PUPIL, 0.85)
    R.disc(ex + 0.5, ey + 0.3, 2.1, IRIS, 0.96, 1.0)
    R.disc(ex + 0.6, ey + 1.0, 1.5, IRIS_HI, 0.55, 0.75)
    R.blend(ex, ey, PUPIL, 0.95)                 # 瞳孔
    R.blend(ex + 1, ey, PUPIL, 0.9)
    R.blend(ex, ey + 1, PUPIL, 0.8)
    R.set(ex - 1, ey - 1, (255, 255, 255))       # 主高光（左上一颗）
    R.blend(ex + 2, ey + 2, (250, 250, 255), 0.9)  # 副高光（右下一点）
    for k in range(-3, 4):                        # 下睫毛淡影
        R.blend(ex + k, ey + 2, (170, 165, 195), 0.30 * (1.0 - abs(k) / 4.0))
    for k in range(-3, 4):                        # 双眼皮浅褶
        R.blend(ex + k, ey - 3, (196, 186, 212), 0.42)
    # 眼影整块去掉：它落在眉与睫毛之间，放大后读作一道灰抹痕，得不偿失
    R.disc(ex, ey + 4.0, 3.0, LIP_ROSE_HI, 0.30, 0.55)     # 卧蚕：暖调，必须能读出来
    R.blend(ex, ey + 6, SKIN_COOL, 0.30)                   # 卧蚕下缘的影
    # 颧骨高光 + 腮红（都落在嘴以上）
    R.set(ex - 1, 22, (255, 252, 253))
    R.disc(7.0, 21.0, 2.4, LIP_ROSE_HI, 0.24, 0.75)
    # 额角：靠刘海投影的斜角收边，不再单独画碎发 —— 31px 宽的面板上那几根会读成浮块
    for yy in range(0, int(h * 0.16)):
        f = yy / float(max(1, int(h * 0.16)))
        for x in (0, 1):
            R.blend(x, yy, (150, 148, 178), 0.30 * (1.0 - f))
        for x in (2,):
            R.blend(x, yy, (176, 172, 198), 0.20 * (1.0 - f))

    # ---- 镜像到右半边 ----
    for yy in range(h):
        for xx in range(nx):
            R.set(w - 1 - xx, yy, R.get(xx, yy))

    # ---- 中线结构：鼻与唇（左右对称，镜像之后画）----
    ny = 27
    for yy in range(21, ny):                      # 鼻梁：中亮、两侧淡影（只走鼻子这一段）
        f = (yy - 21) / float(max(1, ny - 21))
        R.blend(nx, yy, SKIN_HI, 0.44 + 0.34 * f)
        R.blend(nx - 1, yy, SKIN_HI, 0.24 + 0.22 * f)
        R.blend(nx + 1, yy, SKIN_HI, 0.24 + 0.22 * f)
        R.blend(nx - 2, yy, SOFT_SH, 0.42 + 0.22 * f)
        R.blend(nx + 2, yy, SOFT_SH, 0.42 + 0.22 * f)
    for xx in range(nx - 2, nx + 3):              # 鼻头
        R.blend(xx, ny, SKIN_HI, 0.60)
    for xx in range(nx - 1, nx + 2):
        R.blend(xx, ny + 1, SOFT_D, 0.55)                             # 鼻底
    for sgn in (-1, 1):
        R.blend(nx + sgn * 2, ny + 1, SOFT_D, 0.82)                   # 鼻孔（要能一眼看到）
        R.blend(nx + sgn * 3, ny, SOFT_SH, 0.40)
        R.blend(nx + sgn * 3, ny + 1, SOFT_SH, 0.46)                  # 鼻翼
    # 唇：上唇两峰 + 唇珠、唇缝连到唇角、下唇中段亮、外围描一圈唇线
    ly = 33
    lw = 5
    for k in range(-lw, lw + 1):
        t = abs(k) / float(lw)
        dip = 1 if abs(k) in (1, 2) else 0        # 唇峰之间的浅凹
        R.blend(nx + k, ly - 2 + dip, LIP_ROSE, 0.92)                 # 上唇
        R.blend(nx + k, ly - 1 + dip, LIP_ROSE, 0.78)
        R.blend(nx + k, ly + 1, LIP_ROSE, 0.90)                       # 下唇
        R.blend(nx + k, ly + 2, LIP_ROSE_HI, 0.62 - 0.3 * t)          # 下唇受光
        R.blend(nx + k, ly + 3, (206, 200, 224), 0.40)                # 下唇投影（把嘴唇托起来）
    R.hline(ly, nx - lw + 1, nx + lw - 1, LIP_ROSE_D, 0.92)           # 唇缝
    R.set(nx, ly - 2, (255, 250, 253))                                # 唇珠（上唇中央一点亮）
    R.blend(nx, ly + 1, LIP_ROSE_HI, 0.55)
    for sgn in (-1, 1):                                               # 唇线：沿外缘描一圈
        for k in (lw, lw + 1):
            R.blend(nx + sgn * k, ly - 2, LIP_ROSE_D, 0.55)
            R.blend(nx + sgn * k, ly, LIP_ROSE_D, 0.60)
            R.blend(nx + sgn * k, ly + 1, LIP_ROSE_D, 0.45)
    R.blend(nx - lw, ly + 3, LIP_ROSE_D, 0.35)
    R.blend(nx + lw, ly + 3, LIP_ROSE_D, 0.35)

    # 下颌线：沿鹅蛋颌的边描一道浅线（这一条是「脸型」能读出来的关键，柔色叠不出来）
    for yy in range(int(h * 0.62), h - 2):
        f = (yy - h * 0.62) / max(1.0, h * 0.38)
        x = 1 + int(2.2 * f)
        R.blend(x, yy, SOFT_SH, 0.34 + 0.26 * f)
        R.blend(w - 1 - x, yy, SOFT_SH, 0.34 + 0.26 * f)

    # ---- 不对称痕迹（镜像之后补；强度压到旧版的 1/3，只留形不留势）----
    R.disc(w * 0.74, h * 0.70, 2.2, SKIN_DEEP, 0.12, 0.9)             # 右颌一点冷斑
    R.blend(nx - lw, ly + 4, BLOOD, 0.34)                             # 左嘴角一道极淡的血痕
    R.blend(nx - lw, ly + 5, BLOOD_D, 0.22)


def p_head_side(P):
    """头侧：上 2/3 是头发，下 1/3 是耳朵与脸颊。"""
    R = P.R
    w, h = R.w, R.h
    R.vgrad(HAIR, HAIR_MID)
    grain(R, (116, 113, 140), 17, 0.18)
    for xx in range(w):        # 发丝
        for yy in range(h):
            f = frac(xx, yy // 3, 21)
            if f > 0.72:
                R.blend(xx, yy, HAIR_HI, 0.5)
            elif f < 0.12:
                R.blend(xx, yy, (116, 113, 140), 0.6)
    cut = int(h * 0.62)
    for yy in range(cut, h):   # 脸颊/耳
        f = (yy - cut) / float(max(1, h - cut))
        col = tuple(int(SKIN[i] + (SKIN_COOL[i] - SKIN[i]) * f) for i in range(3))
        for xx in range(w):
            R.set(xx, yy, col)
    R.disc(w * 0.45, cut + 1, max(1.2, w * 0.2), SKIN_DEEP, 0.45, 1.0)   # 耳
    R.disc(w * 0.45, cut + 1, max(1.0, w * 0.12), (188, 197, 224), 0.5, 1.0)
    R.hline(cut, 0, w - 1, HAIR, 0.9)
    R.hline(cut + 1, 0, w - 1, HAIR_MID, 0.5)


def _hair(R, seed=5, tip_dark=True):
    R.vgrad(HAIR, HAIR_MID)
    grain(R, (116, 113, 140), seed, 0.20)
    for xx in range(R.w):
        for yy in range(R.h):
            f = frac(xx, yy // 3, seed + 3)
            if f > 0.70:
                R.blend(xx, yy, HAIR_HI, 0.55)
            elif f < 0.13:
                R.blend(xx, yy, (116, 113, 140), 0.6)
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
        R.band(R.h - max(1, R.h // 4), max(1, R.h // 4), (116, 113, 140), 0.45)


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
            R.blend(xx, yy, (122, 119, 148), 1.0)


def p_hair_fringe(P):
    _hair(P.R, 43, tip_dark=False)
    R = P.R
    R.band(0, max(1, R.h // 5), HAIR_HI, 0.35)
    R.band(R.h - 2, 2, (116, 113, 140), 0.7)


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
            R.blend(xx, yy, (122, 119, 148), 1.0)


def p_hair_side_tip(P):
    _hair(P.R, 59, tip_dark=False)
    R = P.R
    for yy in range(R.h):        # 卷发尾：波浪
        wob = int(R.w * 0.25 * (1 + (1 if yy % 6 < 3 else -1)))
        for xx in range(R.w):
            if abs(xx - wob) > R.w * 0.55:
                R.blend(xx, yy, (122, 119, 148), 1.0)


def p_hair_bun(P):
    _hair(P.R, 61, tip_dark=False)
    R = P.R
    cx, cy = R.w * 0.5, R.h * 0.5
    for k in range(max(2, R.w // 2)):     # 盘发的螺旋
        ang = k * 0.9
        rr = (k / float(max(2, R.w // 2))) * min(R.w, R.h) * 0.55
        R.disc(cx + rr * 0.9 * (1 if k % 2 else -1) * 0.6, cy + rr * 0.35, max(1.0, R.w * 0.1),
               HAIR_HI, 0.25, 1.0)
        R.disc(cx - rr * 0.5, cy - rr * 0.3, max(1.0, R.w * 0.08), (116, 113, 140), 0.35, 1.0)


def p_hair_bun_top(P):
    _hair(P.R, 67, tip_dark=False)
    R = P.R
    R.disc(R.w * 0.5, R.h * 0.5, min(R.w, R.h) * 0.42, HAIR_HI, 0.3, 1.0)


def _veil_blood(R, band, lift=0.0):
    """把血渍叠到面纱的**已有着色像素**上：镂空处不染，血跟着纱走。

    <p>这是「血纱」这个名字本身：头纱若一点血都没有，四段就只是四张白网。
    血的流向按「越往下越重」分档（顶段 0.20 → 中段 0.38 → 底段 0.58），
    随机相位取图集坐标 `R.u/R.v` ⇒ 四段共用同一条流向、浓淡各不相同，
    且跨次运行稳定（用 `frac` 而不是 `random`）。</p>

    <p>一律用 `blend` 半透明叠加而不是 `set` 实心覆盖：网眼织纹要能透出来，
    读数才是「染了血的纱」而不是「贴了块灰布」。</p>
    """
    base = {0: 0.20, 1: 0.58, 2: 0.38}.get(band, 0.38) + lift
    seed = (R.u * 7 + R.v * 13) & 0xFFFF
    for yy in range(R.h):
        t = yy / float(max(1, R.h - 1))
        weight = base * (0.55 + 0.45 * t)
        for xx in range(R.w):
            if R.get(xx, yy)[3] == 0:
                continue                       # 镂空处不上色：血要跟着纱走
            f = frac(xx * 2 + seed, yy * 7 + seed, 23)
            if f < weight:
                R.blend(xx, yy, BLOOD, 0.30 + 0.50 * (f / max(1e-6, weight)))
            elif f < weight + 0.20:
                # 血渍边缘的一圈渗色：没有它，血斑边界是刀切的圆
                R.blend(xx, yy, BLOOD, 0.16)


def p_veil(P):
    """蕾丝面纱（4 段布料链）：网格 + alpha 镂空 + 扇形花边 + 血纱。

    `band` 分档，对应四段的不同位置 —— 原来只有 2 段（0/1），现在中间两段要 `band=2`：
      0 = 顶段（带一道实边 + 一排珠饰，贴着发髻；血从这里往下淌）
      1 = 底段（带扇形花边 + 缝线；血最重，颜色也最沉）
      2 = 中间段（**纯网格**，任何压边都不能加，否则四段会各长出一圈花边）
    """
    R = P.R
    band = P.kwargs.get("band", 0)
    if min(R.w, R.h) <= 2:
        # 面纱的**侧边/厚度窄条**（e/w 面，1~2px 宽）装不下 4px 网眼：`xx % step != 0`
        # 对 1px 宽的面恒为假 ⇒ 整块镂空成洞（轮廓上出现能看穿的缝）。窄条改铺半透明白纱。
        R.wipe((255, 255, 255, 205))
        for yy in range(R.h):
            for xx in range(R.w):
                if (xx + yy) % 3 == 0:
                    R.set(xx, yy, (255, 251, 254, 240))
        # 窄条也要有上下明暗：一条恒定 205 的alpha 在侧视里是块灰板，读不出"纱的厚度"
        for yy in range(R.h):
            R.blend(0, yy, SILK_D, 0.10 + 0.30 * (yy / float(max(1, R.h - 1))))
        _veil_blood(R, band, lift=0.10)
        return
    R.wipe((255, 255, 255, 0))     # 全透明起手
    step = 3 if band == 0 else 4
    for yy in range(R.h):
        for xx in range(R.w):
            keep = (xx % step != 0) and (yy % step != 0)
            if keep:
                a = 205 if (xx + yy) % 7 else 235
                R.set(xx, yy, (255, 255, 255, a))
            else:
                R.set(xx, yy, (255, 255, 255, 0))
    # 斜向网格线加亮
    for yy in range(R.h):
        for xx in range(R.w):
            if (xx + yy) % step == 1:
                R.blend(xx, yy, (255, 253, 248, 255), 0.4)
    # 纱面织纹：纱不是纯白纸。只落在不透明处，且越靠下越沉（受重力，纱在下面堆得厚）
    for yy in range(R.h):
        for xx in range(R.w):
            if R.get(xx, yy)[3] > 0:
                f = frac(xx * 3 + R.u, yy * 5 + R.v, 11)
                if f < 0.32:
                    R.blend(xx, yy, SILK_SH, 0.14 + 0.20 * f + 0.18 * (yy / float(max(1, R.h - 1))))
    _veil_blood(R, band)
    # 上下压边
    if band == 0:
        R.band(0, 1, (255, 249, 255, 255), 0.9)
        # 发髻那一侧的珠饰：一排 1px 高光 + 间隔的暗点，让"压边"不是一条白线
        for xx in range(0, R.w, 3):
            R.set(xx, 0, (255, 255, 255, 255))
        for xx in range(1, R.w, 3):
            R.blend(xx, 0, SILK_D, 0.45)
    elif band == 1:
        R.band(R.h - 2, 2, (255, 249, 255, 255), 0.95)
        for xx in range(R.w):      # 扇形花边
            d = abs(((xx % 6) - 3))
            if d <= 1:
                R.set(xx, R.h - 2, (255, 255, 255, 0))
            R.set(xx, R.h - 1, (255, 255, 255, 230 if d <= 2 else 0))
        # 花边上方一道缝线：扇形不是凭空长在纱上的
        for xx in range(R.w):
            if (xx + R.u) % 2 == 0:
                R.blend(xx, R.h - 3, SILK_D, 0.5)


def p_neck_lace(P):
    """领口蕾丝压边：白蕾丝 + 齿状边。"""
    R = P.R
    R.wipe(LACE)
    for yy in range(R.h):
        for xx in range(R.w):
            f = frac(xx, yy, 71)
            if f > 0.8:
                R.blend(xx, yy, LACE_SH, 0.6)
    R.band(0, 1, (255, 255, 255), 0.7)
    R.band(R.h - 1, 1, LACE_SH, 0.8)
    for xx in range(0, R.w, 2):
        R.set(xx, R.h - 1, LACE if xx % 4 == 0 else LACE_SH)


def p_cuff_lace(P):
    p_neck_lace(P)
    R = P.R
    R.band(0, max(1, R.h // 4), (255, 255, 255), 0.5)


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
    R.disc(R.w * 0.35, R.h * 0.32, max(1.0, min(R.w, R.h) * 0.22), (232, 246, 255), 0.8)
    R.disc(R.w * 0.7, R.h * 0.72, max(1.0, min(R.w, R.h) * 0.18), (205, 231, 247), 0.6)


def p_gold_belt(P):
    p_gold(P)
    R = P.R
    for i in range(0, R.w, 4):
        R.disc(i + 2, R.h // 2, max(1.0, R.h * 0.18), GEM, 0.8)
    R.band(R.h - 1, 1, GOLD_D, 0.8)


def p_bow(P):
    R = P.R
    R.vgrad((168, 198, 232), (205, 231, 247))
    for xx in range(R.w):
        f = abs(xx / float(max(1, R.w - 1)) - 0.5) * 2
        for yy in range(R.h):
            R.blend(xx, yy, (168, 198, 232), 0.5 * f)
    R.hline(R.h // 2, 0, R.w - 1, (232, 246, 255), 0.4)
    R.hline(R.h // 2 + 1, 0, R.w - 1, (205, 231, 247), 0.4)
    grain(R, (205, 231, 247), 79, 0.15)


def p_bow_tail(P):
    R = P.R
    R.vgrad((168, 198, 232), (205, 231, 247))
    for xx in range(R.w):
        for yy in range(R.h):
            if frac(xx, yy // 2, 83) > 0.75:
                R.blend(xx, yy, (232, 246, 255), 0.35)
    R.band(R.h - 2, 2, (168, 198, 232), 0.6)


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
    R.band(0, 1, (255, 255, 255), 0.5)
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
                R.blend(xx, yy, (255, 255, 255), 0.35)
    R.band(0, 2, (255, 255, 255), 0.4)


def p_shoe(P):
    """鞋：深红漆皮 + 高光 + 系带。"""
    R = P.R
    R.vgrad(SHOE_HI, SHOE)
    R.disc(R.w * 0.35, R.h * 0.3, max(1.0, min(R.w, R.h) * 0.3), (205, 231, 247), 0.4, 0.8)
    R.hline(int(R.h * 0.62), 0, R.w - 1, SEAM, 0.7)
    for xx in range(1, R.w - 1, 4):      # 系带
        R.vline(xx, int(R.h * 0.2), int(R.h * 0.55), (253, 244, 246), 0.5)
    R.band(R.h - 1, 1, SEAM, 0.8)


def p_sole(P):
    R = P.R
    R.wipe((122, 119, 148))
    grain(R, (122, 119, 148), 103, 0.2)
    R.band(R.h - 1, 1, (122, 119, 148), 0.8)


def p_heel(P):
    R = P.R
    R.vgrad((116, 113, 140), (122, 119, 148))
    R.vline(R.w // 2, 0, R.h - 1, (188, 197, 224), 0.5)


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