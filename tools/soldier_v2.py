"""军装士兵僵尸（残兵）—— 几何 + 贴图生成器（纯标准库，可重复）。

设计依据：`art/soldier/DESIGN.md`（从参考图提取的配色与装备）。规范沿用项目铁律：
16u = 1Block、1u = 1px、贴图 128×128、模型面朝 -Z、`_r` 在 x>0、rest 姿态全零旋转。

产物：
    art/soldier/soldier_zombie.geo.json          ← 几何（GeckoLib 直接吃）
    art/soldier/soldier_archer.png                ← 弓手变种贴图
    art/soldier/soldier_sapper.png                ← 爆破兵变种贴图
    art/soldier/soldier_atlas.json                ← 图集台账（每块每个面的 UV + 画法）
    src/main/resources/assets/apocalypse_zombies/geo/soldier_zombie.geo.json
    src/main/resources/assets/apocalypse_zombies/textures/entity/soldier/*.png

**可重复性**：同一份输入跑两遍 sha256 必须一致。所有"随机"都走 `_sh()`（md5 派生的稳定哈希），
不用内建 `hash()`（它带进程随机盐，会让贴图每跑一次都不一样）。
"""
import hashlib
import json
import pathlib
import struct
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = ROOT / "art" / "soldier"
SRC = ROOT / "src" / "main" / "resources" / "assets" / "apocalypse_zombies"

IDENT = "soldier_zombie"
GEO_NAME = IDENT + ".geo.json"
TEX_DIR_REL = "textures/entity/soldier/"
VARIANTS = ("archer", "sapper")

TEX_W = 128
TEX_H = 128
FACE_ORDER = ("n", "s", "e", "w", "u", "d")
GEO_FACE = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}
# 面明暗：上最亮、下最暗、正面接近本色、背面压一档 —— 平面色块靠这个出体积
FACE_SHADE = {"u": 1.10, "n": 1.00, "e": 0.90, "w": 0.90, "s": 0.84, "d": 0.72}

BONES = []
CUBES = []


# --------------------------------------------------------------------------- 几何层
def bone(name, pivot, parent=None):
    BONES.append({"name": name, "pivot": [round(float(v), 3) for v in pivot], "parent": parent})


def cube(bone_name, box, part, out=None):
    """box=(x0,y0,z0,x1,y1,z1)，单位 u。part=画法名（见 PALETTE）。

    out：贴片（贴在别的体块表面上的一层薄片）**朝外**的那张脸。细节（发光眼、血渍掩膜）
    只画在它上面，另外五张脸填实色 —— 留空就是洞口，会看见模型内部。

    **所有面都上色**：早先版本给"贴片"体块只画一个面、其余留空，结果那些留空的面
    在渲染/游戏里就是洞口（能透过胸口看到背后的箭袋）。细节靠"在哪张脸上叠字"表达
    （见 render_texture 的 band / stencil_mp），不靠留空。
    """
    x0, y0, z0, x1, y1, z1 = [round(float(v), 3) for v in box]
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    z0, z1 = sorted((z0, z1))
    assert x1 > x0 and y1 > y0 and z1 > z0, f"{part}: 退化体块 {(x0, y0, z0, x1, y1, z1)}"
    CUBES.append({"bone": bone_name, "box": [x0, y0, z0, x1, y1, z1],
                  "part": part, "out": out})


