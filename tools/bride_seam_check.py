"""裙摆「层间是否裂开」检查（纯标准库，不经渲染器）。

为什么不能拿 `bride_chain_check.py` 的间隙判据核裙摆：它的量是「上一段体块下缘中点 → 下一段
上缘中点」的距离。对**条状**布（面纱/长发/拖尾）那是合适的；但裙摆是**同心层叠的环**，
每根骨横跨 9 块板，层与层是**故意重叠**的（静置时上环 y 9.8~13.2、中环 7.6~10.0，
重叠 0.2u）。一圈环相对上一圈转过一个角度时，中点距离必然大幅变化（实测 0.8u），
但那不叫裂开 —— 真正会露馅的是**层与层在竖直方向彻底分开**。

所以这里量的是**竖直重叠量**：对同一组的三层，逐帧算
    overlap = (下层全部顶点 y 的最大值) - (上层全部顶点 y 的最小值)
≥0 表示两层仍相互咬合（看到的是厚布层叠），<0 才是裂开，且负值就是裂口高度（u）。

用法：
    python tools/bride_seam_check.py            # 全部剪辑
    python tools/bride_seam_check.py skill_veil_snare
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bride_pose_probe import apply, rotm, sample

GEO = "art/bride/bride_zombie.geo.json"
ANIM = "art/bride/bride_zombie.animation.json"
GROUPS = [("skirt", "skirt2", "skirt3"), ("hem_l", "hem_l2", "hem_l3"), ("hem_r", "hem_r2", "hem_r3")]
STEPS = 41          # 每个剪辑采样帧数
TOL = 0.0           # 允许的最小重叠（u）


def load():
    geo = json.load(open(GEO, encoding="utf-8"))
    return ({b["name"]: b for b in geo["minecraft:geometry"][0]["bones"]},
            json.load(open(ANIM, encoding="utf-8"))["animations"])


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


def ys(bones, bn, R, loc):
    """该骨所有体块 8 个角点的世界 y 列表。"""
    piv = bones[bn].get("pivot", [0, 0, 0])
    out = []
    for c in bones[bn].get("cubes", []):
        org, size = c["origin"], c["size"]
        for dx in (0, size[0]):
            for dy in (0, size[1]):
                for dz in (0, size[2]):
                    p = [org[0] + dx, org[1] + dy, org[2] + dz]
                    out.append(loc[1] + apply(R, [p[i] - piv[i] for i in range(3)])[1])
    return out


def main():
    want = sys.argv[1:]
    bones, anim = load()
    worst_all, bad, checked, skip = 9e9, 0, 0, []
    for clip, clipd in anim.items():
        if want and clip not in want:
            continue
        length = float(clipd["animation_length"])
        world, rot = make_world(bones, clipd)
        rows = []
        for grp in GROUPS:
            if not all(b in bones for b in grp):
                continue
            lo_ov = 9e9
            for k in range(STEPS + 1):
                t = round(length * k / float(STEPS), 4)
                cache = {}
                for upper, lower in zip(grp, grp[1:]):
                    if upper not in rot and lower not in rot:
                        continue
                    Ru, lu = world(upper, t, cache)
                    Rl, ll = world(lower, t, cache)
                    ov = max(ys(bones, lower, Rl, ll)) - min(ys(bones, upper, Ru, lu))
                    lo_ov = min(lo_ov, ov)
            if lo_ov > 1e8:      # 该剪辑根本不驱动这组（未驱动 ≠ 通过）
                rows.append((grp[0], None)); continue
            rows.append((grp[0], lo_ov))
            if lo_ov < 1e8:
                worst_all = min(worst_all, lo_ov)
        flag = "OK " if all(v is not None and v >= TOL for _, v in rows) else "✗  "
        if any(v is None for _, v in rows) and all(v is None for _, v in rows):
            skip.append(clip)
        else:
            checked += 1
            if not all(v is None or v >= TOL for _, v in rows):
                bad += 1
        print(f"  {flag}{clip:22s} " + "  ".join(
            f"{g} 最小重叠 {v:+6.2f}u" if v is not None else f"{g} 未驱动" for g, v in rows))
    print(f"\n最差重叠 {worst_all:+.2f}u（≥0 = 层间仍咬合；<0 的负值就是裂口高度）"
          f"，裂缝剪辑数：{bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
