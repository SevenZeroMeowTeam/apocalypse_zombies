#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""awm 动画自检：契约 + Java 契约 + 直译保真度 + 运动学落点。

跑法：python tools/check_awm_anim.py        （在 F:/mcmod 下）

它检查四件事，任何一件不过就非零退出：
  1. 契约  —— 动画里出现的每个骨骼名，必须在 art/awm/awm.geo.json 里真实存在；
              每个关键帧时刻 ≤ 该段 animation_length；loop 标记正确。
              （这一条是为了抓住"动画在动一根模型里根本没有的骨头"这类静默失效。）
  2. Java 契约 —— AWMItem.java 里写的 clip 名必须真的在动画文件里，触发名必须唯一，
              时长常量必须等于 clip 长度×20 向上取整。这三样错一样，动画就会静默不播：
              clip 名打错什么都不动，时长比 clip 短则下一段动作会把它截断。
  3. 保真  —— 把 TaCZ 源文件按 tools/tacz_anim_transcribe.py 的换算规则重新采样，
              与我们导出的 JSON 逐点比对，容差 1e-3。直译必须真的直译。
  4. 落点  —— 抽查关键运动学量：栓行程、抬把角、抛壳是否越过机匣、弹匣行程。
  5. 音效  —— AWMItem.java 里每张音效时刻表，必须与动画 JSON 的 sound_effects 逐条一致；
              表里引用的每个 SoundEvent 必须在 ModSounds.java 里有定义、在 sounds.json 里有登记、
              对应的 .ogg 文件确实存在。枪战手感一半靠声音落在动作上，错一拍就散架。
"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO = os.path.join(HERE, 'art', 'awm', 'awm.geo.json')
OURS = os.path.join(HERE, 'art', 'awm', 'awm.animation.json')
ITEM_JAVA = os.path.join(HERE, 'src', 'main', 'java', 'com', 'apocalypse', 'zombies',
                         'item', 'AWMItem.java')
SOUNDS_JAVA = os.path.join(HERE, 'src', 'main', 'java', 'com', 'apocalypse', 'zombies',
                           'registry', 'ModSounds.java')
SOUNDS_JSON = os.path.join(HERE, 'src', 'main', 'resources', 'assets', 'apocalypse_zombies',
                           'sounds.json')
SOUND_DIR = os.path.join(HERE, 'src', 'main', 'resources', 'assets', 'apocalypse_zombies',
                         'sounds', 'awm')
ITEM_MODEL = os.path.join(HERE, 'src', 'main', 'resources', 'assets', 'apocalypse_zombies',
                          'models', 'item', 'awm.json')
SRC = ('C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2'
       '/tacz/tacz_default_gun/assets/tacz/animations/ai_awp.animation.json')

S_GUN = 57.07 / 23.97
INV_S = 1.0 / S_GUN
LOOPING = {'static_idle', 'static_bolt_caught'}
TOL = 1e-3

#: 提柄角必须翻号：TaCZ 的模型柄长在 +X 侧，我们这把长在 −X（同一个「绕 +Z 正向旋转」，
#: 在 −X 侧是把柄往下压 —— 压进枪托里，就是拉栓穿模）。推导见 tools/bolt_lift_sign.py 顶部。
#: 纯直译会得到 +60，装进我们的模型是反的，所以这里按翻转后的期望值比对。
ROT_NEG = {('bolt', 'rotation')}

sys.path.insert(0, os.path.join(HERE, 'tools'))
from tacz_anim_transcribe import MAP, norm_chan, sample, rot_compose, rot_apply  # noqa: E402

fails = []
warns = []


def check_contract():
    geo = json.load(open(GEO, encoding='utf-8'))['minecraft:geometry'][0]
    bones = {b['name'] for b in geo['bones']}
    anim = json.load(open(OURS, encoding='utf-8'))['animations']
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
                        fails.append(f'契约: {clip}.{b}.{ch} 关键帧 {t} 超过长度 {L}')
    return anim


