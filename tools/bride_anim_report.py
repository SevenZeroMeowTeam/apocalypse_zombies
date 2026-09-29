# -*- coding: utf-8 -*-
"""手臂攻击动画的**定量**报告：把手在真实世界的位移算出来。

为什么要它：「手臂抬得明显不明显」是可以用数字回答的问题 —— 只要能把
hand_r 这个点在剪辑各时刻的世界坐标算出来，和静置姿态一比，就知道
抬了多少格、伸出去多远、有没有过肩。这比「看图感觉」硬，也能在改完
动画后立刻回归（数值掉出阈值就说明改动把动作改弱了）。

口径与 bride_pose_probe.py 完全一致（同一套骨骼链数学）：
- 每根骨绕自己的 pivot 旋转，子骨继承父骨的世界变换。
- 旋转按 Bedrock 惯例 X → Y → Z 依次施加。
- 世界坐标 y 向上、-Z 为前方（本工程铁律：枪口朝 -Z）。

用法：
    python tools/bride_anim_report.py                      # 三个手臂技能全查
    python tools/bride_anim_report.py skill_veil_chop      # 只查一个剪辑
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GEO = os.path.join(HERE, "..", "art/bride/bride_zombie.geo.json")
ANIM = os.path.join(HERE, "..", "art/bride/bride_zombie.animation.json")

# 手臂链（从肩到手）。右臂是攻击手，左臂参与平衡。
CHAIN = ["shoulder_r", "arm_r", "forearm_r", "hand_r"]
PREFIX = {}


def rotm(rx, ry, rz):
    a, b, c = (math.radians(v) for v in (rx, ry, rz))
    ca, sa, cb, sb, cc, sc = (math.cos(a), math.sin(a), math.cos(b),
                              math.sin(b), math.cos(c), math.sin(c))
    Rx = [[1, 0, 0], [0, ca, -sa], [0, sa, ca]]
    Ry = [[cb, 0, sb], [0, 1, 0], [-sb, 0, cb]]
    Rz = [[cc, -sc, 0], [sc, cc, 0], [0, 0, 1]]

    def mul(A, B):
        return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)]
                for i in range(3)]
    return mul(Rz, mul(Ry, Rx))


def apply(m, v):
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def sample(keys, t):
    ts = sorted(keys)
    if t <= ts[0]:
        return keys[ts[0]]
    if t >= ts[-1]:
        return keys[ts[-1]]
    for a, b in zip(ts, ts[1:]):
        if a <= t <= b:
            f = 0.0 if b == a else (t - a) / (b - a)
            return [keys[a][i] + (keys[b][i] - keys[a][i]) * f for i in range(3)]
    return keys[ts[-1]]


def load(clip):
    geo = json.load(open(GEO, encoding="utf-8"))
    anim = json.load(open(ANIM, encoding="utf-8"))
    bones = {b["name"]: b for b in geo["minecraft:geometry"][0]["bones"]}
    d = anim["animations"][clip]
    rot = {}
    for bn, ch in d.get("bones", {}).items():
        if "rotation" in ch:
            rot[bn] = {float(k): (v["post"]["vector"] if isinstance(v, dict) else v)
                       for k, v in ch["rotation"].items()}
    return bones, rot, d


def world(bones, rot, bn, t, cache):
    """骨的世界 (旋转矩阵, pivot 世界位置)。"""
    key = (bn, round(t, 4))
    if key in cache:
        return cache[key]
    b = bones[bn]
    piv = b.get("pivot", [0, 0, 0])
    rr = rot.get(bn)
    R = rotm(*(sample(rr, t) if rr else [0.0, 0.0, 0.0]))
    loc = list(piv)
    if b.get("parent") and b["parent"] in bones:
        PR, PL = world(bones, rot, b["parent"], t, cache)
        dp = [piv[i] - bones[b["parent"]].get("pivot", [0, 0, 0])[i] for i in range(3)]
        loc = [PL[i] + apply(PR, dp)[i] for i in range(3)]
        R = [[sum(PR[i][k] * R[k][j] for k in range(3)) for j in range(3)]
             for i in range(3)]
    cache[key] = (R, loc)
    return cache[key]


def tip(bones, rot, bn, t, cache):
    """骨的**远端**世界坐标：pivot 再沿骨长（到子骨 pivot 或体块末端）走一格。

    hand_r 常常没有子骨，所以退化到「体块远端」—— 取该骨所有体块里
    离 pivot 最远的那个角点，绕 pivot 转过去。
    """
    R, loc = world(bones, rot, bn, t, cache)
    piv = bones[bn].get("pivot", [0, 0, 0])
    pts = []
    for cube in bones[bn].get("cubes", []):
        org, size = cube["origin"], cube["size"]
        for sx in (0, 1):
            for sy in (0, 1):
                for sz in (0, 1):
                    p = [org[i] + (size[i] if (sx, sy, sz)[i] else 0.0)
                         for i in range(3)]
                    pts.append(p)
    if not pts:
        return loc
    far = max(pts, key=lambda p: sum((p[i] - piv[i]) ** 2 for i in range(3)))
    d = [far[i] - piv[i] for i in range(3)]
    off = apply(R, d)
    return [loc[i] + off[i] for i in range(3)]


def elevation(shoulder, hand):
    """手相对肩的方向：抬升角 + 方向分量。

    抬升角 = 与竖直向下方向(-Y)的夹角，0=自然下垂、90=平举、180=举到头顶。
    方向分量 (dx,dy,dz) 是归一化后的世界方向 —— 手抬过肩以后「侧摆/前摆」
    这类以「向下」为参考的角会退化（分母换个符号就翻 180°），分量不会。
    """
    d = [hand[i] - shoulder[i] for i in range(3)]
    n = math.sqrt(sum(v * v for v in d)) or 1e-9
    up = math.degrees(math.acos(max(-1.0, min(1.0, -d[1] / n))))
    return up, [v / n for v in d], n


def report(clip, step=0.15):
    bones, rot, d = load(clip)
    L = d.get("animation_length", 0)
    cache = {}
    base = None
    rows = []
    t = 0.0
    while t <= L + 1e-9:
        sh = world(bones, rot, "shoulder_r", t, cache)[1]
        hd = tip(bones, rot, "hand_r", t, cache)
        up, dirv, reach = elevation(sh, hd)
        if base is None:
            base = (hd, up)
        rows.append((t, hd[1], hd[2], hd[0], up, dirv[0], dirv[1], dirv[2], reach))
        t = round(t + step, 4)
    # 峰值帧（抬升角最大 = 手最高/最前的那一下）
    peak = max(rows, key=lambda r: r[4])
    print("=== %s   时长 %.2fs  静置抬升角 %.1f°" % (clip, L, base[1]))
    print("    t     手高y   前后z   左右x   抬升角  方向(dx,dy,dz)     离肩距离")
    for (t, y, z, x, up, dx, dy, dz, reach) in rows:
        mark = "  ← 峰值" if abs(t - peak[0]) < 1e-6 else ""
        print("  %4.2f  %7.1f %7.1f %7.1f   %6.1f°  (%5.2f,%5.2f,%5.2f) %6.1fu%s"
              % (t, y, z, x, up, dx, dy, dz, reach, mark))
    print("    峰值：t=%.2fs 抬升 %.1f°（静置 %.1f°，净抬 %.1f°）｜"
          "手比静置高 %.1fu = %.2f 格、前伸 %.2fu = %.2f 格、离肩 %.1fu"
          % (peak[0], peak[4], base[1], peak[4] - base[1],
             peak[1] - base[0][1], (peak[1] - base[0][1]) / 16.0,
             -(peak[2] - base[0][2]), -(peak[2] - base[0][2]) / 16.0, peak[8]))
    print()
    return peak, base


def mangle(A, B):
    """两个旋转矩阵之间的夹角（度）：把 B 转到 A 的坐标系里看净转角。

    用来量「袖子相对前臂滞后多少」—— 滞后是拖尾（好看），
    但超过约 35° 就不再是拖尾，而是钟形袖看着跟手臂脱开了（像断裂）。
    """
    R = [[sum(A[k][i] * B[k][j] for k in range(3)) for j in range(3)]
         for i in range(3)]
    tr = R[0][0] + R[1][1] + R[2][2]
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1.0) / 2.0))))


def sleeve_lag(clip, step=0.05, limit=35.0):
    """袖骨相对它父骨（前臂 / 上一节袖）的滞后角，逐帧列出峰值。"""
    bones, rot, d = load(clip)
    cache = {}
    L = d.get("animation_length", 0)
    pairs = [("sleeve_r", "forearm_r"), ("sleeve_r2", "sleeve_r")]
    worst = {}
    t = 0.0
    while t <= L + 1e-9:
        for child, parent in pairs:
            if child not in bones or parent not in bones:
                continue
            Rc = world(bones, rot, child, t, cache)[0]
            Rp = world(bones, rot, parent, t, cache)[0]
            a = mangle(Rc, Rp)
            if a > worst.get(child, (0, 0))[0]:
                worst[child] = (a, t)
        t = round(t + step, 4)
    out = []
    for child, parent in pairs:
        if child in worst:
            a, t = worst[child]
            out.append((child, parent, a, t))
    print("=== %s 袖骨滞后" % clip)
    for child, parent, a, t in out:
        flag = "✓" if a <= limit else "✗ 超过 %.0f° —— 看着像跟手臂脱开" % limit
        print("    %-10s 相对 %-10s 峰值 %5.1f°（t=%.2fs）  %s"
              % (child, parent, a, t, flag))
    print()
    return out


def centroid(bones, rot, bn, t, cache):
    """骨骼所有体块中心的世界坐标（用来量「袖片还在不在手边」）。"""
    R, loc = world(bones, rot, bn, t, cache)
    piv = bones[bn].get("pivot", [0, 0, 0])
    pts = []
    for c in bones[bn].get("cubes", []):
        ctr = [c["origin"][i] + c["size"][i] / 2.0 for i in range(3)]
        d = [ctr[i] - piv[i] for i in range(3)]
        pts.append([loc[i] + apply(R, d)[i] for i in range(3)])
    if not pts:
        return None
    return [sum(p[i] for p in pts) / len(pts) for i in range(3)]


def sleeve_gap(clip, step=0.05, ratio=2.0):
    """手到最近袖片体块中心的距离：静置 vs 峰值。

    袖片是**套在前臂上**的（体块 13.6~16.6u 正好包着肘到腕），所以它相对父骨
    只能小幅滞后。一旦这个距离涨到静置的 2 倍以上，屏幕上看到的就不是「袖口
    拖尾」，而是「手/前臂裸露、袖片飘在旁边」。这是纯数字判据，不靠看图感觉。
    """
    bones, rot, d = load(clip)
    cache = {}
    L = d.get("animation_length", 0)
    rest, worst, rows = None, (0.0, 0.0), []
    t = 0.0
    while t <= L + 1e-9:
        h = centroid(bones, rot, "hand_r", t, cache)
        best = None
        for bn in ("sleeve_r", "sleeve_r2"):
            s = centroid(bones, rot, bn, t, cache)
            if s is None:
                continue
            dd = math.sqrt(sum((h[i] - s[i]) ** 2 for i in range(3)))
            best = dd if best is None else min(best, dd)
        if best is not None:
            if rest is None:
                rest = best
            rows.append((t, best))
            if best > worst[1]:
                worst = (t, best)
        t = round(t + step, 4)
    ok = rest is not None and worst[1] <= rest * ratio
    print("=== %s 手↔袖片距离" % clip)
    print("    静置 %.2fu → 峰值 %.2fu（t=%.2fs），是静置的 %.1f 倍   %s"
          % (rest, worst[1], worst[0], worst[1] / rest,
             "✓ 袖片一直贴着手" if ok else "✗ 超过 %.1f 倍：袖片已经飘离手/前臂" % ratio))
    print()
    return ok, rest, worst


def main():
    clips = sys.argv[1:] or ["skill_veil_swipe", "skill_flower_dart",
                             "skill_veil_chop"]
    got = []
    for c in clips:
        peak, base = report(c)
        got.append((c, peak[4] - base[1], peak))
    weak = min(got, key=lambda g: g[1])
    print("三个技能净抬升：%s" % "  ".join("%s %.1f°" % (c, g) for c, g, _ in got))
    print("最弱的是 %s（净抬 %.1f°）" % (weak[0], weak[1]))
    bad = [c for c, g, _ in got if g < 45.0]
    print("净抬升全部 ≥45°（不到 45° 就不叫「明显」）：%s"
          % ("是 ✓" if not bad else "否 ✗ —— " + ", ".join(bad)))
    print()
    lags = []
    for c in clips:
        lags += sleeve_lag(c)
    over = [(ch, a) for ch, _p, a, _t in lags if a > 35.0]
    print("袖骨滞后全部 ≤35°（拖尾而非脱开）：%s"
          % ("是 ✓" if not over else "否 ✗ —— "
             + ", ".join("%s %.1f°" % (ch, a) for ch, a in over)))
    print()
    gaps = [sleeve_gap(c) for c in clips]
    bad_gap = [c for c, (ok, _r, _w) in zip(clips, gaps) if not ok]
    print("袖片全程贴着手（≤2 倍静置距离）：%s"
          % ("是 ✓" if not bad_gap else "否 ✗ —— " + ", ".join(bad_gap)))


if __name__ == "__main__":
    main()
