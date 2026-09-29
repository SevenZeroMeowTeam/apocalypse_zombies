# -*- coding: utf-8 -*-
"""现代复合狩猎弩（modern compound hunting crossbow）crossbow v2 —— 程序化生成器.

按参考图重做：替换此前「汉代连弩/横置箭匣」方向，改为**哑光黑现代复合弩**。
  · 长而平直的合金主梁 + 箭头箭道槽（盛箭用）
  · 后段：抵肩枪托（骨架掏空式）+ 末端橡胶抵肩板
  · 中段下方：手枪式握把 + 扳机 + 扳机护圈 + 保险
  · 中段上方：皮卡汀尼导轨 + 黑色圆柱光学瞄准镜（4x32：镜筒/物镜/目镜/调节钮/镜环）
  · 前段：弓片座（riser）+ 两条弓臂向两侧展开（根部宽厚、向梢部渐薄、略有前曲）
  · 弓臂末端各一个椭圆形**凸轮**（金属黑，绕竖直轴 Y 自转）：
    偏心轮缘上下两道轮缘板、其间内凹**轮槽**，配圆形**轮毂**+幅条+贯穿**轴心**销与锁母
  · 复合弦系统：主弦横跨两凸轮（静止位于弓片座前方）；两段副缆自凸轮向内
    **交叉走线**（左缆过中线落右侧滚轮、右缆镜像落左侧），穿行于主梁上的
    **导线器**（cable_slide：跨主梁的 U 形卡座 + 两侧悬臂与立轴滚轮，沿主梁滑行）
  · **没有**脚踏环、**没有**箭匣/弹仓、静止无装箭（与参考图一致）

硬约束（逐条落实）：
  1. 朝向：枪口 = −Z，上 = +Y，+X = 射手右侧；原点 = 机身中心
  2. 骨骼 rest 全部零旋转（弧线/角度靠逐段 pivot+rot 的几何表达 + 动画通道）
  3. GeckoLib 真骨骼驱动；**绝不用整体缩放**，scale 只用于 0 隐藏
  4. 单位 16u = 1 方块；成品 14.8u(长) × 9.0u(宽) × 4.46u(高) = 92.5cm × 56.3cm × 27.9cm
  5. 圆/弧部件用图元函数（ring/disc/ring_y/cam 的等价做法），不手堆方块拼圆
  6. 贴图 512×512 逐面 UV；命名全小写+下划线；模型/贴图/动画同名 crossbow
  7. 交付坐标约定：写出前必须过 crossbow_v1.game_convention_geo / game_convention_anims
     （X 取反；**直接 import 复用，不重写**），否则游戏里左右镜像、动作反向

关键物理（几何/动画/自检三处共用同一套解算，见「弓弦运动学」段）：
  · 弦长恒定：主弦半段 STRING_LEN 固定，拉弦靠**弓臂绕枢轴屈曲** + 弦骨只转不伸缩
  · 凸轮同步自转；副缆由凸轮指向滑座，滑座 z 由「缆长恒定」解出 ⇒ 缆不会伸缩
  · 拉满时弦心恰落在牙（latch）上，弦卧箭道槽内

运行：cd /f/mcmod && python tools/crossbow_v2.py        （不需要 Blender）
预览：见 tools/crossbow_v2_scene.py（Blender 侧 bpy 渲 4 张图）
"""
from __future__ import annotations
import copy
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ---- 复用 v1 工具链（色板/图元/图集装箱/PNG/取反约定）——不重写 ----
import crossbow_v1 as cb1  # noqa: E402  （import 会先跑一遍 v1 的几何，随即被清空）

add, add_bone, y_rot2, LC = cb1.add, cb1.add_bone, cb1.y_rot2, cb1.LC
TEX, FACES = cb1.TEX, cb1.FACES
NAME = 'crossbow'
ART, RES = cb1.ART, cb1.RES

# v2 追加材质（浅灰银弦/缆、哑光黑聚合物）
cb1.MAT['string'] = ('cloth', (178, 180, 184))   # 主弦：浅灰银
cb1.MAT['cable'] = ('cloth', (166, 168, 172))    # 副缆：略深的灰银
cb1.MAT['poly'] = ('plastic', (34, 34, 36))      # 黑色聚合物（握把/枪托）

# ---------------------------------------------------------------- 清空 v1 几何
cb1.BONES[:] = []
cb1.CUBES[:] = []
cb1._cidx = 0

# ================================================================ 尺寸常量（u）
# 朝向：−Z 枪口 / +Y 上 / +X 射手右；原点 = 机身中心
Z_RAIL0, Z_RAIL1 = -6.60, -3.30        # 箭道槽段（弦在其中后行至牙）；后端随 LATCH_Z 后移
X_RAIL = 0.55                          # 主梁半宽
RAIL_Y0, RAIL_Y1 = 0.72, 1.12          # 主梁底/槽口顶
Z_RISER0, Z_RISER1 = -6.60, -5.55      # 弓片座前后

# 弓臂几何（1.1.28 重定）：静止时梢部**略向后掠（+6.3°）**，凸轮落在弓片座平面稍后，与参考图一致；
# 拉满时由解算器得出 19.5° 屈曲。旧版梢部是 −11° **向前甩**的，弓臂因此显得短而直。
# 「后掠」以前做不到的原因：旧解算器是「先指定屈曲角 → 再解出臂长变化」，梢部一后掠就要把臂长
# 拉伸 1.95u；现在解算器改成「臂长与弦长都不变 → 两圆交点定出梢部 → **屈曲角是解出来的**」，
# 滑移恒为 0，后掠随之解锁（详见 limb_pose()）。
# 总宽已顶到参考要求的 65cm 上限（64.7cm），x 方向无可再加 ⇒ 「加长」靠曲度 LIMB_ARC（只进几何）。
LIMB_PIVOT_X, LIMB_PIVOT_Z = 0.95, -6.60   # 弓臂枢轴（= limb_* 骨 pivot，贴弓片座前脸）
LIMB_TIP_X, LIMB_TIP_Z = 4.55, -6.20       # 弓臂梢部 = 凸轮心 = 弦挂点（静止后掠 +6.3°）
STRING_Y = 0.95
STRING_LEN = LIMB_TIP_X                    # 主弦半段长（严格不可变）
Z_NOCK_REST = LIMB_TIP_Z                   # 静止弦心 z（= 梢部 z）
LATCH_Z = -3.30                            # 牙（挂机）z：落在扳机 z −3.40 上，拉程 2.90u。
# 约束（自检硬断言）：拉程越短 ⇒ 解出的屈曲角越小，draw 段要求 ≥15° ⇒ 梢部后掠有上限。
CAM_R0, CAM_DR = 0.50, 0.07                # 凸轮平均半径/椭圆偏心（半径 0.43~0.57）
CAM_YTH = 0.30                             # 凸轮轴向（Y）厚度
CAM_FLANGE = 0.082                         # 轮缘板厚度（沿 Y，上下各一道）
CAM_GROOVE = 0.058                         # 轮槽深（径向内凹量；槽底即弦/缆行走面）

CABLE_Y = 1.00                             # 副缆平面（略高于主弦，避免穿插）
SLIDE_REST_Z = -6.60                       # 导线器（滚轮座）静止 z
GUIDE_X = 0.86                             # 导线器滚轮 x；副缆**交叉**走线：左缆落 +x、右缆落 −x
END_X = {'l': GUIDE_X, 'r': -GUIDE_X}
# 缆长恒定：L_CABLE = |凸轮心 − 对侧滚轮|（静止姿态）。左右镜像 ⇒ 两缆的 |Δx| 恒等，
# 故「滑座 z 由缆长解出」单通道仍能逐帧同时满足两条缆，缆永不伸缩。
L_CABLE = math.hypot(LIMB_TIP_X + GUIDE_X, SLIDE_REST_Z - LIMB_TIP_Z)   # ≈5.50u

CAM_SPIN = 140.0                           # 拉满时凸轮自转 140°
SCOPE_Y = 2.06                             # 瞄准镜轴线高
HIDDEN = ('hand_l', 'bolt_loaded')         # 平时 scale=0 隐藏的部件
# ================================================================ 图元函数（圆形/弧形）
def ring_y(bone, cx, cz, y0, y1, r0, r1, n, mat):
    """绕 Y 轴的空心环（法向 ±Y，位于 XZ 平面）：n 段箱体，径向沿 X、切向沿 Z，绕 Y 旋 −a。"""
    if r1 <= r0:
        return
    thick = r1 - r0
    rm = (r0 + r1) / 2.0
    half = (rm * 2 * math.pi / n) * 0.5
    for i in range(n):
        a = math.radians(360.0 / n * i)
        xc, zc = cx + rm * math.cos(a), cz + rm * math.sin(a)
        add(bone, [xc - thick / 2, y0, zc - half], [xc + thick / 2, y1, zc + half], mat,
            rot=[0, -math.degrees(a), 0], pivot=[xc, (y0 + y1) / 2, zc])

def ring_x(bone, cy, cz, x0, x1, r0, r1, n, mat):
    """绕 X 轴的空心环（法向 ±X，位于 YZ 平面）：径向沿 Y、切向沿 Z，绕 X 旋 −a。"""
    if r1 <= r0:
        return
    thick = r1 - r0
    rm = (r0 + r1) / 2.0
    half = (rm * 2 * math.pi / n) * 0.5
    for i in range(n):
        a = math.radians(360.0 / n * i)
        yc, zc = cy + rm * math.cos(a), cz + rm * math.sin(a)
        add(bone, [x0, yc - thick / 2, zc - half], [x1, yc + thick / 2, zc + half], mat,
            rot=[math.degrees(a), 0, 0], pivot=[(x0 + x1) / 2, yc, zc])

