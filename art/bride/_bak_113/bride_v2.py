#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""美女僵尸 Phase 2 生成器 —— GeckoLib 骨骼模型（geometry + animation + 图集清单 + 自校验）。

设计约定（与 meishu.md 一致，且**不做任何坐标取反**）：
  * 16u = 1 Block；+Y = 上；-Z = 面部朝向（正面）；+X = 角色自己的右手边。
  * 本生成器**内部空间就是游戏/Bedrock 空间**，写进 JSON 的就是最终坐标，
    所以 Blockbench 打开看到的、Blender 用同一份 JSON 渲出来的、游戏里渲染的，三者是同一套坐标。
    （十字弩那套 `game_convention_*` 取反是它自己的历史约定，这里不复用，避免二次取反。）
  * 曲面体块一律走「Generate Shape」思路：用多块薄板围成八角环（oct ring），
    而不是一整块大方块——这样正面/侧面/四角各自有独立 UV 矩形，贴图能画出圆润的明暗过渡。
  * 动画只驱动骨骼的 Translation / Rotation，**绝不写 scale 通道**（整模型缩放会破坏碰撞箱手感）。
  * **命名约定**：`_l` = 角色左手边（x<0）、`_r` = 角色右手边（x>0）；**骨骼名必须与其 pivot/盒体同侧**
    （动画按骨骼名取 pivot，反侧会让部件绕对侧 pivot 甩出去）。纯 UV 部件标签（`collar_side_*` 等）沿用
    历史约定、只决定贴图分区，不影响骨骼，改贴图时才需要关心。

产物：
  art/bride/bride_zombie.geo.json         + src/.../geo/bride_zombie.geo.json
  art/bride/bride_zombie.animation.json   + src/.../animations/bride_zombie.animation.json
  art/bride/bride_atlas.json              图集清单（贴图脚本读它来作画）
  art/bride/bride_v2_report.json          自校验 + sha256 汇报