def build_model():
    bone("root", (0, 0, 0))          # 不参与动画的挂点（GeckoLib 从 root 往下找骨）
    # ---- 腿：左右镜像（_r 在 x>0）----
    for tag, sg in (("r", 1), ("l", -1)):
        bone("leg_" + tag, (2 * sg, 13, 0), "hip")
        bone("shin_" + tag, (2 * sg, 6.5, 0), "leg_" + tag)
        bone("foot_" + tag, (2 * sg, 2.0, 0), "shin_" + tag)
        # 大腿（裤）
        cube("leg_" + tag, (0.4 * sg, 6.4, -2.1, 3.8 * sg, 13.3, 2.1), "pants")
        # 小腿（裤）+ 绑腿
        cube("shin_" + tag, (0.6 * sg, 2.6, -1.9, 3.6 * sg, 6.6, 1.9), "pants")
        cube("shin_" + tag, (0.45 * sg, 2.5, -2.05, 3.75 * sg, 4.8, 2.05), "gaiter")
        # 靴：鞋头往 -Z 前伸
        cube("foot_" + tag, (0.5 * sg, 0.0, -3.4, 3.7 * sg, 1.6, 2.05), "boot")
        cube("foot_" + tag, (0.6 * sg, 1.55, -1.6, 3.6 * sg, 2.6, 1.9), "boot")

    # ---- 骨盆 / 腰带 ----
    bone("hip", (0, 13, 0), "root")
    cube("hip", (-4.0, 11.9, -2.4, 4.0, 13.5, 2.4), "pants")
    cube("hip", (-4.25, 12.3, -2.7, 4.25, 13.7, 2.7), "belt")
    cube("hip", (-1.0, 12.5, -2.95, 1.0, 13.5, 2.85), "buckle")
    for sg in (1, -1):
        cube("hip", (1.4 * sg, 11.6, -3.35, 3.5 * sg, 14.6, -2.55), "pouch")
        cube("hip", (2.9 * sg, 11.6, 2.5, 4.3 * sg, 14.2, 2.9), "pouch")

    # ---- 腹 / 胸 ----
    bone("spine", (0, 13.4, 0), "hip")
    cube("spine", (-3.9, 13.4, -2.35, 3.9, 18.6, 2.15), "jacket")
    bone("chest", (0, 18.6, 0), "spine")
    cube("chest", (-4.4, 18.6, -2.45, 4.4, 25.4, 2.25), "jacket")
    # 战术马甲（比外套外凸一点）+ 两条肩带
    cube("chest", (-4.55, 19.1, -2.95, 4.55, 25.1, 2.35), "vest")
    for sg in (1, -1):
        cube("chest", (2.15 * sg, 18.8, -3.0, 3.25 * sg, 26.1, 2.4), "strap")
    # 背后箭袋 + 三支露头的箭
    cube("chest", (-3.6, 19.2, 2.3, -0.7, 26.0, 3.6), "quiver")
    for i, dx in enumerate((-3.1, -2.3, -1.5)):
        cube("chest", (dx - 0.25, 26.0, 2.6, dx + 0.25, 29.2, 3.1), "arrow")
        cube("chest", (dx - 0.45, 28.6, 2.45, dx + 0.45, 29.9, 3.25), "fletch")

    # ---- 颈 / 头 / 盔 ----
    bone("neck", (0, 25.4, 0), "chest")
    cube("neck", (-1.6, 24.9, -1.6, 1.6, 26.6, 1.6), "skin")
    bone("head", (0, 26.6, 0), "neck")
    cube("head", (-4.0, 26.4, -4.0, 4.0, 32.4, 4.0), "skin")
    # 面部：两眼发光 + 嘴。眼睛做成 2u×2u 的贴片（1u=1px，1u 高的眼睛在贴图上只有 1px，
    # 实机里等于看不见）；贴片厚 0.6u 是为了让侧面也有非零 UV 矩形，不留退化面。
    cube("head", (-3.4, 29.0, -4.60, -1.4, 31.0, -4.0), "eye_glow", out="n")
    cube("head", (1.4, 29.0, -4.60, 3.4, 31.0, -4.0), "eye_glow", out="n")
    cube("head", (-1.8, 26.5, -4.58, 1.8, 28.5, -4.0), "mouth", out="n")
    cube("head", (-4.58, 27.4, -3.2, -4.0, 29.6, -0.8), "gore", out="w")
    # 头盔整顶抬到眼睛（29.0~31.0）之上，否则盔檐会把发光的眼睛盖掉
    bone("helmet", (0, 26.6, 0), "head")
    cube("helmet", (-4.3, 31.5, -4.3, 4.3, 33.6, 4.3), "helmet")
    cube("helmet", (-4.7, 31.0, -4.95, 4.7, 31.9, 4.7), "helmet_rim")
    cube("helmet", (-1.1, 31.5, -5.15, 1.1, 32.9, -4.35), "helmet_plate")

    # ---- 臂：左右镜像 ----
    for tag, sg in (("r", 1), ("l", -1)):
        bone("arm_" + tag, (5.2 * sg, 23.5, 0), "chest")
        bone("forearm_" + tag, (5.2 * sg, 17.5, 0), "arm_" + tag)
        bone("hand_" + tag, (5.4 * sg, 12.4, 0), "forearm_" + tag)
        cube("arm_" + tag, (3.55 * sg, 17.5, -2.0, 7.25 * sg, 23.5, 2.0), "jacket")
        # 臂章：一圈略外凸的浅色带，正面与外侧各一个 M（4×4 的面放不下 3×5 字形）
        if tag == "r":
            cube("arm_" + tag, (3.4 * sg, 18.4, -2.5, 7.4 * sg, 22.4, 2.5), "band")
        # 右前臂整块是血：只有它朝外的 e 面做污渍掩膜
        cube("forearm_" + tag, (3.65 * sg, 12.4, -1.9, 7.15 * sg, 17.5, 1.9),
             "gore" if tag == "r" else "jacket", out="e" if tag == "r" else None)
        cube("hand_" + tag, (4.05 * sg, 10.3, -1.7, 6.85 * sg, 12.5, 1.7), "skin")
        # 手指：三根短块，比光秃秃的手更像尸手
        for fx in (-1.15, 0.0, 1.15):
            cube("hand_" + tag, ((5.4 + fx) * sg - 0.3, 9.5, -1.5, (5.4 + fx) * sg + 0.3, 10.4, 1.5), "skin")

    # ---- 弓：只在右手，整条做成骨骼树（弓把 + 上下梢 + 两段弦）----
    # 弓面向 -z（模型朝前），弓把向前凸、弦在两个弓梢之间走直线，
    # 拉弓就是把两段弦各自绕自己的弓梢往 +z 转同一个角度。
    bone("bow", (7.2, 11.6, -1.0), "hand_r")
    cube("bow", (6.5, 9.6, -2.40, 7.9, 13.6, -1.10), "bow_wood")
    bone("bow_limb_up", (7.2, 13.6, -1.75), "bow")
    cube("bow_limb_up", (6.7, 13.6, -2.20, 7.7, 16.0, -0.90), "bow_wood")
    cube("bow_limb_up", (6.9, 16.0, -1.80, 7.5, 18.2, -0.50), "bow_wood")
    cube("bow_limb_up", (7.0, 18.2, -1.40, 7.4, 19.4, -0.20), "bow_wood")
    bone("bow_limb_low", (7.2, 9.6, -1.75), "bow")
    cube("bow_limb_low", (6.7, 7.2, -2.20, 7.7, 9.6, -0.90), "bow_wood")
    cube("bow_limb_low", (6.9, 5.0, -1.80, 7.5, 7.2, -0.50), "bow_wood")
    cube("bow_limb_low", (7.0, 3.8, -1.40, 7.4, 5.0, -0.20), "bow_wood")
    # 弦：上段绕上梢、下段绕下梢，静置时两段接成一条直线（rest 零旋转的铁律）
    bone("bow_string_up", (7.2, 19.4, -0.05), "bow_limb_up")
    cube("bow_string_up", (7.0, 11.6, -0.20, 7.4, 19.4, 0.10), "bow_string")
    bone("bow_string_down", (7.2, 3.8, -0.05), "bow_limb_low")
    cube("bow_string_down", (7.0, 3.8, -0.20, 7.4, 11.6, 0.10), "bow_string")

    # 胸口的血（贴在马甲正面的一层薄片）
    cube("chest", (0.4, 19.6, -3.05, 4.2, 23.0, -2.96), "gore", out="n")

    # ---- 引信点燃的 TNT：与弓同构，整条建在骨骼树里 ----
    # 为什么不走原版物品层：主手那把弓是给原版 RangedBowAttackGoal 判定用的、不可见；
    # 一旦加 BlockAndItemGeoLayer，原版物品会和骨骼树的弓同时出现两把。TNT 走同一条路
    # 才一致 —— 看得见的手持物一律建模进骨骼树，才能跟着手骨动、才能画引信亮芯。
    # 它只属于爆破兵：弓手/爆破兵的装备差异在渲染时按变种显隐（见 SoldierGeoModel）。
    # 挂在**左**手：throw_tnt 剪辑抡的是左臂（右臂一直在撑弓），TNT 跟左手才和动作对上。
    bone("tnt", (-5.75, 10.85, -0.6), "hand_l")
    # 4×4.5×4u：比手大一圈刚好「握住」；往 -x/-z 偏一点，避开大腿（x≥-3.8）与前臂（y≥12.4）
    cube("tnt", (-3.75, 8.6, -2.6, -7.75, 13.1, 1.4), "tnt")
    bone("tnt_fuse", (-5.75, 13.1, -2.5), "tnt")
    # 引信 1.6×1.6×1.8u：1u=1px 的尺度下 0.6u 的柱子连一个像素都占不满，实机等于看不见 ——
    # 尺寸要按「至少 2×2 像素」倒推。位置必须**在前臂之外**：前臂占 z ∈ [-1.9, 1.9] 且
    # y ∈ [12.4, 17.5]，引信只要落在那个盒子里就会被整根吞掉（第一版就是这样，画了看不见）。
    # 现在它从药包顶部前沿往 -z 支出，两个变种的姿势下都不会被遮。
    cube("tnt_fuse", (-6.55, 12.3, -4.3, -4.95, 13.9, -2.5), "fuse_lit")