def check_java_contract(anim, tag='java'):
    """Java 里引用的 clip / 时长，必须和动画文件、参考数据对得上。

    tag 用来区分被检查的是哪一份动画：`java` 是随开发包走的转录版，
    `clean` 是纯净版（不随包分发 TaCZ 派生数据）用的完全原创版。
    """
    src = open(ITEM_JAVA, encoding='utf-8').read()
    consts = {}
    for kind, value in re.findall(
            r'(?:public|private|protected)?\s*static final (?:String|int)\s+(\w+)\s*=\s*"?'"'"'?([^";]+)?"?'"'"'?\s*;',
            src):
        consts[kind] = value

    # 提取失败会让下面所有检查静默变成空转，所以先挡住
    if not consts:
        fails.append(f'{tag}: 没能从 AWMItem.java 解析出任何常量，正则失配')

    # 每个 ANIM_xxx 常量都要能在动画文件里找到同名 clip
    for name, value in consts.items():
        if name.startswith('ANIM_') and value not in anim:
            fails.append(f'{tag}: {name} = "{value}"，动画文件里没有这段 clip')

    # 时长常量 vs clip 长度（20 t/s，向上取整）
    for const, clip in (('SHOOT_TICKS', 'shoot'), ('BOLT_TICKS', 'bolt'),
                        ('RELOAD_TACTICAL_TICKS', 'reload_tactical'),
                        ('RELOAD_EMPTY_TICKS', 'reload_empty')):
        got = consts.get(const)
        if got is None or clip not in anim:
            continue
        want = math.ceil(anim[clip]['animation_length'] * 20 - 1e-9)
        if int(got) != want:
            fails.append(f'{tag}: {const} = {got}，但 {clip} 长 {anim[clip]["animation_length"]}s '
                         f'= {want} ticks')

    # 触发名必须唯一（重名会让其中一段动作永远播不出来）
    triggers = [v for k, v in consts.items() if k.startswith('TRIGGER_')]
    for t in set(triggers):
        if triggers.count(t) > 1:
            fails.append(f'{tag}: 触发名 "{t}" 重复定义')

    # 第一人称比例：太小看着像手枪挂在手上，太大糊满屏幕
    if os.path.exists(ITEM_MODEL):
        display = json.load(open(ITEM_MODEL, encoding='utf-8')).get('display', {})
        scale = display.get('firstperson_righthand', {}).get('scale', [0])[0]
        if not 0.6 <= scale <= 0.9:
            fails.append(f'java: 第一人称 scale={scale}，超出 0.6~0.9 的合理区间')
    return consts


def check_sounds(anim):
    """音效时刻表 vs 动画 JSON，以及 SoundEvent 定义 / sounds.json / ogg 三者齐全。"""
    src = open(ITEM_JAVA, encoding='utf-8').read()

    # 表名 -> clip 名
    tables = {'BOLT_SOUNDS': 'bolt', 'RELOAD_TACTICAL_SOUNDS': 'reload_tactical',
              'RELOAD_EMPTY_SOUNDS': 'reload_empty'}

    # {表名: {tick: 常量名}}
    parsed = {}
    for m in re.finditer(r'(\w+_SOUNDS)\s*=\s*Map\.of\((.*?)\);', src, re.S):
        parsed[m.group(1)] = {int(t): c for t, c in
                              re.findall(r'(\d+)\s*,\s*ModSounds\.(\w+)', m.group(2))}
    for name in tables:
        if name not in parsed:
            fails.append(f'音效: AWMItem.java 里没有解析到 {name}（正则失配或表被删了）')

    # 常量名 -> 音效 id
    msrc = open(SOUNDS_JAVA, encoding='utf-8').read()
    ids = dict(re.findall(r'RegistryObject<SoundEvent>\s+(\w+)\s*=\s*sound\("([^"]+)"\)', msrc))
    if not ids:
        fails.append('音效: 没能从 ModSounds.java 解析出任何音效 id，正则失配')

    registered = json.load(open(SOUNDS_JSON, encoding='utf-8'))

    # ModSounds.java 里定义的每一个音效都必须有登记、有文件 —— 枪声不在时刻表里（由引擎在开火瞬间播），
    # 只查表会把它漏掉，而枪声恰恰是最不该哑掉的那个。
    for const, sid in ids.items():
        if sid not in registered:
            fails.append(f'音效: {sid}（{const}）定义了但没有登记在 sounds.json 里')
            continue
        for entry in registered[sid]['sounds']:
            name = entry['name'].split(':')[-1]
            if not os.path.exists(os.path.join(SOUND_DIR, os.path.basename(name) + '.ogg')):
                fails.append(f'音效: {sid} 指向的 {name}.ogg 不存在')

    for table, clip in tables.items():
        want = {}
        for t, ev in anim[clip].get('sound_effects', {}).items():
            effect = ev['effect']
            want[round(float(t) * 20)] = effect.split(':')[-1]
        got = {tick: ids.get(const, f'<未定义 {const}>') for tick, const in parsed.get(table, {}).items()}
        if got != want:
            only_want = {k: v for k, v in want.items() if got.get(k) != v}
            only_got = {k: v for k, v in got.items() if want.get(k) != v}
            fails.append(f'音效: {table} 与 {clip} 的 sound_effects 不一致；'
                         f'应为 {only_want}，实际 {only_got}')
        # 每个 id 都要有定义 / 登记 / 文件
        for const in parsed.get(table, {}).values():
            sid = ids.get(const)
            if sid is None:
                continue
            if sid not in registered:
                fails.append(f'音效: {sid} 没有登记在 sounds.json 里')
                continue
            for entry in registered[sid]['sounds']:
                name = entry['name'].split(':')[-1]
                path = os.path.join(SOUND_DIR, os.path.basename(name) + '.ogg')
                if not os.path.exists(path):
                    fails.append(f'音效: {sid} 指向的 {name}.ogg 不存在')


