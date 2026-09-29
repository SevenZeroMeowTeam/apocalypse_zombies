# -*- coding: utf-8 -*-
"""核对探针与报告器用的是不是同一套骨骼数学（逐帧极端坐标）。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bride_anim_report import load, world, rotm, apply, sample   # noqa: E402

CHAIN = ["shoulder_r", "arm_r", "forearm_r", "hand_r", "sleeve_r", "sleeve_r2"]


def corners(bones, rot, bn, t, cache):
    R, loc = world(bones, rot, bn, t, cache)
    piv = bones[bn].get("pivot", [0, 0, 0])
    pts = []
    for cube in bones[bn].get("cubes", []):
        org, size = cube["origin"], cube["size"]
        for sx in (0, 1):
            for sy in (0, 1):
                for sz in (0, 1):
                    p = [org[i] + (size[i] if (sx, sy, sz)[i] else 0.0) for i in range(3)]
                    d = [p[i] - piv[i] for i in range(3)]
                    off = apply(R, d)
                    pts.append([loc[i] + off[i] for i in range(3)])
    return pts


def main():
    clip = sys.argv[1] if len(sys.argv) > 1 else "skill_veil_chop"
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 0.30
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    bones, rot, d = load(clip)
    print("%s  画布：y 可见 0~%0.1fu（H=460, SCALE=11）" % (clip, 38.2))
    print("  帧     t      y 范围        z 范围      是否越出画布上沿")
    for i in range(n):
        t = round(i * interval, 3)
        cache = {}
        ys, zs = [], []
        for bn in CHAIN:
            if bn not in bones:
                continue
            for p in corners(bones, rot, bn, t, cache):
                ys.append(p[1])
                zs.append(p[2])
        over = "是 ← 方块跑到画布上方看不见" if max(ys) > 38.2 else "否"
        print("  %2d  %5.2f  %5.1f~%5.1f  %6.1f~%5.1f   %s"
              % (i, t, min(ys), max(ys), min(zs), max(zs), over))


if __name__ == "__main__":
    main()
