# -*- coding: utf-8 -*-
"""win94 几何生成器 —— 按 tools/win94/spec.py 的真枪基准出方块表。

输出（build/win94/）：
  groups.json         骨骼表（add_groups）
  cubes_<bone>.json   分批方块表（add_cubes，含逐面 UV）
  uvmap.json          逐面 UV 矩形 + 材质（给贴图脚本）

自带三项自检/自愈（项目惯例"生成器末尾自带自检"）：
  1) UV 货架打包 —— 逐面 UV 写进 cubes 的 faces 字段（密度 24 px/u），消灭 zero_uv；
  2) 共面自愈 —— 未旋转方块两两共面时把后者沿该轴外移 NUDGE，避免 z-fighting；
  3) 环段保护 —— 杠杆环 / 护圈 / 卡箍的段不许被共面自愈挪动（挪了环就裂口）。

用法：python tools/win94/model.py
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import spec as S  # noqa: E402

OUT = ROOT / 'build' / 'win94'
CUBES = []


def add(name, bone, frm, to, rot=None, origin=None, mat_faces=None):
    a = [min(frm[i], to[i]) for i in range(3)]
    b = [max(frm[i], to[i]) for i in range(3)]
    CUBES.append({
        'name': name, 'parent': bone,
        'from': [round(v, 4) for v in a], 'to': [round(v, 4) for v in b],
        'rotation': [round(v, 3) for v in (rot or (0, 0, 0))],
        'origin': [round(v, 4) for v in (origin if origin else a)],
        'mat': mat_of(name),
        'mat_faces': dict(mat_faces or {}),
    })


def mat_of(name):
    n = name
    if n.startswith(('stock_', 'forearm', 'forend')):
        return 'walnut'
    if n.startswith('buttplate') or n.startswith('sling') or n.startswith('screw'):
        return 'steel'
    if n.startswith('cartridge_bullet'):
        return 'copper'
    if n.startswith('cartridge'):
        return 'brass'
    if n.startswith('shell'):
        return 'brass_dark'
    if n.startswith(('bolt', 'carrier')):
        return 'steel'
    if n.startswith('scope_obj') or n.startswith('scope_eye'):
        return 'blued_dark'
    if n.startswith('scope'):
        return 'blued_dark'
    return 'blued'          # 枪管 / 机匣 / 杠杆 / 护圈 / 扳机 / 击锤 / 卡箍


def tube(name, bone, z0, z1, segs, R_out, R_in, cx=0.0, cy=0.0, overlap=1.08,
         cap_face=None, cap_mat='lens'):
    """沿 Z 轴的 n 棱管：每面一块、绕自身中心旋转 —— 真枪枪管/管仓/镜管必须是圆的。"""
    half_w = R_out * math.sin(math.pi / segs) * overlap
    t = R_out - R_in
    r_mid = (R_out + R_in) / 2.0
    for k in range(segs):
        theta = math.pi / segs + 2 * math.pi * k / segs
        px = cx + r_mid * math.cos(theta)
        py = cy + r_mid * math.sin(theta)
        add(f'{name}_{k}', bone,
            [px - half_w, py - t / 2.0, z0],
            [px + half_w, py + t / 2.0, z1],
            rot=[0, 0, math.degrees(theta)],
            origin=[px, py, (z0 + z1) / 2.0],
            mat_faces={cap_face: cap_mat} if cap_face else None)


def ring_yz(name, bone, cy, cz, rz, ry, thick, half_w, n=16):
    """环面在 YZ 平面（环绕 X 轴）的**连贯椭圆环**：杠杆环、扳机护圈用。

    把椭圆按角度切成 n 段，每段是一根沿弦方向的直条，长度按弦长再放 10% 与邻段搭接
    —— 相邻段端点必然重叠，整圈看不到缝。（若用 n 个轴对齐方块各绕自身中心转一个角度，
    块边长短于弧长，环上会出现明显的缝，看起来像断开成两个环。）
    """
    pts = []
    for k in range(n):
        th = 2 * math.pi * k / n
        pts.append((cz + rz * math.cos(th), cy + ry * math.sin(th)))
    for k in range(n):
        z0, y0 = pts[k]
        z1, y1 = pts[(k + 1) % n]
        dz, dy = z1 - z0, y1 - y0
        ln = math.hypot(dy, dz) * 1.10
        mz, my = (z0 + z1) / 2.0, (y0 + y1) / 2.0
        add(f'{name}_{k}', bone,
            [-half_w, my - thick / 2.0, mz - ln / 2.0],
            [half_w, my + thick / 2.0, mz + ln / 2.0],
            rot=[math.degrees(math.atan2(-dy, dz)), 0, 0], origin=[0, my, mz])


def ring_xy(name, bone, cz, cy, rx, ry, thick, half_w, n=12):
    """环面在 XY 平面（环绕枪身轴线）的**连贯环**：枪管/护木卡箍（barrel band）用。"""
    pts = []
    for k in range(n):
        th = 2 * math.pi * k / n
        pts.append((rx * math.cos(th), cy + ry * math.sin(th)))
    for k in range(n):
        x0, y0 = pts[k]
        x1, y1 = pts[(k + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        ln = math.hypot(dx, dy) * 1.10
        mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        add(f'{name}_{k}', bone,
            [mx - ln / 2.0, my - thick / 2.0, cz - half_w],
            [mx + ln / 2.0, my + thick / 2.0, cz + half_w],
            rot=[0, 0, math.degrees(math.atan2(dy, dx))], origin=[mx, my, cz])


# ============================================================= 1. 枪管组
BZ0, BZ1 = -10.60, -2.60                 # 外露枪管 8.0 u = 500 mm（真枪 24 in）
_seg = (BZ1 - BZ0) / 4.0
for i in range(4):
    tube(f'barrel_tube{i}', 'barrel', BZ0 + i * _seg, BZ0 + (i + 1) * _seg,
         segs=8, R_out=0.165, R_in=0.075)
add('muzzle_crown', 'barrel', [-0.175, -0.175, -10.72], [0.175, 0.175, -10.58])
add('muzzle_bore', 'barrel', [-0.075, -0.075, -10.74], [0.075, 0.075, -10.62])
add('front_sight_base', 'barrel', [-0.10, 0.145, -10.52], [0.10, 0.235, -10.20])
add('front_sight_blade', 'barrel', [-0.028, 0.225, -10.48], [0.028, 0.40, -10.34])
# 照门（buckhorn rear sight）：真枪在枪管后段、机匣前方
add('rear_sight_base', 'barrel', [-0.13, 0.16, -3.90], [0.13, 0.24, -3.44])
add('rear_sight_leaf', 'barrel', [-0.115, 0.23, -3.86], [0.115, 0.40, -3.72])
add('rear_sight_notch', 'barrel', [-0.03, 0.38, -3.84], [0.03, 0.44, -3.74])

# 管状弹仓（枪管正下方，容量 5 发）
_ms = (BZ1 - (BZ0 + 1.0)) / 3.0
for i in range(3):
    z0 = BZ0 + 1.0 + i * _ms
    tube(f'mag_tube{i}', 'barrel', z0, z0 + _ms, segs=6, R_out=0.12, R_in=0.045, cy=S.MAG_CY)
add('mag_end_cap', 'barrel', [-0.145, S.MAG_CY - 0.145, -10.22], [0.145, S.MAG_CY + 0.145, -10.02])
add('mag_plug', 'barrel', [-0.135, S.MAG_CY - 0.135, -10.04], [0.135, S.MAG_CY + 0.135, -9.88])
# 卡箍：闭合钢环，箍住枪管与管仓（真枪前箍在护木前端、后箍在护木后端）
ring_xy('band_front', 'barrel', -5.20, -0.225, 0.264, 0.395, 0.055, 0.14, n=12)
ring_xy('band_rear', 'barrel', -3.24, -0.256, 0.256, 0.421, 0.05, 0.13, n=12)
add('sling_stud_front', 'barrel', [-0.045, S.MAG_CY - 0.20, -9.30], [0.045, S.MAG_CY - 0.10, -9.00])
add('sling_swivel_front', 'barrel', [-0.035, S.MAG_CY - 0.30, -9.24], [0.035, S.MAG_CY - 0.19, -9.06])

# ============================================================= 2. 护木
add('forearm_tip', 'forearm', [-0.235, -0.60, -6.30], [0.235, -0.185, -5.42])
add('forearm_mid', 'forearm', [-0.245, -0.62, -5.44], [0.245, -0.180, -4.52])
add('forearm_rear', 'forearm', [-0.252, -0.66, -4.54], [0.252, -0.178, -3.64])
add('forearm_breech', 'forearm', [-0.258, -0.72, -3.66], [0.258, -0.172, -2.62])
add('forend_check_negx', 'forearm', [-0.264, -0.44, -4.40], [-0.250, -0.24, -3.10])
add('forend_check_posx', 'forearm', [0.250, -0.44, -4.40], [0.264, -0.24, -3.10])
add('forearm_cap', 'forearm', [-0.243, -0.61, -6.42], [0.243, -0.19, -6.28])

# ============================================================= 3. 机匣
RX, RT, RB = S.RECEIVER_X, S.RY_TOP, S.RY_BOT
RZF, RZB = S.RZ_F, S.RZ_B
PZ0, PZ1 = S.PORT_Z0, S.PORT_Z1          # 右壁开口（装填门 + 抛壳口所在）
add('receiver_top', 'receiver', [-RX, 0.06, RZF], [RX, RT, RZB])
add('receiver_upper_negx', 'receiver', [-RX, 0.06, RZF], [-RX + 0.05, RT, RZB])
add('receiver_wall_negx', 'receiver', [-RX, RB, RZF], [-RX + 0.05, 0.06, RZB])
# 右壁：上部中间是抛壳口（分前后两段），下部在装填门的位置挖一个凹槽，
# 装填门（gate 骨）嵌在槽里 —— 真枪这块弹簧钢片就装在机匣右壁的开口中。
add('receiver_upper_posx', 'receiver', [RX - 0.05, 0.07, RZF], [RX, RT, PZ0])
add('receiver_upper_posx_aft', 'receiver', [RX - 0.05, 0.07, PZ1], [RX, RT, RZB])
add('receiver_lower_posx_fwd', 'receiver', [RX - 0.05, RB, RZF], [RX, 0.07, S.GATE_Z0])
add('receiver_lower_posx_aft', 'receiver', [RX - 0.05, RB, S.GATE_Z1], [RX, 0.07, RZB])
add('receiver_lower_posx_gate', 'receiver', [RX - 0.05, RB, S.GATE_Z0],
    [RX - 0.025, 0.07, S.GATE_Z1])
add('port_liner', 'receiver', [RX - 0.055, -0.10, PZ0 - 0.02], [RX - 0.02, 0.06, PZ1 + 0.02])
add('receiver_floor', 'receiver', [-RX, RB, RZF], [RX, RB + 0.08, 0.06])
add('receiver_floor_rear', 'receiver', [-RX + 0.01, RB - 0.07, 0.04], [RX - 0.01, RB + 0.02, RZB])
add('receiver_front_ring', 'receiver', [-RX + 0.02, RB, -2.72], [RX - 0.02, RT, RZF + 0.02])
add('receiver_front_bridge', 'receiver', [-RX + 0.01, -0.50, -2.58], [RX - 0.01, 0.14, -2.44])
add('receiver_rear_block', 'receiver', [-RX + 0.02, -0.46, 0.30], [RX - 0.02, 0.05, 0.40])
add('receiver_tang_top', 'receiver', [-0.175, -0.50, 0.36], [0.175, 0.13, 0.78])
add('receiver_tang_bottom', 'receiver', [-0.215, -0.84, 0.28], [0.215, -0.73, 0.56])
add('side_plate_negx', 'receiver', [-RX - 0.022, -0.40, -2.10], [-RX - 0.004, 0.06, -1.30])
add('side_plate_posx', 'receiver', [RX + 0.004, -0.42, -2.14], [RX + 0.022, 0.06, -1.34])
for i, (yy, zz) in enumerate([(-0.86, -0.34), (-0.30, -0.06), (-0.06, -2.26)]):
    add(f'screw_negx{i}', 'receiver', [-RX - 0.022, yy, zz], [-RX - 0.004, yy + 0.13, zz + 0.13])
    add(f'screw_posx{i}', 'receiver', [RX + 0.004, yy, zz], [RX + 0.022, yy + 0.13, zz + 0.13])

# ---- 扳机护圈（trigger guard）：机匣的一部分，**固定不动**，包住扳机 ----
# 真枪量测：中心 (y −1.22, z −0.12)，半轴 (z 0.46, y 0.27)，管厚 0.09 → 外径 58 × 34 mm。
ring_yz('guard_loop', 'receiver', S.GUARD_CY, S.GUARD_CZ, S.GUARD_RZ, S.GUARD_RY,
        S.GUARD_THICK, 0.065, n=16)
# 护圈不是悬空的小环：真枪上它是机匣底向后延伸的**扳机座（trigger plate）**的一部分，
# 上缘与机匣底连成一条金属带（早先只放两块小连接块，侧面看护圈像浮在机匣下面）。
add('guard_strap', 'receiver', [-0.09, -0.99, S.GUARD_CZ - S.GUARD_RZ - 0.11],
    [0.09, -0.72, S.GUARD_CZ + S.GUARD_RZ + 0.07])
add('guard_mount_fwd', 'receiver', [-0.072, -0.94, S.GUARD_CZ - S.GUARD_RZ - 0.05],
    [0.072, -0.76, S.GUARD_CZ - S.GUARD_RZ + 0.12])
add('guard_mount_aft', 'receiver', [-0.072, -0.94, S.GUARD_CZ + S.GUARD_RZ - 0.12],
    [0.072, -0.76, S.GUARD_CZ + S.GUARD_RZ + 0.05])
# 下尾板（lower tang）：机匣底向后延伸到枪托腕部的金属，护圈后端与它相接
add('lower_tang', 'receiver', [-0.10, -0.88, S.GUARD_CZ + S.GUARD_RZ - 0.02],
    [0.10, -0.70, 1.30])

# ============================================================= 4. 闭锁块
add('bolt_body_a', 'bolt', [-0.245, -0.30, -2.06], [0.245, 0.05, -1.36])
add('bolt_body_b', 'bolt', [-0.24, -0.295, -1.38], [0.24, 0.045, -0.62])
add('bolt_face', 'bolt', [-0.225, -0.28, -2.14], [0.225, 0.035, -2.04])
add('extractor_claw', 'bolt', [0.20, 0.01, -2.10], [0.265, 0.09, -1.92])
add('ejector_spring', 'bolt', [-0.10, -0.26, -1.90], [0.10, -0.20, -1.30])

# ============================================================= 5. 击锤
add('hammer_body', 'hammer', [-0.075, -0.12, 0.14], [0.075, 0.30, 0.34])
add('hammer_spur', 'hammer', [-0.085, 0.26, 0.08], [0.085, 0.40, 0.28])
add('hammer_half_cock', 'hammer', [-0.05, 0.02, 0.32], [0.05, 0.12, 0.40])

# ============================================================= 6. 杠杆（lever）
# 真枪：转轴在机匣前下方 (y −0.95, z −2.30)；一根杆贴机匣底向后，末端弯成**杠杆环**。
# 环中心 (y −1.85, z +0.92)、半轴 (z 0.84, y 0.32)、管厚 0.11 → 外径 105 × 40 mm。
add('lever_pin', 'lever', [-0.062, S.LEVER_PIVOT_Y - 0.09, S.LEVER_PIVOT_Z - 0.14],
    [0.062, S.LEVER_PIVOT_Y + 0.05, S.LEVER_PIVOT_Z + 0.14])
add('lever_pin_screw_negx', 'lever', [-0.076, S.LEVER_PIVOT_Y - 0.07, S.LEVER_PIVOT_Z - 0.045],
    [-0.060, S.LEVER_PIVOT_Y - 0.015, S.LEVER_PIVOT_Z + 0.045])
add('lever_pin_screw_posx', 'lever', [0.060, S.LEVER_PIVOT_Y - 0.07, S.LEVER_PIVOT_Z - 0.045],
    [0.076, S.LEVER_PIVOT_Y - 0.015, S.LEVER_PIVOT_Z + 0.045])

# 杆：从转轴到环的**一根直钢条** —— 真枪 lever 是从机匣前下方一路斜到握把下方的，
# 中途从**扳机护圈下方**穿过。3 段共用同一条中心线并各自绕 X 轴倾斜 θ：
# 早先做成 6 个不旋转的方块逐格下降，侧面看是"楼梯"；再加前段水平，杆会从护圈孔里穿过去。
# ⚠ 终点必须**正好落在环的前端点**上（椭圆 z 最小的那个点 = (LOOP_CZ − LOOP_RZ, LOOP_CY)）：
#   早先把终点放在环前上方再用一块"肩"去补，实测杆末端离环前端 0.263 u ≈ 16 mm，
#   在 Blockbench 里一眼就看得出杆和环是分开的两件东西。
ARM_Z0, ARM_Y0 = -2.34, -0.94
ARM_Z1 = S.LOOP_CZ - S.LOOP_RZ                 # 0.08：环的前端点
ARM_Y1 = S.LOOP_CY                             # −1.85
_arm_slope = (ARM_Y1 - ARM_Y0) / (ARM_Z1 - ARM_Z0)
_arm_theta = math.degrees(math.atan2(-_arm_slope, 1.0))      # 绕 X 正角度 ⇒ 后端（+z）向下
for i in range(3):
    za = ARM_Z0 + (ARM_Z1 - ARM_Z0) * i / 3.0
    zb = ARM_Z0 + (ARM_Z1 - ARM_Z0) * (i + 1) / 3.0
    zc = (za + zb) / 2.0
    yc = ARM_Y0 + _arm_slope * (zc - ARM_Z0)
    half = (zb - za) / 2.0 * 1.06                            # 端部搭接 6%，接缝看不见
    add(f'lever_arm_{i}', 'lever', [-0.075, yc - 0.07, zc - half],
        [0.075, yc + 0.07, zc + half], rot=[_arm_theta, 0, 0], origin=[0, yc, zc])
ring_yz('lever_loop', 'lever', S.LOOP_CY, S.LOOP_CZ, S.LOOP_RZ, S.LOOP_RY,
        S.LOOP_THICK, 0.075, n=20)

# ============================================================= 7. 升降器（carrier）
add('carrier_plate', 'carrier', [-0.19, -0.66, -1.64], [0.19, -0.44, -1.08])
add('carrier_lifter', 'carrier', [-0.075, -0.66, -1.10], [0.075, -0.32, -0.80])

# ============================================================= 8. 待发弹（cartridge）
CZ0, CZ1 = -1.62, -0.66
add('cartridge_case_a', 'cartridge', [-0.095, -0.095, CZ0 + 0.04], [0.095, 0.095, CZ0 + 0.50])
add('cartridge_case_b', 'cartridge', [-0.093, -0.093, CZ0 + 0.52], [0.093, 0.093, CZ1])
add('cartridge_rim', 'cartridge', [-0.107, -0.107, CZ1], [0.107, 0.107, CZ1 + 0.05])
add('cartridge_bullet_a', 'cartridge', [-0.062, -0.062, CZ0 - 0.30], [0.062, 0.062, CZ0 + 0.06])
add('cartridge_bullet_b', 'cartridge', [-0.038, -0.038, CZ0 - 0.48], [0.038, 0.038, CZ0 - 0.24])

# ============================================================= 9. 空壳（spent_shell）
add('shell_body_a', 'spent_shell', [-0.095, -0.095, -1.10], [0.095, 0.095, -0.68])
add('shell_body_b', 'spent_shell', [-0.093, -0.093, -0.70], [0.093, 0.093, -0.42])
add('shell_rim', 'spent_shell', [-0.107, -0.107, -0.44], [0.107, 0.107, -0.38])

# ============================================================= 10. 扳机
# 真枪量测：扳机在护圈内偏后（z ≈ +0.06），从机匣底垂到 y ≈ −1.36，刀片下端略向前弯。
add('trigger_blade_top', 'trigger', [-0.048, -1.02, -0.04], [0.048, -0.80, 0.08])
add('trigger_blade_mid', 'trigger', [-0.044, -1.22, -0.09], [0.044, -1.00, 0.03])
add('trigger_blade_tip', 'trigger', [-0.040, -1.38, -0.15], [0.040, -1.20, -0.05])
add('trigger_sear', 'trigger', [-0.035, -0.88, -0.02], [0.035, -0.74, 0.14])

# ============================================================= 11. 装填门（loading gate）
# 真枪：机匣右壁的一块**弹簧钢片**，逐发压弹时被子弹向里顶开、弹进仓后回位。
# x 跨过机匣壁（0.29）但不与壁面共面：面在 0.268 / 0.312。
add('loading_gate', 'gate', [RX - 0.022, -0.64, S.GATE_Z0 + 0.02],
    [RX + 0.022, -0.30, S.GATE_Z1 - 0.02])
add('loading_gate_lip', 'gate', [RX - 0.024, -0.66, S.GATE_Z0 - 0.05],
    [RX + 0.012, -0.58, S.GATE_Z0 + 0.20])
add('gate_spring', 'gate', [RX - 0.024, -0.60, S.GATE_Z1 - 0.06],
    [RX + 0.008, -0.44, S.GATE_Z1 + 0.10])

# ============================================================= 12. 倍镜
# 真枪 M1894 顶抛壳 ⇒ 镜子必须架够高：本模型镜管中心高于 bore 0.80 u = 50 mm，
# 镜管底（0.595）与机匣顶（0.16）之间留 0.435 u ≈ 27 mm 抛壳净空。
SCY = S.SCOPE_CY
SZ0, SZ1 = S.SCOPE_Z0, S.SCOPE_Z1
tube('scope_tube', 'scope', SZ0, SZ1, segs=6, R_out=S.SCOPE_R, R_in=0.10, cy=SCY)
tube('scope_obj', 'scope', SZ0 - 0.34, SZ0, segs=8, R_out=0.335, R_in=0.24, cy=SCY,
     cap_face='north', cap_mat='lens')
tube('scope_eye', 'scope', SZ1, SZ1 + 0.30, segs=8, R_out=0.275, R_in=0.20, cy=SCY,
     cap_face='south', cap_mat='lens')
add('scope_obj_rim', 'scope', [-0.345, SCY - 0.345, SZ0 - 0.40], [0.345, SCY + 0.345, SZ0 - 0.32])
add('scope_eye_ring', 'scope', [-0.285, SCY - 0.285, SZ1 + 0.28], [0.285, SCY + 0.285, SZ1 + 0.36])
add('scope_turret_top', 'scope', [-0.075, SCY + 0.19, -3.66], [0.075, SCY + 0.35, -3.36])
add('scope_turret_cap', 'scope', [-0.09, SCY + 0.33, -3.70], [0.09, SCY + 0.39, -3.32])
add('scope_turret_side', 'scope', [0.19, SCY - 0.075, -3.60], [0.36, SCY + 0.075, -3.30])
add('scope_turret_side_cap', 'scope', [0.34, SCY - 0.09, -3.64], [0.40, SCY + 0.09, -3.26])
add('scope_ring_front', 'scope', [-0.245, SCY - 0.245, -6.06], [0.245, SCY + 0.245, -5.76])
add('scope_ring_rear', 'scope', [-0.235, SCY - 0.235, -1.26], [0.235, SCY + 0.235, -0.96])
# 高镜座：从机匣顶（0.16）顶到卡环底（SCY − 0.245 = 0.555）
add('mount_front', 'scope', [-0.13, 0.13, -6.04], [0.13, SCY - 0.235, -5.78])
add('mount_rear', 'scope', [-0.13, 0.13, -1.24], [0.13, SCY - 0.225, -0.98])
add('mount_base_rail', 'scope', [-0.15, 0.15, -6.10], [0.15, 0.20, -0.92])

# ============================================================= 13. 枪托
_hx0, _hx1 = 0.275, 0.330
_yt0, _yt1 = -0.42, -0.98
_yb0, _yb1 = -1.20, -3.12
_sz0, _sz1 = 0.42, 6.70
# 24 段：腕部（前 1/4）曲率变化最快，段数少了侧面会看出"阶梯"（用户反馈过枪托像一摞板子）。
# 用 smoothstep 而不是线性插值：腕部一段较直的握把区，向后才加快变宽变深。
NSEG = 24


def _ease(t):
    return t * t * (3 - 2 * t)


for i in range(NSEG):
    ta, tb = i / NSEG, (i + 1) / NSEG
    za = _sz0 + (_sz1 - _sz0) * ta - (0.05 if i else 0.0)
    zb = _sz0 + (_sz1 - _sz0) * tb
    mid = _ease((ta + tb) / 2)
    hx = _hx0 + (_hx1 - _hx0) * mid
    yt = _yt0 + (_yt1 - _yt0) * mid
    yb = _yb0 + (_yb1 - _yb0) * mid
    add(f'stock_seg{i}', 'stock', [-hx, yb, za], [hx, yt, zb])
add('buttplate', 'stock', [-0.335, -3.20, 6.66], [0.335, -1.00, 6.90])
add('buttplate_heel', 'stock', [-0.32, -1.16, 6.88], [0.32, -0.98, 7.04])
add('buttplate_toe', 'stock', [-0.34, -3.32, 6.88], [0.34, -2.98, 7.06])
add('stock_latch', 'stock', [-0.06, -2.72, 6.82], [0.06, -2.56, 7.00])
add('sling_swivel_rear', 'stock', [-0.035, -2.06, 4.60], [0.035, -1.90, 4.90])


# ============================================================= 共面自愈
def is_rotated(c):
    return any(abs(v) > 0.001 for v in c['rotation'])


def is_ring_seg(name):
    """环段（杠杆环 / 护圈 / 卡箍）不许被共面自愈挪动：环上总有一两段角度恰好 0°/180°，
    会被当成"未旋转方块"挪走，一挪就把整圈搭接量吃掉，环上出现明显的缝。"""
    return name.startswith(('lever_loop', 'guard_loop', 'band_front', 'band_rear'))


def heal_coplanar(cubes, rounds=4):
    """**真重叠**的共面才推：两未旋转方块在同一轴上区间有重叠、又共享一个平面时，
    它们的面同向重合 → z-fighting。只是"相接"（区间不重叠、只共一个平面）不推。"""
    movers = [c for c in cubes if not is_rotated(c) and not is_ring_seg(c['name'])]
    total = 0
    for _ in range(rounds):
        fixed = 0
        for i in range(len(movers)):
            a = movers[i]
            for j in range(i + 1, len(movers)):
                b = movers[j]
                for ax in range(3):
                    o1, o2 = [k for k in range(3) if k != ax]
                    if (min(a['to'][o1], b['to'][o1]) - max(a['from'][o1], b['from'][o1])) <= 0.1:
                        continue
                    if (min(a['to'][o2], b['to'][o2]) - max(a['from'][o2], b['from'][o2])) <= 0.1:
                        continue
                    if min(a['to'][ax], b['to'][ax]) - max(a['from'][ax], b['from'][ax]) <= 0.0:
                        continue
                    hit = False
                    for pa in (a['from'][ax], a['to'][ax]):
                        for pb in (b['from'][ax], b['to'][ax]):
                            if abs(pa - pb) >= 0.02:
                                continue
                            if abs(b['from'][ax] - pa) < abs(b['to'][ax] - pa):
                                b['from'][ax] = round(b['from'][ax] - S.NUDGE, 4)
                            else:
                                b['to'][ax] = round(b['to'][ax] + S.NUDGE, 4)
                            fixed += 1
                            hit = True
                            break
                        if hit:
                            break
        total += fixed
        if not fixed:
            break
    return total


# ============================================================= UV 货架
FACE_AXES = {
    'north': (0, 1), 'south': (0, 1),   # 宽 X / 高 Y
    'east': (2, 1), 'west': (2, 1),     # 宽 Z / 高 Y
    'up': (0, 2), 'down': (0, 2),       # 宽 X / 高 Z
}


def pack_uv(cubes):
    items = []
    for ci, c in enumerate(cubes):
        size = [c['to'][k] - c['from'][k] for k in range(3)]
        for face, (wa, ha) in FACE_AXES.items():
            w = max(3, int(round(size[wa] * S.UV_DENSITY)))
            h = max(3, int(round(size[ha] * S.UV_DENSITY)))
            items.append({'ci': ci, 'face': face, 'w': w, 'h': h})
    items.sort(key=lambda it: (-it['h'], -it['w']))
    x = y = row_h = 0
    for it in items:
        if x + it['w'] > S.TEX_W:
            x, y, row_h = 0, y + row_h + S.UV_PAD, 0
        it['uv'] = [x, y, x + it['w'], y + it['h']]
        x += it['w'] + S.UV_PAD
        row_h = max(row_h, it['h'])
    used_h = y + row_h
    for it in items:
        c = cubes[it['ci']]
        c.setdefault('faces', {})[it['face']] = {'uv': it['uv'], 'rotation': 0, 'texture': 'win94'}
        c['autouv'] = 0          # 必须显式关自动 UV，否则 Blockbench 会重算、丢弃 faces.uv
        c['box_uv'] = False
    return used_h, items


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    healed = heal_coplanar(CUBES)
    used_h, items = pack_uv(CUBES)

    groups = [{'name': n, 'origin': o, **({'parent': p} if p else {})}
              for n, p, o in S.GROUPS]
    (OUT / 'groups.json').write_text(
        json.dumps({'groups': groups}, ensure_ascii=False, indent=1), encoding='utf-8')

    by_bone = {}
    for c in CUBES:
        by_bone.setdefault(c['parent'], []).append(c)
    for bone, lst in by_bone.items():
        payload = {'cubes': [{k: v for k, v in c.items() if k not in ('mat', 'mat_faces')}
                             for c in lst]}
        (OUT / f'cubes_{bone}.json').write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding='utf-8')

    uvmap = []
    for it in items:
        c = CUBES[it['ci']]
        wa, ha = FACE_AXES[it['face']]
        uvmap.append({
            'cube': c['name'], 'bone': c['parent'],
            'mat': c.get('mat_faces', {}).get(it['face'], c['mat']),
            'face': it['face'], 'uv': it['uv'],
            # 沿 uv-u 轴 / v 轴的**模型坐标跨度**：木纹要按模型坐标画才跨段连续
            # （枪托是 16 段拼的，逐段独立随机纹会在侧面上显出"栅栏"竖纹）。
            'span_u': [c['from'][wa], c['to'][wa]],
            'span_v': [c['from'][ha], c['to'][ha]],
        })
    (OUT / 'uvmap.json').write_text(
        json.dumps({'density': S.UV_DENSITY, 'texture': [S.TEX_W, S.TEX_H], 'faces': uvmap},
                   ensure_ascii=False, indent=1), encoding='utf-8')

    print(f'cubes total = {len(CUBES)}   coplanar healed = {healed}   uv used = {used_h}/{S.TEX_H}')
    for n, _, _ in S.GROUPS:
        if n in by_bone:
            print(f'  {n:14s} {len(by_bone[n]):3d}')
    xs = [c['from'][0] for c in CUBES] + [c['to'][0] for c in CUBES]
    ys = [c['from'][1] for c in CUBES] + [c['to'][1] for c in CUBES]
    zs = [c['from'][2] for c in CUBES] + [c['to'][2] for c in CUBES]
    print(f'bounds: x [{min(xs):.2f},{max(xs):.2f}] y [{min(ys):.2f},{max(ys):.2f}] '
          f'z [{min(zs):.2f},{max(zs):.2f}]')
    print(f'OAL = {max(zs) - min(zs):.2f} u = {(max(zs) - min(zs)) * S.U_MM:.0f} mm')
    return 0


if __name__ == '__main__':
    sys.exit(main())