def cam_wheel(bone, cx, cy, cz):
    """复合凸轮（细化版）：偏心椭圆轮缘（上下两道轮缘板 + 其间内凹轮槽）+ 圆形轮毂 +
    4 辐 + 贯穿轴销与外侧锁母 + 弦槽凸榫 + 副缆柱。
    非对称特征让「凸轮随拉弦自转」看得见；轮槽是弦/缆的实际行走面。"""
    n = 10
    y0, y1 = cy - CAM_YTH / 2, cy + CAM_YTH / 2
    for i in range(n):
        a = math.radians(360.0 / n * i)
        r = CAM_R0 + CAM_DR * math.cos(a)
        xc, zc = cx + r * math.cos(a), cz + r * math.sin(a)
        t_half = (r * 2 * math.pi / n) * 0.5 * 0.62          # 切向半宽（留缝）
        # ① 轮缘板：上下各一道，中间让出轮槽
        for ya, yb in ((y0, y0 + CAM_FLANGE), (y1 - CAM_FLANGE, y1)):
            add(bone, [xc - 0.055, ya, zc - t_half], [xc + 0.055, yb, zc + t_half], 'park',
                rot=[0, -math.degrees(a), 0], pivot=[xc, cy, zc])
        # ② 槽底：径向内凹 CAM_GROOVE，弦/缆卧于两缘板之间
        ri = r - CAM_GROOVE
        xi, zi = cx + ri * math.cos(a), cz + ri * math.sin(a)
        add(bone, [xi - 0.048, y0 + CAM_FLANGE, zi - t_half * 0.86],
            [xi + 0.048, y1 - CAM_FLANGE, zi + t_half * 0.86], 'dark',
            rot=[0, -math.degrees(a), 0], pivot=[xi, cy, zi])
    # ③ 圆形轮毂（图元环）+ 4 辐（不对称 ⇒ 自转可见）
    ring_y(bone, cx, cz, y0 - 0.012, y1 + 0.012, 0.115, 0.185, 8, 'dark')
    for deg in (26.0, 112.0, 198.0, 292.0):
        a = math.radians(deg)
        rm = (0.165 + CAM_R0 - CAM_GROOVE) / 2.0
        xc, zc = cx + rm * math.cos(a), cz + rm * math.sin(a)
        L = CAM_R0 - CAM_GROOVE - 0.15
        add(bone, [xc - L / 2, y0 + 0.045, zc - 0.042], [xc + L / 2, y1 - 0.045, zc + 0.042], 'dark',
            rot=[0, -deg, 0], pivot=[cx, cy, cz])
    # ④ 轴心：贯穿轴销（图元环）+ 出缘锁母（上下各一）
    ring_y(bone, cx, cz, y0 - 0.075, y1 + 0.075, 0.030, 0.068, 8, 'steel')
    for ya, yb in ((y0 - 0.075, y0 - 0.040), (y1 + 0.040, y1 + 0.075)):
        ring_y(bone, cx, cz, ya, yb, 0.068, 0.104, 6, 'steel')
    # ⑤ 弦槽凸榫（主弦缠绕点，−40°）+ 副缆柱（140°）
    for deg, rr in ((-40.0, CAM_R0 - 0.02), (140.0, CAM_R0 - CAM_GROOVE - 0.02)):
        a = math.radians(deg)
        xc, zc = cx + rr * math.cos(a), cz + rr * math.sin(a)
        ring_y(bone, xc, zc, cy - 0.165, cy + 0.165, 0.028, 0.058, 6, 'steel')

# ================================================================ 骨骼树（rest 姿态全零旋转）
add_bone('root', None, (0, 0, 0))
add_bone('move', 'root', (0, 0, 0))
add_bone('body', 'move', (0, 0, 0))
add_bone('constraint', 'body', (0, STRING_Y, LATCH_Z))          # 控制器：牙/挂机点
add_bone('camera', 'body', (0, SCOPE_Y, -1.50))                 # 控制器：瞄具视线
add_bone('limb_l', 'body', (-LIMB_PIVOT_X, STRING_Y, LIMB_PIVOT_Z))
add_bone('limb_r', 'body', (LIMB_PIVOT_X, STRING_Y, LIMB_PIVOT_Z))
add_bone('cam_l', 'limb_l', (-LIMB_TIP_X, STRING_Y, LIMB_TIP_Z))
add_bone('cam_r', 'limb_r', (LIMB_TIP_X, STRING_Y, LIMB_TIP_Z))
add_bone('string_l', 'limb_l', (-LIMB_TIP_X, STRING_Y, LIMB_TIP_Z))
add_bone('string_r', 'limb_r', (LIMB_TIP_X, STRING_Y, LIMB_TIP_Z))
add_bone('cable_l', 'limb_l', (-LIMB_TIP_X, CABLE_Y, LIMB_TIP_Z))
add_bone('cable_r', 'limb_r', (LIMB_TIP_X, CABLE_Y, LIMB_TIP_Z))
add_bone('cable_slide', 'body', (0, CABLE_Y, SLIDE_REST_Z))
add_bone('latch', 'body', (0, STRING_Y, LATCH_Z))               # 牙
add_bone('trigger', 'body', (0, 0.60, -3.40))                   # 扳机枢轴
add_bone('scope', 'body', (0, SCOPE_Y, -1.50))
add_bone('scope_elev', 'scope', (0, SCOPE_Y + 0.34, -1.50))
add_bone('scope_wind', 'scope', (0.40, SCOPE_Y, -1.50))
add_bone('hand_l', 'body', (-1.30, -0.30, -5.45))               # 左手（含所持箭矢）
add_bone('bolt_loaded', 'body', (0, STRING_Y, -5.40))           # 箭道上待发矢

BONE_NAMES = [b['name'] for b in cb1.BONES]

# ================================================================ 主体几何
# ---- 弓片座 riser（中央留 0.44u 弦/箭通道；弦可自前向后通过）----
add('body', [-0.95, 0.55, -6.60], [-0.22, 1.60, -6.42], 'park')      # 前板左
add('body', [0.22, 0.55, -6.60], [0.95, 1.60, -6.42], 'park')        # 前板右
add('body', [-0.22, 1.38, -6.60], [0.22, 1.60, -6.42], 'park')       # 前板上桥（下留通道）
add('body', [-0.95, 0.72, -6.42], [-0.30, 1.48, -5.55], 'poly')      # 左肩
add('body', [0.30, 0.72, -6.42], [0.95, 1.48, -5.55], 'poly')        # 右肩
add('body', [-0.30, 1.26, -6.42], [0.30, 1.48, -5.55], 'poly')       # 上桥
add('body', [-0.30, 0.72, -6.42], [-0.22, 1.26, -5.55], 'dark')    # 通道左壁
add('body', [0.22, 0.72, -6.42], [0.30, 1.26, -5.55], 'dark')      # 通道右壁
for sx in (-1.0, 1.0):
    add('body', [0.82 * sx, 0.50, -7.14], [1.09 * sx, 1.40, -6.58], 'dark')   # 弓片夹座（座前脸外侧）
    add('body', [0.60 * sx, 0.56, -7.08], [0.84 * sx, 1.34, -6.66], 'park')   # 夹座内衬

# ---- 主梁 / 箭道槽（盛箭 + 弦卧其中后行至牙）----
add('body', [-X_RAIL, RAIL_Y0, Z_RAIL0], [X_RAIL, RAIL_Y0 + 0.14, Z_RAIL1], 'poly')       # 槽底
add('body', [-X_RAIL, RAIL_Y0 + 0.14, Z_RAIL0], [-0.16, RAIL_Y1, Z_RAIL1], 'poly')        # 槽左壁
add('body', [0.16, RAIL_Y0 + 0.14, Z_RAIL0], [X_RAIL, RAIL_Y1, Z_RAIL1], 'poly')          # 槽右壁
add('body', [-0.62, 0.58, -6.30], [-X_RAIL, RAIL_Y0, -3.70], 'poly')                      # 护木左
add('body', [X_RAIL, 0.58, -6.30], [0.62, RAIL_Y0, -3.70], 'poly')                        # 护木右
add('body', [-0.62, 0.44, -5.90], [0.62, 0.58, -4.60], 'dark')                            # 护木下脊（缩短，为前握把让位）
# ---- 垂直前握把（现代弩标配；整体落在 y ≤ 0.44，不侵入弦道）----
add('body', [-0.26, -0.62, -5.20], [0.26, 0.44, -4.70], 'poly')                            # 前握把主体
add('body', [-0.24, -0.78, -5.14], [0.24, -0.60, -4.76], 'dark')                           # 前握把底盖
# ---- 脚踏环（现代弩标志件：拉弦时脚踩固定；纯外挂，不侵入弦/箭通道）----
add('body', [-0.62, 0.56, -7.62], [-0.42, 1.34, -6.55], 'dark')                            # 环左立柱
add('body', [0.42, 0.56, -7.62], [0.62, 1.34, -6.55], 'dark')                              # 环右立柱
add('body', [-0.62, 0.56, -7.62], [0.62, 0.76, -7.44], 'dark')                             # 环下梁
add('body', [-0.62, 1.14, -7.62], [0.62, 1.34, -7.44], 'dark')                             # 环上梁（弦/箭从 y 0.76~1.14 的空档穿过）

