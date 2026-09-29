# -*- coding: utf-8 -*-
"""
第三人称 GeckoLib 物品的「模型空间平移常量」求解器（纯标准库）。

用途：给定一把枪的 display 块（rotation/translation/scale）与它在模型空间里的
握把靶点 grip（单位 px，16px = 1 格），解出 M1GarandItemRenderer 里那四个常量
TP_X_RIGHT / TP_X_LEFT / TP_Y / TP_Z。

=====================================================================
链条（全部逐项来自源码，应用顺序 = 从左到右，右侧最先作用到模型点）
=====================================================================

  M = M_hand · T(A) · T(t_d) · R_d · S_d · T(−0.5,−0.5,−0.5) · T(TP) · T(nudge) · M_bones

  1) M_hand = HumanoidModel.translateToHand(arm) · rotX(−90°) · rotY(180°)
       出处: net/minecraft/client/renderer/entity/layers/ItemInHandLayer.java
             renderArmWithItem(...)  (1.20.1-47.3.0)
             - translateToHand 把坐标系原点放到手臂末端（手部锚定帧）；
             - 随后 mulPose(Axis.XP, −90°)、mulPose(Axis.YP, 180°)；
             - 收尾平移 p_117111_.m_252880_(flag? -1/16 : +1/16, 0.125, -0.625)
               其中 flag = (arm == HumanoidArm.LEFT)，即 **右手 +1/16、左手 −1/16**。
               单位是「格」(blocks)：1/16 格 = 1 px。这就是注释里的 A。
  2) display 块（models/item/<gun>.json 的 thirdperson_righthand/lefthand）
       出处: net/minecraft/client/renderer/block/model/ItemTransform.java
             apply(boolean leftHand, PoseStack)：先 translate(t_d)，再
             mulPose(Quaternionf().rotationXYZ(rx,ry,rz))，最后 scale(s)。
             - t_d = display.translation × 0.0625（JSON 里是 px，apply 时按格用）；
             - leftHand=true 时 t_d.x 取反、且 ry/rz 取反（rx 不变）；
             - JOML 的 rotationXYZ(a,b,c) 合成的矩阵是 R = Rx·Ry·Rz（已用
               M1 的 [90,0,0] 数值校验，X 单轴时与顺序无关）。
       Forge 打补丁后这一行变成
             p_115151_ = ForgeHooksClient.handleCameraTransforms(...)
       出处: forge-1.20.1-47.3.0-sources.jar
             patches/net/minecraft/client/renderer/entity/ItemRenderer.java.patch
             (handleCameraTransforms 只是 model.applyTransform(ctx, pose, leftHand)，
              即仍然落到 ItemTransform.apply，语义不变。)
  3) T(−0.5,−0.5,−0.5)：块状物品模型（0..1 体积）的再居中。
       出处: 同上 patch —— 该行 `p_115147_.m_252880_(-0.5F, -0.5F, -0.5F);` 在
             自定义渲染器（BEWLR）分支之前，Forge **没有**删掉它。自定义渲染
             分支调用 IClientItemExtensions.of(stack).getCustomRenderer()
             .renderByItem(...)，即我们的 M1GarandItemRenderer.renderByItem。
  4) T(TP)：就是本渲染器 renderByItem 里的 poseStack.translate(TP_X, TP_Y, TP_Z)，
       发生在 super.renderByItem 之前，因此排在 display 的 R_d/S_d **之后**
       （后乘），向量 TP 是「模型空间、格」的量。
  5) T(nudge) = T(0.5, 0.51, 0.5)
       出处: software/bernie/geckolib/renderer/GeoItemRenderer.java preRender(...)
             `if (!isReRender) poseStack.translate(0.5f, 0.51f, 0.5f);`
             （紧接着 scaleModelForRender(scaleWidth, scaleHeight, ...)，本渲染
              器未 withScale，故 scaleWidth=scaleHeight=1，几何上无作用。）
  6) M_bones：GeckoLib 的骨骼变换，pivot/位置按 /16 转格
       出处: software/bernie/geckolib/util/RenderUtils.java prepMatrixForBone(...)

=====================================================================
配方（= 文件里注释写的那条式子，左右手只差 A 的 x 符号）
=====================================================================

  TP = S⁻¹ · Rᵀ · ( −(A + t_d) ) − nudge − grip/16

  等价于要求  R·S·(TP + nudge + grip/16) = −(A + t_d)，
  即：在 display 的旋转/缩放之后，把「握把靶点」放到蒙皮锚点 A（连同 display
  平移）的反号位置上 —— 骨骼链里 A 是最后加进来的，模型原点因此偏出拳头，
  这一步把 A 抵消、换成模型自己的握把点。

  Rᵀ = R⁻¹（正交阵转置）。M1 与 Uzi 的 display 都是 rotation=[90,0,0]、
  translation=[0,0,0]，所以 R 只有 rotX(+90°)、t_d = (0,0,0)；左右手的差别
  只剩 A.x = ±1/16，于是
        TP_X_RIGHT − TP_X_LEFT = 2·(1/16)/S
  （M1: 0.125/0.6 = 0.2083，对应 −0.597 与 −0.388，差 0.209 ✓）
  TP_Y / TP_Z 两手共用。

本脚本内置 M1 标定断言：算出的 M1 四值若与已知值差超过 0.02 就报错退出。
"""

