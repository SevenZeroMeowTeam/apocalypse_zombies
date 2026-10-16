# -*- coding: utf-8 -*-
"""win94（温彻斯特 M1894 杠杆步枪）几何生成器 v3 —— 按真枪文献基准出方块表。

坐标约定（与项目一致，见 docs/wiki/05-武器制作流程.md 步骤 0 铁律）：
  16 u = 1 方块；1 u = 62.5 mm；枪口 −Z、上 +Y、+X = 射手右侧；原点 = 机匣中心（bore 轴线 y=0）。

真枪基准（Winchester Model 1894 Rifle，24" 枪管）：
  全长 43.6 in ≈ 1108 mm = 17.72 u（枪口 z=−10.74 → 托底 z=+6.98）
  枪管外露 24 in = 610 mm（八棱管，Ø 0.33 u = 20.6 mm）
  机匣长 3.02 u = 189 mm / 宽 0.58 u = 36 mm（真枪 1.4 in）
  管仓在枪管正下方 Ø 0.24 u = 15 mm，容量 5 发（六棱管）
  护木 230 mm 长、32 mm 宽（真枪 1.3 in）；枪托 LOP 13 in = 330 mm
  托底 drop：heel 75 mm / toe 194 mm；托底板高 124 mm（真枪 4.8 in）
  杠杆圈最低点 bore 下 ≈ 2.0 u；瞄准镜 1" 管 Ø 0.41 u，物镜 Ø 42 mm，镜长 391 mm

本脚本自带三项自检/自愈（对应项目"生成器末尾自带自检"的惯例）：
  1) UV 货架打包 —— 逐面 UV 写进 cubes 的 faces 字段（密度 12 px/u），避免 zero_uv；
  2) 共面自愈 —— 未旋转方块两两共面时把后者沿该轴外移 0.03，避免 z-fighting；
  3) 左右命名去方位词 —— BlockbenchMCP 的 side 阈值是 0.35 u（为角色模型设计），
     对 0.8 u 宽的枪械会把所有机匣件判成"中线"，故对称件用 negx/posx 命名。

输出：
  build/bbmcp/win94_groups.json        骨骼表（add_groups）
  build/bbmcp/win94_cubes_<bone>.json  分批方块表（add_cubes，含 faces UV）
  build/bbmcp/win94_uvmap.json         逐面 UV 矩形 + 材质（给贴图绘制脚本）
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'build', 'bbmcp')

TEX_W = TEX_H = 512
UV_DENSITY = 24.0        # px per model unit（枪械件很薄，密度低了 0.05 u 的面只有 2 px 会漏色）
UV_PAD = 2
NUDGE = 0.03             # 共面自愈的偏移量

# 杠杆转轴：机匣**前下方**（弹仓口下方）。真枪 lever 是一根从这儿向后延伸的长杆，
# 末端弯成兼作扳机护圈的环 —— 所以环在转轴后方，开栓用正角度。详见下面 lever 段。
LEVER_PIVOT_Z = -1.90
LEVER_PIVOT_Y = -0.78

GROUPS = [
    ('root',        None,       [0, 0, 0]),
    ('move',        'root',     [0, 0, 0]),
    ('body',        'move',     [0, -0.30, 0.50]),
    ('barrel',      'body',     [0, 0, -2.60]),
    ('forearm',     'body',     [0, -0.30, -4.40]),
    ('receiver',    'body',     [0, -0.30, -1.00]),
    ('stock',       'body',     [0, -1.00, 0.50]),
    ('bolt',        'receiver', [0, -0.10, -1.45]),
    ('hammer',      'receiver', [0, -0.25, 0.30]),
    ('lever',       'receiver', [0, LEVER_PIVOT_Y, LEVER_PIVOT_Z]),
    ('carrier',     'receiver', [0, -0.55, -1.35]),
    ('cartridge',   'receiver', [0, -0.35, -1.40]),
    ('spent_shell', 'receiver', [0, 0.05, -0.85]),
    ('trigger',     'receiver', [0, -0.74, -0.24]),
    # 装填门（loading gate）单独一根骨骼：真枪这块是弹簧钢片，压弹时被子弹顶开、
    # 弹进仓后弹回 —— 做成可动件才能把"装弹"这一下做真。
    ('gate',        'receiver', [0, -0.47, 0.06]),
    ('scope',       'receiver', [0, 0.44, -3.50]),
]

# 材质：给贴图绘制脚本用（也决定每面的底色）
MAT = {
    'blued': (46, 51, 58),      # 发蓝钢
    'blued_dark': (28, 31, 36),
    'steel': (128, 135, 144),   # 抛光钢
    'walnut': (110, 74, 42),    # 胡桃木
    'walnut_dark': (74, 48, 24),
    'brass': (176, 141, 87),
    'brass_dark': (128, 96, 52),
    'copper': (156, 95, 51),
    'lens': (72, 94, 118),
}


def mat_of(name):
    n = name
    if n.startswith(('stock_', 'buttplate')) or n.startswith('forearm') or n.startswith('forend'):
        return 'walnut' if not n.startswith('buttplate') else 'steel'
    if n.startswith('cartridge_bullet'):
        return 'copper'
    if n.startswith('cartridge') or n.startswith('shell'):
        return 'brass_dark' if n.startswith('shell') else 'brass'
    if n.startswith('bolt') or n.startswith('carrier'):
        return 'steel'
    if n.startswith('scope_obj') or n.startswith('scope_eye'):
        return 'blued_dark'
    if n.startswith('scope'):
        return 'blued_dark'
    if n.startswith('sling') or n.startswith('screw') or n.startswith('lever_pin_screw'):
        return 'steel'
    # 杠杆（含杠杆环与扳机护圈）在真枪上与机匣同为**发蓝钢**，不是亮银抛光钢 ——
    # 参考图上它们的颜色和机匣是一个色系，只有边缘有一点高光。
    if n.startswith('lever'):
        return 'blued'
    return 'blued'


CUBES = []


def add(name, bone, frm, to, rot=None, origin=None, mat_faces=None):
    a = [min(frm[i], to[i]) for i in range(3)]
    b = [max(frm[i], to[i]) for i in range(3)]
    CUBES.append({
        'name': name, 'parent': bone,
        'from': a, 'to': b,
        'rotation': list(rot or (0, 0, 0)),
        'origin': list(origin if origin else a),
        'mat': mat_of(name),
        'mat_faces': dict(mat_faces or {}),
    })


def tube(name, bone, z0, z1, segs, R_out, R_in, cx=0.0, cy=0.0, overlap=1.08,
         cap_face=None, cap_mat='lens'):
    """沿 Z 轴的 n 棱管：每面一块、绕自身中心旋转 —— 真枪枪管/管仓/镜管必须是圆的。
    cap_face 给 'north'/『south』时，该端面单独用 cap_mat（镜片）。"""
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
    """**连贯的椭圆环**，环面在 YZ 平面（环绕 X 轴）：杠杆环 / 扳机护圈用。

    做法：把椭圆按角度切成 n 段，每段是一根沿弦方向的直条，长度按弦长再放 10% 与邻段搭接
    —— 相邻段端点必然重叠，整圈看不到缝。
    （早先的写法是 n 个轴对齐方块各绕自身中心转一个角度：块边长短于弧长，环上有 6 处缝，
     看起来像断开成两个环。）
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
    """**连贯的环**，环面在 XY 平面（环绕枪身轴线）：枪管/护木卡箍（barrel band）用。

    真枪的卡箍是一个闭合的钢环箍住枪管与管仓，不是一块实心方疙瘩 —— 参考图里能看清
    护木前端那个环的管厚是均匀的、整圈连贯。
    """
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