# --------------------------------------------------------------------------- 展开与打包
def unwrap(w, h, d):
    """原版十字展开：返回 {面: (du,dv,dw,dh)}（局部像素坐标，1u=1px）。"""
    w, h, d = int(w), int(h), int(d)
    return {
        "u": (d, 0, w, d),
        "d": (d + w, 0, w, d),
        "e": (0, d, d, h),
        "n": (d, d, w, h),
        "w": (d + w, d, d, h),
        "s": (2 * d + w, d, w, h),
    }


MANIFEST = []


def pack():
    """货架打包：把每块的展开图（连同 1px 间隔）塞进 128×128。"""
    items = []
    for idx, c in enumerate(CUBES):
        x0, y0, z0, x1, y1, z1 = c["box"]
        w, h, d = round(x1 - x0), round(y1 - y0), round(z1 - z0)
        items.append((idx, w, h, d, 2 * d + 2 * w, d + h))
    # 高的先放：货架法按高度降序最省空间
    items.sort(key=lambda it: (-it[5], -it[4]))
    pen_x, pen_y, row_h = 0, 0, 0
    GAP = 1
    placed = {}
    for idx, w, h, d, fw, fh in items:
        if pen_x + fw + GAP > TEX_W:
            pen_x = 0
            pen_y += row_h + GAP
            row_h = 0
        assert pen_y + fh + GAP <= TEX_H, "图集塞不下：体块太多或贴图太小"
        placed[idx] = (pen_x, pen_y, w, h, d, fw, fh)
        pen_x += fw + GAP
        row_h = max(row_h, fh)
    pitems = []
    used = [[None] * TEX_H for _ in range(TEX_W)]
    for idx, (ox, oy, w, h, d, fw, fh) in sorted(placed.items()):
        c = CUBES[idx]
        loc = unwrap(w, h, d)
        faces = {}
        for f in FACE_ORDER:
            du, dv, dw, dh = loc[f]
            au, av = ox + du, oy + dv
            faces[f] = (au, av, dw, dh)
            # 只查**实际占用**的像素：同一块展开图里各面本来就贴边，相邻块之间由打包的
            # 1px 间隔保证不贴（间隔在 pack() 里就留好了，不需要在这里重复外扩检查）
            for yy in range(av, av + dh):
                for xx in range(au, au + dw):
                    if used[xx][yy] is not None and used[xx][yy] != idx:
                        raise AssertionError(
                            f"UV 重叠 @{(xx, yy)} {c['part']}.{f} 撞上 {CUBES[used[xx][yy]]['part']}")
            for yy in range(av, av + dh):
                for xx in range(au, au + dw):
                    used[xx][yy] = idx
        MANIFEST.append({"i": idx, "bone": c["bone"], "part": c["part"],
                         "box": c["box"], "faces": faces})


