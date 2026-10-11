#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 本脚本 import numpy（Windows 的 py 会按 shebang 选解释器）→ 用 py -3.13 跑，见 rsc_1917_preview.py 顶部说明。
"""RSC M1917 侧视轮廓对表 —— 模型的剪影 vs 参考图量出来的 profile.json，逐列算误差。

profile.json（art/rsc_1917/）是量取参考照片得到的真值表：
    profile[i] = {z_mm: 距枪口 mm, top_mm: 轴上高度, bot_mm: 轴下深度}（mm，相对膛线轴）
本脚本把 geo.json 的方块按 Z 分列求出模型的 top/bot，同一套 mm 口径逐列比对：
    * 每列误差 = 模型 - 真值（正=模型高了/深了）
    * 分段（每 100 mm）均值，方便看是哪一段不像
    * 交并比 IoU（两个剪影按 1px 掩码重叠）
    * 最差 12 列
退出码：RMS 超阈值（默认 top/bot 各 3.0 mm，约 0.05 u）→ 1，给门禁用。

用法：py -3.13 tools/rsc_1917_silhouette.py [--tol 3.0] [--geo 路径] [--verbose]
"""

import argparse
import json

import numpy as np

MM = 16 / 1000
PROFILE = 'art/rsc_1917/profile2.json'   # alpha 剪影量取（profile.json 是旧的亮度法，y 轴差 9mm）
GEO = 'art/rsc_1917/rsc_1917.geo.json'


def model_columns(geo_path, z_step_mm, skip=()):
    geo = json.load(open(geo_path, encoding='utf-8'))['minecraft:geometry'][0]
    cubes = []
    for b in geo['bones']:
        if b['name'] in skip:          # 手/弹药这类非枪身件不算剪影（参考图是裸枪）
            continue
        for c in b.get('cubes', []):
            o = np.array(c['origin'], float)
            cubes.append((o, o + np.array(c['size'], float)))
    z0 = min(c[0][2] for c in cubes)
    z1 = max(c[1][2] for c in cubes)
    n = int(round((z1 - z0) / MM / z_step_mm)) + 1
    zs = z0 + np.arange(n) * (z_step_mm * MM)
    top = np.full(n, -1e9)
    bot = np.full(n, 1e9)
    for lo, hi in cubes:
        # 该方块覆盖的列
        i0 = np.searchsorted(zs, lo[2] - 1e-9, 'left')
        i1 = np.searchsorted(zs, hi[2] + 1e-9, 'right')
        if i1 <= i0:
            continue
        top[i0:i1] = np.maximum(top[i0:i1], hi[1])
        bot[i0:i1] = np.minimum(bot[i0:i1], lo[1])
    return zs, top / MM, bot / MM, (z0, z1)