import json
import os
import re
import sys

# ---------------------------------------------------------------- 链条常量

# ItemInHandLayer.renderArmWithItem：右手 +1/16，左手 −1/16（格）
ANCHOR_RIGHT = (1.0 / 16.0, 0.125, -0.625)
ANCHOR_LEFT = (-1.0 / 16.0, 0.125, -0.625)

# GeoItemRenderer.preRender：半格微调（格）
GECKO_NUDGE = (0.5, 0.51, 0.5)

# M1 已知常量（M1GarandItemRenderer.java 第 53-56 行），用来做标定
M1_KNOWN_RIGHT = (-0.597, 0.450, -0.335)
M1_KNOWN_LEFT = (-0.388, 0.450, -0.335)

M1_CALIBRATION_TOLERANCE = 0.02

# ------------------------------------------------- 输入一律从源码读，不许手抄
#
# 踩过的坑：本脚本最初把 Uzi 的 scale 写成 0.68、握把写成 geo 里 grip 骨的 pivot
# (0, 0.80, 1.85)，而真值分别是 uzi.json 的 0.67 与 UziGeoModel.GRIP 的
# (0.00, 0.50, 2.00) —— 解出的 TP_Y 因此偏了 0.019 格，肉眼看不出、只有对着
# 源码比才现形。手抄的表必然与源码漂移，所以这里直接解析源码文件。
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AST = 'src/main/resources/assets/apocalypse_zombies/'
MODEL_JSON = AST + 'models/item/%s.json'
GEO_MODEL_JAVA = 'src/main/java/com/apocalypse/zombies/client/model/%sGeoModel.java'

_GRIP_RE = re.compile(r'float\[\]\s+GRIP\s*=\s*\{\s*([-\d.]+)F\s*,\s*([-\d.]+)F\s*,\s*([-\d.]+)F')


def read_thirdperson_scale(item_id):
    """models/item/<id>.json 的 thirdperson_righthand.scale[0]（左右手同值，另断）。"""
    with open(os.path.join(ROOT, MODEL_JSON % item_id), encoding='utf-8') as fh:
        disp = json.load(fh)['display']
    right = disp['thirdperson_righthand']
    left = disp['thirdperson_lefthand']
    assert right['scale'] == left['scale'], '%s 左右手 scale 不同：%r vs %r' % (
        item_id, right['scale'], left['scale'])
    assert right['rotation'] == left['rotation'] == [90, 0, 0], \
        '%s 第三人称 rotation 不是 [90,0,0]：%r / %r' % (item_id, right['rotation'], left['rotation'])
    assert right['translation'] == left['translation'] == [0, 0, 0], \
        '%s 第三人称 translation 非零，闭式解多一项 t_d：%r' % (item_id, right['translation'])
    return right['scale'][0]


