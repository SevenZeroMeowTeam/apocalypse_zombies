# -*- coding: utf-8 -*-
"""win94 重设计 v2 —— 按 PUBG Win94 参考图 + 真枪 M1894 文献全量重建几何。
基准: 1u=62.5mm, OAL≈1089mm(文献1079.5, +0.9%), bore中心 y=0, 枪口 -z。
参考图实测(px→u, 1px=0.78225mm/62.5):
  枪管Ø21px=16.4mm | 弹仓管Ø26px=20mm | 机匣长230px=180mm 顶面与枪管齐平
  杠杆圈垂至 bore 下139mm 后伸至托腕下 | 枪托全长37% 月牙托底 heel 75/toe 195mm drop
  镜长411mm Ø42mm 双卡环 | 护木长239mm 楔形
同时修复: 组 parent/children 大纲断裂(root 自引用), 骨原点按新几何重定。
从 tools/win94_backup_1016.bbmodel 读入(保组uuid→动画引用不断), 写回 win94.bbmodel。
"""
import json, os, sys, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'tools', 'win94_backup_1016.bbmodel')
DST = os.path.join(ROOT, 'win94.bbmodel')

r4 = lambda v: round(v + 0.0, 4)

# ---- 方块表: name -> (bone, (x0,y0,z0), (x1,y1,z1))  绝对坐标 ----
CUBES = [
    # === barrel 骨: 枪管/弹仓/准星/箍带 ===
    ('barrel_pipe_a',      'barrel', (-0.125,-0.125,-10.52), (0.125,0.125,-6.38)),
    ('barrel_pipe_b',      'barrel', (-0.121,-0.121,-6.40),  (0.121,0.121,-2.32)),
    ('muzzle_crown',       'barrel', (-0.142,-0.142,-10.54), (0.142,0.142,-10.30)),
    ('front_sight_base',   'barrel', (-0.09,0.115,-10.44),   (0.09,0.20,-10.24)),
    ('front_sight_blade',  'barrel', (-0.03,0.18,-10.40),    (0.03,0.345,-10.28)),
    ('mag_tube_a',         'barrel', (-0.163,-0.457,-10.33), (0.163,-0.131,-6.40)),
    ('mag_tube_b',         'barrel', (-0.159,-0.453,-6.42),  (0.159,-0.135,-2.32)),
    ('mag_nose_cap',       'barrel', (-0.20,-0.494,-10.32),  (0.20,-0.094,-10.10)),
    ('mag_band_mid',       'barrel', (-0.175,-0.47,-4.60),   (0.175,-0.11,-4.40)),
    ('band_fore',          'barrel', (-0.245,-0.47,-6.35),   (0.245,0.16,-6.05)),
    ('sling_swivel_front', 'barrel', (-0.045,-0.52,-9.20),   (0.045,-0.42,-8.90)),
    # === forearm 骨: 护木(楔形, 越靠机匣越深) + 检纹侧板 ===
    ('forearm_tip',        'forearm', (-0.235,0.02,-6.28),  (0.235,-0.60,-5.40)),
    ('forearm_mid',        'forearm', (-0.245,0.04,-5.42),  (0.245,-0.64,-3.90)),
    ('forearm_rear',       'forearm', (-0.25,0.045,-3.92),  (0.25,-0.73,-2.55)),
    ('forend_check_left',  'forearm', (-0.262,-0.30,-3.90), (-0.248,-0.10,-3.10)),
    ('forend_check_right', 'forearm', (0.248,-0.30,-3.90),  (0.262,-0.10,-3.10)),
    # === receiver 骨: 壳体(右墙留抛壳口缺口) + 侧板/装弹门/螺钉 ===
    ('receiver_top',          'receiver', (-0.35,0.04,-2.48),    (0.35,0.14,+0.43)),
    ('receiver_left',         'receiver', (-0.37,-0.80,-2.46),   (-0.31,0.06,+0.41)),
    ('receiver_right_a',      'receiver', (0.31,-0.80,-2.46),    (0.37,0.06,-1.28)),
    ('receiver_right_b',      'receiver', (0.31,-0.80,-0.68),    (0.37,0.06,+0.41)),
    ('port_liner',            'receiver', (0.30,-0.34,-1.26),    (0.34,0.05,-0.70)),
    ('receiver_floor_front',  'receiver', (-0.349,-0.795,-2.42), (0.349,-0.70,-0.50)),
    ('receiver_floor_rear',   'receiver', (-0.345,-0.87,-0.52),  (0.345,-0.78,+0.39)),
    ('receiver_front_bridge', 'receiver', (-0.348,-0.79,-2.44),  (0.348,0.13,-2.30)),
    ('receiver_front_ring',   'receiver', (-0.32,-0.50,-2.55),   (0.32,0.135,-2.42)),
    ('receiver_rear_block',   'receiver', (-0.345,-0.46,+0.32),  (0.345,0.05,+0.39)),
    ('receiver_tang_top',     'receiver', (-0.17,-0.50,+0.37),   (0.17,0.13,+0.75)),
    ('receiver_tang_bottom',  'receiver', (-0.21,-0.83,+0.30),   (0.21,-0.72,+0.55)),
    ('side_plate_r',          'receiver', (0.366,-0.40,-2.10),   (0.392,0.08,-1.30)),
    ('side_plate_l',          'receiver', (-0.392,-0.38,-2.05),  (-0.366,0.055,-1.35)),
    ('loading_gate',          'receiver', (0.366,-0.62,+0.04),   (0.388,-0.28,+0.36)),
    ('lever_pin_screw_r',     'receiver', (0.366,-0.60,-0.42),   (0.392,-0.48,-0.28)),
    ('lever_pin_screw_l',     'receiver', (-0.392,-0.60,-0.42),  (-0.366,-0.48,-0.28)),
    ('big_screw_r',           'receiver', (0.366,-0.14,-0.10),   (0.392,-0.02,+0.04)),
    ('big_screw_l',           'receiver', (-0.392,-0.14,-0.10),  (-0.366,-0.02,+0.04)),
    ('small_screw_r1',        'receiver', (0.366,-0.02,-2.30),   (0.388,0.05,-2.18)),
    ('small_screw_l1',        'receiver', (-0.388,-0.02,-2.30),  (-0.366,0.05,-2.18)),
    ('small_screw_r2',        'receiver', (0.366,-0.72,-0.34),   (0.388,-0.64,-0.22)),
    ('small_screw_l2',        'receiver', (-0.388,-0.72,-0.34),  (-0.366,-0.64,-0.22)),
    # === bolt 骨: 机匣内枪机(抛壳口开启时可见) ===
    ('bolt_body_a',   'bolt', (-0.27,-0.26,-1.90), (0.27,0.08,-1.00)),
    ('bolt_body_b',   'bolt', (-0.265,-0.255,-1.02), (0.265,0.075,-0.60)),
    ('bolt_face',     'bolt', (-0.25,-0.24,-1.98), (0.25,0.06,-1.86)),
    ('extractor_claw','bolt', (0.24,0.02,-1.99), (0.30,0.10,-1.84)),
    # === hammer 骨: 击锤(pivot [0,0.30,0.26], +x=待击) ===
    ('hammer_body', 'hammer', (-0.11,0.12,0.16), (0.11,0.34,0.36)),
    ('hammer_spur', 'hammer', (-0.125,0.30,0.12), (0.125,0.42,0.30)),
    # === lever 骨: 大杠杆圈(pivot [0,-0.80,0.09], +x=开膛下摆) ===
    ('lever_pin',    'lever', (-0.06,-0.86,-0.10), (0.06,-0.66,+0.28)),
    ('lever_arm',    'lever', (-0.10,-1.02,-0.12), (0.10,-0.72,+0.24)),
    ('lever_loop_1', 'lever', (-0.095,-1.25,-0.55), (0.095,-0.76,-0.32)),
    ('lever_loop_2', 'lever', (-0.090,-1.68,-0.50), (0.090,-1.20,-0.26)),
    ('lever_loop_3', 'lever', (-0.095,-1.98,-0.40), (0.095,-1.63,-0.14)),
    ('lever_loop_4', 'lever', (-0.090,-2.16,-0.24), (0.090,-1.93,+0.18)),
    ('lever_loop_5', 'lever', (-0.095,-2.22,+0.14), (0.095,-2.05,+0.60)),
    ('lever_loop_6', 'lever', (-0.090,-2.13,+0.58), (0.090,-2.00,+1.02)),
    ('lever_loop_7', 'lever', (-0.095,-2.10,+1.00), (0.095,-1.88,+1.32)),
    ('lever_loop_8', 'lever', (-0.090,-1.95,+1.30), (0.090,-1.62,+1.82)),
    # === carrier 骨: 送弹器(+y 抬升) ===
    ('carrier_plate',  'carrier', (-0.20,-0.62,-1.55), (0.20,-0.38,-1.05)),
    ('carrier_lifter', 'carrier', (-0.07,-0.62,-1.03), (0.07,-0.30,-0.75)),
    # === trigger 骨 ===
    ('trigger_blade', 'trigger', (-0.04,-1.12,-0.26), (0.04,-0.76,-0.18)),
    # === scope 骨: 长管镜(镜长6.6u=411mm Ø~0.55u 双卡环) ===
    ('scope_tube_a',     'scope', (-0.275,0.145,-6.20), (0.275,0.695,-3.20)),
    ('scope_tube_b',     'scope', (-0.271,0.149,-3.22), (0.271,0.691,-0.50)),
    ('scope_obj',        'scope', (-0.34,0.07,-6.79),   (0.34,0.77,-6.16)),
    ('scope_obj_rim',    'scope', (-0.36,0.05,-6.81),   (0.36,0.79,-6.66)),
    ('scope_eye',        'scope', (-0.30,0.12,-0.52),   (0.30,0.72,-0.22)),
    ('scope_eye_ring',   'scope', (-0.32,0.10,-0.32),   (0.32,0.74,-0.20)),
    ('scope_turret_top', 'scope', (-0.08,0.68,-3.60),   (0.08,0.82,-3.40)),
    ('scope_turret_cap', 'scope', (-0.085,0.80,-3.62),  (0.085,0.84,-3.38)),
    ('scope_turret_side','scope', (0.26,0.35,-3.55),    (0.42,0.49,-3.45)),
    ('mount_front',      'scope', (-0.13,-0.14,-2.40),  (0.13,0.16,-2.14)),
    ('mount_rear',       'scope', (-0.13,-0.14,-1.14),  (0.13,0.16,-0.86)),
    # === stock 骨: 弧形枪托(阶梯逼近参考轮廓, 驼峰肩部+月牙托底) ===
    ('stock_wrist',      'stock', (-0.30,-1.22,+0.36),  (0.30,-0.40,+1.10)),
    ('stock_grip',       'stock', (-0.31,-1.58,+1.00),  (0.31,-0.58,+1.88)),
    ('stock_lowcomb',    'stock', (-0.315,-1.86,+1.76), (0.315,-0.84,+2.62)),
    ('stock_shoulder',   'stock', (-0.32,-2.12,+2.50),  (0.32,-0.60,+3.32)),
    ('stock_butt_upper', 'stock', (-0.325,-2.36,+3.22), (0.325,-0.68,+4.24)),
    ('stock_butt_mid',   'stock', (-0.33,-2.72,+4.14),  (0.33,-0.84,+5.24)),
    ('stock_butt_lower', 'stock', (-0.335,-3.06,+5.14), (0.335,-1.00,+6.34)),
    ('stock_toe',        'stock', (-0.34,-3.16,+6.24),  (0.34,-1.16,+6.76)),
    ('buttplate',        'stock', (-0.35,-3.18,+6.74),  (0.35,-1.08,+6.88)),
    ('stock_latch',      'stock', (-0.06,-3.22,+6.78),  (0.06,-3.14,+6.92)),
    ('sling_swivel_rear','stock', (-0.045,-2.86,+4.60), (0.045,-2.68,+4.90)),
    # === cartridge 骨: .45-70 弹(备用弹在弹仓位, 隐藏于机匣内) ===
    ('cartridge_case_a',   'cartridge', (-0.071,-0.37,-2.20), (0.071,-0.23,-1.41)),
    ('cartridge_case_b',   'cartridge', (-0.068,-0.367,-2.19), (0.068,-0.233,-1.42)),
    ('cartridge_rim',      'cartridge', (-0.078,-0.375,-1.43), (0.078,-0.225,-1.395)),
    ('cartridge_bullet_a', 'cartridge', (-0.045,-0.345,-2.40), (0.045,-0.255,-2.18)),
    ('cartridge_bullet_b', 'cartridge', (-0.042,-0.342,-2.38), (0.042,-0.258,-2.215)),
    # === spent_shell 骨: 已击发弹壳(藏于抛壳口内侧, x>0 E规则) ===
    ('shell_body_a', 'spent_shell', (0.02,0.01,-1.20),  (0.155,0.115,-0.41)),
    ('shell_body_b', 'spent_shell', (0.025,0.015,-1.19),(0.15,0.11,-0.42)),
    ('shell_rim',    'spent_shell', (0.015,0.00,-0.44), (0.16,0.135,-0.40)),
]