def print_ascii(rz, rt, rb, mt, mb, cols=132, rows=34):
    """把两条剪影按同一口径打成 ASCII（上=真值，下=模型），毫米级对照。"""
    z0, z1 = float(rz[0]), float(rz[-1])
    lo = min(float(rb.min()), float(mb.min()))
    hi = max(float(rt.max()), float(rt.max()))
    lo, hi = int(lo) - 4, int(hi) + 4
    zi = np.linspace(z0, z1, cols)
    R_t, R_b = np.interp(zi, rz, rt), np.interp(zi, rz, rb)
    M_t, M_b = np.interp(zi, rz, mt), np.interp(zi, rz, mb)
    yi = np.linspace(lo, hi, rows)

    def grid(t, b):
        return (yi[:, None] <= t[None, :]) & (yi[:, None] >= b[None, :])

    A, B = grid(R_t, R_b), grid(M_t, M_b)
    print('\n------ 剪影 ASCII（每列 %.0f mm，上行刻度为距枪口 mm；轴 = 膛线）------'
          % ((z1 - z0) / cols))
    hdr = ''.join('|' if (i % 11 == 0) else ' ' for i in range(cols))
    print('        ' + hdr)
    print('        ' + ''.join(
        ('%d' % (z0 + i * (z1 - z0) / cols / 100))[-1] if i % 11 == 0 else ' ' for i in range(cols)))
    for r in range(rows):
        tag = ('%+4d ' % yi[r])
        ra = ''.join('#' if A[r, c] else '.' for c in range(cols))
        rb_ = ''.join('o' if B[r, c] else ('#' if A[r, c] else '.') for c in range(cols))
        print('%s 真值 %s' % (tag, ra))
        print('      模型 %s' % rb_)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--geo', default=GEO)
    ap.add_argument('--profile', default=PROFILE)
    ap.add_argument('--skip-bones', default='hand_l',
                    help='这些骨的方块不计入剪影（默认 hand_l）')
    ap.add_argument('--tol', type=float, default=3.0, help='上缘 RMS 上限（mm）')
    ap.add_argument('--tol-bot', type=float, default=5.0, help='下缘 RMS 上限（mm）')
    ap.add_argument('--min-iou', type=float, default=0.90, help='IoU 下限')
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--ascii', action='store_true', help='打印剪影 ASCII 对照图')
    a = ap.parse_args()
    skip = tuple(x.strip() for x in a.skip_bones.split(',') if x.strip())

    ref = json.load(open(a.profile, encoding='utf-8'))
    if 'cols' in ref:                      # profile2.json 结构
        prof = sorted(ref['cols'], key=lambda q: q['z_mm'])
        for q in prof:
            q['top_mm'], q['bot_mm'] = q['top'], q['bot']
    else:
        prof = sorted(ref['profile'], key=lambda p: p['z_mm'])
    rz = np.array([p['z_mm'] for p in prof])
    rt = np.array([p['top_mm'] for p in prof])
    rb = np.array([p['bot_mm'] for p in prof])
    step = float(rz[1] - rz[0])

    zs, mt, mb, (mz0, mz1) = model_columns(a.geo, step, skip=skip)
    mz_mm = (zs - mz0) / MM                      # 模型列 → 距枪口 mm
    # 采样到参考列
    mt_i = np.interp(rz, mz_mm, mt)
    mb_i = np.interp(rz, mz_mm, mb)
    d_top = mt_i - rt
    d_bot = mb_i - rb
    rms_t = float(np.sqrt(np.mean(d_top ** 2)))
    rms_b = float(np.sqrt(np.mean(d_bot ** 2)))
    mx_t = float(np.max(np.abs(d_top)))
    mx_b = float(np.max(np.abs(d_bot)))

    def iou():
        n = len(rz)
        lo = int(min(rb.min(), mb_i.min())) - 6
        hi = int(max(rt.max(), mt_i.max())) + 6
        rng = np.arange(lo, hi)
        A = (rng[None, :] <= rt[:, None]) & (rng[None, :] >= rb[:, None])
        B = (rng[None, :] <= mt_i[:, None]) & (rng[None, :] >= mb_i[:, None])
        return float((A & B).sum()) / float((A | B).sum())

    print('模型 Z 范围 %.2f..%.2f u（全长 %.2f u = %.0f mm；真枪 %.0f mm）'
          % (mz0, mz1, mz1 - mz0, (mz1 - mz0) / MM, ref['total_mm']))
    print('轮廓交并比 IoU = %.3f    上缘 RMS %.2f mm（最大 %.2f）   下缘 RMS %.2f mm（最大 %.2f）'
          % (iou(), rms_t, mx_t, rms_b, mx_b))
    print()
    print('%-10s %8s %8s %8s %8s' % ('距枪口mm', '真值上', '模型上', '真值下', '模型下'))
    seg = np.arange(0, ref['total_mm'], 100.0)
    for s in seg:
        m = (rz >= s) & (rz < s + 100)
        if not m.any():
            continue
        print('%-10.0f %8.1f %8.1f %8.1f %8.1f   Δ上 %+6.1f  Δ下 %+6.1f'
              % (s, rt[m].mean(), mt_i[m].mean(), rb[m].mean(), mb_i[m].mean(),
                 d_top[m].mean(), d_bot[m].mean()))
    print()
    order = np.argsort(-np.maximum(np.abs(d_top), np.abs(d_bot)))[:12]
    print('最差 12 列：')
    for i in sorted(order):
        print('  z=%6.0f mm  上 %+7.1f  下 %+7.1f' % (rz[i], d_top[i], d_bot[i]))
    if a.verbose:
        print()
        for i in range(0, len(rz), 25):
            print('  z=%6.0f  真值[%7.1f,%7.1f]  模型[%7.1f,%7.1f]'
                  % (rz[i], rt[i], rb[i], mt_i[i], mb_i[i]))
    if a.ascii:
        print_ascii(rz, rt, rb, mt_i, mb_i)
    # 判据：IoU 下限 + 上下缘 RMS 上限（点状特征——拖曳钩/背带环的尖——离散化后
    # 会贡献几列 20~36 mm 的离群值，故上缘/下缘分开定阈值；最大误差只作参考打印）
    i_val = iou()
    bad = not (i_val >= a.min_iou and rms_t <= a.tol and rms_b <= a.tol_bot)
    print('\n判据：IoU ≥ %.2f（实测 %.3f）  上缘 RMS ≤ %.1f mm（实测 %.2f）  下缘 RMS ≤ %.1f mm（实测 %.2f）'
          % (a.min_iou, i_val, a.tol, rms_t, a.tol_bot, rms_b))
    print('%s' % ('*** 轮廓对不上' if bad else '轮廓在容差内'))
    raise SystemExit(1 if bad else 0)


if __name__ == '__main__':
    main()
