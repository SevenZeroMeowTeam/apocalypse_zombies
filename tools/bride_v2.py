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
             panels=("n", "s", "e", "w", "fe", "fw", "be", "bw"), tpu_by_panel=None):
    """out: {面: paint 值}，只作用于该环的外表面。cap_up/cap_down 给顶/底切片。

    tpu_by_panel: 给环上某一块面板单独改采样密度（键是面板名 n/s/e/w/fe/fw/be/bw）。
    存在的理由：脸那块面板是唯一需要高分辨率的地方，而整个环一起提密度会让图集塞不下 ——
    密度要能按块给，不是按环给。
    """
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
        cube(bone_name, boxes[p], paint, part=f"{part}_{p}", flip=flip,
             tpu=(tpu_by_panel or {}).get(p, tpu))


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

# 袖骨（两节/侧）：纱袖要能「甩」，就不能把袖体块死绑在手臂上 —— 手臂一停它就停，
# 看起来是戴了根管子。挂在肘下、rest 零旋转 ⇒ 静止姿态与加骨之前**逐 texel 一致**
# （零旋转绕任意轴心都是恒等变换），只有动起来才看得出袖子比手臂慢半拍。
bone("sleeve_l", (-4.9, 16.6, 0), "forearm_l")
bone("sleeve_l2", (-4.9, 13.9, 0), "sleeve_l")
bone("sleeve_r", (4.9, 16.6, 0), "forearm_r")
bone("sleeve_r2", (4.9, 13.9, 0), "sleeve_r")

# 头 / 发 / 面纱
bone("neck", (0, 22.8, 0), "chest")
bone("head", (0, 24.4, 0), "neck")
bone("fringe", (0, 29.0, -3.2), "head")
bone("hair_bun", (0, 30.4, 1.3), "head")
bone("hair_back", (0, 25.6, 2.5), "head")
bone("hair_side_l", (-3.5, 29.4, -0.4), "head")
bone("hair_side_r", (3.5, 29.4, -0.4), "head")
bone("hair_side_l2", (-3.5, 25.8, -0.4), "hair_side_l")   # ↓ 鬓发两段链：铰链落自己上缘
bone("hair_side_r2", (3.5, 25.8, -0.4), "hair_side_r")    #   挂在 head 上 ⇒ 转头时发梢能慢半拍
bone("veil", (0, 30.8, 4.4), "head")          # 面纱根：整幅布的挂点（现有动画都按这个 pivot 调过，不动它）
bone("veil2", (0, 28.3, 4.4), "veil")         # ↓ 四段布料链：每段 pivot 落在**自己上缘** = 铰链，
bone("veil3", (0, 25.4, 4.4), "veil2")        #   子段绕上一段的末端转，才能读出布的波
bone("veil4", (0, 22.5, 4.4), "veil3")
bone("crown", (0, 30.6, -1.6), "head")
bone("hair_fall", (0, 22.0, 3.0), "chest")   # 肩以下的长发：挂在胸上，不跟头甩
bone("hair_fall2", (0, 19.6, 3.0), "hair_fall")   # ↓ 长发同样拆链：每段 pivot 落在**自己上缘**
bone("hair_fall3", (0, 17.2, 3.0), "hair_fall2")  #   = 铰链。根骨 pivot 不动，旧键全部继续成立

# 腿
bone("leg_l", (-1.75, 12.2, 0), "hip")
bone("shin_l", (-1.75, 5.6, 0), "leg_l")
bone("foot_l", (-1.75, 2.1, 0), "shin_l")
bone("leg_r", (1.75, 12.2, 0), "hip")
bone("shin_r", (1.75, 5.6, 0), "leg_r")
bone("foot_r", (1.75, 2.1, 0), "shin_r")