def read_grip(geo_model_class):
    """<Class>GeoModel.java 里 {@code float[] GRIP} 的真值（px）。

    必须用 Java 里那个——姿势系统（HandMotion）用的是它，不是 geo 里 grip 骨的 pivot。
    """
    p = os.path.join(ROOT, GEO_MODEL_JAVA % geo_model_class)
    with open(p, encoding='utf-8') as fh:
        txt = fh.read()
    m = _GRIP_RE.search(txt)
    assert m, '%s 里找不到 float[] GRIP' % p
    return tuple(float(g) for g in m.groups())

# ---------------------------------------------------------------- 线代小工具


def rot_xyz(rx, ry, rz):
    """JOML Quaternionf().rotationXYZ(rx,ry,rz) 的 3x3 旋转阵（度）。

    合成顺序 R = Rx·Ry·Rz（JOML 实现如此；本仓库两把枪都只有 rx≠0，
    所以顺序无关，这里仍然写成通用形式）。返回以行为主的 3x3 列表。
    """
    cx, sx = _cos_sin(rx)
    cy, sy = _cos_sin(ry)
    cz, sz = _cos_sin(rz)

    # Rx = [[1,0,0],[0,cx,-sx],[0,sx,cx]]
    # Ry = [[cy,0,sy],[0,1,0],[-sy,0,cy]]
    # Rz = [[cz,-sz,0],[sz,cz,0],[0,0,1]]
    rx_m = ((1.0, 0.0, 0.0), (0.0, cx, -sx), (0.0, sx, cx))
    ry_m = ((cy, 0.0, sy), (0.0, 1.0, 0.0), (-sy, 0.0, cy))
    rz_m = ((cz, -sz, 0.0), (sz, cz, 0.0), (0.0, 0.0, 1.0))
    return _mat_mul(rx_m, _mat_mul(ry_m, rz_m))


def _cos_sin(deg):
    from math import cos, radians, sin

    r = radians(deg)
    return cos(r), sin(r)


def _mat_mul(a, b):
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )


def _transpose(m):
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))


def _mat_vec(m, v):
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


# ---------------------------------------------------------------- 求解


def solve_tp(rotation, translation, scale, grip_px, anchor, verbose=False):
    """解一组 TP = (x, y, z)。

    rotation    : display block 的 rotation（度）
    translation : display block 的 translation（JSON 原始 px 值）
    scale       : display block 的 scale（标量，本仓库都是等比）
    grip_px     : 模型空间握把靶点（px）
    anchor      : ItemInHandLayer 的锚点 A（格），右手 +1/16、左手 −1/16
    """
    # ItemTransform.apply：translation 在 JSON 里是 px，×0.0625 变格
    disp_trans = tuple(t / 16.0 for t in translation)

    # 链条上 A 与 display 平移在同一个加法簇里：目标 = −(A + t_d)
    target = tuple(-(anchor[i] + disp_trans[i]) for i in range(3))

    rot = rot_xyz(*rotation)
    v = _mat_vec(_transpose(rot), target)  # Rᵀ·target
    v = tuple(c / scale for c in v)  # S⁻¹（等比缩放）
    v = tuple(
        v[i] - GECKO_NUDGE[i] - grip_px[i] / 16.0 for i in range(3)
    )  # − nudge − grip/16

    if verbose:
        print("    display.translation(px) = %s  ->  格 %s" % (translation, disp_trans))
        print("    R = rotationXYZ%s" % (rotation,))
        for row in rot:
            print("        [%9.6f %9.6f %9.6f]" % row)
        print("    −(A + t_d) = %s" % (target,))
    return v


def max_abs_diff(a, b):
    return max(abs(a[i] - b[i]) for i in range(3))


# ---------------------------------------------------------------- 两把枪的配置

M1 = dict(
    name="M1 加兰德（标定用）",
    rotation=(90.0, 0.0, 0.0),  # models/item/m1_garand.json thirdperson_*
    translation=(0.0, 0.0, 0.0),
    scale=read_thirdperson_scale('m1_garand'),
    grip_px=read_grip('M1Garand'),  # M1GarandGeoModel.GRIP
)

UZI = dict(
    name="Uzi（求解对象）",
    rotation=(90.0, 0.0, 0.0),  # uzi.json thirdperson_*
    translation=(0.0, 0.0, 0.0),
    scale=read_thirdperson_scale('uzi'),
    grip_px=read_grip('Uzi'),  # UziGeoModel.GRIP —— 不是 geo 里 grip 骨的 pivot
)