# ---- 骨原点(新几何下的真实铰点) ----
BONE_ORIGIN = {
    'root': [0,0,0], 'move': [0,0,0], 'body': [0,-0.3,+0.5],
    'barrel': [0,0,-6.0], 'forearm': [0,-0.3,-4.4],
    'receiver': [0,-0.3,-1.0], 'bolt': [0,-0.1,-1.45],
    'hammer': [0,0.30,0.26], 'lever': [0,-0.80,0.09],
    'carrier': [0,-0.50,-1.30], 'cartridge': [0,-0.30,-1.80],
    'spent_shell': [0,0.075,-0.80], 'trigger': [0,-0.80,-0.22],
    'scope': [0,0.42,-3.50], 'stock': [0,-1.8,+3.5],
    'camera': [0,0,0], 'constraint': [0,0,0],
}
# ---- 骨层级(修复大纲断裂; root 自引用交导出器) ----
BONE_PARENT = {
    'move': 'root', 'body': 'move',
    'barrel': 'body', 'forearm': 'body', 'receiver': 'body', 'stock': 'body',
    'camera': 'body', 'constraint': 'body',
    'bolt': 'receiver', 'hammer': 'receiver', 'lever': 'receiver',
    'carrier': 'receiver', 'cartridge': 'receiver', 'spent_shell': 'receiver',
    'trigger': 'receiver', 'scope': 'receiver',
}

