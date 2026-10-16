# -*- coding: utf-8 -*-
"""win94 修正 pass2：SPECIAL_Z 后缀 bug（_a/_b 件没吃到特殊 Z）+ coplanar 内嵌修正。"""
import json, os

SRC = os.path.join(os.path.dirname(__file__), '..', 'win94.bbmodel')
d = json.load(open(SRC, encoding='utf-8'))
els = {e['name']: e for e in d['elements']}
def r4(v): return round(v + 0.0, 4)

# ---- 1) SPECIAL_Z 前缀修复 ----
SPECIAL = [
    ('cartridge_case', (-0.24, 0.55)),
    ('cartridge_rim', (0.53, 0.565)),
    ('cartridge_bullet', (-0.44, -0.24)),
    ('shell_body', (-1.1, -0.31)),
    ('shell_rim', (-0.34, -0.3)),
]
for name, e in els.items():
    for pref, (z0, z1) in SPECIAL:
        if name.startswith(pref):
            e['from'][2], e['to'][2] = z0, z1
            rot = e.get('rotation') or [0, 0, 0]
            if not any(abs(v) > 1e-9 for v in rot):
                e['origin'] = [e['from'][0], e['from'][1], z0]
            else:
                e['origin'] = [r4((e['from'][0]+e['to'][0])/2),
                               r4((e['from'][1]+e['to'][1])/2),
                               r4((z0+z1)/2)]
            break

def setx(n, x0=None, x1=None):
    if n in els:
        if x0 is not None: els[n]['from'][0] = x0
        if x1 is not None: els[n]['to'][0] = x1
def sety(n, y0=None, y1=None):
    if n in els:
        if y0 is not None: els[n]['from'][1] = y0
        if y1 is not None: els[n]['to'][1] = y1
def setz(n, z0=None, z1=None):
    if n in els:
        if z0 is not None: els[n]['from'][2] = z0
        if z1 is not None: els[n]['to'][2] = z1

# ---- 2) coplanar 内嵌（tuck=藏进邻件实体内 0.01~0.025） ----
# 机匣底板/侧墙齐平面
setx('receiver_floor_front', -0.36, 0.36)
setx('receiver_floor_rear', -0.36, 0.36)
setx('receiver_floor_l', -0.36, None)
setx('receiver_floor_r', None, 0.36)
sety('receiver_floor_front', -0.84, None)
sety('receiver_floor_rear', -0.84, None)
sety('receiver_floor_l', -0.84, None)
sety('receiver_floor_r', -0.84, None)
setz('receiver_floor_front', -1.39, None)
setz('receiver_floor_rear', None, 1.39)
# 底板前后之间的齐平：中段底板伸进前后底板
setz('receiver_floor_l', -0.75, 0.75)
setz('receiver_floor_r', -0.75, 0.75)
# 桥顶板与侧墙
sety('receiver_front_bridge', None, 0.24)
sety('receiver_rear_bridge', None, 0.24)
setz('receiver_front_bridge', -1.39, None)
setz('receiver_rear_bridge', None, 1.39)
# 装弹口 vs 大侧螺
setx('big_side_screw_r', 0.35, None)
setx('big_side_screw_r2', 0.35, None)
# 托弹板 vs 抬弹板
sety('carrier_lifter', -0.51, None)
# 杠杆环段间齐平 → 全部 y ±0.005 互嵌
for i in range(1, 11):
    n = 'lever_loop_%d' % i
    els[n]['from'][1] = r4(els[n]['from'][1] - 0.005)
    els[n]['to'][1] = r4(els[n]['to'][1] + 0.005)
# 瞄准镜管/目镜/镜环
setz('scope_eye_a', 0.47, None)
setz('scope_eye_b', 0.47, None)
setz('mount_ring_rear_a', None, 1.43)
setz('mount_ring_rear_b', None, 1.43)
# 准星刀嵌入基座
sety('front_sight_blade', 0.18, None)
# 弹仓帽螺钉嵌进帽
setz('mag_cap_screw', None, -9.95)
# 护木防滑条嵌进护木
setx('forearm_check_left', None, -0.23)
setx('forearm_check_right', 0.23, None)
# 瞄镜后座嵌进机匣桥
sety('mount_base_rear', 0.23, None)

json.dump(d, open(SRC, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('pass2 saved', os.path.getsize(SRC))
# 复查特殊 Z 生效
for n in ('cartridge_case_a', 'cartridge_bullet_a', 'shell_body_a', 'shell_rim'):
    e = els[n]
    print(n, e['from'], e['to'])
