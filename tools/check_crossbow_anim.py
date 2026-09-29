#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""crossbow 动画自检：契约 + Java 契约 + 弦缆运动学 + 镜像 + 隐藏约定 + 已知偏差钉死。

跑法：python tools/check_crossbow_anim.py        （在 F:/mcmod 下）

十字弩是本项目唯一「弓臂—凸轮—弦—副缆」四件套联动的武器，光看动画文件
「有没有关键帧」抓不到它的病：弦是一根**长度恒定**的刚体，拉弦靠弓臂屈曲 +
凸轮自转，弦心必须落到牙上。任何一处写错，游戏里就是「弦从弩里穿出去」「弦
拉伸」「轮子乱转」而日志一声不响。所以这里查六件事，任何一件不过就非零退出：

  1. 契约   —— 动画里出现的每个骨骼名必须在 geo 里真实存在；关键帧时刻 ≤ 段长；
                loop 标记正确（只有 static_idle 是循环）。
  2. Java 契约 —— CrossbowItem.java 的 clip 名 / 时长常量 / 触发名唯一性 /
                AIM_TIME 与 ADS 段长 / display 角度缩放与物品模型一致。
  3. 弦缆运动学 —— 逐剪辑解算骨链，验证：
                · 弦心（两半弦在 x=0 的交点）在 draw 末帧落在牙枢轴（解算器 LATCH_Z）±0.05u；
                · 静止态弦心在牙**前方**（z 至少差 1u），即没拉弦；
                · 满弦屈曲 ≥15°、凸轮自转 ±140°、满弦点齿轮比 = 140/19.46；
                · 弦/缆半段长恒定：这些骨不得出现 position 通道（屈曲不许靠位移伪造）。
  4. 镜像 —— 左右成对部件（弓臂/凸轮/弦/副缆）逐关键帧角度相等且反号。按 mod 360 比，
                所以「−360°」与「0°」是同一姿态，不会误报。
  5. 隐藏与缩放约定 —— 只有 hand_l / bolt_loaded 允许出现 scale，且只能取 0（藏）或
                1（现身）；其它骨一旦被 scale 就是整机缩放，属铁律禁止项。
  6. 已知偏差钉死 —— 台账 art/crossbow/DELIVERY.md §已知偏差 里在案的几何偏差，在这里
                写成常量：值一旦变化（修好了，或者又漂了）都必须有人来更新两处。
"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO = os.path.join(HERE, 'art', 'crossbow', 'crossbow.geo.json')
ANIM = os.path.join(HERE, 'art', 'crossbow', 'crossbow.animation.json')
ITEM_JAVA = os.path.join(HERE, 'src', 'main', 'java', 'com', 'apocalypse', 'zombies',
                         'item', 'CrossbowItem.java')
ITEM_MODEL = os.path.join(HERE, 'src', 'main', 'resources', 'assets', 'apocalypse_zombies',
                          'models', 'item', 'crossbow.json')
SOUNDS_JAVA = os.path.join(HERE, 'src', 'main', 'java', 'com', 'apocalypse', 'zombies',
                           'registry', 'ModSounds.java')
SOUNDS_JSON = os.path.join(HERE, 'src', 'main', 'resources', 'assets', 'apocalypse_zombies',
                           'sounds.json')
CLIENT_DIR = os.path.join(HERE, 'src', 'main', 'java', 'com', 'apocalypse', 'zombies', 'client')

LOOPING = {'static_idle'}
GUN_PAIRS = [('limb_l', 'limb_r'), ('cam_l', 'cam_r'),
             ('string_l', 'string_r'), ('cable_l', 'cable_r')]
CAM_SPIN = 140.0                # 拉满时凸轮自转角（生成器 CAM_SPIN）
CAM_GEAR = CAM_SPIN / 19.46     # 满弦点 凸轮/弓臂 比值
TOL_LATCH = 0.05                # 弦心到牙枢轴，单位 u
TOL_GEAR = 0.02                 # 满弦点齿轮比相对误差
TOL_MIRROR = 1e-6               # 镜像：写出层必须精确反号（mod 360 之后）
MIN_FLEX = 15.0                 # draw 段要求的最小满弦屈曲（度）
HIDDEN = ('hand_l', 'bolt_loaded')

