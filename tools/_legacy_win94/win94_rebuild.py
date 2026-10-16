# -*- coding: utf-8 -*-
"""win94.bbmodel 离线重整脚本（桥挂死期间的替代通道）。
应用前会话验证过的设计表：
  zA=0.9231*z+0.169 (barrel/forearm)  zB=0.7*z-0.21 (receiver全树)  zC=0.6139*z-0.012 (stock)
  cartridge/shell 用绝对特殊 Z；lever_loop 用 LOOP_Y；XY 用文献表。
"""
import json, math, sys, os

SRC = os.path.join(os.path.dirname(__file__), '..', 'win94.bbmodel')
d = json.load(open(SRC, encoding='utf-8'))

def zA(z): return 0.9231 * z + 0.169
def zB(z): return 0.7 * z - 0.21
def zC(z): return 0.6139 * z - 0.012
def LOOP_Y(y): return 1.0185 * (y + 2.616) - 1.60

def r4(v): return round(v + 0.0, 4)

# ---- 特殊 Z（绝对值，保 .30-30 弹全长） ----
SPECIAL_Z = {
    'cartridge_case': (-0.24, 0.55),
    'cartridge_rim':  (0.53, 0.565),
    'cartridge_bullet': (-0.44, -0.24),
    'shell_body': (-1.1, -0.31),
    'shell_rim': (-0.34, -0.3),
}