# ===================================================== 1. barrel（枪管组）
BZ0, BZ1 = -10.60, -2.60
_seg = (BZ1 - BZ0) / 4.0
for i in range(4):
    tube(f'barrel_tube{i}', 'barrel', BZ0 + i * _seg, BZ0 + (i + 1) * _seg,
         segs=8, R_out=0.165, R_in=0.075)
add('muzzle_crown', 'barrel', [-0.175, -0.175, -10.72], [0.175, 0.175, -10.58])
add('muzzle_bore', 'barrel', [-0.075, -0.075, -10.74], [0.075, 0.075, -10.62])
add('front_sight_base', 'barrel', [-0.10, 0.145, -10.52], [0.10, 0.235, -10.20])
add('front_sight_blade', 'barrel', [-0.028, 0.225, -10.48], [0.028, 0.40, -10.34])
MAG_CY = -0.30
_ms = (BZ1 - (BZ0 + 1.0)) / 3.0
for i in range(3):
    z0 = BZ0 + 1.0 + i * _ms
    tube(f'mag_tube{i}', 'barrel', z0, z0 + _ms, segs=6, R_out=0.12, R_in=0.045, cy=MAG_CY)
add('mag_end_cap', 'barrel', [-0.145, MAG_CY - 0.145, -10.22], [0.145, MAG_CY + 0.145, -10.02])
add('mag_plug', 'barrel', [-0.135, MAG_CY - 0.135, -10.04], [0.135, MAG_CY + 0.135, -9.88])
# 前卡箍（barrel band）：**闭合的钢环**箍住枪管与管仓 —— 参考图里这个环在护木前端上，
# 管厚均匀、整圈连贯（早先做的是一块实心方疙瘩，看着像个方块而不是环）。
ring_xy('band_front', 'barrel', -5.20, -0.225, 0.264, 0.395, 0.055, 0.14, n=12)
# 护木后端 / 机匣前的箍（参考图 x≈645 处的金属环）
ring_xy('band_rear', 'barrel', -3.24, -0.256, 0.256, 0.421, 0.05, 0.13, n=12)
add('sling_stud_front', 'barrel', [-0.045, MAG_CY - 0.20, -9.30], [0.045, MAG_CY - 0.10, -9.00])
add('sling_swivel_front', 'barrel', [-0.035, MAG_CY - 0.30, -9.24], [0.035, MAG_CY - 0.19, -9.06])