# 台账 art/crossbow/DELIVERY.md §已知偏差 在案的值，钉成常量：对不上就说明有人动过，两处都要更新。
KNOWN = {
    # 偏差 #7（1.1.34 已修）留下的哨兵：牙的实体**不得**落在弦的扫掠区间内。
    # 修前牙体在 z −4.40..−4.00 ⇒ True（弦穿过牙体）；现在勾爪整体位于落点之后 ⇒ 必须 False。
    '弦扫掠穿过牙体': False,
}

fails = []
warns = []


# ---------------------------------------------------------------- 骨链

def load_geo():
    g = json.load(open(GEO, encoding='utf-8'))['minecraft:geometry'][0]
    bones = {}
    for b in g['bones']:
        bones[b['name']] = {'pivot': b.get('pivot', [0, 0, 0]),
                            'parent': b.get('parent'),
                            'cubes': b.get('cubes', [])}
    return g, bones


def rot_axis(point, axis, deg):
    x, y, z = point
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    if axis == 0:
        return [x, y * c - z * s, y * s + z * c]
    if axis == 1:
        return [x * c + z * s, y, -x * s + z * c]
    return [x * c - y * s, x * s + y * c, z]


def wrap180(a):
    """把角度差折算到 (−180, 180]，让 −360° 与 0° 视为同一姿态。"""
    while a > 180.0:
        a -= 360.0
    while a <= -180.0:
        a += 360.0
    return a


def chan_at(chans, chan, t):
    keys = chans.get(chan)
    if not keys:
        return [0.0, 0.0, 0.0]
    items = sorted(keys.items(), key=lambda kv: float(kv[0]))
    # 关键帧时刻集合是逐帧对齐的（生成器逐帧写出），所以取「≤t 的最后一个」
    prev = None
    for k, v in items:
        if float(k) <= t + 1e-9:
            prev = v['post']['vector']
        else:
            break
    return list(prev if prev is not None else items[0][1]['post']['vector'])


def bone_xform(bones, clip_bones, name, t, memo):
    """把 name 骨在 t 时刻的变换做成一个函数：模型坐标点 → 该帧的模型坐标点。

    单轴旋转在本模型里是常态（弓臂/凸轮/弦绕 Y、body 绕 X），旋转次序无关，
    因此按「先 X 后 Y 再 Z」逐个作用即可，与 model_preview 的软渲染一致。
    """
    if name in memo:
        return memo[name]
    b = bones[name]
    par = b['parent']
    P = (lambda p: p) if par is None else bone_xform(bones, clip_bones, par, t, memo)
    chans = clip_bones.get(name, {})
    pos = chan_at(chans, 'position', t)
    rot = chan_at(chans, 'rotation', t)
    pivot = b['pivot']

    def f(p, pivot=pivot, pos=pos, rot=rot, P=P):
        w = [p[0] - pivot[0], p[1] - pivot[1], p[2] - pivot[2]]
        for axis, deg in enumerate(rot):
            if abs(deg) > 1e-12:
                w = rot_axis(w, axis, deg)
        return P([pivot[0] + w[0] + pos[0], pivot[1] + w[1] + pos[1], pivot[2] + w[2] + pos[2]])

    memo[name] = f
    return f


def keyframe_times(clip):
    ts = set()
    for chans in clip['bones'].values():
        for keys in chans.values():
            ts.update(float(k) for k in keys)
    return sorted(ts)


def rest_point(bone_cubes, want_y=None):
    """取一根骨里某个立方体的指定端点（默认整根骨包围盒的最小 x/z 角）。"""
    xs = [c['origin'][0] for c in bone_cubes] + [c['origin'][0] + c['size'][0] for c in bone_cubes]
    ys = [c['origin'][1] for c in bone_cubes] + [c['origin'][1] + c['size'][1] for c in bone_cubes]
    zs = [c['origin'][2] for c in bone_cubes] + [c['origin'][2] + c['size'][2] for c in bone_cubes]
    return [min(xs), want_y if want_y is not None else (min(ys) + max(ys)) / 2.0, (min(zs) + max(zs)) / 2.0]


