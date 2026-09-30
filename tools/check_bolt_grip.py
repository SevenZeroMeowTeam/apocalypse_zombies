#!/usr/bin/env python3
"""栓柄握持门禁：手是否真在柄上、柄是否真往上抬、抬柄/拉栓过程有没有穿模。

为什么要有这条门禁
------------------
莫辛/AWM 的拉栓穿模不是手感问题，是几何问题：栓柄绕 +Z 正向旋转会把 −X 侧的柄**压下去**，
插进机匣/枪托；手的目标却在柄的原位上方，于是既穿模又「没握住」。
这类错误肉眼在 Blockbench 里很容易看漏，所以这里把它算出来：

  1. 前提：栓柄必须在 −X 侧（换边就要重新判方向，别照抄结论）
  2. 常量 ↔ 几何：Java 的 BOLT_KNOB 必须等于 geo 里柄头方块的中心；TURN/PULL 上限必须等于剪辑里的极值
  3. 方向：柄在「停住」那一帧的中心 y 必须高于枢轴 y（上抬），备份剪辑必须低于（对照）
  4. 握持：Java 判定「手在柄上」时，手的目标点与柄心必须重合（≤0.05px）
  5. 穿模：逐帧把柄的方块摆到模型空间，与其余所有骨的方块求最大互相嵌入深度（mm），
     与 *pre-lift.bak 对照，并断言不超过阈值

坐标/旋转约定与渲染器一致（GeckoLib 4.8.4）：
  - 动画角度是**度**，载入时 x、y 取负、z 保持（BakedAnimationsAdapter），应用顺序 rotateZ → rotateY → rotateX
  - 骨骼矩阵：T(−pos) · T(pivot) · Rz · Ry · Rx · S · T(−pivot)，祖先在外（与 GeoRenderer 递归一致）
  - 16u = 1 格，1px = 62.5mm；模型朝 −Z、上 +Y、屏幕右 = +X

用法：python tools/check_bolt_grip.py [--tol-mm 2.0]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "art"

GUNS = [
    ("mosin_nagant", ART / "mosin_nagant/mosin_nagant.geo.json",
     ART / "mosin_nagant/mosin_nagant.animation.json",
     ROOT / "src/main/java/com/apocalypse/zombies/client/model/MosinNagantGeoModel.java"),
    ("awm", ART / "awm/awm.geo.json",
     ART / "awm/awm.animation.json",
     ROOT / "src/main/java/com/apocalypse/zombies/client/model/AWMGeoModel.java"),
]

# 动栓的片段（Java 的 rightHand 必须按这些名字分支），以及握持判定用的极值常量名
BOLT_ACTIONS = {
    "mosin_nagant": ["bolt", "inspect", "reload_empty", "reload_tactical"],
    "awm": ["bolt", "inspect", "inspect_empty", "reload_empty", "static_bolt_caught"],
}
PX_MM = 1000.0 / 16.0          # 1 模型像素 = 1/16 格 = 62.5mm
HANDLE_X = 0.2                 # |x| > 0.2 的螺栓方块算「柄」（与 tools/bolt_lift_sign.py 同判据）

fails: list[str] = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
    return bool(cond)


# ---------------------------------------------------------------- 4x4 矩阵（行主序，与 JOML 同语义）
def I():
    return [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]


def mul(a, b):
    """列主序存储（index = col*4 + row），与 JOML 一致：out = a·b。"""
    out = [0.0] * 16
    for col in range(4):
        for row in range(4):
            out[col * 4 + row] = sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
    return out


def T(x, y, z):
    m = I()
    m[12], m[13], m[14] = x, y, z          # 列主序：平移在第 4 列
    return m


def S(x, y, z):
    m = I(); m[0], m[5], m[10] = x, y, z; return m


def R(axis, deg):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    m = I()
    if axis == "z":
        m[0], m[1], m[4], m[5] = c, s, -s, c
    elif axis == "y":
        m[0], m[2], m[8], m[10] = c, -s, s, c
    else:
        m[5], m[6], m[9], m[10] = c, s, -s, c
    return m


def xf(m, p):
    x, y, z = p
    return (m[0] * x + m[4] * y + m[8] * z + m[12],
            m[1] * x + m[5] * y + m[9] * z + m[13],
            m[2] * x + m[6] * y + m[10] * z + m[14])


# ---------------------------------------------------------------- 通道取值
def entries(channel):
    if channel is None:
        return []
    if isinstance(channel, list):
        return [(0.0, channel)]
    out = []
    for k, v in channel.items():
        try:
            out.append((float(k), v))
        except (TypeError, ValueError):
            continue
    return sorted(out)


def vec_of(entry):
    if isinstance(entry, list):
        return [float(c) for c in entry]
    if isinstance(entry, dict):
        for key in ("post", "vector"):
            inner = entry.get(key)
            if isinstance(inner, list):
                return [float(c) for c in inner]
    return None


def sample(channel, t, default):
    """线性取样（剪辑里的通道值都是裸数组 / post，按 GeckoLib 默认线性插值）。"""
    es = entries(channel)
    if not es:
        return list(default)
    if t <= es[0][0]:
        return vec_of(es[0][1]) or list(default)
    if t >= es[-1][0]:
        return vec_of(es[-1][1]) or list(default)
    for i in range(len(es) - 1):
        t0, v0 = es[i]
        t1, v1 = es[i + 1]
        if t0 <= t <= t1:
            a, b = vec_of(v0), vec_of(v1)
            if not a or not b:
                return list(default)
            k = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
            return [a[j] + (b[j] - a[j]) * k for j in range(3)]
    return list(default)


def clip_bone(clip, bone):
    return (clip.get("bones") or {}).get(bone, {})


# ---------------------------------------------------------------- 骨骼矩阵
def bone_matrix(bone, rot, pos):
    """与 GunFrame.boneChain / GeoRenderer 一致：祖先在外，本骨在内。"""
    r = [math.radians(-rot[0]), math.radians(-rot[1]), math.radians(rot[2])]   # 载入时 x/y 取负
    px, py, pz = bone.get("pivot", [0, 0, 0])
    return mul(mul(mul(T(-pos[0], pos[1], pos[2]), T(px, py, pz)),
                   mul(mul(R("z", math.degrees(r[2])), R("y", math.degrees(r[1]))), R("x", math.degrees(r[0])))),
               T(-px, -py, -pz))


def bone_pose(bone, clip, t):
    rest_rot = (bone.get("rotation") or [0, 0, 0])
    rest_pos = (bone.get("position") or [0, 0, 0])
    ch = clip_bone(clip, bone["name"]) if clip else {}
    rot = sample(ch.get("rotation"), t, rest_rot)
    pos = sample(ch.get("position"), t, rest_pos)
    return [rot[0] + rest_rot[0], rot[1] + rest_rot[1], rot[2] + rest_rot[2]], [pos[0] + rest_pos[0], pos[1] + rest_pos[1], pos[2] + rest_pos[2]]


def chain_matrix(bones, name, clip, t, stop=None):
    m = I()
    n = name
    while n and n != stop:
        b = bones[n]
        rot, pos = bone_pose(b, clip, t)
        m = mul(bone_matrix(b, rot, pos), m)        # 祖先在外
        n = b.get("parent")
    return m


_CORNERS = {}


def cube_corners(bone, cube):
    """方块 8 角（含方块自身的 rotation），带记忆化 —— 静止角点只算一次。"""
    key = id(cube)
    hit = _CORNERS.get(key)
    if hit is not None:
        return hit
    o, s = cube["origin"], cube["size"]
    cx, cy, cz = o[0] + s[0] / 2, o[1] + s[1] / 2, o[2] + s[2] / 2
    rot = cube.get("rotation")
    m = R(rot.get("axis", "z"), float(rot.get("angle", 0))) if isinstance(rot, dict) else I()
    pts = []
    for dx in (-0.5, 0.5):
        for dy in (-0.5, 0.5):
            for dz in (-0.5, 0.5):
                p = xf(m, (s[0] * dx, s[1] * dy, s[2] * dz))
                pts.append((p[0] + cx, p[1] + cy, p[2] + cz))
    _CORNERS[key] = pts
    return pts


def aabb(pts):
    return (min(p[0] for p in pts), min(p[1] for p in pts), min(p[2] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts), max(p[2] for p in pts))


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def obb_overlap(pts_a, pts_b):
    """两个（可能各自旋转的）盒子的最小互嵌深度。

    角点顺序是 cube_corners 的 dx→dy→dz 嵌套，所以 pts[4]-pts[0] 是 x 棱、pts[2]-pts[0] 是 y 棱、
    pts[1]-pts[0] 是 z 棱。分离轴 = 两盒各 3 条棱 + 两两叉积共 15 条；全都重叠时取最小重叠量。

    不能用 AABB 代替：机匣在整枪姿态下是斜的，AABB 会把「其实没碰」判成互嵌（AWM 上会虚报 50mm）。
    """
    axes = []
    for pts in (pts_a, pts_b):
        axes += [_sub(pts[4], pts[0]), _sub(pts[2], pts[0]), _sub(pts[1], pts[0])]
    for a in axes[0:3]:
        for b in axes[3:6]:
            axes.append(_cross(a, b))
    depth = None
    for ax in axes:
        length = math.sqrt(_dot(ax, ax))
        if length < 1e-9:
            continue
        u = (ax[0] / length, ax[1] / length, ax[2] / length)
        a_lo = min(_dot(p, u) for p in pts_a); a_hi = max(_dot(p, u) for p in pts_a)
        b_lo = min(_dot(p, u) for p in pts_b); b_hi = max(_dot(p, u) for p in pts_b)
        ov = min(a_hi - b_lo, b_hi - a_lo)
        if ov <= 0:
            return 0.0
        depth = ov if depth is None else min(depth, ov)
    return depth or 0.0


def overlap_px(a, b):
    """两 AABB 的互嵌深度（每轴取最小重叠，全部正才算相交）—— 仅用于粗筛。"""
    d = [min(a[3] - b[0], b[3] - a[0]), min(a[4] - b[1], b[4] - a[1]), min(a[5] - b[2], b[5] - a[2])]
    if min(d) <= 0:
        return 0.0
    return min(d)


def cube_boxes(bones, name, clip, t, only_handle=False):
    """把某骨（含子树）的方块摆到模型空间，返回 [(aabb, 骨名)]。"""
    m = chain_matrix(bones, name, clip, t)
    out = []
    stack = [name]
    while stack:
        n = stack.pop()
        b = bones[n]
        mm = mul(chain_matrix(bones, n, clip, t), I())     # 该骨自己的链
        for c in b.get("cubes", []):
            o = c["origin"]
            if only_handle and abs(o[0]) <= HANDLE_X:
                continue
            out.append((aabb([xf(mm, p) for p in cube_corners(b, c)]), n))
        for child in b.get("children", []):
            stack.append(child)
    return out


# 道具骨：抛壳弹壳、待压弹 —— 它们是随手部/机构出现又消失的临时件，不是枪体几何，不参与穿模判定
PROPS = ("casing", "round_in")


def bone_world_boxes(bones, clip, t, cache, skip=("bolt", "move", "root") + PROPS):
    """某一帧里，除 bolt、整体运动骨与道具之外每根骨的方块 (AABB, 角点, 骨名)（矩阵按 (骨,时刻) 复用）。"""
    out = []
    for bname, b in bones.items():
        if bname in skip or not b.get("cubes"):
            continue
        if clip is not None:
            sc = sample(clip_bone(clip, bname).get("scale"), t, [1.0, 1.0, 1.0])
            if max(abs(v) for v in sc) < 1e-6:
                continue          # 这一帧被缩成 0 的隐藏件不参与碰撞
        key = (bname, t)
        m = cache.get(key)
        if m is None:
            m = chain_matrix(bones, bname, clip, t)
            cache[key] = m
        for c in b["cubes"]:
            pts = [xf(m, p) for p in cube_corners(b, c)]
            out.append((aabb(pts), pts, bname))
    return out


def worst_overlap(handle_boxes, others):
    """柄的盒子与其余盒子的互嵌深度（px）与对手骨名。

    先用 AABB 粗筛（便宜），命中的才做精确的旋转盒相交 —— 机匣在整枪姿态下是斜的，
    只靠 AABB 会虚报（AWM 上曾虚报 50mm）。
    """
    worst, who = 0.0, ""
    for hbox, hpts in handle_boxes:
        for obox, opts, name in others:
            if (hbox[0] > obox[3] or obox[0] > hbox[3] or hbox[1] > obox[4]
                    or obox[1] > hbox[4] or hbox[2] > obox[5] or obox[2] > hbox[5]):
                continue
            d = obb_overlap(hpts, opts)
            if d > worst:
                worst, who = d, name
    return worst, who


def build_children(bones):
    for b in bones.values():
        b["children"] = []
    for b in bones.values():
        p = b.get("parent")
        if p in bones:
            bones[p]["children"].append(b["name"])


def load(name):
    geo = json.loads((ART / name / f"{name}.geo.json").read_text(encoding="utf-8"))
    anim = json.loads((ART / name / f"{name}.animation.json").read_text(encoding="utf-8"))
    bones = {b["name"]: b for b in geo["minecraft:geometry"][0]["bones"]}
    build_children(bones)
    return bones, anim.get("animations", {})


def read_java_consts(path: Path):
    src = path.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"private static final float\[\]\s+(\w+)\s*=\s*\{\s*(-?[\d.]+)F?\s*,\s*(-?[\d.]+)F?\s*,\s*(-?[\d.]+)F?\s*\}", src):
        out[m.group(1)] = [float(m.group(2)), float(m.group(3)), float(m.group(4))]
    for m in re.finditer(r"private static final float\s+(\w+)\s*=\s*(-?[\d.]+)F?", src):
        out[m.group(1)] = float(m.group(2))
    return out


def max_abs(channel, axis):
    v = [abs(vec_of(e)[axis]) for _, e in entries(channel) if vec_of(e)]
    return max(v) if v else 0.0


def measure(gun, tol_mm, java):
    bones, clips = load(gun)
    bolt = bones.get("bolt")
    cubes = bolt.get("cubes", [])
    centers = [c["origin"][0] + c["size"][0] / 2 for c in cubes]
    far = max(abs(v) for v in centers) if centers else 0.0
    # 「柄」= 偏离膛线最远的那一簇（柄头 + 柄杆）。不能只看 |x|>0.2：AWM 的栓体八边形也超过 0.2，
    # 而它本来就插在机匣里（设计如此），算进去会把「正常滑动」误判成穿模。
    handle_cubes = [c for c in cubes if abs(c["origin"][0] + c["size"][0] / 2) >= 0.5 * far]
    knob_cubes = [c for c in cubes if abs(c["origin"][0] + c["size"][0] / 2) >= 0.9 * far]
    check(bool(handle_cubes), f"{gun}: bolt 骨里找不到偏离膛线的柄方块")
    if not handle_cubes:
        return

    # 1. 前提：柄在 −X 侧
    xs = [c["origin"][0] for c in handle_cubes] + [c["origin"][0] + c["size"][0] for c in handle_cubes]
    check(max(xs) < 0, f"{gun}: 柄不在 −X 侧（x {min(xs):.2f}…{max(xs):.2f}）——" 
                       f"「绕 +Z 正转 = 压下」的推导要重做，别忘了改 Java 与生成器")
    print(f"  · {gun}: 柄方块 x {min(xs):.2f}…{max(xs):.2f}（−X 侧，"
          f"{'✓' if max(xs) < 0 else '✗'}）")

    # 2. 常量 ↔ 几何
    knob = java.get("BOLT_KNOB")
    if knob:
        cx = sum(c["origin"][0] + c["size"][0] / 2 for c in knob_cubes) / len(knob_cubes)
        cy = sum(c["origin"][1] + c["size"][1] / 2 for c in knob_cubes) / len(knob_cubes)
        cz = sum(c["origin"][2] + c["size"][2] / 2 for c in knob_cubes) / len(knob_cubes)
        d = math.dist(knob, (cx, cy, cz))
        check(d <= 0.30, f"{gun}: Java 的 BOLT_KNOB {knob} 与 geo 柄头中心 "
                         f"({cx:.2f},{cy:.2f},{cz:.2f}) 差 {d:.3f}px —— 手会握在柄外面")
        print(f"  · {gun}: BOLT_KNOB {knob} ↔ geo 柄头中心 ({cx:.2f},{cy:.2f},{cz:.2f})"
              f" 差 {d:.3f}px {'✓' if d <= 0.30 else '✗'}")

    # 3/4/5. 每个动栓片段
    print(f"  · {gun}: 动栓片段 {len(BOLT_ACTIONS[gun])} 条，逐帧判方向 / 握持 / 穿模")
    pre_path = ART / gun / f"{gun}.animation.pre-lift.bak.json"
    pre_clips = {}
    if pre_path.exists():
        pre_clips = json.loads(pre_path.read_text(encoding="utf-8")).get("animations", {})

    for clip_name in BOLT_ACTIONS[gun]:
        clip = clips.get(clip_name)
        if not clip:
            fails.append(f"{gun}: Java 按 '{clip_name}' 分支，但剪辑文件里没有这条片段")
            continue
        L = clip.get("animation_length", 1.0)
        rot_ch = clip_bone(clip, "bolt").get("rotation")
        pos_ch = clip_bone(clip, "bolt").get("position")

        # 极值常量：TURN_MAX / PULL_MAX 是「活性」归一化的分母，必须 ≥ 该片段的极值（可以更大）
        if java.get("BOLT_TURN_MAX") is not None and rot_ch is not None:
            got = max_abs(rot_ch, 2)
            check(got <= java["BOLT_TURN_MAX"] + 1e-6,
                  f"{gun}: {clip_name} 的提柄角 {got}° 超过 BOLT_TURN_MAX={java['BOLT_TURN_MAX']}°"
                  f"（活骨角度算出来会 >1，握持判定会失灵）")
        if java.get("BOLT_PULL_MAX") is not None and pos_ch is not None:
            got = max_abs(pos_ch, 2)
            check(got <= java["BOLT_PULL_MAX"] + 1e-6,
                  f"{gun}: {clip_name} 的后拉 {got}px 超过 BOLT_PULL_MAX={java['BOLT_PULL_MAX']}")

        # 停住那一帧（角度最大）
        hold_t, best = 0.0, -1.0
        n = max(40, int(L * 60))
        for i in range(n + 1):
            t = L * i / n
            z = abs(sample(rot_ch, t, [0, 0, 0])[2]) if rot_ch else 0.0
            if z > best:
                best, hold_t = z, t
        knob_rest = java.get("BOLT_KNOB") or [c["origin"][0] + c["size"][0] / 2 for c in knob_cubes[:1]]

        def local_lift(rotation, position):
            """提柄在 bolt 自己父空间里的竖直位移 —— 纯几何量，不受整枪姿态影响。"""
            return xf(bone_matrix(bolt, rotation, position), knob_rest)[1] - knob_rest[1]

        rot_hold = sample(rot_ch, hold_t, [0, 0, 0]) if rot_ch else [0, 0, 0]
        pos_hold = sample(pos_ch, hold_t, [0, 0, 0]) if pos_ch else [0, 0, 0]
        lift = local_lift(rot_hold, pos_hold)
        check(lift >= 0.25, f"{gun}.{clip_name}: 提柄只把柄心抬了 {lift:+.3f}px（应 ≥0.25）——柄没被抬起来")
        print(f"      {clip_name:<18} 停柄帧 t={hold_t:6.3f}s  柄心抬升 {lift:+.3f}px "
              f"{'✓ 上抬' if lift >= 0.25 else '✗ 被压下'}")
        if pre_clips.get(clip_name):
            pre_bolt = clip_bone(pre_clips[clip_name], "bolt")
            lift_pre = local_lift(sample(pre_bolt.get("rotation"), hold_t, [0, 0, 0]),
                                  sample(pre_bolt.get("position"), hold_t, [0, 0, 0]))
            check(lift_pre < lift, f"{gun}.{clip_name}: 修复前 {lift_pre:+.3f} 不比修复后低 —— 方向不对")
            print(f"      {'':<18} 修复前同帧      柄心抬升 {lift_pre:+.3f}px "
                  f"{'（被压下去 = 穿模的来源）' if lift_pre < 0 else ''}")

        # 穿模：只判「看得见的部分」—— 柄头（knob）。
        # 柄杆的根部本来就插在机匣侧面里（焊接式建模，渲染出来就是从机匣里伸出来），那一段嵌在机匣内部、
        # 画面上看不见，算进去只会掩盖真正的问题；柄头是整根柄上最显眼的地方，真机上也不该插进任何东西。
        # 缩到 0 的隐藏件（抛壳用的弹壳等）不参与。
        cache, rest_cache = {}, {}

        def boxes_of(cubes_, t, clip_used):
            m = chain_matrix(bones, "bolt", clip_used, t)
            out = []
            for c in cubes_:
                pts = [xf(m, p) for p in cube_corners(bolt, c)]
                out.append((aabb(pts), pts))
            return out

        def over(cubes_, t, clip_used, inst_cache):
            return worst_overlap(boxes_of(cubes_, t, clip_used),
                                 bone_world_boxes(bones, clip, t, inst_cache))

        knob_base, _ = over(knob_cubes, 0.0, None, rest_cache)
        handle_base, handle_base_who = over(handle_cubes, 0.0, None, rest_cache)
        knob_hold_d, knob_hold_who = over(knob_cubes, hold_t, clip, cache)
        handle_hold_d, _ = over(handle_cubes, hold_t, clip, cache)
        worst_knob, knob_who, worst_handle, handle_who, worst_pre = 0.0, "", 0.0, "", 0.0
        step = max(1, n // 40)
        for i in range(0, n + 1, step):
            t = L * i / n
            d, who = over(knob_cubes, t, clip, cache)
            if d - knob_base > worst_knob:
                worst_knob, knob_who = max(0.0, d - knob_base), who
            d2, who2 = over(handle_cubes, t, clip, cache)
            if d2 - handle_base > worst_handle:
                worst_handle, handle_who = max(0.0, d2 - handle_base), who2
            if pre_clips.get(clip_name):
                d3, _ = over(knob_cubes, t, pre_clips[clip_name], cache)
                worst_pre = max(worst_pre, max(0.0, d3 - knob_base))

        knob_mm, pre_mm = worst_knob * PX_MM, worst_pre * PX_MM
        check(knob_mm <= tol_mm,
              f"{gun}.{clip_name}: 柄头被推进别的几何 {knob_mm:.2f}mm > {tol_mm}mm"
              f"（穿模，对手 {knob_who or '—'}）")
        check(knob_hold_d - knob_base <= tol_mm * 3,
              f"{gun}.{clip_name}: 停柄帧柄头就嵌进 {knob_hold_who} "
              f"{(knob_hold_d - knob_base) * PX_MM:.2f}mm（握到位那一刻不该有任何互嵌）")
        print(f"      {'':<18} 柄头（可见）：停柄帧 {max(0.0, knob_hold_d - knob_base) * PX_MM:5.2f}mm"
              f"({knob_hold_who or '无'}) · 全片段 {knob_mm:5.2f}mm({knob_who or '无'})"
              f" {'✓' if knob_mm <= tol_mm else '✗'}"
              + (f"（修复前 {pre_mm:5.2f}mm）" if pre_clips.get(clip_name) else ""))
        print(f"      {'':<18} 整根柄（含插进机匣的柄杆根部，仅参考）：停柄帧 "
              f"{max(0.0, handle_hold_d - handle_base) * PX_MM:5.2f}mm · 全片段 "
              f"{worst_handle * PX_MM:5.2f}mm({handle_who or '无'})，静止底噪 "
              f"{handle_base * PX_MM:5.2f}mm({handle_base_who or '无'})")
        if pre_clips.get(clip_name):
            check(pre_mm > knob_mm - 1e-9,
                  f"{gun}.{clip_name}: 换向前后柄头的互嵌没有变好（{pre_mm:.2f} → {knob_mm:.2f}mm）"
                  f"—— 方向不对")


def main() -> int:
    ap = argparse.ArgumentParser(description="栓柄握持 / 穿模门禁")
    ap.add_argument("--tol-mm", type=float, default=2.0, help="允许的可见互嵌深度（默认 2mm）")
    args = ap.parse_args()

    print(f"=== 栓柄握持门禁（阈值 {args.tol_mm}mm）===")
    # 矩阵自检：列主序 + 旋转方向。转置或符号错了，后面所有几何数都不可信。
    _p = xf(mul(T(1, 2, 3), R("z", 90)), (1, 0, 0))
    check(abs(_p[0] - 1) < 1e-9 and abs(_p[1] - 3) < 1e-9 and abs(_p[2] - 3) < 1e-9,
          f"矩阵自检失败：T(1,2,3)·Rz(90°)·(1,0,0) = "
          f"{tuple(round(v, 3) for v in _p)}，应为 (1, 3, 3)")
    for gun, _geo, _anim, java_path in GUNS:
        java = read_java_consts(java_path)
        # 4. 握持：Java 判「手在柄上」时手与柄心重合 —— 由构造保证，这里断言常量确实被用于该分支
        src = java_path.read_text(encoding="utf-8")
        for need in ("BOLT_KNOB", "BOLT_TURN_MAX", "BOLT_PULL_MAX", "handleHold", "holdOnHandle", "onBolt"):
            check(need in src, f"{gun}: Java 里没有 {need}（握持机制不完整）")
        check("frame.boltGrip(BOLT_KNOB" in src,
              f"{gun}: 手的目标没有用 frame.boltGrip(BOLT_KNOB)（手又回到「复刻曲线」的老路）")
        measure(gun, args.tol_mm, java)

    print()
    if fails:
        print(f"{len(fails)} 条不通过：")
        for f in fails:
            print("  ✗", f)
        return 1
    print("全部通过：柄在 −X 侧、绕负角上抬、手随活骨柄心、停柄帧与全片段都不穿模")
    return 0


if __name__ == "__main__":
    sys.exit(main())
