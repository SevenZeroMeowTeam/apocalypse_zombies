"""纯标准库「骨骼变换探测」：把某根骨链在若干时刻的**真实世界变换**投影成侧视图。

为什么要它：Blender 被禁用（第三方 tripo_addon 会挂主线程），但"布料有没有真的起波"
必须看图才能判。这里不复用任何渲染器 —— 直接从 geo/anim 两个 JSON 取骨骼 pivot、
父子关系、体块尺寸与关键帧旋转，逐帧算世界变换，再做正交投影光栅化。

数学口径（够本用，且已在代码里写明）：
- 每根骨绕**自己的 pivot** 旋转；子骨的位置继承父骨的世界变换（骨骼是链式驱动）。
- 旋转按 Bedrock 惯例的 X → Y → Z 依次施加；面纱这类**以 X 轴摆动为主**的动作，
  该次序与实机的差异可以忽略（要精确判读 Y/Z 占主导的动作时需另行对时序）。
- 投影：看沿 -X 方向的**侧视**（Y 向上、Z 向右）= 判断前后摆动/拖尾的视角。

用法：
    python tools/bride_pose_probe.py <clip> <骨骼前缀> [帧数] [间隔秒]
    例：python tools/bride_pose_probe.py walk veil 6 0.13
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bride_face_crop import write_png

GEO = "art/bride/bride_zombie.geo.json"
ANIM = "art/bride/bride_zombie.animation.json"
PACK = "src/main/resources/assets/apocalypse_zombies/geo/bride_zombie.geo.json"
PACKA = "src/main/resources/assets/apocalypse_zombies/animations/bride_zombie.animation.json"


def rotm(rx, ry, rz):
    """返回 3x3 旋转矩阵（度）。按 X → Y → Z 施加。"""
    a, b, c = (math.radians(v) for v in (rx, ry, rz))
    ca, sa, cb, sb, cc, sc = (math.cos(a), math.sin(a), math.cos(b),
                              math.sin(b), math.cos(c), math.sin(c))
    m = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    Rx = [[1, 0, 0], [0, ca, -sa], [0, sa, ca]]
    Ry = [[cb, 0, sb], [0, 1, 0], [-sb, 0, cb]]
    Rz = [[cc, -sc, 0], [sc, cc, 0], [0, 0, 1]]

    def mul(A, B):
        return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

    m = mul(Rz, mul(Ry, Rx))
    return m


def apply(m, v):
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def sample(keys, t):
    """关键帧字典 {t: [x,y,z]} 在时刻 t 的取值（线性插值）。"""
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


def main():
    clip = sys.argv[1] if len(sys.argv) > 1 else "walk"
    prefix = sys.argv[2] if len(sys.argv) > 2 else "veil"
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    step = float(sys.argv[4]) if len(sys.argv) > 4 else 0.13

    geo = json.load(open(PACK if os.path.exists(PACK) else GEO, encoding="utf-8"))
    anim = json.load(open(PACKA if os.path.exists(PACKA) else ANIM, encoding="utf-8"))
    bones = {b["name"]: b for b in geo["minecraft:geometry"][0]["bones"]}
    clipd = anim["animations"][clip]
    rot = {}
    for bn, ch in clipd.get("bones", {}).items():
        r = ch.get("rotation")
        if r:
            rot[bn] = {float(k): v["post"]["vector"] if isinstance(v, dict) else v
                       for k, v in r.items()}

    def world(bn, t, cache):
        if bn in cache:
            return cache[bn]
        b = bones[bn]
        piv = b.get("pivot", [0, 0, 0])
        rr = rot.get(bn)
        ang = sample(rr, t) if rr else [0.0, 0.0, 0.0]
        R = rotm(*ang)
        loc = [piv[i] for i in range(3)]
        if b.get("parent") and b["parent"] in bones:
            PR, PL = world(b["parent"], t, cache)
            d = [piv[i] - bones[b["parent"]].get("pivot", [0, 0, 0])[i] for i in range(3)]
            loc = [PL[i] + apply(PR, d)[i] for i in range(3)]
            R = [[sum(PR[i][k] * R[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
        cache[bn] = (R, loc)
        return cache[bn]

    # 只画目标前缀的体块：世界坐标 → 侧视正交投影（Y 上、Z 右）
    # prefix 支持逗号分隔（如 "shoulder,arm,forearm,hand,sleeve"）——单前缀没法
    # 框住「肩→手」整条链，那样就只能看到上臂，判断不了手抬到哪儿。
    prefs = [p for p in prefix.split(",") if p]
    targets = [n_ for n_ in bones if any(n_.startswith(p) for p in prefs)]
    SCALE, PAD = 11, 40
    W = n * 120 + PAD * 2
    H = 460
    img = bytearray(W * H * 4)
    for i in range(W * H):
        img[i * 4] = img[i * 4 + 1] = img[i * 4 + 2] = 255
        img[i * 4 + 3] = 255          # 白底

    def plot(x, y, col):
        if 0 <= x < W and 0 <= y < H:
            o = (y * W + x) * 4
            img[o:o + 4] = bytes(col[:3]) + b"\xff"   # 必须补第 4 个字节：
            # bytes(3 元组) 只有 3 字节，会**缩短** bytearray ⇒ PNG 末尾截断、解码失败

    def line(p, q, col):
        dx, dy = q[0] - p[0], q[1] - p[1]
        k = int(max(abs(dx), abs(dy)))
        for s in range(k + 1):
            f = 0.0 if k == 0 else s / float(k)
            plot(int(p[0] + dx * f), int(p[1] + dy * f), col)

    palette = {0: (52, 84, 140), 1: (86, 128, 190), 2: (132, 108, 190), 3: (196, 96, 140)}
    for fi in range(n):
        t = round(fi * step, 3)
        cx = PAD + fi * 120
        # 地面参考线：脚底（y=0）
        for x in range(cx + 4, cx + 116):
            plot(x, int(H - 40 - 0 * SCALE), (206, 206, 214))
        cache = {}
        for bi, bn in enumerate(sorted(targets)):
            R, loc = world(bn, t, cache)
            piv = bones[bn].get("pivot", [0, 0, 0])
            for cube in bones[bn].get("cubes", []):
                org, size = cube["origin"], cube["size"]
                corners = []
                for sx in (0, 1):
                    for sy in (0, 1):
                        for sz in (0, 1):
                            p = [org[i] + (size[i] if (sx, sy, sz)[i] else 0.0) for i in range(3)]
                            d = [p[i] - piv[i] for i in range(3)]
                            w = [loc[i] + apply(R, d)[i] for i in range(3)]
                            corners.append(w)
                pts = [(cx + 60 + c[2] * SCALE, int(H - 40 - c[1] * SCALE)) for c in corners]
                col = palette[bi % 4]
                edges = [(0, 1), (1, 3), (3, 2), (2, 0), (4, 5), (5, 7), (7, 6), (6, 4),
                         (0, 4), (1, 5), (2, 6), (3, 7)]
                for a, b in edges:
                    line(pts[a], pts[b], col)
                # 段号×10 作为刻度：段落越高越靠上
                line((cx + 6, int(H - 40 - 31 * SCALE)), (cx + 6, int(H - 40 - 20 * SCALE)),
                     (222, 222, 232))
        print(f"帧 {fi} t={t:4.2f}  骨头 {len(targets)} 根")

    out = f"art/bride/probe_{clip}_{prefix}.png"
    write_png(out, W, H, img)
    print(f"-> {out} ({W}x{H})  clip={clip} 骨骼前缀={prefix} 帧数={n} 间隔={step}s")


if __name__ == "__main__":
    main()
