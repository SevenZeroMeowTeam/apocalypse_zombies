# -*- coding: utf-8 -*-
"""win94 门禁 —— 把「真枪机构」和「环必须与真枪一致」变成可自动检查的断言。

检查项（任一条不过就是装反 / 装错位 / 环上有缝）：
  1. 契约骨骼 16 根齐全；方块数 / 贴图尺寸合规。
  2. **两个环**都在且闭合：
     · 扳机护圈（guard_loop，16 段）—— 机匣的一部分，包住扳机；
     · 杠杆环（lever_loop，20 段）—— 在护圈**后下方**、横向拉长、随杠杆摆。
     闭合判据：相邻段端点最小距离 < 0.03 u（早先的写法在环上有 6 处缝，看着像断开成两个环）。
  3. 环的尺寸对得上真枪：护圈外径 58×34 mm、杠杆环外径 105×40 mm（±15%）。
  4. 环包住扳机：扳机 z 跨度落在护圈 z 跨度内，扳机底不低于护圈底。
  5. 杠杆转轴在机匣**前下方**，环在转轴**后方**（Δz > 0）⇒ 打开必须是**正角度**。
  6. 装填门在机匣**中后部**（真枪原图 x 482…527 → z −1.63…−0.88），不在尾端。
  7. 倍镜：镜管中心高于 bore 50 mm（±5），镜管底与机匣顶留 ≥ 20 mm 抛壳净空。
  8. 动画（读**落盘** animation.json）：7 条契约 clip 与 Java 的 tick 常量一致（40/16/12/22/44/88/52）；
     **落盘空间的机构符号**（GeckoLib 加载时对旋转做 (−rx,−ry,+rz) 预烹饪，见 export.py）
     —— lever 应为负（渲染 +62° = 环向前下方摆）、击锤负（渲染 +32° = 锤顶向后倒）、
     扳机正（渲染 −16° = 刀片下端向后）；
     bolt 行程 ≥ 0.9 u（够抽壳）；
     **carrier 先下后上**：最低位时刻必须晚于 bolt 后退行程的 50%，且早于最高位时刻；
     reload_empty 至少压 5 发（gate 被顶开 5 次，开度按 |x| 计）。
  9. 交付资源：geo identifier / 骨骼数 / 贴图 / animation format_version。
 10. **落盘动画与导出几何同坐标系**：geo 的装填门在 −X（导出空间 −X = 射手右侧），
     换弹的子弹必须从 −X 一侧（装填门侧）压入、空壳向 −X 上方抛出（渲染时统一取反回 +X）——
     1.1.105 及以前几何在导出空间、动画还在作者空间，实机就是「装弹方向反了」。

用法：python tools/win94/gate.py
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import spec as S  # noqa: E402

BBMODEL = S.BBMODEL
ASSETS = S.ASSETS
GEO = ASSETS / 'geo' / 'win94.geo.json'
ANIM = ASSETS / 'animations' / 'win94.animation.json'
TEX = ASSETS / 'textures' / 'item' / 'win94.png'

GAP_TOL = 0.03
problems = []
notes = []


def ok(msg):
    notes.append(msg)


def bad(msg):
    problems.append(msg)


# --------------------------------------------------------------- 读 bbmodel
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


# --------------------------------------------------------------- 环几何
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


def check_ring(label, cubes, ends_of, plane, min_segs=8):
    """相邻判定用四个端点配对里的最小距离（环上相邻两段共享一个端点）。"""
    if len(cubes) < min_segs:
        bad(f'{label}：段数太少（{len(cubes)} < {min_segs}），不足以围成连贯的环')
        return None
    if plane == 'yz':
        cs = [((c['from'][1] + c['to'][1]) / 2, (c['from'][2] + c['to'][2]) / 2) for c in cubes]
    else:
        cs = [((c['from'][0] + c['to'][0]) / 2, (c['from'][1] + c['to'][1]) / 2) for c in cubes]
    cy = sum(p[0] for p in cs) / len(cs)
    cz = sum(p[1] for p in cs) / len(cs)
    order = sorted(range(len(cubes)),
                   key=lambda i: math.atan2(cs[i][0] - cy, cs[i][1] - cz))
    gaps = []
    for k in range(len(order)):
        a = cubes[order[k]]
        b = cubes[order[(k + 1) % len(order)]]
        ea, eb = ends_of(a), ends_of(b)
        d = min(math.dist(p, q) for p in ea for q in eb)
        gaps.append(d)
    worst = max(gaps)
    if worst > GAP_TOL:
        bad(f'{label}：环上有缝，最大 {worst:.3f} u（上限 {GAP_TOL}）')
    else:
        ok(f'{label}：{len(cubes)} 段闭合，最大缝 {worst * S.U_MM:.2f} mm')
    # 外径（沿 plane 两轴的极值跨度）
    if plane == 'yz':
        ys = [c['from'][1] for c in cubes] + [c['to'][1] for c in cubes]
        zs = [c['from'][2] for c in cubes] + [c['to'][2] for c in cubes]
        return (max(zs) - min(zs), max(ys) - min(ys), (sum(zs) / len(zs), sum(ys) / len(ys)))
    xs = [c['from'][0] for c in cubes] + [c['to'][0] for c in cubes]
    ys = [c['from'][1] for c in cubes] + [c['to'][1] for c in cubes]
    return (max(xs) - min(xs), max(ys) - min(ys), (sum(xs) / len(xs), sum(ys) / len(ys)))


def by_prefix(cubes, prefix):
    return [c for c in cubes if (c.get('name') or '').startswith(prefix)]


# --------------------------------------------------------------- 动画读取
def anim_channel(anim, bone, channel):
    ch = (anim.get('bones', {}).get(bone) or {}).get(channel) or {}
    return sorted(((float(t), v['post']['vector']) for t, v in ch.items()), key=lambda x: x[0])


def main():
    bb = json.loads(BBMODEL.read_text(encoding='utf-8'))
    groups = load_groups(bb)

    # ---- 1. 结构
    for b in S.CONTRACT_BONES:
        if b not in groups:
            bad(f'缺契约骨骼 {b}')
    ncubes = sum(len(g['cubes']) for g in groups.values())
    ok(f'骨骼 {len(groups)} 根 / 方块 {ncubes} 个')
    if ncubes < 200:
        bad(f'方块数偏少（{ncubes}）')
    texs = bb.get('textures') or []
    if len(texs) != 1:
        bad(f'贴图数应为 1，实为 {len(texs)}')
    elif (texs[0].get('uv_width'), texs[0].get('uv_height')) != (512, 512):
        bad(f'贴图应为 512²，实为 {texs[0].get("uv_width")}x{texs[0].get("uv_height")}')

    # ---- 2/3. 两个环
    guard = by_prefix(groups['receiver']['cubes'], 'guard_loop')
    loop = by_prefix(groups['lever']['cubes'], 'lever_loop')
    g_dim = check_ring('扳机护圈 guard_loop', guard, ends_x_rot, 'yz', 12)
    l_dim = check_ring('杠杆环 lever_loop', loop, ends_x_rot, 'yz', 14)
    for label, dim, want_z, want_y in (('护圈', g_dim, 0.92, 0.54), ('杠杆环', l_dim, 1.68, 0.64)):
        if not dim:
            continue
        dz, dy, _c = dim
        if abs(dz - want_z) > want_z * 0.18 or abs(dy - want_y) > want_y * 0.22:
            bad(f'{label}外径 {dz * S.U_MM:.0f}×{dy * S.U_MM:.0f} mm 与真枪 '
                f'{want_z * S.U_MM:.0f}×{want_y * S.U_MM:.0f} mm 差太多')
        else:
            ok(f'{label}外径 {dz * S.U_MM:.0f}×{dy * S.U_MM:.0f} mm（真枪基准 '
               f'{want_z * S.U_MM:.0f}×{want_y * S.U_MM:.0f} mm）')

    # ---- 4. 环包住扳机
    trig = groups['trigger']['cubes']
    if guard and trig:
        gz = [c['from'][2] for c in guard] + [c['to'][2] for c in guard]
        gy = [c['from'][1] for c in guard] + [c['to'][1] for c in guard]
        tz = [c['from'][2] for c in trig] + [c['to'][2] for c in trig]
        ty = [c['from'][1] for c in trig] + [c['to'][1] for c in trig]
        if min(tz) < min(gz) - 0.02 or max(tz) > max(gz) + 0.02:
            bad(f'扳机 z [{min(tz):.2f},{max(tz):.2f}] 没落在护圈 z [{min(gz):.2f},{max(gz):.2f}] 内')
        if min(ty) < min(gy) - 0.05:
            bad(f'扳机下端（y {min(ty):.2f}）低于护圈下端（{min(gy):.2f}）—— 扳机露在环外')
        else:
            ok(f'护圈包住扳机：扳机 z [{min(tz):.2f},{max(tz):.2f}] ⊂ 护圈 '
               f'[{min(gz):.2f},{max(gz):.2f}]，扳机底 y {min(ty):.2f} ≥ 护圈底 {min(gy):.2f}')

    # ---- 5. 转轴与环的相对位置
    piv = groups['lever']['origin']
    if loop and guard:
        lcy, lcz = l_dim[2][1], l_dim[2][0]
        gcy, gcz = g_dim[2][1], g_dim[2][0]
        if lcz <= gcz:
            bad(f'杠杆环（z {lcz:.2f}）没在护圈（z {gcz:.2f}）后方 —— 真枪环在护圈后下方')
        if lcy >= gcy:
            bad(f'杠杆环（y {lcy:.2f}）没在护圈（{gcy:.2f}）下方')
        if lcz - piv[2] <= 0:
            bad(f'杠杆环在转轴前方（Δz = {lcz - piv[2]:.2f}）→ 打开方向会反')
        else:
            ok(f'环在转轴后方 Δz = {lcz - piv[2]:.2f} u ⇒ 打开为正角度；'
               f'环中心（y {lcy:.2f}, z {lcz:.2f}）在护圈（y {gcy:.2f}, z {gcz:.2f}）后下方')
    if piv[2] > S.RZ_F + 0.6 or piv[1] > S.RY_BOT:
        bad(f'杠杆转轴 {piv} 不在机匣前下方')
    else:
        ok(f'杠杆转轴 (y {piv[1]:.2f}, z {piv[2]:.2f}) 在机匣前下方')

    # ---- 5b. 杆与环、护圈与机匣必须"长在一起"（用户标过这块：杆像插了根棍、环像挂在外面）
    arms = by_prefix(groups['lever']['cubes'], 'lever_arm')
    straps = by_prefix(groups['receiver']['cubes'], 'guard_strap')
    if arms and loop:
        z_end = max(c['to'][2] for c in arms)
        near_end = [c for c in arms if abs(c['to'][2] - z_end) < 0.02]
        y_end = min(c['from'][1] for c in near_end)
        z_loop = min(c['from'][2] for c in loop)
        front = [c for c in loop if c['from'][2] < z_loop + 0.30]
        y_loop = sum((c['from'][1] + c['to'][1]) / 2 for c in front) / len(front)
        d = math.hypot(z_end - z_loop, y_end - y_loop)
        if d > 0.45:
            bad(f'杠杆杆末端 (z {z_end:.2f}, y {y_end:.2f}) 离环前端 (z {z_loop:.2f}, y {y_loop:.2f}) '
                f'{d:.2f} u —— 环看起来是挂在杆外面的')
        else:
            ok(f'杠杆杆与环连成一体：杆末端到环前端 {d * S.U_MM:.0f} mm')
    # 杆必须从**护圈下方**穿过（早先杆是水平的，正好插进护圈孔里）
    if arms and guard:
        gz = [min(c['from'][2] for c in guard), max(c['to'][2] for c in guard)]
        inside = [c for c in arms if c['to'][2] > gz[0] and c['from'][2] < gz[1]]
        if inside:
            y_bot = max(c['to'][1] for c in inside)
            # 允许 0.06 的"贴合重叠"：真枪上杠杆杆就是紧贴护圈下缘走的
            if y_bot > S.GUARD_CY - S.GUARD_RY + 0.06:
                bad(f'杠杆杆在护圈区域里最高到 y {y_bot:.2f}，比护圈底 '
                    f'{S.GUARD_CY - S.GUARD_RY:.2f} 高出 0.06 以上 —— 杆从护圈孔里穿过去了'
                    f'（真枪从护圈下方过）')
            else:
                ok(f'杠杆杆从护圈下方穿过（护圈区最高 y {y_bot:.2f} < 护圈底 '
                   f'{S.GUARD_CY - S.GUARD_RY:.2f}）')
    if straps:
        sy0 = min(c['from'][1] for c in straps)
        sy1 = max(c['to'][1] for c in straps)
        g_top = S.GUARD_CY + S.GUARD_RY
        if not (sy0 <= g_top + 0.02 and sy1 >= S.RY_BOT - 0.02):
            bad(f'护圈与机匣之间没连上：guard_strap y {sy0:.2f}…{sy1:.2f} '
                f'没同时够到护圈顶 {g_top:.2f} 与机匣底 {S.RY_BOT}')
        else:
            ok(f'护圈挂在机匣上：guard_strap 覆盖 y {sy0:.2f}…{sy1:.2f}'
               f'（机匣底 {S.RY_BOT} → 护圈顶 {g_top:.2f}）')
    else:
        bad('缺 guard_strap：护圈上缘与机匣底之间有缝（侧面看护圈像浮在机匣下面）')

    # ---- 6. 装填门位置
    gate = groups['gate']['cubes']
    if gate:
        gz0 = min(c['from'][2] for c in gate)
        gz1 = max(c['to'][2] for c in gate)
        gx = max(c['to'][0] for c in gate)
        if not (S.RZ_F + 0.4 < gz0 and gz1 < S.RZ_B - 0.4):
            bad(f'装填门 z [{gz0:.2f},{gz1:.2f}] 贴到机匣尾端了（真枪在机匣中后部）')
        elif gz1 > -0.55:
            bad(f'装填门 z [{gz0:.2f},{gz1:.2f}] 太靠后（真枪 z −1.63…−0.88）')
        else:
            ok(f'装填门在机匣中后部 z [{gz0:.2f},{gz1:.2f}]（真枪 −1.63…−0.88），x 到 {gx:.2f}')
        if gx < 0.25:
            bad('装填门不在机匣右壁（x 应 > 0.25）')

    # ---- 7. 倍镜高度
    scope = groups['scope']['cubes']
    tube = by_prefix(scope, 'scope_tube')
    if tube:
        ys = [c['from'][1] for c in tube] + [c['to'][1] for c in tube]
        zs = [c['from'][2] for c in tube] + [c['to'][2] for c in tube]
        cy = (min(ys) + max(ys)) / 2.0
        clear = min(ys) - S.RY_TOP
        want = S.SCOPE_CY * S.U_MM
        if abs(cy - S.SCOPE_CY) > 0.05:
            bad(f'镜管中心 y {cy:.2f} u 与规范 {S.SCOPE_CY} 不符')
        if clear * S.U_MM < 20:
            bad(f'镜管底与机匣顶只留 {clear * S.U_MM:.0f} mm，抛壳会打镜（真枪必须架高）')
        else:
            ok(f'镜管中心高于 bore {cy * S.U_MM:.0f} mm（真枪顶装架 38–50 mm），'
               f'抛壳净空 {clear * S.U_MM:.0f} mm')
        notes.append(f'（参考：{want:.0f} mm 目标值）')
        if max(zs) - min(zs) < 5.5:
            bad('镜身太短')

    # ---- 8. 动画
    anim = json.loads(ANIM.read_text(encoding='utf-8'))
    clips = anim.get('animations', {})
    want_ticks = {'static_idle': 40, 'draw': 16, 'shoot': 12, 'bolt': 22,
                  'reload_tactical': 44, 'reload_empty': 88, 'inspect': 52}
    for name in S.CONTRACT_ANIMS:
        a = clips.get(name)
        if not a:
            bad(f'缺契约 clip {name}')
            continue
        ticks = int(round(a['animation_length'] * 20))
        if ticks != want_ticks[name]:
            bad(f'{name}: ticks {ticks} ≠ Java 契约 {want_ticks[name]}')
        else:
            ok(f'{name}: len {a["animation_length"]}s = {ticks} ticks（与 Java 一致）')

    # ---- 8b. GeckoLib 关键帧契约：零时间戳帧必须是各通道第一个键
    #      （违反 ⇒ BakedAnimationsAdapter 抛 "multiple starting keyframes" ⇒
    #       整包 animation.json 解析失败 ⇒ 客户端在资源加载阶段直接崩溃）
    order_bad = []
    for cname, a in clips.items():
        for bone, chans in (a.get('bones') or {}).items():
            for ch, ks in chans.items():
                for i, k in enumerate(list(ks)):
                    try:
                        t = float(k)
                    except ValueError:
                        t = 0.0
                    if t == 0 and i > 0:
                        order_bad.append(f'{cname}/{bone}.{ch}')
    if order_bad:
        bad(f'GeckoLib 关键帧契约不通过（{len(order_bad)} 处零时间戳帧不在首位，'
            f'会把客户端启动打崩）：' + '；'.join(order_bad[:5]))
    else:
        ok(f'GeckoLib 关键帧契约：{len(clips)} 条 clip 的零时间戳帧均在各通道首位')

    bolt = clips.get('bolt')
    if bolt:
        lev = anim_channel(bolt, 'lever', 'rotation')
        lev_peak = max((v[0] for _t, v in lev), key=abs) if lev else 0.0
        if not lev or lev_peak >= 0:
            bad('bolt：lever 在落盘空间应为负角度（GeckoLib 预烹饪取反 ⇒ 渲染 +62°。'
                '文件写正角度 = 实机杠杆向上翻，1.1.105/106 的 bug）')
        else:
            ok(f'bolt：lever 落盘 {lev_peak:.1f}°（渲染 {-lev_peak:.1f}° = 环向前下方摆）')
        bp = anim_channel(bolt, 'bolt', 'position')
        if bp:
            back = max(v[2] for _t, v in bp)
            if back < 0.9:
                bad(f'bolt：闭锁块行程 {back:.2f} u = {back * S.U_MM:.0f} mm，抽不出弹壳（需 ≥ 0.9 u）')
            else:
                ok(f'bolt：闭锁块后退 {back:.2f} u = {back * S.U_MM:.0f} mm（真枪 ≈ 2.4 in）')
            t_full = max(t for t, v in bp if abs(v[2] - back) < 0.02)
        else:
            t_full = None
            bad('bolt：闭锁块没有位移关键帧')
        cp = anim_channel(bolt, 'carrier', 'position')
        if cp:
            lows = [(t, v[1]) for t, v in cp if v[1] < -0.02]
            highs = [(t, v[1]) for t, v in cp if v[1] > 0.02]
            if not lows or not highs:
                bad('carrier 没有"先下摆接弹、再抬起送弹"的两段位移')
            else:
                t_low = min(t for t, _ in lows)
                t_high = min(t for t, _ in highs)
                if t_low > t_high:
                    bad('carrier 顺序反了：抬起早于下摆 —— 等于把还没出弹仓的子弹抬到膛口')
                elif t_full is not None and t_low < t_full * 0.5:
                    bad(f'carrier 下摆太早（t={t_low:.2f}s，闭锁块全退在 {t_full:.2f}s）'
                        f'—— 真枪是闭锁块后退**后半段**才下摆')
                else:
                    ok(f'carrier 先下后上：下摆 t={t_low:.2f}s（闭锁块全退 {t_full:.2f}s 的后半段）'
                       f'→ 抬起 t={t_high:.2f}s → 闭锁块推弹')
        ct = anim_channel(bolt, 'cartridge', 'position')
        if ct:
            zmin = min(v[2] for _t, v in ct)
            if zmin > S.CHAMBER_Z + 0.05:
                bad(f'bolt：新弹最远只走到 z 偏移 {zmin:.2f}，没进膛（应到 {S.CHAMBER_Z}）')
            else:
                ok(f'bolt：新弹被推进膛（z 偏移 {zmin:.2f}）')

    emp = clips.get('reload_empty')
    if emp:
        gp = anim_channel(emp, 'gate', 'position')
        # 开度按 |x| 计：装填门在导出空间是 −X 侧，被顶开时 x 朝哪边弹是 2 mm 级的细节，
        # 「开合几次」才是要卡的东西（1.1.106 起落盘动画已镜像，见检查项 10）。
        opens = [t for t, v in gp if abs(v[0]) > 0.005]
        # 顶开是"到峰值再回位"，按峰值计数
        peaks = 0
        prev = 0.0
        for t, v in gp:
            if abs(v[0]) > 0.005 and prev <= 0.005:
                peaks += 1
            prev = abs(v[0])
        if peaks < 5:
            bad(f'reload_empty：装填门只被顶开 {peaks} 次（管仓 5 发要压 5 次）')
        else:
            ok(f'reload_empty：装填门被顶开 {peaks} 次 = 压入 5 发；共 {len(opens)} 帧有开度')
        lev = anim_channel(emp, 'lever', 'rotation')
        lev_peak = max((v[0] for _t, v in lev), key=abs) if lev else 0.0
        if not lev or abs(lev_peak) < 40:
            bad('reload_empty：收尾的杠杆循环没做（满仓后要扳一次杠杆上膛）')
        elif lev_peak >= 0:
            bad(f'reload_empty：收尾杠杆在落盘空间是正角度 {lev_peak:.0f}° —— 实机会向上翻')
        else:
            ok(f'reload_empty：收尾杠杆循环落盘 {lev_peak:.0f}°（渲染 {-lev_peak:.0f}° 向下）')
    tac = clips.get('reload_tactical')
    if tac:
        gp = anim_channel(tac, 'gate', 'position')
        peaks, prev = 0, 0.0
        for _t, v in gp:
            if abs(v[0]) > 0.005 and prev <= 0.005:
                peaks += 1
            prev = abs(v[0])
        if peaks != 3:
            bad(f'reload_tactical：应压 3 发，实为 {peaks}')
        else:
            ok('reload_tactical：装填门顶开 3 次 = 压入 3 发')

    for clip, bone, chan, sign, label in (
            ('bolt', 'hammer', 'rotation', -1, '击锤待击：落盘负角度，渲染 +32°（锤顶向后倒）'),
            ('shoot', 'trigger', 'rotation', 1, '扳机扣动：落盘正角度，渲染 −16°（刀片下端向后）')):
        a = clips.get(clip)
        if not a:
            continue
        ch = anim_channel(a, bone, chan)
        if ch:
            peak = max(ch, key=lambda x: abs(x[1][0]))[1][0]
            if peak * sign <= 0:
                bad(f'{clip}/{bone}：峰值 {peak:.1f}° 方向不对（{label}）')
            else:
                ok(f'{clip}/{bone}：{peak:.1f}°（{label}）')

    # ---- 9. 资源
    geo = json.loads(GEO.read_text(encoding='utf-8'))
    g0 = geo['minecraft:geometry'][0]
    desc = g0['description']
    if desc.get('identifier') != 'geometry.win94':
        bad(f"geo identifier = {desc.get('identifier')}（应为 geometry.win94）")
    else:
        ok(f"geo identifier geometry.win94 · {len(g0['bones'])} bones · "
           f"{sum(len(b.get('cubes', [])) for b in g0['bones'])} cubes · "
           f"{desc.get('texture_width')}x{desc.get('texture_height')}")
    if anim.get('format_version') != '1.8.0':
        bad(f"animation format_version = {anim.get('format_version')}")
    if not TEX.exists():
        bad('缺贴图文件')
    else:
        from PIL import Image
        im = Image.open(TEX)
        if im.size != (512, 512):
            bad(f'贴图尺寸 {im.size}')
        else:
            ok(f'贴图 {TEX.name} {im.size[0]}x{im.size[1]} · {TEX.stat().st_size} B')

    # ---- 10. 落盘动画与导出几何同坐标系（换弹方向 = 装填门侧）
    #      geo 导出时 X 被取反：bbmodel 作者空间 +X = 射手右侧 → 导出空间 −X = 射手右侧
    #      （全项目一致，wiki 07；莫辛/AWM 的枪机柄、抛壳件都在 −X 侧）。动画必须由
    #      export.py 做同一次镜像 —— 1.1.105 及以前这层缺失：几何镜像了、动画没镜像，
    #      子弹从"没有装填门的那一侧"压进机匣，实机看到的就是「装弹方向反了」。
    geo_gate = [c for b in g0.get('bones', []) if b.get('name') == 'gate'
                for c in b.get('cubes', [])]
    if not geo_gate:
        bad('geo 里没有 gate 骨骼的方块')
    else:
        gx1 = max(c['origin'][0] + c['size'][0] for c in geo_gate)
        if gx1 > -0.2:
            bad(f'geo 装填门 x 到 {gx1:.2f} —— 导出空间应在 −X 侧（−X = 射手右侧）')
        else:
            ok(f'geo 装填门在导出空间右侧（x 到 {gx1:.2f}，bbmodel 作者空间为镜像的 +X）')
    for clip_name in ('reload_tactical', 'reload_empty'):
        a = clips.get(clip_name)
        if not a:
            continue
        cp = anim_channel(a, 'cartridge', 'position')
        if not cp:
            bad(f'{clip_name}：cartridge 没有位移关键帧')
            continue
        xmin = min(v[0] for _t, v in cp)
        xmax = max(v[0] for _t, v in cp)
        # 不变量：子弹永不越过中线到 +X 侧（那是装填门的对侧）；且必须有"门外"帧（x ≤ −0.8，
        # 机匣右壁 −0.29 之外）。收尾上膛到 x = 0 的中线是合法终点。
        if xmin > -0.8 or xmax > 0.05:
            bad(f'{clip_name}：子弹 x 偏移 [{xmin:.2f},{xmax:.2f}] —— 不是从装填门（−X）一侧'
                f'压入（越过了中线），几何与动画不在同一坐标空间（export.py 的镜像层漏了？）')
        else:
            ok(f'{clip_name}：子弹从装填门一侧压入（x {xmin:.2f} → {xmax:.2f}）')
    bolt_clip = clips.get('bolt')
    if bolt_clip:
        sp = anim_channel(bolt_clip, 'spent_shell', 'position')
        if sp:
            xe = sp[-1][1][0]
            if xe > -0.5:
                bad(f'bolt：空壳末帧 x {xe:.2f} —— 应向右上方（−X）抛出，与莫辛/AWM 同侧')
            else:
                ok(f'bolt：空壳向右上方抛出（末帧 x {xe:.2f}）')

    print('=== win94 门禁 ===')
    for n in notes:
        print('  ·', n)
    if problems:
        print(f'\n{len(problems)} 条不通过：')
        for p in problems:
            print('  [x]', p)
        return 1
    print('\n全部通过：两个环都闭合且与真枪尺寸一致 · 护圈包住扳机 · 环在转轴后方（正角度）·\n'
          '          装填门在机匣中后部 · 倍镜按真枪架高 · 动画 carrier 先下后上、'
          '5 发压弹 + 收尾上膛 · 换弹方向 = 装填门侧（几何/动画同坐标系）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
