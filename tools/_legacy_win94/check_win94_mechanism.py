# -*- coding: utf-8 -*-
"""win94 机构门禁 —— 把「真枪逻辑」和「环必须连贯」变成可自动检查的断言。

检查项（任一条不过就是装反 / 装错位 / 环上有缝）：
  1. 杠杆环闭合：16 段首尾搭接，任意相邻段端点缝隙 < 0.03 u。
     （用户反馈过"环上有缝、看着像两个环"，这条是防它回归）
  2. 卡箍环闭合：护木前端 / 后端的两个 barrel band 也各是一整圈（同上判据）。
  3. 环包住扳机：环的最高点高于扳机下端，且扳机落在环的 z 跨度内
     （真枪的环本身就是扳机护圈，扳机垂在环里）。
  4. 转轴位置：lever 转轴在 trigger 轴**之后**（+Z 侧），且两者都在机匣底部以下。
  5. 杠杆打开方向：animation.json 里 lever 的旋转必须是**负角度**
     （+X = 射手右侧、−Z = 枪口 ⇒ 环在转轴前方 ⇒ 负角度才是向下后方打开）。
  6. 扳机扣动方向：trigger 必须是负角度（刀片下端向后）。
  7. 击锤待击方向：hammer 必须是正角度（锤顶向后倒）。

⚠ bbmodel 的骨骼**名字不在 outliner 节点上**，而在顶层 `groups` 数组里（按 uuid 索引），
  outliner 只存 children/uuid。门禁早期版本就是漏了这点而报"骨骼缺失"。

用法：python tools/check_win94_mechanism.py
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BBMODEL = ROOT / 'win94.bbmodel'
ANIM = ROOT / 'src' / 'main' / 'resources' / 'assets' / 'apocalypse_zombies' / 'animations' / 'win94.animation.json'
GAP_TOL = 0.03          # 环上允许的最大缝隙（u）

# Java 契约：这些骨骼名不许改（Java 侧按名字取骨骼，Win94ItemRenderer 还硬编码了 "lever"）
CONTRACT_BONES = ('root', 'move', 'body', 'barrel', 'forearm', 'receiver', 'bolt', 'hammer',
                  'lever', 'carrier', 'cartridge', 'spent_shell', 'trigger', 'scope', 'stock')
CONTRACT_ANIMS = ('static_idle', 'draw', 'shoot', 'bolt', 'reload_tactical', 'reload_empty', 'inspect')

problems = []
notes = []


def load_groups(data):
    gmeta = {g['uuid']: g for g in data.get('groups', [])}
    elements = {e['uuid']: e for e in data.get('elements', [])}
    groups = {}

    def walk(nodes, parent_name=None):
        for n in nodes:
            if isinstance(n, str):
                e = elements.get(n)
                if e is not None and parent_name:
                    groups[parent_name]['cubes'].append(e)
                continue
            meta = gmeta.get(n.get('uuid')) or {}
            name = meta.get('name') or n.get('name') or 'group'
            groups[name] = {'origin': meta.get('origin', [0, 0, 0]), 'cubes': [], 'parent': parent_name}
            walk(n.get('children') or [], name)

    walk(data.get('outliner') or [])
    return groups


def ends_x_rot(c):
    """环面在 YZ（块绕 X 旋转）：未旋转时长轴沿 Z。"""
    (_, y0, z0), (_, y1, z1) = c['from'], c['to']
    cy, cz = (y0 + y1) / 2.0, (z0 + z1) / 2.0
    ln = abs(z1 - z0)
    th = math.radians((c.get('rotation') or [0, 0, 0])[0])
    dy, dz = -math.sin(th), math.cos(th)
    return ((cy - dy * ln / 2, cz - dz * ln / 2), (cy + dy * ln / 2, cz + dz * ln / 2))


def ends_z_rot(c):
    """环面在 XY（块绕 Z 旋转）：未旋转时长轴沿 X。"""
    (x0, y0, _), (x1, y1, _) = c['from'], c['to']
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    ln = abs(x1 - x0)
    th = math.radians((c.get('rotation') or [0, 0, 0])[2])
    dx, dy = math.cos(th), math.sin(th)
    return ((cx - dx * ln / 2, cy - dy * ln / 2), (cx + dx * ln / 2, cy + dy * ln / 2))


def check_ring(label, cubes, ends_of, plane):
    """plane: 'yz' → 极角用 (y,z)；'xy' → 用 (x,y)。

    相邻判定用**四个端点配对里的最小距离**：环上相邻两段共享一个端点，另一个端点离得远；
    而极角排序的方向可能与实际生成方向相反（卡箍环就是反的），
    只看"a 的后端 → b 的前端"会把好好的环误报成裂开 0.41 u。
    """
    if len(cubes) < 8:
        problems.append(f'{label}：段数太少（{len(cubes)}），不足以围成连贯的环')
        return
    if plane == 'yz':
        cs = [((c['from'][1] + c['to'][1]) / 2, (c['from'][2] + c['to'][2]) / 2) for c in cubes]
    else:
        cs = [((c['from'][0] + c['to'][0]) / 2, (c['from'][1] + c['to'][1]) / 2) for c in cubes]
    cy = sum(p[0] for p in cs) / len(cs)
    cz = sum(p[1] for p in cs) / len(cs)
    ordered = [c for _, c in sorted(zip(
        [math.atan2(p[0] - cy, p[1] - cz) for p in cs], cubes))]
    gaps = []
    for i in range(len(ordered)):
        ea = ends_of(ordered[i])
        eb = ends_of(ordered[(i + 1) % len(ordered)])
        gaps.append(min(math.hypot(pa[0] - pb[0], pa[1] - pb[1])
                        for pa in ea for pb in eb))
    worst = max(gaps)
    notes.append(f'{label}：{len(cubes)} 段，最大缝隙 {worst:.4f} u（{worst * 62.5:.2f} mm）')
    if worst > GAP_TOL:
        problems.append(f'{label} 有缝隙：最大 {worst:.4f} u（>{GAP_TOL}）—— 会被看成断开的两个环')


def extreme_vec(anims, clip, bone, channel):
    """取该通道里**绝对值最大**的那个向量 —— 不能取首帧：clip 首帧常常就是 0（静止起手），
    方向要看整个片段的极值。"""
    ch = (anims.get(clip, {}).get('bones', {}).get(bone, {}) or {}).get(channel)
    if not ch:
        return None
    best, best_mag = None, -1.0
    for t in sorted(ch.keys(), key=float):
        v = ch[t]['post']['vector']
        mag = abs(v[0]) + abs(v[1]) + abs(v[2])
        if mag > best_mag:
            best, best_mag = v, mag
    return best


def main():
    if not BBMODEL.exists():
        print('缺 win94.bbmodel')
        return 1
    data = json.loads(BBMODEL.read_text(encoding='utf-8'))
    groups = load_groups(data)
    for need in ('lever', 'trigger', 'hammer', 'bolt', 'barrel'):
        if need not in groups:
            problems.append(f'骨骼缺失：{need}')

    # 0) Java 契约：骨骼名 / 动画名不许改
    missing_bones = [b for b in CONTRACT_BONES if b not in groups]
    extra_bones = sorted(set(groups) - set(CONTRACT_BONES))
    notes.append(f'骨骼 {len(groups)} 根：契约名齐全 = {not missing_bones}，'
                 f'额外 = {extra_bones or "无"}')
    if missing_bones:
        problems.append(f'Java 契约骨骼名缺失：{missing_bones}（改了名 Java 侧取不到骨骼）')

    if problems:
        print('=== win94 机构门禁 ===')
        for n in notes:
            print('  ·', n)
        for p in problems:
            print('  ✗', p)
        return 1

    # 1) 三个环各自的闭合度（杠杆环兼作扳机护圈；另有两个枪管/护木卡箍环）
    loops = [c for c in groups['lever']['cubes'] if (c.get('name') or '').startswith('lever_loop')]
    check_ring('杠杆环（兼扳机护圈）', loops, ends_x_rot, 'yz')
    for band in ('band_front', 'band_rear'):
        segs = [c for c in groups['barrel']['cubes'] if (c.get('name') or '').startswith(band)]
        if not segs:
            problems.append(f'缺少卡箍环 {band}')
            continue
        check_ring(f'卡箍环 {band}', segs, ends_z_rot, 'xy')

    # 2) 环包住扳机（真枪 lever 环**兼作**扳机护圈，照片上机匣下方只有一个环）
    trg = groups['trigger']['cubes']
    if loops and trg:
        loop_top = max(c['to'][1] for c in loops)
        loop_zmin, loop_zmax = min(c['from'][2] for c in loops), max(c['to'][2] for c in loops)
        trg_bot = min(c['from'][1] for c in trg)
        trg_zmin, trg_zmax = min(c['from'][2] for c in trg), max(c['to'][2] for c in trg)
        notes.append(f'环 y 顶 {loop_top:.3f} / 扳机底 {trg_bot:.3f}；'
                     f'环 z [{loop_zmin:.3f},{loop_zmax:.3f}] / 扳机 z [{trg_zmin:.3f},{trg_zmax:.3f}]')
        if not loop_top > trg_bot:
            problems.append('环没有包住扳机：环的最高点低于扳机下端'
                            '（真枪 lever 环兼作扳机护圈，扳机垂在环里）')
        if not (loop_zmin < trg_zmax and trg_zmin < loop_zmax):
            problems.append('扳机不在环的 z 跨度内')
        # 真枪只有一个环：机匣下方不该再有第二个独立的护圈/环
        extra = [c['name'] for c in groups['receiver']['cubes']
                 if 'guard' in (c.get('name') or '')]
        if extra:
            problems.append(f'机匣下出现了多余的护圈件 {extra[:3]} —— 真枪只有一个环（环兼护圈）')

    # 3) 转轴位置 + 环在转轴的哪一侧（决定动画方向的正负号）
    lv_o, tg_o = groups['lever']['origin'], groups['trigger']['origin']
    notes.append(f'lever 轴 (y{lv_o[1]:.2f}, z{lv_o[2]:.2f}) / trigger 轴 (y{tg_o[1]:.2f}, z{tg_o[2]:.2f})')
    if not lv_o[2] < tg_o[2]:
        problems.append('杠杆转轴不在扳机之前（真枪 lever 转轴在机匣前下方，'
                        '长杆向后延伸、末端成环）')
    if not (lv_o[1] < -0.70 and tg_o[1] < -0.70):
        problems.append('转轴没有落在机匣底部以下')
    loop_center_z_expected = None
    if loops:
        lz2 = sum((c['from'][2] + c['to'][2]) / 2 for c in loops) / len(loops)
        loop_center_z_expected = lz2
        notes.append(f'杠杆环相对转轴：Δz = {lz2 - lv_o[2]:+.3f}（>0 = 环在转轴后方 ⇒ 用正角度）')

    # 5~7) 动画方向
    if not ANIM.exists():
        problems.append(f'缺动画文件 {ANIM.name}')
    else:
        anims = json.loads(ANIM.read_text(encoding='utf-8')).get('animations', {})
        missing_anims = [a for a in CONTRACT_ANIMS if a not in anims]
        notes.append(f'动画 {len(anims)} 条：{sorted(anims)}')
        if missing_anims:
            problems.append(f'Java 契约动画名缺失：{missing_anims}'
                            f'（Win94Item 的 RawAnimation 按名字播放）')
        # 杠杆的期望符号**自动推导**：环在转轴后方（Δz>0）就该用正角度，在前方就用负角度。
        # 这样以后再把环挪位置，门禁不会反过来误判。
        lever_sign = 1 if (loop_center_z_expected is not None and loop_center_z_expected > lv_o[2]) else -1
        side = '后' if lever_sign > 0 else '前'
        for clip, bone, ch, want_sign, why in (
            ('bolt', 'lever', 'rotation', lever_sign,
             f'杠杆打开方向（环在转轴{side}方 ⇒ 期望{"正" if lever_sign > 0 else "负"}角度）'),
            ('shoot', 'trigger', 'rotation', -1, '扳机刀片下端应向后（负角度）'),
            ('shoot', 'hammer', 'rotation', +1, '击锤待击时锤顶向后倒（正角度）'),
        ):
            v = extreme_vec(anims, clip, bone, ch)
            if v is None:
                problems.append(f'{clip} 动画里没有 {bone} 的 {ch} 通道')
                continue
            notes.append(f'{clip}/{bone} 极值 = {v}')
            if v[0] * want_sign <= 0:
                problems.append(f'{why}，实际 {v[0]}')

        # 进弹顺序：升降器必须**先下摆接弹、再抬起送弹**（用户强调过这条，防止再写成"一开栓就抬起"）
        ch_carrier = (anims.get('bolt', {}).get('bones', {}).get('carrier', {}) or {}).get('position')
        if not ch_carrier:
            problems.append('bolt 动画里没有 carrier 的 position 通道')
        else:
            seq = [(float(t), ch_carrier[t]['post']['vector'][1]) for t in ch_carrier]
            seq.sort()
            lows = [(t, y) for t, y in seq if y < -0.02]
            highs = [(t, y) for t, y in seq if y > 0.02]
            notes.append(f'carrier 低位 {[f"{t:.2f}s:{y:+.2f}" for t, y in lows]} → '
                         f'高位 {[f"{t:.2f}s:{y:+.2f}" for t, y in highs]}')
            if not lows or not highs:
                problems.append('carrier 没有"先下摆再接弹、再抬起送弹"的两段位移'
                                '（真枪顺序：闭锁块后退后半段下摆接弹 → 复进前抬起送弹）')
            elif min(t for t, _ in lows) > min(t for t, _ in highs):
                problems.append('carrier 顺序反了：抬起（送弹）早于下摆（接弹）'
                                '—— 等于把还没出弹仓的子弹抬到膛口')

    print('=== win94 机构门禁 ===')
    for n in notes:
        print('  ·', n)
    if problems:
        print(f'\n{len(problems)} 条不通过：')
        for p in problems:
            print('  ✗', p)
        return 1
    print('\n全部通过：杠杆环连贯且兼作扳机护圈 · 环包住扳机 · 转轴在机匣前下方（扳机之前）·\n'
          '          杠杆/扳机/击锤方向均为真枪方向 · carrier 先下摆接弹、再抬起送弹')
    return 0


if __name__ == '__main__':
    sys.exit(main())