def cube_bbox(cubes):
    xs = [c['origin'][0] for c in cubes] + [c['origin'][0] + c['size'][0] for c in cubes]
    ys = [c['origin'][1] for c in cubes] + [c['origin'][1] + c['size'][1] for c in cubes]
    zs = [c['origin'][2] for c in cubes] + [c['origin'][2] + c['size'][2] for c in cubes]
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


# ---------------------------------------------------------------- 1. 契约

def check_contract(geo, bones, anim):
    for clip, c in anim.items():
        L = c['animation_length']
        if bool(c.get('loop')) != (clip in LOOPING):
            fails.append(f'契约: {clip} loop={c.get("loop")}，期望 {clip in LOOPING}')
        for b, chans in c['bones'].items():
            if b not in bones:
                fails.append(f'契约: {clip} 动了不存在的骨骼 {b}')
            for ch, keys in chans.items():
                if ch not in ('rotation', 'position', 'scale'):
                    fails.append(f'契约: {clip}.{b} 未知通道 {ch}')
                for t in keys:
                    if float(t) > L + 1e-6:
                        fails.append(f'契约: {clip}.{b}.{ch} 关键帧 {t} 超过段长 {L}')


# ---------------------------------------------------------------- 2. Java 契约

def consts_of(src):
    out = {}
    for _kind, name, value in re.findall(
            r'static final (String|int|float|double)\s+(\w+)\s*=\s*"?([^";]+?)"?\s*;', src):
        out[name] = value.strip().rstrip('FfDd')
    return out