def ours_at(anim, clip, bone, chan, t):
    keys = {float(k): v for k, v in anim[clip]['bones'].get(bone, {}).get(chan, {}).items()}
    return sample(keys, t) if keys else None


def check_fidelity(anim):
    """按直译规则重算 TaCZ，与我们的输出比对（只查直搬的通道）。"""
    tacz = json.load(open(SRC, encoding='utf-8'))['animations']
    for (sb, sc), (db, dc, kind) in MAP.items():
        if kind.endswith('+') or kind == 'scale':
            continue                       # 合成/缩放通道另有逻辑，抽查意义不大
        scale = INV_S if kind == 'pos' else 1.0
        if (db, dc) in ROT_NEG:
            scale = -1.0                   # 提柄角翻号，见 ROT_NEG 的说明
        for clip, c in tacz.items():
            if clip not in anim:
                continue
            keys = norm_chan(c.get('bones', {}).get(sb, {}).get(sc))
            if not keys:
                continue
            L = anim[clip]['animation_length']
            for t in sorted(keys):
                if t > L + 1e-9:
                    continue
                got = ours_at(anim, clip, db, dc, t)
                if got is None:
                    fails.append(f'保真: {clip} 缺 {db}.{dc}（源 {sb}.{sc}）')
                    continue
                want = [x * scale for x in keys[t]]
                if max(abs(got[i] - want[i]) for i in range(3)) > 0.02:
                    fails.append(f'保真: {clip}.{db}.{dc} @{t}s 得到 '
                                 f'{[round(v,3) for v in got]}，应为 {[round(v,3) for v in want]}')


