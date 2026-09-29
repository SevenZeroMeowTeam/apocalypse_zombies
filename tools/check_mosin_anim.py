#!/usr/bin/env python3
"""莫辛-纳甘动画结构自检：片段长度契约 / 骨名对齐 / 换弹时序 / 隐藏件钉位。

检查项（对应 美术规范.md 五·动画与八·动作时长契约）：
  1. 片段清单与长度：与生成器 tools/mosin_nagant_bb_anim.js 声明的一致（防手改漂移）
  2. 骨名：动画驱动的每一根骨都必须在 geo 里存在（GeckoLib 找不到骨会静默忽略整条通道）
  3. 时长契约：ceil(length x 20) = Java 的 *_TICKS（打印出来给 Java 用）
  4. 隐藏件钉位：不使用弹壳/待压弹的片段必须把 scale 钉成 0（否则进游戏就是"浮空的弹壳"）
  5. reload_empty：5 次压弹窗口，时间递增、互不重叠；弹仓里 5 发出现顺序 = 从底层到上层
  6. reload_tactical：3 次压弹窗口，且 mag_r1/r2 全程可见（仓里本来就有 2 发）
  7. bolt：提柄(rotation) → 后拉(position) → 抛壳(casing scale 0→1→0) → 推回 → 压柄 的先后关系
  8. 静默片段：scale 通道只允许 0 或 1（渐变之外不许出现 0.3 这种"缩小枪"的值）

退出码 0 = 全部对上。用法：python tools/check_mosin_anim.py [枪名，默认 mosin_nagant]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "art"
RES = ROOT / "src/main/resources/assets/apocalypse_zombies"

# 生成器里声明的片段契约（改生成器就要改这里，否则自检会拦下来）
EXPECT = {
    "static_idle":     {"length": 2.00, "loop": True,  "ticks": 40, "hidden": ["casing", "round_in"]},
    "draw":            {"length": 0.90, "loop": None,  "ticks": 18, "hidden": ["casing", "round_in"]},
    "shoot":           {"length": 0.60, "loop": None,  "ticks": 12, "hidden": ["casing", "round_in"]},
    "bolt":            {"length": 1.10, "loop": None,  "ticks": 22, "hidden": ["round_in"]},
    "reload_tactical": {"length": 3.60, "loop": None,  "ticks": 72, "hidden": ["casing"]},
    "reload_empty":    {"length": 4.40, "loop": None,  "ticks": 88, "hidden": ["casing"]},
    "inspect":         {"length": 2.60, "loop": None,  "ticks": 52, "hidden": ["casing", "round_in"]},
}

fails: list[str] = []
notes: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        fails.append(msg)


def entries(channel):
    """把通道解成 [(时刻, 值字典)]；单键静态缩写 {"vector":[...]} 视作 0 时刻一帧。"""
    if not isinstance(channel, dict):
        return []
    if "vector" in channel:
        return [(0.0, channel)]
    out = []
    for k, v in channel.items():
        try:
            out.append((float(k), v))
        except (TypeError, ValueError):
            continue
    return sorted(out, key=lambda kv: kv[0])


def key_times(channel) -> list[float]:
    return [t for t, _ in entries(channel)]


def vec_of(entry) -> list[float] | None:
    """keyframe 的 value -> [x, y, z]（{"vector":[...]} 或 {"post":{"vector":[...]}}）。"""
    if not isinstance(entry, dict):
        return None
    if "vector" in entry:
        return [float(c) for c in entry["vector"]]
    post = entry.get("post")
    if isinstance(post, dict) and "vector" in post:
        return [float(c) for c in post["vector"]]
    if isinstance(post, list):
        return [float(c) for c in post]
    return None


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "mosin_nagant"
    geo_path = ART / name / f"{name}.geo.json"
    anim_path = ART / name / f"{name}.animation.json"
    check(geo_path.exists() and anim_path.exists(), f"缺文件：{geo_path.name} / {anim_path.name}")
    if fails:
        for f in fails:
            print("  ✗", f)
        return 1

    geo = json.loads(geo_path.read_text(encoding="utf-8"))
    anim = json.loads(anim_path.read_text(encoding="utf-8"))
    bones = {b["name"] for b in geo["minecraft:geometry"][0]["bones"]}
    clips = anim.get("animations", {})

    notes.append(f"format_version={anim.get('format_version')} · geckolib_format_version={anim.get('geckolib_format_version')}")
    check("geckolib_format_version" in anim, "缺 geckolib_format_version（说明不是插件编出来的文件，GeckoLib 4 可能读不进去）")

    # 1. 片段清单
    missing = set(EXPECT) - set(clips)
    extra = set(clips) - set(EXPECT)
    check(not missing, f"缺片段：{sorted(missing)}")
    if extra:
        notes.append(f"额外片段（生成器没声明）：{sorted(extra)}")
    notes.append(f"片段 {len(clips)} 条：" + ", ".join(f"{k}({v['animation_length']}s)" for k, v in clips.items()))

    # 2. 骨名 + 契约 + 隐藏件
    tick_lines = []
    for clip_name, spec in EXPECT.items():
        clip = clips.get(clip_name)
        if not clip:
            continue
        length = clip.get("animation_length")
        loop = clip.get("loop")
        check(abs(length - spec["length"]) < 1e-6,
              f"{clip_name}: 长度 {length} ≠ 生成器声明的 {spec['length']}")
        real_ticks = math.ceil(round(length * 20, 6))
        check(real_ticks == spec["ticks"],
              f"{clip_name}: ceil({length}x20)={real_ticks} ≠ 声明的 {spec['ticks']} ticks")
        tick_lines.append(f"    {clip_name:<16} {length:>5}s -> {real_ticks:>3} ticks   loop={loop}")
        if spec["loop"] is True:
            check(loop is True, f"{clip_name}: 应为循环片段，实测 loop={loop}")
        else:
            check(loop in (None, False, "hold_on_last_frame") or loop is None,
                  f"{clip_name}: 实测 loop={loop}（once 片段应为 null/false）")

        driven = set(clip.get("bones", {}).keys())
        unknown = driven - bones
        check(not unknown, f"{clip_name}: 驱动了 geo 里不存在的骨 {sorted(unknown)}")

        for hide in spec["hidden"]:
            ch = clip["bones"].get(hide, {})
            sc = ch.get("scale")
            if sc is None:
                # 没有 scale 通道时，可能靠 constant 通道（BB 导出成裸 vector）表达
                entry = ch.get("scale_constant")
                check(False, f"{clip_name}: {hide} 没有规模通道，进游戏会以上一条片段的残留值显示（应为 0）")
                continue
            vals = [vec_of(v) for _, v in entries(sc)]
            for v in vals:
                if v is None:
                    continue
                check(all(abs(c) < 1e-6 for c in v),
                      f"{clip_name}: 隐藏件 {hide} 的 scale 出现非零值 {v}")

        # 8. scale 只许 0/1（静态缩放不许出现中间值）
        for bname, chans in clip.get("bones", {}).items():
            sc = chans.get("scale")
            if not isinstance(sc, dict):
                continue
            for t, entry in entries(sc):
                v = vec_of(entry)
                if not v:
                    continue
                for c in v:
                    check(abs(c) < 1e-6 or abs(c - 1) < 1e-6,
                          f"{clip_name}.{bname}.scale @{t} = {c}（只允许 0 或 1，缩放枪体是铁律禁止的）")

    # 4/5. reload_empty 的压弹窗口
    def insert_windows(clip_name: str) -> list[float]:
        """round_in 的 scale 由 0 变 1 的时刻 = 压弹开始。"""
        clip = clips.get(clip_name, {})
        sc = clip.get("bones", {}).get("round_in", {}).get("scale")
        if not isinstance(sc, dict):
            return []
        out = []
        prev = 0.0
        for t, val in entries(sc):                      # 只数 0 -> 1 的上升沿（保持帧不算）
            v = vec_of(val)
            cur = 1.0 if (v and all(abs(c - 1) < 1e-6 for c in v)) else 0.0
            if cur > 0.5 and prev < 0.5:
                out.append(t)
            prev = cur
        return out

    empty_windows = insert_windows("reload_empty")
    check(len(empty_windows) == 5, f"reload_empty 的压弹窗口 {len(empty_windows)} 个，应为 5（5 发弹仓）")
    if len(empty_windows) == 5:
        gaps = [empty_windows[i + 1] - empty_windows[i] for i in range(4)]
        check(all(g > 0.3 for g in gaps), f"reload_empty 压弹节奏太密：间隔 {gaps}")
        notes.append("reload_empty 压弹时刻：" + ", ".join(f"{t:.2f}s" for t in empty_windows))
    tact_windows = insert_windows("reload_tactical")
    check(len(tact_windows) == 3, f"reload_tactical 的压弹窗口 {len(tact_windows)} 个，应为 3（补满 5 发）")

    # 弹仓 5 发出现顺序：第 1 发应落到最底层（mag_r5）
    clip = clips.get("reload_empty", {})
    appear: list[tuple[float, str]] = []
    for bname in [f"mag_r{i}" for i in range(1, 6)]:
        sc = clip.get("bones", {}).get(bname, {}).get("scale")
        if not isinstance(sc, dict):
            fails.append(f"reload_empty: {bname} 没有 scale 通道")
            continue
        for t, val in entries(sc):
            v = vec_of(val)
            if v and all(abs(c - 1) < 1e-6 for c in v) and t > 0:
                appear.append((t, bname))
                break
    appear.sort()
    order = [b for _, b in appear]
    check(order == ["mag_r5", "mag_r4", "mag_r3", "mag_r2", "mag_r1"],
          f"reload_empty 的落弹顺序 {order}，应从底层往上（mag_r5 → mag_r1）")
    if order:
        notes.append("落弹顺序：" + " → ".join(order))

    # reload_tactical：仓里已有 2 发必须全程可见
    tact = clips.get("reload_tactical", {})
    for bname in ("mag_r1", "mag_r2"):
        sc = tact.get("bones", {}).get(bname, {}).get("scale")
        check(isinstance(sc, dict), f"reload_tactical: {bname} 没有 scale 通道（仓里的 2 发应全程可见）")
        if isinstance(sc, dict):
            vals = [vec_of(v) for _, v in entries(sc)]
            for v in vals:
                if v:
                    check(all(abs(c - 1) < 1e-6 for c in v),
                          f"reload_tactical: {bname} 被隐藏/缩放了（应为 1）")

    # 7. bolt 的先后关系
    bclip = clips.get("bolt", {})
    bbolt = bclip.get("bones", {}).get("bolt", {})
    rot, pos = bbolt.get("rotation"), bbolt.get("position")
    cas = bclip.get("bones", {}).get("casing", {}).get("scale")
    check(isinstance(rot, dict) and isinstance(pos, dict) and isinstance(cas, dict), "bolt: 缺 bolt.rotation/position 或 casing.scale")
    if isinstance(rot, dict) and isinstance(pos, dict) and isinstance(cas, dict):
        def reach_time(chan, axis, threshold):
            """第一次达到阈值（>=）的时刻。"""
            for t, val in entries(chan):
                v = vec_of(val)
                if v and v[axis] >= threshold - 1e-6:
                    return t
            return None

        t_open = reach_time(rot, 2, 79.0)               # 提柄到位（绕 +Z 80 度）
        t_pull = reach_time(pos, 2, 1.5)                # 后拉到到位
        t_home = max(key_times(pos)) if key_times(pos) else None
        t_cas = [t for t, val in entries(cas) if (vec_of(val) or [0, 0, 0])[0] > 0.5]
        check(t_open is not None and t_pull is not None and t_open <= t_pull + 1e-6,
              f"bolt: 提柄到位 {t_open} 应不晚于后拉到位 {t_pull}")
        check(t_pull is not None and t_home is not None and t_home > t_pull,
              f"bolt: 后拉到位 {t_pull} 之后必须有推回（末键 {t_home}）")
        if t_cas:
            check(t_pull is not None and t_cas[0] >= t_pull - 1e-6,
                  f"bolt: 抛壳({t_cas[0]}) 应在后拉到位({t_pull})之后")
            check(t_cas[-1] <= bclip.get("animation_length", 1.1) + 1e-6,
                  f"bolt: 抛壳结束 {t_cas[-1]} 超出片段长度")
            notes.append(f"bolt 时序：提柄到位 {t_open:.3f}s → 后拉到位 {t_pull:.3f}s → "
                         f"抛壳 {t_cas[0]:.3f}~{t_cas[-1]:.3f}s → 推回 {t_home:.3f}s")

    print(f"=== {name} 动画自检 ===")
    for n in notes:
        print(" ", n)
    print("  时长契约（Java 的 *_TICKS 直接抄这几行）：")
    for line in tick_lines:
        print(line)
    if fails:
        print(f"\n{len(fails)} 条不通过：")
        for f in fails[:20]:
            print("  ✗", f)
        return 1
    print("\n全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())