EPS = 1e-4

def coplanar_report(cubes):
    """faces 共面重叠检测: 同轴同坐标(±EPS)且另两轴区间重叠"""
    faces = []  # (name, axis, coord, (a0,a1), (b0,b1))
    for name, _, f, t in cubes:
        for axis in range(3):
            a1, a2 = [a for a in range(3) if a != axis]
            faces.append((name, axis, f[axis], (f[a1],t[a1]), (f[a2],t[a2])))
            faces.append((name, axis, t[axis], (f[a1],t[a1]), (f[a2],t[a2])))
    bad = []
    for i in range(len(faces)):
        n1, ax1, c1, u1, v1 = faces[i]
        for j in range(i+1, len(faces)):
            n2, ax2, c2, u2, v2 = faces[j]
            if n1 == n2 or ax1 != ax2: continue
            if abs(c1-c2) > EPS: continue
            if min(u1[1],u2[1]) - max(u1[0],u2[0]) > EPS and \
               min(v1[1],v2[1]) - max(v1[0],v2[0]) > EPS:
                bad.append((n1, n2, 'xyz'[ax1], round(c1,4)))
    return bad

def main():
    d = json.load(open(SRC, encoding='utf-8'))

    # 1) 重建 elements
    els = []
    by_bone = {}
    for name, bone, f, t in CUBES:
        f = [r4(v) for v in f]; t = [r4(v) for v in t]
        for k in range(3):
            if f[k] > t[k]:
                f[k], t[k] = t[k], f[k]
            if f[k] >= t[k]:
                print('!! 退化方块', name, f, t); sys.exit(1)
        u = str(uuid.uuid4())
        els.append({
            'name': name, 'box_uv': False, 'render_order': 'default',
            'locked': False, 'export': True, 'scope': 0,
            'allow_mirror_modeling': True,
            'from': f, 'to': t, 'autouv': 0, 'color': (hash(name) % 8),
            'origin': [f[0], f[1], f[2]],
            'faces': {k: {'uv': [0, 0, 1, 1], 'texture': 0}
                      for k in ('north','east','south','west','up','down')},
            'type': 'cube', 'uuid': u,
        })
        by_bone.setdefault(bone, []).append(u)

    # 共面自检
    bad = coplanar_report(CUBES)
    if bad:
        print('!! coplanar %d 处:' % len(bad))
        for b in bad[:40]: print('  ', b)
        sys.exit(1)

    # 2) 组: 原点 / parent / children / rotation 归零
    gByName = {g['name']: g for g in d['groups']}
    for n, g in gByName.items():
        g['origin'] = BONE_ORIGIN[n]
        g['rotation'] = [0, 0, 0]
        if n in BONE_PARENT:
            g['parent'] = gByName[BONE_PARENT[n]]['uuid']
        else:
            g.pop('parent', None)
    gByName['root']['children'] = [gByName['move']['uuid']]
    gByName['move']['children'] = [gByName['body']['uuid']]
    gByName['body']['children'] = [gByName[n]['uuid']
        for n in ('barrel','forearm','receiver','stock','camera','constraint')]
    gByName['receiver']['children'] = [gByName[n]['uuid']
        for n in ('bolt','hammer','lever','carrier','cartridge','spent_shell','trigger','scope')]
    for bone, kids in by_bone.items():
        gByName[bone]['children'] = kids

    d['elements'] = els
    json.dump(d, open(DST, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

    # 3) 终验输出
    xs = [v for _,_,f,t in CUBES for v in (f[0],t[0])]
    ys = [v for _,_,f,t in CUBES for v in (f[1],t[1])]
    zs = [v for _,_,f,t in CUBES for v in (f[2],t[2])]
    lenZ = max(zs)-min(zs)
    print('cubes=%d bones=%d' % (len(els), len(d['groups'])))
    print('bbox X %.3f..%.3f Y %.3f..%.3f Z %.3f..%.3f' % (min(xs),max(xs),min(ys),max(ys),min(zs),max(zs)))
    print('OAL %.2fu = %.1fmm (文献1079.5, %+.1f%%)' % (lenZ, lenZ*62.5, (lenZ*62.5/1079.5-1)*100))
    print('coplanar 0  |  E规则(弹壳x>0):',
          all(f[0]>0 for n,b,f,t in CUBES if n.startswith('shell')))
    print('saved', DST, os.path.getsize(DST))

if __name__ == '__main__':
    main()