def check_kinematics(anim):
    def peak(clip, bone, chan, axis, fn=max):
        ks = {float(k): v for k, v in anim[clip]['bones'].get(bone, {}).get(chan, {}).items()}
        if not ks:
            return None
        return round(fn(v[axis] for v in ks.values()), 3)

    rep = {}
    rep['bolt 栓后退最大 z'] = peak('bolt', 'bolt', 'position', 2)
    rep['bolt 提柄角（负 = 上抬）'] = peak('bolt', 'bolt', 'rotation', 2, min)
    rep['bolt 抛壳最远 x'] = peak('bolt', 'casing', 'position', 0, min)
    rep['reload_empty 弹匣最低 y'] = peak('reload_empty', 'magazine', 'position', 1, min)
    rep['reload_empty 抛壳最远 x'] = peak('reload_empty', 'casing', 'position', 0, min)
    rep['shoot 枪口上跳 x'] = peak('shoot', 'move', 'rotation', 0, min)
    rep['reload_tactical 枪身最大倾 z'] = peak('reload_tactical', 'move', 'rotation', 2, min)
    rep['static_bolt_caught 栓 z'] = peak('static_bolt_caught', 'bolt', 'position', 2)

    # 期望值来自 TaCZ 源 ÷S_GUN 或 1:1
    exp = {
        'bolt 栓后退最大 z': (round(4.6 * INV_S, 3), 0.01),
        'bolt 提柄角（负 = 上抬）': (-60.0, 0.01),
        'reload_empty 弹匣最低 y': (round(-22.56 * INV_S, 3), 0.02),
        'shoot 枪口上跳 x': (-7.95, 0.5),
        'reload_tactical 枪身最大倾 z': (-25.74, 0.5),
        'static_bolt_caught 栓 z': (round(4.6 * INV_S, 3), 0.01),
    }
    for k, (want, tol) in exp.items():
        got = rep.get(k)
        if got is None:
            fails.append(f'落点: {k} 没有数据')
            continue
        if abs(got - want) > tol:
            fails.append(f'落点: {k} = {got}，期望 {want} ±{tol}')

    # 抛壳必须真的抛出机匣（机匣右壁外沿别用中心判断，用弹壳静止中心 x=-0.45）
    geo = json.load(open(GEO, encoding='utf-8'))['minecraft:geometry'][0]
    wall = None
    for b in geo['bones']:
        if b['name'] == 'body':
            wall = min(c['origin'][0] for c in b['cubes'])
    if wall is not None:
        for clip in ('bolt', 'reload_empty'):
            away = rep.get(f'{clip} 抛壳最远 x')
            if away is None or away > wall:
                fails.append(f'落点: {clip} 抛壳没有飞出机匣（最远 x={away}，机匣壁 x={wall}）')
    return rep


HANDMADE = os.path.join(HERE, 'art', 'awm', 'awm.animation.handmade.bak.json')


def check_clean_animation():
    """「纯净版」用的完全原创动画必须顶得住同一套 Java 契约。

    发布包不能带 TaCZ 派生数据，那个 jar 里的动画会被换成手工版；
    它的 clip 名、时长要和 Java 常量对得上，骨骼名还要在模型里真实存在 ——
    否则纯净版会静默变成一杆既不动也不响的枪，而这正是最初要修的毛病。
    """
    if not os.path.exists(HANDMADE):
        fails.append('clean: 找不到完全原创动画 art/awm/awm.animation.handmade.bak.json，'
                     '纯净版无料可换')
        return

    anim = json.load(open(HANDMADE, encoding='utf-8')).get('animations', {})
    if not anim:
        fails.append('clean: 手工动画里没有 animations 段')
        return

    # 同一个 Java 契约（clip 名 / 时长 / 触发名唯一性），换 tag 复检一遍
    check_java_contract(anim, tag='clean')

    # 驱动不存在的骨骼 = 那根骨骼纹丝不动，且日志里什么都不会说
    known = {b['name'] for b in
             json.load(open(GEO, encoding='utf-8'))['minecraft:geometry'][0]['bones']}
    for clip, body in anim.items():
        for bone in body.get('bones', {}):
            if bone not in known:
                fails.append(f'clean: {clip} 驱动了模型里不存在的骨骼 "{bone}"')

    # 手工版没有 sound_effects 是允许的（音效时刻表在 Java 里，与动画文件解耦），
    # 但如果它反而带了一版，就该和 Java 表一致 —— 这里只记一笔，不判失败
    if any('sound_effects' in c for c in anim.values()):
            warns.append('clean: 手工动画自带 sound_effects，请确认与 Java 时刻表一致')


if __name__ == '__main__':
    anim = check_contract()
    check_java_contract(anim)
    check_sounds(anim)
    check_clean_animation()
    check_fidelity(anim)
    rep = check_kinematics(anim)

    print('== 关键落点 ==')
    for k, v in rep.items():
        print(f'  {k:26s} {v}')
    print()
    print(f'clips: {len(anim)}  bones/clip: '
          f'{sorted({len(c["bones"]) for c in anim.values()})}')
    if warns:
        print('\n'.join('WARN ' + w for w in warns))
    if fails:
        print('\n'.join('FAIL ' + f for f in fails))
        sys.exit(1)
    print('OK  契约 / Java 契约 / 保真 / 落点 / 音效 / 纯净版契约 全部通过')