# ---- 机匣（短机匣；箭道槽后端 = 勾爪总成的喉部）----
add('body', [-0.62, 0.55, -4.10], [-0.16, 1.24, -1.30], 'dark')                           # 侧板左
add('body', [0.16, 0.55, -4.10], [0.62, 1.24, -1.30], 'dark')                             # 侧板右
add('body', [-0.16, 1.14, -3.70], [0.16, 1.28, -1.30], 'poly')                             # 上盖
add('body', [-0.68, 0.92, -3.92], [-0.46, 1.06, -3.68], 'dark')                           # 保险座
add('body', [-0.86, 0.94, -3.88], [-0.68, 1.06, -3.72], 'steel')                          # 保险钮
# 皮卡汀尼导轨（座 + 8 齿）
add('body', [-0.24, 1.28, -4.30], [0.24, 1.42, 0.40], 'park')
for i in range(8):
    z = -4.22 + i * 0.56
    add('body', [-0.26, 1.42, z], [0.26, 1.50, z + 0.16], 'park')

# ---- 扳机护圈 + 扳机 ----
add('body', [-0.26, 0.06, -4.00], [0.26, 0.86, -3.82], 'park')                            # 护圈前柱
add('body', [-0.26, 0.06, -2.72], [0.26, 0.86, -2.54], 'park')                            # 护圈后柱
add('body', [-0.26, 0.06, -4.00], [0.26, 0.22, -2.54], 'park')                            # 护圈底
add('trigger', [-0.13, 0.16, -3.55], [0.13, 0.90, -3.37], 'steel', pivot=[0, 0.60, -3.40])
add('trigger', [-0.13, 0.16, -3.41], [0.13, 0.34, -3.25], 'steel', pivot=[0, 0.60, -3.40])

# ---- 现代勾爪总成（弦的落点 = 爪面；台账偏差 #7 的正解）----
# 弦体实测厚 0.09u ⇒ 弦高带 y 0.905~0.995；满弦弦心钉在 LATCH_Z = −3.30（latch 骨 pivot 也在此）
# ⇒ 弦后脸 = −3.255 ⇒ 卡爪前脸必须正好落在 −3.255：弦被爪咬住，不再悬在牙后方 0.90u 的空中；
#   弦道走廊（z −6.20 → −3.30、y 0.905~0.995、过 x=0）内除箭道内壁（|x|≥0.16）外不得再有实体。
add('body', [-0.20, 0.55, -3.80], [0.20, 0.905, -3.10], 'dark')                           # 勾爪罩下座（顶面 0.905 = 弦道底，弦贴其面滑行）
add('latch', [-0.20, 0.86, -3.44], [0.20, 0.905, -3.00], 'steel')                         # 爪座（随牙骨微转）
add('latch', [-0.155, 0.905, -3.255], [0.155, 0.995, -3.06], 'steel')                     # 下爪（弦后脸正抵此面）
add('latch', [-0.155, 0.995, -3.255], [0.155, 1.14, -3.06], 'steel')                      # 上颚（封槽口；放弦时随牙下摆让弦通过）
add('latch', [-0.22, 0.90, -3.22], [0.22, 1.00, -3.08], 'copper')                         # 轴销（贯穿爪体，落在牙骨 pivot 高度）

# ---- 现代短托（拇指孔托颈 + 骨架托梁 + 抵肩板；托段总长自 8.30u 收到 4.92u）----
add('body', [-0.44, 0.10, -1.30], [0.44, 1.28, 0.55], 'poly')                             # 机匣尾段（顶面 1.28 承导轨、底面 0.10 接托颈下梁）
add('body', [-0.30, 0.72, 0.55], [0.30, 1.20, 1.35], 'poly')                              # 托颈上梁（拇指孔上缘）
add('body', [-0.30, 0.10, 0.55], [0.30, 0.42, 1.35], 'poly')                              # 托颈下梁（拇指孔下缘）
add('body', [-0.44, 0.62, 1.35], [0.44, 1.34, 3.60], 'poly')                              # 托颊
add('body', [-0.30, 1.34, 1.35], [0.30, 1.46, 3.00], 'dark')                              # 托腮软垫
add('body', [-0.46, 0.26, 3.60], [0.46, 1.28, 3.74], 'dark')                              # 抵肩板
add('body', [-0.34, 0.26, 3.74], [0.34, 0.94, 4.24], 'poly')                              # 骨架后梁
add('body', [-0.34, 0.94, 3.74], [0.34, 1.22, 4.24], 'poly')                              # 骨架后梁上
add('body', [-0.36, 0.20, 4.24], [0.36, 0.96, 4.48], 'dark')                              # 抵肩胶垫
# ---- 手枪式握把（后倾 16°，绕 X 旋）----
add('body', [-0.34, -2.10, -3.30], [0.34, 0.86, -2.30], 'poly', rot=[-16, 0, 0], pivot=[0, 0.86, -2.86])
add('body', [-0.36, -1.05, -3.05], [0.36, -0.45, -2.35], 'dark', rot=[-16, 0, 0], pivot=[0, 0.86, -2.86])
add('body', [-0.36, -2.16, -3.16], [0.36, -1.90, -2.36], 'dark', rot=[-16, 0, 0], pivot=[0, 0.86, -2.86])

# ---- 瞄准镜（4x32：镜筒/物镜/目镜/调节钮/镜环/分划）----
add('scope', [-0.16, 1.50, -2.50], [0.16, 1.80, -2.10], 'dark')                           # 前镜环柱
add('scope', [-0.16, 1.50, -0.40], [0.16, 1.80, 0.00], 'dark')                            # 后镜环柱
for zc in (-2.30, -0.20):
    cb1.ring('scope', 0.0, SCOPE_Y, zc - 0.09, zc + 0.09, 0.30, 0.44, 8, 'park')           # 镜环
for i in range(7):
    z0 = -2.60 + i * 0.40
    cb1.ring('scope', 0.0, SCOPE_Y, z0, z0 + 0.40, 0.28, 0.30, 12, 'park')               # 镜筒 7 段
cb1.ring('scope', 0.0, SCOPE_Y, -3.40, -3.20, 0.44, 0.46, 12, 'park')                    # 物镜口环
cb1.ring('scope', 0.0, SCOPE_Y, -3.20, -2.60, 0.34, 0.46, 12, 'park')                    # 物镜喇叭
cb1.ring('scope', 0.0, SCOPE_Y, 0.20, 0.44, 0.34, 0.38, 10, 'park')                      # 目镜喇叭
cb1.ring('scope', 0.0, SCOPE_Y, 0.44, 1.00, 0.36, 0.38, 12, 'park')                      # 目镜筒
add('scope', [-0.32, SCOPE_Y - 0.34, 1.00], [0.32, SCOPE_Y + 0.34, 1.12], 'poly')          # 眼罩
cb1.disc('scope', 0.0, SCOPE_Y, -3.30, 0.40, 8, 'glass')                                   # 物镜玻璃
cb1.disc('scope', 0.0, SCOPE_Y, 1.04, 0.36, 8, 'glass')                                    # 目镜玻璃
add('scope', [-0.34, SCOPE_Y - 0.02, 0.58], [0.34, SCOPE_Y + 0.02, 0.62], 'dark')          # 分划横线
add('scope', [-0.02, SCOPE_Y - 0.34, 0.58], [0.02, SCOPE_Y + 0.34, 0.62], 'dark')          # 分划竖线
cb1.ring('scope', 0.0, SCOPE_Y, -1.58, -1.42, 0.34, 0.46, 8, 'park')                       # 高低调节座
add('scope_elev', [-0.16, SCOPE_Y + 0.34, -1.70], [0.16, SCOPE_Y + 0.50, -1.30], 'steel')  # 高低钮
ring_y('scope_elev', 0.0, -1.50, SCOPE_Y + 0.50, SCOPE_Y + 0.56, 0.06, 0.16, 8, 'dark')
add('scope_wind', [0.34, SCOPE_Y - 0.14, -1.64], [0.46, SCOPE_Y + 0.14, -1.36], 'steel')   # 风偏钮
ring_x('scope_wind', SCOPE_Y, -1.50, 0.46, 0.52, 0.06, 0.16, 8, 'dark')

# ---- 弓臂（弓片）：逐段贴弧线切线；根宽厚、向梢渐薄；略有前曲 ----
LIMB_ARC = -1.10        # 前曲量（中段前凸、两端平滑回收）：现代复合弩的长弯弓臂
LIMB_SEG = 11           # 弓臂分段数（弧越强需越多段才不出现折面）
def do_limb(side):
    bone = 'limb_l' if side == 'l' else 'limb_r'
    sgn = -1.0 if side == 'l' else 1.0
    x0, x1 = LIMB_PIVOT_X * sgn, LIMB_TIP_X * sgn
    z0, z1 = LIMB_PIVOT_Z, LIMB_TIP_Z
    n = LIMB_SEG
    def pt(u):
        # sin² 剖面：两端斜率为 0 ⇒ 弓臂根部贴合弓片座、梢部与凸轮面平齐，不再有折角
        # （旧版 sin 剖面端部斜率为 π·LIMB_ARC，曲度一大就在凸轮接合处出现约 25° 折角）
        return (x0 + (x1 - x0) * u,
                z0 + (z1 - z0) * u + LIMB_ARC * math.sin(math.pi * u) ** 2)
    pts = [pt(i / n) for i in range(n + 1)]
    for i in range(n):
        (xa, za), (xb, zb) = pts[i], pts[i + 1]
        u = (i + 0.5) / n
        h = 0.60 - 0.20 * u                    # 上下宽（Y）：根 3.75cm → 梢 2.5cm
        t = 0.42 - 0.16 * u                    # 前后厚（Z）：根 2.6cm → 梢 1.6cm
        dx, dz = xb - xa, zb - za
        Ln = math.hypot(dx, dz)
        ang = math.degrees(math.atan2(dz, dx))
        rot = -ang                              # 箱体长轴原沿 +X ⇒ 绕 Y 旋 −ang
        ext = 0.05
        ox, ln = min(xa, xb) - ext, Ln + 2 * ext
        add(bone, [ox, STRING_Y - h / 2, za - t / 2], [ox + ln, STRING_Y + h / 2, za + t / 2], 'poly',
            rot=[0, rot, 0], pivot=[xa, STRING_Y, za])
    # 梢部凸轮轴座 + 竖轴
    add(bone, [min(x1, x1 - 0.30 * sgn), STRING_Y - 0.19, LIMB_TIP_Z - 0.22],
        [max(x1, x1 - 0.30 * sgn), STRING_Y + 0.19, LIMB_TIP_Z + 0.22], 'park')
    add(bone, [LIMB_TIP_X * sgn - 0.08, 0.52, LIMB_TIP_Z - 0.08],
        [LIMB_TIP_X * sgn + 0.08, 1.38, LIMB_TIP_Z + 0.08], 'steel')
