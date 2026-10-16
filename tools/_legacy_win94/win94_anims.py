# -*- coding: utf-8 -*-
"""win94 离线写 7 个莫辛命名动画（杠杆枪专用设计）。
杠杆循环：lever +58°开→bolt 后移 0.55→carrier 升 0.12→hammer 上 32°(保持)→复位。
换弹：机匣右侧装弹门侧向进弹（管仓），reload_empty 4 发+收尾循环，reload_tactical 3 发不循环。
"""
import json, uuid, os

SRC = os.path.join(os.path.dirname(__file__), '..', 'win94.bbmodel')
d = json.load(open(SRC, encoding='utf-8'))

BONE = {
    'root': '23c23070-cfdb-7a7b-035c-dd92cc530ba7',
    'barrel': '56f2d43b-947a-c23a-78d1-daf4be94a3aa',
    'forearm': '1b3334c7-8525-a959-2aea-955a6cc518d8',
    'receiver': '55515c01-b864-20c7-e148-6e9fffa7c780',
    'bolt': 'a2256f7f-43c8-cfab-1f71-de18d566bbd4',
    'hammer': 'e7253188-7846-1bd8-2c9d-78886f5be88c',
    'lever': '358285ee-e378-9616-8760-22a324b10d94',
    'carrier': 'a173abbe-e5a9-1940-6218-03bc61fdc316',
    'cartridge': '52483b72-4b7b-46b6-a4ff-e72083fbc6d2',
    'spent_shell': '363dc562-15b3-f7ca-46ea-232018f4c814',
    'trigger': '0ede51a0-14f0-b188-c9fe-ed1292d7c8fa',
    'scope': 'e9d23beb-946a-d6ef-45cf-291e1675e940',
    'stock': 'e9dd5877-6996-ab73-6b2f-ba3290ea3d92',
    'camera': '49bfc281-db1a-9edf-2dc2-40e9ef484784',
    'constraint': '52e14d07-614a-d810-1c77-78530da05e19',
    'move': '5e4f5118-b806-009e-8a66-8fe7fd94bf56',
    'body': '2d30a3f0-2f5b-f94f-1fd1-73a64e603685',
}

def kf(channel, time, x, y, z, interp='catmullrom'):
    return {'channel': channel, 'color': -1,
            'data_points': [{'x': str(x), 'y': str(y), 'z': str(z)}],
            'interpolation': interp, 'time': round(time, 3), 'uuid': str(uuid.uuid4())}

def animator(bone, kfs):
    return {'keyframes': kfs, 'name': bone, 'quaternion_interpolation': False,
            'rotation_global': False, 'type': 'bone'}

def anim(name, length, loop, spec):
    ans = {}
    for bone, kfs in spec.items():
        ans[BONE[bone]] = animator(bone, kfs)
    return {'anim_time_update': '', 'animators': ans, 'blend_weight': '',
            'length': length, 'loop': loop, 'loop_delay': '', 'name': name,
            'override': False, 'path': '', 'saved': True, 'scope': 0,
            'selected': False, 'snapping': 24, 'start_delay': '',
            'uuid': str(uuid.uuid4())}

# ---------- 1. static_idle (loop 2s) ----------
idle = anim('static_idle', 2.0, 'loop', {
    'move': [kf('position', 0, 0, 0, 0), kf('position', 1.0, 0, -0.012, 0), kf('position', 2.0, 0, 0, 0)],
    'body': [kf('rotation', 0, 0.7, 0, 0), kf('rotation', 1.0, 0, 0.35, 0.4), kf('rotation', 2.0, 0.7, 0, 0)],
})

# ---------- 2. draw (once 0.9s) ----------
draw = anim('draw', 0.9, 'once', {
    'body': [kf('rotation', 0, 25, -18, 0), kf('rotation', 0.55, -4, 4, 0), kf('rotation', 0.9, 0, 0, 0)],
    'move': [kf('position', 0, 0, -0.55, 0.25), kf('position', 0.55, 0, 0.05, -0.03), kf('position', 0.9, 0, 0, 0)],
})

# ---------- 3. shoot (once 0.6s) 含击锤落下 ----------
shoot = anim('shoot', 0.6, 'once', {
    'hammer': [kf('rotation', 0, 32, 0, 0), kf('rotation', 0.07, 0, 0, 0, 'linear')],
    'body': [kf('rotation', 0, 0, 0, 0), kf('rotation', 0.06, 8, 0, 0), kf('rotation', 0.25, -2.5, 0, 0), kf('rotation', 0.6, 0, 0, 0)],
    'move': [kf('position', 0, 0, 0, 0), kf('position', 0.06, 0, 0.03, 0.16), kf('position', 0.25, 0, -0.01, -0.03), kf('position', 0.6, 0, 0, 0)],
})

