"""猫耳娘 v4 生成器（真相源）：几何 + UV 装箱 + 128² 贴图，全部程序化。

v3 的三个毛病在这里解决：
  1) 比例：立绘逐带量出的宽度剖面 → 头 5.6 宽、猫耳落回头顶、手臂贴身、裙腰贴胯。
  2) 脸糊：v3 头部 UV 只有 7x8 像素（1px/u）。v4 按件分配密度（头 4px/u → 脸 ~22x26），
     128² 内装箱（v3 只用掉 24% 面积，白白空着）。
  3) 头是方盒：拆成 下颌/脸/头顶 三层，下颌前后内收做圆。

产物:
  art/cat_girl/cat_girl_spec.json            几何+UV（含每块密度 k）
  src/main/resources/.../textures/entity/cat_girl.png   128x128
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "art/cat_girl/cat_girl_spec.json"
TEX = ROOT / "src/main/resources/assets/apocalypse_zombies/textures/entity/cat_girl.png"
TEXSIZE = 128
FILL = 0.97          # 装箱目标占用率
DENSITY_BOOST = 1.40        # 装箱实测只用到 46% 面积，整体提密度再让装箱器回缩
FACE_UV = (0, 0, 44, 32)   # 脸层正面专用 UV 矩形（7.9px/u；盒式展开只给侧后）
HEAD_K = 4.0         # 头部目标密度 px/u（装箱后可能被整体缩放）

# ---------------------------------------------------------------- 调色板
C_SKIN, C_SKIN_D, C_SKIN_L = (250, 214, 205), (226, 188, 180), (255, 234, 227)
C_BLUSH = (250, 180, 180)
# 参考图头发是「灰粉亚麻」不是金黄；暗部偏梅灰
C_HAIR, C_HAIR_D, C_HAIR_L = (222, 200, 196), (188, 160, 158), (240, 226, 222)
C_HAIR_HL = (250, 244, 242)
# 眼：上睑线/瞳孔是暖梅灰（参考图里没有纯黑），虹膜梅紫、下缘淡紫
C_EYE_W, C_EYE_D, C_EYE_HL = (252, 250, 250), (104, 70, 78), (255, 255, 255)
C_EYE_I, C_EYE_I_L = (154, 102, 120), (206, 168, 186)
C_BROW, C_LASH = (188, 154, 148), (138, 100, 98)
C_MOUTH = (208, 132, 136)
C_RIBBON, C_RIBBON_D = (186, 196, 214), (160, 172, 194)
C_GOLD = (222, 179, 138)
C_FUR = (248, 239, 238)
C_NAVY, C_NAVY_D = (58, 68, 112), (40, 48, 84)
C_BLUE, C_BLUE_D = (158, 182, 214), (132, 156, 190)
C_WHITE, C_WHITE_D = (246, 245, 249), (222, 221, 230)
C_CREAM, C_CREAM_D = (240, 228, 208), (216, 202, 182)
C_CREAM_L = (252, 246, 232)
C_JACKET, C_JACKET_D = (246, 200, 214), (224, 172, 190)   # 外套要明显比肤色粉，否则像光着胳膊
C_WHITE_L = (252, 250, 252)
C_PINK, C_PINK_D = (240, 156, 174), (214, 126, 148)
C_SOLE = (74, 66, 76)
C_PLUSH, C_PLUSH_D = (250, 236, 226), (226, 206, 194)

# ---------------------------------------------------------------- 骨骼
BONES = [
    ("root", None, (0, 0, 0)),
    ("left_leg", "root", (-1.15, 13.0, 0)),
    ("left_shin", "left_leg", (-1.1, 6.8, 0)),
    ("left_foot", "left_shin", (-1.1, 1.6, 0)),
    ("right_leg", "root", (1.15, 13.0, 0)),
    ("right_shin", "right_leg", (1.1, 6.8, 0)),
    ("right_foot", "right_shin", (1.1, 1.6, 0)),
    ("body", "root", (0, 13.4, 0)),
    ("skirt", "body", (0, 14.6, 0)),
    ("plush", "skirt", (-2.2, 10.4, -2.6)),
    ("tail1", "body", (0, 14.6, 2.4)),
    ("tail2", "tail1", (0.5, 12.6, 4.0)),
    ("tail3", "tail2", (1.3, 10.4, 5.0)),
    ("tail4", "tail3", (2.1, 8.2, 5.2)),
    ("left_arm", "root", (-3.35, 22.4, 0)),
    ("left_forearm", "left_arm", (-2.95, 17.4, 0)),
    ("left_hand", "left_forearm", (-2.75, 12.6, 0)),
    ("right_arm", "root", (3.35, 22.4, 0)),
    ("right_forearm", "right_arm", (2.95, 17.4, 0)),
    ("right_hand", "right_forearm", (2.75, 12.6, 0)),
    ("item_righthand", "right_hand", (2.75, 10.4, 0)),
    ("head", "root", (0, 23.8, 0)),
    ("bangs", "head", (0, 28.6, -2.9)),
    ("side_lock_l", "head", (-2.95, 25.2, 0)),
    ("side_lock_r", "head", (2.95, 25.2, 0)),
    ("hair_back", "head", (0, 24.4, 2.6)),
    ("left_ear", "head", (-1.6, 30.2, -0.4)),
    ("right_ear", "head", (1.6, 30.2, -0.4)),
    ("left_ribbon", "head", (-2.2, 30.0, 0.9)),
    ("right_ribbon", "head", (2.2, 30.0, 0.9)),
    ("ahoge", "head", (0, 30.6, 0.3)),
]

cubes = []


def C(bone, name, x, y, z, w, h, d, mat, detail=None, rot=None, pivot=None):
    cubes.append({"bone": bone, "name": name, "from": [x, y, z], "size": [w, h, d],
                  "mat": mat, "detail": detail, "rot": rot, "pivot": pivot})


def mirror(name, bone_l, bone_r, x, y, z, w, h, d, mat, detail=None, rot=None, pivot=None):
    """左右镜像各来一块（x 取负号）"""
    C(bone_l, f"{name}_l", x, y, z, w, h, d, mat, detail, rot, pivot)
    C(bone_r, f"{name}_r", -x - w, y, z, w, h, d, mat, detail,
      None if rot is None else [rot[0], -rot[1], -rot[2]],
      None if pivot is None else [-pivot[0], pivot[1], pivot[2]])


def X(s, outer, w):
    """按「外缘绝对距离」对称定位（s<0 左 / s>0 右），避免左右写歪"""
    return -outer if s < 0 else outer - w


# ================================================================ 几何
# ---- 腿（x 中心 ±1.1；鞋 2.2 宽 3.2 长 · 小腿 2.0 · 大腿 2.4）
for side, bl, bs, bf in ((-1, "left_leg", "left_shin", "left_foot"),
                         (1, "right_leg", "right_shin", "right_foot")):
    c = side * 1.1
    C(bl, f"thigh_{'l' if side < 0 else 'r'}", c - 1.2, 9.4, -1.2, 2.4, 3.6, 2.4, "skin", "thigh")
    C(bl, f"hip_{'l' if side < 0 else 'r'}", c - 1.25, 12.4, -1.3, 2.5, 1.6, 2.6, "skin", "hip")
    C(bs, f"socktop_{'l' if side < 0 else 'r'}", c - 0.8, 9.0, -0.8, 1.6, 0.8, 1.6, "white", "sock_top")
    C(bs, f"sock_{'l' if side < 0 else 'r'}", c - 0.8, 1.4, -0.8, 1.6, 7.6, 1.6, "white", "sock")
    C(bf, f"shoe_{'l' if side < 0 else 'r'}", c - 1.05, 0.85, -1.85, 2.1, 1.5, 3.3, "blue", "shoe")
    C(bf, f"shoe_toe_{'l' if side < 0 else 'r'}", c - 1.05, 0.85, -2.4, 2.1, 1.1, 0.6, "white", "shoe")
    C(bf, f"sole_{'l' if side < 0 else 'r'}", c - 1.1, 0.0, -2.05, 2.2, 0.85, 3.7, "white", "sole")

# ---- 躯干
C("body", "waist", -2.6, 14.4, -1.5, 5.2, 5.1, 3.0, "skin", None)          # 露腰（立绘是露腹短上衣）
C("body", "top", -3.0, 19.5, -1.8, 6.0, 3.1, 3.6, "white", "shirt")         # 白抹胸
C("body", "top_hem", -3.05, 19.25, -1.85, 6.1, 0.45, 3.7, "white_d", "shirt")
C("body", "bust_l", -2.55, 19.8, -2.2, 2.2, 2.2, 1.0, "white", "bust")
C("body", "bust_r", 0.35, 19.8, -2.2, 2.2, 2.2, 1.0, "white", "bust")
C("body", "jacket_l", -3.45, 19.6, -1.95, 0.85, 3.5, 3.9, "jacket", "cardigan")
C("body", "jacket_r", 2.6, 19.6, -1.95, 0.85, 3.5, 3.9, "jacket", "cardigan")
C("body", "jacket_back", -3.45, 19.6, 1.45, 6.9, 3.5, 0.5, "jacket", "cardigan")
C("body", "lapel_l", -2.7, 20.0, -2.05, 0.55, 3.1, 0.5, "jacket_d", "cardigan")
C("body", "lapel_r", 2.15, 20.0, -2.05, 0.55, 3.1, 0.5, "jacket_d", "cardigan")
C("body", "jacket_collar", -2.5, 22.75, -1.7, 5.0, 0.75, 3.4, "jacket_d", None)
C("body", "shoulder_l", -3.35, 22.9, -1.5, 1.5, 1.1, 3.1, "jacket", "cardigan")
C("body", "shoulder_r", 1.85, 22.9, -1.5, 1.5, 1.1, 3.1, "jacket", "cardigan")
C("body", "neck", -0.9, 22.6, -0.85, 1.8, 1.5, 1.7, "skin", "neck")
C("body", "choker", -1.35, 22.85, -1.35, 2.7, 0.55, 2.7, "ribbon", None)
C("body", "bow_knot", -0.35, 22.15, -2.1, 0.7, 0.7, 0.4, "ribbon", None)
C("body", "bow_l", -1.5, 22.0, -2.05, 1.15, 0.85, 0.35, "ribbon", None,
  rot=[0, 0, 14], pivot=[-0.35, 22.5, -1.9])
C("body", "bow_r", 0.35, 22.0, -2.05, 1.15, 0.85, 0.35, "ribbon", None,
  rot=[0, 0, -14], pivot=[0.35, 22.5, -1.9])
C("body", "bell", -0.42, 22.05, -1.75, 0.84, 0.85, 0.5, "gold", None)

# ---- 裙子（腰围贴胯 r≈3.2/2.1；下摆 r≈4.4/3.0；12 片褶）
def skirt_ring():
    """三段同心环 → 真锥形（半径由多环给出，不用斜块，避免旋转顺序踩坑）
    环半径取自立绘剖面：下摆 r=4.35(y6.9) → 腰 r=2.90(y14.9)"""
    n = 8
    for ri, (y_top, y_bot, r) in enumerate(((14.7, 12.0, 2.95),
                                            (12.3, 10.6, 3.95))):
        for i in range(n):
            a = (i + 0.5) * 2 * math.pi / n
            ca, sa = math.cos(a), math.sin(a)
            cx, cz = ca * r * 0.95, sa * r * 0.70
            if abs(ca) > 0.8:          # 模型左右两侧：切向沿 z
                w, d = 0.85, 3.15
            elif abs(sa) > 0.8:        # 模型正前/正后：切向沿 x
                w, d = 3.15, 0.95
            else:                      # 斜角：近似方
                w, d = 2.25, 2.25
            C("skirt", f"skirt{ri}_{i}", cx - w / 2, y_bot, cz - d / 2, w, y_top - y_bot, d,
              "blue", "pleat" if (i + ri) % 2 == 0 else "pleat_d")
    C("skirt", "band", -3.0, 13.9, -2.0, 6.0, 1.0, 4.0, "navy", "band")
    for i in range(n):
        a = (i + 0.5) * 2 * math.pi / n
        ca, sa = math.cos(a), math.sin(a)
        cx, cz = ca * 4.15 * 0.95, sa * 4.15 * 0.70
        if abs(ca) > 0.8:
            w, d = 0.95, 3.35
        elif abs(sa) > 0.8:
            w, d = 3.35, 1.05
        else:
            w, d = 2.45, 2.45
        C("skirt", f"frill_{i}", cx - w / 2, 10.6, cz - d / 2, w, 0.55, d, "white", "frill")


skirt_ring()


# ---- 挂件：垂在左大腿前的猫玩偶
C("plush", "plush_body", -2.2, 8.6, -3.1, 1.7, 1.9, 1.1, "plush", "plush")
C("plush", "plush_head", -2.05, 10.5, -3.05, 1.4, 1.3, 1.0, "plush", "plush")
C("plush", "plush_ear_l", -2.1, 11.7, -3.0, 0.5, 0.7, 0.4, "plush", "plush")
C("plush", "plush_ear_r", -1.4, 11.7, -3.0, 0.5, 0.7, 0.4, "plush", "plush")
C("plush", "plush_tail", -2.3, 8.9, -2.35, 0.5, 0.5, 0.9, "plush_d", "plush")

# ---- 尾巴（从腰后向右下弯，4 节）
C("tail1", "tail_a", -0.85, 13.6, 2.1, 1.7, 2.3, 1.8, "hair", "tail",
  rot=[-30, 0, 0], pivot=[0, 14.6, 2.4])
C("tail2", "tail_b", -0.35, 11.9, 3.3, 1.6, 2.3, 1.7, "hair", "tail",
  rot=[-12, 0, 0], pivot=[0.4, 12.5, 3.4])
C("tail3", "tail_c", 0.25, 10.0, 4.0, 1.55, 2.3, 1.65, "hair", "tail",
  rot=[4, 0, 0], pivot=[1.0, 10.6, 4.3])
C("tail3", "tail_c2", 0.75, 8.2, 4.35, 1.5, 2.2, 1.6, "hair", "tail",
  rot=[18, 0, 0], pivot=[1.6, 8.8, 4.7])
C("tail4", "tail_d", 1.25, 6.5, 4.35, 1.4, 2.1, 1.5, "hair", "tail",
  rot=[32, 0, 0], pivot=[2.2, 7.1, 4.7])
C("tail4", "tail_tip", 1.8, 4.9, 4.0, 1.3, 1.9, 1.4, "hair_l", "tail_tip",
  rot=[48, 0, 0], pivot=[2.8, 5.5, 4.4])
C("tail2", "tail_fluff_l", -1.75, 11.3, 3.2, 0.9, 1.8, 1.3, "hair_l", "tail",
  rot=[-14, 0, 14], pivot=[0.4, 12.5, 3.4])
C("tail3", "tail_fluff_r", 1.5, 8.9, 4.3, 0.9, 1.7, 1.3, "hair_l", "tail",
  rot=[16, 0, -12], pivot=[1.6, 8.8, 4.7])

# ---- 手臂（上臂贴身 → 泡泡袖外缘 ±4.3 → 前臂/手收到大腿外侧 ±3.0）
for s, ba, bf2, bh in ((-1, "left_arm", "left_forearm", "left_hand"),
                       (1, "right_arm", "right_forearm", "right_hand")):
    t = "l" if s < 0 else "r"
    C(ba, f"upper_arm_{t}", s * 3.4 - 0.8, 17.8, -0.8, 1.6, 4.8, 1.6, "skin", "arm")
    C(ba, f"sleeve_{t}", X(s, 5.2, 2.6), 16.0, -1.45, 2.6, 3.0, 3.0,
      "jacket", "sleeve")
    C(ba, f"sleeve_top_{t}", X(s, 4.05, 2.1), 18.4, -1.3, 2.1, 4.6, 2.7,
      "jacket", "sleeve")
    C(bf2, f"forearm_{t}", X(s, 2.9, 1.4), 13.4, -0.7, 1.4, 3.9, 1.4, "skin", "arm")
    C(bf2, f"cuff_{t}", s * 2.95 - 0.85, 16.6, -0.95, 1.7, 1.3, 1.9, "jacket_d", "cuff")
    C(bh, f"hand_{t}", X(s, 2.8, 1.5), 12.0, -0.75, 1.5, 1.7, 1.5, "skin", "hand")

C("item_righthand", "item_slot", 1.75, 10.6, -0.6, 1.5, 1.5, 1.2, "skin", None)

# ---- 头（三层：下颌内收 / 脸层（带脸贴图）/ 头顶发）
C("head", "jaw", -2.5, 23.3, -2.5, 5.0, 1.3, 5.0, "skin", "jaw")
C("head", "face", -2.8, 24.4, -2.8, 5.6, 4.0, 5.6, "skin", "face")
cubes[-1]["uvn"] = list(FACE_UV)
C("head", "crown", -2.8, 28.4, -2.8, 5.6, 1.8, 5.6, "hair", "crown")
C("head", "cheek_l", -3.0, 25.0, -2.6, 0.4, 2.4, 4.6, "skin_l", "cheek")
C("head", "cheek_r", 2.6, 25.0, -2.6, 0.4, 2.4, 4.6, "skin_l", "cheek")

# ---- 头发：刘海 / 鬓发 / 后发
# 中分刘海：左右各两片，斜向垂下压到眼睛上方（眼睛在 y26.2~26.9）
for i, (x, w, y, h, r) in enumerate(((-2.95, 1.65, 27.05, 3.3, -7),
                                     (-1.40, 1.65, 27.05, 3.5, -2),
                                     (0.40, 1.65, 27.05, 3.4, 3),
                                     (1.90, 1.65, 27.05, 3.2, 8))):
    C("bangs", f"bang_{i}", x, y, -3.25, w, h, 0.6, "hair", "bang",
      rot=[r, 0, 0], pivot=[x + w / 2, y + h, -3.15])
C("bangs", "bang_side_l", -3.15, 25.6, -2.95, 0.5, 4.6, 2.7, "hair", "bang")
C("bangs", "bang_side_r", 2.65, 25.6, -2.95, 0.5, 4.6, 2.7, "hair", "bang")
# 鬓发：及腰长发（胸前两段，垂到腰 y11.8）
C("side_lock_l", "lock_l", -3.05, 17.8, -2.3, 0.75, 6.6, 2.5, "hair", "lock",
  rot=[0, 0, 2], pivot=[-2.8, 29.4, -1.0])
C("side_lock_l", "lock_l2", -3.15, 11.8, -2.45, 0.7, 6.2, 2.2, "hair_d", "lock",
  rot=[0, 0, 3], pivot=[-2.9, 29.4, -1.0])
C("side_lock_r", "lock_r", 2.3, 17.8, -2.3, 0.75, 6.6, 2.5, "hair", "lock",
  rot=[0, 0, -2], pivot=[2.7, 29.4, -1.0])
C("side_lock_r", "lock_r2", 2.45, 11.8, -2.45, 0.7, 6.2, 2.2, "hair_d", "lock",
  rot=[0, 0, -3], pivot=[2.9, 29.4, -1.0])
# 后发：主体到腰、两侧外翻发片、下层
C("hair_back", "back_hair", -3.0, 17.2, 2.15, 6.0, 11.8, 1.6, "hair", "back")
C("hair_back", "back_hair2", -2.7, 11.4, 2.45, 5.4, 6.2, 1.1, "hair_d", "back")
C("hair_back", "back_side_l", -3.45, 15.2, 2.0, 0.8, 9.2, 1.8, "hair_d", "back")
C("hair_back", "back_side_r", 2.65, 15.2, 2.0, 0.8, 9.2, 1.8, "hair_d", "back")
C("hair_back", "top_hair", -2.95, 29.9, -2.95, 5.9, 0.8, 5.9, "hair", "top")
# 波浪发梢（反向倾斜 → 侧面轮廓不再是直筒）
C("side_lock_l", "wave_l", -3.3, 10.0, -2.55, 0.8, 1.9, 2.3, "hair_l", "lock",
  rot=[0, 0, -9], pivot=[-3.1, 11.9, -1.2])
C("side_lock_l", "wave_l2", -3.45, 8.4, -2.45, 0.7, 1.9, 2.1, "hair_d", "lock",
  rot=[0, 0, 8], pivot=[-3.25, 10.2, -1.2])
C("side_lock_r", "wave_r", 2.5, 10.0, -2.55, 0.8, 1.9, 2.3, "hair_l", "lock",
  rot=[0, 0, 9], pivot=[2.9, 11.9, -1.2])
C("side_lock_r", "wave_r2", 2.75, 8.4, -2.45, 0.7, 1.9, 2.1, "hair_d", "lock",
  rot=[0, 0, -8], pivot=[3.05, 10.2, -1.2])

# 猫耳（每只 3 片：后片/前片/内耳，外缘 ≤ ±2.5）
for bone, sgn in (("left_ear", -1), ("right_ear", 1)):
    t = "l" if sgn < 0 else "r"
    C(bone, f"ear_back_{t}", X(sgn, 2.7, 1.9), 30.1, -1.0, 1.9, 2.1, 0.6,
      "hair", "ear", rot=[0, 0, sgn * -16], pivot=[sgn * 1.6, 30.2, -0.7])
    C(bone, f"ear_front_{t}", X(sgn, 2.45, 1.7), 30.3, -1.35, 1.7, 1.85, 0.45,
      "hair", "ear", rot=[0, 0, sgn * -16], pivot=[sgn * 1.6, 30.2, -0.7])
    C(bone, f"ear_fur_{t}", X(sgn, 2.15, 1.25), 30.5, -1.5, 1.25, 1.45, 0.25,
      "fur", "ear_in", rot=[0, 0, sgn * -16], pivot=[sgn * 1.6, 30.2, -0.7])
    # 耳根白毛簇（参考图耳朵根部有绒毛）
    C(bone, f"ear_fluff_{t}", X(sgn, 2.9, 0.8), 28.6, -1.85, 0.8, 0.9, 1.2,
      "fur", None, rot=[0, 0, sgn * -12], pivot=[sgn * 1.6, 30.2, -0.7])

for bone, sgn in (("left_ribbon", -1), ("right_ribbon", 1)):
    t = "l" if sgn < 0 else "r"
    bx = sgn * 2.35 if sgn < 0 else sgn * 2.35 - 1.0
    C(bone, f"ribbon_{t}", bx, 29.6, 0.55, 1.0, 1.0, 0.9, "ribbon", "ribbon",
      rot=[0, 0, sgn * -14], pivot=[sgn * 2.2, 30.0, 0.9])
    C(bone, f"ribbon_knot_{t}", sgn * 2.2 - 0.3, 29.9, 0.7, 0.6, 0.6, 0.6, "ribbon_d", "ribbon")
    C(bone, f"ribbon_tail_{t}", X(sgn, 2.3, 0.5), 28.3, 0.9, 0.5, 1.4, 0.5,
      "ribbon", "ribbon", rot=[0, 0, sgn * -10], pivot=[sgn * 2.2, 29.8, 0.9])

# 立绘没有呆毛，改成右鬓的白猫发夹
C("ahoge", "clip_body", 1.45, 28.15, -3.05, 1.05, 0.9, 0.45, "white", None)
C("ahoge", "clip_ear_l", 1.52, 29.05, -3.05, 0.35, 0.4, 0.4, "white", None)
C("ahoge", "clip_ear_r", 2.08, 29.05, -3.05, 0.35, 0.4, 0.4, "white", None)
C("ahoge", "ahoge_dummy", -0.3, 31.1, 0.3, 0.6, 0.9, 0.5, "hair_l", "ahoge",
  rot=[-32, 0, 0], pivot=[0, 31.1, 0.6])

# ================================================================ UV 装箱
def box_uv(u, v, w, h, d):
    return {"north": (u + d, v + d, u + d + w, v + d + h),
            "east": (u, v + d, u + d, v + d + h),
            "south": (u + 2 * d + w, v + d, u + 2 * d + 2 * w, v + d + h),
            "west": (u + d + w, v + d, u + d + w + d, v + d + h),
            "up": (u + d, v, u + d + w, v + d),
            "down": (u + d + w, v, u + d + w + w, v + d)}


def rect_of(c, k):
    w, h, d = [int(round(v * k)) for v in c["size"]]
    return (2 * (w + d), h + d)   # 盒式展开：宽 2*(w+d)，高 h+d


def target_k(c):
    if c["name"] in ("face",) or c["bone"] in ("bangs", "side_lock_l", "side_lock_r", "ahoge"):
        return HEAD_K
    if c["bone"] in ("head", "hair_back", "left_ear", "right_ear", "left_ribbon", "right_ribbon"):
        return 3.0
    if c["bone"] == "skirt":
        return 2.0
    return 2.0


def pack():
    """按目标密度装箱进 TEXSIZE²，超了就整体等比缩密度（确定性）"""
    for scale in [1.0 - i * 0.02 for i in range(40)]:
        items = []
        for i, c in enumerate(cubes):
            k = target_k(c) * scale
            w, h = rect_of(c, k)
            items.append({"i": i, "k": k, "w": w + 1, "h": h + 1})
        area = sum(it["w"] * it["h"] for it in items)
        if area > FILL * TEXSIZE * TEXSIZE:
            continue
        items.sort(key=lambda it: (-it["h"], -it["w"]))
        # best-fit 货架装箱：逐件扫已有货架，选「放进去后剩余宽度最小」的那一层，
        # 放不下再开新层。比 next-fit 逐行少浪费行尾碎空 → 同一张图能选更高的密度。
        y0 = FACE_UV[3] + 1                      # 顶部给脸部专用矩形留条带
        # 脸矩形右侧那条带（x≥44, y 0..32）照样能装箱，别浪费 17% 版面
        shelves = [[0, FACE_UV[3], FACE_UV[2]]]  # [y, rowh, x游标]
        ok = True
        for it in items:
            best = None
            for sh in shelves:
                if it["h"] <= sh[1] and sh[2] + it["w"] <= TEXSIZE:
                    if best is None or (TEXSIZE - (sh[2] + it["w"])) < (TEXSIZE - (best[2] + it["w"])):
                        best = sh
            if best is None:
                yy = y0 if not shelves else max(sh[0] + sh[1] for sh in shelves)
                if yy + it["h"] > TEXSIZE:
                    ok = False
                    break
                best = [yy, it["h"], 0]
                shelves.append(best)
            it["x"], it["y"] = best[2], best[0]
            best[2] += it["w"]
        if not ok:
            continue
        for it in items:
            if it["i"] < 0:
                continue
            c = cubes[it["i"]]
            c["k"] = round(it["k"], 4)
            c["uv"] = [it["x"], it["y"]]
            c["_wh"] = [it["w"], it["h"]]
        used = sum(it["w"] * it["h"] for it in items if it["i"] >= 0)
        return scale, used / (TEXSIZE * TEXSIZE)
    raise SystemExit("装箱失败")


scale, occupancy = pack()

# ================================================================ 贴图
W = H = TEXSIZE
px = [[(0, 0, 0, 0)] * W for _ in range(H)]


def put(x, y, c, a=255):
    if 0 <= x < W and 0 <= y < H:
        px[int(y)][int(x)] = (c[0], c[1], c[2], a)


def rect(x, y, w, h, c, a=255):
    for j in range(int(h)):
        for i in range(int(w)):
            put(x + i, y + j, c, a)


def blend(x, y, c, al):
    if 0 <= x < W and 0 <= y < H:
        o = px[int(y)][int(x)]
        put(x, y, tuple(round(o[i] * (1 - al) + c[i] * al) for i in range(3)), 255)


def ell(cx, cy, rx, ry, c, a=255):
    for j in range(-int(ry) - 1, int(ry) + 2):
        for i in range(-int(rx) - 1, int(rx) + 2):
            if (i / max(rx, .1)) ** 2 + (j / max(ry, .1)) ** 2 <= 1.0:
                put(cx + i, cy + j, c, a)


def shade_of(c, f):
    return tuple(min(255, round(v * f)) for v in c)


MAT = {"skin": C_SKIN, "skin_l": C_SKIN_L, "skin_d": C_SKIN_D, "hair": C_HAIR, "hair_l": C_HAIR_L,
       "hair_d": C_HAIR_D, "white": C_WHITE, "blue": C_BLUE, "navy": C_NAVY, "cream": C_CREAM,
       "pink": C_PINK, "pink_d": C_PINK_D, "sole": C_SOLE, "plush": C_PLUSH, "plush_d": C_PLUSH_D,
       "ribbon": C_RIBBON, "ribbon_d": C_RIBBON_D, "fur": C_FUR, "gold": C_GOLD,
       "cream_l": C_CREAM_L, "jacket": C_JACKET, "jacket_d": C_JACKET_D, "white_d": C_WHITE_D}
FACE_SHADE = {"north": 1.0, "east": 0.95, "south": 0.9, "west": 0.95, "up": 1.06, "down": 0.82}


def paint_face(r):
    """脸层正面：照参考图逐像素画。
    结构（由下往上）：皮肤渐变+额头高光+颊高光 → 眉(内粗外细+眉上散毛+眉下影) →
    眼影 → 卧蚕+高光 → 眼白+上睑投影 → 虹膜暗环/梅紫/淡紫下段/瞳孔 → 双高光+目头亮 →
    上睑线 → 外眼角睫毛+上挑尖 → 下睑线 → 鼻影+鼻头高光 → 唇线(嘴角上扬)+下唇亮+唇下影 →
    三层渐变腮红 → 下颌收边。"""
    x, y, w, h = r
    fw, fh = w, h

    def P(u, v):
        return x + u * fw, y + v * fh

    def R(u, v, uw, vh, c, al=255):
        rect(x + u * fw, y + v * fh, max(1, uw * fw), max(1, vh * fh), c, al)

    # ── 皮肤：先铺底色再叠渐变（vgrad 是半透明叠加，没有底色会被洗白）
    rect(x, y, w, h, C_SKIN)
    vgrad(x, y, w, h, C_SKIN_L, C_SKIN_D, 165)
    R(0.0, 0.0, 1.0, 0.09, C_SKIN_L, 235)
    R(0.0, 0.88, 1.0, 0.12, C_SKIN_D, 215)
    for i in range(max(1, int(fw * 0.045))):
        rect(x + i, y + fh * 0.14, 1, fh * 0.72, C_SKIN_D, 115)
        rect(x + fw - 1 - i, y + fh * 0.14, 1, fh * 0.72, C_SKIN_D, 115)
    R(0.30, 0.045, 0.40, 0.065, (255, 240, 234), 150)
    _EC = 2 + max(6, int(round(fw * 0.335))) / 2.0      # 左眼中心（列）
    for cx in (_EC, w - _EC):                           # 镜像：两眼中心正下方
        ell(x + cx, y + 0.60 * fh, fw * 0.10, fh * 0.06, (255, 236, 230), 115)

    # ── 眉：内粗外细 + 眉上散毛 + 眉下阴影
    BWh = max(3, int(round(fw * 0.26)))
    for bx, out in ((x + 3, 1), (x + w - 3 - BWh, -1)):
        n = BWh
        for i in range(n):
            t = i / (n - 1)
            inner = t if out > 0 else 1.0 - t
            yy = y + (0.196 - 0.024 * (1 - (2 * t - 1) ** 2)) * fh
            th = max(1.0, fh * (0.030 + 0.018 * inner))
            rect(bx + i, yy, 1, th, C_BROW, 205)
            if i in (1, 2) if out > 0 else i in (n - 3, n - 2):      # 只在眉头侧留两撮散毛
                rect(bx + i, yy - max(1.0, fh * 0.030), 1, 1, C_BROW, 155)
        R((bx - x) / fw, 0.242, 0.26, 0.016, C_SKIN_D, 75)

    # ── 眼（外眼角 = 远离鼻梁那一侧，睫毛必在外侧）
    # 左右必须严格镜像：整数列 + 镜像公式 a' = w - a - width（浮点会让两只眼各差 1px）
    EW = max(6, int(round(fw * 0.335)))
    EH = max(4, int(round(fh * 0.215)))
    EY = y + int(round(0.370 * fh))
    for ex0, outer_left in ((x + 2, True), (x + w - 2 - EW, False)):
        ew, eh = EW, EH
        ey0 = EY
        # 眼影/目头亮/下睑线 必须按「外眼角在哪侧」翻，否则两只眼同向偏移 = 不对称
        sh = 0.36 if outer_left else 0.64
        inn = 0.85 if outer_left else 0.03
        ell(ex0 + ew * sh, ey0 - eh * 0.12, ew * 0.44, eh * 0.24, (226, 196, 206), 60)    # 眼影（外眼角上方）
        rect(ex0 + ew * 0.14, ey0 + eh, ew * 0.72, max(1.0, fh * 0.045), C_BLUSH, 95)     # 卧蚕（居中）
        rect(ex0 + ew * 0.25, ey0 + eh * 1.12, ew * 0.5, max(1.0, fh * 0.022), (255, 236, 232), 120)
        rect(ex0, ey0, ew, eh, C_EYE_W)
        rect(ex0, ey0, ew, max(1.0, eh * 0.30), (222, 214, 224), 125)                     # 上睑投影
        ell(ex0 + ew * 0.5, ey0 + eh * 0.54, ew * 0.44, eh * 0.50,
            (192, 152, 172), 150)                                                         # 外圈：淡梅紫细环（参考图不是黑框）
        ell(ex0 + ew * 0.5, ey0 + eh * 0.50, ew * 0.40, eh * 0.48, C_EYE_I_L)             # 主体淡紫
        ell(ex0 + ew * 0.5, ey0 + eh * 0.62, ew * 0.30, eh * 0.34, C_EYE_I, 175)          # 中段梅紫（半透）
        ell(ex0 + ew * 0.5, ey0 + eh * 0.52, ew * 0.16, ey0 * 0 + eh * 0.26, C_EYE_D)     # 瞳孔（小）
        ell(ex0 + ew * 0.35, ey0 + eh * 0.34, ew * 0.16, eh * 0.24, C_EYE_HL, 250)        # 主高光
        ell(ex0 + ew * 0.68, ey0 + eh * 0.72, ew * 0.10, eh * 0.14, C_EYE_HL, 180)        # 次高光
        rect(ex0 + ew * inn, ey0 + eh * 0.30, max(1.0, ew * 0.13), max(1.0, eh * 0.5),
             (255, 246, 246), 140)                                                        # 目头亮（内眼角侧）
        rect(ex0, ey0 - max(1.0, fh * 0.038), ew, max(1.0, fh * 0.042), C_LASH)            # 上睑线
        li = int(ex0 - 1) if outer_left else int(ex0 + ew - 1)                            # 外眼角
        rect(li, ey0 - max(1.0, fh * 0.10), 2, max(1.0, fh * 0.09), C_LASH)               # 睫毛
        rect(li + (0 if outer_left else 1), ey0 - max(1.0, fh * 0.145), 1,
             max(1.0, fh * 0.05), C_LASH, 200)                                            # 上挑尖
        rect(ex0 + (ew * 0.30 if outer_left else 0), ey0 + eh - max(1.0, fh * 0.012),
             ew * 0.70, max(1.0, fh * 0.018), (196, 148, 156), 130)                       # 下睑线（外 70%）

    # ── 鼻：鼻影 + 鼻头高光
    ny = y + int(round(0.685 * fh))
    nx = x + (w - 2) // 2                                                                # 2px 宽 → 中心正好 22.0
    rect(nx, ny, 2, max(1.0, fh * 0.07), C_SKIN_D, 100)                                  # 鼻影（淡）
    rect(nx, ny + fh * 0.055, 2, max(1.0, fh * 0.03), (255, 240, 236), 150)               # 鼻头高光

    # ── 嘴：唇线（嘴角高、中间低）+ 下唇亮 + 唇下影
    n = max(4, int(round(fw * 0.14))) & ~1         # 偶数宽 → 中心才能正好落在 22.0
    xm, ym = x + (w - n) // 2, y + int(round(0.845 * fh))   # 严格居中：中心列 = 22
    for i in range(n):
        t = i / (n - 1)
        yy = ym - ((2 * t - 1) ** 2) * max(1.0, fh * 0.032)
        rect(xm + i, yy, 1, 1, C_MOUTH, 170)
    rect(xm + n * 0.25, ym + max(1.0, fh * 0.052), n * 0.5, max(1.0, fh * 0.024),
         (242, 196, 194), 120)
    rect(xm + n * 0.2, ym + max(1.0, fh * 0.082), n * 0.6, max(1.0, fh * 0.020),
         C_SKIN_D, 70)

    # ── 腮红：三层叠加出「外淡内浓」的渐变（参考图很淡，不用色块）
    for cx0 in (_EC + 3, w - _EC - 3):
        cx, cy = cx0 / fw, 0.735
        ell(x + cx * fw, y + cy * fh, fw * 0.105, fh * 0.065, C_BLUSH, 42)
        ell(x + cx * fw, y + cy * fh, fw * 0.075, fh * 0.046, C_BLUSH, 68)
        ell(x + cx * fw, y + cy * fh, fw * 0.045, fh * 0.028, C_BLUSH, 92)


def _mix(c1, c2, t):
    return (int(c1[0] + (c2[0] - c1[0]) * t), int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


def vgrad(x, y, w, h, top, bot, a=255):
    """上亮下暗的竖直渐变：布料/皮肤的体积感都靠它。"""
    n = max(1, int(round(h)))
    for i in range(n):
        rect(x, y + i, w, 1, _mix(top, bot, i / max(1, n - 1)), a)


def folds(x, y, w, h, col, n=2, a=170):
    """布料竖褶。"""
    for i in range(1, n + 1):
        rect(x + w * i / (n + 1) - max(1, w * 0.035), y, max(1, w * 0.07), h, col, a)


def strands(x, y, w, h, a=205):
    """发丝：亮/暗交替细竖带 + 顶部高光 + 中部暗带。"""
    n = max(2, int(w / 2.0))
    for i in range(n):
        col = C_HAIR_L if i % 2 == 0 else C_HAIR_D
        rect(x + i * (w / n), y, max(1, w / n * 0.8), h, col, a)
    rect(x, y, w, max(1, h * 0.10), C_HAIR_HL, 225)
    rect(x, y + h * 0.62, w, max(1, h * 0.10), C_HAIR_D, 190)


def stitch(x, y, w, a=205):
    """虚线缝线。"""
    for i in range(0, int(w), 2):
        rect(x + i, y, 1, 1, C_JACKET_D, a)


def hem(x, y, w, h, col, a=205):
    """下摆/收边暗带。"""
    rect(x, y + h - max(1, h * 0.12), w, max(1, h * 0.12), col, a)


def paint_cube(c):
    u, v = c["uv"]
    w, h, d = [int(round(x * c["k"])) for x in c["size"]]
    f = box_uv(u, v, w, h, d)
    # box_uv 返回角点对 [x0,y0,x1,y1]，而下面所有画法都按 (x,y,w,h) 解包 —— 这里统一转换，
    # 否则每块会按「宽=x1、高=y1」画成巨矩形互相覆盖（整张贴图会变成最后画的头发色）。
    f = {k: (a, b, cc - a, dd - b) for k, (a, b, cc, dd) in f.items()}
    base = MAT.get(c["mat"], C_SKIN)
    det = c.get("detail") or ""
    for name, (x, y, ww, hh) in f.items():
        sh = FACE_SHADE[name]
        rect(x, y, ww, hh, shade_of(base, sh))
    if det == "face":
        paint_face(tuple(c["uvn"]))
    elif det in ("hair", "bang", "lock", "back", "top", "ahoge"):
        for name in ("north", "south", "east", "west"):
            if name in f:
                strands(*f[name])
        for name in ("up", "down"):
            if name in f:
                x, y, ww, hh = f[name]
                rect(x, y, ww, max(1, hh * 0.4), C_HAIR_HL, 200)
                hem(x, y, ww, hh, C_HAIR_D, 195)
    elif det == "shirt":
        for name in ("north", "south", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                rect(x, y, ww, max(1, hh * 0.16), C_WHITE_L, 245)
                folds(x, y, ww, hh, (226, 224, 234), 2, 160)
                hem(x, y, ww, hh, C_WHITE_D, 200)
        if "north" in f:
            x, y, ww, hh = f["north"]
            stitch(x, y + hh * 0.22, ww, 200)
    elif det in ("sock", "sock_top"):
        for name in ("north", "south", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                if det == "sock":
                    rect(x, y + hh * 0.86, ww, max(1, hh * 0.12), C_NAVY, 255)
                    rect(x, y + hh * 0.72, ww, max(1, hh * 0.08), C_RIBBON, 235)
                    rect(x, y, max(1, ww * 0.16), hh, (234, 236, 242), 150)
                    rect(x + ww * 0.8, y, max(1, ww * 0.16), hh, (228, 230, 238), 130)
                else:
                    rect(x, y + hh * 0.55, ww, max(1, hh * 0.45), C_NAVY, 255)
                    rect(x, y, ww, max(1, hh * 0.22), C_WHITE_L, 240)
    elif det == "shoe":
        for name in ("north", "south", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                rect(x, y, ww, max(1, hh * 0.2), C_WHITE_L, 245)
                rect(x, y + hh * 0.30, ww, max(1, hh * 0.09), C_WHITE, 240)
                rect(x, y + hh * 0.44, ww, max(1, hh * 0.09), C_WHITE, 240)
                hem(x, y, ww, hh, C_NAVY_D, 215)
    elif det == "sole":
        for name in ("north", "south", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                rect(x, y, ww, max(1, hh * 0.35), C_WHITE_L, 240)
                rect(x, y + hh * 0.62, ww, max(1, hh * 0.38), (206, 208, 218), 255)
                for i in range(0, int(ww), 2):
                    rect(x + i, y + hh * 0.62, 1, max(1, hh * 0.2), (186, 188, 200), 220)
    elif det in ("pleat", "pleat_d"):
        for name in ("north", "south", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                if ww >= 3:
                    t3 = max(1, int(ww / 3.0))
                    rect(x, y, t3, hh, C_BLUE, 205)
                    rect(x + t3, y, t3, hh, C_NAVY, 205)
                    rect(x + 2 * t3, y, max(1, ww - 2 * t3), hh, C_BLUE_D, 205)
                rect(x, y, ww, max(1, hh * 0.12), (180, 200, 226), 180)
                rect(x, y + hh * 0.88, ww, max(1, hh * 0.12), C_WHITE, 245)
    elif det == "frill":
        for name in ("north", "south", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                rect(x, y, ww, hh, C_WHITE, 250)
                rect(x, y + hh * 0.55, ww, max(1, hh * 0.45), C_WHITE_L, 250)
                for i in range(0, int(ww), 2):
                    rect(x + i, y + hh * 0.5, 1, max(1, hh * 0.5), (222, 221, 230), 200)
    elif det == "band":
        for name in ("north", "south", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                rect(x, y, ww, max(1, hh * 0.3), (96, 108, 156), 230)
                rect(x, y + hh * 0.55, ww, max(1, hh * 0.25), C_NAVY_D, 220)
        if "north" in f:
            x, y, ww, hh = f["north"]
            rect(x + ww * 0.4, y, max(2, ww * 0.2), hh, C_GOLD, 240)
            rect(x + ww * 0.43, y + hh * 0.25, max(1, ww * 0.14), max(1, hh * 0.5), (250, 230, 180), 240)
    elif det in ("tail", "tail_tip"):
        for name in ("north", "south", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                for i in range(3):
                    rect(x, y + hh * (0.08 + i * 0.30), ww, max(1, hh * 0.16),
                         C_HAIR_L if i % 2 == 0 else C_HAIR_D, 190)
                rect(x, y, max(1, ww * 0.2), hh, C_HAIR_HL, 130)
        if det == "tail_tip" and "north" in f:
            x, y, ww, hh = f["north"]
            rect(x, y + hh * 0.5, ww, hh * 0.5, C_FUR, 250)
    elif det in ("ear", "ear_in"):
        for name in ("north", "south", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                strands(x, y, ww, hh, 185)
                hem(x, y, ww, hh, C_HAIR_D, 200)
        if det == "ear_in" and "north" in f:
            x, y, ww, hh = f["north"]
            rect(x + ww * 0.12, y + hh * 0.08, ww * 0.76, hh * 0.84, C_FUR, 255)
            rect(x + ww * 0.28, y + hh * 0.28, ww * 0.44, hh * 0.5, (238, 228, 228), 225)
    elif det == "sleeve":
        for name in ("north", "south", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                folds(x, y, ww, hh, C_JACKET_D, 2, 155)
                hem(x, y, ww, hh, C_JACKET_D, 210)
        if "north" in f:
            x, y, ww, hh = f["north"]
            rect(x, y + hh * 0.87, ww, max(1, hh * 0.13), C_WHITE_L, 240)
    elif det == "cuff":
        for name in ("north", "south", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                rect(x, y, ww, max(1, hh * 0.3), C_WHITE_L, 235)
                hem(x, y, ww, hh, C_JACKET_D, 200)
    elif det == "cardigan":
        for name in ("north", "south", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                rect(x, y, max(1, ww * 0.12), hh, C_JACKET_D, 215)
                stitch(x, y + hh * 0.24, ww, 200)
                hem(x, y, ww, hh, C_JACKET_D, 205)
                rect(x + ww * 0.55, y + hh * 0.6, max(2, ww * 0.33), max(1, hh * 0.26), C_JACKET_D, 165)
    elif c["mat"] == "ribbon":
        for name in ("north", "south", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                rect(x, y, ww, max(1, hh * 0.3), (210, 218, 232), 240)
                hem(x, y, ww, hh, C_RIBBON_D, 225)
    elif c["mat"] == "gold":
        for name in ("north", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                rect(x, y, ww, max(1, hh * 0.22), (242, 214, 170), 240)
                ell(x + ww * 0.34, y + hh * 0.42, max(1, ww * 0.15), max(1, hh * 0.16), (255, 248, 226), 240)
                hem(x, y, ww, hh, (176, 134, 96), 230)
        if "down" in f:
            x, y, ww, hh = f["down"]
            rect(x + ww * 0.4, y + hh * 0.35, max(1, ww * 0.2), max(1, hh * 0.45), (176, 134, 96), 250)
    elif det == "neck":
        for name in ("north", "south", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                vgrad(x, y, ww, hh, C_SKIN_D, C_SKIN, 255)
                rect(x, y + hh * 0.8, ww, max(1, hh * 0.2), (206, 168, 160), 220)
    elif det in ("arm", "forearm", "hand", "thigh", "hip", "jaw", "crown", "cheek"):
        for name in ("north", "south", "east", "west"):
            if name in f:
                x, y, ww, hh = f[name]
                vgrad(x, y, ww, hh, C_SKIN_L, C_SKIN_D, 95)
    elif det == "bust":
        # 衣服被胸顶起：受光面提亮、下缘压暗，靠明暗读出「衣下微凸」而不是靠颜色贴片
        x, y, ww, hh = f["north"]
        rect(x, y, ww, hh, C_WHITE_L, 200)
        rect(x, y, ww, max(1, hh * 0.18), C_WHITE_L, 160)
        rect(x, y + hh - max(1, hh * 0.22), ww, max(1, hh * 0.22), C_WHITE_D, 180)
    elif det == "plush":
        x, y, ww, hh = f["north"]
        ell(x + ww * 0.32, y + hh * 0.45, max(1, ww * 0.09), max(1, hh * 0.14), C_EYE_D)
        ell(x + ww * 0.68, y + hh * 0.45, max(1, ww * 0.09), max(1, hh * 0.14), C_EYE_D)
        ell(x + ww * 0.36, y + hh * 0.52, max(1, ww * 0.05), max(1, hh * 0.07), C_PINK, 200)
        ell(x + ww * 0.64, y + hh * 0.52, max(1, ww * 0.05), max(1, hh * 0.07), C_PINK, 200)
        rect(x + ww * 0.35, y + hh * 0.62, ww * 0.3, max(1, hh * 0.06), C_EYE_D, 200)
        rect(x + ww * 0.2, y + hh * 0.8, ww * 0.6, max(1, hh * 0.16), (252, 240, 240), 200)

for c in cubes:
    paint_cube(c)

# ---------------------------------------------------------------- 写出
names = {}
for c in cubes:
    names[c["name"]] = names.get(c["name"], 0) + 1
dup = {k: v for k, v in names.items() if v > 1}
if dup:
    raise SystemExit(f"块名重复: {dup}")
for c in cubes:
    c.pop("_wh", None)
spec = {"texture_size": TEXSIZE, "bones": [{"name": n, "parent": p, "pivot": list(pv)}
                                           for n, p, pv in BONES], "cubes": cubes}
SPEC.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")

from PIL import Image
im = Image.new("RGBA", (TEXSIZE, TEXSIZE))
im.putdata([px[y][x] for y in range(H) for x in range(W)])
im.save(TEX)

ys = [c["from"][1] for c in cubes]
xs = [c["from"][0] for c in cubes] + [c["from"][0] + c["size"][0] for c in cubes]
zs = [c["from"][2] for c in cubes] + [c["from"][2] + c["size"][2] for c in cubes]
face = [c for c in cubes if c["name"] == "face"][0]
fw, fh, fd = [int(round(x * face["k"])) for x in face["size"]]
print(f"v4: {len(BONES)} 骨骼 / {len(cubes)} 块  密度全局系数 {scale:.2f}  贴图占用 {occupancy*100:.0f}%")
print(f"  高度 {min(ys):.1f}~{max(ys)+0:.1f}u  宽 {min(xs):.1f}~{max(xs):.1f}  深 {min(zs):.1f}~{max(zs):.1f}")
print(f"  脸部 UV {FACE_UV[2]}x{FACE_UV[3]} px（专用矩形 {FACE_UV}，{FACE_UV[2]/face['size'][0]:.1f} px/u）→ v3 是 7x8")
print(f"  写 {SPEC.name} / {TEX.name}")