# ---- XY 文献表：name -> (x0,x1,y0,y1) ----
XY = {
    # barrel
    'barrel_pipe_a': (-0.106, 0.106, -0.106, 0.106),
    'barrel_pipe_b': (-0.106, 0.106, -0.106, 0.106),
    'muzzle_crown_a': (-0.125, 0.125, -0.125, 0.125),
    'muzzle_crown_b': (-0.125, 0.125, -0.125, 0.125),
    'front_sight_base': (-0.11, 0.11, 0.14, 0.20),
    'front_sight_blade': (-0.035, 0.035, 0.20, 0.33),
    'mag_tube_a': (-0.106, 0.106, -0.452, -0.14),
    'mag_tube_b': (-0.106, 0.106, -0.452, -0.14),
    'mag_cap_a': (-0.16, 0.16, -0.47, -0.12),
    'mag_cap_b': (-0.16, 0.16, -0.47, -0.12),
    'mag_cap_screw': (-0.045, 0.045, -0.34, -0.27),
    'band_muzzle': (-0.165, 0.165, -0.54, 0.18),
    'band_fore': (-0.165, 0.165, -0.54, 0.18),
    'sling_swivel_front': (-0.045, 0.045, -0.60, -0.48),
    # forearm
    'forearm_body': (-0.24, 0.24, -0.50, 0.10),
    'forearm_tip': (-0.205, 0.205, -0.46, 0.06),
    'forearm_swell': (-0.175, 0.175, -0.56, -0.44),
    'forearm_check_left': (-0.255, -0.24, -0.42, 0.02),
    'forearm_check_right': (0.24, 0.255, -0.42, 0.02),
    'forearm_nose_trim': (-0.22, 0.22, -0.52, 0.08),
    # receiver
    'receiver_left': (-0.37, -0.31, -0.85, 0.25),
    'receiver_right': (0.31, 0.37, -0.85, 0.25),
    'receiver_floor_front': (-0.37, 0.37, -0.85, -0.75),
    'receiver_floor_rear': (-0.37, 0.37, -0.85, -0.75),
    'receiver_floor_l': (-0.37, -0.19, -0.85, -0.75),
    'receiver_floor_r': (0.19, 0.37, -0.85, -0.75),
    'receiver_front_bridge': (-0.37, 0.37, 0.13, 0.25),
    'receiver_rear_bridge': (-0.37, 0.37, 0.13, 0.25),
    'loading_gate': (0.355, 0.385, -0.55, -0.08),
    # screws (big 0.355~0.395 / small 0.355~0.385)
    'lever_pin_screw_r': (0.355, 0.395, -0.37, -0.23),
    'lever_pin_screw_r2': (0.355, 0.395, -0.37, -0.23),
    'lever_pin_screw_l': (-0.395, -0.355, -0.37, -0.23),
    'lever_pin_screw_l2': (-0.395, -0.355, -0.37, -0.23),
    'big_side_screw_r': (0.355, 0.395, -0.10, 0.10),
    'big_side_screw_r2': (0.355, 0.395, -0.10, 0.10),
    'big_side_screw_l': (-0.395, -0.355, -0.10, 0.10),
    'big_side_screw_l2': (-0.395, -0.355, -0.10, 0.10),
    'small_screw_r1': (0.355, 0.385, 0.12, 0.20),
    'small_screw_r1b': (0.355, 0.385, 0.12, 0.20),
    'small_screw_l1': (-0.385, -0.355, 0.12, 0.20),
    'small_screw_l1b': (-0.385, -0.355, 0.12, 0.20),
    'small_screw_r2': (0.355, 0.385, -0.60, -0.50),
    'small_screw_l2': (-0.385, -0.355, -0.60, -0.50),
    'receiver_tang_top': (-0.14, 0.14, -0.04, 0.05),
    'receiver_tang_bottom': (-0.14, 0.14, -0.75, -0.62),
    'ejector_ramp': (-0.30, -0.26, -0.02, 0.22),
    # bolt
    'bolt_body_a': (-0.165, 0.165, -0.17, 0.12),
    'bolt_body_b': (-0.165, 0.165, -0.17, 0.12),
    'bolt_face_a': (-0.15, 0.15, -0.15, 0.10),
    'bolt_face_b': (-0.15, 0.15, -0.15, 0.10),
    'bolt_shroud': (-0.145, 0.145, -0.15, 0.11),
    'extractor_claw': (0.03, 0.095, 0.085, 0.125),
    # hammer
    'hammer_body': (-0.115, 0.115, 0.25, 0.50),
    'hammer_spur': (-0.125, 0.125, 0.47, 0.58),
    # lever
    'lever_pin': (-0.06, 0.06, -0.30, -0.18),
    'lever_pin2': (-0.06, 0.06, -0.30, -0.18),
    'lever_arm': (-0.10, 0.10, -0.44, -0.20),
    # carrier
    'carrier_plate': (-0.15, 0.15, -0.52, -0.36),
    'carrier_lifter': (-0.07, 0.07, -0.52, -0.10),
    # cartridge (y)
    'cartridge_case_a': (-0.071, 0.071, -0.37, -0.23),
    'cartridge_case_b': (-0.071, 0.071, -0.37, -0.23),
    'cartridge_rim': (-0.078, 0.078, -0.375, -0.225),
    'cartridge_bullet_a': (-0.045, 0.045, -0.345, -0.255),
    'cartridge_bullet_b': (-0.045, 0.045, -0.345, -0.255),
    # spent shell (E 规则 x>0)
    'shell_body_a': (0.02, 0.155, 0.01, 0.145),
    'shell_body_b': (0.02, 0.155, 0.01, 0.145),
    'shell_rim': (0.015, 0.16, 0.0, 0.15),
    # trigger
    'trigger_blade': (-0.04, 0.04, -0.72, -0.50),
    # scope
    'scope_tube_a': (-0.145, 0.145, 0.615, 0.905),
    'scope_tube_b': (-0.145, 0.145, 0.615, 0.905),
    'scope_obj_a': (-0.25, 0.25, 0.51, 1.01),
    'scope_obj_b': (-0.25, 0.25, 0.51, 1.01),
    'scope_obj_rim_a': (-0.27, 0.27, 0.50, 1.02),
    'scope_obj_rim_b': (-0.27, 0.27, 0.50, 1.02),
    'scope_eye_a': (-0.17, 0.17, 0.60, 0.92),
    'scope_eye_b': (-0.17, 0.17, 0.60, 0.92),
    'scope_eye_ring_a': (-0.185, 0.185, 0.59, 0.93),
    'scope_eye_ring_b': (-0.185, 0.185, 0.59, 0.93),
    'scope_turret_a': (-0.08, 0.08, 0.95, 1.10),
    'scope_turret_b': (-0.08, 0.08, 0.95, 1.10),
    'scope_turret_cap': (-0.085, 0.085, 1.09, 1.13),
    'scope_turret_side_a': (0.19, 0.33, 0.69, 0.83),
    'scope_turret_side_b': (0.19, 0.33, 0.69, 0.83),
    'mount_ring_front_a': (-0.18, 0.18, 0.54, 0.98),
    'mount_ring_front_b': (-0.18, 0.18, 0.54, 0.98),
    'mount_ring_rear_a': (-0.18, 0.18, 0.54, 0.98),
    'mount_ring_rear_b': (-0.18, 0.18, 0.54, 0.98),
    'mount_base_front': (-0.09, 0.09, 0.25, 0.56),
    'mount_base_rear': (-0.09, 0.09, 0.25, 0.56),
    # stock
    'stock_neck': (-0.25, 0.25, -0.52, 0.03),
    'stock_mid': (-0.27, 0.27, -0.95, -0.05),
    'stock_butt': (-0.29, 0.29, -1.30, -0.22),
    'buttplate': (-0.30, 0.30, -1.34, -0.18),
    'stock_latch': (-0.10, 0.10, -1.38, -1.32),
    'sling_swivel_rear': (-0.045, 0.045, -1.56, -1.45),
}
# lever_loop 全部 x±0.125（y 走 LOOP_Y）
for i in range(1, 11):
    XY['lever_loop_%d' % i] = (-0.125, 0.125, None, None)  # y 由 LOOP_Y 算