# --------------------------------------------------------------------------- 贴图
def _sh(*parts):
    """稳定哈希：同输入同输出，且不随进程变化（内建 hash() 带随机盐，不能用）。"""
    return int(hashlib.md5(repr(parts).encode("utf-8")).hexdigest()[:8], 16)


PALETTE = {
    # 军装：同色系靠明度分层（外套最深、裤子浅、马甲介于其间）
    "jacket": (0x4A, 0x52, 0x3C, "fabric"),
    "vest": (0x38, 0x40, 0x2F, "fabric"),
    "strap": (0x33, 0x3A, 0x2B, "fabric"),
    "pants": (0x4E, 0x55, 0x41, "fabric"),
    "gaiter": (0x3A, 0x3E, 0x33, "fabric"),
    "belt": (0x2A, 0x25, 0x20, "leather"),
    "buckle": (0x9A, 0x8B, 0x52, "metal"),
    "pouch": (0x3E, 0x44, 0x33, "leather"),
    "boot": (0x23, 0x21, 0x1E, "leather"),
    "helmet": (0x4F, 0x57, 0x46, "metal"),
    "helmet_rim": (0x34, 0x3A, 0x2C, "metal"),
    "helmet_plate": (0x5A, 0x62, 0x4E, "metal"),
    "quiver": (0x4A, 0x3A, 0x28, "leather"),
    "arrow": (0x6B, 0x5A, 0x3E, "wood"),
    "fletch": (0xC8, 0xC2, 0xB0, "cloth"),
    "skin": (0x8C, 0x82, 0x76, "rot"),
    "eye_glow": (0xFF, 0xC6, 0x3A, "glow"),
    "mouth": (0x3A, 0x2A, 0x28, "flat"),
    "gore": (0x8E, 0x14, 0x14, "blood"),
    "bow_wood": (0x4A, 0x35, 0x24, "leather"),
    "bow_string": (0xC6, 0xC0, 0xAE, "flat"),
    "band": (0xCF, 0xC9, 0xB6, "cloth"),
    # TNT：1u=1px 的尺度下 4×5 px 的一个面画不出 "TNT" 三个字，靠「暗红顶 + 白腰带 +
    # 引信孔」三个特征读出来；引信是亮芯（与发光眼同一套「亮像素」做法，不加发光层）。
    "tnt": (0x9E, 0x3A, 0x2E, "tnt"),
    "fuse_lit": (0xFF, 0xE2, 0x86, "fuse"),
}