def check_java_contract(anim):
    src = open(ITEM_JAVA, encoding='utf-8').read()
    cs = consts_of(src)
    if not cs:
        fails.append('java: 没能从 CrossbowItem.java 解析出任何常量，正则失配')

    for name, value in cs.items():
        if name.startswith('ANIM_') and value not in anim:
            fails.append(f'java: {name} = "{value}"，动画文件里没有这段 clip')

    for const, clip in (('SHOOT_TICKS', 'shoot'), ('DRAW_TICKS', 'draw'),
                        ('RELOAD_TACTICAL_TICKS', 'reload_tactical')):
        got = cs.get(const)
        if got is None or clip not in anim:
            continue
        want = math.ceil(anim[clip]['animation_length'] * 20 - 1e-9)
        if int(float(got)) != want:
            fails.append(f'java: {const} = {got}，但 {clip} 长 {anim[clip]["animation_length"]}s = {want} ticks')

    # AIM_TIME 必须等于 ADS 两段的时长，否则瞄准过渡会被截断
    aim = cs.get('AIM_TIME')
    if aim is not None:
        for clip in ('ADS_up', 'ADS_down'):
            if clip in anim and abs(float(aim) - anim[clip]['animation_length']) > 1e-6:
                fails.append(f'java: AIM_TIME = {aim}s，但 {clip} 长 {anim[clip]["animation_length"]}s')

    triggers = [v for k, v in cs.items() if k.startswith('TRIGGER_')]
    for t in set(triggers):
        if triggers.count(t) > 1:
            fails.append(f'java: 触发名 "{t}" 重复定义')
    for k, v in cs.items():
        if k.startswith('TRIGGER_') and v not in anim:
            fails.append(f'java: {k} = "{v}"，动画里没有这段 clip，触发会静默无效')

    # display 角度/缩放必须与物品模型一致（否则第一人称朝向对不上）
    item = json.load(open(ITEM_MODEL, encoding='utf-8'))
    fp = item['display']['firstperson_righthand']
    for const, idx, label in (('DISPLAY_PITCH', 0, 'pitch'), ('DISPLAY_YAW', 1, 'yaw')):
        if const in cs and abs(float(cs[const]) - fp['rotation'][idx]) > 1e-6:
            fails.append(f'java: {const} = {cs[const]}°，物品模型 firstperson rotation[{idx}] = '
                         f'{fp["rotation"][idx]}°（{label} 对不上）')
    if len(set(fp['scale'])) != 1:
        fails.append(f'java: firstperson scale 三轴不等 {fp["scale"]}，会把武器拉歪')
    eff = fp['scale'][0] * float(cs.get('FIRST_PERSON_SCALE', 1))
    if not 0.6 <= eff <= 1.4:
        fails.append(f'java: 第一人称有效缩放 = {fp["scale"][0]} × {cs.get("FIRST_PERSON_SCALE")} = '
                     f'{eff:.3f}，超出 0.6~1.4')

    # 瞄准镜契约：十字弩要的是**透明镜**，三条是一件事，动一条就会从另外两条里露出来。
    #   hasScopeOverlay() = false  ⇒ 右键不画任何镜，只剩原版准星（1.1.35 之前的状态）；
    #   sightStyle() = TELESCOPE   ⇒ 走 AWM 的黑镜筒分支，整屏被 SCOPE_DARKNESS 压黑，透明镜变黑镜；
    #   hidesModelWhileAimed() = true ⇒ 举镜过半把弩和双手藏掉，而透明镜的前提正是「看得见世界和弩」。
    sight = re.search(r'public\s+boolean\s+hasScopeOverlay\s*\(\s*\)\s*\{\s*return\s+(true|false)\s*;', src)
    style = re.search(r'public\s+GunItem\.SightStyle\s+sightStyle\s*\(\s*\)\s*\{\s*return\s+'
                      r'GunItem\.SightStyle\.(\w+)\s*;', src)
    hides = re.search(r'public\s+boolean\s+hidesModelWhileAimed\s*\(\s*\)\s*\{\s*return\s+(true|false)\s*;', src)
    if sight is None:
        fails.append('java: 没找到 hasScopeOverlay() 的字面返回，透明镜契约无法核对')
    elif sight.group(1) != 'true':
        fails.append('java: hasScopeOverlay() = false —— 右键不画十字镜，只剩原版准星')
    if style is None:
        fails.append('java: 没找到 sightStyle() = GunItem.SightStyle.X 的字面返回')
    elif style.group(1) != 'CLEAR_SIGHT':
        fails.append(f'java: sightStyle() = {style.group(1)} —— 十字弩要的是 CLEAR_SIGHT（透明镜），'
                     f'TELESCOPE 会落进 AWM 的全屏压黑分支')
    if hides is None:
        fails.append('java: 没找到 hidesModelWhileAimed() 的字面返回')
    elif hides.group(1) != 'false':
        fails.append('java: hidesModelWhileAimed() = true —— 举镜过半把弩和手藏掉，透明镜就白做了')

    # 客户端必须真的认得这个镜种：转发与分派都要在，否则上面三条只是摆设。
    # GunAimState 只负责把问题转给手持枪，所以查的是 sightStyle 转发本身；画法在 ClientEvents。
    client_src = {}
    for name, needles in (('GunAimState.java', ('sightStyle',)),
                          ('ClientEvents.java', ('CLEAR_SIGHT', 'renderClearSight'))):
        text = open(os.path.join(CLIENT_DIR, name), encoding='utf-8').read()
        client_src[name] = text
        for needle in needles:
            if needle not in text:
                fails.append(f'client: {name} 里没有 {needle}，镜种接不上（十字镜画不出来）')

    # 观感同源：用户看图定稿的方案 B 画在 tools/sight_mock.py 里，游戏里画在 ClientEvents 里。
    # 两处必须逐项相等 —— 颜色或透明度改一个数字，肉眼在游戏里根本看不出来，但和定稿的就不是一件东西了。
    events = client_src['ClientEvents.java']
    mock = open(os.path.join(HERE, 'tools', 'sight_mock.py'), encoding='utf-8').read()
    NUM = r'(0x[0-9A-Fa-f]+|[0-9]+(?:\.[0-9]+)?)'
    java_const = {}
    for m in re.finditer(r'private static final (?:int|float) (\w+) = ' + NUM + r'F?;', events):
        java_const[m.group(1)] = m.group(2)

    def mock_nums(prefix):
        m = re.search(r'^%s\s*=\s*\(?\s*([0-9xXa-fA-F.,\s]+?)\s*\)?\s*(?:#.*)?$' % re.escape(prefix), mock, re.M)
        if m is None:
            return None
        return [int(p.strip(), 0) if p.strip().lower().startswith('0x') else float(p.strip())
                for p in m.group(1).split(',')]

    def packed(colour):
        return (int(colour[0]) << 16) | (int(colour[1]) << 8) | int(colour[2])

    core = mock_nums('CORE')
    halo = mock_nums('HALO')
    dot = mock_nums('DOT')
    lens = mock_nums('LENS')
    core_a = mock_nums('CORE_A, HALO_A, DOT_A')
    lens_a = mock_nums('LENS_A, RIM_A')
    radius_f = mock_nums('RADIUS_FRACTION')
    arm_f = mock_nums('ARM_FRACTION')
    if None in (core, halo, dot, lens, core_a, lens_a, radius_f, arm_f):
        fails.append('mock: tools/sight_mock.py 的常量块认不出来，观感同源无法核对')
    else:
        # (说明, mock 侧的值, Java 侧常量名)
        pairs = [('镜半径系数', radius_f[0], 'SCOPE_RADIUS_FRACTION'),
                 ('十字臂长系数', arm_f[0], 'RETICLE_ARM_FRACTION'),
                 ('暗芯颜色', packed(core), 'RETICLE_CORE_COLOUR'),
                 ('浅晕颜色', packed(halo), 'RETICLE_HALO_COLOUR'),
                 ('镜片颜色', packed(lens), 'CLEAR_LENS_COLOUR'),
                 ('暗芯透明度', core_a[0], 'RETICLE_CORE_ALPHA'),
                 ('浅晕透明度', core_a[1], 'RETICLE_HALO_ALPHA'),
                 ('镜片透明度', lens_a[0], 'CLEAR_LENS_ALPHA'),
                 ('镜圈透明度', lens_a[1], 'CLEAR_RIM_ALPHA')]
        for label, want, name in pairs:
            raw = java_const.get(name)
            if raw is None:
                fails.append(f'java: 找不到常量 {name}，观感同源无法核对')
                continue
            got = float(int(raw, 16)) if raw.lower().startswith('0x') else float(raw)
            if abs(float(want) - got) > 1e-6:
                fails.append(f'观感不同源: {label} —— mock={want} 而 {name}={raw}')
        # 红心：Java 侧沿用望远镜那条 (0xE6·p)<<24 | 0xB02020，mock 记 0.90 / 0xB02020，是同一条
        if packed(dot) != 0xB02020 or '0xB02020' not in events:
            fails.append('观感不同源: 红心颜色对不上（mock 0x%06X / Java 里没有 0xB02020）' % packed(dot))
        elif abs(core_a[2] - 0xE6 / 255.0) > 0.01:
            fails.append(f'观感不同源: 红心透明度 mock={core_a[2]} 而 Java 0xE6/255={0xE6 / 255.0:.3f}')
    return src


