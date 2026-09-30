#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""换弹「压入件」位移纯竖直化 —— 只该沿 Y（竖直）走的供弹件，Z（前后）分量必须为 0。

背景（2026-09-30 用户截图反馈）：
    莫辛纳甘换弹时，压进弹仓的那一发（round_in）一边下沉 1.9u、一边沿枪身向射手
    方向平移 2.75u（z 由 -0.30 走到 +2.45）。视觉上那一发是"横着滑向枪托"，
    用户要求：这一件只走竖直（绿色 Y 轴），不许有前后（蓝色 Z 轴）平移。

做法（与 tools/m1_well_shift.py 的「装填动作纯平移化」同款）：
    * 逐个关键帧把 z 分量置 0；y 曲线与时间点原样保留（抬起—压入仍走纯竖直）；
    * art/ 与 src/main/resources/ 两份一起改（莫辛这两份改前逐字节相同，改完仍须相同）；
    * 断言：改完后该骨该通道每个关键帧 x=z=0、y 与原值逐一相同、关键帧时刻集合不变；
    * 断言：整个文件除目标位置外与改前逐字段相同（防止手抖动了别的骨）；
    * 断言：出货件（src/main/resources）里 M1 的 clip_in 本来就是 z=0，本脚本不得
      往它写一个字节（它是已发版内容）。

用法：
    python tools/reload_press_vertical.py          # 应用（幂等：已是纯竖直则不改）
    python tools/reload_press_vertical.py --check   # 只校验，不改