def mix(c, f):
    return tuple(max(0, min(255, int(round(v * f)))) for v in c[:3])


def style_paint(buf, rect, part, face, variant, seed, flat=False):
    """按画法把一块面的像素画出来。buf 是 [y][x] = (r,g,b,a)。

    flat=True 表示这是贴片的"非朝外面"：必须整块填实色（留空就是透明洞口）。
    """
    au, av, dw, dh = rect
    r, g, b, style = PALETTE[part]
    base = (r, g, b)
    shade = FACE_SHADE[face]
    # 爆破兵偏土褐、弓手偏冷绿 —— 变种差异只走贴图
    if variant == "sapper":
        base = (min(255, base[0] + 12), min(255, base[1] + 4), max(0, base[2] - 8))
    elif variant == "archer":
        base = (max(0, base[0] - 4), min(255, base[1] + 3), max(0, base[2] + 6))
    for yy in range(av, av + dh):
        for xx in range(au, au + dw):
            n = (_sh(seed, xx, yy) % 1000) / 1000.0
            col = mix(base, shade * (0.97 + 0.06 * n))
            if style == "blood" and not flat:
                # 血渍不是色块：带噪声的椭圆掩膜，掩膜外**透明**——贴片底下就是军装，
                # 透出来的地方正好是"染上去"而不是"贴了张红纸"。
                cxx, cyy = (dw - 1) / 2.0, (dh - 1) / 2.0
                dx = (xx - au - cxx) / max(1.0, dw / 2.0)
                dy = (yy - av - cyy) / max(1.0, dh / 2.0)
                d = (dx * dx * 0.8 + dy * dy * 1.15) ** 0.5
                edge = 0.84 + 0.34 * (((_sh(seed, xx // 2, yy // 2) % 100) / 100.0) - 0.5)
                if d > edge:
                    buf[yy][xx] = (0, 0, 0, 0)
                    continue
            if style == "fabric":
                # 迷彩斑：低频块状，靠稳定哈希取阈值而不是逐像素噪声
                blob = (_sh(seed, xx // 3, yy // 3) % 1000) / 1000.0
                if blob > 0.72:
                    col = mix(base, shade * 0.82)
                elif blob < 0.16:
                    col = mix(base, shade * 1.12)
                if yy % 4 == 0:
                    col = mix(base, shade * 0.90)
            elif style == "rot":
                if n > 0.80:
                    col = (0x6E, 0x65, 0x5A)
                elif n < 0.14:
                    col = mix(base, 1.16)
            elif style == "glow":
                # 朝外那面才是发光的眼；贴片侧面压暗成眼窝
                col = (0xFF, 0xC6 + int(20 * n), 0x3A + int(30 * n)) if not flat else mix(base, 0.55)
            elif style == "blood":
                col = mix(base, 0.85 + 0.35 * n)
                if n > 0.78:
                    col = (0x5E, 0x0E, 0x0E)
            elif style == "metal":
                col = mix(base, shade * (0.95 + 0.10 * n))
                if n > 0.88:
                    col = mix(base, 0.66)      # 锈迹/磨损点
            elif style == "tnt":
                # 顶面：压暗 + 正中一个引信孔；底面：更暗（看不见但必须填实，留空就是洞）
                if face == "u":
                    col = mix(base, shade * 0.62 * (0.96 + 0.08 * n))
                    if xx == au + dw // 2 and yy == av + dh // 2:
                        col = (0x2A, 0x22, 0x18)
                elif face == "d":
                    col = mix(base, shade * 0.52 * (0.94 + 0.08 * n))
                else:
                    col = mix(base, shade * (0.97 + 0.06 * n))
                    # 白腰带：横贯中段的那一行 —— 远看就是「一包炸药」的形状特征
                    mid = av + dh // 2
                    if yy == mid:
                        col = (0xDC, 0xD6, 0xC4)
                    elif yy == mid - 1 and xx in (au, au + dw - 1):
                        col = (0xB4, 0xAE, 0x9E)
                    if n > 0.90:
                        col = mix(base, 0.70)
            elif style == "fuse":
                # 亮芯：白中透黄，噪声往橙偏 —— 一根点燃的引信就靠这几像素
                col = (0xFF, 0xE2 + int(14 * n), 0x86 + int(60 * n))
                if n > 0.84:
                    col = (0xFF, 0xFF, 0xE6)
                elif n < 0.12:
                    col = (0xE0, 0x8A, 0x2A)
                if flat:
                    col = mix((0xC8, 0x9A, 0x3A), 0.9)
                # 根那一行画焦：引信插进药包的地方本来就该是黑的
                elif yy == av + dh - 1:
                    col = (0x4A, 0x36, 0x22)
            elif style == "leather":
                col = mix(base, shade * (0.95 + 0.09 * n))
            buf[yy][xx] = (col[0], col[1], col[2], 255)
    # 边缘压暗 1px：平面色块靠它出"体块感"
    if dw > 2 and dh > 2 and not (style == "blood" and not flat):
        for yy in (av, av + dh - 1):
            for xx in range(au, au + dw):
                c = buf[yy][xx]
                buf[yy][xx] = (int(c[0] * 0.82), int(c[1] * 0.82), int(c[2] * 0.82), 255)
        for xx in (au, au + dw - 1):
            for yy in range(av, av + dh):
                c = buf[yy][xx]
                buf[yy][xx] = (int(c[0] * 0.88), int(c[1] * 0.88), int(c[2] * 0.88), 255)


GLYPH = {
    # 3px 宽画不出可辨认的 M（会糊成 H），所以钢印用 5×5 的 M5
    "W": ["10001", "11011", "10101", "10001", "10001"],
    "m": ["101", "111", "101"],
    "M": ["101", "111", "111", "101", "101"],
    "P": ["110", "101", "110", "100", "100"],
    "A": ["010", "101", "111", "101", "101"],
    "X": ["101", "101", "010", "101", "101"],
}


def draw_text(buf, rect, text, col=(0x23, 0x25, 0x1E)):
    """把 3×5 字形居中画在一块面上（只用于钢印/臂章这类需要认字的地方）。"""
    au, av, dw, dh = rect
    gw = sum(len(GLYPH[c][0]) + 1 for c in text) - 1
    gh = max(len(GLYPH[c]) for c in text)
    ox = au + max(0, (dw - gw) // 2)
    oy = av + max(0, (dh - gh) // 2)
    for i, ch in enumerate(text):
        rows = GLYPH[ch]
        for ry, row in enumerate(rows):
            for rx, bit in enumerate(row):
                if bit == "1":
                    xx = ox + sum(len(GLYPH[c][0]) + 1 for c in text[:i]) + rx
                    yy = oy + ry
                    if au <= xx < au + dw and av <= yy < av + dh:
                        buf[yy][xx] = (col[0], col[1], col[2], 255)


def render_texture(variant):
    buf = [[(0, 0, 0, 0)] * TEX_W for _ in range(TEX_H)]
    for m in MANIFEST:
        out = m.get("out")
        for f in FACE_ORDER:
            style_paint(buf, m["faces"][f], m["part"], f, variant,
                        _sh(variant, m["i"], f), flat=(out is not None and f != out))
    # 臂章字母：臂围放不下 MP，只画一个 M 作军警标记
    for m in MANIFEST:
        if m["part"] != "band":
            continue
        # 臂章：正面(n)与外侧(e)各一个 M —— 玩家从正面看僵尸时看到的是 n 面
        for f in ("n", "e"):
            rect = m["faces"][f]
            if rect[2] >= 3 and rect[3] >= 3:
                draw_text(buf, rect, "m", col=(0x2A, 0x2E, 0x24))
    return buf


def write_png(path, w, h, buf):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            raw.extend(buf[y][x])
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    return hashlib.sha256(png).hexdigest()


# --------------------------------------------------------------------------- 输出
def geo_json():
    order = {b["name"]: i for i, b in enumerate(BONES)}
    by_bone = {}
    for c in CUBES:
        by_bone.setdefault(c["bone"], []).append(c)
    bones_out = []
    for b in BONES:
        o = {"name": b["name"], "pivot": b["pivot"]}
        if b["parent"]:
            o["parent"] = b["parent"]
        cubes = []
        by_idx = {m["i"]: m for m in MANIFEST}
        for c in by_bone.get(b["name"], []):
            idx = CUBES.index(c)
            m = by_idx[idx]
            x0, y0, z0, x1, y1, z1 = c["box"]
            uvm = {}
            for f in FACE_ORDER:
                au, av, dw, dh = m["faces"][f]
                uvm[GEO_FACE[f]] = {"uv": [au, av], "uv_size": [dw, dh]}
            cubes.append({"origin": [x0, y0, z0],
                          "size": [round(x1 - x0, 3), round(y1 - y0, 3), round(z1 - z0, 3)],
                          "uv": uvm})
        if cubes:
            o["cubes"] = cubes
        bones_out.append(o)
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {
                "identifier": "geometry." + IDENT,
                "texture_width": TEX_W,
                "texture_height": TEX_H,
                "visible_bounds_width": 2.5,
                "visible_bounds_height": 3.0,
                "visible_bounds_offset": [0, 1.05, 0],
            },
            "bones": bones_out,
        }],
    }


def dump_json(paths, obj):
    data = (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    sha = hashlib.sha256(data).hexdigest()
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return sha


def main():
    build_model()
    pack()
    geo = geo_json()

    art_geo = ART / GEO_NAME
    src_geo = SRC / "geo" / GEO_NAME
    gsha = dump_json([art_geo, src_geo], geo)

    shas = {}
    for v in VARIANTS:
        buf = render_texture(v)
        p = ART / ("soldier_" + v + ".png")
        shas[v] = write_png(p, TEX_W, TEX_H, buf)
        write_png(SRC / TEX_DIR_REL / ("soldier_" + v + ".png"), TEX_W, TEX_H, buf)

    # 图集台账（谁都能拿它复核 UV 落在哪）
    (ART / "soldier_atlas.json").write_text(json.dumps({
        "texture": TEX_DIR_REL + "soldier_archer.png", "size": [TEX_W, TEX_H],
        "cubes": [{"bone": m["bone"], "part": m["part"], "box": m["box"],
                   "faces": {f: list(v) for f, v in m["faces"].items()}} for m in MANIFEST],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # ---------------- 自检 ----------------
    bad = []
    names = {b["name"] for b in BONES}
    for b in BONES:
        if b["parent"] and b["parent"] not in names:
            bad.append(f"骨骼 {b['name']} 的父骨 {b['parent']} 不存在")
    for c in CUBES:
        if c["bone"] not in names:
            bad.append(f"体块挂在未知骨骼 {c['bone']}")
        if c["part"] not in PALETTE:
            bad.append(f"未知画法 {c['part']}")
    ys = [(c["box"][1], c["box"][4]) for c in CUBES]
    y0, y1 = min(a for a, _ in ys), max(b for _, b in ys)
    # 左右对称性（除刻意的装备件之外，镜像块必须成对）
    boxes = {}
    for c in CUBES:
        boxes.setdefault(c["part"], []).append(c["box"])
    # 刻意的单侧装备：右侧臂章/右臂血、左背箭袋、胸口血片、朝前的嘴与发光眼
    EXPECT_ASYM = {"band", "quiver", "arrow", "fletch", "gore", "mouth", "eye_glow",
                   "jacket", "bow_wood", "bow_string"}  # jacket：右小臂整块换成 gore，不成镜像对
    asym = []
    for part, bs in boxes.items():
        xs = {round(b[0], 2) for b in bs} | {round(b[3], 2) for b in bs}
        if not all(round(-v, 2) in xs for v in xs) and part not in EXPECT_ASYM:
            asym.append(part)
    texels = sum((f[2] * f[3]) for m in MANIFEST for f in m["faces"].values())
    print(f"骨骼 {len(BONES)} / 体块 {len(CUBES)} / 图集已用 {texels} / {TEX_W*TEX_H} px "
          f"({texels * 100.0 / (TEX_W * TEX_H):.1f}%)")
    print(f"高度 {y0:.1f}u → {y1:.1f}u  （{y1/16:.2f} 方块，命中盒按 2.0 注册）")
    print(f"geo sha256={gsha[:16]}  archer png={shas['archer'][:16]}  sapper png={shas['sapper'][:16]}")
    if asym:
        print("左右未镜像的画法（应只出现刻意的单侧装备）:", asym)
    if bad:
        print("自检 FAIL:")
        for x in bad:
            print("   ", x)
        return 1
    print("自检: 全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