# ===================================================== 2. forearm（护木）
add('forearm_tip', 'forearm', [-0.235, -0.60, -6.30], [0.235, -0.185, -5.42])
add('forearm_mid', 'forearm', [-0.245, -0.62, -5.44], [0.245, -0.180, -4.52])
add('forearm_rear', 'forearm', [-0.252, -0.66, -4.54], [0.252, -0.178, -3.64])
add('forearm_breech', 'forearm', [-0.258, -0.72, -3.66], [0.258, -0.172, -2.62])
add('forend_check_negx', 'forearm', [-0.264, -0.44, -4.40], [-0.250, -0.24, -3.10])
add('forend_check_posx', 'forearm', [0.250, -0.44, -4.40], [0.264, -0.24, -3.10])
add('forearm_cap', 'forearm', [-0.243, -0.61, -6.42], [0.243, -0.19, -6.28])

# ===================================================== 3. receiver（机匣）
RX = 0.29
RY_TOP, RY_BOT = 0.16, -0.78
RZ_F, RZ_B = -2.60, 0.42
add('receiver_top', 'receiver', [-RX, 0.06, RZ_F], [RX, RY_TOP, RZ_B])
add('receiver_wall_closed', 'receiver', [-RX, RY_BOT, RZ_F], [-RX + 0.05, 0.06, RZ_B])
add('receiver_wall_port_fwd', 'receiver', [RX - 0.05, RY_BOT, RZ_F], [RX, 0.06, -1.36])
add('receiver_wall_port_aft', 'receiver', [RX - 0.05, RY_BOT, -0.74], [RX, 0.06, RZ_B])
add('receiver_wall_port_low', 'receiver', [RX - 0.05, RY_BOT, -1.38], [RX, -0.30, -0.72])
add('port_liner', 'receiver', [RX - 0.06, -0.28, -1.34], [RX - 0.02, 0.05, -0.76])
add('receiver_floor', 'receiver', [-RX, RY_BOT, RZ_F], [RX, RY_BOT + 0.08, 0.06])
add('receiver_floor_rear', 'receiver', [-RX + 0.01, RY_BOT - 0.07, 0.04], [RX - 0.01, RY_BOT + 0.02, RZ_B])
add('receiver_front_ring', 'receiver', [-RX + 0.02, RY_BOT, -2.72], [RX - 0.02, RY_TOP, RZ_F + 0.02])
add('receiver_front_bridge', 'receiver', [-RX + 0.01, -0.50, -2.58], [RX - 0.01, 0.14, -2.44])
add('receiver_rear_block', 'receiver', [-RX + 0.02, -0.46, 0.30], [RX - 0.02, 0.05, 0.40])
add('receiver_tang_top', 'receiver', [-0.175, -0.50, 0.36], [0.175, 0.13, 0.78])
add('receiver_tang_bottom', 'receiver', [-0.215, -0.84, 0.28], [0.215, -0.73, 0.56])
add('side_plate_negx', 'receiver', [-RX - 0.022, -0.40, -2.10], [-RX - 0.004, 0.06, -1.30])
add('side_plate_posx', 'receiver', [RX + 0.004, -0.42, -2.14], [RX + 0.022, 0.06, -1.34])
add('loading_gate', 'gate', [RX + 0.004, -0.64, 0.02], [RX + 0.028, -0.30, 0.34])
add('loading_gate_lip', 'gate', [RX + 0.006, -0.66, -0.06], [RX + 0.020, -0.60, 0.40])
for i, (yy, zz) in enumerate([(-0.86, -0.34), (-0.30, -0.06), (-0.06, -2.26)]):
    add(f'screw_negx{i}', 'receiver', [-RX - 0.022, yy, zz], [-RX - 0.004, yy + 0.13, zz + 0.13])
    add(f'screw_posx{i}', 'receiver', [RX + 0.004, yy, zz], [RX + 0.022, yy + 0.13, zz + 0.13])