def check_sounds(src):
    """音效表引用的每个 SoundEvent 必须有定义、有登记、有 ogg。"""
    ids = dict(re.findall(r'RegistryObject<SoundEvent>\s+(\w+)\s*=\s*sound\("([^"]+)"\)',
                          open(SOUNDS_JAVA, encoding='utf-8').read()))
    registered = json.load(open(SOUNDS_JSON, encoding='utf-8'))
    sound_root = os.path.join(HERE, 'src', 'main', 'resources', 'assets',
                              'apocalypse_zombies', 'sounds')
    files = set()
    for _root, _dirs, fs in os.walk(sound_root):
        files.update(fs)
    used = {}
    for m in re.finditer(r'(\w+_SOUNDS)\s*=\s*Map\.of\((.*?)\);', src, re.S):
        used[m.group(1)] = re.findall(r'\d+\s*,\s*ModSounds\.(\w+)', m.group(2))
    if not used:
        fails.append('音效: CrossbowItem.java 里没解析到任何 *_SOUNDS 时刻表（正则失配或表被删）')
    for table, names in used.items():
        for const in names:
            sid = ids.get(const)
            if sid is None:
                fails.append(f'音效: {table} 引用了 ModSounds 里不存在的 {const}')
                continue
            if sid not in registered:
                fails.append(f'音效: {sid}（{const}）没有登记在 sounds.json 里')
                continue
            for entry in registered[sid]['sounds']:
                name = os.path.basename(entry['name'].split(':')[-1]) + '.ogg'
                if name not in files:
                    fails.append(f'音效: {sid} 指向的 {name} 不存在')


