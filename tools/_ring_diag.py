# -*- coding: utf-8 -*-
"""诊断卡箍环的段数据：从 win94.bbmodel 读回 band_* 段，算端点与相邻间隙。"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
data = json.loads((ROOT / 'win94.bbmodel').read_text(encoding='utf-8'))
els = {e['name']: e for e in data.get('elements', [])}


def report(prefix, plane):
    segs = [e for n, e in els.items() if n.startswith(prefix + '_')]
    segs.sort(key=lambda e: int(e['name'].rsplit('_', 1)[1]))
    print(f'\n=== {prefix}  ({len(segs)} 段, plane={plane})')
    pts = []
    for e in segs:
        f, t = e['from'], e['to']
        rot = e.get('rotation') or [0, 0, 0]
        org = e.get('origin') or [0, 0, 0]
        if plane == 'xy':
            cx, cy = (f[0] + t[0]) / 2, (f[1] + t[1]) / 2
            ln = abs(t[0] - f[0])
            th = math.radians(rot[2])
            dx, dy = math.cos(th), math.sin(th)
            p0 = (cx - dx * ln / 2, cy - dy * ln / 2)
            p1 = (cx + dx * ln / 2, cy + dy * ln / 2)
        else:
            cy, cz = (f[1] + t[1]) / 2, (f[2] + t[2]) / 2
            ln = abs(t[2] - f[2])
            th = math.radians(rot[0])
            dy, dz = -math.sin(th), math.cos(th)
            p0 = (cy - dy * ln / 2, cz - dz * ln / 2)
            p1 = (cy + dy * ln / 2, cz + dz * ln / 2)
        pts.append((e['name'], p0, p1, rot, org, (f, t)))
    for name, p0, p1, rot, org, ft in pts:
        print(f'  {name:16s} len={math.hypot(p1[0]-p0[0], p1[1]-p0[1]):.4f} rot={[round(r,2) for r in rot]} '
              f'org={[round(o,3) for o in org]} p0=({p0[0]:.3f},{p0[1]:.3f}) p1=({p1[0]:.3f},{p1[1]:.3f})')
    print('  相邻间隙（按生成顺序）:')
    worst = 0.0
    for i in range(len(pts)):
        a = pts[i]
        b = pts[(i + 1) % len(pts)]
        d = math.hypot(a[2][0] - b[1][0], a[2][1] - b[1][1])
        worst = max(worst, d)
        print(f'    {a[0]} -> {b[0]}: {d:.4f} u' + ('   <== 大' if d > 0.03 else ''))
    print(f'  最大间隙 = {worst:.4f} u')


report('band_front', 'xy')
report('lever_loop', 'yz')