# ===================================================== 4. bolt（闭锁块）
add('bolt_body_a', 'bolt', [-0.245, -0.30, -2.06], [0.245, 0.05, -1.36])
add('bolt_body_b', 'bolt', [-0.24, -0.295, -1.38], [0.24, 0.045, -0.62])
add('bolt_face', 'bolt', [-0.225, -0.28, -2.14], [0.225, 0.035, -2.04])
add('extractor_claw', 'bolt', [0.20, 0.01, -2.10], [0.265, 0.09, -1.92])

# ===================================================== 5. hammer（击锤）
add('hammer_body', 'hammer', [-0.075, -0.12, 0.14], [0.075, 0.30, 0.34])
add('hammer_spur', 'hammer', [-0.085, 0.26, 0.08], [0.085, 0.40, 0.28])
add('hammer_half_cock', 'hammer', [-0.05, 0.02, 0.32], [0.05, 0.12, 0.40])

# ===================================================== 6. lever（杠杆，含环）
# 真枪结构（按用户给的照片级参考图 + 复核旧图定下来）：**只有一个环** ——
#   · 转轴（lever pin）在机匣**前下方**（弹仓口下方，z ≈ −1.90）；
#   · lever 是一根**长杆**，沿机匣底部向后延伸；
#   · 杆的末端弯成**环（lever loop）**，这个环**兼作扳机护圈**，扳机就垂在环里；
#     照片上环的前上方那段短金属，就是长杆与机匣相接的地方。
#   ⚠ 上一轮我把旧参考图里的"长杆 + 环"误读成"护圈 + 杠杆环"两个环 —— 照片级参考图上
#     机匣下方只有一个环，所以这一版把那个多余的护圈删掉了。
# 量取（真枪环外径约 2.5 × 2.2 in ⇒ 1.0 × 1.2 u 量级；环管厚约 0.11 u）：
#   环中心 (y −1.35, z −0.20)、半轴 (z 0.53, y 0.42) ⇒ y −1.77 … −0.93，扳机底 −1.08 落在环内
# 打开方向：环在转轴**后方**（Δz = +1.70）⇒ 绕 X 轴**正向**转（真枪约 35–45°）
LEVER_PIVOT_Z = -1.90
LEVER_PIVOT_Y = -0.78