# ---------------------------------------------------------------- 3/4/5/6. 运动学 / 镜像 / 约定 / 偏差

def check_kinematics(bones, anim):
    lbb = cube_bbox(bones['latch']['cubes'])
    latch_center = [(lbb[0] + lbb[3]) / 2.0, (lbb[1] + lbb[4]) / 2.0, (lbb[2] + lbb[5]) / 2.0]
    latch_pivot = list(bones['latch']['pivot'])
    # 弦心 = 两半弦在 x=0 的公共端点（弦骨 pivot 在凸轮心，弦止于 x=0）
    sbb = cube_bbox(bones['string_l']['cubes'])
    string_tip = [(sbb[0] + sbb[3]) / 2.0, (sbb[1] + sbb[4]) / 2.0, (sbb[2] + sbb[5]) / 2.0]
    string_tip[0] = 0.0

    report = {}
    for clip, c in anim.items():
        memo = {}
        worst = 0.0
        for t in keyframe_times(c):
            L = bone_xform(bones, c['bones'], 'latch', t, memo)
            S = bone_xform(bones, c['bones'], 'string_l', t, memo)
            worst = max(worst, math.dist(L(latch_center), S(string_tip)))
        report[f'{clip} 弦心→牙实体中心 最大距离'] = round(worst, 4)

    # 静止态：弦心必须在牙实体**前方**（没拉弦）
    memo = {}
    S = bone_xform(bones, anim['static_idle']['bones'], 'string_l', 0.0, memo)
    L = bone_xform(bones, anim['static_idle']['bones'], 'latch', 0.0, memo)
    rest_gap = L(latch_center)[2] - S(string_tip)[2]
    report['static_idle 弦心在牙实体前 (u)'] = round(rest_gap, 4)
    if rest_gap < 1.0:
        fails.append(f'运动学: static_idle 弦心在牙实体后方 {rest_gap:.3f}u —— 静止态像是没拉到位')

    # draw 末帧：弦心必须落在牙的枢轴点（解算器 LATCH_Z）
    draw = anim['draw']
    t_end = max(keyframe_times(draw))
    memo = {}
    S = bone_xform(bones, draw['bones'], 'string_l', t_end, memo)
    L = bone_xform(bones, draw['bones'], 'latch', t_end, memo)
    d_end = math.dist(S(string_tip), L(latch_pivot))
    report['draw 末帧 弦心→牙枢轴'] = round(d_end, 4)
    report['draw 末帧 弦心→牙实体中心'] = round(math.dist(S(string_tip), L(latch_center)), 4)
    if d_end > TOL_LATCH:
        fails.append(f'运动学: draw 末帧弦心离牙枢轴 {d_end:.3f}u（>{TOL_LATCH}u）—— 拉满没落在牙上')

    # 弦在 draw 段的行程是否扫过牙实体（哨兵：必须 False，见 KNOWN）
    lo, hi = lbb[2], lbb[5]
    report['弦扫掠穿过牙体'] = bool(lo >= min(string_tip[2], latch_pivot[2])
                             and hi <= max(string_tip[2], latch_pivot[2]))

    # ① 弦道走廊：弦自静止位扫到落点、在弦高带内、过 x=0 的路径上不得有实体。
    #    箭道内壁（|x| ≥ 0.16）本就是让弦藏进去的，所以只查「跨 x=0」的块。
    band0, band1 = sbb[1], sbb[4]
    z_lo = min(string_tip[2], latch_pivot[2]) + 0.05
    z_hi = max(string_tip[2], latch_pivot[2])
    offenders = []
    for bname, b in bones.items():
        if bname in ('string_l', 'string_r', 'cable_l', 'cable_r') + HIDDEN:
            continue
        for c in b['cubes']:
            x0, x1 = c['origin'][0], c['origin'][0] + c['size'][0]
            y0, y1 = c['origin'][1], c['origin'][1] + c['size'][1]
            z0, z1 = c['origin'][2], c['origin'][2] + c['size'][2]
            if not x0 < 0.0 < x1:
                continue
            if min(y1, band1) - max(y0, band0) <= 1e-6:
                continue
            if min(z1, z_hi) - max(z0, z_lo) <= 1e-6:
                continue
            offenders.append(f'{bname}[z {z0:.2f}..{z1:.2f}, y {y0:.2f}..{y1:.2f}]')
    report['弦道走廊 越界块'] = offenders if offenders else '无'
    if offenders:
        fails.append('运动学: 弦道走廊内有实体（弦会穿模）—— ' + '；'.join(offenders))

    # ② 弦被卡爪咬住（不是悬在空中）：牙必须有一块的前脸落在弦后脸 ±0.05u
    string_rear = latch_pivot[2] + (band1 - band0) / 2.0
    report['弦后脸 z'] = round(string_rear, 4)
    cand = [c['origin'][2] for c in bones['latch']['cubes']
            if c['origin'][0] < 0.0 < c['origin'][0] + c['size'][0]]
    gap = min((abs(z0 - string_rear) for z0 in cand), default=None)
    report['弦后脸↔爪前脸 差'] = round(gap, 4) if gap is not None else '牙无跨中块'
    if gap is None or gap > 0.05:
        fails.append(f'运动学: 牙没有块的前脸落在弦后脸（差 {gap}u）—— 拉满时弦没被咬住')

    # 弦缆长度恒定靠骨骼转动：这些骨不许有位移通道
    for clip, c in anim.items():
        for b, chans in c['bones'].items():
            if 'position' in chans and b in ('limb_l', 'limb_r', 'string_l', 'string_r',
                                             'cable_l', 'cable_r'):
                fails.append(f'约定: {clip} 里 {b} 有 position 通道 —— 弦缆长度恒定不许靠位移伪造')

    # 镜像：左右成对，角度相等反号（mod 360 之后比，−360°≡0°）
    for clip, c in anim.items():
        for bl, br in GUN_PAIRS:
            for chan in ('rotation', 'position'):
                kl, kr = c['bones'].get(bl, {}).get(chan, {}), c['bones'].get(br, {}).get(chan, {})
                for t in sorted(set(kl) | set(kr), key=float):
                    vl = kl.get(t, {}).get('post', {}).get('vector')
                    vr = kr.get(t, {}).get('post', {}).get('vector')
                    if vl is None or vr is None:
                        one = vl if vl is not None else vr
                        # 旋转按 mod 360 折算：−360° 是「占位不转」，不是缺通道
                        live = [abs(wrap180(v)) for v in one] if chan == 'rotation' else [abs(v) for v in one]
                        if max(live) > 1e-6:
                            missing = br if vl is not None else bl
                            fails.append(f'镜像: {clip} {bl}/{br} 在 {t}s 只有一侧有 {chan} 通道（{missing} 缺）')
                        continue
                    if chan == 'position':
                        want = [-vr[0], vr[1], vr[2]]
                        bad = max(abs(vl[i] - want[i]) for i in range(3))
                    else:
                        want = [vr[0], -vr[1], -vr[2]]
                        bad = max(abs(wrap180(vl[i] - want[i])) for i in range(3))
                    if bad > TOL_MIRROR:
                        fails.append(f'镜像: {clip} {bl}.{chan}@{t}s = {vl}，应为 {want}（镜像 {br}）')

    # 齿轮比只在满弦点成立：凸轮是偏心轮，中段比值随弦角变化，不该拿来当常量
    limb = draw['bones'].get('limb_r', {}).get('rotation', {})
    cam = draw['bones'].get('cam_r', {}).get('rotation', {})
    t_max = max(limb, key=lambda t: abs(limb[t]['post']['vector'][1]))
    a = limb[t_max]['post']['vector'][1]
    g = cam[t_max]['post']['vector'][1]
    report['draw 满弦点 弓臂/凸轮'] = (round(a, 3), round(g, 3))
    if abs(a) < MIN_FLEX:
        fails.append(f'运动学: 满弦屈曲只有 {abs(a):.2f}°（draw 段要求 ≥{MIN_FLEX}°）')
    if abs(abs(g) - CAM_SPIN) > 0.01:
        fails.append(f'运动学: 满弦凸轮自转 {g}°，应为 ±{CAM_SPIN}°')
    if abs(a) > 1e-9:
        ratio = g / a
        if abs(ratio - CAM_GEAR) / CAM_GEAR > TOL_GEAR:
            fails.append(f'运动学: 满弦点 凸轮/弓臂 = {ratio:.3f}，应为 {CAM_GEAR:.3f}')
    return report


