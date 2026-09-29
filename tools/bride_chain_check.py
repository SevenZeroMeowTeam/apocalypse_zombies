"""骨骼链的**几何**自检（纯标准库，不经渲染器）：

自校验器只管关键帧层面的规矩（首末归零、循环缝、通道齐备），它看不出"链其实没接上"
或"整条链硬得像一根棍"。这个脚本补上两件事：

1. **连续性**：每段体块的「上缘中点」与上一段的「下缘中点」世界距离，应当**恒定**等于
   静置时的偏差量（拆链时特意留的设计垂坠/厚度差），逐帧抖动才是真错位。
2. **有没有真的形变**：末段的世界角度必须**明显大于**根段（逐段累加），否则就是"整条硬甩"。

用法：
    python tools/bride_chain_check.py                # 默认核面纱链 + 长发链
    python tools/bride_chain_check.py veil hair_fall # 指定链的根骨前缀
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bride_pose_probe import apply, rotm, sample

GEO = "art/bride/bride_zombie.geo.json"
ANIM = "art/bride/bride_zombie.animation.json"
TOL_GAP = 0.25      # u：间隙逐帧相对静置值的容许抖动（1u=6.25cm）
TOL_BEND = 1.12     # 末段世界角 / 根段世界角 的下限（>1 才算有波）。**别按标称增益取值**：
#   链是相位滞后的，各段峰值不在同一时刻，所以任何瞬间的累加都到不了标称值；段数越少、
#   幅度越小，偏离越大（两段鬓发在 veil_snare 里只有 1.15）。标定按**故障可分辨**来定：
#   实测三条链 1.15~1.91，而出故障时会落到 1.00~1.05（子段没写进去、或写成与父段同值），
#   1.12 正好把"弯的"和"坏的"分开。


def load():
    geo = json.load(open(GEO, encoding="utf-8"))
    anim = json.load(open(ANIM, encoding="utf-8"))
    return ({b["name"]: b for b in geo["minecraft:geometry"][0]["bones"]}, anim)


def make_world(bones, clipd):
    rot = {}
    for bn, ch in clipd.get("bones", {}).items():
        if ch.get("rotation"):
            rot[bn] = {float(k): (v["post"]["vector"] if isinstance(v, dict) else v)
                       for k, v in ch["rotation"].items()}

    def world(bn, t, cache):
        if bn in cache:
            return cache[bn]
        b = bones[bn]
        piv = b.get("pivot", [0, 0, 0])
        ang = sample(rot[bn], t) if bn in rot else [0.0, 0.0, 0.0]
        R = rotm(*ang)
        loc = list(piv)
        par = b.get("parent")
        if par in bones:
            PR, PL = world(par, t, cache)
            pp = bones[par].get("pivot", [0, 0, 0])
            loc = [PL[i] + apply(PR, [piv[i] - pp[i] for i in range(3)])[i] for i in range(3)]
            R = [[sum(PR[i][k] * R[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
        cache[bn] = (R, loc)
        return cache[bn]

    return world, rot


def edge_centers(bones, bn, R, loc):
    """该骨体块（取第一个 cube）在世界系里的上缘中点 / 下缘中点。"""
    c = bones[bn]["cubes"][0]
    org, size = c["origin"], c["size"]
    piv = bones[bn].get("pivot", [0, 0, 0])
    hi = [org[0] + size[0] / 2.0, org[1] + size[1], org[2] + size[2] / 2.0]
    lo = [org[0] + size[0] / 2.0, org[1], org[2] + size[2] / 2.0]

    def w(p):
        return [loc[i] + apply(R, [p[i] - piv[i] for i in range(3)])[i] for i in range(3)]
    return w(hi), w(lo)


def main():
    roots = sys.argv[1:] or ["veil", "hair_fall"]
    bones, anim = load()
    bad = 0
    for root in roots:
        chain = [root] + [n for n in bones
                          if n.startswith(root) and n != root
                          and _is_descendant(bones, n, root)]
        chain.sort(key=lambda n: bones[n].get("pivot", [0, 0, 0])[1], reverse=True)
        print(f"\n=== 链 {root} ：{len(chain)} 段  {chain}")
        for clip, clipd in anim["animations"].items():
            if root not in clipd.get("bones", {}):
                continue
            length = float(clipd["animation_length"])
            loop = bool(clipd.get("loop"))
            world, rot = make_world(bones, clipd)
            # 静置间隙（t=0 无旋转时应等于设计偏差），逐帧比对
            gaps, bends, angles = [], [], []
            for k in range(11):
                t = round(length * k / 10.0, 3)
                cache = {}
                prev_lo = None
                ang_sum = 0.0
                for bn in chain:
                    R, loc = world(bn, t, cache)
                    hi, lo = edge_centers(bones, bn, R, loc)
                    if prev_lo is not None:
                        gaps.append(math.dist(prev_lo, hi))
                    prev_lo = lo
                    a = rot.get(bn)
                    ang_sum += abs(sample(a, t)[0]) if a else 0.0
                    angles.append(ang_sum)
            g0 = _rest_gap(bones, chain)
            dev = max(abs(g - g0) for g in gaps) if gaps else 0.0
            peak = max(angles) if angles else 0.0
            root_peak = max(abs(sample(rot[chain[0]], length * k / 10.0)[0])
                            for k in range(11)) if chain[0] in rot else 0.0
            bend = (peak / root_peak) if root_peak > 1e-6 else 0.0
            ok_gap = dev <= TOL_GAP
            ok_bend = bend >= TOL_BEND or root_peak <= 1e-6
            flag = "OK " if (ok_gap and ok_bend) else "✗  "
            if not (ok_gap and ok_bend):
                bad += 1
            print(f"  {flag}{clip:22s} len={length:4} loop={str(loop):5s} "
                  f"静置间隙={g0:5.2f}u 逐帧偏差≤{dev:5.2f}u  根峰={root_peak:5.1f}° "
                  f"末段世界角累加峰={peak:6.1f}° 弯折比={bend:4.2f}")
    print(f"\n不达标剪辑数：{bad}")
    return 1 if bad else 0


def _is_descendant(bones, n, root):
    p = bones[n].get("parent")
    while p:
        if p == root:
            return True
        p = bones.get(p, {}).get("parent")
    return False


def _rest_gap(bones, chain):
    """静置（零旋转）时相邻段的间隙 —— 作为比对的基准值。"""
    prev_lo, g = None, 0.0
    for bn in chain:
        c = bones[bn]["cubes"][0]
        org, size = c["origin"], c["size"]
        hi = [org[0] + size[0] / 2.0, org[1] + size[1], org[2] + size[2] / 2.0]
        lo = [org[0] + size[0] / 2.0, org[1], org[2] + size[2] / 2.0]
        if prev_lo is not None:
            g = max(g, math.dist(prev_lo, hi))
        prev_lo = lo
    return g


if __name__ == "__main__":
    sys.exit(main())