# lever 本体：转轴销 + 长杆（沿机匣底向后） + 末端兼作护圈的环
add('lever_pin', 'lever', [-0.062, LEVER_PIVOT_Y - 0.09, LEVER_PIVOT_Z - 0.14],
    [0.062, LEVER_PIVOT_Y + 0.05, LEVER_PIVOT_Z + 0.14])
add('lever_pin_screw_negx', 'lever', [-0.076, -0.85, LEVER_PIVOT_Z - 0.045],
    [-0.060, -0.795, LEVER_PIVOT_Z + 0.045])
add('lever_pin_screw_posx', 'lever', [0.060, -0.85, LEVER_PIVOT_Z - 0.045],
    [0.076, -0.795, LEVER_PIVOT_Z + 0.045])
add('lever_arm_a', 'lever', [-0.075, -0.90, -1.92], [0.075, -0.78, -1.42], rot=[-13, 0, 0])
add('lever_arm_b', 'lever', [-0.075, -0.94, -1.48], [0.075, -0.82, -0.98], rot=[-14, 0, 0])
add('lever_arm_c', 'lever', [-0.078, -1.00, -1.04], [0.078, -0.86, -0.56], rot=[-16, 0, 0])
# 环：兼作扳机护圈（照片上就是这么一件），包住扳机
ring_yz('lever_loop', 'lever', -1.35, -0.20, 0.53, 0.42, 0.11, 0.075, n=18)

# ===================================================== 7. carrier（升降器）
add('carrier_plate', 'carrier', [-0.19, -0.66, -1.64], [0.19, -0.44, -1.08])
add('carrier_lifter', 'carrier', [-0.075, -0.66, -1.10], [0.075, -0.32, -0.80])

# ===================================================== 8. cartridge（一发待装弹）
CZ0, CZ1 = -1.62, -0.66
add('cartridge_case_a', 'cartridge', [-0.095, -0.095, CZ0 + 0.04], [0.095, 0.095, CZ0 + 0.50])
add('cartridge_case_b', 'cartridge', [-0.093, -0.093, CZ0 + 0.52], [0.093, 0.093, CZ1])
add('cartridge_rim', 'cartridge', [-0.107, -0.107, CZ1], [0.107, 0.107, CZ1 + 0.05])
add('cartridge_bullet_a', 'cartridge', [-0.062, -0.062, CZ0 - 0.30], [0.062, 0.062, CZ0 + 0.06])
add('cartridge_bullet_b', 'cartridge', [-0.038, -0.038, CZ0 - 0.48], [0.038, 0.038, CZ0 - 0.24])

# ===================================================== 9. spent_shell（空壳）
add('shell_body_a', 'spent_shell', [-0.095, -0.095, -1.10], [0.095, 0.095, -0.68])
add('shell_body_b', 'spent_shell', [-0.093, -0.093, -0.70], [0.093, 0.093, -0.42])
add('shell_rim', 'spent_shell', [-0.107, -0.107, -0.44], [0.107, 0.107, -0.38])

# ===================================================== 10. trigger（扳机）
# 真枪扳机从机匣底部垂下来，落在杠杆环**内部**；轴在机匣底部（靠后），
# 扣扳机是下端向**后**摆 = 绕 X 轴负向（与 lever 同向）。
add('trigger_blade', 'trigger', [-0.05, -1.08, -0.30], [0.05, -0.76, -0.19])
add('trigger_sear', 'trigger', [-0.035, -0.80, -0.30], [0.035, -0.70, -0.22])

# ===================================================== 11. scope（瞄准镜）
SCY = 0.64               # 镜管中心高度。真枪 M1894 是**顶部抛壳**，镜子必须架得够高
                         # 才不会挡住抛壳口 —— 这也是真实 M1894 多不装顶置镜的原因。
                         # 镜管底（0.435）与机匣顶（0.16）之间留 0.275 u ≈ 17 mm 可见空隙。
