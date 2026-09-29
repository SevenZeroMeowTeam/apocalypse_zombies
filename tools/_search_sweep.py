# -*- coding: utf-8 -*-
"""搜索：在「弓臂径向滑移 ≤0.35u」的自检约束下，弓臂最多能向后掠多少。

背景：弦的半段长 STRING_LEN 是**从弦心（牙）量到梢部**的常数，拉满时弦心后移，
梢部必须沿臂轴滑移才能维持该长度；滑移量对「梢部方向相对 x 轴的夹角」极敏感
（原设计梢部 −11.4° 恰在残差极小处，滑移仅 0.28u）。直接改梢部 z 会把它推到 1.95u ✗。

做法：网格扫描 (LIMB_TIP_Z, LATCH_Z, FLEX_MAX)，每次改写常量、跑真生成器、解析
「臂轴滑移 ≤X」与失败条数，最后把通过项里**后掠最多**的一组写回去。
"""
import re
import subprocess
import sys

P = 'tools/crossbow_v2.py'
ARC = -0.55                     # 曲度：只进几何、不参与解算，故单独固定
with open(P, 'r', encoding='utf-8', newline='') as fh:
    BASE = fh.read()


def apply(tip_z, latch_z, flex):
    s = BASE
    s = re.sub(r'LIMB_TIP_X, LIMB_TIP_Z = [\d.\-]+, [\d.\-]+',
               'LIMB_TIP_X, LIMB_TIP_Z = 4.55, %.2f' % tip_z, s)
    s = re.sub(r'LATCH_Z = -?[\d.]+', 'LATCH_Z = %.2f' % latch_z, s)
    s = re.sub(r'Z_RAIL0, Z_RAIL1 = -?[\d.]+, -?[\d.]+',
               'Z_RAIL0, Z_RAIL1 = -6.60, %.2f' % latch_z, s)
    s = re.sub(r'FLEX_MAX = -?[\d.]+', 'FLEX_MAX = %.1f' % flex, s)
    s = re.sub(r'LIMB_ARC = -?[\d.]+', 'LIMB_ARC = %.2f' % ARC, s)
    with open(P, 'w', encoding='utf-8', newline='') as fh:
        fh.write(s)


def run():
    r = subprocess.run([sys.executable, 'tools/crossbow_v2.py'],
                       capture_output=True, cwd='.')
    out = r.stdout.decode('utf-8', 'replace')
    m = re.search(r'臂轴滑移 ≤([\d.]+)', out)
    return (float(m.group(1)) if m else 999.0), out.count('[X]')


rows = []
for tip_z in (-7.30, -7.10, -6.95, -6.80, -6.65, -6.50, -6.35, -6.20):
    for draw in (2.4, 2.8, 3.2):
        apply(tip_z, tip_z + draw, -36.0)
        slide, nf = run()
        rows.append((tip_z, draw, -36.0, slide, nf))
        print('tip_z=%.2f draw=%.1f flex=-36.0 -> slide=%.3f fails=%d' % (tip_z, draw, slide, nf))
        sys.stdout.flush()

# 通过项里取「后掠最多」= tip_z 最大者；并列取 fail 最少、slide 最小
ok = [r for r in rows if r[4] == 0]
print()
print('=== 可用组合 %d 组 ===' % len(ok))
for r in sorted(ok, key=lambda r: (-r[0], r[3])):
    print('  tip_z=%.2f draw=%.1f flex=%.1f slide=%.3f' % r[:4])
if ok:
    best = sorted(ok, key=lambda r: (-r[0], r[3]))[0]
    print()
    print('=== 选定：tip_z=%.2f draw=%.1f flex=%.1f（slide=%.3f）===' % best[:4])
    apply(best[0], best[0] + best[1], best[2])
    slide, nf = run()
    print('回写后复跑：slide=%.3f fails=%d' % (slide, nf))
else:
    print('*** 无一通过，需放宽曲度或减小 FLEX_MAX ***')
    apply(-7.30, -4.20, -36.0)      # 还原
    run()