# ---- 归属分段 ----
ZA_P = ('barrel_pipe', 'muzzle_crown', 'front_sight', 'mag_tube', 'mag_cap',
        'band_muzzle', 'band_fore', 'sling_swivel_front', 'forearm_')
ZC_P = ('stock_', 'buttplate', 'sling_swivel_rear')

def seg(name):
    if name in SPECIAL_Z: return 'S'
    if name.startswith(ZA_P): return 'A'
    if name.startswith(ZC_P): return 'C'
    return 'B'

MAP = {'A': zA, 'B': zB, 'C': zC}

# ---- 应用到 elements ----
els = {e['name']: e for e in d['elements']}
missing = set()
for name, e in els.items():
    if name not in XY:
        missing.add(name); continue
    x0, x1, y0, y1 = XY[name]
    f, t = list(e['from']), list(e['to'])
    # X/Y
    if name.startswith('lever_loop'):
        # y 用 LOOP_Y：旧 y 映射（保每件厚度）
        oy0, oy1 = f[1], t[1]
        ny0, ny1 = LOOP_Y(oy0), LOOP_Y(oy1)
        if ny0 > ny1: ny0, ny1 = ny1, ny0
        f[1], t[1] = r4(ny0), r4(ny1)
        f[0], t[0] = x0, x1
    else:
        f[0], t[0] = x0, x1
        f[1], t[1] = y0, y1
    # Z
    s = seg(name)
    if s == 'S':
        z0, z1 = SPECIAL_Z[name]
        f[2], t[2] = z0, z1
    else:
        m = MAP[s]
        f[2], t[2] = r4(m(f[2])), r4(m(t[2]))
        if f[2] > t[2]: f[2], t[2] = t[2], f[2]
    e['from'], e['to'] = f, t
    # origin 规则
    rot = e.get('rotation') or [0, 0, 0]
    if any(abs(v) > 1e-9 for v in rot) and abs(rot[0]) in (3, 10, 12):
        o = e.get('origin', [0, 0, 0])
        oz = o[2]
        oz = SPECIAL_Z[name][0] if s == 'S' else MAP[s](oz)
        # hammer/trigger 缩放后按"占自身几何的相对位置"保 pivot（不能盲保绝对 y）
        if name == 'hammer_body' or name == 'hammer_spur':
            e['origin'] = [0, 0.31, r4(oz)]
        elif name == 'trigger_blade':
            e['origin'] = [0, -0.52, r4(oz)]
        else:
            e['origin'] = [o[0], o[1], r4(oz)]
    elif any(abs(v) > 1e-9 for v in rot):
        # 45° 菱形/螺帽：origin = 新 box 中心
        e['origin'] = [r4((f[0]+t[0])/2), r4((f[1]+t[1])/2), r4((f[2]+t[2])/2)]
    else:
        e['origin'] = [f[0], f[1], f[2]]