do_limb('l')
do_limb('r')

# ---- 凸轮（每侧一个，绕 Y 自转；椭圆偏心 + 幅条让自转可见）----
cam_wheel('cam_l', -LIMB_TIP_X, STRING_Y, LIMB_TIP_Z)
cam_wheel('cam_r', LIMB_TIP_X, STRING_Y, LIMB_TIP_Z)

# ---- 主弦（两段；内端汇于弦心；弦长恒定，只转不伸缩）----
for side in ('l', 'r'):
    sgn = -1.0 if side == 'l' else 1.0
    tipx = LIMB_TIP_X * sgn
    ax, bx = min(tipx, 0.0), max(tipx, 0.0)
    add('string_%s' % side, [ax, STRING_Y - 0.03, LIMB_TIP_Z - 0.03],
        [bx, STRING_Y + 0.03, LIMB_TIP_Z + 0.03], 'string')
    if side == 'l':
        add('string_l', [-0.95, STRING_Y - 0.045, LIMB_TIP_Z - 0.045],
            [-0.62, STRING_Y + 0.045, LIMB_TIP_Z + 0.045], 'dark')
    else:
        add('string_r', [0.62, STRING_Y - 0.045, LIMB_TIP_Z - 0.045],
            [0.95, STRING_Y + 0.045, LIMB_TIP_Z + 0.045], 'dark')

# ---- 副缆（自凸轮指向导线滑座；几何按静止姿态烘好倾角，动画通道写相对值）----
def cable_rest_rot(side):
    """静止姿态副缆的烘焙倾角：由凸轮心指向**对侧**导线滚轮（交叉走线）。"""
    tx = LIMB_TIP_X * (-1.0 if side == 'l' else 1.0)
    dx, dz = END_X[side] - tx, SLIDE_REST_Z - LIMB_TIP_Z
    axis = 0.0 if side == 'l' else 180.0
    return round(axis - math.degrees(math.atan2(dz, dx)), 3)

CABLE_REST = {s: cable_rest_rot(s) for s in ('l', 'r')}

for side in ('l', 'r'):
    sgn = -1.0 if side == 'l' else 1.0
    tx = LIMB_TIP_X * sgn
    ox, ex = (tx, tx + L_CABLE) if side == 'l' else (tx - L_CABLE, tx)
    add('cable_%s' % side, [ox, CABLE_Y - 0.035, LIMB_TIP_Z - 0.035],
        [ex, CABLE_Y + 0.035, LIMB_TIP_Z + 0.035], 'cable',
        rot=[0, CABLE_REST[side], 0], pivot=[tx, CABLE_Y, LIMB_TIP_Z])

# ---- 导线器（cable_slide：跨主梁的滑动轮架；两段副缆交叉穿行其上）----
add('cable_slide', [-0.72, 0.78, SLIDE_REST_Z - 0.26], [-0.55, 1.06, SLIDE_REST_Z + 0.26], 'park')   # 左卡板
add('cable_slide', [0.55, 0.78, SLIDE_REST_Z - 0.26], [0.72, 1.06, SLIDE_REST_Z + 0.26], 'park')    # 右卡板
add('cable_slide', [-0.72, 1.12, SLIDE_REST_Z - 0.26], [0.72, 1.25, SLIDE_REST_Z + 0.26], 'dark')   # 顶梁（跨过箭道）
add('cable_slide', [-0.30, 0.58, SLIDE_REST_Z - 0.30], [0.30, 0.78, SLIDE_REST_Z + 0.30], 'dark')   # 底滑靴
for sx in (-1.0, 1.0):
    x0 = sx * GUIDE_X                                                  # 滚轮中心 = 副缆交叉落点
    lo, hi = sorted((sx * 0.60, x0))
    add('cable_slide', [lo, 0.82, SLIDE_REST_Z - 0.19], [hi, 0.945, SLIDE_REST_Z + 0.19], 'park')    # 悬臂（监滚轮）
    ring_y('cable_slide', x0, SLIDE_REST_Z, 0.95, 1.19, 0.062, 0.128, 8, 'steel')                    # 立轴滚轮
    ring_y('cable_slide', x0, SLIDE_REST_Z, 0.902, 0.946, 0.062, 0.152, 8, 'dark')                   # 下挡肩（防缆脹出轮面）
    ring_y('cable_slide', x0, SLIDE_REST_Z, 1.194, 1.238, 0.062, 0.152, 8, 'dark')                   # 上挡肩
    ring_y('cable_slide', x0, SLIDE_REST_Z, 0.80, 1.30, 0.022, 0.048, 6, 'steel')                    # 滚轮立轴

# ---- 箭夹（左护木下；参考图无匣无箭）----
add('body', [-0.92, 0.24, -5.90], [-0.70, 0.66, -5.80], 'dark')
add('body', [-0.92, 0.24, -5.10], [-0.70, 0.66, -5.00], 'dark')
add('body', [-0.92, 0.24, -5.90], [-0.70, 0.32, -5.00], 'dark')
add('body', [-0.86, 0.30, -5.84], [-0.74, 0.60, -5.06], 'poly')

# ---- 箭矢（短矢；平时 scale=0 隐藏，仅 reload_tactical 期间按剧本出现）----
def bolt(bone, z_nock, z_tip, y, x=0.0):
    zn, zt = max(z_nock, z_tip), min(z_nock, z_tip)
    Lb = zn - zt
    add(bone, [x - 0.05, y - 0.05, zt + Lb * 0.16], [x + 0.05, y + 0.05, zn], 'wood_b')             # 箭杆
    add(bone, [x - 0.085, y - 0.085, zt], [x + 0.085, y + 0.085, zt + Lb * 0.16], 'steel')         # 铁镞
    add(bone, [x - 0.14, y - 0.02, zn - Lb * 0.30], [x + 0.14, y + 0.02, zn - Lb * 0.06], 'cloth')  # 尾羽
    add(bone, [x - 0.05, y - 0.05, zn], [x + 0.05, y + 0.05, zn + 0.07], 'dark')                  # 尾槽

bolt('bolt_loaded', LATCH_Z, LATCH_Z - 2.40, STRING_Y)          # 箭道上（待发位）
bolt('hand_l', LATCH_Z, LATCH_Z - 2.40, 0.36, x=-1.30)          # 左手所持（箭夹处）
# 左手（手套简形 + 三指）
add('hand_l', [-1.46, 0.10, -5.90], [-0.70, 0.66, -4.90], 'cloth')      # 手套（灰布，黑枪身上可辨）
for i in (-1, 0, 1):
    add('hand_l', [-0.72, 0.12, -5.70 + i * 0.42], [-0.52, 0.62, -5.42 + i * 0.42], 'cloth')
# ================================================================ 弓弦运动学（几何/动画/自检共用）
def limb_tip(side, deg):
    """弓臂绕枢轴屈曲 deg 后的梢部（未含沿臂轴的径向滑移）。"""
    sgn = -1.0 if side == 'l' else 1.0
    return y_rot2(LIMB_TIP_X * sgn, LIMB_TIP_Z, LIMB_PIVOT_X * sgn, LIMB_PIVOT_Z, deg)

def limb_dir(side, deg):
    """屈曲后臂轴方向（单位向量，父骨坐标帧）。"""
    sgn = -1.0 if side == 'l' else 1.0
    ph = math.atan2(LIMB_TIP_Z - LIMB_PIVOT_Z, (LIMB_TIP_X - LIMB_PIVOT_X) * sgn) - math.radians(deg)
    return math.cos(ph), math.sin(ph)

def limb_tip_full(side, deg, slide):
    """梢部真实位置 = 屈曲后梢部 + 沿臂轴的径向滑移（父骨帧）。"""
    tx, tz = limb_tip(side, deg)
    ex, ez = limb_dir(side, deg)
    return (tx + slide * ex, tz + slide * ez)

def limb_solve(side, z_nock, deg):
    """给定屈曲角 deg，解析解出沿臂轴滑移 s，使 |梢 − 弦心| 严格 == STRING_LEN。
    射线－圆交点（取远根）：过程连续、无镜像分支翻转，弦永不伸缩。返回 (slide, tip_x, tip_z)。"""
    sgn = -1.0 if side == 'l' else 1.0
    px, pz = LIMB_PIVOT_X * sgn, LIMB_PIVOT_Z
    tx0, tz0 = LIMB_TIP_X * sgn, LIMB_TIP_Z
    r = math.hypot(tx0 - px, tz0 - pz)
    ex, ez = limb_dir(side, deg)
    f = (0.0 - px) * ex + (z_nock - pz) * ez
    d = math.hypot(0.0 - px, z_nock - pz)
    disc = f * f - d * d + STRING_LEN ** 2
    if disc < 0.0:
        raise ValueError('弦长无解：d=%.3f f=%.3f L=%.3f' % (d, f, STRING_LEN))
    rho = f + math.sqrt(disc)
    return rho - r, px + rho * ex, pz + rho * ez