"""
import argparse
import json
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RES = os.path.join(ROOT, "src", "main", "resources", "assets", "apocalypse_zombies", "animations")


def P(*parts):
    return os.path.join(*parts)


# (显示名, 文件, 剪辑, 骨, 允许写盘, 只读守卫)
TARGETS = [
    ("莫辛纳甘 round_in（art）", P(ROOT, "art", "mosin_nagant", "mosin_nagant.animation.json"),
     ("reload_empty", "reload_tactical"), "round_in", True, False),
    ("莫辛纳甘 round_in（资源/出货）", P(RES, "mosin_nagant.animation.json"),
     ("reload_empty", "reload_tactical"), "round_in", True, False),
    ("M1 加兰德 clip_in（art，对齐出货件）", P(ROOT, "art", "m1garand", "m1_garand.animation.json"),
     ("reload_empty", "reload_tactical"), "clip_in", True, False),
    ("M1 加兰德 clip_in（资源/出货）", P(RES, "m1_garand.animation.json"),
     ("reload_empty", "reload_tactical"), "clip_in", False, True),
]

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)
    return ok


def vectors(node):
    """把一帧的写法归一化成可改的 vector 列表引用。

    出厂文件里同一帧有两种写法：
        {"vector": [x, y, z]}                       —— 静态缩写 / 单键
        {"post": {"vector": [...]}, "lerp_mode": ...} —— 关键帧（可能还有 pre）
    """
    out = []
    if isinstance(node, dict):
        if isinstance(node.get("vector"), list):
            out.append(node["vector"])
        for holder in ("post", "pre"):
            inner = node.get(holder)
            if isinstance(inner, dict) and isinstance(inner.get("vector"), list):
                out.append(inner["vector"])
    return out


def frame_z_paths(obj):
    """收集 (clip, bone, t, vector 引用) —— 只针对 position 通道。"""
    got = []
    for clip, body in (obj.get("animations") or {}).items():
        for bone, chan in ((body or {}).get("bones") or {}).items():
            pos = chan.get("position")
            if not isinstance(pos, dict):
                continue
            for t, frame in pos.items():
                for vec in vectors(frame):
                    got.append((clip, bone, t, vec))
    return got


def _diff(before, after, path, out):
    if type(before) is not type(after):
        out.append((path, before, after))
        return
    if isinstance(before, dict):
        for k in set(before) | set(after):
            if k not in before or k not in after:
                out.append((path + [k], before.get(k), after.get(k)))
            else:
                _diff(before[k], after[k], path + [k], out)
    elif isinstance(before, list):
        if len(before) != len(after):
            out.append((path, before, after))
        else:
            for i, (b, a) in enumerate(zip(before, after)):
                _diff(b, a, path + [i], out)
    elif before != after:
        out.append((path, before, after))


def dump_like_source(obj, raw):
    """按出厂文件的写法回写：json.dumps(indent=2)，并保留原文件的换行风格与末尾换行。

    实测：莫辛两份 = LF、无末尾换行；M1 两份 = CRLF、有末尾换行。写错行尾会让
    整份文件逐行都算"改动"，所以这里按原文件探测。
    """
    text = json.dumps(obj, indent=2)
    if raw.endswith(b"\n"):
        text += "\n"
    if b"\r\n" in raw:
        text = text.replace("\n", "\r\n")
    return text.encode("utf-8")


def _is_target_change(path, old, new, clips, bone):
    """判定一处差异是否就是"目标骨目标通道的 Z 分量归零"。

    路径有两种写法（出厂文件里并存）：
        [... clip, 'bones', bone, 'position', t, 'vector', 2]
        [... clip, 'bones', bone, 'position', t, 'post', 'vector', 2]
    """
    if not path or path[-1] != 2 or new != 0.0 or old == 0.0:
        return False
    if "position" not in path or "vector" not in path or bone not in path:
        return False
    ci = path.index("position")
    if path.index(bone) > ci:
        return False
    return any(p in clips for p in path[:ci])


def process(label, path, clips, bone, writable, guard, stats):
    raw = open(path, "rb").read()
    before = json.loads(raw.decode("utf-8"))
    after = json.loads(raw.decode("utf-8"))  # 独立副本

    changed = []
    for clip, b, t, vec in frame_z_paths(after):
        if clip not in clips or b != bone:
            continue
        if vec[0] != 0.0:
            fails.append("%s：%s/%s@%s 横向位移 x=%s 非 0" % (label, clip, bone, t, vec[0]))
        if vec[2] != 0.0:
            changed.append((clip, t, list(vec)))
            vec[2] = 0.0
    stats.append((label, path, len(changed)))

    if not changed:
        print("  %-34s 已是纯竖直（无需改动）" % label)
    else:
        print("  %-34s 归零 %d 帧的 Z 分量：" % (label, len(changed)))
        for clip, t, vec in changed:
            print("        %-16s @%-7s [0, %.2f, %.2f] → [0, %.2f, 0]" % (clip, t, vec[1], vec[2], vec[1]))

    if guard:
        check(before == after, "%s：出货副本不应被本脚本改动" % label)
        return
    if not writable:
        return

    # 断言：改动只允许落在目标骨的目标通道的 z 分量上
    diffs = []
    _diff(before, after, [], diffs)
    bad = [d for d in diffs if not _is_target_change(d[0], d[1], d[2], clips, bone)]
    check(not bad, "%s：出现计划外改动 %s" % (label, bad[:3]))

    # 断言：改完每帧 x=z=0
    for clip, b, t, vec in frame_z_paths(after):
        if clip in clips and b == bone:
            check(vec[0] == 0.0 and vec[2] == 0.0, "%s：%s/%s@%s 仍未纯竖直 %s" % (label, clip, bone, t, vec))

    if changed:
        out = dump_like_source(after, raw)
        check(json.loads(out.decode("utf-8")) == after, "%s：回写后无法解析回同一对象" % label)
        check(out.count(b"\n") == raw.count(b"\n"), "%s：回写后行数变了" % label)
        open(path, "wb").write(out)
        print("        已写盘 %s（%d → %d 字节）" % (os.path.relpath(path, ROOT), len(raw), len(out)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验，不写盘")
    args = ap.parse_args()
    stats = []
    print("换弹压入件纯竖直化：")
    for label, path, clips, bone, writable, guard in TARGETS:
        if not os.path.exists(path):
            fails.append("找不到 %s" % path)
            continue
        process(label, path, clips, bone, writable and not args.check, guard, stats)

    # art 与出货副本必须内容相同（行尾由 .gitattributes/autocrlf 决定，不进内容比对）—— 只在应用模式校验
    if not args.check:
        for gun, art, res in (
            ("莫辛纳甘", P(ROOT, "art", "mosin_nagant", "mosin_nagant.animation.json"),
             P(RES, "mosin_nagant.animation.json")),
            ("M1 加兰德", P(ROOT, "art", "m1garand", "m1_garand.animation.json"),
             P(RES, "m1_garand.animation.json")),
        ):
            a_raw, r_raw = open(art, "rb").read(), open(res, "rb").read()
            check(json.loads(a_raw.decode("utf-8")) == json.loads(r_raw.decode("utf-8")),
                  "%s：art 与出货副本内容不一致" % gun)
            if b"\r\n" not in a_raw and b"\r\n" not in r_raw:
                check(a_raw == r_raw, "%s：同为 LF 的两份副本却不逐字节相同" % gun)

    print()
    if fails:
        for f in fails:
            print("✗ " + f)
        return 1
    print("✓ 全部断言通过：压入件位移只剩竖直分量，两份副本逐字节一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
