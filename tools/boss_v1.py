#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""尸潮之主（Horde Overlord）生成器 —— 三阶段 Boss 的唯一真相源。

管线位置：本脚本（几何/骨骼/动画/图集清单） → tools/boss_v1_skin.py（贴图） →
art/boss/*（台账副本） + src/main/resources/assets/... （游戏读取）。

规格（与美术规范.md / docs/wiki/04-美术规范速查.md 对齐）：
  16 u = 1 block；上 = +Y，正面（脸/胸前）= -Z，+X = 模型自身右侧；原点 = 两脚之间的地面。
  曲面部件（躯干/四肢/头颅）一律用八角环拼「圆润柱体」，不堆方块。
  动画全部骨骼驱动（rotation/position），**没有任何 scale 通道** —— 整体缩放式假动画一律禁止。
  贴图 512×512（Minecraft 只接受 2 的幂正方形），逐面 UV 图集，密度见 DENSITY_TRIES。

Boss 结构（4200 HP / 三阶段）：
  Phase 1 (>66%)  : attack_melee（巨斧横扫） / attack_ranged（骨刺齐射）
  Phase 2 (≤66%)  : + summon（召唤尸群） / skill_quake（踏地冲击波）
  Phase 3 (≤33%)  : + skill_rage（血怒变身，进场） / 技能强化；skill_death（亡语崩解）
"""

import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = ROOT / "art" / "boss"
SRC_ASSETS = ROOT / "src/main/resources/assets/apocalypse_zombies"

MODEL_ID = "horde_overlord"
GEO_NAME = f"{MODEL_ID}.geo.json"
ANIM_NAME = f"{MODEL_ID}.animation.json"
MANIFEST_NAME = "boss_atlas.json"
GEO_ID = f"geometry.{MODEL_ID}"
TEX_REL = f"textures/entity/{MODEL_ID}.png"

TEX_W = TEX_H = 512
TPU_DIV = 3                    # 3u 一像素 = 1px/u 的基准；DEFAULT_TPU=6 → 2px/u（vanilla mob 的 2 倍）
DEFAULT_TPU = 6
FACE_TPU = 12                  # 脸 = 4px/u，五官在这个体量上才读得出来
DENSITY_TRIES = (3, 4, 5, 6)    # 分母从 3 起步（=2px/u），装不下才逐档降密度

# ---- Boss 硬数字（Java 侧必须一字不差地同步） ----
BOSS_MAX_HEALTH = 4200.0
# 分段阈值在 Java 侧是「派生表达式」（改上限即跟着走），这里也只存比例 —— 两边都不许各写各的字面量。
PHASE2_RATIO = 2.0 / 3.0       # 4200 → 2800
PHASE3_RATIO = 1.0 / 3.0       # 4200 → 1400
PHASE2_HP = BOSS_MAX_HEALTH * PHASE2_RATIO
PHASE3_HP = BOSS_MAX_HEALTH * PHASE3_RATIO
BOSS_WAVE = 5                  # 尸潮第 5 波（原 4 波 → 5 波）
HORDE_WAVES = 5

# ---------------------------------------------------------------------------
# 0. 骨骼表 / 体块表（pivot 与 cube 坐标都是模型空间绝对坐标，单位 u）
# ---------------------------------------------------------------------------

BONES = []
CUBES = []


def bone(name, pivot, parent=None):
    BONES.append({"name": name, "pivot": [round(v, 3) for v in pivot], "parent": parent})


def _paint_map(paint, hidden):
    """把 paint 规格规范化成 {面: 值}；值 = 字符串名 或 (名字, kwargs)。"""
    faces = ("n", "s", "e", "w", "u", "d")
    if isinstance(paint, (str, tuple)):
        out = {f: paint for f in faces}
    else:
        out = {f: paint.get(f, "@lining") for f in faces}
    for ch in hidden:
        out[ch] = "@lining"
    return out


def cube(bone_name, box, paint, hidden="", part="", flip=False, tpu=None):
    """box = (x0,y0,z0,x1,y1,z1)，单位 u。"""
    x0, y0, z0, x1, y1, z1 = [round(float(v), 3) for v in box]
    x0, x1 = sorted((x0, x1))          # 左右镜像写法会给出反向的 x，统一成 min/max
    y0, y1 = sorted((y0, y1))
    z0, z1 = sorted((z0, z1))
    assert x1 > x0 and y1 > y0 and z1 > z0, f"{part}: 退化体块 {box}"
    CUBES.append({
        "bone": bone_name,
        "box": [x0, y0, z0, x1, y1, z1],
        "paint": _paint_map(paint, hidden),
        "part": part or bone_name,
        "flip": bool(flip),
        "tpu": tpu,
    })


def _oct_boxes(y0, y1, hx, hz, ax, bz):
    return {
        "n":  (-ax, y0, -hz, ax, y1, -bz),
        "s":  (-ax, y0, bz, ax, y1, hz),
        "e":  (ax, y0, -bz, hx, y1, bz),
        "w":  (-hx, y0, -bz, -ax, y1, bz),
        "fe": (ax, y0, -hz, hx, y1, -bz),
        "fw": (-hx, y0, -hz, -ax, y1, -bz),
        "be": (ax, y0, bz, hx, y1, hz),
        "bw": (-hx, y0, bz, -ax, y1, hz),
    }


PANEL_FACES = {
    "n": ("n",), "s": ("s",), "e": ("e",), "w": ("w",),
    "fe": ("n", "e"), "fw": ("n", "w"), "be": ("s", "e"), "bw": ("s", "w"),
}


def oct_ring(bone_name, y0, y1, hx, hz, ax, bz, out, part, tpu=None,
             cap_up=None, cap_down=None, mid_cap="@cloth_dark", flip=False,
             panels=("n", "s", "e", "w", "fe", "fw", "be", "bw"), tpu_by_panel=None):
    """八角环：八块薄板围成一根圆润柱体，每块板材有独立的正面/侧面 UV。

    panels 只给 ("n","s","e","w") 时省掉四个切角 → 四肢用的「方柱」，
    面数省一半，且视觉上跟方块手臂一致（boss 的四肢本来就该硬朗）。
    """
    boxes = _oct_boxes(y0, y1, hx, hz, ax, bz)
    for p in panels:
        paint = {}
        for f in PANEL_FACES[p]:
            paint[f] = out.get(f, "@lining")
        paint["u"] = cap_up if cap_up else mid_cap
        paint["d"] = cap_down if cap_down else mid_cap
        for f in ("n", "s", "e", "w", "u", "d"):
            if f not in PANEL_FACES[p] or (p in ("n", "s", "e", "w") and f != PANEL_FACES[p][0]):
                if f not in ("u", "d"):
                    paint[f] = "@lining"
        cube(bone_name, boxes[p], paint, part=f"{part}_{p}", flip=flip,
             tpu=(tpu_by_panel or {}).get(p, tpu))


def slab(bone_name, box, paint, hidden="", part="", flip=False, tpu=None):
    cube(bone_name, box, paint, hidden=hidden, part=part, flip=flip, tpu=tpu)


# ---------------------------------------------------------------------------
# 1. 骨骼树
# ---------------------------------------------------------------------------
bone("root", (0, 0, 0))
bone("move", (0, 0, 0), "root")
bone("hip", (0, 18.5, 0), "move")
bone("spine", (0, 22.6, 0), "hip")
bone("chest", (0, 27.4, 0), "spine")
bone("neck", (0, 34.4, 0), "chest")
bone("head", (0, 36.6, 0), "neck")
bone("jaw", (0, 38.2, -1.0), "head")
bone("crown", (0, 44.6, 0), "head")
bone("horn_l", (-3.0, 43.8, 0.4), "head")
bone("horn_l2", (-4.6, 47.4, 1.2), "horn_l")
bone("horn_r", (3.0, 43.8, 0.4), "head")
bone("horn_r2", (4.6, 47.4, 1.2), "horn_r")
bone("shoulder_l", (-5.2, 33.4, 0), "chest")
bone("shoulder_r", (5.2, 33.4, 0), "chest")
bone("pauldron_l", (-6.6, 34.4, 0), "shoulder_l")
bone("pauldron_r", (6.6, 34.4, 0), "shoulder_r")
bone("arm_l", (-6.4, 33.6, 0), "shoulder_l")
bone("forearm_l", (-6.4, 27.0, 0), "arm_l")
bone("hand_l", (-6.4, 21.4, 0), "forearm_l")
bone("claw_l1", (-6.4, 18.8, -1.5), "hand_l")
bone("claw_l2", (-6.4, 18.8, 0.0), "hand_l")
bone("claw_l3", (-6.4, 18.8, 1.5), "hand_l")
bone("arm_r", (6.4, 33.6, 0), "shoulder_r")
bone("forearm_r", (6.4, 27.0, 0), "arm_r")
bone("hand_r", (6.4, 21.4, 0), "forearm_r")
bone("claw_r1", (6.4, 18.8, -1.5), "hand_r")
bone("claw_r2", (6.4, 18.8, 0.0), "hand_r")
bone("claw_r3", (6.4, 18.8, 1.5), "hand_r")
bone("axe", (6.4, 20.0, 0), "hand_r")
bone("back_cage", (0, 30.6, 4.2), "chest")
bone("cage_band1", (0, 27.6, 4.2), "back_cage")
bone("cage_band2", (0, 35.2, 4.2), "back_cage")
bone("cage_soul", (0, 30.6, 4.2), "back_cage")
bone("cape", (0, 33.6, 2.8), "chest")
bone("cape2", (0, 27.4, 3.4), "cape")
bone("cape3", (0, 21.2, 3.8), "cape2")
bone("cape_wl", (-6.2, 32.0, 3.0), "cape")
bone("cape_wr", (6.2, 32.0, 3.0), "cape")
bone("leg_l", (-2.8, 18.6, 0), "hip")
bone("leg_r", (2.8, 18.6, 0), "hip")
bone("shin_l", (-2.8, 10.2, 0), "leg_l")
bone("shin_r", (2.8, 10.2, 0), "leg_r")
bone("foot_l", (-2.8, 2.6, 0), "shin_l")
bone("foot_r", (2.8, 2.6, 0), "shin_r")

# ---------------------------------------------------------------------------
# 2. 几何：躯干 / 头颅 / 四肢 / 尸笼 / 披风 / 巨斧
# ---------------------------------------------------------------------------
LIMB = ("n", "s", "e", "w")

# --- 躯干：臀 → 腰 → 胸 三段八角环；胸最宽（boss 的桶状胸廓） ---
oct_ring("hip", 14.6, 22.6, 4.8, 3.5, 3.3, 2.2,
         {"n": "hide_front", "s": "hide_back", "e": "hide_side", "w": "hide_side"},
         "hip", tpu=6, cap_up="@cloth_dark", cap_down="plate_hip")
oct_ring("spine", 22.6, 27.4, 4.2, 3.1, 2.9, 2.0,
         {"n": "hide_front", "s": "hide_back", "e": "hide_side", "w": "hide_side"},
         "spine", tpu=6)
oct_ring("chest", 27.4, 34.4, 6.1, 3.9, 4.5, 2.5,
         {"n": "plate_chest", "s": "plate_back", "e": "hide_side", "w": "hide_side"},
         "chest", tpu=6, cap_up="plate_hook", cap_down="@cloth_dark")

# 胸甲分片：左右两瓣 + 中央脊板 + 背脊板（V 形，比一整块桶壳好读）
slab("chest", (-4.4, 28.4, -4.6, -0.5, 33.8, -3.8), "plate_chest", part="plate_chest_l")
slab("chest", (0.5, 28.4, -4.6, 4.4, 33.8, -3.8), "plate_chest", part="plate_chest_r")
slab("chest", (-1.0, 27.6, -4.2, 1.0, 34.4, -3.5), "plate_ridge", part="plate_ridge")
slab("chest", (-1.6, 26.8, 3.6, 1.6, 35.4, 4.4), "plate_ridge", part="plate_back_ridge")
slab("chest", (-5.6, 33.4, -3.0, 5.6, 34.6, 3.0), "plate_hook", part="plate_collar")

# --- 脖颈 / 头颅 ---
oct_ring("neck", 34.4, 36.8, 2.5, 2.3, 1.8, 1.4, {"n": "hide_front", "s": "hide_back", "e": "hide_side", "w": "hide_side"},
         "neck", tpu=6, cap_up="@cloth_dark")
oct_ring("head", 36.8, 45.2, 4.3, 3.9, 3.1, 2.6,
         {"n": "face", "s": "skull_back", "e": "skull_side", "w": "skull_side"},
         "head", tpu=6, cap_up="skull_top", cap_down="@cloth_dark",
         tpu_by_panel={"n": FACE_TPU, "fe": FACE_TPU, "fw": FACE_TPU})  # 脸 + 前切角 = 4px/u

# 下颚 / 獠牙 / 眼窝
slab("jaw", (-2.9, 36.4, -4.9, 2.9, 38.4, -2.4), "jaw", part="jaw")
slab("jaw", (-2.6, 38.2, -4.7, 2.6, 38.9, -2.6), "teeth", part="teeth_lower")
slab("head", (-2.7, 39.1, -4.6, 2.7, 39.8, -2.8), "teeth", part="teeth_upper")
slab("head", (-2.9, 40.6, -4.2, -1.1, 42.0, -3.7), "soul_glow", part="eye_l")
slab("head", (1.1, 40.6, -4.2, 2.9, 42.0, -3.7), "soul_glow", part="eye_r")
slab("head", (-4.4, 39.0, -3.4, 4.4, 40.4, -2.6), "skull_ridge", part="brow")

# 骨冠 + 双角（两段，逐段收细）
slab("crown", (-3.6, 44.6, -3.2, 3.6, 46.0, 2.4), "crown", part="crown_base")
slab("crown", (-1.0, 46.0, -2.2, 1.0, 48.6, 0.6), "crown", part="crown_spike_c")
slab("crown", (-3.4, 46.0, -1.8, -1.4, 47.9, 0.4), "crown", part="crown_spike_l")
slab("crown", (1.4, 46.0, -1.8, 3.4, 47.9, 0.4), "crown", part="crown_spike_r")
slab("horn_l", (-3.9, 43.8, -0.4, -2.1, 46.2, 1.6), "horn", part="horn_l")
slab("horn_l2", (-5.3, 45.6, 0.4, -3.7, 48.4, 2.2), "horn", part="horn_l2")
slab("horn_r", (2.1, 43.8, -0.4, 3.9, 46.2, 1.6), "horn", part="horn_r")
slab("horn_r2", (3.7, 45.6, 0.4, 5.3, 48.4, 2.2), "horn", part="horn_r2")

# --- 肩甲 / 手臂 / 爪 ---
for tag, sx in (("l", -1.0), ("r", 1.0)):
    pa = f"pauldron_{tag}"
    slab(pa, (sx * 6.9, 33.5, -3.0, sx * 4.1, 36.4, 3.0), "plate_shoulder", part=f"{pa}_top")
    slab(pa, (sx * 7.6, 31.6, -2.4, sx * 5.0, 33.6, 2.4), "plate_shoulder", part=f"{pa}_rim")
    slab(pa, (sx * 8.4, 34.6, -1.0, sx * 7.0, 38.0, 1.0), "plate_spike", part=f"{pa}_spike")
    arm, fa, hd = f"arm_{tag}", f"forearm_{tag}", f"hand_{tag}"
    flip = tag == "l"
    oct_ring(arm, 27.0, 34.0, 2.4, 2.4, 1.7, 1.7,
             {"n": "muscle", "s": "muscle", "e": "hide_side", "w": "hide_side"},
             arm, panels=LIMB, flip=flip, tpu=6)
    oct_ring(fa, 21.4, 27.0, 2.1, 2.1, 1.5, 1.5,
             {"n": "muscle", "s": "muscle", "e": "hide_side", "w": "hide_side"},
             fa, panels=LIMB, flip=flip, tpu=6, cap_down="@cloth_dark")
    slab(hd, (sx * 7.6, 18.8, -2.3, sx * 5.2, 21.4, 2.3), "hide_hand", part=hd, flip=flip)
    for i, cz in enumerate((-1.5, 0.0, 1.5)):
        slab(f"claw_{tag}{i + 1}", (sx * 7.0, 15.6, cz - 1.1, sx * 5.8, 18.8, cz + 1.1),
             "claw", part=f"claw_{tag}{i + 1}")

# --- 巨斧（挂在 hand_r 上：骨骼驱动，挥砍是真实骨骼变换） ---
slab("axe", (5.8, 6.4, -0.7, 7.0, 31.0, 0.7), "axe_haft", part="axe_haft")
slab("axe", (5.5, 25.6, -8.2, 7.3, 33.4, -0.6), "axe_head", part="axe_head")
slab("axe", (5.8, 27.4, -9.4, 7.0, 31.6, -8.2), "axe_edge", part="axe_edge")
slab("axe", (5.6, 28.6, 0.6, 7.2, 30.6, 3.6), "axe_spike", part="axe_spike")
slab("axe", (5.9, 20.4, -0.9, 6.9, 25.0, 0.9), "hide_hand", part="axe_grip")

# --- 背后尸笼（召唤源：骨条 + 两条会转的箍 + 笼中魂火） ---
for i, (cx, cz) in enumerate(((-3.4, 3.6), (-1.2, 4.4), (1.2, 4.4), (3.4, 3.6))):
    slab("back_cage", (cx - 0.5, 25.6, cz, cx + 0.5, 38.4, cz + 0.9), "cage_iron",
         part=f"cage_bar{i + 1}")
for tag, band_bone in (("low", "cage_band1"), ("high", "cage_band2")):
    y0 = 27.4 if tag == "low" else 35.0
    slab(band_bone, (-3.9, y0, 3.4, 3.9, y0 + 1.3, 4.3), "cage_iron", part=f"cage_band_{tag}_s")
    slab(band_bone, (-3.9, y0, 4.3, -2.9, y0 + 1.3, 5.6), "cage_iron", part=f"cage_band_{tag}_e")
    slab(band_bone, (2.9, y0, 4.3, 3.9, y0 + 1.3, 5.6), "cage_iron", part=f"cage_band_{tag}_w")
slab("cage_soul", (-1.9, 29.4, 4.0, 1.9, 33.0, 5.2), "soul_glow", part="cage_soul")
slab("cage_soul", (-1.2, 33.0, 4.2, 1.2, 34.4, 5.0), "soul_glow", part="cage_soul_top")

# --- 披风（三段链 + 左右翼片，走起路来甩） ---
slab("cape", (-6.0, 26.6, 3.4, 6.0, 33.8, 4.2), "cloth_cape", part="cape")
slab("cape2", (-6.6, 19.2, 3.9, 6.6, 26.6, 4.8), "cloth_cape", part="cape2")
slab("cape3", (-7.2, 11.6, 4.4, 7.2, 19.2, 5.4), "cloth_cape_edge", part="cape3")
slab("cape_wl", (-8.6, 24.4, 3.1, -5.4, 32.6, 4.1), "cloth_cape_edge", part="cape_wl", flip=True)
slab("cape_wr", (5.4, 24.4, 3.1, 8.6, 32.6, 4.1), "cloth_cape_edge", part="cape_wr")

# --- 腿 ---
for tag, sx in (("l", -1.0), ("r", 1.0)):
    flip = tag == "l"
    leg, shin, foot = f"leg_{tag}", f"shin_{tag}", f"foot_{tag}"
    oct_ring(leg, 10.2, 18.8, 2.8, 2.7, 2.0, 1.9,
             {"n": "hide_leg", "s": "hide_leg", "e": "hide_side", "w": "hide_side"},
             leg, panels=LIMB, flip=flip, tpu=6)
    oct_ring(shin, 2.8, 10.2, 2.3, 2.3, 1.6, 1.6,
             {"n": "hide_leg", "s": "hide_leg", "e": "hide_side", "w": "hide_side"},
             shin, panels=LIMB, flip=flip, tpu=6, cap_up="@cloth_dark")
    slab(foot, (sx * 4.4, -0.1, -5.0, sx * 1.2, 3.0, 2.0), "boot", part=foot)

# ---------------------------------------------------------------------------
# 3. UV 图集：货架装箱 + 共享图元
# ---------------------------------------------------------------------------
FACE_ORDER = ("n", "s", "e", "w", "u", "d")
FACE_WH = {
    "n": lambda w, h, d: (w, h), "s": lambda w, h, d: (w, h),
    "e": lambda w, h, d: (d, h), "w": lambda w, h, d: (d, h),
    "u": lambda w, h, d: (w, d), "d": lambda w, h, d: (w, d),
}
# 每面在 UV 里的「向右」对应模型哪个轴（决定画家函数里的横向是否是镜像的）
FACE_UVDIR = {"n": "x", "s": "x", "e": "z", "w": "z", "u": "x", "d": "x"}
FACE_UP_DIR = {"n": "y", "s": "y", "e": "y", "w": "y", "u": "z", "d": "z"}

# 共享图元：2×2 / 4×4 的纯色小块，摊在图集最底部一条 8px 高的带子里，
# 所有「看不见的面」（内壁、切面、被压住的面）都指向这里 —— 省贴图，也让内壁颜色统一。
SAMPLES = ("lining", "cloth_dark", "cloth_top", "hide_dark", "hide_top", "iron_dark_top")
SAMPLE_STRIP_H = 6
SAMPLE_RECT = {}
for _i, _name in enumerate(SAMPLES):
    SAMPLE_RECT[_name] = (_i * 6, TEX_H - SAMPLE_STRIP_H, 4, 4)

PACK_TOP = 2
PACK_BOTTOM = TEX_H - SAMPLE_STRIP_H - 2


class Packer:
    """货架装箱：按高度降序排队，逐行左→右摆放，行高 = 该行最高元素。"""

    def __init__(self, width, top, bottom, pad=1):
        self.w, self.top, self.bottom, self.pad = width, top, bottom, pad
        self.shelf_y = top
        self.x = 0
        self.row_h = 0

    def alloc(self, w, h):
        w, h = int(w), int(h)
        raise_ = self.pad
        if self.x + w + self.pad > self.w:
            self.shelf_y += self.row_h + self.pad
            self.x = 0
            self.row_h = 0
        if self.shelf_y + h + self.pad > self.bottom:
            raise OverflowError(f"图集塞不下：{w}x{h} @ y={self.shelf_y}")
        u, v = self.x + self.pad, self.shelf_y + self.pad
        self.x += w + self.pad
        self.row_h = max(self.row_h, h + self.pad)
        return (u, v, w, h)

    def used_height(self):
        return self.shelf_y + self.row_h


MANIFEST = []


def build_manifest(tpu_div):
    """tpu_div：3u/px；值越大密度越低。返回 None 表示这一档装不下。"""
    global MANIFEST
    MANIFEST = []
    packer = Packer(TEX_W, PACK_TOP, PACK_BOTTOM)
    reqs = []
    for ci, c in enumerate(CUBES):
        x0, y0, z0, x1, y1, z1 = c["box"]
        w, h, d = x1 - x0, y1 - y0, z1 - z0
        for face in FACE_ORDER:
            fw, fh = FACE_WH[face](w, h, d)
            pv = c["paint"][face]
            name = pv if isinstance(pv, str) else pv[0]
            kw = {} if isinstance(pv, str) else dict(pv[1] or {})
            tpu = 0 if name.startswith("@") else (c["tpu"] or DEFAULT_TPU)
            reqs.append([ci, face, name, kw, fw, fh, tpu, None])
    own = [r for r in reqs if r[6]]
    own.sort(key=lambda r: (-max(r[4] * r[6], r[5] * r[6]), -min(r[4] * r[6], r[5] * r[6])))
    try:
        for r in own:
            w = max(1, int(round(r[4] * r[6] / float(tpu_div))))
            h = max(1, int(round(r[5] * r[6] / float(tpu_div))))
            r[7] = list(packer.alloc(w, h))
    except OverflowError:
        return None
    for ci, face, name, kw, fw, fh, tpu, rect in reqs:
        if name.startswith("@"):
            u, v, w, h = SAMPLE_RECT[name[1:]]
            rect, tpu = [u, v, w, h], 0
        MANIFEST.append({
            "cube": ci, "bone": CUBES[ci]["bone"], "part": CUBES[ci]["part"], "face": face,
            "rect": rect, "tpu": tpu, "fw": round(fw, 3), "fh": round(fh, 3),
            "painter": name, "kwargs": kw, "flip": CUBES[ci]["flip"],
            "u_dir": FACE_UVDIR[face], "up_dir": FACE_UP_DIR[face],
        })
    return packer


def bind_uvs():
    for c in CUBES:
        c["uv"] = {}
    for m in MANIFEST:
        u, v, w, h = m["rect"]
        CUBES[m["cube"]]["uv"][m["face"]] = {"uv": [u, v], "uv_size": [w, h]}


DENSITY = DENSITY_TRIES[0]
PACK_USED = 0
PACKER = None
for _try in DENSITY_TRIES:
    PACKER = build_manifest(_try)
    if PACKER is not None:
        DENSITY = _try
        break
if PACKER is None:
    raise SystemExit(f"图集 {TEX_W}x{TEX_H} 在密度 {DENSITY_TRIES} 下都塞不下，需要加大贴图")
PACK_USED = PACKER.used_height()
bind_uvs()


def face_size(box, face):
    x0, y0, z0, x1, y1, z1 = box
    return FACE_WH[face](x1 - x0, y1 - y0, z1 - z0)


# ---------------------------------------------------------------------------
# 4. 动画
# ---------------------------------------------------------------------------
def s(t):
    return round(t, 3)


def sine(length, n, amp, phase=0.0, steps=None):
    """周期通道：0 与 length 处的值必然相等（循环接缝天然闭合）。"""
    steps = steps or max(4, n * 4)
    out = {}
    import math
    for i in range(steps + 1):
        t = length * i / float(steps)
        out[s(t)] = round(amp * math.sin(2 * math.pi * (n * t / length) + phase), 4)
    return out


def env(length, pts):
    """折线包络：pts = [(t, v), ...]，端点补 0。"""
    keys = {0.0: 0.0}
    for t, v in pts:
        keys[s(min(max(t, 0.0), length))] = round(v, 4)
    keys[s(length)] = 0.0
    return dict(sorted(keys.items()))


def sample_axis(keys, t):
    """在单个轴自己的键上线性取值（区间外取端点值）。

    合并 x/y/z 成向量时各轴的键时刻往往不同；线性插值对「在段中插采样点」是不变的，
    所以按并集取样的动作与原动作逐帧等价。
    """
    if not keys:
        return 0.0
    ts = sorted(keys)
    if t <= ts[0]:
        return keys[ts[0]]
    if t >= ts[-1]:
        return keys[ts[-1]]
    for a, b in zip(ts, ts[1:]):
        if a <= t <= b:
            if b == a:
                return keys[b]
            return keys[a] + (keys[b] - keys[a]) * (t - a) / (b - a)
    return keys[ts[-1]]


class Clip:
    def __init__(self, name, length, loop=False):
        self.name = name
        self.length = round(length, 3)
        self.loop = loop
        self.data = {}

    def rot(self, bone, spec):
        self._add(bone, "rotation", spec)

    def pos(self, bone, spec):
        self._add(bone, "position", spec)

    def _add(self, bone, chan, spec):
        d = self.data.setdefault(bone, {}).setdefault(chan, {})
        for axis, keys in spec.items():
            if isinstance(keys, (int, float)):
                keys = {0.0: keys}          # 标量 = 整段常量偏置（仅循环剪辑合理）
            elif not hasattr(keys, "items"):
                keys = dict(keys)           # 允许 [(t, v), ...] 写法
            d.setdefault(axis, {}).update({s(t): round(v, 4) for t, v in keys.items()})

    def finalize(self):
        """自动补首尾键：非循环剪辑首尾归零（收招回静止），循环剪辑两端取同值（接缝闭合）。"""
        L = self.length
        for bone, chans in self.data.items():
            for chan, axes in chans.items():
                for axis, keys in axes.items():
                    if 0.0 not in keys:
                        keys[0.0] = 0.0 if not self.loop else list(keys.values())[-1]
                    if L not in keys:
                        keys[L] = 0.0 if not self.loop else keys[0.0]
                    axes[axis] = dict(sorted(keys.items()))

    def bones_touched(self):
        return set(self.data)

    def to_json(self):
        """出口形状：**时间 → 三元向量**（GeckoLib/Bedrock 契约）。

        内部模型是按轴存的（{x: {t: v}, y: {...}}），必须在出口处合并成向量 ——
        GeckoLib 的 BakedAnimationsAdapter 只认「值 = 数组」或「值 = 含 vector/post/pre
        的对象」，把 per-axis 结构原样写出去会被判
        'Invalid keyframe data - expected array'，而且它是在**资源重载**里解析动画文件的：
        一个文件抛异常 → 整次重载失败 → 客户端清空用户选中的资源包 → 字体没重建 → 全屏方框。

        裸数组（不带 lerp_mode）＝ GeckoLib 默认缓动 LINEAR（EasingType.LINEAR），
        正是本生成器「密集采样正弦」所对应的插值方式。
        """
        bones = {}
        for bone, chans in self.data.items():
            out = {}
            for chan, axes in chans.items():
                times = sorted({t for keys in axes.values() for t in keys})
                out[chan] = {str(t): [round(sample_axis(axes.get(ax), t), 4)
                                      for ax in ("x", "y", "z")]
                             for t in times}
            bones[bone] = out
        return {"loop": self.loop, "animation_length": self.length, "bones": bones}


# 位移幅度表（u）：语义同美术规范 —— y = 起落，z = 前后（负 = 正面 -Z），x = 左右（+X = 右侧）
MOVE_AMP = {
    "idle": {"y": 1.0},
    "walk": {"y": 1.4},
    "attack_melee": {"y": 1.2, "z": 2.6},
    "attack_ranged": {"y": 0.8, "z": 1.8},
    "summon": {"y": 2.4},
    "skill_quake": {"y": 4.6},
    "skill_rage": {"y": 3.2},
    "skill_death": {"y": 6.0},
}


def build_animations():
    clips = []

    # --- idle：呼吸 + 笼箍慢转 + 披风轻摆 ---
    c = Clip("idle", 3.0, loop=True)
    c.rot("chest", {"x": sine(3.0, 2, 1.6)})
    c.rot("spine", {"x": sine(3.0, 2, 1.1, phase=0.6)})
    c.rot("head", {"x": sine(3.0, 1, 2.2, phase=1.2), "y": sine(3.0, 1, 3.0, phase=0.4)})
    c.rot("jaw", {"x": sine(3.0, 3, 1.4, phase=2.0)})
    c.rot("arm_l", {"x": sine(3.0, 2, 2.0, phase=0.9)})
    c.rot("arm_r", {"x": sine(3.0, 2, 1.6, phase=1.5)})
    c.rot("cape", {"x": sine(3.0, 2, 2.4, phase=0.3)})
    c.rot("cape2", {"x": sine(3.0, 2, 3.4, phase=0.9)})
    c.rot("cape3", {"x": sine(3.0, 2, 4.6, phase=1.5)})
    c.rot("cage_band1", {"y": sine(3.0, 1, 12.0)})
    c.rot("cage_band2", {"y": sine(3.0, 1, -12.0, phase=0.7)})
    c.pos("move", {"y": sine(3.0, 2, MOVE_AMP["idle"]["y"], phase=-1.5708)})
    clips.append(c)

    # --- walk：迈步 / 摆臂 / 披风甩动 / 巨斧拖拽 ---
    c = Clip("walk", 1.6, loop=True)
    c.rot("leg_l", {"x": sine(1.6, 1, 22.0)})
    c.rot("leg_r", {"x": sine(1.6, 1, 22.0, phase=3.1416)})
    c.rot("shin_l", {"x": [(t, round(max(0.0, -v) * 0.8, 4)) for t, v in sine(1.6, 1, 26.0, phase=2.6).items()]})
    c.rot("shin_r", {"x": [(t, round(max(0.0, -v) * 0.8, 4)) for t, v in sine(1.6, 1, 26.0, phase=5.74).items()]})
    c.rot("foot_l", {"x": sine(1.6, 1, 9.0, phase=1.2)})
    c.rot("foot_r", {"x": sine(1.6, 1, 9.0, phase=4.34)})
    c.rot("hip", {"z": sine(1.6, 1, 2.6), "x": 2.0})
    c.rot("spine", {"z": sine(1.6, 1, -2.2), "x": -2.4})
    c.rot("chest", {"z": sine(1.6, 1, -1.6)})
    c.rot("arm_l", {"x": sine(1.6, 1, 16.0, phase=3.1416)})
    c.rot("forearm_l", {"x": sine(1.6, 1, 8.0, phase=2.5)})
    c.rot("arm_r", {"x": sine(1.6, 1, 9.0, phase=0.9)})
    c.rot("axe", {"x": sine(1.6, 1, 5.0, phase=1.6), "z": sine(1.6, 1, 3.0, phase=2.4)})
    c.rot("head", {"y": sine(1.6, 1, 4.0, phase=0.6), "x": sine(1.6, 2, 1.8)})
    c.rot("cape", {"x": [(t, round(-abs(v) * 0.9, 4)) for t, v in sine(1.6, 1, 9.0, phase=1.0).items()]})
    c.rot("cape2", {"x": [(t, round(-abs(v) * 1.1, 4)) for t, v in sine(1.6, 1, 11.0, phase=1.5).items()]})
    c.rot("cape3", {"x": [(t, round(-abs(v) * 1.3, 4)) for t, v in sine(1.6, 1, 13.0, phase=2.0).items()]})
    c.rot("cage_band1", {"y": sine(1.6, 1, 9.0)})
    c.rot("cage_band2", {"y": sine(1.6, 1, -9.0, phase=0.8)})
    c.pos("move", {"y": sine(1.6, 2, MOVE_AMP["walk"]["y"], phase=-1.5708)})
    clips.append(c)

    # --- attack_melee：巨斧过顶蓄力 → 命中 tick 下劈横扫 → 收招 ---
    c = Clip("attack_melee", 1.1)
    c.rot("arm_r", {"x": env(1.1, [(0.10, -40), (0.34, -118), (0.50, -126), (0.55, 58), (0.72, 30), (0.94, 6)]),
                    "z": env(1.1, [(0.20, -14), (0.50, -26), (0.55, 16), (0.78, 8), (0.98, 2)])})
    c.rot("forearm_r", {"x": env(1.1, [(0.20, -22), (0.50, -34), (0.55, 12), (0.80, 6)])})
    c.rot("axe", {"x": env(1.1, [(0.16, 10), (0.50, 24), (0.55, -18), (0.74, -8), (0.96, -2)])})
    c.rot("arm_l", {"x": env(1.1, [(0.30, -18), (0.55, 14), (0.86, 4)])})
    c.rot("spine", {"y": env(1.1, [(0.16, -14), (0.50, -20), (0.55, 22), (0.74, 14), (0.98, 3)]),
                    "x": env(1.1, [(0.20, -8), (0.55, 12), (0.80, 5)])})
    c.rot("chest", {"y": env(1.1, [(0.30, -12), (0.55, 16), (0.84, 5)])})
    c.rot("hip", {"y": env(1.1, [(0.40, -8), (0.55, 10), (0.86, 3)])})
    c.rot("head", {"y": env(1.1, [(0.20, -10), (0.55, 12), (0.88, 4)]), "x": env(1.1, [(0.36, -6), (0.55, 8), (0.90, 3)])})
    c.rot("leg_l", {"x": env(1.1, [(0.34, -10), (0.55, 12), (0.86, 4)])})
    c.rot("leg_r", {"x": env(1.1, [(0.34, 8), (0.55, -10), (0.86, -3)])})
    c.rot("cape", {"x": env(1.1, [(0.30, 8), (0.55, -14), (0.80, -6)])})
    c.rot("cape2", {"x": env(1.1, [(0.34, 11), (0.58, -18), (0.84, -8)])})
    c.rot("cape3", {"x": env(1.1, [(0.38, 14), (0.62, -22), (0.88, -10)])})
    c.rot("cage_band1", {"y": env(1.1, [(0.30, 26), (0.55, -18), (0.86, 6)])})
    c.rot("cage_band2", {"y": env(1.1, [(0.30, -26), (0.55, 18), (0.86, -6)])})
    c.rot("pauldron_r", {"z": env(1.1, [(0.36, -10), (0.55, 9), (0.88, 2)])})
    c.pos("move", {"y": env(1.1, [(0.40, -1.0), (0.55, 0.7), (0.88, 0.2)]),
                   "z": env(1.1, [(0.42, -1.4), (0.55, -1.0), (0.90, -0.3)])})
    clips.append(c)

    # --- attack_ranged：骨刺齐射（抬手集气 → 命中 tick 甩出，颚部开合） ---
    c = Clip("attack_ranged", 1.3)
    c.rot("arm_l", {"x": env(1.3, [(0.16, -34), (0.62, -104), (0.85, -36), (1.06, -12)]),
                    "z": env(1.3, [(0.20, 10), (0.62, 30), (0.85, -6), (1.10, -2)])})
    c.rot("forearm_l", {"x": env(1.3, [(0.24, -18), (0.62, -42), (0.85, 8), (1.10, 3)])})
    c.rot("hand_l", {"z": env(1.3, [(0.30, 6), (0.62, 22), (0.85, -8)])})
    c.rot("jaw", {"x": env(1.3, [(0.30, -12), (0.72, -26), (0.85, 7), (1.08, 2)])})
    c.rot("head", {"x": env(1.3, [(0.40, -10), (0.85, 12), (1.10, 4)]), "z": env(1.3, [(0.50, -6), (0.85, 8)])})
    c.rot("spine", {"x": env(1.3, [(0.40, -9), (0.85, 13), (1.14, 4)]), "y": env(1.3, [(0.60, 8), (0.85, -10), (1.14, -3)])})
    c.rot("chest", {"x": env(1.3, [(0.55, -6), (0.85, 9), (1.16, 3)])})
    c.rot("arm_r", {"x": env(1.3, [(0.50, 10), (0.85, -8), (1.16, -2)])})
    c.rot("cape", {"x": env(1.3, [(0.40, -12), (0.85, 10), (1.16, 4)])})
    c.rot("cape2", {"x": env(1.3, [(0.46, -16), (0.88, 13), (1.20, 5)])})
    c.rot("cape3", {"x": env(1.3, [(0.52, -20), (0.92, 16), (1.24, 6)])})
    c.rot("cage_band1", {"y": env(1.3, [(0.60, 40), (0.88, -24), (1.20, 8)])})
    c.rot("cage_band2", {"y": env(1.3, [(0.60, -40), (0.88, 24), (1.20, -8)])})
    c.pos("move", {"y": env(1.3, [(0.50, -0.8), (0.85, 0.5), (1.20, 0.2)]),
                   "z": env(1.3, [(0.62, 1.4), (0.85, -1.0), (1.22, -0.3)])})
    clips.append(c)

    # --- summon：尸笼高速旋转 → 命中 tick 双臂下拍，笼中魂火拔高，召唤尸群 ---
    c = Clip("summon", 1.8)
    c.rot("arm_l", {"x": env(1.8, [(0.24, -30), (0.86, -96), (1.10, 34), (1.42, 14)]),
                    "z": env(1.8, [(0.30, 24), (0.86, 62), (1.10, 18), (1.46, 6)])})
    c.rot("arm_r", {"x": env(1.8, [(0.24, -30), (0.86, -96), (1.10, 34), (1.42, 14)]),
                    "z": env(1.8, [(0.30, -24), (0.86, -62), (1.10, -18), (1.46, -6)])})
    c.rot("forearm_l", {"x": env(1.8, [(0.40, -20), (0.86, -48), (1.10, 10), (1.48, 4)])})
    c.rot("forearm_r", {"x": env(1.8, [(0.40, -20), (0.86, -48), (1.10, 10), (1.48, 4)])})
    c.rot("spine", {"x": env(1.8, [(0.36, -6), (0.86, -18), (1.10, 16), (1.50, 6)])})
    c.rot("chest", {"x": env(1.8, [(0.50, -5), (0.86, -13), (1.10, 12), (1.54, 5)])})
    c.rot("head", {"x": env(1.8, [(0.30, -8), (0.86, -30), (1.10, 10), (1.46, 4)])})
    c.rot("jaw", {"x": env(1.8, [(0.40, -18), (0.86, -34), (1.10, 4), (1.52, 2)])})
    c.rot("cage_band1", {"y": env(1.8, [(0.30, 70), (0.86, 260), (1.10, 300), (1.55, 120)])})
    c.rot("cage_band2", {"y": env(1.8, [(0.30, -70), (0.86, -260), (1.10, -300), (1.55, -120)])})
    c.rot("cage_soul", {"x": env(1.8, [(0.50, -12), (0.86, -26), (1.10, 8), (1.50, 3)])})
    c.rot("cape", {"x": env(1.8, [(0.40, -14), (0.86, -24), (1.10, 12), (1.52, 5)])})
    c.rot("cape2", {"x": env(1.8, [(0.46, -18), (0.86, -30), (1.14, 15), (1.56, 6)])})
    c.rot("cape3", {"x": env(1.8, [(0.52, -22), (0.86, -36), (1.18, 18), (1.60, 7)])})
    c.rot("leg_l", {"x": env(1.8, [(0.60, -8), (1.10, 10), (1.50, 4)])})
    c.rot("leg_r", {"x": env(1.8, [(0.60, -8), (1.10, 10), (1.50, 4)])})
    c.pos("move", {"y": env(1.8, [(0.60, 1.8), (0.86, 2.4), (1.10, -2.2), (1.52, -0.6)])})
    c.pos("cage_soul", {"y": env(1.8, [(0.50, 0.6), (0.86, 1.6), (1.10, 0.4), (1.52, 0.1)])})
    clips.append(c)

    # --- skill_quake：下蹲蓄力 → 命中 tick 双脚踏地（冲击波）→ 收招 ---
    c = Clip("skill_quake", 1.4)
    c.rot("leg_l", {"x": env(1.4, [(0.20, 14), (0.66, 18), (0.70, -6), (1.00, -3)])})
    c.rot("leg_r", {"x": env(1.4, [(0.20, 14), (0.66, 18), (0.70, -6), (1.00, -3)])})
    c.rot("shin_l", {"x": env(1.4, [(0.20, -22), (0.66, -28), (0.70, 6), (1.04, 3)])})
    c.rot("shin_r", {"x": env(1.4, [(0.20, -22), (0.66, -28), (0.70, 6), (1.04, 3)])})
    c.rot("hip", {"x": env(1.4, [(0.26, 10), (0.66, 13), (0.70, -5), (1.06, -2)])})
    c.rot("spine", {"x": env(1.4, [(0.26, 12), (0.66, 15), (0.70, -8), (1.06, -3)])})
    c.rot("chest", {"x": env(1.4, [(0.34, 8), (0.66, 11), (0.70, -6), (1.10, -2)])})
    c.rot("head", {"x": env(1.4, [(0.30, 10), (0.66, 14), (0.70, -12), (1.12, -4)])})
    c.rot("jaw", {"x": env(1.4, [(0.40, -10), (0.70, -28), (0.96, -8)])})
    c.rot("arm_l", {"x": env(1.4, [(0.20, 18), (0.66, 26), (0.70, -22), (1.06, -8)]),
                    "z": env(1.4, [(0.30, 8), (0.70, 30), (1.10, 10)])})
    c.rot("arm_r", {"x": env(1.4, [(0.20, 18), (0.66, 26), (0.70, -22), (1.06, -8)]),
                    "z": env(1.4, [(0.30, -8), (0.70, -30), (1.10, -10)])})
    c.rot("axe", {"x": env(1.4, [(0.30, -10), (0.70, 14), (1.08, 5)])})
    c.rot("cage_band1", {"y": env(1.4, [(0.40, 30), (0.70, -60), (1.10, 20)])})
    c.rot("cage_band2", {"y": env(1.4, [(0.40, -30), (0.70, 60), (1.10, -20)])})
    c.rot("cape", {"x": env(1.4, [(0.30, 14), (0.70, -20), (1.08, -8)])})
    c.rot("cape2", {"x": env(1.4, [(0.36, 18), (0.74, -26), (1.14, -10)])})
    c.rot("cape3", {"x": env(1.4, [(0.42, 22), (0.78, -32), (1.20, -12)])})
    c.pos("move", {"y": env(1.4, [(0.30, -3.4), (0.66, -4.6), (0.70, 1.4), (1.06, 0.5)])})
    clips.append(c)

    # --- skill_rage：Phase 3 进场（血怒变身）—— 骨冠仰天、双臂张开、尸笼狂转 ---
    c = Clip("skill_rage", 2.0)
    c.rot("arm_l", {"x": env(2.0, [(0.20, -18), (0.86, -24), (1.30, -20), (1.70, -8)]),
                    "z": env(2.0, [(0.24, 30), (0.86, 78), (1.30, 70), (1.76, 22)])})
    c.rot("arm_r", {"x": env(2.0, [(0.20, -18), (0.86, -24), (1.30, -20), (1.70, -8)]),
                    "z": env(2.0, [(0.24, -30), (0.86, -78), (1.30, -70), (1.76, -22)])})
    c.rot("forearm_l", {"x": env(2.0, [(0.30, -14), (0.86, -22), (1.30, -18), (1.80, -6)])})
    c.rot("forearm_r", {"x": env(2.0, [(0.30, -14), (0.86, -22), (1.30, -18), (1.80, -6)])})
    c.rot("spine", {"x": env(2.0, [(0.24, -8), (0.86, -20), (1.30, -16), (1.84, -5)]),
                    "z": sine(2.0, 6, 1.6)})
    c.rot("chest", {"x": env(2.0, [(0.40, -6), (0.86, -14), (1.30, -11), (1.86, -4)])})
    c.rot("head", {"x": env(2.0, [(0.20, -14), (0.80, -34), (1.30, -28), (1.88, -8)])})
    c.rot("jaw", {"x": env(2.0, [(0.26, -20), (0.80, -38), (1.40, -30), (1.90, -6)])})
    c.rot("crown", {"x": env(2.0, [(0.40, -8), (0.86, -14), (1.40, -10), (1.92, -3)])})
    c.rot("horn_l", {"z": env(2.0, [(0.40, 10), (0.86, 18), (1.40, 14), (1.92, 4)])})
    c.rot("horn_r", {"z": env(2.0, [(0.40, -10), (0.86, -18), (1.40, -14), (1.92, -4)])})
    c.rot("cage_band1", {"y": env(2.0, [(0.30, 90), (0.86, 320), (1.40, 420), (1.94, 150)])})
    c.rot("cage_band2", {"y": env(2.0, [(0.30, -90), (0.86, -320), (1.40, -420), (1.94, -150)])})
    c.rot("cage_soul", {"x": env(2.0, [(0.40, -16), (0.86, -30), (1.40, -24), (1.94, -6)])})
    c.rot("cape", {"x": env(2.0, [(0.30, -18), (0.86, -34), (1.40, -28), (1.96, -7)])})
    c.rot("cape2", {"x": env(2.0, [(0.36, -22), (0.90, -40), (1.44, -33), (1.98, -8)])})
    c.rot("cape3", {"x": env(2.0, [(0.42, -26), (0.94, -46), (1.48, -38), (2.0, -9)])})
    c.rot("cape_wl", {"z": env(2.0, [(0.40, 12), (0.94, 34), (1.48, 28), (2.0, 8)])})
    c.rot("cape_wr", {"z": env(2.0, [(0.40, -12), (0.94, -34), (1.48, -28), (2.0, -8)])})
    c.rot("leg_l", {"z": env(2.0, [(0.40, -7), (0.94, -12), (1.48, -10)]),
                    "x": env(2.0, [(0.50, -6), (0.94, -10), (1.48, -8)])})
    c.rot("leg_r", {"z": env(2.0, [(0.40, 7), (0.94, 12), (1.48, 10)]),
                    "x": env(2.0, [(0.50, -6), (0.94, -10), (1.48, -8)])})
    c.pos("move", {"y": env(2.0, [(0.40, 2.0), (0.86, 3.2), (1.40, 2.8), (2.0, 0.8)])})
    clips.append(c)

    # --- skill_death：亡语崩解（跪伏 → 命中 tick 炸开 → 塌回） ---
    c = Clip("skill_death", 1.6)
    c.rot("spine", {"x": env(1.6, [(0.24, 16), (0.82, 40), (0.90, -22), (1.34, -8)])})
    c.rot("chest", {"x": env(1.6, [(0.34, 12), (0.82, 30), (0.90, -16), (1.38, -6)])})
    c.rot("head", {"x": env(1.6, [(0.24, 10), (0.82, 24), (0.90, -26), (1.40, -8)])})
    c.rot("jaw", {"x": env(1.6, [(0.30, -12), (0.82, -18), (0.90, -34), (1.44, -8)])})
    c.rot("arm_l", {"x": env(1.6, [(0.20, -12), (0.82, -26), (0.90, -64), (1.40, -20)]),
                    "z": env(1.6, [(0.30, 10), (0.82, 18), (0.90, 54), (1.44, 16)])})
    c.rot("arm_r", {"x": env(1.6, [(0.20, -12), (0.82, -26), (0.90, -64), (1.40, -20)]),
                    "z": env(1.6, [(0.30, -10), (0.82, -18), (0.90, -54), (1.44, -16)])})
    c.rot("leg_l", {"x": env(1.6, [(0.26, 14), (0.82, 34), (0.90, 10), (1.42, 4)])})
    c.rot("leg_r", {"x": env(1.6, [(0.26, 14), (0.82, 34), (0.90, 10), (1.42, 4)])})
    c.rot("shin_l", {"x": env(1.6, [(0.26, -16), (0.82, -40), (0.90, -10), (1.44, -4)])})
    c.rot("shin_r", {"x": env(1.6, [(0.26, -16), (0.82, -40), (0.90, -10), (1.44, -4)])})
    c.rot("cage_band1", {"y": env(1.6, [(0.40, -40), (0.90, 180), (1.44, 60)])})
    c.rot("cage_band2", {"y": env(1.6, [(0.40, 40), (0.90, -180), (1.44, -60)])})
    c.rot("cage_soul", {"x": env(1.6, [(0.40, -14), (0.90, -30), (1.44, -8)])})
    c.rot("cape", {"x": env(1.6, [(0.34, 14), (0.90, -26), (1.44, -10)])})
    c.rot("cape2", {"x": env(1.6, [(0.40, 18), (0.94, -32), (1.48, -12)])})
    c.rot("cape3", {"x": env(1.6, [(0.46, 22), (0.98, -38), (1.52, -14)])})
    c.pos("move", {"y": env(1.6, [(0.30, -2.4), (0.82, -6.0), (0.90, 1.2), (1.48, 0.4)])})
    clips.append(c)

    for c in clips:
        c.finalize()
    retarget_move(clips)
    return clips


def retarget_move(clips):
    """按 MOVE_AMP 重标 move 骨位移：形状不动，只把幅度放大到看得见的量级。"""
    for c in clips:
        table = MOVE_AMP.get(c.name)
        if not table:
            continue
        pos = c.data.get("move", {}).get("position")
        if not pos:
            continue
        for axis, target in table.items():
            keys = pos.get(axis)
            if not keys:
                continue
            peak = max(abs(v) for v in keys.values())
            if peak <= 1e-9:
                continue
            factor = target / peak
            for t in keys:
                keys[t] = round(keys[t] * factor, 4)


# ---------------------------------------------------------------------------
# 4. geo / anim JSON
# ---------------------------------------------------------------------------
# GeckoLib 4.x 的 UVFaces 反序列化只认全名；单字母键会被静默丢掉 →
# BakedModelFactory.buildQuad 拿到 null 直接 return null → 该面不产生四边形。
FACE_FULL = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}


def build_geo():
    bones = []
    for b in BONES:
        cubes = []
        for c in CUBES:
            if c["bone"] != b["name"]:
                continue
            x0, y0, z0, x1, y1, z1 = c["box"]
            entry = {
                "origin": [x0, y0, z0],
                "size": [round(x1 - x0, 3), round(y1 - y0, 3), round(z1 - z0, 3)],
                "uv": {FACE_FULL[f]: c["uv"][f] for f in FACE_ORDER},
            }
            if c["flip"]:
                entry["mirror"] = True
            cubes.append(entry)
        bb = {"name": b["name"], "pivot": b["pivot"]}
        if b["parent"]:
            bb["parent"] = b["parent"]
        if cubes:
            bb["cubes"] = cubes
        bones.append(bb)
    heights = [c["box"][4] for c in CUBES]
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {
                "identifier": GEO_ID,
                "texture_width": TEX_W,
                "texture_height": TEX_H,
                "visible_bounds_width": 3.0,
                "visible_bounds_height": 4.5,
                "visible_bounds_offset": [0, 1.8, 0],
            },
            "bones": bones,
        }],
    }


def dump_json(paths, obj):
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    data = (text + "\n").encode("utf-8")
    sha = hashlib.sha256(data).hexdigest()
    shas = {}
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        shas[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return sha, shas


# Java 侧对应关系：(剪辑名, EliteAbility 枚举名, 命中点秒数)
ABILITY_MAP = (
    ("attack_melee", "BOSS_SWEEP", 0.55),
    ("attack_ranged", "BONE_VOLLEY", 0.85),
    ("summon", "RAISE_HORDE", 1.10),
    ("skill_quake", "GROUND_QUAKE", 0.70),
    ("skill_rage", "BLOOD_RAGE", 0.90),
    ("skill_death", "DEATH_WAIL", 0.90),
)


def main():
    geo = build_geo()
    clips = build_animations()
    anim = {"format_version": "1.8.0", "animations": {c.name: c.to_json() for c in clips}}

    art_geo, art_anim = ART / GEO_NAME, ART / ANIM_NAME
    src_geo = SRC_ASSETS / "geo" / GEO_NAME
    src_anim = SRC_ASSETS / "animations" / ANIM_NAME
    gsha, gshas = dump_json([art_geo, src_geo], geo)
    asha, ashas = dump_json([art_anim, src_anim], anim)

    manifest = {"texture": TEX_REL, "size": [TEX_W, TEX_H], "faces": MANIFEST,
                "samples": {k: list(v) for k, v in SAMPLE_RECT.items()},
                "density_tpu_div": DENSITY}
    ART.mkdir(parents=True, exist_ok=True)
    (ART / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report = {"geo_sha256": gsha, "anim_sha256": asha, "geo_copies": gshas, "anim_copies": ashas,
              "bones": len(BONES), "cubes": len(CUBES), "faces": len(MANIFEST),
              "density_tpu_div": DENSITY, "atlas_rows_used": PACK_USED, "checks": []}
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        report["checks"].append({"name": name, "pass": bool(cond), "detail": detail})

    names = [b["name"] for b in BONES]
    check("骨骼名唯一", len(names) == len(set(names)), f"{len(names)} 根")
    check("父骨存在", all((b["parent"] is None) or (b["parent"] in names) for b in BONES))
    check("体块引用骨骼存在", all(c["bone"] in names for c in CUBES))

    # GeckoLib 4.x 的 UVFaces 只读全名（north/south/...）：单字母键会被静默丢掉 →
    # 该面不产生四边形 → 实体不可见只剩阴影。
    uv_keys, uv_faces = set(), 0
    for gm in geo["minecraft:geometry"]:
        for b in gm["bones"]:
            for c in b.get("cubes", []):
                uv_keys |= set((c.get("uv") or {}).keys())
                uv_faces += len(c.get("uv") or {})
    short = [k for k in sorted(uv_keys) if k in ("n", "e", "s", "w", "u", "d")]
    check("geo UV 面键为全名（GeckoLib 只认全名）", not short,
          f"面键 {len(uv_keys)} 种" + (f" / 单字母残留 {short} ✗" if short else ""))
    check("每个立方体 6 面 UV 齐全", uv_faces == len(CUBES) * 6,
          f"{uv_faces} 面 / 期望 {len(CUBES) * 6}")
    check("geo 里没有骨骼旋转（rest 全零旋转）",
          all("rotation" not in b for b in geo["minecraft:geometry"][0]["bones"]))
    check("geo 里没有骨骼缩放",
          all("scale" not in b for b in geo["minecraft:geometry"][0]["bones"]))
    check("动画骨骼都在 geo 里", all(b in names for c in clips for b in c.data),
          str(sorted({b for c in clips for b in c.data if b not in names})))
    check("动画只有 rotation/position（禁止缩放式假动画）",
          all(ch in ("rotation", "position") for c in clips for b in c.data for ch in c.data[b]))
    check("动画不含 scale 通道",
          all("scale" not in c.data[b].get("rotation", {}) for c in clips for b in c.data))

    # GeckoLib 的解析契约（4.8.4 BakedAnimationsAdapter.addBedrockKeyframes）：
    # 通道值必须是「时间 → 三元向量」—— 数组，或含 vector / post / pre 的对象。
    # 之前生成器把内部 per-axis 结构原样写盘（{"x": {"0.0": 0.0}}），GeckoLib 读第一个
    # 键 "x" 当时间、把 {"0.0":0.0,...} 当值 → 'Invalid keyframe data - expected array'。
    # 后果不只是「动画不播」：异常抛在资源重载里，整次重载失败，客户端清掉用户选中的
    # 资源包（全屏文字变方框）。这条断言是唯一能防住它的地方。
    def _vec_ok(v):
        if isinstance(v, list):
            return len(v) == 3 and all(isinstance(n, (int, float)) for n in v)
        if isinstance(v, dict):
            if "vector" in v:
                return _vec_ok(v["vector"])
            if "post" in v or "pre" in v:
                return all(k not in v or _vec_ok(v[k]) for k in ("post", "pre"))
        return False

    shape_bad = []
    for clip_name, cobj in anim["animations"].items():
        for bone, chans in cobj["bones"].items():
            for chan, val in chans.items():
                if chan not in ("rotation", "position"):
                    shape_bad.append(f"{clip_name}/{bone}/{chan} 通道名非法")
                    continue
                for t, v in val.items():
                    try:
                        float(t)
                    except (TypeError, ValueError):
                        shape_bad.append(f"{clip_name}/{bone}/{chan} 时间键非数字 {t!r}")
                        break
                    if not _vec_ok(v):
                        shape_bad.append(f"{clip_name}/{bone}/{chan}@{t} 不是向量 {v!r}")
                        break
    check("动画通道符合 GeckoLib 形状（时间 → [x,y,z]）", not shape_bad,
          f"{len(anim['animations'])} 段" + (f" 违规 {shape_bad[:3]}" if shape_bad else ""))

    # 每个非 loop 剪辑首尾归零；loop 剪辑首尾一致
    for c in clips:
        for bone, chans in c.data.items():
            for ch, axes in chans.items():
                for ax, ks in axes.items():
                    ts = sorted(ks)
                    check(f"{c.name}.{bone}.{ch}.{ax} 有 ≥2 关键帧", len(ts) >= 2, str(ts))
                    if c.loop:
                        has0 = 0.0 in ks and c.length in ks
                        eq = has0 and abs(ks[0.0] - ks[c.length]) < 1e-6
                        check(f"{c.name}.{bone}.{ch}.{ax} 循环接缝一致（0 = 片尾）", eq, f"keys={ts}")
                    else:
                        check(f"{c.name}.{bone}.{ch}.{ax} 收招归零",
                              abs(ks.get(0.0, 9)) < 1e-6 and abs(ks.get(c.length, 9)) < 1e-6,
                              f"{ks.get(0.0)} -> {ks.get(c.length)}")

    # 位移幅度：走查 MOVE_AMP，确认没有「等于没动」的剪辑
    for c in clips:
        amp = MOVE_AMP.get(c.name)
        if not amp:
            continue
        pos = c.data.get("move", {}).get("position", {})
        for axis, target in amp.items():
            keys = pos.get(axis)
            got = max(abs(v) for v in keys.values()) if keys else 0.0
            check(f"{c.name} 位移 {axis} 达到语义幅度 {target}u",
                  abs(got - target) < 0.05, f"{got:.2f}u")

    # UV：越界 / 重叠 / 采样密度
    used = [[0] * TEX_H for _ in range(TEX_W)]
    overlap = []
    for m in MANIFEST:
        u, v, w, h = m["rect"]
        if not (0 <= u and 0 <= v and u + w <= TEX_W and v + h <= TEX_H):
            overlap.append(("越界", m["part"], m["face"], m["rect"]))
            continue
        if m["painter"].startswith("@"):
            continue
        for yy in range(v, v + h):
            row = used[yy]
            for xx in range(u, u + w):
                if row[xx]:
                    overlap.append(("重叠", m["part"], m["face"], m["rect"]))
                row[xx] = 1
    check("UV 无越界/无重叠", not overlap, str(overlap[:5]))
    texels = sum(m["rect"][2] * m["rect"][3] for m in MANIFEST if not m["painter"].startswith("@"))
    report["atlas_texels"] = texels
    report["atlas_usage"] = round(texels / float(TEX_W * TEX_H) * 100, 2)
    check("图集占用 < 70%（留出重绘余量）", report["atlas_usage"] < 70.0,
          f"{report['atlas_usage']}%")

    # 脸部面板密度：脸必须比躯干高一档，否则五官在这个体量上读不出来
    face_tpu = [m["tpu"] for m in MANIFEST if m["painter"] == "face"]
    check(f"脸部面板密度 = {FACE_TPU // TPU_DIV}px/u（躯干的 {FACE_TPU // DEFAULT_TPU} 倍）",
          bool(face_tpu) and min(face_tpu) >= FACE_TPU, f"tpu={face_tpu}")
    check("四指/爪骨存在", all(f"claw_{t}{i}" in names for t in ("l", "r") for i in (1, 2, 3)))

    # 尺寸：Boss 必须明显高于普通僵尸（1.95 格 = 31u）
    top = max(c["box"][4] for c in CUBES)
    height_blocks = top / 16.0
    report["height_u"], report["height_blocks"] = top, round(height_blocks, 3)
    check("Boss 身高 ≥ 3 格（普通僵尸 1.95 格）", height_blocks >= 3.0, f"{height_blocks:.2f} 格")

    # Java 侧双向同步
    jm = ROOT / "src/main/java/com/apocalypse/zombies/client/model/OverlordGeoModel.java"
    jz = ROOT / "src/main/java/com/apocalypse/zombies/entity/HordeOverlord.java"
    je = ROOT / "src/main/java/com/apocalypse/zombies/entity/EliteAbility.java"
    jt = jm.read_text(encoding="utf-8") if jm.exists() else ""
    jzt = jz.read_text(encoding="utf-8") if jz.exists() else ""
    jet = je.read_text(encoding="utf-8") if je.exists() else ""
    check("OverlordGeoModel 存在", bool(jt), str(jm))
    check("HordeOverlord 存在且是 GeoEntity",
          "implements GeoEntity" in jzt or "GeoEntity" in jzt)

    def jconst(name, text):
        m = re.search(rf"{name}\s*=\s*(-?[0-9.]+)F", text)
        return float(m.group(1)) if m else None

    def jexpr(name, text):
        """取 Java 常量声明的右值表达式：分段阈值在 Java 侧是派生式，只认字面量会误报。"""
        m = re.search(rf"{name}\s*=\s*([^;]+);", text)
        return m.group(1).strip() if m else ""

    def jeval(expr, text):
        """只放行数字 / BOSS_MAX_HEALTH / 四则运算的算术式求值。"""
        if not re.fullmatch(r"[0-9A-Za-z_.\s+\-*/()]+", expr or ""):
            return None
        base = jconst("BOSS_MAX_HEALTH", text)
        if base is None:
            return None
        safe = expr.replace("BOSS_MAX_HEALTH", repr(base)).replace("F", "").replace("D", "")
        try:
            return float(eval(safe, {"__builtins__": {}}, {}))
        except Exception:
            return None

    got_max = jconst("BOSS_MAX_HEALTH", jzt)
    check(f"Java 常量 BOSS_MAX_HEALTH == {BOSS_MAX_HEALTH}",
          got_max is not None and abs(got_max - BOSS_MAX_HEALTH) < 1e-6, f"java={got_max}")
    for cname, want in (("PHASE2_HP", PHASE2_HP), ("PHASE3_HP", PHASE3_HP)):
        expr = jexpr(cname, jzt)
        got = jeval(expr, jzt)
        check(f"Java 常量 {cname} 派生自 BOSS_MAX_HEALTH 且 == {want}",
              "BOSS_MAX_HEALTH" in expr and got is not None and abs(got - want) < 1e-6,
              f"java={expr or '读不到'} → {got}")
    # 原版 MAX_HEALTH 夹到 1024（且 calculateValue() 结尾还会再夹一次）：总量超上限就必须抬 maxValue
    if BOSS_MAX_HEALTH > 1024.0:
        jme = ROOT / "src/main/java/com/apocalypse/zombies/registry/ModEntities.java"
        jmet = jme.read_text(encoding="utf-8") if jme.exists() else ""
        check("Java 侧抬高了 MAX_HEALTH 上限（ModEntities 反射抬 maxValue；只写大常量或挂修饰符都无效）",
              "liftHealthCap" in jmet)
    for clip in [c.name for c in clips]:
        check(f'Java 剪辑名 "{clip}" 存在', f'"{clip}"' in jzt, "HordeOverlord 里的常量")
    for clip, enum_name, strike in ABILITY_MAP:
        m = re.search(rf"\b{enum_name}\((\d+),\s*(-?\d+)\)", jet)
        c = next((x for x in clips if x.name == clip), None)
        if not m or c is None:
            check(f"{clip} 与 {enum_name} 对齐", False, f"enum={bool(m)} clip={bool(c)}")
            continue
        dur, imp = int(m.group(1)), int(m.group(2))
        check(f"{clip} 时长 {c.length}s == {enum_name} 的 {dur} tick",
              abs(c.length * 20 - dur) < 0.5, f"{c.length * 20:.0f} vs {dur}")
        check(f"{clip} 命中点 {strike}s == {enum_name} 的冲击 {imp} tick",
              abs(strike * 20 - imp) < 0.5, f"{strike * 20:.0f} vs {imp}")

    report["clips"] = {c.name: {"length": c.length, "loop": c.loop,
                                "bones": sorted(c.bones_touched())} for c in clips}
    report["all_pass"] = ok
    (ART / "boss_v1_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"geo : {art_geo}  sha256={gsha}")
    print(f"anim: {art_anim}  sha256={asha}")
    print(f"art↔src geo  一致: {gshas[str(art_geo)] == gshas[str(src_geo)]}")
    print(f"art↔src anim 一致: {ashas[str(art_anim)] == ashas[str(src_anim)]}")
    print(f"骨骼 {len(BONES)} / 体块 {len(CUBES)} / 面 {len(MANIFEST)} / "
          f"躯干密度 {DEFAULT_TPU / TPU_DIV:.2f}px·u⁻¹ / 图集占用 {report['atlas_usage']}% "
          f"({texels} texels, {TEX_W}×{TEX_H}) / 身高 {height_blocks:.2f} 格")
    for c in report["checks"]:
        if not c["pass"]:
            print(f"  FAIL {c['name']} {c['detail']}")
    print(f"自校验: {'全部通过' if ok else '有失败项'} "
          f"({sum(1 for c in report['checks'] if c['pass'])}/{len(report['checks'])})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