def limb_pose(side, ease):
    """该侧弓臂在 ease(0 静止 / 1 拉满) 时的 (屈曲角, 滑移, 弦心 z, 梢位置)。

    **物理正确的解算（1.1.28 起）**：弓臂是刚体、弦长恒定 —— 两个不变量把梢部位置钉死在
    「以枢轴为心、半径 r 的圆」与「以弦心为心、半径 STRING_LEN 的圆」的**交点**上，取该侧的
    那个交点（用与静止方向的夹角最小来选支，过程连续、无分支翻转）。于是：

      · **屈曲角是解出来的**（不再由外部常量指定）—— 臂长与弦长都由几何决定，绝不伸缩；
      · **滑移恒为 0** —— 旧版「先指定屈曲角、再解出臂长变化」会让弓臂在拉满过程中被拉伸
        0.2~0.4u（自检里的「径向滑移」就是它），也正是「梢部后掠」被否掉的原因。
    """
    sgn = -1.0 if side == 'l' else 1.0
    px, pz = LIMB_PIVOT_X * sgn, LIMB_PIVOT_Z
    tx0, tz0 = LIMB_TIP_X * sgn, LIMB_TIP_Z
    r = math.hypot(tx0 - px, tz0 - pz)
    ph0 = math.atan2(tz0 - pz, tx0 - px)
    z_nock = Z_NOCK_REST + (LATCH_Z - Z_NOCK_REST) * ease
    d = math.hypot(0.0 - px, z_nock - pz)
    if d < 1e-6:
        raise ValueError('枢轴与弦心重合，两圆无解')
    a = (r * r - STRING_LEN ** 2 + d * d) / (2.0 * d)
    h2 = r * r - a * a
    if h2 < 0.0:
        raise ValueError('弦长无解：两圆不相交 r=%.3f L=%.3f d=%.3f' % (r, STRING_LEN, d))
    h = math.sqrt(h2)
    ux, uz = (0.0 - px) / d, (z_nock - pz) / d
    pick = None
    for sgv in (1.0, -1.0):
        cx = px + a * ux - sgv * h * uz
        cz = pz + a * uz + sgv * h * ux
        dev = abs((math.atan2(cz - pz, cx - px) - ph0 + math.pi) % (2.0 * math.pi) - math.pi)
        if pick is None or dev < pick[0]:
            pick = (dev, cx, cz)
    _, cx, cz = pick
    # 符号约定：生成器内部 ph = ph0 − deg（见 limb_dir）⇒ 屈曲角取方向角变化的相反数。
    deg = -math.degrees(math.atan2(cz - pz, cx - px) - ph0)
    return deg, 0.0, z_nock, (cx, cz)

def string_bone_param(side, z_nock, limb_deg, tip):
    """弦骨 (rot_y, scale_x)：内端落 (0, STRING_Y, z_nock)；弦长恒定 ⇒ scale 恒 == 1。"""
    tx, tz = tip
    dx, dz = 0.0 - tx, z_nock - tz
    dx, dz = y_rot2(dx, dz, 0.0, 0.0, -limb_deg)
    axis = 0.0 if side == 'l' else 180.0
    rot = axis - math.degrees(math.atan2(dz, dx))
    if abs(rot) < 0.01:
        rot = 0.0
    return round(rot, 4), round(math.hypot(dx, dz) / STRING_LEN, 4)

def cable_pose(side, limb_deg, tip):
    """副缆 (骨旋转, 滑座 z)：内端落**对侧**导线滚轮；滑座 z 由「缆长恒定」解出。
        交叉走线：左缆自左凸轮过中线落 +GUIDE_X，右缆镜像落 −GUIDE_X ⇒ 两缆在中线交叉。"""
    tx, tz = tip
    dxe = END_X[side] - tx
    q = L_CABLE ** 2 - dxe * dxe
    if q <= 0.0:
        raise ValueError('副缆无解：|Δx|=%.3f > L_CABLE=%.3f' % (abs(dxe), L_CABLE))
    zs = tz + math.sqrt(q)
    dx, dz = dxe, zs - tz
    dx, dz = y_rot2(dx, dz, 0.0, 0.0, -limb_deg)
    axis = 0.0 if side == 'l' else 180.0
    rot = axis - math.degrees(math.atan2(dz, dx))
    rel = (rot - CABLE_REST[side] + 180.0) % 360.0 - 180.0      # 几何已烘静止倾角 ⇒ 通道写相对值
    if abs(rel) < 0.01:
        rel = 0.0                                              # 消掉浮点噪声，静止段不写该通道
    return round(rel, 4), zs

def base_pose():
    p = {}
    for nm in BONE_NAMES:
        hide = nm in HIDDEN
        p[nm] = ((0, 0, 0), (0, 0, 0), (0, 0, 0) if hide else (1, 1, 1))
    return p

def bow_pose(p, ease, cam_spin=CAM_SPIN):
    """写「弓臂屈曲 + 沿臂轴滑移 + 弦骨只转 + 凸轮自转 + 副缆/滑座」。
    ease 0=静止 1=拉满；弦长与缆长在整个过程中严格恒定。"""
    for side in ('l', 'r'):
        sgn = 1.0 if side == 'l' else -1.0
        deg, slide, zn, tip = limb_pose(side, ease)
        ex, ez = limb_dir(side, deg)
        r, sc = string_bone_param(side, zn, deg, tip)
        p['limb_%s' % side] = ((0, round(deg, 4), 0),
                               (round(slide * ex, 4), 0, round(slide * ez, 4)), (1, 1, 1))
        p['string_%s' % side] = ((0, r, 0), (0, 0, 0), (sc, 1, 1))
        p['cam_%s' % side] = ((0, round(cam_spin * ease * sgn, 3), 0), (0, 0, 0), (1, 1, 1))
        cr, zs = cable_pose(side, deg, tip)
        p['cable_%s' % side] = ((0, cr, 0), (0, 0, 0), (1, 1, 1))
        if side == 'l':
            p['cable_slide'] = ((0, 0, 0), (0, 0, round(zs - SLIDE_REST_Z, 4)), (1, 1, 1))
    return p

def merge(keys):
    """关键帧合并：与默认值相同的通道整条不写（省体积），其余逐帧写 catmullrom。"""
    bones = {}
    DEF = {'rotation': (0, 0, 0), 'position': (0, 0, 0), 'scale': (1, 1, 1)}
    for t, pose in keys:
        for bn, (rot, pos, sc) in pose.items():
            e = bones.setdefault(bn, {'rotation': {}, 'position': {}, 'scale': {}})
            ts = '%s' % (round(t, 4),)
            e['rotation'][ts] = rot
            e['position'][ts] = pos
            e['scale'][ts] = sc
    out = {}
    for bn, chans in bones.items():
        ent = {}
        for chan in ('rotation', 'position', 'scale'):
            vals = chans[chan]
            distinct = {tuple(v) for v in vals.values()}
            if len(distinct) == 1 and tuple(next(iter(vals.values()))) == DEF[chan]:
                continue                                     # 恒为默认 ⇒ 不写
            node = {}
            for ts, v in vals.items():
                node[ts] = {'post': {'vector': [round(x, 4) for x in v]}, 'lerp_mode': 'catmullrom'}
            if len(distinct) == 1:
                node = {'%s' % (0.0,): node[next(iter(node))]}    # 恒定非默认 ⇒ 只留 t=0
                node[next(iter(node))] = node['0.0']
                node = {'0.0': node['0.0']}
            ent[chan] = node
        if ent:
            out[bn] = ent
    return out

# ================================================================ 精确镜像（左右必须逐块成镜像）
def mirror_side(src, dst):
    """把 src 骨的几何按 x=0 平面**精确镜像**成 dst 骨（不是平移副本）。

    为什么必须有这一步：`cam_wheel` 的偏心半径 r = CAM_R0 + CAM_DR·cos(a) 在 a=0° 取极大，
    即**鼓包恒指向 +x** —— 于是右凸轮鼓包朝外（正确），左凸轮鼓包朝内（错）。再加上 4 根辐条
    （26/112/198/292°）、弦槽凸榫（−40°）、副缆柱（140°）全都按**绝对角度**摆放，两侧看起来
    就是两个不同的轮子。`do_limb` 同理：左右各用 ±sgn 独立算一遍抛物线弧，差 0.01u，
    整机 x 包围盒因此不对称（−4.91..+5.04）。

    镜像规则（内部坐标，即取反层之前）：
      · origin.x → −(origin.x + size.x)，size 不变
      · pivot.x  → −pivot.x
      · rot      → (rx, −ry, −rz)  —— 过 x=0 平面的反射把 Y/Z 转角取反，X 转角不变
      · mat 不变。每个面由装箱器各自分配同色贴块，平色材质下无需手工翻面。
    """
    src_cubes = [c for c in cb1.CUBES if c['bone'] == src]
    if not src_cubes:
        raise SystemExit('镜像源 %s 没有几何' % src)
    if not any(c['bone'] == dst for c in cb1.CUBES):
        raise SystemExit('镜像目标 %s 没有几何' % dst)
    kept = [c for c in cb1.CUBES if c['bone'] != dst]
    made = []
    for c in src_cubes:
        m = copy.deepcopy(c)
        m['bone'] = dst                      # 必须改归属骨，否则镜像块会留在源骨上（副本翻倍）
        m['origin'] = [round(-(c['origin'][0] + c['size'][0]), 4), c['origin'][1], c['origin'][2]]
        m['pivot'] = [round(-c['pivot'][0], 4), c['pivot'][1], c['pivot'][2]]
        if c.get('rot'):
            rx, ry, rz = c['rot']
            m['rot'] = [rx, -ry, -rz]
        m['id'] = cb1._cidx
        cb1._cidx += 1
        made.append(m)
    cb1.CUBES[:] = kept + made
    print('  镜像 %-8s → %-8s  %2d 块（精确镜像，替换原本的平移副本）' % (src, dst, len(made)))

