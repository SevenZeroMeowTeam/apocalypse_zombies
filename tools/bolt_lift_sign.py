#!/usr/bin/env python3
"""把栓动枪「提柄」的转向改对：栓柄是往上抬的，不是往下压。

为什么（这是莫辛/AWM 拉栓穿模的根因）
--------------------------------------
栓柄在模型的 −X 侧：莫辛 handle 三块方块在 x −0.30…−0.68（knob 中心 x −0.62），
AWM 的球头在 x −1.26…−1.46（中心 −1.36）。
模型朝 −Z，第一人称相机在 +Z 侧朝 −Z 看，因此屏幕右 = 模型 +X、屏幕上 = 模型 +Y
（相机右向量 f×u = (0,0,-1)×(0,1,0) = (1,0,0)）。

绕 +Z 转 θ 把 (x, y) 送到 (x·cosθ − y·sinθ, x·sinθ + y·cosθ)：
对 −X 侧的栓柄（x < 0）来说，θ > 0 时 y' = x·sinθ < 0 —— **栓柄被压下去**。
压下去就插进机匣/枪托里（穿模），而 Java 给手的目标在柄的原位上方，于是「没握住」。

真机的栓柄是往上抬的，所以 rotation.z 必须取负。
（生成器里原来的注释写着「手柄在 +X，正向旋转抬柄」—— 前提就是错的，柄在 −X，见上。）

改什么
------
每把「动栓」的片段里，bolt 骨 rotation 通道的 z 分量取负（x/y 不动，都是 0）；
art/ 与 src/ 两份同步写；生成器里的字面量一并改掉，否则重新导出会把错误带回来。

用法
----
  python tools/bolt_lift_sign.py            预演：只列出将要改的键，不写文件
  python tools/bolt_lift_sign.py --apply    落地：备份 -> 写 art/ 与 src/
  python tools/bolt_lift_sign.py --check    门禁：断言现状已是「手柄上抬」，且生成器里没有正号
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "art"
RES = ROOT / "src/main/resources/assets/apocalypse_zombies"

# (枪名, art 动画文件, src 动画文件, 生成器, 生成器里 bolt rotation 的正则：第 1 组是 z 值)
GUNS = [
    (
        "mosin_nagant",
        ART / "mosin_nagant/mosin_nagant.animation.json",
        RES / "animations/mosin_nagant.animation.json",
        ROOT / "tools/mosin_nagant_bb_anim.js",
        re.compile(r"K\(\s*a\s*,\s*'bolt'\s*,\s*'rotation'\s*,\s*[0-9.]+\s*,\s*\[\s*0\s*,\s*0\s*,\s*(-?[0-9.]+)\s*\]"),
    ),
    (
        "awm",
        ART / "awm/awm.animation.json",
        RES / "animations/awm.animation.json",
        ROOT / "tools/awm_bb_anim.js",
        re.compile(r"K\(\s*[A-Za-z_$][\w$]*\s*,\s*'bolt'\s*,\s*'rotation'\s*,\s*[0-9.]+\s*,\s*\[\s*0\s*,\s*0\s*,\s*(-?[0-9.]+)\s*\]"),
    ),
]

#: 除了正片，还有一份要一起管的动画：cleanJar（分发包）的 AWM 动画取自
#: art/awm/awm.animation.handmade.bak.json（见 build.gradle 的 cleanJar），
#: 它同样把柄加压反了 —— 漏掉它，分发包里就还是老 bug。
EXTRA_FILES = [
    (ART / "awm/awm.animation.handmade.bak.json",),
]

#: 每个文件的留档后缀（正片是 .pre-lift，手工版也一样）。
BACKUP_SUFFIX_ALL = ".pre-lift.bak.json"

# art/ 的备份后缀。src/ 是副本、_anim_raw.json 是导出输入，都不留档。
BACKUP_SUFFIX = ".pre-lift.bak.json"


def vec_of(value):
    """通道里的一帧 -> [x, y, z]；单键静态缩写 {"vector":[...]} 或 {"post":[...]} 都算。"""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("vector", "post"):
            inner = value.get(key)
            if isinstance(inner, list):
                return inner
    return None


def bolt_rotation_channels(anim: dict):
    """产出 (片段名, bolt 骨的 rotation 通道)，兼容出货结构与 Blockbench 原始转储结构。"""
    if "animations" in anim:                                   # art/*/x.animation.json
        for clip, body in anim["animations"].items():
            ch = ((body or {}).get("bones") or {}).get("bolt", {}).get("rotation")
            if ch is not None:
                yield clip, ch
    elif "anims" in anim:                                      # art/*/_anim_raw.json
        for body in anim["anims"]:
            ch = ((body or {}).get("bones") or {}).get("bolt", {}).get("rotation")
            if ch is not None:
                yield body.get("name", "?"), ch


def keys_in_order(channel):
    if isinstance(channel, list):
        return [(0.0, channel)]
    out = []
    for k, v in channel.items():
        try:
            out.append((float(k), v))
        except (TypeError, ValueError):
            continue
    return sorted(out)


def nonzero_keys(anim: dict):
    """产出 (片段, 时刻, z) —— 所有非零的提柄键。"""
    for clip, channel in bolt_rotation_channels(anim):
        for t, value in keys_in_order(channel):
            v = vec_of(value)
            if v and len(v) >= 3 and abs(float(v[2])) > 1e-9:
                yield clip, t, float(v[2])


def flip(anim: dict) -> int:
    """把提柄键里的**正号**改成负号（目标状态：所有提柄键 ≤ 0）。

    幂等：已经是负号的键不动，所以连跑两次不会把修好的又翻回去。
    """
    n = 0
    for _clip, channel in bolt_rotation_channels(anim):
        if isinstance(channel, list):
            if len(channel) >= 3 and float(channel[2]) > 1e-9:
                channel[2] = -float(channel[2])
                n += 1
            continue
        for _, value in keys_in_order(channel):
            v = vec_of(value)
            if v and len(v) >= 3 and float(v[2]) > 1e-9:
                v[2] = -float(v[2])
                n += 1
    return n


def dump(path: Path, anim: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(anim, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generator_positive(path: Path, pattern: re.Pattern):
    """生成器里还是正号的提柄键（正号 = 会压柄，重新导出就把错误带回来）。"""
    if not path.exists():
        return []
    out = []
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for m in pattern.finditer(line):
            if float(m.group(1)) > 0:
                out.append((path.name, no, m.group(1)))
    return out


def premise(gun: str):
    """前提断言：栓柄必须在 −X 侧，否则「取负即上抬」这条推理不成立。返回 (描述, 是否成立)。"""
    geo = json.loads((ART / gun / f"{gun}.geo.json").read_text(encoding="utf-8"))
    bones = {b["name"]: b for b in geo["minecraft:geometry"][0]["bones"]}
    xs = []
    for c in bones.get("bolt", {}).get("cubes", []):
        xs += [c["origin"][0], c["origin"][0] + c["size"][0]]
    handle = [x for x in xs if abs(x) > 0.2]
    ok = bool(handle) and max(handle) < 0
    desc = (f"{gun}: 栓柄 x {min(handle):.2f}…{max(handle):.2f}（−X 侧，取负 = 上抬）" if handle
            else f"{gun}: bolt 骨没有偏离膛线的方块（x {min(xs):.2f}…{max(xs):.2f}）")
    return desc, ok


def main() -> int:
    ap = argparse.ArgumentParser(description="栓柄提柄方向矫正（莫辛 / AWM）")
    ap.add_argument("--apply", action="store_true", help="写文件（默认只预演）")
    ap.add_argument("--check", action="store_true", help="门禁模式：断言已是目标状态，不写文件")
    args = ap.parse_args()
    if args.apply and args.check:
        ap.error("--apply 与 --check 互斥")

    for gun, *_ in GUNS:
        desc, ok = premise(gun)
        if not ok:
            print(f"  ✗ {desc} —— 栓柄不在 −X 侧，取负就不再是「上抬」；"
                  f"先重新判定方向，别照抄本工具", file=sys.stderr)
            return 2
        print("  ·", desc)

    rows = []
    extra_paths = []
    for entry in EXTRA_FILES:
        # 手工版挂在 AWM 名下（枪名只用于报告），没有生成器/正则
        extra_paths.append(("awm", entry[0], None, None, None))
    for gun, art_path, src_path, _gen, _pat in GUNS + extra_paths:
        for path in (art_path, src_path, art_path.parent / "_anim_raw.json"):
            if path is None or not path.exists():
                continue
            anim = json.loads(path.read_text(encoding="utf-8"))
            rows += [(gun, path.name, clip, t, z) for clip, t, z in nonzero_keys(anim)]
            if args.apply and flip(anim):
                if path == art_path:
                    backup = art_path.with_name(art_path.name.replace(".json", BACKUP_SUFFIX_ALL))
                    if not backup.exists():
                        shutil.copy2(art_path, backup)
                dump(path, anim)

    bad_gen = []
    for _gun, _art, _src, gen, pat in GUNS:
        bad_gen += generator_positive(gen, pat)

    mode = "门禁" if args.check else ("落地" if args.apply else "预演")
    print(f"\n=== 栓柄提柄方向 · {mode} ===")
    if rows:
        print(f"  bolt rotation 非零键 {len(rows)} 个（art / src / 原始转储 各算一份）：")
        for gun, fname, clip, t, z in rows[:24]:
            print(f"    {gun:<13} {fname:<28} {clip:<18} @{t:<8.4f} z {z:>7.3f}"
                  f"{'  ← 仍是正号（柄被压下）' if z > 0 else ''}")
        if len(rows) > 24:
            print(f"    … 另 {len(rows) - 24} 个")
    else:
        print("  （没有找到非零的 bolt rotation 键）")

    if args.check:
        still = [r for r in rows if r[4] > 0]
        ok = True
        if still:
            ok = False
            print(f"  ✗ {len(still)} 个提柄键仍是正号（柄被往下压）："
                  + ", ".join(f"{r[1]}:{r[2]}@{r[3]:.4f}" for r in still[:6]))
        if bad_gen:
            ok = False
            print(f"  ✗ 生成器里还有正号 {len(bad_gen)} 处（重新导出会把错误带回来）："
                  + ", ".join(f"{f}:{no}={v}" for f, no, v in bad_gen[:6]))
        if ok:
            print("  ✓ 所有提柄键均为负（手柄上抬），生成器无正号")
        return 0 if ok else 1

    if args.apply:
        if bad_gen:
            print(f"  ✗ 生成器里仍有正号 {len(bad_gen)} 处，请一并改掉（否则重新导出会退回）")
            return 1
        print("  → 已写 art/ 与 src/（art/ 首次写盘留档 *" + BACKUP_SUFFIX + "）")
    else:
        print("  （预演，未写文件；加 --apply 落地）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