SZ0, SZ1 = -6.62, -0.36
tube('scope_tube', 'scope', SZ0, SZ1, segs=6, R_out=0.205, R_in=0.10, cy=SCY)
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
# 底座：从机匣顶（0.16）顶到卡环底（SCY−0.245 = 0.395），把抬高后的镜稳稳架住
add('mount_front', 'scope', [-0.12, 0.13, -6.02], [0.12, 0.41, -5.80])
add('mount_rear', 'scope', [-0.12, 0.13, -1.22], [0.12, 0.41, -1.00])

# ===================================================== 12. stock（枪托）
# 真枪托：托背（comb）近乎水平、托腹向后下方倾斜，托底 drop 约 195 mm。
# 分 8 段让轮廓连续 —— 每段尺寸只差 ~0.08 u（若用 6 段大跳变会看出"台阶"），
# 相邻段 z 向重叠 0.04 以免相接面被判共面。
_hx0, _hx1 = 0.275, 0.330
_yt0, _yt1 = -0.42, -0.98
_yb0, _yb1 = -1.20, -3.12
_sz0, _sz1 = 0.42, 6.70
NSEG = 16
for i in range(NSEG):
    ta, tb = i / NSEG, (i + 1) / NSEG
    za = _sz0 + (_sz1 - _sz0) * ta - (0.06 if i else 0.0)
    zb = _sz0 + (_sz1 - _sz0) * tb
    mid = (ta + tb) / 2
    hx = _hx0 + (_hx1 - _hx0) * mid
    yt = _yt0 + (_yt1 - _yt0) * mid
    yb = _yb0 + (_yb1 - _yb0) * mid
    add(f'stock_seg{i}', 'stock', [-hx, yb, za], [hx, yt, zb])
add('buttplate', 'stock', [-0.335, -3.20, 6.66], [0.335, -1.00, 6.90])
add('buttplate_heel', 'stock', [-0.32, -1.16, 6.88], [0.32, -0.98, 7.04])
add('buttplate_toe', 'stock', [-0.34, -3.32, 6.88], [0.34, -2.98, 7.06])
add('stock_latch', 'stock', [-0.06, -2.72, 6.82], [0.06, -2.56, 7.00])
add('sling_swivel_rear', 'stock', [-0.035, -2.06, 4.60], [0.035, -1.90, 4.90])


# --------------------------------------------------------------- 共面自愈
def is_rotated(c):
    return any(abs(v) > 0.001 for v in c['rotation'])


def is_ring_seg(name):
    """环的段（杠杆环 / 卡箍环）：**不许被共面自愈挪动**。
    环上总有一两段的角度正好是 0° 或 180°（切线与 X 轴或 Z 轴平行），会被 is_rotated()
    当成"未旋转方块"参与 nudge —— 一挪就把整圈的搭接量吃掉，环上出现明显的缝
    （实测 band_front 因此裂了 0.41 u ≈ 26 mm）。"""
    return name.startswith(('lever_loop', 'band_front', 'band_rear'))


def heal_coplanar(cubes, rounds=4):
    """**真重叠**的共面才推：两未旋转方块在同一轴上区间有重叠、又共享一个平面时，
    它们的面同向重合 → z-fighting。只是"相接"（区间不重叠、只共一个平面）不推 ——
    枪管/护木分段相贴是正常的，推开会出缝。"""
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
                    ov_ax = min(a['to'][ax], b['to'][ax]) - max(a['from'][ax], b['from'][ax])
                    if ov_ax <= 0.0:      # 只是相接，不会 z-fight
                        continue
                    hit = False
                    for pa in (a['from'][ax], a['to'][ax]):
                        for pb in (b['from'][ax], b['to'][ax]):
                            if abs(pa - pb) >= 0.02:
                                continue
                            if abs(b['from'][ax] - pa) < abs(b['to'][ax] - pa):
                                b['from'][ax] -= NUDGE
                            else:
                                b['to'][ax] += NUDGE
                            fixed += 1
                            hit = True
                            break
                        if hit:
                            break
        total += fixed
        if not fixed:
            break
    return total