# ---------- 4. bolt (once 1.1s) 杠杆全循环 ----------
bolt = anim('bolt', 1.1, 'once', {
    'lever': [kf('rotation', 0, 0, 0, 0), kf('rotation', 0.32, 58, 0, 0), kf('rotation', 0.52, 58, 0, 0), kf('rotation', 0.85, 0, 0, 0), kf('rotation', 1.1, 0, 0, 0)],
    'bolt': [kf('position', 0, 0, 0, 0), kf('position', 0.12, 0, 0, 0.06), kf('position', 0.5, 0, 0, 0.55), kf('position', 0.58, 0, 0, 0.55), kf('position', 0.88, 0, 0, 0), kf('position', 1.1, 0, 0, 0)],
    'hammer': [kf('rotation', 0.05, 0, 0, 0), kf('rotation', 0.5, 32, 0, 0), kf('rotation', 1.1, 32, 0, 0)],
    'carrier': [kf('position', 0.15, 0, 0, 0), kf('position', 0.5, 0, 0.12, 0), kf('position', 0.6, 0, 0.12, 0), kf('position', 0.85, 0, 0, 0), kf('position', 1.1, 0, 0, 0)],
    'spent_shell': [kf('position', 0.15, 0, 0, 0), kf('position', 0.55, 0.35, 0.9, 0.4),
                    kf('position', 0.85, 0.7, 1.8, 0.9), kf('position', 1.1, 0.7, 1.8, 0.9),
                    kf('rotation', 0.15, 0, 0, 0), kf('rotation', 0.55, 140, 60, 30),
                    kf('rotation', 0.85, 260, 120, 60), kf('rotation', 1.1, 260, 120, 60)],
    'body': [kf('rotation', 0, 0, 0, 0), kf('rotation', 0.4, 2, 0, 0), kf('rotation', 0.85, 0, 0, 0), kf('rotation', 1.1, 0, 0, 0)],
})

# ---------- 5. reload_empty (once 4.4s) 侧门 4 发 + 收尾循环 ----------
# 装弹点位：右舷门外推入（x 0.95→0.12），逐发沿 z 前移
def load_rounds(t0, zs, out_x=0.95):
    kfs = []
    for i, z in enumerate(zs):
        ta = t0 + i * 0.5
        kfs += [kf('position', ta, out_x, -0.25, z),
                kf('position', ta + 0.28, 0.12, -0.28, z)]
    return kfs

re = anim('reload_empty', 4.4, 'once', {
    'body': [kf('rotation', 0, 0, 0, 0), kf('rotation', 0.55, -5, 8, 32), kf('rotation', 3.35, -5, 8, 32), kf('rotation', 3.95, 0, 0, 0), kf('rotation', 4.4, 0, 0, 0)],
    'cartridge': load_rounds(0.6, [-0.5, -0.3, -0.1, 0.1]) + [
        kf('position', 2.9, 0, 0, 0), kf('position', 4.4, 0, 0, 0)],
    # 收尾杠杆循环上膛
    'lever': [kf('rotation', 3.5, 0, 0, 0), kf('rotation', 3.8, 55, 0, 0), kf('rotation', 3.95, 55, 0, 0), kf('rotation', 4.25, 0, 0, 0), kf('rotation', 4.4, 0, 0, 0)],
    'bolt': [kf('position', 3.6, 0, 0, 0), kf('position', 3.92, 0, 0, 0.5), kf('position', 4.0, 0, 0, 0.5), kf('position', 4.28, 0, 0, 0), kf('position', 4.4, 0, 0, 0)],
    'carrier': [kf('position', 3.62, 0, 0, 0), kf('position', 3.92, 0, 0.12, 0), kf('position', 4.02, 0, 0.12, 0), kf('position', 4.28, 0, 0, 0), kf('position', 4.4, 0, 0, 0)],
    'hammer': [kf('rotation', 3.55, 0, 0, 0), kf('rotation', 4.0, 32, 0, 0), kf('rotation', 4.4, 32, 0, 0)],
})

# ---------- 6. reload_tactical (once 3.6s) 侧门 3 发，不循环 ----------
rt = anim('reload_tactical', 3.6, 'once', {
    'body': [kf('rotation', 0, 0, 0, 0), kf('rotation', 0.45, -3, 5, 18), kf('rotation', 2.6, -3, 5, 18), kf('rotation', 3.2, 0, 0, 0), kf('rotation', 3.6, 0, 0, 0)],
    'cartridge': load_rounds(0.5, [-0.3, -0.1, 0.1], out_x=0.9) + [
        kf('position', 2.4, 0, 0, 0), kf('position', 3.6, 0, 0, 0)],
})

# ---------- 7. inspect (once 2.6s) ----------
ins = anim('inspect', 2.6, 'once', {
    'move': [kf('position', 0, 0, 0, 0), kf('position', 0.55, 0.1, 0.15, 0.25),
             kf('position', 1.25, 0, 0.2, 0.3), kf('position', 1.95, 0.1, 0.15, 0.25),
             kf('position', 2.6, 0, 0, 0)],
    'body': [kf('rotation', 0, 0, 0, 0), kf('rotation', 0.55, 8, 25, 22),
             kf('rotation', 1.25, 8, -25, -22), kf('rotation', 1.95, 8, 25, 22),
             kf('rotation', 2.6, 0, 0, 0)],
})

d['animations'] = [idle, draw, shoot, bolt, re, rt, ins]
json.dump(d, open(SRC, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('animations written:', [(a['name'], a['loop'], a['length']) for a in d['animations']])