mirror_side('cam_r', 'cam_l')       # 右轮鼓包朝外（对），左轮照它镜像
mirror_side('limb_r', 'limb_l')

def build_anims():
    anims = {}

    # -- static_idle：静止待机（呼吸 + 镜身摇曳；弦在静止位）--
    keys = []
    for i in range(41):
        t = i / 20.0
        p = base_pose()
        ph = 2 * math.pi * t / 2.0
        p['move'] = ((0, 0, 0), (0, round(0.090 * math.sin(ph), 4), 0), (1, 1, 1))
        p['body'] = ((round(2.40 * math.sin(ph), 4), 0, 0), (0, 0, 0), (1, 1, 1))
        p['scope'] = ((0, 0, round(1.50 * math.sin(ph + 0.9), 4)), (0, 0, 0), (1, 1, 1))
        bow_pose(p, 0.0)
        keys.append((round(t, 4), p))
    anims['static_idle'] = {'animation_length': 2.0, 'loop': True, 'bones': merge(keys)}

    # -- draw：拉弦（弓臂屈曲、弦后行挂牙、凸轮自转、副缆随动；弦长恒定）--
    DRAW = 1.2
    keys = []
    for i in range(int(DRAW * 24) + 1):
        t = i / 24.0
        u = min(1.0, t / 0.86)
        ease = u * u * (3 - 2 * u) if t < 0.86 else 1.0     # smoothstep，0.86s 拉满挂牙
        p = base_pose()
        bow_pose(p, ease)
        p['move'] = ((0, 0, 0), (0, round(-0.03 * ease, 4), round(-0.14 * ease, 4)), (1, 1, 1))
        p['body'] = ((round(-0.8 * ease, 3), 0, 0), (0, 0, 0), (1, 1, 1))
        p['latch'] = ((round(-4.0 * ease, 3), 0, 0), (0, 0, 0), (1, 1, 1))
        p['trigger'] = ((round(-3.0 * ease, 3), 0, 0), (0, 0, 0), (1, 1, 1))
        keys.append((round(t, 4), p))
    anims['draw'] = {'animation_length': DRAW, 'loop': False, 'bones': merge(keys)}

    # -- shoot：放弦（弦弹回 + 凸轮反向自转 + 牙落/扳机扣动 + 机身轻微后座）--
    SHOOT = 0.6
    RELEASE = 0.22                                           # 弦弹回时长：原 0.13s ⇒ 凸轮 140°/3.1 帧 = 44.9°/帧硬弹；
    keys = []                                                #            0.22s ⇒ 约 26.5°/帧，弓臂不再「啪」地瞬移
    for i in range(int(SHOOT * 24) + 1):
        t = i / 24.0
        u = min(1.0, t / RELEASE)                            # 弦 RELEASE 秒弹回
        ease = 1.0 - u
        p = base_pose()
        bow_pose(p, ease)
        rt = min(1.0, t / 0.20)                              # 后座脉冲
        kick = math.sin(math.pi * rt) if t < 0.20 else 0.0
        rs = max(0.0, 1.0 - t / 0.10)                        # 拉弦残位：击发瞬间仍在 draw 末帧姿态，随弦弹出归中
        rs = rs * rs * (3 - 2 * rs)                          # smoothstep ⇒ 与 draw 末帧 C1 接续，消掉 0.14u 单帧回弹
        p['move'] = ((0, 0, 0),
                     (0, round(-0.03 * rs + 0.05 * kick, 4), round(-0.14 * rs + 0.20 * kick, 4)),
                     (1, 1, 1))
        p['body'] = ((round(-0.8 * rs + 2.2 * kick, 3), 0, 0), (0, 0, 0), (1, 1, 1))
        # 牙：先落（卸弦）再回位
        lt = min(1.0, t / 0.08)
        p['latch'] = ((round(-2.0 + 30.0 * lt - (26.0 * min(1.0, max(0.0, (t - 0.30) / 0.30))), 3), 0, 0), (0, 0, 0), (1, 1, 1))
        pt = min(1.0, t / 0.06)
        p['trigger'] = ((round(-14.0 * pt + 11.0 * min(1.0, max(0.0, (t - 0.22) / 0.38)), 3), 0, 0), (0, 0, 0), (1, 1, 1))
        keys.append((round(t, 4), p))
    anims['shoot'] = {'animation_length': SHOOT, 'loop': False, 'bones': merge(keys)}

    # -- reload_tactical：左手自箭夹取矢 → 抬到主梁上方 → 顺箭道放到待发位 → 手收回，箭留在箭道 --
    T = 1.6
    keys = []
    HX, HY, HZ = -1.30, -0.30, -5.45                        # hand_l 骨 pivot = 静止位（箭夹处）
    for i in range(int(T * 24) + 1):
        t = i / 24.0
        p = base_pose()
        bow_pose(p, 0.0)
        lift = min(1.0, max(0.0, (t - 0.08) / 0.34))        # 0.08~0.42 抬起（越过导轨/机匣）
        push = min(1.0, max(0.0, (t - 0.46) / 0.42))        # 0.46~0.88 送到箭道正上方
        ret = min(1.0, max(0.0, (t - 0.94) / 0.42))         # 0.94~1.36 抽手收回
        vis = 1.0 if 0.06 < t < 0.92 else 0.0
        dx = 1.30 * push - 0.80 * ret
        dy = 1.64 * lift + 0.30 * ret
        dz = 0.40 * ret
        p['hand_l'] = ((0, round(-16.0 * lift * (1 - push), 3), 0),
                       (round(dx, 4), round(dy, 4), round(dz, 4)), (vis, vis, vis))
        # 待发矢：0.90 起由手无缝接管（同高同位）→ 0.90~1.12 落进箭道 → 留在箭道
        drop = min(1.0, max(0.0, (t - 0.90) / 0.22))
        lvis = 1.0 if t >= 0.90 else 0.0
        p['bolt_loaded'] = ((0, 0, 0), (0, round(1.05 * (1.0 - drop), 4), 0), (lvis, lvis, lvis))
        keys.append((round(t, 4), p))
    anims['reload_tactical'] = {'animation_length': T, 'loop': False, 'bones': merge(keys)}

    # -- ADS_up / ADS_down：抬镜/落镜（各 0.18s）--
    for nm, up in (('ADS_up', True), ('ADS_down', False)):
        keys = []
        # 关键帧只写到段长之内：0.18s 只装得下 0~4/24（0.1667s）。原先 range(6) 多写一帧
        # 0.2083s 落在段长之外 —— GeckoLib 会把它截掉，等于写了个死键。
        for i in range(5):
            t = round(i / 24.0, 4)
            u = min(1.0, i / 4.0)
            e = u if up else 1.0 - u
            p = base_pose()
            bow_pose(p, 0.0)
            p['move'] = ((0, 0, 0), (0, round(0.42 * e, 4), round(-0.26 * e, 4)), (1, 1, 1))
            p['body'] = ((round(-3.6 * e, 3), 0, 0), (0, 0, 0), (1, 1, 1))
            keys.append((t, p))
        anims[nm] = {'animation_length': 0.18, 'loop': False, 'bones': merge(keys)}

    # -- inspect：检视旋转 --
    INS = 2.6
    keys = []
    for i in range(int(INS * 24) + 1):
        t = i / 24.0
        p = base_pose()
        bow_pose(p, 0.0)
        y = -180.0 * (t / INS)
        p['root'] = ((0, round(y, 3), 0), (0, 0, 0), (1, 1, 1))
        p['scope'] = ((0, 0, round(2.0 * math.sin(2 * math.pi * t / INS), 3)), (0, 0, 0), (1, 1, 1))
        keys.append((round(t, 4), p))
    anims['inspect'] = {'animation_length': INS, 'loop': False, 'bones': merge(keys)}
    return anims

# ================================================================ 图集/贴图
def repack():
    d = 12.0
    while d >= 8.0:
        pl = cb1.pack(d)
        if pl is not None:
            return d, pl
        d -= 1.0
    return None, None

def repaint(placement):
    cb1.placement = placement
    cb1.CUBES_byid = {c['id']: c for c in cb1.CUBES}
    cb1.atlas = bytearray(b'\x00\x00\x00\x00' * (TEX * TEX))
    for ci, faces in placement.items():
        for f, (x, y, w, h) in faces.items():
            cb1.paint_face(ci, f, x, y, w, h)
    cb1._PNG = cb1.png_build()

