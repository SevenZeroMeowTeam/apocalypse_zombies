#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 TaCZ 官方枪包 ai_awp 的动画**逐帧直译**到我们自己的模型骨架上。

输入  <游戏实例>/tacz/tacz_default_gun/assets/tacz/animations/ai_awp.animation.json
输出  art/awm/awm.animation.json（再 cp 到 resources/.../animations/）

换算规则（来源见 art/awm/tacz_ai_awp_reference.md）
  · 旋转        1:1 直抄（角度与模型尺寸无关）
  · 位移        ÷ S_GUN = 整枪长度比 57.07 / 23.97 = 2.381
  · 左右        不镜像（TaCZ 弹壳同样往 -X 抛，与我们模型同侧；实测 min_x=-42.34）
  · 时间轴      原样保留（TaCZ 已按 60 fps 烘焙，键就是真值）

骨对应（两套 rig 不是同一副，只有"枪"的骨骼可以逐字对搬）
  root                -> move        整枪
  gun_and_righthand   -> move        枪在手里的**额外**相对运动（inspect 用），与 root 叠加
  bolt_group+bolt_rotate -> bolt     我们只有一根栓骨，位移与旋转合到一根
  bullet_shell        -> casing      抛壳
  bullet_in_barrel    -> round_in    膛内子弹
  bullet.scale        -> round_in.scale
  mag_and_lefthand / magzine_and_bullet -> magazine
  其余（striker / 手 / camera / constraint / bullet_in_mag / *_pos / *view*）不搬，见文末 LEDGER

