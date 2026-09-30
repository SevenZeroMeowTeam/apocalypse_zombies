#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""尸潮之主贴图生成器 —— 读 art/boss/boss_atlas.json，画出 512×512 的 horde_overlord.png。

管线位置：tools/boss_v1.py（几何/骨骼/动画/图集清单） → 本脚本（贴图） → Blockbench 校验。

复用 tools/bride_v2_skin.py 的通用底座（Canvas / Rect / Pctx / write_png / 噪声），
但调色板与 33 个画家函数全部独立：Boss 是骨白 + 锈铁 + 凝血 + 魂火青，
和美女僵尸那套冷调象牙白礼服没有任何共用色块。

纯标准库（zlib + struct）手写 PNG，保证可重复：同一份清单两次运行 sha256 完全一致。
"""

import hashlib
import json
import pathlib
import sys

# 通用底座直接复用：Canvas / Rect / Pctx / write_png / frac / grain / _stable_hash
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from bride_v2_skin import Canvas, Pctx, frac, grain, write_png  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = ROOT / "art" / "boss"
MANIFEST = ART / "boss_atlas.json"
ART_TEX = ART / "horde_overlord.png"
SRC_TEX = (ROOT / "src/main/resources/assets/apocalypse_zombies"
           / "textures/entity/horde_overlord.png")

# ---------------------------------------------------------------------------
# 调色板 —— 尸潮之主
# ---------------------------------------------------------------------------
# 四族色：骨（冠/角/爪/牙/颅）、腐肉（体表）、锈铁（甲/笼/斧/靴）、凝血与魂火（点缀）。
# 每族内部至少留 60 的明度跨度（BONE_HI 233 → BONE_D 124），
# 否则在 2px/u 的躯干上叠出来的全是"同一个灰"—— 这是本项目贴图最常见的失败模式。

BONE = (206, 198, 176)          # #CEC6B0 骨基色（旧象牙，不是纯白：Boss 该有年头）
BONE_HI = (233, 227, 207)       # #E9E3CF 骨高光
BONE_SH = (168, 160, 136)       # #A8A088 骨影
BONE_D = (124, 116, 96)         # #7C7460 骨深影 / 骨缝
BONE_STAIN = (156, 142, 118)    # #9C8E76 陈年污渍（铁锈渗进骨头的那种黄褐）

HIDE = (96, 108, 86)            # #606C56 腐肉基色（尸绿灰）
HIDE_HI = (124, 136, 106)       # #7C886A 腐肉高光
HIDE_SH = (68, 78, 60)          # #444E3C 腐肉影
HIDE_D = (44, 52, 40)           # #2C3428 腐肉深影
HIDE_BRUISE = (78, 62, 74)      # #4E3E4A 瘀斑（紫调，和尸绿拉开色相）

SINEW = (118, 58, 52)           # #763A34 肌肉基色
SINEW_HI = (150, 80, 68)        # #965044 肌肉高光
SINEW_D = (72, 32, 30)          # #48201E 肌肉深影

IRON = (78, 82, 90)             # #4E525A 锈铁基色
IRON_HI = (118, 124, 134)       # #767C86 铁高光
IRON_D = (46, 50, 58)           # #2E323A 铁深影
IRON_EDGE = (156, 162, 172)     # #9CA2AC 磨亮的刃口
RUST = (128, 78, 50)            # #804E32 锈
RUST_D = (92, 54, 34)           # #5C3622 深锈

BLOOD = (128, 24, 30)           # #80181E 凝血
BLOOD_D = (80, 14, 20)          # #500E14 干血
BLOOD_HI = (176, 48, 52)        # #B03034 鲜血

SOUL_CORE = (255, 255, 255)     # #FFFFFF 魂火芯（1px，超过 1px 就糊成一坨白）
SOUL_HI = (206, 255, 234)       # #CEFFEA 魂火高光
SOUL = (118, 238, 196)          # #76EEC4 魂火（尸笼/眼窝的自发光）
SOUL_D = (56, 152, 124)         # #38987C 魂火影
SOUL_VOID = (22, 46, 42)        # #162E2A 魂火外的暗部

CLOTH = (52, 44, 52)            # #342C34 破布基色（披风）
CLOTH_HI = (80, 70, 80)         # #504650 布高光
CLOTH_D = (30, 26, 32)          # #1E1A20 布影
CLOTH_EDGE = (16, 14, 18)       # #100E12 布缘（破口/缝线）
LINING = (54, 48, 46)           # #36302E 内衬（Boss 的内壁走暗褐，不走新娘的淡紫）
CLOTH_DARK = (38, 34, 38)       # #262226 暗布（共享图元 @cloth_dark）

EYE_VOID = (20, 18, 22)         # #141216 眼窝底


# ---------------------------------------------------------------------------
# 通用底纹
# ---------------------------------------------------------------------------

def bone_base(R, seed):
    """骨架底：上亮下暗 + 污渍斑 + 骨缝裂纹。骨冠/角/爪/牙/颅共用。"""
    R.vgrad(BONE_HI, BONE_SH)
    grain(R, BONE_STAIN, seed, 0.22)
    # 陈年污渍：两三块不规则黄褐斑，位置由种子决定
    for i in range(2 + (seed % 2)):
        cx = (frac(i, seed, 3) * 0.8 + 0.1) * R.w
        cy = (frac(i, seed, 5) * 0.8 + 0.1) * R.h
        R.disc(cx, cy, max(1.4, min(R.w, R.h) * 0.22), BONE_STAIN, 0.30, 0.75)
    R.band(R.h - max(1, R.h // 5), max(1, R.h // 5), BONE_D, 0.22)


def hide_base(R, seed):
    """腐肉底：尸绿渐变 + 瘀斑 + 毛孔噪声。躯干/四肢/手/腿共用。"""
    R.vgrad(HIDE_HI, HIDE_SH)
    grain(R, HIDE_D, seed, 0.26)
    for i in range(2 + (seed % 3)):
        cx = frac(i, seed, 11) * R.w
        cy = frac(i, seed, 13) * R.h
        R.disc(cx, cy, max(1.0, min(R.w, R.h) * 0.24), HIDE_BRUISE, 0.34, 0.8)
    R.band(R.h - max(1, R.h // 6), max(1, R.h // 6), HIDE_D, 0.28)


def iron_base(R, seed, horizontal=True):
    """锈铁底：先铺满一层铁，再叠拉丝 / 铆钉 / 磨亮的边。

    `wipe` 是必须的第一笔：本文件里所有 `band` / `col_band` / `grain` 走的都是 blend
    （只按 alpha 混色），对透明像素等于什么都没做 —— 少了这一笔，甲片会带一片镂空，
    模型上直接看穿过去（实测 plate_chest 18×14 里漏 86px）。
    """
    R.wipe(IRON)
    R.vgrad(IRON_HI, IRON_D)
    if horizontal:
        R.band(R.h - max(1, R.h // 4), max(1, R.h // 4), IRON_D, 0.42)
    else:
        R.col_band(0, max(1, R.w // 4), IRON_HI, 0.28)
        R.col_band(R.w - max(1, R.w // 4), max(1, R.w // 4), IRON_D, 0.40)
    grain(R, IRON_D, seed, 0.20)
    grain(R, RUST, seed + 3, 0.10)


def rivets(R, count, col_hi=IRON_EDGE, col_sh=IRON_D):
    """沿上下缘打一圈铆钉：1px 亮 + 1px 暗，读起来就是"金属件"。"""
    if R.w < 4 or R.h < 4:
        return
    step = max(2, R.w // max(1, count))
    for x in range(1, R.w - 1, step):
        R.blend(x, 1, col_hi, 0.85)
        R.blend(x, 2, col_sh, 0.6)
        if R.h > 6:
            R.blend(x, R.h - 2, col_hi, 0.5)
            R.blend(x, R.h - 3, col_sh, 0.6)


def cracks(R, seed, col, n=3, length=None):
    """从随机点向下斜向裂开：每步 x 抖动，读起来像骨裂/铁裂。"""
    length = length or max(2, R.h // 3)
    for i in range(n):
        x = int(frac(i, seed, 17) * (R.w - 1))
        y = int(frac(i, seed, 19) * max(1, R.h // 3))
        for step in range(length):
            if not (0 <= x < R.w and 0 <= y + step < R.h):
                break
            R.blend(x, y + step, col, 0.7)
            if frac(x, y + step, seed + i) < 0.4:
                x += 1 if frac(x, y, seed + 7) < 0.5 else -1


# ---------------------------------------------------------------------------
# 体表：腐肉
# ---------------------------------------------------------------------------

def p_hide_front(P):
    """躯干正面：腐肉 + 胸口一道旧伤（Boss 正面要有"被开过膛"的信息）。"""
    R = P.R
    hide_base(R, 31)
    # 肋骨压痕：几条横向暗带，从中间往两侧收
    for i in range(1, 3):
        y = int(R.h * (0.35 + 0.18 * i))
        if y < R.h:
            R.hline(y, max(1, R.w // 6), min(R.w - 2, R.w - R.w // 6), HIDE_D, 0.35)
    # 旧伤：一道从上到下的缝合痕，两侧血渍
    x = R.w // 2
    R.vline(x, 0, R.h - 1, BLOOD_D, 0.55)
    R.col_band(max(0, x - 1), 1, BLOOD, 0.30)
    for y in range(1, R.h - 1, 3):
        R.blend(x + 2, y, BONE, 0.55)
        R.blend(x - 2, y, BONE, 0.55)


def p_hide_back(P):
    """躯干背面：腐肉 + 脊椎突起（一排骨节从背部顶出来）。"""
    R = P.R
    hide_base(R, 37)
    x = R.w // 2
    for y in range(0, R.h, 3):
        R.disc(x, y, max(1.0, R.w * 0.12), BONE_SH, 0.75, 0.9)
        R.blend(x, y, BONE_HI, 0.7)
    R.col_band(max(0, x - 1), 2, HIDE_D, 0.22)


def p_hide_side(P):
    """体侧：腐肉 + 静脉（青紫血管沿纵向爬）。"""
    R = P.R
    hide_base(R, 41)
    for i in range(2):
        x = int(R.w * (0.25 + 0.4 * i))
        for y in range(R.h):
            xx = x + int(1.5 * frac(y, i, 23))
            if 0 <= xx < R.w:
                R.blend(xx, y, HIDE_BRUISE, 0.5)
    R.band(0, max(1, R.h // 5), HIDE_HI, 0.25)


def p_hide_hand(P):
    """手掌：腐肉 + 指节（面板很小，只留最高性价比的两笔）。"""
    R = P.R
    hide_base(R, 43)
    if R.h >= 3:
        R.hline(R.h // 2, 0, R.w - 1, HIDE_D, 0.4)
    R.band(0, max(1, R.h // 3), HIDE_HI, 0.35)
    R.disc(R.w * 0.7, R.h * 0.6, max(1.0, R.w * 0.2), BLOOD, 0.30)


def p_hide_leg(P):
    """腿：腐肉 + 底部凝血（拖在地上的那截）。"""
    R = P.R
    hide_base(R, 47)
    R.band(R.h - max(1, R.h // 3), max(1, R.h // 3), BLOOD_D, 0.30)
    R.band(R.h - 1, 1, BLOOD_D, 0.7)
    for i in range(2):
        y = int(R.h * (0.3 + 0.3 * i))
        if y < R.h:
            R.hline(y, 0, R.w - 1, HIDE_D, 0.30)


def p_muscle(P):
    """裸露的肌肉束：纵向纤维 + 血膜。手臂/前臂用。"""
    R = P.R
    R.vgrad(SINEW_HI, SINEW_D)
    # 纤维：每 2px 一组（亮线 + 暗线），沿纵向
    for x in range(0, R.w, 2):
        R.col_band(x, 1, SINEW_HI, 0.45)
        if x + 1 < R.w:
            R.col_band(x + 1, 1, SINEW_D, 0.40)
    grain(R, SINEW_D, 53, 0.20)
    R.band(0, max(1, R.h // 6), BLOOD, 0.25)


# ---------------------------------------------------------------------------
# 骨架件：颅 / 冠 / 角 / 爪 / 牙
# ---------------------------------------------------------------------------

def p_skull_top(P):
    """颅顶：骨 + 颅缝（两条纵向锯齿缝）。"""
    R = P.R
    bone_base(R, 59)
    for x in (R.w // 3, (2 * R.w) // 3):
        for y in range(R.h):
            xx = x + int(frac(y, x, 29) * 2) - 1
            if 0 <= xx < R.w:
                R.blend(xx, y, BONE_D, 0.65)
    R.band(0, max(1, R.h // 4), BONE_HI, 0.30)


def p_skull_side(P):
    """颞侧：骨 + 太阳穴凹陷 + 一道裂纹。"""
    R = P.R
    bone_base(R, 61)
    R.disc(R.w * 0.35, R.h * 0.45, max(1.5, min(R.w, R.h) * 0.26), BONE_D, 0.32, 1.1)
    cracks(R, 61, BONE_D, 2, max(3, R.h // 3))
    R.band(R.h - max(1, R.h // 4), max(1, R.h // 4), BONE_SH, 0.30)


def p_skull_back(P):
    """枕骨：骨 + 枕骨大孔（一枚暗洞）。"""
    R = P.R
    bone_base(R, 67)
    R.disc(R.w * 0.5, R.h * 0.62, max(1.5, min(R.w, R.h) * 0.22), BONE_D, 0.7, 0.9)
    R.disc(R.w * 0.5, R.h * 0.62, max(1.0, min(R.w, R.h) * 0.12), EYE_VOID, 0.85, 0.9)


def p_skull_ridge(P):
    """颅脊：一条凸起的骨棱（中间亮、两侧塌）。"""
    R = P.R
    bone_base(R, 71)
    cx = R.w // 2
    for y in range(R.h):
        R.blend(cx, y, BONE_HI, 0.85)
        if cx + 1 < R.w:
            R.blend(cx + 1, y, BONE_SH, 0.55)
        if cx - 1 >= 0:
            R.blend(cx - 1, y, BONE_SH, 0.45)


def p_crown(P):
    """骨冠：骨座 + 铁箍 + 魂火宝石（冠上的亮点就是这只 Boss 的"眼睛"）。"""
    R = P.R
    bone_base(R, 73)
    # 下缘铁箍
    hb = max(1, R.h // 3)
    R.band(R.h - hb, hb, IRON, 0.85)
    R.band(R.h - hb, 1, IRON_HI, 0.7)
    # 骨冠尖：上缘一排亮齿
    for x in range(0, R.w, max(2, R.w // 8)):
        R.vline(x, 0, max(0, R.h // 2), BONE_HI, 0.5)
    # 魂火宝石：隔一段嵌一颗
    step = max(3, R.w // 3)
    for x in range(step // 2, R.w, step):
        y = max(0, R.h - hb - 2)
        R.disc(x, y, 1, SOUL, 0.9, 1.0)
        R.blend(x, y, SOUL_CORE, 0.9)
        R.blend(x, y + 1, SOUL_D, 0.6)


def p_horn(P):
    """角：根部暗、梢部亮 + 环纹（面板很矮，用横向环线表达年轮）。"""
    R = P.R
    R.vgrad(BONE_D, BONE_HI)
    for y in range(R.h):
        if y % 2 == 0:
            R.band(y, 1, BONE_SH, 0.35)
    R.band(0, max(1, R.h // 3), BONE_D, 0.35)
    R.band(R.h - 1, 1, BONE_HI, 0.6)     # 梢部磨亮


def p_claw(P):
    """爪：骨锥 —— 底暗、尖亮、尖上带血。"""
    R = P.R
    R.vgrad(BONE_SH, BONE_HI)
    R.band(0, max(1, R.h // 3), BONE_D, 0.5)
    # 中轴高光（锥体的棱）
    R.col_band(R.w // 2, 1, BONE_HI, 0.8)
    R.band(R.h - 1, 1, BLOOD, 0.55)
    grain(R, BONE_STAIN, 79, 0.18)


def p_teeth(P):
    """牙：暗红牙床 + 一排骨牙（面板只有几 px 高，靠明暗交替读齿）。"""
    R = P.R
    R.wipe(BLOOD_D)
    grain(R, BLOOD, 83, 0.25)
    if R.h >= 2:
        R.band(R.h - max(1, R.h // 2), max(1, R.h // 2), BONE, 0.9)
        for x in range(0, R.w, 2):
            R.col_band(x, 1, BONE_HI, 0.85)
            if x + 1 < R.w:
                R.col_band(x + 1, 1, BONE_SH, 0.7)
    else:
        for x in range(0, R.w, 2):
            R.blend(x, 0, BONE_HI, 0.9)


def p_jaw(P):
    """下颌：腐肉 + 下缘一排牙（张合靠骨骼旋转，牙齿本身画在颌上）。"""
    R = P.R
    hide_base(R, 89)
    if R.h >= 2:
        R.band(R.h - 2, 2, BLOOD_D, 0.45)
        for x in range(0, R.w, 2):
            R.blend(x, R.h - 1, BONE_HI, 0.9)
            R.blend(x, R.h - 2, BONE, 0.6)
    R.band(0, 1, HIDE_HI, 0.4)


# ---------------------------------------------------------------------------
# 脸：唯一需要"读得出五官"的面板（4px/u，25×34 texels）
# ---------------------------------------------------------------------------

def p_face(P):
    """头骨正脸。

    这一块是整个模型的信息中心：眼窝里的魂火、鼻腔的暗三角、咬合齿列。
    面板 25×34 texel（4px/u）—— 五官按比例落位，不做像素级描线（4px/u 下描线会糊）。
    前切角（head_fe / head_fw，1.2u 宽）宽度不足，走 {@link #_face_bevel} 的侧面画法。
    """
    R = P.R
    if R.w < 12:
        return _face_bevel(P)

    W, H = R.w, R.h
    # --- 底：颅骨（上亮下暗，眉骨处压一道影）
    bone_base(R, 97)
    R.band(int(H * 0.16), max(1, int(H * 0.08)), BONE_SH, 0.45)   # 眉骨下影

    # --- 眼窝：两个大空洞，内嵌魂火
    eye_w = max(2, int(W * 0.24))
    eye_h = max(2, int(H * 0.18))
    eye_y = int(H * 0.30)
    for x0 in (int(W * 0.16), int(W * 0.60)):
        R.fill(x0, eye_y, eye_w, eye_h, EYE_VOID)
        # 魂火：下暗上亮，芯 1px 白
        R.fill(x0 + 1, eye_y + 1, max(1, eye_w - 2), max(1, eye_h - 2), SOUL_D)
        R.fill(x0 + 1, eye_y + 1, max(1, eye_w - 2), max(1, (eye_h - 2) // 2 + 1), SOUL)
        R.blend(x0 + eye_w // 2, eye_y + 1, SOUL_CORE, 1.0)
    # 眼眶上缘的骨棱高光（让眼窝"陷进去"）
    for x0 in (int(W * 0.16), int(W * 0.60)):
        R.hline(eye_y - 1, x0, x0 + eye_w - 1, BONE_HI, 0.75)
        R.hline(eye_y + eye_h, x0, x0 + eye_w - 1, BONE_D, 0.6)

    # --- 鼻腔：倒三角暗洞
    nose_y = eye_y + eye_h + max(1, int(H * 0.04))
    nose_h = max(2, int(H * 0.14))
    for i in range(nose_h):
        half = max(0, int(nose_w := (W * 0.07)) * (nose_h - i) // max(1, nose_h))
        cx = W // 2
        R.fill(cx - half, nose_y + i, max(1, half * 2 + 1), 1, EYE_VOID)

    # --- 齿列：上排 + 下排，中间一条咬合暗缝
    mouth_y = int(H * 0.68)
    mouth_h = max(2, int(H * 0.16))
    R.fill(int(W * 0.08), mouth_y, int(W * 0.84), mouth_h, BLOOD_D)
    R.hline(mouth_y + mouth_h // 2, int(W * 0.08), int(W * 0.92), EYE_VOID, 0.85)
    tooth_w = 2
    for x in range(int(W * 0.10), int(W * 0.90) - tooth_w, tooth_w + 1):
        top_h = max(1, mouth_h // 2)
        R.fill(x, mouth_y + 1, tooth_w, top_h - 1, BONE_HI)
        R.fill(x, mouth_y + mouth_h - max(1, top_h - 1), tooth_w, max(1, top_h - 1), BONE)
    # 嘴角撕裂 + 血
    for cx in (int(W * 0.06), int(W * 0.92)):
        R.vline(cx, mouth_y, mouth_y + mouth_h, BLOOD, 0.75)
    R.band(mouth_y + mouth_h, max(1, int(H * 0.06)), BLOOD_D, 0.5)

    # --- 颧骨高光 + 裂纹（从眼窝往外爬，脸的"年岁"）
    R.hline(int(H * 0.60), 0, W - 1, BONE_HI, 0.30)
    cracks(R, 97, BONE_D, 3, max(3, H // 5))
    # --- 下缘：下颌影（Boss 的下巴是骨茬）
    R.band(H - max(1, H // 8), max(1, H // 8), BONE_SH, 0.45)
    grain(R, BONE_STAIN, 101, 0.16)


def _face_bevel(P):
    """前切角（1.2u 宽）：只画眼窝外沿的一段弧 + 骨的明暗，不重复五官。"""
    R = P.R
    bone_base(R, 103)
    eye_h = max(2, int(R.h * 0.18))
    eye_y = int(R.h * 0.30)
    R.fill(0, eye_y, R.w, eye_h, EYE_VOID)
    R.blend(R.w - 1, eye_y + 1, SOUL_D, 0.55)
    R.hline(eye_y - 1, 0, R.w - 1, BONE_HI, 0.7)
    cracks(R, 103, BONE_D, 1, max(2, R.h // 4))
    R.band(R.h - max(1, R.h // 6), max(1, R.h // 6), BONE_SH, 0.4)


# ---------------------------------------------------------------------------
# 锈铁：甲片 / 尖刺 / 钩环 / 笼条 / 斧
# ---------------------------------------------------------------------------

def p_plate_chest(P):
    """胸甲：中央脊线 + 铆钉 + 划痕（Boss 的正面主装甲）。"""
    R = P.R
    iron_base(R, 107)
    cx = R.w // 2
    R.col_band(max(0, cx - 1), 3, IRON_EDGE, 0.28)
    R.col_band(cx, 1, IRON_HI, 0.55)
    rivets(R, max(2, R.w // 4))
    # 划痕：几道斜线
    for i in range(3):
        x = int(frac(i, 107, 31) * R.w)
        y = int(frac(i, 107, 37) * R.h)
        for s in range(max(2, R.w // 4)):
            if 0 <= x + s < R.w and 0 <= y + s < R.h:
                R.blend(x + s, y + s, IRON_EDGE, 0.5)
    R.band(R.h - 1, 1, RUST_D, 0.5)


def p_plate_back(P):
    """背甲：纵向肋条（比胸甲更粗糙，Boss 的背部要能撑住尸笼）。"""
    R = P.R
    iron_base(R, 109)
    for x in range(0, R.w, 4):
        R.col_band(x, 1, IRON_D, 0.45)
        if x + 1 < R.w:
            R.col_band(x + 1, 1, IRON_HI, 0.35)
    rivets(R, max(2, R.w // 5))


def p_plate_shoulder(P):
    """肩甲：叠层甲片（横向三道），最上面一道磨亮。"""
    R = P.R
    iron_base(R, 113)
    for i in range(1, 3):
        y = int(R.h * i / 3.0)
        R.hline(y, 0, R.w - 1, IRON_D, 0.7)
        R.hline(y + 1, 0, R.w - 1, IRON_EDGE, 0.45)
    R.band(0, max(1, R.h // 3), IRON_HI, 0.30)
    R.disc(R.w * 0.5, R.h * 0.5, max(1.5, min(R.w, R.h) * 0.22), RUST, 0.25)


def p_plate_hip(P):
    """腰甲：小面板 —— 只留一道亮边 + 一颗铆钉。"""
    R = P.R
    iron_base(R, 127)
    R.band(0, 1, IRON_EDGE, 0.6)
    R.band(R.h - 1, 1, IRON_D, 0.7)
    if R.w >= 3 and R.h >= 3:
        R.disc(R.w // 2, R.h // 2, 1, IRON_EDGE, 0.7)


def p_plate_ridge(P):
    """甲脊：中间一条亮线到底，两侧塌成暗。"""
    R = P.R
    iron_base(R, 131, horizontal=False)
    cx = R.w // 2
    R.col_band(cx, 1, IRON_EDGE, 0.85)
    R.col_band(max(0, cx - 1), 1, IRON_HI, 0.5)
    R.col_band(min(R.w - 1, cx + 1), 1, IRON_D, 0.6)


def p_plate_spike(P):
    """甲刺：根部暗铁 → 梢部磨亮（方向由面板中心往两端）。"""
    R = P.R
    R.vgrad(IRON_D, IRON_EDGE)
    R.band(0, max(1, R.h // 3), RUST_D, 0.45)
    R.col_band(max(0, R.w // 2 - 1), 2, IRON_HI, 0.45)
    R.band(R.h - 1, 1, IRON_EDGE, 0.6)


def p_plate_hook(P):
    """钩环：一排链环（每环两行，环间暗缝）—— 挂在胸甲与尸笼之间。"""
    R = P.R
    R.wipe(IRON_D)
    grain(R, RUST, 137, 0.22)
    ring_w = max(3, R.w // 3)
    for x in range(1, R.w - 1, ring_w):
        w = min(ring_w - 1, R.w - x - 1)
        if w <= 0:
            continue
        for y in range(R.h):
            R.blend(x, y, IRON_HI if y % 2 == 0 else IRON, 0.75)
            R.blend(x + w - 1, y, IRON_D, 0.6)
        R.hline(0, x, x + w - 1, IRON_EDGE, 0.5)
        R.hline(R.h - 1, x, x + w - 1, RUST_D, 0.6)


def p_cage_iron(P):
    """尸笼骨条/铁箍：细长面板（1~2px 宽），只做"中轴亮 + 两侧暗 + 端头锈"。"""
    R = P.R
    R.wipe(IRON)
    cx = max(0, R.w // 2)
    R.col_band(cx, max(1, R.w - cx), IRON_HI, 0.55)
    R.col_band(0, 1, IRON_D, 0.7)
    grain(R, IRON_D, 139, 0.2)
    R.band(0, max(1, R.h // 12), RUST_D, 0.55)
    R.band(R.h - max(1, R.h // 12), max(1, R.h // 12), RUST_D, 0.55)
    # 笼条上的魂火反光：每隔一段一抹青
    for y in range(0, R.h, 7):
        R.blend(cx, y, SOUL_D, 0.35)


def p_soul_glow(P):
    """魂火（自发光）：暗底 → 青 → 白芯。做在笼内与胸口的"能量"面上。"""
    R = P.R
    R.vgrad(SOUL_D, SOUL)
    # 中央竖条白芯：1~2px，宽了就成白板
    cx = max(0, R.w // 2 - 1)
    R.col_band(cx, min(2, R.w), SOUL_HI, 0.9)
    R.col_band(max(0, cx - 1), 1, SOUL, 0.7)
    for y in range(0, R.h, 2):
        R.blend(cx, y, SOUL_CORE, 0.95)
    # 边缘压暗：让发光体有"体积"
    R.col_band(0, 1, SOUL_VOID, 0.55)
    R.col_band(R.w - 1, 1, SOUL_VOID, 0.55)
    R.band(0, 1, SOUL_VOID, 0.35)
    R.band(R.h - 1, 1, SOUL_VOID, 0.35)


def p_axe_haft(P):
    """斧柄：纵向木纹 + 缠绕的皮条（49px 高，能画出节奏）。"""
    R = P.R
    R.wipe(CLOTH_D)
    R.vgrad(HIDE_D, HIDE_SH)
    for x in range(0, R.w, 2):
        R.col_band(x, 1, HIDE,
                   0.35)
    # 缠皮：每 6px 一组斜向亮带
    for y in range(2, R.h - 2, 6):
        R.band(y, 1, BONE_SH, 0.45)
        R.band(y + 1, 1, HIDE_D, 0.5)
    R.band(R.h - 3, 3, IRON_D, 0.7)      # 尾端铁箍
    R.band(R.h - 4, 1, IRON_HI, 0.5)


def p_axe_head(P):
    """斧头：铁面 + 中央凹槽（血槽）+ 磨亮的上缘。"""
    R = P.R
    iron_base(R, 149, horizontal=False)
    cx = R.w // 2
    R.col_band(max(0, cx - 1), 2, IRON_D, 0.55)
    R.col_band(cx + 2, 1, IRON_HI, 0.35)
    rivets(R, max(2, R.w // 5))
    # 血槽里积的干血
    R.col_band(max(0, cx - 1), 1, BLOOD_D, 0.5)
    R.band(R.h - 1, 1, RUST, 0.45)


def p_axe_edge(P):
    """斧刃：窄面板（1.2u）—— 整条都是刃，只做"内暗外亮"。"""
    R = P.R
    R.vgrad(IRON_D, IRON_EDGE)
    R.col_band(0, 1, IRON_D, 0.6)
    R.col_band(R.w - 1, 1, (222, 228, 236), 0.9)   # 刃口的镜面高光
    R.band(0, 1, IRON_HI, 0.5)
    grain(R, RUST, 151, 0.10)


def p_axe_spike(P):
    """斧背尖刺：铁锥，根部锈、梢部亮。"""
    R = P.R
    R.vgrad(RUST_D, IRON_EDGE)
    R.col_band(max(0, R.w // 2 - 1), 2, IRON_HI, 0.5)
    R.band(0, 1, RUST_D, 0.6)


# ---------------------------------------------------------------------------
# 布 / 靴
# ---------------------------------------------------------------------------

def p_cloth_cape(P):
    """披风：暗布 + 纵向褶（一道亮脊 + 一道暗谷）。"""
    R = P.R
    R.vgrad(CLOTH_HI, CLOTH_D)
    for x in range(0, R.w, 3):
        R.col_band(x, 1, CLOTH_HI, 0.35)
        if x + 1 < R.w:
            R.col_band(x + 1, 1, CLOTH_D, 0.4)
    grain(R, CLOTH_D, 157, 0.2)
    R.band(0, 1, CLOTH_HI, 0.35)


def p_cloth_cape_edge(P):
    """披风下摆：上面是布，最下 3~4 行撕成参差的破口（Boss 拖在尸群里的那截）。"""
    R = P.R
    p_cloth_cape(P)
    fray = min(4, max(2, R.h // 4))
    for x in range(R.w):
        depth = 1 + int(frac(x, 7, 41) * (fray - 1))
        for y in range(R.h - depth, R.h):
            R.set(x, y, CLOTH_EDGE)
        R.blend(x, R.h - depth - 1, CLOTH_D, 0.7)
    # 破口边缘挂的血
    for x in range(0, R.w, 5):
        R.blend(x, max(0, R.h - fray - 1), BLOOD_D, 0.5)


def p_boot(P):
    """战靴：皮质 + 铁包趾 + 绑带（脚是俯视最显眼的部件）。"""
    R = P.R
    R.vgrad(HIDE_SH, CLOTH_D)
    grain(R, HIDE_D, 163, 0.22)
    # 铁包趾：前 1/3
    toe = max(1, R.w // 3)
    for y in range(R.h):
        for x in range(toe):
            R.blend(x, y, IRON, 0.75)
    R.vline(toe, 0, R.h - 1, IRON_EDGE, 0.7)
    R.band(0, 1, IRON_HI, 0.45)
    # 绑带：两道横带
    for i in (1, 2):
        y = int(R.h * i / 3.0)
        R.hline(y, 0, R.w - 1, CLOTH_EDGE, 0.75)
        R.hline(y + 1, 0, R.w - 1, CLOTH_HI, 0.4)
    R.band(R.h - 1, 1, CLOTH_EDGE, 0.8)


# ---------------------------------------------------------------------------
# 注册表（清单里的 painter 名 → 函数）
# ---------------------------------------------------------------------------

PAINTERS = {
    # 腐肉
    "hide_front": p_hide_front, "hide_back": p_hide_back, "hide_side": p_hide_side,
    "hide_hand": p_hide_hand, "hide_leg": p_hide_leg, "muscle": p_muscle,
    # 骨架
    "skull_top": p_skull_top, "skull_side": p_skull_side, "skull_back": p_skull_back,
    "skull_ridge": p_skull_ridge, "crown": p_crown, "horn": p_horn,
    "claw": p_claw, "teeth": p_teeth, "jaw": p_jaw, "face": p_face,
    # 锈铁
    "plate_chest": p_plate_chest, "plate_back": p_plate_back,
    "plate_shoulder": p_plate_shoulder, "plate_hip": p_plate_hip,
    "plate_ridge": p_plate_ridge, "plate_spike": p_plate_spike,
    "plate_hook": p_plate_hook, "cage_iron": p_cage_iron, "soul_glow": p_soul_glow,
    "axe_haft": p_axe_haft, "axe_head": p_axe_head, "axe_edge": p_axe_edge,
    "axe_spike": p_axe_spike,
    # 布 / 靴
    "cloth_cape": p_cloth_cape, "cloth_cape_edge": p_cloth_cape_edge, "boot": p_boot,
}

# 共享图元（清单里 "@" 前缀的面）：整块平铺 + 噪声，省图集空间
FLAT = {
    "lining": LINING,
    "cloth_dark": CLOTH_DARK,
}


def p_flat(P, sample):
    R = P.R
    base = FLAT[sample]
    R.wipe(base)
    R.noise((max(0, base[0] - 20), max(0, base[1] - 20), max(0, base[2] - 20)),
            0x5A + len(sample), 0.10)


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
                P.R.wipe(LINING)
            else:
                fn(P)
        for yy in range(v, v + h):
            for xx in range(u, u + w):
                painted[yy][xx] = True

    # 边缘外扩 1px：防 MIP/过滤把相邻矩形的颜色渗进来
    for m in man["faces"]:
        u, v, w, h = m["rect"]
        for yy in range(v - 1, v + h + 1):
            for xx in range(u - 1, u + w + 1):
                if 0 <= xx < W and 0 <= yy < H and not painted[yy][xx]:
                    sx = min(max(xx, u), u + w - 1)
                    sy = min(max(yy, v), v + h - 1)
                    canvas.set(xx, yy, canvas.get(sx, sy))
                    painted[yy][xx] = True

    # 兜底：任何还是透明的作画像素都填内衬色（数字应为 0；不为 0 说明某画家没画满）
    op_fix = 0
    for m in man["faces"]:
        u, v, w, h = m["rect"]
        for yy in range(v, v + h):
            for xx in range(u, u + w):
                if canvas.get(xx, yy)[3] == 0:
                    canvas.set(xx, yy, LINING)
                    op_fix += 1

    png = write_png(ART_TEX, W, H, canvas.buf)
    SRC_TEX.parent.mkdir(parents=True, exist_ok=True)
    SRC_TEX.write_bytes(png)
    a = hashlib.sha256(ART_TEX.read_bytes()).hexdigest()
    b = hashlib.sha256(SRC_TEX.read_bytes()).hexdigest()

    n_painted = sum(1 for m in man["faces"] if not m["painter"].startswith("@"))
    n_shared = len(man["faces"]) - n_painted
    covered = sum(m["rect"][2] * m["rect"][3] for m in man["faces"])
    print(f"贴图 {W}×{H}  作画矩形 {n_painted} / 共享图元 {n_shared}")
    print(f"art : {ART_TEX}\n      sha256={a}")
    print(f"src : {SRC_TEX}\n      sha256={b}")
    print(f"art == src: {a == b}")
    print(f"矩形覆盖 {covered} texels（{covered / float(W * H) * 100:.1f}%）；"
          f"基础层兜底补 {op_fix} px")
    if op_fix:
        print("⚠ 有画家没画满，已用内衬色补上 —— 检查上面那批矩形")
    if unknown:
        print(f"未知画家（用了兜底）: {sorted(unknown)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