def solve_both(cfg, verbose=False):
    right = solve_tp(cfg["rotation"], cfg["translation"], cfg["scale"],
                     cfg["grip_px"], ANCHOR_RIGHT, verbose=verbose)
    left = solve_tp(cfg["rotation"], cfg["translation"], cfg["scale"],
                    cfg["grip_px"], ANCHOR_LEFT, verbose=verbose)
    return right, left


def main():
    print("=" * 72)
    print("第三人称 GeckoLib 物品：模型空间平移常量 T = S⁻¹Rᵀ(−(A+t_d)) − nudge − grip/16")
    print("=" * 72)

    # ---------------- 第 1 步：M1 标定 ----------------
    print()
    print("[1] M1 加兰德标定（必须先复现已知值，容差 %.2f）" % M1_CALIBRATION_TOLERANCE)
    print("    display: rotation=%s translation=%s scale=%s"
          % (M1["rotation"], M1["translation"], M1["scale"]))
    print("    GRIP(px) = %s -> 格 %s" % (M1["grip_px"],
                                          tuple(p / 16.0 for p in M1["grip_px"])))
    m1_right, m1_left = solve_both(M1, verbose=True)

    def show(tag, got, known):
        err = max_abs_diff(got, known)
        print("    %s 计算 = (%8.4f, %8.4f, %8.4f)" % ((tag,) + tuple(got)))
        print("    %s 已知 = (%8.4f, %8.4f, %8.4f)   最大误差 = %.5f"
              % ((tag,) + tuple(known) + (err,)))
        return err

    err_r = show("右", m1_right, M1_KNOWN_RIGHT)
    err_l = show("左", m1_left, M1_KNOWN_LEFT)
    max_err = max(err_r, err_l)
    print("    -> M1 标定最大误差 = %.5f" % max_err)

    if max_err > M1_CALIBRATION_TOLERANCE:
        print()
        print("!!! 标定失败：链条没能复现 M1 的已知常量（误差 %.5f > %.2f）。"
              % (max_err, M1_CALIBRATION_TOLERANCE))
        print("!!! 说明链条还没查对，拒绝输出 Uzi 的数字。")
        return 1

    print("    -> 标定通过（误差 ≪ 0.02），链条可用于求解新枪。")

    # ---------------- 第 2 步：解 Uzi ----------------
    print()
    print("[2] Uzi 求解")
    print("    display: rotation=%s translation=%s scale=%s"
          % (UZI["rotation"], UZI["translation"], UZI["scale"]))
    print("    GRIP(px) = %s -> 格 %s" % (UZI["grip_px"],
                                          tuple(p / 16.0 for p in UZI["grip_px"])))
    uzi_right, uzi_left = solve_both(UZI, verbose=True)

    tp_y = 0.5 * (uzi_right[1] + uzi_left[1])
    tp_z = 0.5 * (uzi_right[2] + uzi_left[2])

    print()
    print("    ---- Uzi 常量（写进 UziItemRenderer，与 M1 同款写法）----")
    print("    private static final float TP_X_RIGHT = %.3fF;" % uzi_right[0])
    print("    private static final float TP_X_LEFT  = %.3fF;" % uzi_left[0])
    print("    private static final float TP_Y       = %.3fF;" % tp_y)
    print("    private static final float TP_Z       = %.3fF;" % tp_z)
    print()
    print("    TP_X_RIGHT = %.6f" % uzi_right[0])
    print("    TP_X_LEFT  = %.6f" % uzi_left[0])
    print("    TP_Y       = %.6f   (左右一致，验算 %.2e)" % (tp_y, abs(uzi_right[1] - uzi_left[1])))
    print("    TP_Z       = %.6f   (左右一致，验算 %.2e)" % (tp_z, abs(uzi_right[2] - uzi_left[2])))
    print()
    print("    自检: TP_X_RIGHT − TP_X_LEFT = %.6f，理论值 2·(1/16)/S = %.6f"
          % (uzi_right[0] - uzi_left[0], 2.0 * (1.0 / 16.0) / UZI["scale"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