# --------------------------------------------------------------- UV 货架打包
FACE_AXES = {
    'north': (0, 1), 'south': (0, 1),   # 宽 X / 高 Y
    'east': (2, 1), 'west': (2, 1),     # 宽 Z / 高 Y
    'up': (0, 2), 'down': (0, 2),       # 宽 X / 高 Z
}


def pack_uv(cubes):
    """给每个方块的每个面分配 512² 图集上的矩形（密度 UV_DENSITY px/u）。"""
    items = []
    for ci, c in enumerate(cubes):
        size = [c['to'][k] - c['from'][k] for k in range(3)]
        for face, (wa, ha) in FACE_AXES.items():
            w = max(3, int(round(size[wa] * UV_DENSITY)))
            h = max(3, int(round(size[ha] * UV_DENSITY)))
            items.append({'ci': ci, 'face': face, 'w': w, 'h': h})
    items.sort(key=lambda it: (-it['h'], -it['w']))
    x = y = row_h = 0
    for it in items:
        if x + it['w'] > TEX_W:
            x = 0
            y += row_h + UV_PAD
            row_h = 0
        it['uv'] = [x, y, x + it['w'], y + it['h']]
        x += it['w'] + UV_PAD
        row_h = max(row_h, it['h'])
    used_h = y + row_h
    for it in items:
        c = cubes[it['ci']]
        c.setdefault('faces', {})[it['face']] = {
            'uv': it['uv'], 'rotation': 0, 'texture': 'win94',
        }
        # 必须显式关自动 UV：否则 Blockbench 会按 autouv/box_uv 重算，faces.uv 被丢弃
        c['autouv'] = 0
        c['box_uv'] = False
    return used_h, items


def main():
    os.makedirs(OUT, exist_ok=True)
    healed = heal_coplanar(CUBES)
    used_h, items = pack_uv(CUBES)

    groups = [{'name': n, 'origin': o, **({'parent': p} if p else {})} for n, p, o in GROUPS]
    with open(os.path.join(OUT, 'win94_groups.json'), 'w', encoding='utf-8') as f:
        json.dump({'groups': groups}, f, ensure_ascii=False, indent=1)

    by_bone = {}
    for c in CUBES:
        by_bone.setdefault(c['parent'], []).append(c)
    for bone, list_ in by_bone.items():
        payload = {'cubes': [{k: v for k, v in c.items() if k not in ('mat', 'mat_faces')} for c in list_]}
        with open(os.path.join(OUT, f'win94_cubes_{bone}.json'), 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)

    uvmap = [{'cube': CUBES[it['ci']]['name'], 'bone': CUBES[it['ci']]['parent'],
              'mat': CUBES[it['ci']].get('mat_faces', {}).get(it['face'], CUBES[it['ci']]['mat']),
              'face': it['face'], 'uv': it['uv']} for it in items]
    with open(os.path.join(OUT, 'win94_uvmap.json'), 'w', encoding='utf-8') as f:
        json.dump({'density': UV_DENSITY, 'texture': [TEX_W, TEX_H], 'faces': uvmap},
                  f, ensure_ascii=False, indent=1)

    print(f'cubes total = {len(CUBES)}   coplanar healed = {healed}   uv used height = {used_h}/{TEX_H}')
    for n, _, _ in GROUPS:
        if n in by_bone:
            print(f'  {n:14s} {len(by_bone[n]):3d}')
    xs = [c['from'][0] for c in CUBES] + [c['to'][0] for c in CUBES]
    ys = [c['from'][1] for c in CUBES] + [c['to'][1] for c in CUBES]
    zs = [c['from'][2] for c in CUBES] + [c['to'][2] for c in CUBES]
    print(f'bounds: x [{min(xs):.2f},{max(xs):.2f}] y [{min(ys):.2f},{max(ys):.2f}] z [{min(zs):.2f},{max(zs):.2f}]')
    print(f'OAL = {max(zs) - min(zs):.2f} u = {(max(zs) - min(zs)) * 62.5:.0f} mm')


if __name__ == '__main__':
    main()