# 裙摆：中/后板挂 skirt，两侧板挂 hem_r/hem_l（召唤/行礼时两侧能单独掀起）
# 三层环各挂一级子骨（skirt → skirt2 → skirt3），于是：① 现有键全部只驱动**上层环**，语义不变；
# ② 链只往下长，中/下两层环独立滞后。铰链落在"下层环的上缘"（y=10.0 / 7.8）= 两层环的交叠处。
bone("skirt", (0, 12.6, 0), "hip")
bone("skirt2", (0, 10.0, 0), "skirt")
bone("skirt3", (0, 7.8, 0), "skirt2")
bone("hem_l", (-4.6, 9.4, 0), "skirt")
bone("hem_l2", (-4.6, 10.0, 0), "hem_l")
bone("hem_l3", (-4.6, 7.8, 0), "hem_l2")
bone("hem_r", (4.6, 9.4, 0), "skirt")
bone("hem_r2", (4.6, 10.0, 0), "hem_r")
bone("hem_r3", (4.6, 7.8, 0), "hem_r2")
bone("train", (0, 11.4, 2.8), "skirt")
bone("train2", (0, 9.0, 5.4), "train")   # 拖尾两段链：下段铰链落在自己上缘（y=9.0, 贴内缘 z=5.4）

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
         # 脸那块面板单独提密度：tpu=18 ⇒ 18/TPU_DIV(3) = 6 px/u ⇒ 正面板 31×43 px，
         # 正是 p_face 那套笔触写的时候假定的尺寸（原来只有 16×22，被量化掉一半，
         # 全身最低密度就落在脸上 —— 五官不精致的机械原因在这里，不是画家不会画）。
         # 只有"脸"这一块提：整个头一起提会让图集塞不下（实测 8x43 那一行装不进去）。
         "head", tpu=9, tpu_by_panel={"n": 18}, cap_up="hair_top", cap_down="@skin_dark")
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
    slab("hair_side_" + s + "2", (x0, 23.4, -1.2, x1, 25.8, 1.6), ("hair_side_tip", {"side": s}),
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
slab("hair_fall2", (-3.2, 17.0, 3.0, 3.2, 19.6, 4.5), "hair_fall", hidden="nu",
     part="fall_low", tpu=4)
slab("hair_fall3", (-2.6, 15.2, 3.1, 2.6, 17.2, 4.4), ("hair_fall_tip", {}), hidden="nu",
     part="fall_tip", tpu=4)

# 面纱：从 2 块刚性板改成 **4 段布料链**（原来只有一根骨，任何动画都只能整幅硬甩）。
# 每段往下微微变宽 + 后移 = 垂坠；中间段用 band=2（纯网格、不带花边），
# 只让最低一段带扇形花边 —— 否则每一段都会长出一圈花边。
slab("veil", (-3.7, 28.3, 4.02, 3.7, 31.2, 5.00), ("veil_lace", {"band": 0}), hidden="nu",
     part="veil_up", tpu=4)
slab("veil2", (-3.9, 25.4, 4.08, 3.9, 28.3, 5.10), ("veil_lace", {"band": 2}), hidden="nu",
     part="veil_mid1", tpu=4)
slab("veil3", (-4.2, 22.5, 4.14, 4.2, 25.4, 5.25), ("veil_lace", {"band": 2}), hidden="nu",
     part="veil_mid2", tpu=4)
slab("veil4", (-4.5, 19.6, 4.20, 4.5, 22.5, 5.40), ("veil_lace", {"band": 1}), hidden="nu",
     part="veil_low", tpu=4)

# ---- 头纱下摆：波浪扇贝边 ----------------------------------------------------
# 原先 veil4 的下缘是一刀切的直线（侧视尤其明显，一整块布像块板）。下摆改成 3 个扇贝弧：
# 每弧 3u 宽、由 3 根 1u 立柱组成，中间那根多垂 1.2u、两侧各垂 0.4u。
#   实测取舍：0.4/1.2 这组差值是「侧影读得出圆头弧」的最小搭配；整幅宽 9u 切 3 弧，
#   每弧 3u（= 18.75cm）正好是婚纱扇贝边的常见比例，再多就碎成锯齿了。
#   * 挂在 **veil4** 骨上而不是新建骨：下摆必须跟着布料链自己甩，
#     单独挂骨会变成「纱在动、边不动」。
#   * 顶面抬到 19.8u（比 veil4 下缘高 0.20u）：与其余布料层同口径的咬合余量，
#     齐平留在 19.6 会因为取整在侧视里露一条缝。
#   * 宽 ≥ 1u ⇒ tpu=4 下每个面宽 ≥4px，走得到 p_veil 的正常蕾丝分支；
#     0.4u 那两根矮柱的面高只有 2~3px，会落到「窄条」分支铺半透明白纱 ——
#     这正是蕾丝下摆边缘该有的通透度，不必另开贴图。
#   * band=1 就是 p_veil 的底段档（扇形花边 + 最重的血），下摆接的正是那一段。
VEIL_HEM_Y = 19.6                      # = veil4 下缘
for _lobe in range(3):
    for _col, _drop in enumerate((0.4, 1.2, 0.4)):
        _x0 = -4.5 + _lobe * 3 + _col
        slab("veil4", (_x0, VEIL_HEM_Y - _drop, 4.20, _x0 + 1.0, VEIL_HEM_Y + 0.20, 5.40),
             ("veil_lace", {"band": 1}), hidden="nu",
             part="veil_hem_%d%d" % (_lobe, _col), tpu=4)

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
    # 肘到腕的丝纱：改挂 sleeve_*（绕肘摆），手臂一停它还会自己荡
    x0, x1 = sorted((sg * 3.9, sg * 5.7))
    slab("sleeve_" + s, (x0, 13.6, -1.15, x1, 16.6, 1.15), "forearm_silk", hidden="ud",
         part=f"forearm_{s}", flip=flip, tpu=3)
    # 腕口蕾丝：改挂 sleeve_*2（绕腕摆）
    x0, x1 = sorted((sg * 3.6, sg * 6.0))
    slab("sleeve_%s2" % s, (x0, 12.6, -1.4, x1, 13.7, 1.4), "cuff_lace", hidden="ud",
         part=f"cuff_{s}", flip=flip, tpu=4)
    # 钟形袖（肘下）：真正在静止姿态里看得见的那圈。腕口那圈在 y 11.4~12.6、正落在
    # 裙摆上沿（12.6）里侧，被裙子吃掉了 —— 手臂垂着时看不出袖子张；抬起来（攻击）就出来了。
    # 内侧必须让开腰身：y≈15 处躯干半宽 3.2u，所以内壁只到 3.7u，外壁张到 6.5u。
    def _mx(m, n):
        return (min(m, n), max(m, n))

    _xn, _xx = _mx(sg * 3.7, sg * 5.0)      # 正/背面：内 3.7 外 5.0
    _xe0, _xe1 = _mx(sg * 5.0, sg * 6.5)    # 外侧张到 6.5
    _xw0, _xw1 = _mx(sg * 3.7, sg * 4.2)    # 内侧只补一薄层，避开腰身
    for _p, _box in (("n", (_xn, 15.0, -2.4, _xx, 16.6, -1.6)),
                     ("s", (_xn, 15.0, 1.6, _xx, 16.6, 2.4)),
                     ("e", (_xe0, 15.0, -1.6, _xe1, 16.6, 1.6)),
                     ("w", (_xw0, 15.0, -1.6, _xw1, 16.6, 1.6))):
        slab("sleeve_" + s, _box, {"n": "forearm_silk", "s": "forearm_silk"}, hidden="ud",
             part="sleeve_bell_%s%s" % (s, _p), flip=flip, tpu=4)
    # 图集是 1u=1px 的 128×128（原版密度），不能扩 —— 所以只有正/背面用专属蕾丝图元，
    # 侧/背面走共享衬里（@lining，零新增 UV），一整圈都画专属图元会把货架式打包器撑爆。
    _ring = (11.4, 12.6, 2.5, 2.5, 1.7, 1.7)
    _ry0, _ry1, _hx, _hz, _ax, _bz = _ring
    _cx = sg * 4.8
    for _p, _box in (("n", (_cx - _ax, _ry0, -_hz, _cx + _ax, _ry1, -_bz)),
                     ("s", (_cx - _ax, _ry0, _bz, _cx + _ax, _ry1, _hz)),
                     ("e", (_cx + _ax, _ry0, -_bz, _cx + _hx, _ry1, _bz)),
                     ("w", (_cx - _hx, _ry0, -_bz, _cx - _ax, _ry1, _bz))):
        slab("sleeve_%s2" % s, _box, {"n": "cuff_lace", "s": "cuff_lace"}, hidden="ud",
             part="cuff_flare_%s%s" % (s, _p), flip=flip, tpu=4)
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
oct_ring("skirt2", 7.6, 10.0, 5.7, 4.3, 3.8, 2.75, SKIRT_PAINT, "skirtB", tpu=3,
         cap_up="@cloth_dark", cap_down="@cloth_dark", panels=("n", "s"))
oct_ring("skirt3", 6.9, 7.8, 6.2, 4.7, 4.2, 3.05, SKIRT_PAINT, "skirtLace", tpu=4,
         cap_up="@cloth_dark", cap_down="@cloth_dark", panels=("n", "s"))
for bn, b2, b3, panels in (("hem_r", "hem_r2", "hem_r3", ("e", "fe", "be")),
                           ("hem_l", "hem_l2", "hem_l3", ("w", "fw", "bw"))):
    oct_ring(bn, 9.8, 13.2, 4.05, 2.95, 2.75, 1.85, SKIRT_PAINT, f"{bn}A", tpu=3,
             cap_up="@cloth_dark", cap_down="@cloth_dark", panels=panels)
    oct_ring(b2, 7.6, 10.0, 5.7, 4.3, 3.8, 2.75, SKIRT_PAINT, f"{bn}B", tpu=3,
             cap_up="@cloth_dark", cap_down="@cloth_dark", panels=panels)
    oct_ring(b3, 6.9, 7.8, 6.2, 4.7, 4.2, 3.05, SKIRT_PAINT, f"{bn}Lace", tpu=4,
             cap_up="@cloth_dark", cap_down="@cloth_dark", panels=panels)

# 拖尾
slab("train", (-3.4, 8.6, 3.0, 3.4, 11.8, 6.2), "skirt_back", hidden="nu",
     part="train_up", tpu=3)
slab("train2", (-2.6, 7.0, 5.4, 2.6, 9.0, 8.4), "skirt_back", hidden="nu",
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
# 基础层 / 覆盖层的分界线。88 → 100 是这一轮改的：脸的面板从 16×22 提到 31×43（+981 px²）
# 后基础层装不下了 —— 不是面积不够（59%→70%），是货架法被那块 43 高的面板逼出一整条高行。
# 覆盖层只用了 37%，匀 12 行给它就够了。改这里会让全模型的 UV 重排（geo 与贴图同步重生）。
LAYERS = {"base": (PACK_TOP, 100), "overlay": (100, TEX_H)}

# 覆盖层 = 叠在基础层之上、可镂空/可透气的部件（头发、面纱、蕾丝、蝴蝶结、首饰）
OVERLAY_PARTS = {
    "fringe_l", "fringe_mid", "fringe_r",
    "sidehair_l", "sidehair_r", "sidehair_tip_l", "sidehair_tip_r",
    "fall_mid", "fall_low", "fall_tip", "nape", "back_mid", "back_low",
    "bun_be", "bun_bw", "bun_e", "bun_fe", "bun_fw", "bun_n", "bun_s", "bun_w",
    "hairpin", "tiara", "tiara_gem",
    "veil_up", "veil_low", "veil_mid1", "veil_mid2",
    "hem_lLace_bw", "hem_lLace_fw", "hem_lLace_w",
    "hem_rLace_be", "hem_rLace_e", "hem_rLace_fe",
    "skirtLace_n", "skirtLace_s",
    "cuff_l", "cuff_r",
    "collar_side_l", "collar_side_r", "collar_front",
    "bow_knot", "bow_loop_l", "bow_loop_r", "bow_tail_l", "bow_tail_r",
    "choker", "pendant",
}
# 头纱下摆的扇贝弧（3 弧 × 3 柱）。与面纱同族 ⇒ 必须登记在覆盖层：
# 未登记的部件会落到基础层被强制不透明，蕾丝镂空会变成实心块。
OVERLAY_PARTS |= {"veil_hem_%d%d" % (_lobe, _col) for _lobe in range(3) for _col in range(3)}


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
    """MaxRects(BSSF) 装箱。

    为什么换掉货架法：脸的面板从 16×22 提到 31×43 之后，货架法怎么分都不行 ——
    一块 43 高的面板会逼出一整条高 43 的行，行里其余高度只能塞更矮的块，全废；
    分界线往基础层挪 12 行，覆盖层又不够了。MaxRects 把空闲区切成矩形集合、每次挑
    「短边最贴合」的那块放，小块能填进大块旁边的空档，同样的面积能放下。
    """

    def __init__(self, w, h, top, pad=1):
        self.w, self.h, self.pad = w, h, pad
        self.free = [(0, top, w, h - top)]
        self.rects = []

    def alloc(self, w, h):
        w, h = int(w), int(h)
        pw, ph = w + self.pad, h + self.pad
        best, best_score = None, None
        for i, (fx, fy, fw, fh) in enumerate(self.free):
            if fw >= pw and fh >= ph:
                score = min(fw - pw, fh - ph)        # BSSF：短边余量最小的那块
                if best_score is None or score < best_score:
                    best, best_score = i, score
        if best is None:
            raise RuntimeError(f"图集塞不下了：需要 {w}x{h}（该层剩余空闲 {len(self.free)} 块）")
        fx, fy, _, _ = self.free[best]
        self.rects.append((fx, fy, w, h))
        self.free = self._split(self.free, fx, fy, pw, ph)
        return (fx, fy, w, h)

    @staticmethod
    def _split(free, x, y, w, h):
        out = []
        for (fx, fy, fw, fh) in free:
            if fx + fw <= x or x + w <= fx or fy + fh <= y or y + h <= fy:
                out.append((fx, fy, fw, fh))         # 不相交，留着
                continue
            if fx < x:
                out.append((fx, fy, x - fx, fh))
            if x + w < fx + fw:
                out.append((x + w, fy, fx + fw - (x + w), fh))
            if fy < y:
                out.append((fx, fy, fw, y - fy))
            if y + h < fy + fh:
                out.append((fx, y + h, fw, fy + fh - (y + h)))
        return Packer._prune(out)

    @staticmethod
    def _prune(rects):
        """丢掉空矩形与「被别的空闲块完全包住」的块（保留较大的那个）。"""
        keep = []
        for i, r in enumerate(rects):
            if r[2] <= 0 or r[3] <= 0:
                continue
            covered = False
            for j, s in enumerate(rects):
                if i == j or s[2] <= 0 or s[3] <= 0:
                    continue
                if s[0] <= r[0] and s[1] <= r[1] and s[0] + s[2] >= r[0] + r[2] \
                        and s[1] + s[3] >= r[1] + r[3]:
                    if (s[2] * s[3] > r[2] * r[3]) or (s[2] * s[3] == r[2] * r[3] and j < i):
                        covered = True
                        break
            if not covered:
                keep.append(r)
        return keep


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
        def at(ks, t):
            """某轴在时刻 t 的取值（线性插值）。**缺键要插值，不能填 0**。

            这里原来是 `axes.get(a, {}).get(t, 0.0)`：某根轴在那个时刻没有自己的键时直接填 0。
            旧代码里一根骨的三根轴**永远同刻**（同一个 dt 平移），所以这个 0 填得出来也看不出来。
            一旦各轴的关键帧时刻不同（如子段按相位变化收滞后：x 与 z 的抬键时刻不再重合），
            缺的那根轴就会在自己两个大键之间**突然掉到 0** —— 子段"先回零再跳回去"，肉眼是一次抽搐。
            实测这种键对：修前子骨 44 对（父骨 0 对），改成插值后归零。
            """
            if not ks:
                return 0.0
            ts = sorted(ks)
            if t <= ts[0]:
                return ks[ts[0]]
            if t >= ts[-1]:
                return ks[ts[-1]]
            for a, b in zip(ts, ts[1:]):
                if a <= t <= b:
                    f = 0.0 if b == a else (t - a) / (b - a)
                    return ks[a] + (ks[b] - ks[a]) * f
            return 0.0

        bones = {}
        for bone, chans in self.data.items():
            bo = {}
            for chan, axes in chans.items():
                co = {}
                all_t = sorted({t for ks in axes.values() for t in ks})
                for t in all_t:
                    vec = [at(axes.get(a, {}), t) for a in ("x", "y", "z")]
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


def phase_env(keys, cycle, amp, rest_in, rest_out):
    """非循环剪辑**子段**的幅度包络（按剪辑相位）：起手小 → 甩开大 → 收招提前归零。

    为什么需要它：`chain_oneshot` 只做「幅度 ×scale + 峰值晚 dt 秒」，全程一个倍率，
    读起来仍是"整段均匀地跟一下"。真实布料/头发的拖动是**跟着速度走**的：
    起手时主体刚动、末梢还没被带起来（小）；掠过峰值时末梢甩过头（大）；
    主体停住后末梢要**贴着主体一起收**，不能拖一条尾巴（提前归零）。

    三个锚点：`t=0 → rest_in`（起手小）、`t=tp → amp`（甩开大）、`t=cycle → rest_out`
    （收招端比起手端更紧，这才是"提前归零"）。

    **`tp` 取父骨自身最大幅度的时刻**，不写死在中点 —— 这些技能剪辑的峰值在 1.1~1.7s
    之间不等，写死中点会把包络套错位置。

    **必须用「源时刻」取值**（即父骨键自己的时刻，不是平移后的）：子段的峰值本来就是
    父骨峰值**平移 dt** 的副本，若在平移后的时刻取包络，子段自己的峰值恰好落在包络的
    衰减段上 —— 结果是峰值不升反降（实测 `skill_bouquet` 的面纱 2.16 → 1.65）。
    """
    A = max(abs(v) for _, v in keys) or 1.0
    tp = min((t for t, v in keys if abs(v) >= A - 1e-9), default=cycle * 0.5)
    tp = min(max(tp, cycle * 0.15), cycle * 0.85)

    def env(t):
        if t <= 0.0:
            return rest_in
        if t >= cycle:
            return rest_out
        if t <= tp:
            return rest_in + (amp - rest_in) * (t / tp) ** 1.4
        return amp + (rest_out - amp) * ((t - tp) / (cycle - tp)) ** 0.7
    return env


def chain(keys, cycle, scale, dt):
    """布料链**子段**的关键帧：把父骨的键「幅度 ×scale、峰值晚 dt 秒」交给下一段。

    段越往下（离挂点越远）摆幅越小、到位越晚 —— 这才是行波；照抄父骨的键会让整幅布
    读成一块硬板（原来面纱只有一根骨，就是这个问题）。
    **只用于循环剪辑**：`shift` 会让 0 点取到被移进来的中间值（循环剪辑要求 0 与片尾相等）。
    循环剪辑**不加相位包络**：循环里没有"起手/收招"，且包络会破坏首尾等值。
    """
    return [(t, v * scale) for t, v in shift(keys, dt, cycle)]


GAP = 0.02          # 子段键的最小时间间距（秒）：时间映射的单调地板，见 chain_oneshot


def amp_norm(keys):
    """父骨键的**归一化幅度函数** m(t) = |v(t)| / max|v| ∈ [0,1]。

    用来做「滞后随速度收」：主体摆得满时末梢拖到最晚（甩鞭子的那一下），
    主体慢下来时末梢要往回追。只压幅度不压时间的话，末梢在**时间上**仍然拖到最后，
    实测"归零相位"几乎不变（0.868 → 0.855，等于没做）。
    """
    A = max((abs(v) for _, v in keys), default=0.0) or 1.0
    return lambda t: min(1.0, abs(_interp(keys, t)) / A)


def chain_oneshot(keys, cycle, scale, dt, env=None, lag_env=None):
    """非循环剪辑的子段键：峰值晚 dt 秒，但**首尾仍钉在 0**。

    非循环剪辑的硬约束是「收招归零」（首尾都必须回 0），所以不能用循环版的 `shift`：
    它会把片尾的键值留成中间值（自校验里就是 `收招归零 -0.171 -> -0.171` 这种失败）。
    这里只平移中间键，两端显式补 0；被挤出片尾的键直接丢（片尾本身有 0 键兜底）。

    - `env`：`phase_env()` 的幅度包络，按**源时刻**取（见 `phase_env` 的注释）。
    - `lag_env`：滞后倍率，取 `amp_norm(keys)`。`nt = t + dt * lag_env(t)` —— 主体摆满时
      拿到全部滞后（峰值处的甩鞭感），主体静下来时滞后收到 25%，末梢**在时间上**也提前收零。

    **映射必须强制单调**（`GAP = 0.02s` 地板）。只按 `nt = t + dt*lag(t)` 映射是不够的：
    滞后倍率在回落段变化很快，而剪辑里常有**相距 0.05s 的一对键**（如裙摆 `1.4s: -12°`
    紧跟 `1.45s: 0°`），只要滞后变化量超过键距，后一个键就会被映射到**前一个键之前** ——
    子段于是"先归零、再跳回去"，肉眼就是一次抽搐。实测这种键对：修前子骨 44 对（父骨 0 对），
    加地板后归零。`max()` 只在键过密时生效，正常间距下与朴素映射完全等价。
    """
    out = {0.0: 0.0}
    prev = 0.0
    for t, v in keys:
        if t <= 0.0 or t >= cycle:
            continue
        nt = t + dt * (lag_env(t) if lag_env else 1.0)
        nt = max(nt, prev + GAP)      # ← 单调下界：键序不能倒挂
        if nt >= cycle:
            continue
        out[round(nt, 3)] = v * scale * (env(t) if env else 1.0)
        prev = nt
    out[round(float(cycle), 3)] = 0.0
    return sorted(out.items())


def cloth_chain(c, ch, keys, cycle, root, subs,
                scales=(1.0, 0.40, 0.28, 0.18), lags=(0.0, 0.11, 0.21, 0.31),
                env=(1.24, 0.60, 0.40)):
    """布料/长发链的通用写法：根段沿用原键，子段幅度递减 + 相位递增。

    `cycle=None` 时取剪辑自己的 `length` —— 长度只有一个口径，免掉手抄错。

    **根段不加增益**：那几组键是动画师按旧版"整幅刚性"调过的，直接改会破坏已调好的观感
    （所以拆链时一律保留根骨的 pivot 与旧键，链只往**下**长）。
    链上各段的世界角度是**逐段累加**的，面纱末段的总摆幅 = 1.0+0.40+0.28+0.18 ≈ **1.86×**。
    子段配比是拿 `bride_pose_probe.py` 的侧视探测图调出来的：面纱子段取到 0.29/0.18/0.11 时
    整条链读起来仍是"整体倾斜"而不是波浪（段间弯角只有 2°/1.3°/0.8°），
    提到 0.40/0.28/0.18 后段间弯角约 2.8°/2.0°/1.3°，下摆明显滞后于上段。

    **非循环剪辑走 `chain_oneshot`**：循环版 `shift` 会让 0 点取到被移进来的中间值，
    破坏「收招归零」硬约束（自校验会报 `收招归零 -0.171 -> -0.171`）。
    """
    cycle = c.length if cycle is None else cycle
    # 相位包络只在**非循环**剪辑上用（起手/收招是技能剪辑的概念；循环里没有，且会破坏首尾等值）。
    penv = None if c.loop else phase_env(keys, cycle, env[0], env[1], env[2])
    lenv = None if c.loop else amp_norm(keys)
    for i, (sc, dt) in enumerate(zip(scales, lags)):
        if i == 0:
            c.r(root, ch, keys)
            continue
        sub = (chain(keys, cycle, sc, dt) if c.loop
               else chain_oneshot(keys, cycle, sc, dt, penv, lenv))
        c.r(subs[i - 1], ch, sub)


def veil_chain(c, ch, keys, cycle=None, scales=(1.0, 0.40, 0.28, 0.18),
               lags=(0.0, 0.11, 0.21, 0.31)):
    return cloth_chain(c, ch, keys, cycle, "veil", ("veil2", "veil3", "veil4"), scales, lags,
                       env=(1.30, 0.60, 0.34))   # 轻纱：甩得最开、起手最小、收得最紧


def sleeve_chain(c, side, ch, keys, cycle=None, scales=(1.0, 0.55), lags=(0.0, 0.12)):
    """纱袖两段的链式写法：根段绕肘（`sleeve_*`）、子段绕腕（`sleeve_*2`）。

    配比比面纱**硬**（0.55 vs 0.40）：袖子是缎的，不是纱的。滞后 0.12s —— 手臂已经扫过去了、
    袖子还在半路上，这一下拖尾就是「她用手臂打你」最直白的读数（1.1.32 之前手臂和袖子是
    同一块刚体，所以只有「转关节」没有「甩东西」）。
    """
    tag = "_" + side
    return cloth_chain(c, ch, keys, cycle, "sleeve" + tag, ("sleeve" + tag + "2",),
                       scales, lags, env=(1.22, 0.68, 0.42))


def hair_chain(c, ch, keys, cycle=None, scales=(1.0, 0.42, 0.26), lags=(0.0, 0.12, 0.23)):
    """长发三段的链式写法（比面纱少一段）。配比同样按探测图调。"""
    return cloth_chain(c, ch, keys, cycle, "hair_fall", ("hair_fall2", "hair_fall3"),
                       scales, lags, env=(1.26, 0.62, 0.38))


def side_hair_chain(c, tag, ch, keys, cycle=None, scales=(1.0, 0.45), lags=(0.0, 0.14)):
    """两侧鬓发的两段链。挂在 `head` 上 ⇒ 顺带做出「转头时发梢慢半拍」。"""
    return cloth_chain(c, ch, keys, cycle, f"hair_side_{tag}", (f"hair_side_{tag}2",),
                       scales, lags, env=(1.22, 0.65, 0.44))


def train_chain(c, ch, keys, cycle=None, scales=(1.0, 0.45), lags=(0.0, 0.15)):
    """婚裙拖尾的两段链 —— 拖尾是"该会飘"的那块，滞后给得比鬓发略长。"""
    return cloth_chain(c, ch, keys, cycle, "train", ("train2",), scales, lags,
                       env=(1.16, 0.75, 0.56))   # 厚拖尾：overshoot 小、收得慢


# 三层裙摆的子段表：根骨 → (中环骨, 下环骨)。根骨保住旧 pivot 与旧键 ⇒ 已调好的侧掀/掀裙动作全部照旧。
CLOTH_SUB = {"skirt": ("skirt2", "skirt3"), "hem_r": ("hem_r2", "hem_r3"),
             "hem_l": ("hem_l2", "hem_l3")}


def skirt_chain(c, root, ch, keys, cycle=None, scales=(1.0, 0.40, 0.25), lags=(0.0, 0.14, 0.27)):
    """裙摆三层的链式写法。配比比面纱/长发更"重"：幅度收得更紧、滞后给得更长（厚布甩不动）。"""
    return cloth_chain(c, ch, keys, cycle, root, CLOTH_SUB[root], scales, lags,
                       env=(1.14, 0.78, 0.58))   # 厚缎三层：最"沉"，包络最平


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


# ---------------------------------------------------------------------------
# 全身位移幅度表（u；1u = 6.25cm = 1px，16u = 1 block）
#
# 2026-09 复标定：此前所有剪辑的 move 骨位移都在 0.10~0.35u（0.6~2.2cm）—— 肉眼等于没动，
# 动作全靠骨骼旋转撑着，「迈步进身」这件事在模型上根本看不见。现在把**语义幅度**集中在这里，
# 各剪辑里只写形状（哪一帧朝前、哪一帧沉下去），幅度统一由这张表重标。
#
# 语义：y = 起落（呼吸/沉腰/跪）、z = 前后（负 = 朝她的正面，即 -Z）、x = 左右（+X 是她右手边）。
MOVE_AMP = {
    "idle":              {"y": 0.9},                      # 呼吸起落
    "walk":              {"y": 1.2},                      # 走路起伏
    # 注意：summon 是叠加层剪辑，不许驱动 move 骨（会和同时播的技能剪辑抢骨头），
    # 所以这里故意没有它。
    "skill_consort":     {"y": 3.5},                      # 起身（原来只有 1.5u = 9cm）
    "skill_death_chime": {"y": 2.0},                      # 立起
    "skill_soul_shriek": {"y": 2.2},                      # 后仰再前倾
    "skill_veil_snare":  {"y": 1.4},                      # 抬手沉腰
    "skill_sacrifice":   {"y": 5.0},                      # 跪下去（原来只有 0.35u = 2cm，等于没跪）
    "skill_bouquet":     {"y": 1.0, "z": 2.0},            # 前倾送花
    "skill_bridal_kiss": {"y": 1.2, "z": 6.0},            # 拉近半个方块去吻
    "skill_blood_regen": {"y": 1.2},                      # 含胸下沉
    "skill_veil_swipe":  {"y": 1.2, "z": 8.0, "x": 2.5},   # 垫步进身（半格）+ 转体横移
    "skill_veil_chop":   {"y": 3.5, "z": 5.0},             # 抬手提起 + 劈下去压身（垂直招，不前冲那么多）
    "skill_flower_dart": {"y": 1.2, "z": 2.5},             # 低位送身（刻意小于横扫：不迈步）
}


def retarget_move(clips):
    """按 MOVE_AMP 重标每个剪辑 move 骨的位置通道：**形状不动，只改振幅**。

    做法：把该轴已有键归一化到表里的幅度 —— 保留原来的节奏与方向（哪一帧朝前、
    哪一帧沉下去都不变），只把「移了多少」放大到看得见的量级。
    不在表里的轴保持原样；剪辑首尾的 0 依然是 0。
    """
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
        side_hair_chain(c, tag, "x", [(0, 0), (1.3, 1.4), (2.4, -1.0), (3.0, 0)])
    c.r("hair_bun", "x", [(0, 0), (1.3, 2.0), (2.4, -1.2), (3.0, 0)])
    c.r("hair_bun", "y", [(0, 0), (1.0, 1.6), (2.2, -1.6), (3.0, 0)])
    c.r("hair_back", "x", [(0, 0), (1.5, 1.2), (3.0, 0)])
    hair_chain(c, "x", [(0, 0), (1.6, 1.6), (3.0, 0)])
    hair_chain(c, "y", [(0, 0), (1.2, -1.0), (2.4, 1.0), (3.0, 0)])
    c.r("fringe", "x", [(0, 0), (1.4, -1.2), (3.0, 0)])
    veil_chain(c, "x", [(0, 0), (0.9, 2.5), (2.1, -1.5), (3.0, 0)], 3.0)
    veil_chain(c, "y", [(0, 0), (1.5, 1.6), (3.0, 0)], 3.0)
    skirt_chain(c, "skirt", "x", [(0, 0), (1.5, -1.0), (3.0, 0)])
    skirt_chain(c, "skirt", "y", [(0, 0), (1.0, 1.2), (2.0, -1.2), (3.0, 0)])
    train_chain(c, "x", [(0, 0), (1.2, -1.6), (2.4, 1.0), (3.0, 0)])
    skirt_chain(c, "hem_r", "x", [(0, 0), (1.4, -0.8), (3.0, 0)])
    skirt_chain(c, "hem_l", "x", [(0, 0), (1.4, -0.8), (3.0, 0)])
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
    hair_chain(w, "x", lag([(0, 0), (0.5, 2.6), (0.9, 0), (1.3, 2.6), (1.6, 0)], 0.08))
    hair_chain(w, "y", lag([(0, 0), (0.4, -1.6), (0.8, 0), (1.2, 1.6), (1.6, 0)], 0.08))
    for tag, sgn in (("r", 1), ("l", -1)):
        side_hair_chain(w, tag, "x", lag([(0, 0), (0.5, 2.2), (0.9, 0), (1.3, 2.2), (1.6, 0)], 0.08))
        w.p("bust_" + tag, "z", [(0, 0), (0.4, -0.06), (0.8, 0), (1.2, -0.06), (1.6, 0)])
    w.r("fringe", "x", lag([(0, 0), (0.5, -1.4), (0.9, 0), (1.3, -1.4), (1.6, 0)], 0.08))
    # 布料：滞后 + 幅度 ×1.4（后摆最重最迟，面纱次之，裙摆/下摆最轻）
    veil_chain(w, "x", lag(s2(-7.0), 0.15), 1.6)
    veil_chain(w, "y", lag(alt(2.8, -2.8), 0.13), 1.6)
    skirt_chain(w, "skirt", "x", lag(s2(-5.6), 0.12))
    skirt_chain(w, "skirt", "y", lag(alt(4.2, -4.2), 0.10))
    skirt_chain(w, "skirt", "z", lag(alt(2.1, -2.1), 0.10))
    train_chain(w, "x", lag(s2(-8.4), 0.16))
    skirt_chain(w, "hem_r", "x", lag(s2(-4.2), 0.10))
    skirt_chain(w, "hem_l", "x", lag(s2(-4.2), 0.10))
    skirt_chain(w, "hem_r", "z", lag(alt(2.8, -2.8), 0.12))
    skirt_chain(w, "hem_l", "z", lag(alt(-2.8, 2.8), 0.12))
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
        skirt_chain(c, "hem_" + tag, "x", [(0, 0), (0.9, -4), (1.0, -9), (1.3, -3), (2.0, 0)])
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
    skirt_chain(c, "skirt", "x", [(0, 0), (0.9, -2), (1.0, -7), (1.3, -3), (2.0, 0)])
    veil_chain(c, "x", [(0, 0), (0.9, 3), (1.0, -12), (1.35, -4), (2.0, 0)], 2.0)
    veil_chain(c, "y", [(0, 0), (0.9, -3), (1.0, 5), (2.0, 0)], 2.0)
    train_chain(c, "x", [(0, 0), (0.9, -3), (1.0, -10), (1.4, -3), (2.0, 0)])
    c.r("hair_bun", "x", [(0, 0), (0.9, 6), (1.05, -8), (1.4, -2), (2.0, 0)])
    hair_chain(c, "x", [(0, 0), (0.9, 4), (1.05, -7), (1.4, -2), (2.0, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (1.0, -0.22), (1.3, -0.05), (2.0, 0)])
        c.r("bust_" + tag, "x", [(0, 0), (0.9, 3), (1.0, -5), (2.0, 0)])
        side_hair_chain(c, tag, "x", [(0, 0), (0.9, 3), (1.05, -5), (2.0, 0)])
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
        skirt_chain(c, "hem_" + tag, "x", [(0, 0), (0.8, -6), (1.4, -22), (1.5, -30), (1.9, -12), (2.6, -3), (3.0, 0)])
        skirt_chain(c, "hem_" + tag, "y", [(0, 0), (1.4, 8 * -sg), (1.5, 10 * -sg), (2.6, 2 * -sg), (3.0, 0)])
    c.r("spine", "x", [(0, 0), (1.2, 12), (1.5, 10), (1.9, -8), (2.5, -3), (3.0, 0)])
    c.r("chest", "x", [(0, 0), (1.2, 10), (1.5, 8), (1.9, -12), (2.5, -4), (3.0, 0)])
    c.r("chest", "y", [(0, 0), (1.2, -6), (1.5, -8), (2.2, 4), (3.0, 0)])
    c.r("neck", "x", [(0, 0), (1.2, 8), (1.5, 5), (1.9, -8), (2.6, -2), (3.0, 0)])
    c.r("head", "x", [(0, 0), (1.2, 12), (1.5, 8), (1.9, -12), (2.6, -3), (3.0, 0)])
    c.r("head", "y", [(0, 0), (1.2, 6), (1.5, 8), (2.2, -5), (3.0, 0)])
    c.r("hip", "x", [(0, 0), (1.2, 6), (1.5, 4), (1.9, -4), (2.6, -1), (3.0, 0)])
    c.p("move", "y", [(0, 0), (1.2, -1.35), (1.5, -1.5), (1.9, -0.5), (2.4, 0.12), (3.0, 0)])
    skirt_chain(c, "skirt", "x", [(0, 0), (1.2, -4), (1.5, -6), (2.0, 3), (2.6, 1), (3.0, 0)])
    veil_chain(c, "x", [(0, 0), (1.2, 4), (1.5, 2), (1.8, -10), (2.4, -3), (3.0, 0)], 3.0)
    train_chain(c, "x", [(0, 0), (1.2, -5), (1.5, -7), (1.9, -12), (2.5, -3), (3.0, 0)])
    c.r("hair_bun", "x", [(0, 0), (1.2, 7), (1.5, 5), (1.9, -8), (2.6, -2), (3.0, 0)])
    hair_chain(c, "x", [(0, 0), (1.2, 5), (1.5, 3), (1.9, -6), (2.6, -2), (3.0, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (1.5, -0.14), (2.0, -0.05), (3.0, 0)])
        c.r("bust_" + tag, "x", [(0, 0), (1.2, 4), (1.9, -5), (3.0, 0)])
        side_hair_chain(c, tag, "x", [(0, 0), (1.2, 3), (1.9, -4), (3.0, 0)])
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
        skirt_chain(c, "hem_" + tag, "x", [(0, 0), (1.1, -12), (1.5, -5), (2.3, 0)])
        skirt_chain(c, "hem_" + tag, "y", [(0, 0), (1.1, 6 * -sg), (2.3, 0)])
    c.r("spine", "x", [(0, 0), (0.7, -6), (1.1, -12), (1.4, 9), (1.8, 3), (2.3, 0)])
    c.r("chest", "x", [(0, 0), (0.7, -8), (1.1, -16), (1.4, 10), (1.8, 3), (2.3, 0)])
    c.r("neck", "x", [(0, 0), (0.7, -14), (1.1, -22), (1.4, 6), (1.8, 2), (2.3, 0)])
    c.r("head", "x", [(0, 0), (0.7, -22), (1.1, -38), (1.35, -14), (1.6, 10), (2.0, 3), (2.3, 0)])
    c.r("head", "z", [(0, 0), (1.1, 8), (1.6, -4), (2.3, 0)])
    c.r("hip", "x", [(0, 0), (1.1, -5), (1.5, 4), (2.3, 0)])
    c.p("move", "y", [(0, 0), (1.1, 0.18), (1.4, -0.3), (2.3, 0)])
    skirt_chain(c, "skirt", "x", [(0, 0), (1.1, -8), (1.5, -4), (2.3, 0)])
    veil_chain(c, "x", [(0, 0), (0.8, -8), (1.1, -16), (1.6, 6), (2.3, 0)], 2.3)
    veil_chain(c, "z", [(0, 0), (1.1, 6), (2.3, 0)], 2.3)
    train_chain(c, "x", [(0, 0), (1.1, -12), (1.6, -4), (2.3, 0)])
    c.r("hair_bun", "x", [(0, 0), (0.9, -10), (1.1, -18), (1.5, 8), (2.0, 2), (2.3, 0)])
    hair_chain(c, "x", [(0, 0), (0.9, -8), (1.1, -14), (1.5, 6), (2.3, 0)])
    hair_chain(c, "z", [(0, 0), (1.1, -4), (2.3, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (1.1, 0.16), (1.5, -0.06), (2.3, 0)])
        c.r("bust_" + tag, "x", [(0, 0), (1.1, -5), (1.6, 3), (2.3, 0)])
        side_hair_chain(c, tag, "x", [(0, 0), (1.1, -6), (1.6, 4), (2.3, 0)])
    clips.append(c)

    # ---------------- 召唤（0.9s，命中窗口触发）：只驱动 hand_r / hand_l / crown ----------------
    c = Clip2("summon", 0.9)
    # 注意：summon 是**叠加层**（与技能剪辑同时播），所以不许碰 move 骨 ——
    # 两边都写 move 会在生成器的「不争骨头」自校验里直接报错。
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
        skirt_chain(c, "hem_" + tag, "x", [(0, 0), (1.1, -8), (1.25, -22), (1.7, -8), (2.2, 0)])
        skirt_chain(c, "hem_" + tag, "z", [(0, 0), (1.1, -4 * sg), (1.25, -12 * sg), (1.7, -5 * sg), (2.2, 0)])
    c.r("spine", "x", [(0, 0), (1.1, 6), (1.25, -9), (1.7, -2), (2.2, 0)])
    c.r("chest", "x", [(0, 0), (1.1, 8), (1.25, -12), (1.7, -3), (2.2, 0)])
    c.r("neck", "x", [(0, 0), (1.1, 4), (1.25, -6), (2.2, 0)])
    c.r("head", "x", [(0, 0), (1.1, 6), (1.25, -10), (1.6, -3), (2.2, 0)])
    c.r("head", "y", [(0, 0), (1.1, -3), (1.25, 3), (2.2, 0)])
    c.r("hip", "x", [(0, 0), (1.1, 4), (1.25, -5), (2.2, 0)])
    c.p("move", "y", [(0, 0), (1.1, -0.20), (1.25, 0.10), (1.7, 0.02), (2.2, 0)])
    skirt_chain(c, "skirt", "x", [(0, 0), (1.1, -10), (1.25, -30), (1.7, -12), (2.2, 0)])
    skirt_chain(c, "skirt", "z", [(0, 0), (1.1, 4), (1.25, 8), (2.2, 0)])
    veil_chain(c, "x", [(0, 0), (1.1, -14), (1.25, -34), (1.7, -8), (2.2, 0)], 2.2)
    veil_chain(c, "z", [(0, 0), (1.1, 5), (1.25, 10), (2.2, 0)], 2.2)
    train_chain(c, "x", [(0, 0), (1.1, -12), (1.25, -26), (1.7, -10), (2.2, 0)])
    c.r("hair_bun", "x", [(0, 0), (1.1, 5), (1.3, -8), (1.8, -2), (2.2, 0)])
    hair_chain(c, "x", [(0, 0), (1.1, 4), (1.3, -7), (1.8, -2), (2.2, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (1.1, 0.12), (1.35, -0.14), (2.2, 0)])
        c.r("bust_" + tag, "x", [(0, 0), (1.1, -4), (1.35, 5), (2.2, 0)])
        side_hair_chain(c, tag, "x", [(0, 0), (1.1, 4), (1.3, -6), (2.2, 0)])
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
        skirt_chain(c, "hem_" + tag, "x", [(0, 0), (1.6, -3), (1.75, -10), (2.4, -3), (2.8, 0)])
        skirt_chain(c, "hem_" + tag, "y", [(0, 0), (1.75, 5 * -sg), (2.8, 0)])
    c.r("spine", "x", [(0, 0), (1.6, 10), (1.75, -8), (2.2, -3), (2.8, 0)])
    c.r("chest", "x", [(0, 0), (1.6, 12), (1.75, -14), (2.2, -4), (2.8, 0)])
    c.r("neck", "x", [(0, 0), (1.6, 10), (1.75, -16), (2.2, -5), (2.8, 0)])
    c.r("head", "x", [(0, 0), (0.7, 10), (1.6, 20), (1.75, -28), (2.2, -8), (2.8, 0)])
    c.r("hip", "x", [(0, 0), (1.6, 6), (1.75, -4), (2.8, 0)])
    # 命中：献祭掉召奬，整个人被"托"起来一下
    c.p("move", "y", [(0, 0), (1.6, -0.35), (1.75, 0.35), (2.2, 0.15), (2.8, 0)])
    skirt_chain(c, "skirt", "x", [(0, 0), (1.6, -6), (1.75, -14), (2.3, -4), (2.8, 0)])
    veil_chain(c, "x", [(0, 0), (1.6, 4), (1.75, -20), (2.3, -6), (2.8, 0)], 2.8)
    train_chain(c, "x", [(0, 0), (1.6, -4), (1.75, -18), (2.3, -5), (2.8, 0)])
    c.r("hair_bun", "x", [(0, 0), (1.6, 5), (1.75, -12), (2.3, -4), (2.8, 0)])
    hair_chain(c, "x", [(0, 0), (1.6, 4), (1.75, -10), (2.3, -3), (2.8, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (1.6, 0.14), (1.75, -0.16), (2.2, -0.05), (2.8, 0)])
        c.r("bust_" + tag, "x", [(0, 0), (1.6, 5), (1.75, -7), (2.8, 0)])
        side_hair_chain(c, tag, "x", [(0, 0), (1.6, 4), (1.75, -9), (2.8, 0)])
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
    # 送出去那一下整个人往前给（move.z 负 = 朝正面，即 -Z）
    c.p("move", "z", [(0, 0), (1.0, 0.10), (1.2, -0.55), (1.5, -0.20), (1.9, 0)])
    for tag, sg in ZH.items():
        c.r("leg_" + tag, "x", [(0, 0), (1.0, -6), (1.2, 4), (1.9, 0)])
        c.r("leg_" + tag, "z", [(0, 0), (1.0, 4 * sg), (1.2, -2 * sg), (1.9, 0)])
        c.r("shin_" + tag, "x", [(0, 0), (1.0, -16), (1.2, -6), (1.9, 0)])
        skirt_chain(c, "hem_" + tag, "x", [(0, 0), (1.1, -9), (1.35, -14), (1.7, -5), (1.9, 0)])
        skirt_chain(c, "hem_" + tag, "y", [(0, 0), (1.1, 6 * sg), (1.45, 8 * sg), (1.9, 0)])
    skirt_chain(c, "skirt", "x", [(0, 0), (1.1, -7), (1.4, -12), (1.7, -4), (1.9, 0)])
    skirt_chain(c, "skirt", "y", [(0, 0), (1.1, -8), (1.45, -10), (1.9, 0)])
    veil_chain(c, "x", [(0, 0), (1.1, -6), (1.4, -12), (1.9, 0)], 1.9)
    train_chain(c, "x", [(0, 0), (1.1, -14), (1.45, -16), (1.9, 0)])
    c.r("hair_bun", "x", [(0, 0), (1.1, 4), (1.4, -7), (1.9, 0)])
    hair_chain(c, "x", [(0, 0), (1.1, 3), (1.4, -6), (1.9, 0)])
    hair_chain(c, "y", [(0, 0), (1.1, -5), (1.45, -7), (1.9, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (1.1, 0.10), (1.45, -0.12), (1.9, 0)])
        side_hair_chain(c, tag, "x", [(0, 0), (1.1, 3), (1.45, -6), (1.9, 0)])
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
        skirt_chain(c, "hem_" + tag, "x", [(0, 0), (1.0, -6), (1.3, -9), (1.8, 0)])
    skirt_chain(c, "skirt", "x", [(0, 0), (1.0, -8), (1.3, -10), (1.8, 0)])
    veil_chain(c, "x", [(0, 0), (1.0, 6), (1.3, -8), (1.8, 0)], 1.8)
    train_chain(c, "x", [(0, 0), (1.0, -12), (1.3, -8), (1.8, 0)])
    c.r("hair_bun", "x", [(0, 0), (1.0, 6), (1.3, -6), (1.8, 0)])
    hair_chain(c, "x", [(0, 0), (1.0, 5), (1.3, -5), (1.8, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (1.0, -0.14), (1.3, -0.05), (1.8, 0)])
        c.r("bust_" + tag, "x", [(0, 0), (1.0, 4), (1.3, -3), (1.8, 0)])
        side_hair_chain(c, tag, "x", [(0, 0), (1.0, 5), (1.3, -5), (1.8, 0)])
    clips.append(c)

    # ---------------- 技能八：血纱回春（2.6s，命中 0.9s）合抱收纱 → 仰头开花、血回全身 ----------------
    c = Clip2("skill_blood_regen", 2.6)
    # 双臂收到胸前合抱：x 略抬、z 内收，前臂折起来 —— 读作「把血收进怀里」
    c.r("arm_r", "x", [(0, 0), (0.45, -6), (0.9, -24), (1.35, -16), (2.6, 0)])
    c.r("arm_r", "z", [(0, 0), (0.45, 10), (0.9, 24), (1.35, 16), (2.6, 0)])
    c.r("forearm_r", "x", [(0, 0), (0.45, 12), (0.9, 28), (1.35, 18), (2.6, 0)])
    c.r("arm_l", "x", [(0, 0), (0.45, -6), (0.9, -24), (1.35, -16), (2.6, 0)])
    c.r("arm_l", "z", [(0, 0), (0.45, -10), (0.9, -24), (1.35, -16), (2.6, 0)])
    c.r("forearm_l", "x", [(0, 0), (0.45, 12), (0.9, 28), (1.35, 18), (2.6, 0)])
    c.r("shoulder_r", "x", [(0, 0), (0.9, -4), (1.35, 2), (2.6, 0)])
    c.r("shoulder_l", "x", [(0, 0), (0.9, -4), (1.35, 2), (2.6, 0)])
    # 含胸低头（收）→ 命中后仰头开胸（放）：这条曲线的正负切换就是「回血落下来」的读点
    c.r("spine", "x", [(0, 0), (0.9, 10), (1.35, -7), (2.6, 0)])
    c.r("chest", "x", [(0, 0), (0.9, 9), (1.35, -8), (2.6, 0)])
    c.r("neck", "x", [(0, 0), (0.9, 7), (1.35, -9), (2.6, 0)])
    c.r("head", "x", [(0, 0), (0.9, 9), (1.35, -13), (2.6, 0)])
    c.r("hip", "x", [(0, 0), (0.9, 6), (1.35, -3), (2.6, 0)])
    # 先下沉（收势）再微微浮起（血回上来的那一瞬）
    c.p("move", "y", [(0, 0), (0.9, -0.12), (1.35, 0.05), (2.6, 0)])
    for tag, sg in ZH.items():
        c.r("leg_" + tag, "x", [(0, 0), (0.9, -7), (1.35, -2), (2.6, 0)])
        c.r("shin_" + tag, "x", [(0, 0), (0.9, -16), (1.35, -7), (2.6, 0)])
        c.r("foot_" + tag, "x", [(0, 0), (0.9, 7), (1.35, 3), (2.6, 0)])
        skirt_chain(c, "hem_" + tag, "x", [(0, 0), (0.9, -5), (1.35, -8), (2.6, 0)])
        side_hair_chain(c, tag, "x", [(0, 0), (0.9, 4), (1.35, -5), (2.6, 0)])
        c.p("bust_" + tag, "z", [(0, 0), (0.9, 0.10), (1.35, -0.10), (2.6, 0)])
    skirt_chain(c, "skirt", "x", [(0, 0), (0.9, -7), (1.35, -9), (2.6, 0)])
    veil_chain(c, "x", [(0, 0), (0.9, 5), (1.35, -9), (2.6, 0)], 2.6)
    train_chain(c, "x", [(0, 0), (0.9, -11), (1.35, -7), (2.6, 0)])
    c.r("hair_bun", "x", [(0, 0), (0.9, 5), (1.35, -6), (2.6, 0)])
    hair_chain(c, "x", [(0, 0), (0.9, 4), (1.35, -5), (2.6, 0)])
    hair_chain(c, "y", [(0, 0), (0.9, -3), (1.35, 4), (2.6, 0)])
    clips.append(c)

    # ---------------- 技能九：纱袖横扫（2.0s，命中 1.0s）提袖后引 → 反手横抡 → 收招 ----------------
    # 近战招。与「抛花束」区分开：那一套是右臂过肩的垂直面鞭打，这一套走水平面的抡扫 ——
    # 主动轴放在 z（体侧外展）而不是 x（抬举），出手方向是「横着扫过去」。
    c = Clip2("skill_veil_swipe", 2.0)
    # 抬臂（x）与横扫（z）**分两段做**：0~0.9 先把手臂抬到肩高，0.9~1.2 再横扫出去。
    # 只在 z 上做横扫时，手臂垂在髋部高度横着抹，第三人称侧后方视角看就是一条线 ——
    # 这是 1.1.32 之前「手臂攻击不明显」的主因（x 全程只有 Δ20°，还不如一个送花动作）。
    c.r("arm_r", "x", [(0, 0), (0.5, -12), (0.9, 74), (1.2, 62), (1.5, 30), (2.0, 0)])
    c.r("arm_r", "z", [(0, 0), (0.5, -34), (0.9, -58), (1.2, 46), (1.5, 16), (2.0, 0)])
    c.r("forearm_r", "x", [(0, 0), (0.5, 26), (1.0, 44), (1.2, -12), (1.5, 6), (2.0, 0)])
    c.r("forearm_r", "y", [(0, 0), (1.0, -14), (1.2, 16), (2.0, 0)])
    # 肩膀从此参与：x 抬举、y 送肩/收肩、z 耸肩压肩。三轴都用上，胳膊才不像甩木棍
    # （数据上 `shoulder_*` 的 y/z 以前在全部 13 个剪辑里恒为 0）。
    c.r("shoulder_r", "x", [(0, 0), (0.5, -8), (0.9, 30), (1.2, 22), (1.6, 6), (2.0, 0)])
    c.r("shoulder_r", "y", [(0, 0), (0.9, -14), (1.2, 16), (1.6, 4), (2.0, 0)])
    c.r("shoulder_r", "z", [(0, 0), (0.5, -6), (0.9, -20), (1.2, 14), (2.0, 0)])
    # 纱袖：跟手臂同向但晚 0.12s。命中帧（1.2）袖子还在半路上（x 44 / z -22），
    # 1.5 才追过头甩到 96 / 68 —— 这一下拖尾就是「纱袖抽过去」。
    sleeve_chain(c, "r", "x", [(0, 0), (0.95, 34), (1.2, 44), (1.5, 96), (1.75, 30), (2.0, 0)], 2.0)
    sleeve_chain(c, "r", "z", [(0, 0), (0.9, -30), (1.2, -22), (1.5, 68), (1.8, 16), (2.0, 0)], 2.0)
    sleeve_chain(c, "l", "x", [(0, 0), (1.0, 10), (1.35, -16), (1.7, 5), (2.0, 0)], 2.0)
    sleeve_chain(c, "l", "z", [(0, 0), (1.0, -14), (1.35, 20), (1.7, -5), (2.0, 0)], 2.0)
    c.r("arm_l", "z", [(0, 0), (1.0, 22), (1.2, -26), (1.6, -8), (2.0, 0)])
    c.r("arm_l", "x", [(0, 0), (1.0, 12), (1.2, -8), (2.0, 0)])
    c.r("forearm_l", "x", [(0, 0), (1.0, 20), (1.2, -6), (2.0, 0)])
    # 转体：腰先拧到右后，出手那一下整条脊柱甩到左前 —— 横扫的力从这里来
    c.r("spine", "y", [(0, 0), (1.0, 18), (1.2, -24), (1.6, -6), (2.0, 0)])
    c.r("spine", "x", [(0, 0), (1.0, -5), (1.2, 7), (2.0, 0)])
    c.r("chest", "y", [(0, 0), (1.0, 26), (1.2, -30), (1.6, -7), (2.0, 0)])
    c.r("chest", "x", [(0, 0), (1.0, 4), (1.2, -6), (2.0, 0)])
    c.r("neck", "y", [(0, 0), (1.0, -10), (1.2, 14), (2.0, 0)])
    c.r("head", "y", [(0, 0), (1.0, -16), (1.2, 20), (1.5, 5), (2.0, 0)])
    c.r("head", "x", [(0, 0), (1.0, -6), (1.2, 6), (2.0, 0)])
    c.r("hip", "y", [(0, 0), (1.0, 12), (1.2, -14), (2.0, 0)])
    c.r("hip", "z", [(0, 0), (1.0, 4), (1.2, -5), (2.0, 0)])
    # 重心：后引时沉腰，出手那一下整个人压进去（move.z 负 = 朝正面，即 -Z）
    c.p("move", "y", [(0, 0), (1.0, -0.20), (1.2, 0.06), (1.5, 0.02), (2.0, 0)])
    c.p("move", "z", [(0, 0), (1.0, 0.08), (1.2, -0.14), (1.6, -0.04), (2.0, 0)])
    # 转体横移：重心跟着手臂的挥向走（后引时压在挥击的反侧，命中那一下甩到同侧）。
    # 方向是拿正向运动学量出来的相对量：命中帧右手从 x=-1.1 扫到 +3.0，所以重心取同号。
    c.p("move", "x", [(0, 0), (1.0, 0.4), (1.2, -1.0), (1.6, -0.25), (2.0, 0)])
    for tag, sg in ZH.items():
        c.r("leg_" + tag, "x", [(0, 0), (1.0, -8 * sg), (1.2, 6 * sg), (2.0, 0)])
        c.r("leg_" + tag, "z", [(0, 0), (1.0, 5 * sg), (1.2, -3 * sg), (2.0, 0)])
        c.r("shin_" + tag, "x", [(0, 0), (1.0, -14), (1.2, -6), (2.0, 0)])
        skirt_chain(c, "hem_" + tag, "y", [(0, 0), (1.1, 12 * sg), (1.45, 16 * sg),
                                           (1.75, 5 * sg), (2.0, 0)])
        skirt_chain(c, "hem_" + tag, "x", [(0, 0), (1.1, -8), (1.4, -13), (1.75, -5), (2.0, 0)])
    # 裙摆被横扫带得横甩 —— 这一套的裙摆是「横向」的，跟其它技能的前后掀不同
    skirt_chain(c, "skirt", "y", [(0, 0), (1.1, -14), (1.45, -18), (1.8, -6), (2.0, 0)])
    skirt_chain(c, "skirt", "x", [(0, 0), (1.1, -8), (1.4, -12), (1.75, -4), (2.0, 0)])
    veil_chain(c, "y", [(0, 0), (1.1, 14), (1.45, 18), (1.8, 6), (2.0, 0)], 2.0)
    veil_chain(c, "x", [(0, 0), (1.1, -7), (1.4, -13), (1.8, -4), (2.0, 0)], 2.0)
    train_chain(c, "y", [(0, 0), (1.1, -12), (1.45, -15), (2.0, 0)])
    train_chain(c, "x", [(0, 0), (1.1, -14), (1.45, -17), (2.0, 0)])
    c.r("hair_bun", "x", [(0, 0), (1.1, 5), (1.4, -8), (2.0, 0)])
    hair_chain(c, "x", [(0, 0), (1.1, 4), (1.4, -7), (2.0, 0)])
    hair_chain(c, "y", [(0, 0), (1.1, -6), (1.45, -9), (2.0, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (1.1, 0.12), (1.45, -0.14), (2.0, 0)])
        side_hair_chain(c, tag, "x", [(0, 0), (1.1, 4), (1.45, -7), (2.0, 0)])
    clips.append(c)

    # ---------------- 技能十：抛花刺（1.8s，命中 0.9s）侧身沉肩 → 低位前送甩出 → 收招 ----------------
    # 远程招。与「抛花束」的区分点在于**出手高度**：花束是过肩的高位鞭打（后仰 → 前挥），
    # 这一套是侧身低位的甩掷（沉肩 → 前送），像甩飞刀；出手点低、轨迹平，跟抛物线的花对得上。
    c = Clip2("skill_flower_dart", 1.8)
    # 保留「侧身低位甩掷」的性格，但把「后引 → 前送」做成真动作：后引时手臂往后（x 负），
    # 出手时前送到 46°（x 正）。原来出手落在 0° 附近 —— 手臂基本垂着，看着像耸了下肩。
    c.r("arm_r", "x", [(0, 0), (0.35, -22), (0.9, 46), (1.2, 30), (1.8, 0)])
    c.r("arm_r", "z", [(0, 0), (0.35, -26), (0.9, 52), (1.2, 22), (1.8, 0)])
    c.r("arm_r", "y", [(0, 0), (0.35, -10), (0.9, 12), (1.8, 0)])
    c.r("forearm_r", "x", [(0, 0), (0.35, 38), (0.9, -22), (1.2, 6), (1.8, 0)])
    c.r("forearm_r", "z", [(0, 0), (0.35, -10), (0.9, 12), (1.8, 0)])
    # 肩膀同上：三轴参与，出手那一下把右肩整片送出去
    c.r("shoulder_r", "x", [(0, 0), (0.35, -14), (0.9, 24), (1.3, 6), (1.8, 0)])
    c.r("shoulder_r", "y", [(0, 0), (0.35, -10), (0.9, 13), (1.3, 4), (1.8, 0)])
    c.r("shoulder_r", "z", [(0, 0), (0.35, -8), (0.9, 15), (1.2, 5), (1.8, 0)])
    # 纱袖：比手臂晚约 0.15s 追上 —— 甩出去那一下袖口整幅横过身前
    sleeve_chain(c, "r", "x", [(0, 0), (0.5, -12), (1.05, 26), (1.4, 78), (1.7, 12), (1.8, 0)], 1.8)
    sleeve_chain(c, "r", "z", [(0, 0), (0.5, -18), (1.05, 30), (1.4, 88), (1.7, 14), (1.8, 0)], 1.8)
    sleeve_chain(c, "l", "x", [(0, 0), (0.9, 12), (1.3, -14), (1.6, 4), (1.8, 0)], 1.8)
    # 左臂在身前做「递花」的配重，出手时收回体侧
    c.r("arm_l", "x", [(0, 0), (0.35, -14), (0.9, -22), (1.2, -8), (1.8, 0)])
    c.r("arm_l", "z", [(0, 0), (0.9, -18), (1.3, -6), (1.8, 0)])
    c.r("forearm_l", "x", [(0, 0), (0.9, 26), (1.3, 8), (1.8, 0)])
    # 侧身：先把右肩让出来，甩出手之后回正
    c.r("spine", "y", [(0, 0), (0.35, 14), (0.9, -16), (1.3, -5), (1.8, 0)])
    c.r("spine", "x", [(0, 0), (0.35, 8), (0.9, -4), (1.8, 0)])
    c.r("chest", "y", [(0, 0), (0.35, 18), (0.9, -22), (1.3, -6), (1.8, 0)])
    c.r("chest", "x", [(0, 0), (0.35, 6), (0.9, -4), (1.8, 0)])
    c.r("neck", "y", [(0, 0), (0.9, 8), (1.3, 3), (1.8, 0)])
    c.r("head", "y", [(0, 0), (0.35, -10), (0.9, 12), (1.8, 0)])
    c.r("head", "x", [(0, 0), (0.35, -5), (0.9, 4), (1.8, 0)])
    c.r("hip", "y", [(0, 0), (0.35, 8), (0.9, -9), (1.8, 0)])
    c.r("hip", "z", [(0, 0), (0.35, 3), (0.9, -3), (1.8, 0)])
    # 重心：低抛靠沉肩沉腰，出手那一下往下压 —— 与花束的「后仰再鞭打」正好相反
    c.p("move", "y", [(0, 0), (0.45, -0.18), (0.9, -0.10), (1.3, -0.03), (1.8, 0)])
    c.p("move", "z", [(0, 0), (0.9, -0.12), (1.3, -0.04), (1.8, 0)])
    for tag, sg in ZH.items():
        c.r("leg_" + tag, "x", [(0, 0), (0.45, -7), (0.9, 5), (1.8, 0)])
        c.r("shin_" + tag, "x", [(0, 0), (0.45, -16), (0.9, -6), (1.8, 0)])
        c.r("foot_" + tag, "x", [(0, 0), (0.45, 6), (1.8, 0)])
        skirt_chain(c, "hem_" + tag, "x", [(0, 0), (0.9, -8), (1.2, -12), (1.6, -4), (1.8, 0)])
        skirt_chain(c, "hem_" + tag, "y", [(0, 0), (0.9, 7 * sg), (1.25, 9 * sg), (1.8, 0)])
    skirt_chain(c, "skirt", "x", [(0, 0), (0.9, -6), (1.2, -10), (1.6, -3), (1.8, 0)])
    skirt_chain(c, "skirt", "y", [(0, 0), (0.9, -7), (1.25, -9), (1.8, 0)])
    veil_chain(c, "x", [(0, 0), (0.9, -7), (1.2, -11), (1.8, 0)], 1.8)
    train_chain(c, "x", [(0, 0), (0.9, -15), (1.25, -18), (1.8, 0)])
    c.r("hair_bun", "x", [(0, 0), (0.9, 4), (1.25, -6), (1.8, 0)])
    hair_chain(c, "x", [(0, 0), (0.9, 3), (1.25, -5), (1.8, 0)])
    hair_chain(c, "y", [(0, 0), (0.9, -5), (1.25, -7), (1.8, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (0.9, 0.09), (1.25, -0.10), (1.8, 0)])
        side_hair_chain(c, tag, "x", [(0, 0), (0.9, 3), (1.25, -5), (1.8, 0)])
    clips.append(c)

    # ---------------- 纱袖下劈（2.1s，第 1.1s 结算）：抬臂过顶 → 直劈而下 ----------------
    # 与「横扫」的分工：横扫走**水平面**（面杀伤，宽）、这一套走**垂直面**（点杀伤，重）。
    # 垂直面是第三人称侧后方视角最好读的平面 —— 抬手过顶到劈下的 125°/0.25s 是全场最快的
    # 一段位移，一眼就知道「她在劈我」。袖子整幅比手臂晚 0.25s 才翻下来，砸完还在头顶，
    # 于是「纱袖」这一下的量感比手臂本身大得多。
    c = Clip2("skill_veil_chop", 2.1)
    c.r("arm_r", "x", [(0, 0), (0.45, -18), (0.85, 145), (1.1, 20), (1.4, 8), (2.1, 0)])
    c.r("arm_r", "z", [(0, 0), (0.85, -14), (1.1, 4), (1.4, 2), (2.1, 0)])
    c.r("forearm_r", "x", [(0, 0), (0.45, -26), (0.85, -42), (1.1, 26), (1.45, 10), (2.1, 0)])
    # 肩膀三轴参与：抬举（x）把整片肩送上去，y/z 跟着转，「劈」才是身体的动作而不是胳膊的
    c.r("shoulder_r", "x", [(0, 0), (0.45, -10), (0.85, 34), (1.1, 10), (1.5, 4), (2.1, 0)])
    c.r("shoulder_r", "y", [(0, 0), (0.85, -12), (1.1, 8), (2.1, 0)])
    c.r("shoulder_r", "z", [(0, 0), (0.85, -18), (1.1, 12), (2.1, 0)])
    # 左臂做配重：抬起时往后、劈下时收到身前
    c.r("arm_l", "x", [(0, 0), (0.85, -22), (1.1, 14), (1.5, 4), (2.1, 0)])
    c.r("arm_l", "z", [(0, 0), (0.85, -10), (1.1, -14), (1.8, -4), (2.1, 0)])
    c.r("forearm_l", "x", [(0, 0), (0.85, 20), (1.1, -10), (2.1, 0)])
    # 袖子：抬手时落在手臂后面（110 vs 145），劈下去时**还挂在头顶 140** ——
    # 那一下整幅布才砸下来（1.45 到 -16 甩过头），这是这一套最值钱的一帧
    sleeve_chain(c, "r", "x", [(0, 0), (0.9, 110), (1.2, 140), (1.45, -16), (1.8, 18), (2.1, 0)], 2.1)
    sleeve_chain(c, "r", "z", [(0, 0), (0.9, -8), (1.2, -10), (1.5, 10), (2.1, 0)], 2.1)
    sleeve_chain(c, "l", "x", [(0, 0), (0.9, -18), (1.25, -8), (1.5, 14), (2.1, 0)], 2.1)
    # 躯干：抬臂时后仰（x 负），劈下时整条脊柱折进去（x 正 22°）—— 力的来源在这里
    c.r("spine", "x", [(0, 0), (0.85, -14), (1.1, 22), (1.5, 6), (2.1, 0)])
    c.r("spine", "y", [(0, 0), (0.85, 8), (1.1, -6), (2.1, 0)])
    c.r("chest", "x", [(0, 0), (0.85, -10), (1.1, 18), (1.5, 5), (2.1, 0)])
    c.r("chest", "y", [(0, 0), (0.85, 10), (1.1, -8), (2.1, 0)])
    c.r("neck", "x", [(0, 0), (0.85, 6), (1.1, 10), (2.1, 0)])
    c.r("head", "x", [(0, 0), (0.85, -4), (1.1, 16), (1.5, 5), (2.1, 0)])
    c.r("hip", "x", [(0, 0), (0.85, -6), (1.1, 10), (2.1, 0)])
    # 重心：抬手时提起来、劈下时压下去（y 由 MOVE_AMP 重标到 3.5u），前冲 5u
    c.p("move", "y", [(0, 0), (0.85, 0.10), (1.1, -0.22), (1.6, -0.05), (2.1, 0)])
    c.p("move", "z", [(0, 0), (0.85, 0.12), (1.1, -0.42), (1.6, -0.12), (2.1, 0)])
    for tag, sg in ZH.items():
        c.r("leg_" + tag, "x", [(0, 0), (0.85, -7), (1.1, 9), (1.6, 3), (2.1, 0)])
        c.r("leg_" + tag, "z", [(0, 0), (0.85, 4 * sg), (1.1, -3 * sg), (2.1, 0)])
        c.r("shin_" + tag, "x", [(0, 0), (0.85, -12), (1.1, -5), (2.1, 0)])
        c.r("foot_" + tag, "x", [(0, 0), (0.85, 5), (1.1, -4), (2.1, 0)])
        skirt_chain(c, "hem_" + tag, "x", [(0, 0), (0.9, 6), (1.15, -14), (1.55, -5), (2.1, 0)])
        skirt_chain(c, "hem_" + tag, "y", [(0, 0), (0.95, 5 * sg), (1.3, 8 * sg), (2.1, 0)])
    # 裙摆与拖尾被「提起来再砸下去」带得先浮后沉 —— 和横扫的横向甩完全不同的读法
    skirt_chain(c, "skirt", "x", [(0, 0), (0.9, 7), (1.15, -15), (1.6, -5), (2.1, 0)])
    veil_chain(c, "x", [(0, 0), (0.9, 8), (1.15, -16), (1.6, -5), (2.1, 0)], 2.1)
    veil_chain(c, "y", [(0, 0), (0.95, 5), (1.3, 8), (2.1, 0)], 2.1)
    train_chain(c, "x", [(0, 0), (0.9, 10), (1.15, -20), (1.7, -6), (2.1, 0)])
    c.r("hair_bun", "x", [(0, 0), (0.9, -6), (1.15, 10), (2.1, 0)])
    hair_chain(c, "x", [(0, 0), (0.9, -5), (1.15, 9), (2.1, 0)])
    for tag in ("r", "l"):
        c.p("bust_" + tag, "z", [(0, 0), (0.95, 0.10), (1.3, -0.12), (2.1, 0)])
        side_hair_chain(c, tag, "x", [(0, 0), (0.9, -4), (1.15, 8), (2.1, 0)])
    clips.append(c)

    retarget_move(clips)
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
              "skill_bouquet": ("BOUQUET", 1.2), "skill_bridal_kiss": ("BRIDAL_KISS", 1.0),
              "skill_blood_regen": ("BLOOD_REGEN", 0.9),
              "skill_veil_swipe": ("VEIL_SWIPE", 1.0), "skill_flower_dart": ("FLOWER_DART", 0.9)}
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