if missing:
    print('!! XY 表缺件:', sorted(missing)); sys.exit(1)

# ---- groups 骨原点 ----
NEW_ORIGIN = {
    'root': ([0, 0, 0], None),
    'move': ([0, 0, 0], None),
    'body': ([0, -0.3, 0.7], None),
    'barrel': ([0, 0, -1.22], None),
    'forearm': ([0, -0.2, -3.52], None),
    'receiver': ([0, 0, r4(zB(0.5))], None),
    'bolt': ([0, 0.03, r4(zB(1.2))], None),
    'hammer': ([0, 0.28, r4(zB(2.0))], None),
    'lever': ([0, -0.24, r4(zB(-0.6))], None),
    'carrier': ([0, -0.44, r4(zB(0.3))], None),
    'cartridge': ([0, -0.3, 0.55], None),
    'spent_shell': ([0, 0.08, -0.3], None),
    'trigger': ([0, -0.61, r4(zB(1.3))], None),
    'scope': ([0, 0.76, r4(zB(-0.5))], None),
    'stock': ([0, -0.3, r4(zC(3.0))], [0, 0, 0]),  # rotation 归零
    'camera': ([0, 0, 0], None),
    'constraint': ([0, 0, 0], None),
}
for g in d['groups']:
    n = g['name']
    if n in NEW_ORIGIN:
        org, rot = NEW_ORIGIN[n]
        g['origin'] = org
        if rot is not None:
            g['rotation'] = rot

# ---- bbox 校验 ----
xs, ys, zs = [], [], []
for e in d['elements']:
    rot = e.get('rotation') or [0, 0, 0]
    f, t = e['from'], e['to']
    cx, cy, cz = (f[0]+t[0])/2, (f[1]+t[1])/2, (f[2]+t[2])/2
    hx, hy, hz = abs(t[0]-f[0])/2, abs(t[1]-f[1])/2, abs(t[2]-f[2])/2
    if rot[0] == 45 and rot[1] == 0:   # X 轴菱形：yz 平面旋转
        ny, nz = (hy+hz)*0.7071, (hy+hz)*0.7071
        hy, hz = ny, nz
    elif rot[2] == 45 and rot[0] == 0: # Z 轴菱形：xy 平面旋转
        nx, ny = (hx+hy)*0.7071, (hx+hy)*0.7071
        hx, hy = nx, ny
    elif rot[0] == 45 and rot[1] == 45:
        pass
    xs += [cx-hx, cx+hx]; ys += [cy-hy, cy+hy]; zs += [cz-hz, cz+hz]
print('bbox X %.4f..%.4f  Y %.4f..%.4f  Z %.4f..%.4f' % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
print('lenZ = %.4f u = %.1f mm ; width = %.4f u = %.1f mm' %
      (max(zs)-min(zs), (max(zs)-min(zs))*62.5, max(xs)-min(xs), (max(xs)-min(xs))*62.5))

json.dump(d, open(SRC, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('saved', SRC, os.path.getsize(SRC))