贴图由 tools/bride_v2_skin.py 依据 bride_atlas.json 生成（128×128，双层皮肤布局）。
"""

import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = ROOT / "art" / "bride"
SRC_ASSETS = ROOT / "src" / "main" / "resources" / "assets" / "apocalypse_zombies"
MOD = "apocalypse_zombies"

GEO_NAME = "bride_zombie.geo.json"
ANIM_NAME = "bride_zombie.animation.json"
TEX_NAME = "bride_zombie.png"          # 贴图新家：textures/entity/bride/
TEX_REL = "textures/entity/bride/" + TEX_NAME

TEX_W = 128                     # 1u = 1px（= 原版皮肤密度）；128×128 双层皮肤布局
TEX_H = 128

# ---------------------------------------------------------------------------
# 0. 骨骼表（pivot 是模型空间绝对坐标，单位 u）
# ---------------------------------------------------------------------------

BONES = []
CUBES = []


def bone(name, pivot, parent=None):
    BONES.append({"name": name, "pivot": [round(v, 3) for v in pivot], "parent": parent})


def _paint_map(paint, hidden):
    """把 paint 规格规范化成 {面: 值}；值 = 字符串名 或 (名字, kwargs)。"""
    faces = ("n", "s", "e", "w", "u", "d")
    if isinstance(paint, str) or isinstance(paint, tuple):
        out = {f: paint for f in faces}
    else:
        out = {f: paint.get(f, "@lining") for f in faces}
    for ch in hidden:
        out[ch] = "@lining"
    return out


def cube(bone_name, box, paint, hidden="", part="", flip=False, tpu=None):
    """box = (x0,y0,z0,x1,y1,z1)，单位 u。paint 见 _paint_map。"""
    x0, y0, z0, x1, y1, z1 = [round(float(v), 3) for v in box]
    x0, x1 = sorted((x0, x1))          # 左右镜像写法会给出反向的 x，这里统一成 min/max
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


# 八角环：八个薄板围成一根「圆润柱体」，每块板材都有独立的正面/侧面 UV。
#   hx/hz = 半宽/半深；ax/bz = 正面板半宽 / 侧板半深（也就是切角的位置）。
PANEL_BOX = {}   # 由 _oct_boxes 填充


def _oct_boxes(y0, y1, hx, hz, ax, bz):
    return {
        "n":  (-ax, y0, -hz, ax, y1, -bz),     # 正面板
        "s":  (-ax, y0, bz, ax, y1, hz),       # 后面板
        "e":  (ax, y0, -bz, hx, y1, bz),       # 右侧板
        "w":  (-hx, y0, -bz, -ax, y1, bz),     # 左侧板
        "fe": (ax, y0, -hz, hx, y1, -bz),      # 前右角
        "fw": (-hx, y0, -hz, -ax, y1, -bz),    # 前左角
        "be": (ax, y0, bz, hx, y1, hz),        # 后右角
        "bw": (-hx, y0, bz, -ax, y1, hz),      # 后左角
    }


PANEL_FACES = {
    "n": ("n",), "s": ("s",), "e": ("e",), "w": ("w",),
    "fe": ("n", "e"), "fw": ("n", "w"), "be": ("s", "e"), "bw": ("s", "w"),
}


def oct_ring(bone_name, y0, y1, hx, hz, ax, bz, out, part, tpu=None,
             cap_up=None, cap_down=None, mid_cap="@cloth_dark", flip=False,
             panels=("n", "s", "e", "w", "fe", "fw", "be", "bw")):
    """out: {面: paint 值}，只作用于该环的外表面。cap_up/cap_down 给顶/底切片。"""
    boxes = _oct_boxes(y0, y1, hx, hz, ax, bz)
    for p in panels:
        paint = {}
        for f in PANEL_FACES[p]:
            paint[f] = out.get(f, "@lining")
        paint["u"] = cap_up if cap_up else mid_cap
        paint["d"] = cap_down if cap_down else mid_cap
        # 非外表面一律走共享衬里图元（省贴图，且内壁颜色统一）
        for f in ("n", "s", "e", "w", "u", "d"):
            if f not in PANEL_FACES[p] or (p in ("n", "s", "e", "w") and f != PANEL_FACES[p][0]):
                if f not in ("u", "d"):
                    paint[f] = "@lining"
        cube(bone_name, boxes[p], paint, part=f"{part}_{p}", flip=flip, tpu=tpu)


def slab(bone_name, box, paint, hidden="", part="", flip=False, tpu=None):
    cube(bone_name, box, paint, hidden=hidden, part=part, flip=flip, tpu=tpu)


# ---------------------------------------------------------------------------
# 1. 骨骼树
# ---------------------------------------------------------------------------
bone("root", (0, 0, 0))
bone("move", (0, 0, 0), "root")
bone("hip", (0, 12.2, 0), "move")
bone("spine", (0, 15.0, 0), "hip")
bone("chest", (0, 17.8, 0), "spine")

# 胸部两瓣（规格：每瓣 2 宽 × 3 高 × 1 深，前伸躯干正面 1u，中缝 1u，左右对称）
bone("bust_l", (-1.5, 20.4, -2.35), "chest")
bone("bust_r", (1.5, 20.4, -2.35), "chest")

# 手臂链
bone("shoulder_l", (-3.8, 22.3, 0), "chest")
bone("arm_l", (-4.9, 22.3, 0), "shoulder_l")
bone("forearm_l", (-4.9, 16.6, 0), "arm_l")
bone("hand_l", (-4.9, 12.9, 0), "forearm_l")
bone("shoulder_r", (3.8, 22.3, 0), "chest")
bone("arm_r", (4.9, 22.3, 0), "shoulder_r")
bone("forearm_r", (4.9, 16.6, 0), "arm_r")
bone("hand_r", (4.9, 12.9, 0), "forearm_r")

# 头 / 发 / 面纱
bone("neck", (0, 22.8, 0), "chest")
bone("head", (0, 24.4, 0), "neck")
bone("fringe", (0, 29.0, -3.2), "head")
bone("hair_bun", (0, 30.4, 1.3), "head")
bone("hair_back", (0, 25.6, 2.5), "head")
bone("hair_side_l", (-3.5, 29.4, -0.4), "head")
bone("hair_side_r", (3.5, 29.4, -0.4), "head")
bone("veil", (0, 30.8, 4.4), "head")
bone("crown", (0, 30.6, -1.6), "head")
bone("hair_fall", (0, 22.0, 3.0), "chest")   # 肩以下的长发：挂在胸上，不跟头甩

# 腿
bone("leg_l", (-1.75, 12.2, 0), "hip")
bone("shin_l", (-1.75, 5.6, 0), "leg_l")
bone("foot_l", (-1.75, 2.1, 0), "shin_l")
bone("leg_r", (1.75, 12.2, 0), "hip")
bone("shin_r", (1.75, 5.6, 0), "leg_r")
bone("foot_r", (1.75, 2.1, 0), "shin_r")

# 裙摆：中/后板挂 skirt，两侧板挂 hem_r/hem_l（召唤/行礼时两侧能单独掀起）
bone("skirt", (0, 12.6, 0), "hip")
bone("hem_l", (-4.6, 9.4, 0), "skirt")
bone("hem_r", (4.6, 9.4, 0), "skirt")
bone("train", (0, 11.4, 2.8), "skirt")

# ---------------------------------------------------------------------------
# 2. 体块
# ---------------------------------------------------------------------------

# ---- 躯干：4 根八角环叠出「沙漏」轮廓（骨盆宽 → 腰最细 → 胸最丰） ----
oct_ring("hip", 12.2, 15.0, 3.9, 2.4, 2.6, 1.6,
         {"n": "silk", "s": "silk", "e": "silk", "w": "silk"},
         "pelvis", tpu=3, cap_up="@cloth_dark", cap_down="@cloth_dark")
oct_ring("spine", 15.0, 17.8, 3.15, 2.0, 2.2, 1.2,
         {"n": "bodice_lower", "s": "bodice_back", "e": "bodice_side", "w": "bodice_side"},
         "waist", tpu=3, cap_up="@cloth_dark", cap_down="@cloth_dark")
oct_ring("chest", 17.8, 20.2, 3.75, 2.4, 2.5, 1.55,
         {"n": "bodice_belt", "s": "bodice_back_low", "e": "bodice_side", "w": "bodice_side"},
         "chestA", tpu=3, cap_up="@cloth_dark", cap_down="@cloth_dark")
oct_ring("chest", 20.2, 22.8, 4.05, 2.4, 2.7, 1.6,
         {"n": "decollete", "s": "bodice_back", "e": "bodice_side", "w": "bodice_side"},
         "chestB", tpu=4, cap_up="@cloth_top", cap_down="@cloth_dark")

# 肩带：胸衣吊带从锁骨压到泡泡袖上
for s, sg in (("l", -1), ("r", 1)):
    slab("chest", (sg * 3.4, 22.0, -1.7, sg * 5.3, 22.9, 1.7), "bodice_strap",
         hidden="ud", part=f"strap_{s}", flip=(s == "l"), tpu=3)

# ---- 胸部两瓣（硬规格）----
# 主瓣：2 宽 × 3 高 × 1 深；背面 z=-2.29 略嵌进躯干，正面到 z=-3.35，
#       相对躯干正面平面 z=-2.35 的前伸量正好 1.00u。
BUST_Z_FRONT = -2.40        # 躯干正面平面（与 BrideGeoModel.CHEST_FRONT_Z 同步）
BUST_SIZE = (2.0, 3.0, 1.0)
BUST_GAP = 1.0
BUST_SOFT = (1.6, 1.0, 0.55)   # 下缘补瓣：让两瓣不是一块平板，前伸只有 0.55u

for tag, sg in (("l", -1), ("r", 1)):   # +X = 她自己的右手边
    flip = (sg > 0)
    inner = sg * 0.5          # 中缝内侧
    outer = sg * 2.5          # 外侧
    x0, x1 = sorted((inner, outer))
    z0 = BUST_Z_FRONT - BUST_SIZE[2]              # -3.40 → 前伸量正好 1.00u
    z1 = BUST_Z_FRONT + 0.06                      # -2.34（背面嵌进躯干 0.06，避免共面闪烁）
    y0 = 19.2
    y1 = y0 + BUST_SIZE[1]                        # 22.2
    slab("bust_" + tag, (x0, y0, z0, x1, y1, z1),
         {"n": ("bust_front", {"side": tag}), "e": ("bust_edge", {"side": tag, "outer": True}),
          "w": ("bust_edge", {"side": tag, "outer": False}), "u": "@cloth_top", "d": "@cloth_dark"},
         part=f"bust_{tag}", flip=flip, tpu=5)
    # 下缘补瓣：贴着主瓣下沿往前收，做「圆润下垂」的过渡
    sx0, sx1 = sorted((sg * 0.7, sg * 2.3))
    slab("bust_" + tag, (sx0, 18.4, BUST_Z_FRONT - BUST_SOFT[2], sx1, 19.3, BUST_Z_FRONT + 0.05),
         {"n": ("bust_soft", {"side": tag})}, hidden="swd", part=f"bust_soft_{tag}",
         flip=flip, tpu=5)

# ---- 颈 / 领口 / 项链 ----
slab("neck", (-1.5, 22.8, -1.5, 1.5, 25.4, 1.5), "neck_skin", hidden="ud", part="neck", tpu=4)
slab("chest", (-2.8, 22.55, -2.55, 2.8, 23.15, -1.9), "neck_lace",
     hidden="s", part="collar_front", tpu=4)
for s, sg in (("r", -1), ("l", 1)):
    slab("chest", (sg * 2.2, 22.45, -2.2, sg * 3.2, 23.1, 0.2), "neck_lace",
         hidden="", part=f"collar_side_{s}", flip=(s == "l"), tpu=3)
slab("neck", (-1.7, 23.4, -1.62, 1.7, 23.85, -1.30), "gold", hidden="s", part="choker", tpu=4)
slab("neck", (-0.45, 23.0, -1.78, 0.45, 23.75, -1.42), "gem", hidden="s", part="pendant", tpu=5)

# ---- 头：一根八角环（正面板就是脸） ----
oct_ring("head", 24.4, 31.6, 3.6, 3.75, 2.6, 2.5,
         {"n": "face_full", "s": "hair_back", "e": ("head_side", {"side": "r"}),
          "w": ("head_side", {"side": "l"})},
         "head", tpu=9, cap_up="hair_top", cap_down="@skin_dark")
# ---- 刘海 / 鬓发 / 发髻 / 后发 / 面纱 / 头饰 ----
slab("fringe", (-1.5, 29.2, -4.15, 1.5, 31.9, -3.55), "hair_fringe", hidden="s", part="fringe_mid", tpu=5)
slab("fringe", (1.5, 28.6, -4.05, 3.2, 31.9, -3.45), "hair_fringe_side", hidden="s",
     part="fringe_r", tpu=4)
slab("fringe", (-3.2, 28.6, -4.05, -1.5, 31.9, -3.45), "hair_fringe_side", hidden="s",
     part="fringe_l", flip=True, tpu=4)

for s, sg in (("l", -1), ("r", 1)):   # 骨骼名必须与 pivot/盒体同侧（动画按 bone 名取 pivot），故 _l→x<0
    x0, x1 = sorted((sg * 3.2, sg * 4.4))
    slab("hair_side_" + s, (x0, 25.6, -1.6, x1, 30.0, 1.4), "hair_side",
         hidden="us", part=f"sidehair_{s}", flip=(s == "l"), tpu=4)
    x0, x1 = sorted((sg * 3.3, sg * 4.2))
    slab("hair_side_" + s, (x0, 23.4, -1.2, x1, 25.8, 1.6), ("hair_side_tip", {"side": s}),
         hidden="us", part=f"sidehair_tip_{s}", flip=(s == "l"), tpu=4)

oct_ring("hair_bun", 30.2, 33.2, 2.1, 2.1, 1.5, 1.5,
         {"n": "hair_top", "s": "hair_bun", "e": "hair_bun", "w": "hair_bun"},
         "bun", tpu=4, cap_up="hair_bun_top", cap_down="@hair_dark")
slab("hair_bun", (-3.4, 31.3, 0.4, 3.4, 32.1, 1.2), "gold", hidden="ud", part="hairpin", tpu=4)

slab("hair_back", (-3.2, 27.4, 2.4, 3.2, 30.8, 4.0), "hair_back", hidden="nud",
     part="back_mid", tpu=4)
slab("hair_back", (-3.4, 25.2, 2.6, 3.4, 27.6, 4.3), "hair_back", hidden="nud",
     part="back_low", tpu=4)
slab("hair_back", (-3.0, 23.9, 2.8, 3.0, 25.4, 4.2), "hair_back", hidden="nud",
     part="nape", tpu=4)

slab("hair_fall", (-3.6, 19.4, 2.9, 3.6, 24.2, 4.4), "hair_fall", hidden="nu",
     part="fall_mid", tpu=4)
slab("hair_fall", (-3.2, 17.0, 3.0, 3.2, 19.6, 4.5), "hair_fall", hidden="nu",
     part="fall_low", tpu=4)
slab("hair_fall", (-2.6, 15.2, 3.1, 2.6, 17.2, 4.4), ("hair_fall_tip", {}), hidden="nu",
     part="fall_tip", tpu=4)

slab("veil", (-3.7, 25.4, 4.05, 3.7, 31.2, 5.00), ("veil_lace", {"band": 0}), hidden="nsu",
     part="veil_up", tpu=4)
slab("veil", (-4.3, 20.2, 4.15, 4.3, 25.6, 5.35), ("veil_lace", {"band": 1}), hidden="nsu",
     part="veil_low", tpu=4)

slab("crown", (-2.8, 30.8, -3.9, 2.8, 31.5, -3.2), "gold", hidden="s", part="tiara", tpu=4)
slab("crown", (-0.7, 31.3, -3.8, 0.7, 32.1, -3.1), "gem", hidden="s", part="tiara_gem", tpu=5)

# ---- 手臂 ----
for s, sg in (("l", -1), ("r", 1)):
    flip = (sg > 0)
    x0, x1 = sorted((sg * 3.1, sg * 5.4))
    slab("shoulder_" + s, (x0, 21.0, -1.8, x1, 23.3, 1.8), "sleeve_puff",
         hidden="ud", part=f"puff_{s}", flip=flip, tpu=3)
    x0, x1 = sorted((sg * 3.8, sg * 5.8))
    slab("arm_" + s, (x0, 19.6, -1.3, x1, 22.1, 1.3), "sleeve", hidden="ud",
         part=f"arm_up_{s}", flip=flip, tpu=3)
    x0, x1 = sorted((sg * 3.9, sg * 5.7))
    slab("arm_" + s, (x0, 17.0, -1.2, x1, 19.7, 1.2), "sleeve", hidden="ud",
         part=f"arm_mid_{s}", flip=flip, tpu=3)
    x0, x1 = sorted((sg * 3.9, sg * 5.7))
    slab("forearm_" + s, (x0, 13.6, -1.15, x1, 16.6, 1.15), "forearm_silk", hidden="ud",
         part=f"forearm_{s}", flip=flip, tpu=3)
    x0, x1 = sorted((sg * 3.6, sg * 6.0))
    slab("forearm_" + s, (x0, 12.6, -1.4, x1, 13.7, 1.4), "cuff_lace", hidden="ud",
         part=f"cuff_{s}", flip=flip, tpu=4)
    x0, x1 = sorted((sg * 4.05, sg * 5.55))
    slab("hand_" + s, (x0, 11.6, -0.85, x1, 12.9, 0.85), "hand", hidden="ud",
         part=f"hand_{s}", flip=flip, tpu=5)
    x0, x1 = sorted((sg * 3.8, sg * 4.35))
    slab("hand_" + s, (x0, 12.0, -1.2, x1, 12.9, -0.45), "hand", hidden="us",
         part=f"thumb_{s}", flip=flip, tpu=5)

# ---- 腿 ----
for s, sg in (("l", -1), ("r", 1)):
    flip = (sg > 0)
    x0, x1 = sorted((sg * 0.45, sg * 3.05))
    slab("leg_" + s, (x0, 8.8, -1.4, x1, 12.3, 1.4), "leg_skin", hidden="ud",
         part=f"thigh_{s}", flip=flip, tpu=4)
    x0, x1 = sorted((sg * 0.55, sg * 2.95))
    slab("leg_" + s, (x0, 5.6, -1.3, x1, 8.9, 1.3), "leg_skin", hidden="ud",
         part=f"thigh_low_{s}", flip=flip, tpu=4)
    x0, x1 = sorted((sg * 0.65, sg * 2.85))
    slab("shin_" + s, (x0, 2.6, -1.25, x1, 5.7, 1.25), "stocking", hidden="ud",
         part=f"calf_{s}", flip=flip, tpu=4)
    x0, x1 = sorted((sg * 0.9, sg * 2.6))
    slab("shin_" + s, (x0, 2.1, -1.15, x1, 2.7, 1.15), "stocking", hidden="ud",
         part=f"ankle_{s}", flip=flip, tpu=4)
    x0, x1 = sorted((sg * 0.6, sg * 2.9))
    slab("foot_" + s, (x0, 0.9, -2.6, x1, 2.2, 0.9), "shoe", hidden="",
         part=f"shoe_{s}", flip=flip, tpu=4)
    x0, x1 = sorted((sg * 0.65, sg * 2.85))
    slab("foot_" + s, (x0, 0.6, -2.55, x1, 1.0, 0.9), "sole", hidden="nu",
         part=f"sole_{s}", flip=flip, tpu=4)
    x0, x1 = sorted((sg * 1.1, sg * 2.4))
    slab("foot_" + s, (x0, 0.0, 0.3, x1, 0.65, 1.3), "heel", hidden="nu",
         part=f"heel_{s}", flip=flip, tpu=4)

# ---- 裙摆：三层（上摆 / 下摆 / 蕾丝边），八板分挂在 skirt / hem_r / hem_l 上 ----
SKIRT_PAINT = {"n": "skirt_front", "s": "skirt_back", "e": "skirt_side", "w": "skirt_side",
               "fe": "skirt_corner", "fw": "skirt_corner", "be": "skirt_corner", "bw": "skirt_corner"}
oct_ring("skirt", 9.8, 13.2, 4.05, 2.95, 2.75, 1.85, SKIRT_PAINT, "skirtA", tpu=3,
         cap_up="@cloth_dark", cap_down="@cloth_dark", panels=("n", "s"))
oct_ring("skirt", 7.6, 10.0, 5.7, 4.3, 3.8, 2.75, SKIRT_PAINT, "skirtB", tpu=3,
         cap_up="@cloth_dark", cap_down="@cloth_dark", panels=("n", "s"))
oct_ring("skirt", 6.9, 7.8, 6.2, 4.7, 4.2, 3.05, SKIRT_PAINT, "skirtLace", tpu=4,
         cap_up="@cloth_dark", cap_down="@cloth_dark", panels=("n", "s"))
for bn, panels in (("hem_r", ("e", "fe", "be")), ("hem_l", ("w", "fw", "bw"))):
    oct_ring(bn, 9.8, 13.2, 4.05, 2.95, 2.75, 1.85, SKIRT_PAINT, f"{bn}A", tpu=3,
             cap_up="@cloth_dark", cap_down="@cloth_dark", panels=panels)
    oct_ring(bn, 7.6, 10.0, 5.7, 4.3, 3.8, 2.75, SKIRT_PAINT, f"{bn}B", tpu=3,
             cap_up="@cloth_dark", cap_down="@cloth_dark", panels=panels)
    oct_ring(bn, 6.9, 7.8, 6.2, 4.7, 4.2, 3.05, SKIRT_PAINT, f"{bn}Lace", tpu=4,
             cap_up="@cloth_dark", cap_down="@cloth_dark", panels=panels)

# 拖尾
slab("train", (-3.4, 8.6, 3.0, 3.4, 11.8, 6.2), "skirt_back", hidden="nu",
     part="train_up", tpu=3)
slab("train", (-2.6, 7.0, 5.4, 2.6, 9.0, 8.4), "skirt_back", hidden="nu",
     part="train_low", tpu=3)

# ---- 腰带 / 蝴蝶结 ----
slab("hip", (-4.3, 13.4, -2.7, 4.3, 14.8, 2.7), "gold_belt", hidden="ud", part="belt", tpu=3)
slab("hip", (-1.6, 13.2, 3.15, 1.6, 15.0, 4.25), "bow", hidden="nd", part="bow_knot", tpu=4)
for s, sg in (("r", -1), ("l", 1)):
    x0, x1 = sorted((sg * 1.4, sg * 3.3))
    slab("hip", (x0, 13.4, 3.25, x1, 14.7, 4.15), "bow", hidden="d",
         part=f"bow_loop_{s}", flip=(s == "l"), tpu=4)
    x0, x1 = sorted((sg * 0.3, sg * 1.1))
    slab("hip", (x0, 10.4, 3.35, x1, 13.4, 4.05), "bow_tail", hidden="d",
         part=f"bow_tail_{s}", flip=(s == "l"), tpu=4)

# ---------------------------------------------------------------------------
# 3. 图集分配（货架打包 + 共享图元）
# ---------------------------------------------------------------------------
FACE_ORDER = ("n", "e", "s", "w", "u", "d")
# GeckoLib 4.x 的 UVFaces 反序列化**只认全名**（north/south/east/west/up/down）：
# 单字母键会被静默丢掉 → BakedModelFactory.buildQuad 拿到 null 直接 return null
# → 该面不产生四边形。整模型所有面都 null 时实体完全不可见，但阴影照画（只剩一团影子的经典症状）。
# 生成器内部一律用单字母（历史约定 + 板面语言），**只在写 geo JSON 那一刻翻译成全名**。
GEO_FACE_NAME = {"n": "north", "s": "south", "e": "east",
                 "w": "west", "u": "up", "d": "down"}
FACE_UVDIR = {           # 该面的 +u / +v 在模型空间指向哪；v 递增方向 = 贴图里向下
    "n": ((-1, 0, 0), (0, -1, 0)),
    "s": ((1, 0, 0), (0, -1, 0)),
    "e": ((0, 0, -1), (0, -1, 0)),
    "w": ((0, 0, 1), (0, -1, 0)),
    "u": ((1, 0, 0), (0, 0, 1)),
    "d": ((1, 0, 0), (0, 0, 1)),
}
# 贴图里「向上」在模型空间的方向（画家据此摆正细节）
FACE_UP_DIR = {f: tuple(-c for c in FACE_UVDIR[f][1]) for f in FACE_UVDIR}

SAMPLES = ["lining", "cloth_dark", "cloth_top", "skin_dark", "hair_dark", "silk_mid"]
SAMPLE_PX = 2                   # 样本条压到 2px：128 图集下 8px 会白吃 40% 高度
SAMPLE_RECT = {name: (0, i * SAMPLE_PX, SAMPLE_PX, SAMPLE_PX) for i, name in enumerate(SAMPLES)}
PACK_TOP = len(SAMPLES) * SAMPLE_PX + 4

DEFAULT_TPU = 3
TPU_DIV = 3                     # 实际密度 = tpu/TPU_DIV px per u；tpu=3 → 精确 1px

# ---- 双层皮肤分区 ----------------------------------------------------------
# 参考图（custom (5).png）本身就是双层皮肤。上半区放基础层（必须不透明），
# 下半区放覆盖层（允许 alpha 镂空）。分区高度经装箱实测定：基础层落到 y≤82，
# 覆盖层落到 y≤120，两侧都留有余量（头部 tpu=9 提密度后基础层需要更多空间）。
LAYERS = {"base": (PACK_TOP, 88), "overlay": (88, TEX_H)}

# 覆盖层 = 叠在基础层之上、可镂空/可透气的部件（头发、面纱、蕾丝、蝴蝶结、首饰）
OVERLAY_PARTS = {
    "fringe_l", "fringe_mid", "fringe_r",
    "sidehair_l", "sidehair_r", "sidehair_tip_l", "sidehair_tip_r",
    "fall_mid", "fall_low", "fall_tip", "nape", "back_mid", "back_low",
    "bun_be", "bun_bw", "bun_e", "bun_fe", "bun_fw", "bun_n", "bun_s", "bun_w",
    "hairpin", "tiara", "tiara_gem",
    "veil_up", "veil_low",
    "hem_lLace_bw", "hem_lLace_fw", "hem_lLace_w",
    "hem_rLace_be", "hem_rLace_e", "hem_rLace_fe",
    "skirtLace_n", "skirtLace_s",
    "cuff_l", "cuff_r",
    "collar_side_l", "collar_side_r", "collar_front",
    "bow_knot", "bow_loop_l", "bow_loop_r", "bow_tail_l", "bow_tail_r",
    "choker", "pendant",
}


def layer_of(part):
    """部件 → 图集分区名。未登记的一律算基础层（保证不透明、不会漏成洞）。"""
    return "overlay" if part in OVERLAY_PARTS else "base"


def face_size(box, face):
    x0, y0, z0, x1, y1, z1 = box
    if face in ("n", "s"):
        return (x1 - x0, y1 - y0)
    if face in ("e", "w"):
        return (z1 - z0, y1 - y0)
    return (x1 - x0, z1 - z0)


class Packer:
    def __init__(self, w, h, top, pad=1):
        self.w, self.h, self.pad = w, h, pad
        self.x, self.y, self.row_h = 0, top, 0
        self.rects = []

    def alloc(self, w, h):
        w, h = int(w), int(h)
        if self.x + w + self.pad > self.w:
            self.y += self.row_h + self.pad
            self.x, self.row_h = 0, 0
        if self.y + h + self.pad > self.h:
            raise RuntimeError(f"图集塞不下了：需要 {w}x{h} @ ({self.x},{self.y})")
        r = (self.x, self.y, w, h)
        self.x += w + self.pad
        self.row_h = max(self.row_h, h)
        self.rects.append(r)
        return r


def round_rect(r):
    return tuple(int(round(v)) for v in r)


# 两层各自独立装箱：基础层落在上半区，覆盖层落在下半区
PACKERS = {name: Packer(TEX_W, bottom, top, pad=1) for name, (top, bottom) in LAYERS.items()}
MANIFEST = []


def build_manifest():
    """先按尺寸降序分配（货架浪费最小），再按原始顺序写回清单，保证产物顺序稳定。"""
    reqs = []
    for ci, c in enumerate(CUBES):
        for face in FACE_ORDER:
            fw, fh = face_size(c["box"], face)
            pv = c["paint"][face]
            name = pv if isinstance(pv, str) else pv[0]
            kw = {} if isinstance(pv, str) else dict(pv[1] or {})
            tpu = 0 if name.startswith("@") else (c["tpu"] or DEFAULT_TPU)
            reqs.append((ci, face, name, kw, fw, fh, tpu))
    rect_of = {}
    own = [r for r in reqs if r[6]]
    own.sort(key=lambda r: (-max(r[4] * r[6], r[5] * r[6]), -min(r[4] * r[6], r[5] * r[6])))
    for ci, face, name, kw, fw, fh, tpu in own:
        w = max(1, int(round(fw * tpu / TPU_DIV)))
        h = max(1, int(round(fh * tpu / TPU_DIV)))
        rect_of[(ci, face)] = list(round_rect(PACKERS[layer_of(CUBES[ci]["part"])].alloc(w, h)))
    for ci, face, name, kw, fw, fh, tpu in reqs:
        c = CUBES[ci]
        if name.startswith("@"):
            u, v, w, h = SAMPLE_RECT[name[1:]]
            rect, tp = [u, v, w, h], 0
        else:
            rect, tp = rect_of[(ci, face)], tpu
        MANIFEST.append({
            "cube": ci, "bone": c["bone"], "part": c["part"], "face": face,
            "rect": rect, "tpu": tp, "fw": round(fw, 3), "fh": round(fh, 3),
            "layer": layer_of(c["part"]),
            "painter": name, "kwargs": kw, "flip": c["flip"],
            "u_dir": FACE_UVDIR[face][0], "up_dir": FACE_UP_DIR[face],
        })


MANIFEST_BY_CUBE = {}


def bind_uvs():
    for ci, c in enumerate(CUBES):
        c["uv"] = {}
    for m in MANIFEST:
        u, v, w, h = m["rect"]
        if m["painter"].startswith("@"):
            c = CUBES[m["cube"]]
            c["uv"][m["face"]] = {"uv": [u, v], "uv_size": [w, h]}
            continue
        CUBES[m["cube"]]["uv"][m["face"]] = {"uv": [u, v], "uv_size": [w, h]}


build_manifest()
bind_uvs()

# ---------------------------------------------------------------------------
# 4. geo JSON
# ---------------------------------------------------------------------------


def build_geo():
    bones_out = []
    order = {b["name"]: i for i, b in enumerate(BONES)}
    by_bone = {}
    for c in CUBES:
        by_bone.setdefault(c["bone"], []).append(c)
    for b in BONES:
        o = {"name": b["name"], "pivot": b["pivot"]}
        if b["parent"]:
            o["parent"] = b["parent"]
        cubes = by_bone.get(b["name"], [])
        if cubes:
            o["cubes"] = []
            for c in cubes:
                uvm = {}
                for f in FACE_ORDER:
                    if f in c["uv"]:
                        uvm[GEO_FACE_NAME[f]] = {"uv": c["uv"][f]["uv"], "uv_size": c["uv"][f]["uv_size"]}
                o["cubes"].append({
                    "origin": c["box"][:3],
                    "size": [round(c["box"][3] - c["box"][0], 3),
                             round(c["box"][4] - c["box"][1], 3),
                             round(c["box"][5] - c["box"][2], 3)],
                    "uv": uvm,
                })
        bones_out.append(o)
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {
                "identifier": "geometry.bride_zombie",
                "texture_width": TEX_W,
                "texture_height": TEX_H,
                "visible_bounds_width": 2.5,
                "visible_bounds_height": 3.0,
                "visible_bounds_offset": [0, 1.05, 0],
            },
            "bones": bones_out,
        }],
    }


# ---------------------------------------------------------------------------
# 5. 动画（只写 rotation / position，绝不写 scale）
# ---------------------------------------------------------------------------

def tstr(t):
    s = f"{round(float(t), 3):.3f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    return s


class Clip2:
    def __init__(self, name, length, loop=False):
        self.name = name
        self.length = round(float(length), 3)
        self.loop = bool(loop)
        self.data = {}   # bone -> chan -> axis -> {t: val}

    def key(self, bone, chan, axis, keys):
        d = self.data.setdefault(bone, {}).setdefault(chan, {}).setdefault(axis, {})
        for t, v in keys:
            d[round(float(t), 3)] = round(float(v), 4)

    def r(self, bone, axis, keys):
        self.key(bone, "rotation", axis, keys)

    def p(self, bone, axis, keys):
        self.key(bone, "position", axis, keys)

    def rot3(self, bone, keys):
        """keys: {t: (x, y, z)}"""
        for axis, i in (("x", 0), ("y", 1), ("z", 2)):
            self.key(bone, "rotation", axis, [(t, v[i]) for t, v in sorted(keys.items())])

    def to_json(self):
        bones = {}
        for bone, chans in self.data.items():
            bo = {}
            for chan, axes in chans.items():
                co = {}
                all_t = sorted({t for ks in axes.values() for t in ks})
                for t in all_t:
                    vec = [axes.get(a, {}).get(t, 0.0) for a in ("x", "y", "z")]
                    co[tstr(t)] = {"post": {"vector": vec}, "lerp_mode": "catmullrom"}
                bo[chan] = co
            bones[bone] = bo
        return {"animation_length": self.length, "loop": self.loop, "bones": bones}

    def bones_touched(self):
        return set(self.data)


def shift(keys, dt, cycle):
    """把 [(t, v)...] 平移相位，回到 [0, cycle]。

    循环剪辑的每个通道都必须在 0 与 cycle 两处各有一个键（否则 GeckoLib 会在接缝处
    把上一帧的值一直保持到片尾，再跳到 0 点的值，走起来就是一卡一卡）。
    """
    out = {}
    for t, v in keys:
        nt = round((t + dt) % cycle, 3)
        out[nt] = v
    v0 = _interp(keys, (0.0 - dt) % cycle)
    out.setdefault(0.0, v0)
    out[round(float(cycle), 3)] = out[0.0]
    return sorted(out.items())


def _interp(keys, t):
    ks = sorted(keys)
    if t <= ks[0][0]:
        return ks[0][1]
    if t >= ks[-1][0]:
        return ks[-1][1]
    for (t0, v0), (t1, v1) in zip(ks, ks[1:]):
        if t0 <= t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * f
    return 0.0


def mirror_keys(keys, axis):
    """L 侧：x 轴同号，y/z 轴反号（镜像）。"""
    if axis == "x":
        return list(keys)
    return [(t, -v) for t, v in keys]


def negate_keys(keys):
    return [(t, -v) for t, v in keys]


def build_animations():
    clips = []

    # ---------------- idle：3.0s 呼吸 + 缓慢转头 ----------------
    c = Clip2("idle", 3.0, loop=True)
    c.p("move", "y", [(0, 0), (1.5, 0.12), (3.0, 0)])
    c.r("hip", "y", [(0, 0), (0.75, 1.5), (1.5, 0), (2.25, -1.5), (3.0, 0)])
    c.r("hip", "z", [(0, 0), (0.75, -1.2), (1.5, 0), (2.25, 1.2), (3.0, 0)])
    c.r("spine", "x", [(0, 0), (1.5, -1.2), (3.0, 0)])
    c.r("spine", "y", [(0, 0), (0.9, -1.0), (2.1, 1.0), (3.0, 0)])
    c.r("chest", "x", [(0, 0), (1.5, -1.6), (3.0, 0)])
    c.r("neck", "x", [(0, 0), (1.5, -1.2), (3.0, 0)])
    c.r("head", "x", [(0, 0), (1.2, 1.0), (2.2, -1.0), (3.0, 0)])
    c.r("head", "y", [(0, 0), (0.9, 4.0), (2.1, -4.0), (3.0, 0)])
    c.r("head", "z", [(0, 0), (1.5, 1.2), (3.0, 0)])
    for tag, sgn in (("r", 1), ("l", -1)):
        c.p("bust_" + tag, "z", [(0, 0), (1.5, -0.1), (3.0, 0)])
        c.r("bust_" + tag, "x", [(0, 0), (1.5, -0.6), (3.0, 0)])
        c.p("shoulder_" + tag, "y", [(0, 0), (1.5, 0.14), (3.0, 0)])
        c.r("arm_" + tag, "x", [(0, 0), (1.5, 1.4), (3.0, 0)])
        c.r("arm_" + tag, "z", [(0, 0), (1.5, 1.2 * sgn), (3.0, 0)])
        c.r("forearm_" + tag, "x", [(0, 0), (1.5, 2.0), (3.0, 0)])
        c.r("shin_" + tag, "x", [(0, 0), (1.5, -1.6), (3.0, 0)])
        c.r("hair_side_" + tag, "x", [(0, 0), (1.3, 1.4), (2.4, -1.0), (3.0, 0)])
    c.r("hair_bun", "x", [(0, 0), (1.3, 2.0), (2.4, -1.2), (3.0, 0)])
    c.r("hair_bun", "y", [(0, 0), (1.0, 1.6), (2.2, -1.6), (3.0, 0)])
    c.r("hair_back", "x", [(0, 0), (1.5, 1.2), (3.0, 0)])
    c.r("hair_fall", "x", [(0, 0), (1.6, 1.6), (3.0, 0)])
    c.r("hair_fall", "y", [(0, 0), (1.2, -1.0), (2.4, 1.0), (3.0, 0)])
    c.r("fringe", "x", [(0, 0), (1.4, -1.2), (3.0, 0)])
    c.r("veil", "x", [(0, 0), (0.9, 2.5), (2.1, -1.5), (3.0, 0)])
    c.r("veil", "y", [(0, 0), (1.5, 1.6), (3.0, 0)])
    c.r("skirt", "x", [(0, 0), (1.5, -1.0), (3.0, 0)])
    c.r("skirt", "y", [(0, 0), (1.0, 1.2), (2.0, -1.2), (3.0, 0)])
    c.r("train", "x", [(0, 0), (1.2, -1.6), (2.4, 1.0), (3.0, 0)])
    c.r("hem_r", "x", [(0, 0), (1.4, -0.8), (3.0, 0)])
    c.r("hem_l", "x", [(0, 0), (1.4, -0.8), (3.0, 0)])
    clips.append(c)

    # ---------------- walk：1.6s 两步（0 点 = 摆动腿提膝经过支撑腿） ----------------
    #
    # 相位约定（循环剪辑的铁律：每个通道都必须在 0 与 1.6 各有一个键，且两处相等，
    # 否则 GeckoLib 会把末帧值一直保持到片尾再跳到 0 点，走起来一卡一卡）：
    #   t=0.4  leg_r 脚跟触地（前伸最大）    t=1.2  leg_r 脚尖蹬离（后伸最大）
    #   t=0.0  leg_r 摆动中段（提膝经过）    t=0.8  leg_r 支撑中段（伸直踩地）
    # leg_l 一律 shift(..., 0.8, 1.6) 取反相。
    #
    # 旧版把 0 点的两条腿都写成 0 —— 那是"双脚并拢立正"：每 0.8s 混进一个静止姿势，
    # 读起来一顿一顿。现在 0 点由摆动腿的屈膝 + 勾脚定义，落点是"正在迈步"。
    #
    # 漂浮感（约 40%）不靠 move.y 硬顶，而是「脚不踩实 + 布料拖曳」：
    #   · 脚尖常驻下垂，支撑相脚掌也不完全放平（+3°），膝盖不锁死（shin 留 -1°）
    #   · move.y 幅度 0.35 → 0.28 并整体抬高 0.10u：裙摆是"贴着地皮飘"不是"砸在地上"
    #   · 裙摆/后摆/面纱滞后 0.10~0.16s、幅度 ×1.4，读作"布被拖着走"而不是"跟着身体甩"
    #   · 手臂 ±14° → ±8°、头颈减到 0.4~1.2°：上半身端庄，不跟着步子甩
    w = Clip2("walk", 1.6, loop=True)

    def s2(a, b=None):
        """一个循环里两次同相的峰（触地 / 蹬离各一次）。"""
        return [(0, 0), (0.4, a), (0.8, 0), (1.2, a if b is None else b), (1.6, 0)]

    def alt(a, b):
        """1/循环 的左右交替量：0.4 偏 +a，1.2 偏 b。"""
        return [(0, 0), (0.4, a), (0.8, 0), (1.2, b), (1.6, 0)]

    def lag(keys, dt):
        """布料/头发的相位滞后：峰值晚 dt 秒出现（shift 会同时补齐 0 与 1.6 两个端键）。"""
        return shift(keys, dt, 1.6)

    w.p("move", "y", [(0, 0.10), (0.4, -0.18), (0.8, 0.10), (1.2, -0.18), (1.6, 0.10)])
    legs = [(0, 0), (0.4, 22), (0.8, 0), (1.2, -15), (1.6, 0)]
    # 屈膝最深落在摆动中段（0 / 1.4），触地时几乎伸直，支撑相也不锁死（-1）
    shins = [(0, -27), (0.4, -5), (0.6, -2), (0.8, -1), (1.1, -10), (1.2, -22), (1.4, -34), (1.6, -27)]
    # 踝：摆动中段脚尖垂下 +10 → 落地前勾脚 -9 → 支撑相放平到 +3 → 蹬离 +16（跟落地/尖离地的滚动）
    feet = [(0, 10), (0.3, -6), (0.4, -9), (0.55, -1), (0.8, 3), (1.1, 8), (1.2, 16), (1.4, 14), (1.6, 10)]
    arms = [(0, 0), (0.4, -8), (0.8, 0), (1.2, 7), (1.6, 0)]
    w.r("leg_r", "x", legs)
    w.r("leg_l", "x", shift(legs, 0.8, 1.6))
    w.r("shin_r", "x", shins)
    w.r("shin_l", "x", shift(shins, 0.8, 1.6))
    w.r("foot_r", "x", feet)
    w.r("foot_l", "x", shift(feet, 0.8, 1.6))
    w.r("arm_r", "x", arms)
    w.r("arm_l", "x", shift(arms, 0.8, 1.6))
    w.r("arm_r", "z", [(0, 0), (0.4, 1.6), (0.8, 2.2), (1.2, 1.6), (1.6, 0)])
    w.r("arm_l", "z", [(0, 0), (0.4, -1.6), (0.8, -2.2), (1.2, -1.6), (1.6, 0)])
    w.r("forearm_r", "x", [(0, 0), (0.4, 7), (0.8, 0), (1.2, 8), (1.6, 0)])
    w.r("forearm_l", "x", shift([(0, 0), (0.4, 7), (0.8, 0), (1.2, 8), (1.6, 0)], 0.8, 1.6))
    w.r("shoulder_r", "x", [(0, 0), (0.4, 2), (0.8, 0), (1.2, -2), (1.6, 0)])
    w.r("shoulder_l", "x", shift([(0, 0), (0.4, 2), (0.8, 0), (1.2, -2), (1.6, 0)], 0.8, 1.6))
    w.r("hip", "y", [(0, 0), (0.4, 2.6), (0.8, 0), (1.2, -2.6), (1.6, 0)])
    w.r("hip", "z", [(0, 0), (0.4, 1.8), (0.8, 0), (1.2, -1.8), (1.6, 0)])
    w.r("spine", "y", [(0, 0), (0.4, -1.8), (0.8, 0), (1.2, 1.8), (1.6, 0)])
    w.r("spine", "x", [(0, 0), (0.4, 1.2), (0.8, 0), (1.2, 1.2), (1.6, 0)])
    w.r("chest", "y", [(0, 0), (0.4, -2.6), (0.8, 0), (1.2, 2.6), (1.6, 0)])
    w.r("chest", "x", [(0, 0), (0.4, 0.8), (0.8, 0), (1.2, 0.8), (1.6, 0)])
    w.r("neck", "x", [(0, 0), (0.4, -0.4), (0.8, 0), (1.2, -0.4), (1.6, 0)])
    w.r("head", "x", [(0, 0), (0.4, -0.8), (0.8, 0), (1.2, -0.8), (1.6, 0)])
    w.r("head", "y", [(0, 0), (0.4, 1.2), (0.8, 0), (1.2, -1.2), (1.6, 0)])
    w.r("hair_bun", "x", lag([(0, 0), (0.5, 3.0), (0.9, 0), (1.3, 3.0), (1.6, 0)], 0.06))
    w.r("hair_back", "x", lag([(0, 0), (0.45, 2.0), (0.85, 0), (1.25, 2.0), (1.6, 0)], 0.06))
    w.r("hair_fall", "x", lag([(0, 0), (0.5, 2.6), (0.9, 0), (1.3, 2.6), (1.6, 0)], 0.08))
    w.r("hair_fall", "y", lag([(0, 0), (0.4, -1.6), (0.8, 0), (1.2, 1.6), (1.6, 0)], 0.08))
    for tag, sgn in (("r", 1), ("l", -1)):
        w.r("hair_side_" + tag, "x", lag([(0, 0), (0.5, 2.2), (0.9, 0), (1.3, 2.2), (1.6, 0)], 0.08))
        w.p("bust_" + tag, "z", [(0, 0), (0.4, -0.06), (0.8, 0), (1.2, -0.06), (1.6, 0)])
    w.r("fringe", "x", lag([(0, 0), (0.5, -1.4), (0.9, 0), (1.3, -1.4), (1.6, 0)], 0.08))
    # 布料：滞后 + 幅度 ×1.4（后摆最重最迟，面纱次之，裙摆/下摆最轻）
    w.r("veil", "x", lag(s2(-7.0), 0.15))
    w.r("veil", "y", lag(alt(2.8, -2.8), 0.13))
    w.r("skirt", "x", lag(s2(-5.6), 0.12))
    w.r("skirt", "y", lag(alt(4.2, -4.2), 0.10))
    w.r("skirt", "z", lag(alt(2.1, -2.1), 0.10))
    w.r("train", "x", lag(s2(-8.4), 0.16))
    w.r("hem_r", "x", lag(s2(-4.2), 0.10))
    w.r("hem_l", "x", lag(s2(-4.2), 0.10))
    w.r("hem_r", "z", lag(alt(2.8, -2.8), 0.12))
    w.r("hem_l", "z", lag(alt(-2.8, 2.8), 0.12))
    clips.append(w)

    # ---------------- 技能一：亡语魅惑（2.0s，命中 1.0s）双手捧胸 → 波动绽放 ----------------
    c = Clip2("skill_death_chime", 2.0)
    ZH = {"r": 1, "l": -1}   # 外展量符号：+X 侧的外展是 +Z
    for tag, sg in ZH.items():
        c.r("arm_" + tag, "x", [(0, 0), (0.45, -18), (0.9, -26), (1.0, -6), (1.25, 4), (2.0, 0)])
        c.r("arm_" + tag, "z", [(0, 0), (0.45, -14 * sg), (0.9, -20 * sg), (1.0, 34 * sg),
                                (1.25, 12 * sg), (2.0, 0)])
        c.r("forearm_" + tag, "x", [(0, 0), (0.45, 34), (0.9, 46), (1.0, 8), (1.25, 14), (2.0, 0)])
        c.r("forearm_" + tag, "y", [(0, 0), (0.9, 12 * -sg), (1.0, -6 * -sg), (2.0, 0)])
        c.r("shoulder_" + tag, "x", [(0, 0), (0.9, 6), (1.0, -5), (2.0, 0)])
        c.r("hem_" + tag, "x", [(0, 0), (0.9, -4), (1.0, -9), (1.3, -3), (2.0, 0)])
        c.r("leg_" + tag, "x", [(0, 0), (0.9, -6), (1.0, -2), (2.0, 0)])
        c.r("leg_" + tag, "z", [(0, 0), (0.9, 3 * sg), (2.0, 0)])
        c.r("shin_" + tag, "x", [(0, 0), (0.9, -14), (1.0, -8), (2.0, 0)])
    c.r("spine", "x", [(0, 0), (0.9, 7), (1.0, -6), (1.3, -2), (2.0, 0)])
    c.r("chest", "x", [(0, 0), (0.9, 9), (1.0, -11), (1.3, -3), (2.0, 0)])
    c.r("neck", "x", [(0, 0), (0.9, 6), (1.0, -8), (2.0, 0)])
    c.r("head", "x", [(0, 0), (0.9, 12), (1.0, -14), (1.3, -4), (2.0, 0)])
    c.r("head", "y", [(0, 0), (0.9, 3), (1.0, -3), (2.0, 0)])
    c.r("hip", "x", [(0, 0), (0.9, 3), (1.0, -2), (2.0, 0)])
    c.p("move", "y", [(0, 0), (0.9, -0.18), (1.0, 0.1), (2.0, 0)])
    c.r("skirt", "x", [(0, 0), (0.9, -2), (1.0, -7), (1.3, -3), (2.0, 0)])
    c.r("veil", "x", [(0, 0), (0.9, 3), (1.0, -12), (1.35, -4), (2.0, 0)])
    c.r("veil", "y", [(0, 0), (0.9, -3), (1.0, 5), (2.0, 0)])
    c.r("train", "x", [(0, 0), (0.9, -3), (1.0, -10), (1.4, -3), (2.0, 0)])
    c.r("hair_bun", "x", [(0, 0), (0.9, 6), (1.05, -8), (1.4, -2), (2.0, 0)])
    c.r("hair_fall", "x", [(0, 0), (0.9, 4), (1.05, -7), (1.4, -2), (2.0, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (1.0, -0.22), (1.3, -0.05), (2.0, 0)])
        c.r("bust_" + tag, "x", [(0, 0), (0.9, 3), (1.0, -5), (2.0, 0)])
        c.r("hair_side_" + tag, "x", [(0, 0), (0.9, 3), (1.05, -5), (2.0, 0)])
    clips.append(c)

    # ---------------- 技能二：血月选妃（3.0s，命中 1.5s）提裙行礼 → 起身展臂 ----------------
    c = Clip2("skill_consort", 3.0)
    for tag, sg in ZH.items():
        c.r("leg_" + tag, "x", [(0, 0), (1.2, -14), (1.5, -16), (1.75, -12), (2.4, -3), (3.0, 0)])
        c.r("leg_" + tag, "z", [(0, 0), (1.2, 6 * sg), (1.5, 7 * sg), (2.4, 2 * sg), (3.0, 0)])
        c.r("shin_" + tag, "x", [(0, 0), (1.2, -30), (1.5, -34), (1.75, -26), (2.4, -6), (3.0, 0)])
        c.r("foot_" + tag, "x", [(0, 0), (1.2, 12), (1.5, 14), (2.4, 3), (3.0, 0)])
        c.r("shin_" + tag, "y", [(0, 0), (1.2, 6 * sg), (3.0, 0)])
    # 右手提裙（向内收），左手向外舒展
    c.r("arm_r", "x", [(0, 0), (0.6, -16), (1.4, -40), (1.5, -42), (1.8, -26), (2.5, -6), (3.0, 0)])
    c.r("arm_r", "z", [(0, 0), (1.4, -12), (1.5, -14), (2.5, -3), (3.0, 0)])
    c.r("forearm_r", "x", [(0, 0), (0.6, 14), (1.4, 44), (1.5, 46), (1.8, 28), (2.5, 6), (3.0, 0)])
    c.r("arm_l", "x", [(0, 0), (0.6, -6), (1.4, -14), (1.5, -10), (2.0, -22), (2.5, -10), (3.0, 0)])
    c.r("arm_l", "z", [(0, 0), (0.6, -22), (1.4, -46), (1.5, -52), (2.0, -30), (2.6, -8), (3.0, 0)])
    c.r("forearm_l", "x", [(0, 0), (0.6, 10), (1.4, 22), (1.5, 24), (2.0, 30), (2.6, 8), (3.0, 0)])
    c.r("forearm_l", "z", [(0, 0), (1.4, -14), (1.5, -16), (2.6, -4), (3.0, 0)])
    for tag, sg in ZH.items():
        c.r("shoulder_" + tag, "x", [(0, 0), (1.4, 4), (1.5, -6), (2.2, 2), (3.0, 0)])
        c.r("hem_" + tag, "x", [(0, 0), (0.8, -6), (1.4, -22), (1.5, -30), (1.9, -12), (2.6, -3), (3.0, 0)])
        c.r("hem_" + tag, "y", [(0, 0), (1.4, 8 * -sg), (1.5, 10 * -sg), (2.6, 2 * -sg), (3.0, 0)])
    c.r("spine", "x", [(0, 0), (1.2, 12), (1.5, 10), (1.9, -8), (2.5, -3), (3.0, 0)])
    c.r("chest", "x", [(0, 0), (1.2, 10), (1.5, 8), (1.9, -12), (2.5, -4), (3.0, 0)])
    c.r("chest", "y", [(0, 0), (1.2, -6), (1.5, -8), (2.2, 4), (3.0, 0)])
    c.r("neck", "x", [(0, 0), (1.2, 8), (1.5, 5), (1.9, -8), (2.6, -2), (3.0, 0)])
    c.r("head", "x", [(0, 0), (1.2, 12), (1.5, 8), (1.9, -12), (2.6, -3), (3.0, 0)])
    c.r("head", "y", [(0, 0), (1.2, 6), (1.5, 8), (2.2, -5), (3.0, 0)])
    c.r("hip", "x", [(0, 0), (1.2, 6), (1.5, 4), (1.9, -4), (2.6, -1), (3.0, 0)])
    c.p("move", "y", [(0, 0), (1.2, -1.35), (1.5, -1.5), (1.9, -0.5), (2.4, 0.12), (3.0, 0)])
    c.r("skirt", "x", [(0, 0), (1.2, -4), (1.5, -6), (2.0, 3), (2.6, 1), (3.0, 0)])
    c.r("veil", "x", [(0, 0), (1.2, 4), (1.5, 2), (1.8, -10), (2.4, -3), (3.0, 0)])
    c.r("train", "x", [(0, 0), (1.2, -5), (1.5, -7), (1.9, -12), (2.5, -3), (3.0, 0)])
    c.r("hair_bun", "x", [(0, 0), (1.2, 7), (1.5, 5), (1.9, -8), (2.6, -2), (3.0, 0)])
    c.r("hair_fall", "x", [(0, 0), (1.2, 5), (1.5, 3), (1.9, -6), (2.6, -2), (3.0, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (1.5, -0.14), (2.0, -0.05), (3.0, 0)])
        c.r("bust_" + tag, "x", [(0, 0), (1.2, 4), (1.9, -5), (3.0, 0)])
        c.r("hair_side_" + tag, "x", [(0, 0), (1.2, 3), (1.9, -4), (3.0, 0)])
    clips.append(c)

    # ---------------- 技能三：摄魂尖啸（2.3s，命中 1.1s）仰头张臂 → 前扑收势 ----------------
    c = Clip2("skill_soul_shriek", 2.3)
    for tag, sg in ZH.items():
        c.r("arm_" + tag, "x", [(0, 0), (0.7, -10), (1.1, -14), (1.5, 6), (2.3, 0)])
        c.r("arm_" + tag, "z", [(0, 0), (0.7, 38 * sg), (1.1, 48 * sg), (1.5, 20 * sg), (2.3, 0)])
        c.r("forearm_" + tag, "x", [(0, 0), (0.7, 20), (1.1, 26), (1.5, 30), (1.9, 10), (2.3, 0)])
        c.r("forearm_" + tag, "y", [(0, 0), (0.7, 10 * sg), (1.1, 14 * sg), (2.3, 0)])
        c.r("shoulder_" + tag, "x", [(0, 0), (1.1, -7), (1.5, 3), (2.3, 0)])
        c.r("leg_" + tag, "x", [(0, 0), (1.1, -8), (1.5, 6), (2.3, 0)])
        c.r("leg_" + tag, "z", [(0, 0), (1.1, 5 * sg), (2.3, 0)])
        c.r("shin_" + tag, "x", [(0, 0), (1.1, -16), (1.5, -6), (2.3, 0)])
        c.r("hem_" + tag, "x", [(0, 0), (1.1, -12), (1.5, -5), (2.3, 0)])
        c.r("hem_" + tag, "y", [(0, 0), (1.1, 6 * -sg), (2.3, 0)])
    c.r("spine", "x", [(0, 0), (0.7, -6), (1.1, -12), (1.4, 9), (1.8, 3), (2.3, 0)])
    c.r("chest", "x", [(0, 0), (0.7, -8), (1.1, -16), (1.4, 10), (1.8, 3), (2.3, 0)])
    c.r("neck", "x", [(0, 0), (0.7, -14), (1.1, -22), (1.4, 6), (1.8, 2), (2.3, 0)])
    c.r("head", "x", [(0, 0), (0.7, -22), (1.1, -38), (1.35, -14), (1.6, 10), (2.0, 3), (2.3, 0)])
    c.r("head", "z", [(0, 0), (1.1, 8), (1.6, -4), (2.3, 0)])
    c.r("hip", "x", [(0, 0), (1.1, -5), (1.5, 4), (2.3, 0)])
    c.p("move", "y", [(0, 0), (1.1, 0.18), (1.4, -0.3), (2.3, 0)])
    c.r("skirt", "x", [(0, 0), (1.1, -8), (1.5, -4), (2.3, 0)])
    c.r("veil", "x", [(0, 0), (0.8, -8), (1.1, -16), (1.6, 6), (2.3, 0)])
    c.r("veil", "z", [(0, 0), (1.1, 6), (2.3, 0)])
    c.r("train", "x", [(0, 0), (1.1, -12), (1.6, -4), (2.3, 0)])
    c.r("hair_bun", "x", [(0, 0), (0.9, -10), (1.1, -18), (1.5, 8), (2.0, 2), (2.3, 0)])
    c.r("hair_fall", "x", [(0, 0), (0.9, -8), (1.1, -14), (1.5, 6), (2.3, 0)])
    c.r("hair_fall", "z", [(0, 0), (1.1, -4), (2.3, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (1.1, 0.16), (1.5, -0.06), (2.3, 0)])
        c.r("bust_" + tag, "x", [(0, 0), (1.1, -5), (1.6, 3), (2.3, 0)])
        c.r("hair_side_" + tag, "x", [(0, 0), (1.1, -6), (1.6, 4), (2.3, 0)])
    clips.append(c)

    # ---------------- 召唤（0.9s，命中窗口触发）：只驱动 hand_r / hand_l / crown ----------------
    c = Clip2("summon", 0.9)
    for tag, sg in ZH.items():
        c.r("hand_" + tag, "x", [(0, 0), (0.25, -18), (0.5, -22), (0.9, 0)])
        c.r("hand_" + tag, "z", [(0, 0), (0.25, 20 * sg), (0.5, 26 * sg), (0.9, 0)])
        c.r("hand_" + tag, "y", [(0, 0), (0.5, -14 * sg), (0.9, 0)])
    c.p("crown", "y", [(0, 0), (0.3, 0.45), (0.6, 0.3), (0.9, 0)])
    c.r("crown", "x", [(0, 0), (0.3, -8), (0.6, -4), (0.9, 0)])
    c.r("crown", "y", [(0, 0), (0.45, 26), (0.9, 0)])
    clips.append(c)

    # ---------------- 技能四：白纱缚足（2.2s，命中 1.1s）提纱上抬 → 下压暴涨缠足 ----------------
    c = Clip2("skill_veil_snare", 2.2)
    for tag, sg in ZH.items():
        c.r("arm_" + tag, "x", [(0, 0), (0.5, -12), (1.1, -18), (1.25, 14), (1.7, 6), (2.2, 0)])
        c.r("arm_" + tag, "z", [(0, 0), (0.5, 26 * sg), (1.1, 34 * sg), (1.25, 10 * sg),
                                (1.7, 18 * sg), (2.2, 0)])
        c.r("forearm_" + tag, "x", [(0, 0), (0.5, 18), (1.1, 26), (1.25, -6), (1.7, 10), (2.2, 0)])
        c.r("shoulder_" + tag, "x", [(0, 0), (1.1, 4), (1.25, -8), (1.8, 2), (2.2, 0)])
        c.r("leg_" + tag, "x", [(0, 0), (1.1, -7), (1.25, 5), (2.2, 0)])
        c.r("leg_" + tag, "z", [(0, 0), (1.1, 3 * sg), (1.25, -2 * sg), (2.2, 0)])
        c.r("shin_" + tag, "x", [(0, 0), (1.1, -20), (1.25, -8), (2.2, 0)])
        c.r("foot_" + tag, "x", [(0, 0), (1.1, 8), (1.25, 2), (2.2, 0)])
        # 下摆：命中瞬间向外下方暴涨（"纱从裙底伸出去"）
        c.r("hem_" + tag, "x", [(0, 0), (1.1, -8), (1.25, -22), (1.7, -8), (2.2, 0)])
        c.r("hem_" + tag, "z", [(0, 0), (1.1, -4 * sg), (1.25, -12 * sg), (1.7, -5 * sg), (2.2, 0)])
    c.r("spine", "x", [(0, 0), (1.1, 6), (1.25, -9), (1.7, -2), (2.2, 0)])
    c.r("chest", "x", [(0, 0), (1.1, 8), (1.25, -12), (1.7, -3), (2.2, 0)])
    c.r("neck", "x", [(0, 0), (1.1, 4), (1.25, -6), (2.2, 0)])
    c.r("head", "x", [(0, 0), (1.1, 6), (1.25, -10), (1.6, -3), (2.2, 0)])
    c.r("head", "y", [(0, 0), (1.1, -3), (1.25, 3), (2.2, 0)])
    c.r("hip", "x", [(0, 0), (1.1, 4), (1.25, -5), (2.2, 0)])
    c.p("move", "y", [(0, 0), (1.1, -0.20), (1.25, 0.10), (1.7, 0.02), (2.2, 0)])
    c.r("skirt", "x", [(0, 0), (1.1, -10), (1.25, -30), (1.7, -12), (2.2, 0)])
    c.r("skirt", "z", [(0, 0), (1.1, 4), (1.25, 8), (2.2, 0)])
    c.r("veil", "x", [(0, 0), (1.1, -14), (1.25, -34), (1.7, -8), (2.2, 0)])
    c.r("veil", "z", [(0, 0), (1.1, 5), (1.25, 10), (2.2, 0)])
    c.r("train", "x", [(0, 0), (1.1, -12), (1.25, -26), (1.7, -10), (2.2, 0)])
    c.r("hair_bun", "x", [(0, 0), (1.1, 5), (1.3, -8), (1.8, -2), (2.2, 0)])
    c.r("hair_fall", "x", [(0, 0), (1.1, 4), (1.3, -7), (1.8, -2), (2.2, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (1.1, 0.12), (1.35, -0.14), (2.2, 0)])
        c.r("bust_" + tag, "x", [(0, 0), (1.1, -4), (1.35, 5), (2.2, 0)])
        c.r("hair_side_" + tag, "x", [(0, 0), (1.1, 4), (1.3, -6), (2.2, 0)])
    clips.append(c)

    # ---------------- 技能五：献祭召奬（2.8s，命中 1.6s）低头合掌下沉 → 仰头张臂上浮 ----------------
    c = Clip2("skill_sacrifice", 2.8)
    for tag, sg in ZH.items():
        c.r("arm_" + tag, "x", [(0, 0), (0.7, -14), (1.6, -24), (1.75, -32), (2.1, -16), (2.8, 0)])
        c.r("arm_" + tag, "z", [(0, 0), (0.7, -16 * sg), (1.6, -26 * sg), (1.75, 52 * sg),
                                (2.2, 20 * sg), (2.8, 0)])
        c.r("forearm_" + tag, "x", [(0, 0), (0.7, 26), (1.6, 44), (1.75, 6), (2.2, 14), (2.8, 0)])
        c.r("shoulder_" + tag, "x", [(0, 0), (1.6, 6), (1.75, -7), (2.3, 2), (2.8, 0)])
        c.r("leg_" + tag, "x", [(0, 0), (1.6, -12), (1.75, -4), (2.4, -2), (2.8, 0)])
        c.r("leg_" + tag, "z", [(0, 0), (1.6, 2 * sg), (1.75, 4 * sg), (2.4, 1 * sg), (2.8, 0)])
        c.r("shin_" + tag, "x", [(0, 0), (1.6, -28), (1.75, -10), (2.8, 0)])
        c.r("foot_" + tag, "x", [(0, 0), (1.6, 10), (1.75, 4), (2.8, 0)])
        c.r("hem_" + tag, "x", [(0, 0), (1.6, -3), (1.75, -10), (2.4, -3), (2.8, 0)])
        c.r("hem_" + tag, "y", [(0, 0), (1.75, 5 * -sg), (2.8, 0)])
    c.r("spine", "x", [(0, 0), (1.6, 10), (1.75, -8), (2.2, -3), (2.8, 0)])
    c.r("chest", "x", [(0, 0), (1.6, 12), (1.75, -14), (2.2, -4), (2.8, 0)])
    c.r("neck", "x", [(0, 0), (1.6, 10), (1.75, -16), (2.2, -5), (2.8, 0)])
    c.r("head", "x", [(0, 0), (0.7, 10), (1.6, 20), (1.75, -28), (2.2, -8), (2.8, 0)])
    c.r("hip", "x", [(0, 0), (1.6, 6), (1.75, -4), (2.8, 0)])
    # 命中：献祭掉召奬，整个人被"托"起来一下
    c.p("move", "y", [(0, 0), (1.6, -0.35), (1.75, 0.35), (2.2, 0.15), (2.8, 0)])
    c.r("skirt", "x", [(0, 0), (1.6, -6), (1.75, -14), (2.3, -4), (2.8, 0)])
    c.r("veil", "x", [(0, 0), (1.6, 4), (1.75, -20), (2.3, -6), (2.8, 0)])
    c.r("train", "x", [(0, 0), (1.6, -4), (1.75, -18), (2.3, -5), (2.8, 0)])
    c.r("hair_bun", "x", [(0, 0), (1.6, 5), (1.75, -12), (2.3, -4), (2.8, 0)])
    c.r("hair_fall", "x", [(0, 0), (1.6, 4), (1.75, -10), (2.3, -3), (2.8, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (1.6, 0.14), (1.75, -0.16), (2.2, -0.05), (2.8, 0)])
        c.r("bust_" + tag, "x", [(0, 0), (1.6, 5), (1.75, -7), (2.8, 0)])
        c.r("hair_side_" + tag, "x", [(0, 0), (1.6, 4), (1.75, -9), (2.8, 0)])
    clips.append(c)

    # ---------------- 技能六：抛花束（1.9s，命中 1.2s）右臂过肩后仰 → 前挥鞭打出手 ----------------
    c = Clip2("skill_bouquet", 1.9)
    # 右臂是主动臂：先抬过肩后仰蓄力，再整条手臂甩出去（鞭打）
    c.r("arm_r", "x", [(0, 0), (0.5, -34), (1.0, -58), (1.2, 18), (1.5, 6), (1.9, 0)])
    c.r("arm_r", "z", [(0, 0), (0.5, -10), (1.0, -16), (1.2, 10), (1.9, 0)])
    c.r("forearm_r", "x", [(0, 0), (0.5, 30), (1.0, 54), (1.2, -14), (1.5, 4), (1.9, 0)])
    c.r("forearm_r", "y", [(0, 0), (1.0, -10), (1.2, 8), (1.9, 0)])
    c.r("shoulder_r", "x", [(0, 0), (1.0, -8), (1.2, 4), (1.9, 0)])
    # 左臂反相配重
    c.r("arm_l", "x", [(0, 0), (1.0, 14), (1.2, -10), (1.9, 0)])
    c.r("arm_l", "z", [(0, 0), (1.0, -20), (1.2, -24), (1.6, -6), (1.9, 0)])
    c.r("forearm_l", "x", [(0, 0), (1.0, 18), (1.9, 0)])
    c.r("shoulder_l", "x", [(0, 0), (1.0, 3), (1.9, 0)])
    # 转体：蓄力转到右后，出手反打到左前
    c.r("spine", "y", [(0, 0), (1.0, 10), (1.2, -10), (1.9, 0)])
    c.r("spine", "x", [(0, 0), (1.0, -6), (1.2, 8), (1.9, 0)])
    c.r("chest", "y", [(0, 0), (1.0, 16), (1.2, -18), (1.6, -4), (1.9, 0)])
    c.r("chest", "x", [(0, 0), (1.0, 4), (1.2, -6), (1.9, 0)])
    c.r("neck", "x", [(0, 0), (1.0, -3), (1.2, 4), (1.9, 0)])
    c.r("head", "y", [(0, 0), (1.0, -14), (1.2, 12), (1.5, 3), (1.9, 0)])
    c.r("head", "x", [(0, 0), (1.0, -8), (1.2, 6), (1.9, 0)])
    c.r("hip", "y", [(0, 0), (1.0, 7), (1.2, -9), (1.9, 0)])
    c.r("hip", "z", [(0, 0), (1.0, 3), (1.2, -4), (1.9, 0)])
    c.p("move", "y", [(0, 0), (1.0, -0.16), (1.2, 0.10), (1.5, 0.02), (1.9, 0)])
    for tag, sg in ZH.items():
        c.r("leg_" + tag, "x", [(0, 0), (1.0, -6), (1.2, 4), (1.9, 0)])
        c.r("leg_" + tag, "z", [(0, 0), (1.0, 4 * sg), (1.2, -2 * sg), (1.9, 0)])
        c.r("shin_" + tag, "x", [(0, 0), (1.0, -16), (1.2, -6), (1.9, 0)])
        c.r("hem_" + tag, "x", [(0, 0), (1.1, -9), (1.35, -14), (1.7, -5), (1.9, 0)])
        c.r("hem_" + tag, "y", [(0, 0), (1.1, 6 * sg), (1.45, 8 * sg), (1.9, 0)])
    c.r("skirt", "x", [(0, 0), (1.1, -7), (1.4, -12), (1.7, -4), (1.9, 0)])
    c.r("skirt", "y", [(0, 0), (1.1, -8), (1.45, -10), (1.9, 0)])
    c.r("veil", "x", [(0, 0), (1.1, -6), (1.4, -12), (1.9, 0)])
    c.r("train", "x", [(0, 0), (1.1, -14), (1.45, -16), (1.9, 0)])
    c.r("hair_bun", "x", [(0, 0), (1.1, 4), (1.4, -7), (1.9, 0)])
    c.r("hair_fall", "x", [(0, 0), (1.1, 3), (1.4, -6), (1.9, 0)])
    c.r("hair_fall", "y", [(0, 0), (1.1, -5), (1.45, -7), (1.9, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (1.1, 0.10), (1.45, -0.12), (1.9, 0)])
        c.r("hair_side_" + tag, "x", [(0, 0), (1.1, 3), (1.45, -6), (1.9, 0)])
    clips.append(c)

    # ---------------- 技能七：鬼嫁之吻（1.8s，命中 1.0s）右手前伸 → 俯身拉近吸血 ----------------
    c = Clip2("skill_bridal_kiss", 1.8)
    # 右臂向正前方（-Z）伸出去抓人：x 抬到接近水平、z 往内收
    c.r("arm_r", "x", [(0, 0), (0.4, -20), (1.0, -42), (1.3, -30), (1.8, 0)])
    c.r("arm_r", "z", [(0, 0), (0.4, -8), (1.0, -22), (1.3, -14), (1.8, 0)])
    c.r("forearm_r", "x", [(0, 0), (0.4, 20), (1.0, -6), (1.3, 4), (1.8, 0)])
    c.r("shoulder_r", "x", [(0, 0), (1.0, -6), (1.3, -3), (1.8, 0)])
    # 左臂向后展（把胸口让出来）
    c.r("arm_l", "x", [(0, 0), (1.0, 20), (1.3, 16), (1.8, 0)])
    c.r("arm_l", "z", [(0, 0), (1.0, -28), (1.3, -22), (1.8, 0)])
    c.r("forearm_l", "x", [(0, 0), (1.0, 22), (1.8, 0)])
    # 俯身低头 + 头略偏（吻的意象），整个人往前压
    c.r("spine", "x", [(0, 0), (1.0, 14), (1.3, 10), (1.8, 0)])
    c.r("chest", "x", [(0, 0), (1.0, 12), (1.3, 8), (1.8, 0)])
    c.r("chest", "y", [(0, 0), (1.0, -6), (1.3, -4), (1.8, 0)])
    c.r("neck", "x", [(0, 0), (1.0, 8), (1.3, 5), (1.8, 0)])
    c.r("head", "x", [(0, 0), (1.0, 12), (1.3, 8), (1.8, 0)])
    c.r("head", "z", [(0, 0), (1.0, -6), (1.3, -3), (1.8, 0)])
    c.r("hip", "x", [(0, 0), (1.0, 5), (1.8, 0)])
    c.p("move", "y", [(0, 0), (1.0, -0.12), (1.3, -0.04), (1.8, 0)])
    c.p("move", "z", [(0, 0), (1.0, -0.10), (1.3, -0.04), (1.8, 0)])
    for tag, sg in ZH.items():
        c.r("leg_" + tag, "x", [(0, 0), (1.0, -8), (1.3, -3), (1.8, 0)])
        c.r("shin_" + tag, "x", [(0, 0), (1.0, -18), (1.3, -8), (1.8, 0)])
        c.r("foot_" + tag, "x", [(0, 0), (1.0, 8), (1.8, 0)])
        c.r("hem_" + tag, "x", [(0, 0), (1.0, -6), (1.3, -9), (1.8, 0)])
    c.r("skirt", "x", [(0, 0), (1.0, -8), (1.3, -10), (1.8, 0)])
    c.r("veil", "x", [(0, 0), (1.0, 6), (1.3, -8), (1.8, 0)])
    c.r("train", "x", [(0, 0), (1.0, -12), (1.3, -8), (1.8, 0)])
    c.r("hair_bun", "x", [(0, 0), (1.0, 6), (1.3, -6), (1.8, 0)])
    c.r("hair_fall", "x", [(0, 0), (1.0, 5), (1.3, -5), (1.8, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (1.0, -0.14), (1.3, -0.05), (1.8, 0)])
        c.r("bust_" + tag, "x", [(0, 0), (1.0, 4), (1.3, -3), (1.8, 0)])
        c.r("hair_side_" + tag, "x", [(0, 0), (1.0, 5), (1.3, -5), (1.8, 0)])
    clips.append(c)

    return clips


# ---------------------------------------------------------------------------
# 6. 产物落盘
# ---------------------------------------------------------------------------
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


def main():
    global MANIFEST
    geo = build_geo()
    clips = build_animations()
    anim = {"format_version": "1.8.0", "animations": {c.name: c.to_json() for c in clips}}

    art_geo = ART / GEO_NAME
    art_anim = ART / ANIM_NAME
    src_geo = SRC_ASSETS / "geo" / GEO_NAME
    src_anim = SRC_ASSETS / "animations" / ANIM_NAME
    gsha, gshas = dump_json([art_geo, src_geo], geo)
    asha, ashas = dump_json([art_anim, src_anim], anim)

    manifest = {"texture": TEX_REL, "size": [TEX_W, TEX_H], "faces": MANIFEST,
                "samples": {k: list(v) for k, v in SAMPLE_RECT.items()}}
    ART.mkdir(parents=True, exist_ok=True)
    (ART / "bride_atlas.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # --- 自校验 ---
    report = {"geo_sha256": gsha, "anim_sha256": asha,
              "geo_copies": gshas, "anim_copies": ashas,
              "bones": len(BONES), "cubes": len(CUBES),
              "faces": len(MANIFEST), "checks": []}
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        report["checks"].append({"name": name, "pass": bool(cond), "detail": detail})

    names = [b["name"] for b in BONES]
    check("骨骼名唯一", len(names) == len(set(names)), f"{len(names)} 根")

    # GeckoLib 4.x 的 UVFaces 反序列化只读全名（north/south/east/west/up/down）：
    # 单字母键会被静默丢掉 → BakedModelFactory.buildQuad 拿到 null 直接 return null →
    # 该面不产生四边形。全模型都 null 时实体完全不可见但阴影照画（实机「只有阴影」的根因）。
    uv_keys, uv_faces = set(), 0
    for gm in geo["minecraft:geometry"]:
        for b in gm["bones"]:
            for c in b.get("cubes", []):
                uv_keys |= set((c.get("uv") or {}).keys())
                uv_faces += len(c.get("uv") or {})
    short = [k for k in sorted(uv_keys) if k in ("n", "e", "s", "w", "u", "d")]
    check("geo UV 面键为全名（GeckoLib 只认全名）", not short,
          f"面键 {sorted(uv_keys)}" + (f" / 单字母残留 {short} ✗" if short else ""))
    check("每个立方体 6 面 UV 齐全", uv_faces == len(CUBES) * 6,
          f"{uv_faces} 面 / 期望 {len(CUBES) * 6}")
    check("父骨存在", all((b["parent"] is None) or (b["parent"] in names) for b in BONES))
    check("体块引用骨骼存在", all(c["bone"] in names for c in CUBES))
    check("动画骨骼都在 geo 里",
          all(b in names for c in clips for b in c.data),
          str(sorted({b for c in clips for b in c.data if b not in names})))
    check("geo 里没有骨骼旋转（rest 全零旋转）",
          all("rotation" not in b for b in geo["minecraft:geometry"][0]["bones"]))
    check("geo 里没有骨骼缩放",
          all("scale" not in b for b in geo["minecraft:geometry"][0]["bones"]))
    check("动画只有 rotation/position",
          all(ch in ("rotation", "position") for c in clips for b in c.data for ch in c.data[b]))

    # 每个非 loop 剪辑首尾归零；loop 剪辑首尾一致
    for c in clips:
        for bone, chans in c.data.items():
            for ch, axes in chans.items():
                for ax, ks in axes.items():
                    ts = sorted(ks)
                    check(f"{c.name}.{bone}.{ch}.{ax} 有 ≥2 关键帧", len(ts) >= 2, str(ts))
                    if not c.loop:
                        check(f"{c.name}.{bone}.{ch}.{ax} 收招归零",
                              abs(ks[0.0]) < 0.001 and abs(ks[round(c.length, 3)]) < 0.001,
                              f"{ks.get(0.0)} -> {ks.get(round(c.length, 3))}")
                    else:
                        has0 = 0.0 in ks and round(c.length, 3) in ks
                        eq = has0 and abs(ks[0.0] - ks[round(c.length, 3)]) < 0.001
                        check(f"{c.name}.{bone}.{ch}.{ax} 循环接缝一致（0 = 片尾）",
                              has0 and eq, f"keys={ts}")
    # 同帧并行的剪辑之间不许争同一根骨头（技能 × 召唤）
    summon_bones = {c for c in clips if c.name == "summon" for c in c.bones_touched()}
    for c in clips:
        if not c.name.startswith("skill_"):
            continue
        shared = summon_bones & c.bones_touched()
        check(f"{c.name} 与 summon 不争骨头", not shared, str(sorted(shared)))

    # UV：范围 + 不重叠
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
    fam = [m for m in MANIFEST if m["part"].startswith("bust_r") and not m["painter"].startswith("@")]
    fbm = [m for m in MANIFEST if m["part"].startswith("bust_l") and not m["painter"].startswith("@")]
    inter = {tuple(m["rect"]) for m in fam} & {tuple(m["rect"]) for m in fbm}
    check("两瓣胸块 UV 不叠", not inter, str(sorted(inter)))
    texels = sum(m["rect"][2] * m["rect"][3] for m in MANIFEST if not m["painter"].startswith("@"))
    report["atlas_texels"] = texels
    report["atlas_usage"] = round(texels / float(TEX_W * TEX_H) * 100, 2)

    # 胸部规格回读
    bz = [c for c in CUBES if c["part"] in ("bust_r", "bust_l")]
    for c in bz:
        x0, y0, z0, x1, y1, z1 = c["box"]
        report.setdefault("bust", {})[c["part"]] = {
            "size": [round(x1 - x0, 3), round(y1 - y0, 3), round(z1 - z0, 3)],
            "x": [x0, x1], "z": [z0, z1],
            "protrusion": round(BUST_Z_FRONT - z0, 3),
        }
    main_r = report["bust"]["bust_r"]
    main_l = report["bust"]["bust_l"]
    gap = round(main_r["x"][0] - main_l["x"][1], 3)   # 右瓣内缘 - 左瓣内缘
    report["bust_gap"] = gap
    check("胸瓣主块宽 2.00u", abs(main_r["size"][0] - 2.0) < 1e-9, str(main_r["size"][0]))
    check("胸瓣主块高 3.00u", abs(main_r["size"][1] - 3.0) < 1e-9, str(main_r["size"][1]))
    check("胸瓣前伸 1.00u", abs(main_r["protrusion"] - 1.0) < 1e-9, str(main_r["protrusion"]))
    check("胸瓣中缝 1.00u", abs(gap - 1.0) < 1e-9, str(gap))
    check("胸瓣主块盒深 = 1.00 前伸 + 0.06 嵌入（等效规格的 1 深）",
          abs(main_r["size"][2] - 1.06) < 1e-9, str(main_r["size"][2]))
    check("胸瓣左右对称",
          main_r["x"] == [-v for v in reversed(main_l["x"])]
          and main_r["z"] == main_l["z"], f"r={main_r['x']} l={main_l['x']}")

    # Java 侧双向同步：常量 / 剪辑名 / 时长与命中点
    jm = ROOT / "src/main/java/com/apocalypse/zombies/client/model/BrideGeoModel.java"
    jz = ROOT / "src/main/java/com/apocalypse/zombies/entity/BrideZombie.java"
    je = ROOT / "src/main/java/com/apocalypse/zombies/entity/EliteAbility.java"
    jt = jm.read_text(encoding="utf-8") if jm.exists() else ""
    jzt = jz.read_text(encoding="utf-8") if jz.exists() else ""
    jet = je.read_text(encoding="utf-8") if je.exists() else ""
    check("BrideGeoModel 存在", bool(jt), str(jm))
    check("BrideZombie 实现了 GeoEntity",
          "implements GeoEntity" in jzt or "GeoEntity" in jzt)

    def jconst(name):
        m = re.search(rf"{name}\s*=\s*(-?[0-9.]+)F", jt)
        return float(m.group(1)) if m else None

    for cname, want in (("CHEST_FRONT_Z", BUST_Z_FRONT), ("BUST_WIDTH", 2.0),
                        ("BUST_HEIGHT", 3.0), ("BUST_PROTRUSION", 1.0), ("BUST_GAP", 1.0)):
        got = jconst(cname)
        check(f"Java 常量 {cname} == {want}", got is not None and abs(got - want) < 1e-6,
              f"java={got}")
    for clip in [c.name for c in clips]:
        check(f'Java 剪辑名 "{clip}" 存在', f'"{clip}"' in jzt, "BrideZombie 里的常量")

    # 剪辑时长/命中点必须 = EliteAbility 的 (duration, impactTick)/20，否则动作和结算会错位
    STRIKE = {"skill_death_chime": ("DEATH_CHIME", 1.0), "skill_consort": ("CONSORT", 1.5),
              "skill_soul_shriek": ("SOUL_SHRIEK", 1.1), "summon": ("DEATH_CHIME", None),
              "skill_veil_snare": ("VEIL_SNARE", 1.1), "skill_sacrifice": ("SACRIFICE", 1.6),
              "skill_bouquet": ("BOUQUET", 1.2), "skill_bridal_kiss": ("BRIDAL_KISS", 1.0)}
    for clip, (enum_name, strike) in STRIKE.items():
        m = re.search(rf"\b{enum_name}\((\d+),\s*(-?\d+)\)", jet)
        c = next((x for x in clips if x.name == clip), None)
        if not m or c is None:
            check(f"{clip} 与 {enum_name} 对齐", False, f"enum={bool(m)} clip={bool(c)}")
            continue
        dur, imp = int(m.group(1)), int(m.group(2))
        if clip == "summon":
            check(f"summon 长度 {c.length}s == 0.9s", abs(c.length - 0.9) < 1e-6, str(c.length))
            continue
        check(f"{clip} 时长 {c.length}s == {enum_name} 的 {dur} tick",
              abs(c.length * 20 - dur) < 0.5, f"{c.length * 20:.0f} vs {dur}")
        check(f"{clip} 命中点 {strike}s == {enum_name} 的冲击 {imp} tick",
              abs(strike * 20 - imp) < 0.5, f"{strike * 20:.0f} vs {imp}")

    # 循环剪辑的接缝：每个通道必须在 0 与 length 处各有一个键、且两处数值相等。
    # 少一个端键，GeckoLib 会把末帧值一直保持到片尾再跳到 0 点的值 —— 走起来一卡一卡。
    seam = []
    for c in clips:
        if not c.loop:
            continue
        for bone, chans in c.data.items():
            for chan, axes in chans.items():
                for axis, keys in axes.items():
                    if 0.0 not in keys or c.length not in keys or keys[0.0] != keys[c.length]:
                        seam.append(f"{c.name}:{bone}.{chan}.{axis}")
    check("循环剪辑接缝闭合（0 与 length 两处键相等）", not seam, str(seam[:5]))

    # 非循环剪辑（技能/召唤）首尾归零：movement 控制器在施法期间 STOP，
    # 施法结束回到 walk/idle 时首尾不为 0 会有一帧硬跳。
    unzero = []
    for c in clips:
        if c.loop:
            continue
        for bone, chans in c.data.items():
            for chan, axes in chans.items():
                for axis, keys in axes.items():
                    if abs(keys.get(0.0, 0.0)) > 1e-9 or abs(keys.get(c.length, 0.0)) > 1e-9:
                        unzero.append(f"{c.name}:{bone}.{chan}.{axis}")
    check("非循环剪辑首尾归零", not unzero, str(unzero[:5]))

    report["clips"] = {c.name: {"length": c.length, "loop": c.loop,
                                "bones": sorted(c.bones_touched())} for c in clips}
    report["all_pass"] = ok
    (ART / "bride_v2_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"geo : {art_geo}  sha256={gsha}")
    print(f"anim: {art_anim}  sha256={asha}")
    print(f"art↔src geo  一致: {gshas[str(art_geo)] == gshas[str(src_geo)]}")
    print(f"art↔src anim 一致: {ashas[str(art_anim)] == ashas[str(src_anim)]}")
    print(f"骨骼 {len(BONES)} / 体块 {len(CUBES)} / 面 {len(MANIFEST)} / "
          f"图集占用 {report['atlas_usage']}% ({texels} texels)")
    for c in report["checks"]:
        if not c["pass"]:
            print(f"  FAIL {c['name']} {c['detail']}")
    print(f"自校验: {'全部通过' if ok else '有失败项'} ({sum(1 for c in report['checks'] if c['pass'])}"
          f"/{len(report['checks'])})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())