# ================================================================ 自检
def selfcheck(geo, anims):
    fails, notes = [], []
    geom = geo['minecraft:geometry'][0]
    allc = [c for b in geom['bones'] for c in b.get('cubes', [])]
    names = [b['name'] for b in geom['bones']]
    # ① 尺寸全 > 0
    for c in allc:
        if not all(v > 0 for v in c['size']):
            fails.append('零/负尺寸 cube %s' % (c['origin'],))
    # ② bbox
    lo = [1e9] * 3; hi = [-1e9] * 3
    for c in allc:
        for kx in (0, 1):
            for ky in (0, 1):
                for kz in (0, 1):
                    v = [c['origin'][0] + c['size'][0] * kx, c['origin'][1] + c['size'][1] * ky,
                         c['origin'][2] + c['size'][2] * kz]
                    for k in range(3):
                        lo[k] = min(lo[k], v[k]); hi[k] = max(hi[k], v[k])
    LX, LY, LZ = hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]
    notes.append('bbox X=[%.2f,%.2f] 宽 %.2fu=%.1fcm' % (lo[0], hi[0], LX, LX * 6.25))
    notes.append('bbox Y=[%.2f,%.2f] 高 %.2fu=%.1fcm' % (lo[1], hi[1], LY, LY * 6.25))
    notes.append('bbox Z=[%.2f,%.2f] 长 %.2fu=%.1fcm=%.2f格' % (lo[2], hi[2], LZ, LZ * 6.25, LZ / 16))
    if not (12.0 <= LZ <= 24.0):
        fails.append('总长 %.2fu 不在 12~24u' % LZ)
    if not (6.0 <= LX <= 12.0):
        fails.append('总宽 %.2fu 不在 6~12u' % LX)
    if not (3.0 <= LY <= 7.0):
        fails.append('总高 %.2fu 不在 3~7u' % LY)
    if abs(Z_NOCK_REST - LIMB_TIP_Z) > 1e-6:
        fails.append('静止弦心与凸轮面不齐')
    # ③ 骨名 / 父骨 / 归属
    import re as _re
    nm_re = _re.compile(r'^[a-z][a-z0-9_]*$')
    nset = set(names)
    for b in geom['bones']:
        if not nm_re.match(b['name']):
            fails.append('骨名非法 %s' % b['name'])
        if b.get('rotation'):
            fails.append('rest 姿态带旋转 %s' % b['name'])
        if b.get('parent') and b['parent'] not in nset:
            fails.append('父骨缺失 %s' % b['name'])
        for c in b.get('cubes', []):
            if c.get('rotation'):
                pass
    for req in ('root', 'move', 'body', 'limb_l', 'limb_r', 'cam_l', 'cam_r',
                'string_l', 'string_r', 'cable_l', 'cable_r', 'cable_slide',
                'latch', 'trigger', 'scope', 'hand_l', 'bolt_loaded'):
        if req not in nset:
            fails.append('缺必需骨 %s' % req)
    used = {c['bone'] for c in cb1.CUBES}
    for bn in used:
        if bn not in nset:
            fails.append('cube 归属的骨不存在 %s' % bn)
    empty = [n for n in names if n not in used and n not in ('root', 'move', 'body', 'constraint', 'camera')]
    if empty:
        fails.append('空骨（无 cube）：%s' % empty)
    notes.append('方块=%d 骨=%d' % (len(allc), len(names)))
    if len(allc) > 600:
        fails.append('方块超 600')
    if len(names) > 40:
        fails.append('骨超 40')
    # ④ UV/贴图
    for c in allc:
        for f, uv in c.get('uv', {}).items():
            x, y, w, h = uv['uv'][0], uv['uv'][1], uv['uv_size'][0], uv['uv_size'][1]
            if x < 0 or y < 0 or x + w > TEX or y + h > TEX:
                fails.append('UV 越界 %s' % (uv,))
                continue
            if not any(cb1.atlas[(yy * TEX + xx) * 4 + 3] > 0
                       for yy in range(y, y + h) for xx in range(x, x + w)):
                fails.append('面全透明 %s %s' % (c['origin'], f))
    # ⑤ 动画：scale 只允许 0/1；弦/缆不得缩放；弦长与缆长恒定；弦两段内端汇于弦心；拉满落牙
    def str_inner(bone, limb_deg, limb_pos, a_deg, sc):
        """弦内端世界位置 (x,z)：梢部（含沿臂轴滑移）+ 弦骨方向 × STRING_LEN×sc。"""
        side = bone[-1]
        ex, ez = limb_dir(side, limb_deg)
        slide = limb_pos[0] * ex + limb_pos[2] * ez
        tx, tz = limb_tip_full(side, limb_deg, slide)
        phi = math.radians((0.0 if bone == 'string_l' else 180.0) - a_deg)
        dx, dz = STRING_LEN * sc * math.cos(phi), STRING_LEN * sc * math.sin(phi)
        dx, dz = y_rot2(dx, dz, 0.0, 0.0, limb_deg)
        return (tx + dx, tz + dz), slide

    def cable_inner(side, limb_deg, limb_pos, chan):
        """副缆内端世界位置 (x,z) = 凸轮心 + 缆骨方向 × L_CABLE（交叉 ⇒ 落对侧滚轮）。"""
        ex, ez = limb_dir(side, limb_deg)
        slide = limb_pos[0] * ex + limb_pos[2] * ez
        tx, tz = limb_tip_full(side, limb_deg, slide)
        phi = math.radians((0.0 if side == 'l' else 180.0) - CABLE_REST[side] - chan - limb_deg)
        return (tx + L_CABLE * math.cos(phi), tz + L_CABLE * math.sin(phi))

    for clip, body in anims.items():
        for bn, ch in body['bones'].items():
            for ts, kf in ch.get('scale', {}).items():
                vals = kf['post']['vector']
                if not all(abs(x) < 1e-6 or abs(x - 1.0) < 1e-6 for x in vals):
                    fails.append('%s %s scale=%s 非 0/1（禁止缩放）' % (clip, bn, vals))
                if bn.startswith(('string_', 'cable_')) and any(abs(x - 1.0) > 1e-6 for x in vals):
                    fails.append('%s %s 弦/缆被缩放 %s' % (clip, bn, vals))
        if clip in ('draw', 'shoot'):
            for need, why in (('cam_l', '凸轮未随拉弦自转'), ('cable_slide', '导线滑座未随动')):
                ch = body['bones'].get(need)
                if ch is None:
                    fails.append('%s 缺 %s（%s）' % (clip, need, why))
                    continue
                seq = ch.get('rotation') or ch.get('position') or {}
                if len({tuple(k['post']['vector']) for k in seq.values()}) < 2:
                    fails.append('%s %s 通道恒定（未真正随动）' % (clip, need))

    def chv(bn, ch, t, dflt=(0.0, 0.0, 0.0)):
        """取某骨某通道在 t 的值；通道被省略（恒为默认）时返回默认值。"""
        d = dr[bn].get(ch) if isinstance(bn, str) else None
        if not d:
            return dflt
        key = '%s' % (round(t, 4),)
        return d[key]['post']['vector'] if key in d else d['%s' % (t,)]['post']['vector']

    okclips = []
    max_slide = 0.0
    for clip in ('static_idle', 'draw', 'shoot', 'inspect', 'reload_tactical', 'ADS_up', 'ADS_down'):
        dr = anims[clip]['bones']
        zero = (0.0, 0.0, 0.0)
        if 'string_l' not in dr or 'string_r' not in dr:
            # 该段未动弓弦：按静止弦位（无屈曲/无滑移 rot=0 scale=1）核验弦仍原长且内端汇于弦心
            el, _ = str_inner('string_l', 0.0, zero, 0.0, 1.0)
            er, _ = str_inner('string_r', 0.0, zero, 0.0, 1.0)
            if math.hypot(el[0] - er[0], el[1] - er[1]) > 0.05 or \
               math.hypot(el[1] - Z_NOCK_REST, er[1] - Z_NOCK_REST) > 0.05:
                fails.append('%s 静止弦位不汇于弦心 (%.2f,%.2f)/(%.2f,%.2f)' % (clip, el[0], el[1], er[0], er[1]))
            okclips.append('%s[静止弦位ok]' % clip)
            continue
        okclips.append(clip)
        for t in sorted(map(float, dr['string_l']['rotation'].keys())):
            al = chv('limb_l', 'rotation', t)[1]
            ar = chv('limb_r', 'rotation', t)[1]
            pl = chv('limb_l', 'position', t)
            pr = chv('limb_r', 'position', t)
            rl = chv('string_l', 'rotation', t)[1]
            sl = chv('string_l', 'scale', t, (1.0, 1.0, 1.0))[0]
            rr = chv('string_r', 'rotation', t)[1]
            sr = chv('string_r', 'scale', t, (1.0, 1.0, 1.0))[0]
            el, sd1 = str_inner('string_l', al, pl, rl, sl)
            er, sd2 = str_inner('string_r', ar, pr, rr, sr)
            max_slide = max(max_slide, abs(sd1), abs(sd2))
            d = math.hypot(el[0] - er[0], el[1] - er[1])
            if d > 0.05:
                fails.append('%s t=%.3f 两段弦内端分离 %.3f u' % (clip, t, d))
            if abs(sl - 1.0) > 0.005 or abs(sr - 1.0) > 0.005:
                fails.append('%s t=%.3f 弦被拉伸 sc=%.4f/%.4f' % (clip, t, sl, sr))
            if abs(sd1) > 0.35 or abs(sd2) > 0.35:
                fails.append('%s t=%.3f 弓臂径向滑移过大 %.3f/%.3f u' % (clip, t, sd1, sd2))
            zs = SLIDE_REST_Z + chv('cable_slide', 'position', t)[2]
            for side, ld, lp in (('l', al, pl), ('r', ar, pr)):
                cd = chv('cable_%s' % side, 'rotation', t)[1]
                ix, iz = cable_inner(side, ld, lp, cd)
                if (ix > 0.0) != (side == 'l'):
                    fails.append('%s t=%.3f 副缆 %s 未交叉（内端 x=%.2f 仍在同侧）' % (clip, t, side, ix))
                if math.hypot(ix - END_X[side], iz - zs) > 0.06:
                    fails.append('%s t=%.3f 副缆 %s 内端未落对侧滚轮 (%.2f,%.2f) vs (±%.2f, z=%.2f)'
                                 % (clip, t, side, ix, iz, GUIDE_X, zs))
                if abs(cd) > 100.0:
                    fails.append('%s t=%.3f 副缆 %s 旋转异常 %.1f°' % (clip, t, side, cd))

    dr = anims['draw']['bones']
    kd = sorted(map(float, dr['string_l']['rotation'].keys()))[-1]
    def vd(b, ch, dflt=(0.0, 0.0, 0.0)):
        return chv(b, ch, kd, dflt)
    el, _ = str_inner('string_l', vd('limb_l', 'rotation')[1], vd('limb_l', 'position'),
                      vd('string_l', 'rotation')[1], vd('string_l', 'scale', (1.0, 1.0, 1.0))[0])
    if math.hypot(el[0] - 0.0, el[1] - LATCH_Z) > 0.06:
        fails.append('draw 拉满弦心未落牙 %s' % (el,))
    if abs(vd('limb_l', 'rotation')[1]) < 15.0:
        fails.append('draw 拉满弓臂几乎不屈曲（弓片不弯 = 不像真弩）')
    cam_end = max(abs(vd('cam_l', 'rotation')[1]), abs(vd('cam_r', 'rotation')[1]))
    if cam_end < 30.0:
        fails.append('draw 拉满凸轮几乎不转（应随弦自转）')
    if abs(vd('cable_slide', 'position')[2]) < 0.5:
        fails.append('draw 拉满导线滑座几乎不动（副缆不随动）')
    notes.append('draw 拉满：弓臂屈曲 l=%.2f° r=%.2f°（臂轴滑移 ≤%.3f u），凸轮自转 %.1f°，滑座 z=%.2f，弦心落 (%.2f,%.2f)'
                 % (vd('limb_l', 'rotation')[1], vd('limb_r', 'rotation')[1], max_slide, cam_end,
                    SLIDE_REST_Z + vd('cable_slide', 'position')[2], el[0], el[1]))
    notes.append('弦半段长恒定 %.3f u（scale 恒 1，禁止拉伸）；副缆长恒定 %.3f u'
                 '（**交叉走线**：左缆落 +%.2f、右缆落 −%.2f 导线滚轮，滑座 z 由缆长解出）'
                 % (STRING_LEN, L_CABLE, GUIDE_X, GUIDE_X))
    notes.append('已核验：%s' % '、'.join(okclips))
    return fails, notes, len(allc), len(names)