TaCZ 本体在 `bolt` 里**不抛壳**（弹壳是独立的世界实体，由它的引擎 spawn），
所以我们把 TaCZ `reload_empty` 里那段真实的抛壳曲线（2.55~3.033 s）**原样平移**到 `bolt` 的
0.55~1.033 s —— 数据仍是 TaCZ 的，只是换了时间窗。同理 `bolt` 里的上膛只用 TaCZ 自己的键。
"""
import json
import math
import os
import sys

SRC = ('C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2'
       '/tacz/tacz_default_gun/assets/tacz/animations/ai_awp.animation.json')
GEO = 'F:/mcmod/art/awm/awm.geo.json'
OUT = 'F:/mcmod/art/awm/awm.animation.json'

# TaCZ 整枪 Z 向长度 57.07u / 我们 23.97u
S_GUN = 57.07 / 23.97
INV_S = 1.0 / S_GUN

# ---------------------------------------------------------------- 通道映射
# (TaCZ bone, channel) -> (our bone, channel, kind)
#   rot/pos/scale = 直抄（pos 要 ÷S）
#   rot+ / pos+   = 叠加到已有通道上（与 root 合成）
MAP = {
    ('root', 'rotation'):             ('move', 'rotation', 'rot+'),
    ('root', 'position'):             ('move', 'position', 'pos+'),
    ('gun_and_righthand', 'rotation'): ('move', 'rotation', 'rot+'),
    ('gun_and_righthand', 'position'): ('move', 'position', 'pos+'),
    ('bolt_group', 'position'):       ('bolt', 'position', 'pos'),
    ('bolt_rotate', 'rotation'):      ('bolt', 'rotation', 'rot'),
    ('bullet_shell', 'rotation'):     ('casing', 'rotation', 'rot'),
    ('bullet_shell', 'position'):     ('casing', 'position', 'pos'),
    ('bullet_shell', 'scale'):        ('casing', 'scale', 'scale'),
    ('bullet_in_barrel', 'rotation'): ('round_in', 'rotation', 'rot'),
    ('bullet_in_barrel', 'position'): ('round_in', 'position', 'pos'),
    ('bullet', 'scale'):              ('round_in', 'scale', 'scale'),
    ('mag_and_lefthand', 'rotation'): ('magazine', 'rotation', 'rot'),
    ('mag_and_lefthand', 'position'): ('magazine', 'position', 'pos'),
    ('magzine_and_bullet', 'rotation'): ('magazine', 'rotation', 'rot'),
    ('magzine_and_bullet', 'position'): ('magazine', 'position', 'pos'),
}

# 每段动画里必须显式写死的"受管骨骼"，防止上一段的状态残留
# value = 该骨骼的 scale 规则：'hide' / 'show' / None（不写 scale，让 TaCZ 的键说话）
NEUTRAL = {
    'move': None,
    'bolt': None,
    'magazine': None,
    'casing': 'hide',
    'round_in': 'show',
    'mag_spare': 'hide',
    'mag_standard': 'show',
    'mag_extended_1': 'hide',
    'mag_extended_2': 'hide',
    'mag_extended_3': 'hide',
}

# TaCZ 的音效键 -> 我们的 SoundEvent id。
# 只映射我们真的随包分发的 22 个 ogg（见 art/awm/README.md「来源与许可」）；
# 没映射的（inspect 系列、draw/put_away 的 p23_sn_alpha50_*）直接丢弃，记进 LEDGER。
SOUND_MAP = {
    'tacz:ai_awp/awp_rechamber_out':          'awm_rechamber_out',
    'tacz:ai_awp/awp_rechember_ejectclick':   'awm_rechamber_ejectclick',   # TaCZ 原文件名拼错了 chemist
    'tacz:ai_awp/awp_rechamber_in':           'awm_rechamber_in',
    'tacz:ai_awp/awp_rechamber_end':          'awm_rechamber_end',
    'tacz:ai_awp/awp_reload_raise':           'awm_reload_raise',
    'tacz:ai_awp/awp_reload_rattle':          'awm_reload_rattle',
    'tacz:ai_awp/awp_reload_ejectclick':      'awm_reload_ejectclick',
    'tacz:ai_awp/awp_reload_magout':          'awm_reload_magout',
    'tacz:ai_awp/awp_reload_empty_fast_01_rattle': 'awm_reload_fast_rattle',
    'tacz:ai_awp/awp_reload_maghit':          'awm_reload_maghit',
    'tacz:ai_awp/awp_reload_magin':           'awm_reload_magin',
    'tacz:ai_awp/awp_reload_end':             'awm_reload_end',
    'tacz:ai_awp/awp_raise_first_rattle':     'awm_reload_empty_raise',
    'tacz:ai_awp/awp_reload_empty_magout':    'awm_reload_empty_magout',
    'tacz:ai_awp/awp_reload_empty_mag_drop':  'awm_reload_empty_mag_drop',
    'tacz:ai_awp/awp_reload_empty_rattle':    'awm_reload_empty_rattle',
    'tacz:ai_awp/awp_reload_empty_fast_maghit': 'awm_reload_empty_maghit',
    'tacz:ai_awp/awp_reload_empty_magin':     'awm_reload_empty_magin',
    'tacz:ai_awp/awp_reload_empty_boltclose': 'awm_reload_empty_boltclose',
    'tacz:ai_awp/awp_reload_empty_end':       'awm_reload_empty_end',
}

LOOPING = {'static_idle', 'static_bolt_caught'}
LOOP_LENGTH = {'static_idle': 2.0, 'static_bolt_caught': 2.0}

# bolt 里补的抛壳段：TaCZ reload_empty 的 bullet_shell 曲线（2.55~3.033）平移到 0.55
SHELL_SHIFT = 0.55 - 2.55
SHELL_FROM = 'reload_empty'

# 空仓挂机（打光最后一发后的收尾）：栓停在后方
BOLT_CAUGHT = {'position': [0.0, 0.0, 4.6 * INV_S], 'rotation': [0.0, 0.0, 60.0]}


# ---------------------------------------------------------------- 工具
def euler_to_mat(r):
    """Bedrock/GeckoLib 的 XYZ 欧拉（度）-> 3x3。"""
    x, y, z = (math.radians(v) for v in r)
    cx, sx = math.cos(x), math.sin(x)
    cy, sy = math.cos(y), math.sin(y)
    cz, sz = math.cos(z), math.sin(z)
    return [
        [cy * cz, -cy * sz, sy],
        [cx * sz + sx * sy * cz, cx * cz - sx * sy * sz, -sx * cy],
        [sx * sz - cx * sy * cz, sx * cz + cx * sy * sz, cx * cy],
    ]


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mat_to_euler(m):
    sy = max(-1.0, min(1.0, m[0][2]))
    y = math.asin(sy)
    if abs(sy) < 0.99999:
        x = math.atan2(-m[1][2], m[2][2])
        z = math.atan2(-m[0][1], m[0][0])
    else:                                    # 万向锁
        x = math.atan2(m[2][1], m[1][1])
        z = 0.0
    return [math.degrees(x), math.degrees(y), math.degrees(z)]


def rot_compose(a, b):
    """父级 a 之后再转 b。"""
    return mat_to_euler(mat_mul(euler_to_mat(a), euler_to_mat(b)))


def rot_apply(r, v):
    """把向量 v 用旋转 r 转到父级坐标系。"""
    m = euler_to_mat(r)
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def norm_chan(ch):
    """TaCZ 的一个通道 -> {t: [x,y,z], ...}；常量通道写成 {0.0: [...]}。"""
    if ch is None:
        return None
    if isinstance(ch, list):
        return {0.0: [float(v) for v in ch]}
    if isinstance(ch, (int, float)):          # 标量常量通道（TaCZ 里偶发，如 bullet_shell.scale = 1）
        return {0.0: [float(ch)] * 3}
    out = {}
    for t, v in ch.items():
        val = v['post'] if isinstance(v, dict) and 'post' in v else v
        if isinstance(val, dict):            # 极少数写法 {"post": ...} 被包了一层
            val = val.get('post', [0, 0, 0])
        out[round(float(t), 4)] = [float(x) for x in val]
    return out


def sample(keys, t, smooth=True):
    ts = sorted(keys)
    if t <= ts[0]:
        return list(keys[ts[0]])
    if t >= ts[-1]:
        return list(keys[ts[-1]])
    lo = max(x for x in ts if x <= t)
    hi = min(x for x in ts if x >= t)
    if hi == lo:
        return list(keys[lo])
    f = (t - lo) / (hi - lo)
    if smooth:
        f = f * f * (3.0 - 2.0 * f)
    a, b = keys[lo], keys[hi]
    return [a[i] + (b[i] - a[i]) * f for i in range(3)]


def r4(v):
    return [round(x, 4) + 0.0 for x in v]


# ---------------------------------------------------------------- 主流程
def main():
    tacz = json.load(open(SRC, encoding='utf-8'))['animations']
    geo = json.load(open(GEO, encoding='utf-8'))['minecraft:geometry'][0]
    our_bones = {b['name'] for b in geo['bones']}

    # 抛壳曲线（从 reload_empty 取，平移时间窗）
    shell_src = {}
    for ch in ('rotation', 'position', 'scale'):
        k = norm_chan(tacz.get(SHELL_FROM, {}).get('bones', {}).get('bullet_shell', {}).get(ch))
        if k:
            shell_src[ch] = {round(t + SHELL_SHIFT, 4): v for t, v in k.items()}
    if not shell_src:
        sys.exit(f'!! 没找到 {SHELL_FROM}.bullet_shell —— 无法给 bolt 补抛壳')

    out = {}
    ledger = []
    for clip_name, clip in tacz.items():
        src_bones = clip.get('bones', {})
        length = clip.get('animation_length')
        if clip_name in LOOP_LENGTH:
            length = LOOP_LENGTH[clip_name]
        elif length is None:
            length = 2.0
        length = float(length)

        # ---- 1. 按映射收集
        dst = {}
        used_src = set()
        for (sb, sc), ch in ((k, v) for b, chans in src_bones.items()
                             for k, v in [((b, c), v2) for c, v2 in chans.items()]):
            keys = norm_chan(ch)
            if keys is None:
                continue
            m = MAP.get((sb, sc))
            if m is None:
                used_src.add(f'{sb}.{sc}')
                ledger.append((clip_name, f'{sb}.{sc}', '未映射（骨架不同，丢弃）'))
                continue
            db, dc, kind = m
            used_src.add(f'{sb}.{sc}')
            if kind.endswith('+'):
                dst.setdefault((db, dc, 'merge'), {})[sb] = keys
            else:
                dst[(db, dc, kind)] = keys

        # ---- 2. 输出
        bones = {}
        for (db, dc, kind), payload in dst.items():
            if kind == 'merge':
                base = payload.get('root')
                extra = payload.get('gun_and_righthand')
                if extra is None:                     # 只有 root：逐字直抄，不做矩阵往返
                    chan = {}
                    for t, v in (base or {}).items():
                        if t > length + 1e-9:
                            continue
                        chan[t] = r4([x * (INV_S if dc == 'position' else 1.0) for x in v])
                else:                                 # root ∘ gun（父先子后）
                    ts = sorted({t for k in payload.values() for t in k if t <= length + 1e-9})
                    chan = {}
                    for t in ts:
                        pr = sample(base, t) if base else [0.0, 0.0, 0.0]
                        pe = sample(extra, t)
                        if dc == 'rotation':
                            chan[t] = r4(rot_compose(pr, pe))
                        else:
                            g = rot_apply(pr, pe)
                            chan[t] = r4([(pr[i] + g[i]) * INV_S for i in range(3)])
                if chan:
                    bones.setdefault(db, {})[dc] = chan
            else:
                scale = INV_S if kind == 'pos' else 1.0
                chan = {}
                for t, v in payload.items():
                    if t > length + 1e-9:
                        continue
                    chan[t] = r4([x * scale for x in v])
                if not chan:
                    continue
                bones.setdefault(db, {})[dc] = chan

        # ---- 3. bolt 补抛壳（TaCZ 本体在 bolt 里不抛壳）
        if clip_name == 'bolt':
            for ch, keys in shell_src.items():
                tgt = {'rotation': 'rotation', 'position': 'position', 'scale': 'scale'}[ch]
                chan = {t: r4([x * (INV_S if tgt == 'position' else 1.0) for x in v])
                        for t, v in keys.items() if t <= length + 1e-9}
                if chan:
                    bones.setdefault('casing', {})[tgt] = chan
            ledger.append((clip_name, f'casing <= {SHELL_FROM}.bullet_shell',
                           f'TaCZ 在 bolt 里不抛壳，抛壳段 {SHELL_FROM} 曲线平移 {SHELL_SHIFT:+.2f}s'))

        # ---- 4. 空仓挂机
        if clip_name == 'static_bolt_caught':
            bones.setdefault('bolt', {})['position'] = {0.0: r4(BOLT_CAUGHT['position'])}
            bones.setdefault('bolt', {})['rotation'] = {0.0: r4(BOLT_CAUGHT['rotation'])}
            bones.setdefault('round_in', {})['scale'] = {0.0: [0.0, 0.0, 0.0]}
            ledger.append((clip_name, 'bolt/round_in', 'TaCZ 这段只动 striker；挂机姿态是我们补的'))

        # ---- 5. 受管骨骼：本段没有数据的通道显式归位，防止上一段的状态残留
        for bone, scale_rule in NEUTRAL.items():
            entry = bones.setdefault(bone, {})
            for ch in ('rotation', 'position'):
                if ch not in entry:
                    entry[ch] = {0.0: [0.0, 0.0, 0.0]}
            if scale_rule is not None and 'scale' not in entry:
                val = [1.0, 1.0, 1.0] if scale_rule == 'show' else [0.0, 0.0, 0.0]
                entry['scale'] = {0.0: r4(val), round(length, 4): r4(val)}

        # ---- 5b. 音效键：TaCZ 的 sound_effects 按同一时间轴搬过来，只留我们随包分发的那些
        sounds = {}
        for t, ev in (clip.get('sound_effects') or {}).items():
            effect = ev.get('effect') if isinstance(ev, dict) else ev
            tgt = SOUND_MAP.get(effect)
            if tgt is None:
                ledger.append((clip_name, effect, '音效未映射（不随包分发）'))
                continue
            if float(t) > length + 1e-9:
                continue
            sounds[str(round(float(t), 4) + 0.0)] = {'effect': f'apocalypse_zombies:{tgt}'}

        entry = {
            'loop': bool(clip.get('loop', False)) or clip_name in LOOPING,
            'animation_length': round(length, 4),
            'bones': bonekey_sorted(bones),
        }
        if sounds:
            entry['sound_effects'] = dict(sorted(sounds.items(), key=lambda kv: float(kv[0])))
        out[clip_name] = entry

    # ---- 6. 契约校验：动画里出现的骨骼必须在 geo 里真实存在
    problems = []
    for clip_name, clip in out.items():
        for b in clip['bones']:
            if b not in our_bones:
                problems.append(f'{clip_name}: 骨骼 {b} 不在模型里')
    if problems:
        print('\n'.join('!! ' + p for p in problems))
        sys.exit('契约校验失败：先修模型或映射，再导出')

    json.dump({'format_version': '1.8.0', 'animations': out},
              open(OUT, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

    print(f'wrote {OUT}  ({os.path.getsize(OUT) / 1024:.0f} KB)')
    print(f'S_GUN = {S_GUN:.3f}')
    for clip_name, clip in out.items():
        nb = len(clip['bones'])
        nk = sum(len(c) for b in clip['bones'].values() for c in b.values())
        print(f"  {clip_name:20s} len={clip['animation_length']:<8} loop={str(clip['loop']):5s} "
              f"bones={nb:2d} keys={nk:5d}")
    print('\nLEDGER（没有直搬的东西，理由）:')
    for c, w, why in ledger:
        if '丢弃' in why:
            continue
    dropped = sorted({w for c, w, why in ledger if '丢弃' in why})
    print('  丢弃的 TaCZ 通道:', ', '.join(dropped))
    for c, w, why in ledger:
        if '丢弃' not in why:
            print(f'  补做: [{c}] {w} — {why}')


def bonekey_sorted(bones):
    """骨骼名排序 + 通道内的键按时间排序，输出稳定。"""
    out = {}
    for b in sorted(bones):
        chans = {}
        for ch in ('rotation', 'position', 'scale'):
            if ch in bones[b]:
                chans[ch] = {str(t): v for t, v in sorted(bones[b][ch].items())}
        if chans:
            out[b] = chans
    return out


if __name__ == '__main__':
    main()