def check_conventions(anim):
    """只有 hand_l / bolt_loaded 允许 scale，且只能 0（藏）或 1（现身）。"""
    for clip, c in anim.items():
        for b, chans in c['bones'].items():
            if 'scale' not in chans:
                continue
            vals = {tuple(round(x, 6) for x in v['post']['vector']) for v in chans['scale'].values()}
            if b in HIDDEN:
                bad = sorted(v for v in vals if v not in ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)))
                if bad:
                    fails.append(f'约定: {clip} 里 {b} 的 scale 出现 {bad} —— 隐藏件只允许 0（藏）或 1（现身）')
            else:
                fails.append(f'约定: {clip} 里 {b} 出现 scale {sorted(vals)} —— 除隐藏件外禁止缩放（铁律）')


def check_known_deviations(report):
    """把台账在案的几何偏差钉成常量：对不上就必须有人来更新台账与这里。"""
    for key, pinned in KNOWN.items():
        got = report.get(key)
        if got is None:
            fails.append(f'偏差: 报表里缺 {key}')
            continue
        if isinstance(pinned, bool):
            if bool(got) != pinned:
                fails.append(f'偏差: {key} 由 {pinned} 变成 {got} —— 台账 §已知偏差 与这里都要更新')
        elif abs(got - pinned) > 1e-3:
            fails.append(f'偏差: {key} = {got}，台账钉的是 {pinned} —— 修好了还是又漂了？请更新两处')


# ---------------------------------------------------------------- main

def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    geo, bones = load_geo()
    anim = json.load(open(ANIM, encoding='utf-8'))['animations']

    check_contract(geo, bones, anim)
    src = check_java_contract(anim)
    check_sounds(src)
    report = check_kinematics(bones, anim)
    check_conventions(anim)
    check_known_deviations(report)

    print('== 弦缆运动学 ==')
    for k, v in report.items():
        print(f'  {k:34s} {v}')
    print()
    print(f'clips: {len(anim)}  bones/clip: {sorted({len(c["bones"]) for c in anim.values()})}')
    print(f'已知偏差钉死 {len(KNOWN)} 条（台账 art/crossbow/DELIVERY.md §已知偏差）')
    if warns:
        print('\n'.join('WARN ' + w for w in warns))
    if fails:
        print('\n'.join('FAIL ' + f for f in fails))
        return 1
    print('OK  契约 / Java 契约 / 音效 / 弦缆运动学 / 镜像 / 约定 / 已知偏差 全部通过')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