def sample_written(geo_written, anim_written, geo_in, anims_in):
    """④ 写出文件抽检：取反必须生效（拿写出的文件与内部表示逐项对照）。"""
    fails = []
    notes = []
    g = geo_written['minecraft:geometry'][0]
    bone = {b['name']: b for b in g['bones']}
    cw = bone['string_l']['cubes'][0]
    ci = [c for c in cb1.CUBES if c['bone'] == 'string_l'][0]
    exp_x = -(ci['origin'][0] + ci['size'][0])
    if abs(cw['origin'][0] - exp_x) > 1e-6:
        fails.append('geo 取反未生效：string_l cube origin.x 写出 %.4f，应为 -(%.4f+%.4f)=%.4f'
                     % (cw['origin'][0], ci['origin'][0], ci['size'][0], exp_x))
    if [round(v, 4) for v in cw['size']] != [round(v, 4) for v in ci['size']]:
        fails.append('geo 取反改动了 size（应只动最小角）')
    if abs(bone['move']['pivot'][0]) > 1e-9 and bone['move']['pivot'][0] != -0.0:
        fails.append('move pivot x 应为 0')
    # 动画：move 骨的 position X 取反
    a = anim_written['animations']['draw']['bones']['move']['position']
    k0 = sorted(a.keys(), key=float)[-1]
    vvv = a[k0]['post']['vector']
    if vvv[0] != 0.0:
        fails.append('anim move position.x 应为 0（取反后仍 0），得 %.4f' % vvv[0])
    # 内部几何的 x 与写出必须符号相反（再抽骨 pivot 与动画 position/rotation）
    bi = {b['name']: b for b in geo_in['minecraft:geometry'][0]['bones']}
    hw = bone['hand_l']['pivot'][0]
    hi = bi['hand_l']['pivot'][0]
    if abs(hw + hi) > 1e-6:
        fails.append('hand_l pivot.x 未取反：内部 %.4f 写出 %.4f' % (hi, hw))
    # 弓臂 position（沿臂轴的径向滑移）：新解算器下**恒为 0** ⇒ merge 会整条省掉该通道。
    # 所以这里不再假设通道存在：两侧必须同样缺失（缺失比存在且为 0 更强 —— 它证明弓臂不伸缩）。
    li = anims_in['draw']['bones']['limb_l']
    lw = anim_written['animations']['draw']['bones']['limb_l']
    ipos, wpos = li.get('position'), lw.get('position')
    posnote = ''
    if (ipos is None) != (wpos is None):
        fails.append('draw limb_l position 通道两侧不一致：内部 %s / 写出 %s'
                     % ('无' if ipos is None else '有', '无' if wpos is None else '有'))
    if ipos is not None:
        kp = sorted(wpos.keys(), key=float)[-1]
        ip = ipos[kp]['post']['vector']
        wp = wpos[kp]['post']['vector']
        if abs(wp[0] + ip[0]) > 1e-6 or abs(wp[2] - ip[2]) > 1e-6:
            fails.append('draw limb_l position 未按约定取反 x：内部 %s 写出 %s' % (ip, wp))
        posnote = ''
    else:
        ip = wp = [0.0, 0.0, 0.0]
        posnote = '（两侧都无该通道 = 弓臂零滑移、绝不伸缩）'
    kr = sorted(lw['rotation'].keys(), key=float)[-1]
    wr = lw['rotation'][kr]['post']['vector']
    ir = li['rotation'][kr]['post']['vector']
    if abs(wr[1] + ir[1]) > 1e-6:
        fails.append('draw limb_l rotation.y 未取反：内部 %.3f 写出 %.3f' % (ir[1], wr[1]))
    notes.append('写出抽检：string_l cube origin.x 内部 %.3f → 写出 %.3f（= −(x+size_x)）✓；'
                 'hand_l pivot.x 内部 %.2f → 写出 %.2f ✓；draw 末帧 limb_l position 内部 %s → 写出 %s%s ✓；'
                 'rotation.y 内部 %.2f → 写出 %.2f ✓'
                 % (ci['origin'][0], cw['origin'][0], hi, hw,
                    [round(v, 3) for v in ip], [round(v, 3) for v in wp], posnote, ir[1], wr[1]))
    return fails, notes

# ================================================================ 写出
def write_all(geo, anims):
    for sub in ('geo', 'animations', 'textures', 'textures/models'):
        os.makedirs(os.path.join(RES, sub), exist_ok=True)
    anim_doc = {'format_version': '1.8.0', 'animations': anims, 'geckolib_format_version': 2}
    geo_out = cb1.game_convention_geo(copy.deepcopy(geo))        # ← 复用 v1 的取反层
    anim_out = cb1.game_convention_anims(copy.deepcopy(anim_doc))
    geo_txt = json.dumps(geo_out, ensure_ascii=False, indent=2)
    anim_txt = json.dumps(anim_out, ensure_ascii=False, indent=2)
    paths = []
    for p in (os.path.join(ART, NAME + '.geo.json'), os.path.join(RES, 'geo', NAME + '.geo.json')):
        with open(p, 'w', encoding='utf-8') as f:
            f.write(geo_txt)
        paths.append(p)
    for p in (os.path.join(ART, NAME + '.animation.json'), os.path.join(RES, 'animations', NAME + '.animation.json')):
        with open(p, 'w', encoding='utf-8') as f:
            f.write(anim_txt)
        paths.append(p)
    for p in (os.path.join(ART, NAME + '.png'), os.path.join(RES, 'textures', 'models', NAME + '.png'),
              os.path.join(ART, NAME + '_geo.png'), os.path.join(RES, 'textures', 'models', NAME + '_geo.png')):
        cb1.write_png(p)
        paths.append(p)
    return paths

def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
    d, placement = repack()
    if placement is None:
        print('图集塞不下'); return 1
    repaint(placement)
    print('UV 装箱密度 %.0f，%d 个面' % (d, sum(len(f) for f in placement.values())), flush=True)
    geo = cb1.build_geo()
    anims = build_anims()
    paths = write_all(geo, anims)
    fails, notes, nc, nb = selfcheck(geo, anims)
    geo_written = json.load(open(os.path.join(ART, NAME + '.geo.json'), encoding='utf-8'))
    anim_written = json.load(open(os.path.join(ART, NAME + '.animation.json'), encoding='utf-8'))
    fw, swnotes = sample_written(geo_written, anim_written, geo, anims)
    fails += fw
    notes += swnotes
    print('=== crossbow v2（现代复合狩猎弩）自检 ===')
    for n in notes:
        print('  ', n)
    print('  贴图 %dx%d, %.1f KB；动画 %d 段：%s' % (
        TEX, TEX, len(cb1._PNG) / 1024.0, len(anims),
        ', '.join('%s(%.2fs%s)' % (k, v['animation_length'], ',loop' if v.get('loop') else '')
                  for k, v in anims.items())))
    print('  文件：')
    for p in paths:
        print('   ', os.path.relpath(p, cb1._BASE).replace('\\', '/'))
    if fails:
        print('未通过：')
        for f in fails:
            print('   [X]', f)
        return 1
    print('全部通过')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())