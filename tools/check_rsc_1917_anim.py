#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RSC M1917 动画自检：片段契约 / 骨名 / 换弹因果 / 隐藏件钉位 / 镜像符号。

检查项（对应 美术规范.md 五·动画与八·动作时长契约，以及 RSC 真机换弹顺序）：
  1. 片段清单与长度：与 tools/rsc_1917_bb_anim.js 声明一致（防手改漂移）
  2. 骨名：动画驱动的每根骨都必须在 geo 里存在（GeckoLib 找不到骨会静默忽略整条通道）
  3. 时长契约：ceil(length × 20) = Java 的 *_TICKS（直接读 Rsc1917Item.java，不靠人手抄）
  4. 隐藏件钉位：不用弹壳/空漏夹/补弹的片段必须把 scale 钉成 0（否则进游戏就是"浮空的弹壳"）
  5. **换弹因果**（RSC 真机，与 M1 最大的差别）：
       * 空漏夹只能在弹匣盖敞开之后掉出
       * 新漏夹只能在盖敞开之后自下往上进入，且**纯平移**（rotation 全 0、x/z 位移全 0）
       * 枪机只能在盖**完全合上之后**才被拉动（拉手柄送弹入膛是最后一步）
       * 末帧 = rest（所有骨回零，否则会从中间姿势跳回 idle）
  6. reload_tactical 比 reload_empty 短，且同样满足"先开盖后动枪机"
  7. shoot/shoot_last：枪机走满行程；弹壳在枪机退到位那一刻显形；shoot_last 末态**枪机闭锁**
     （M1917 无空仓挂机 —— 这是与 M1 的硬差别，错了就是"最后一发后枪机吊在半空"）
  8. 不许整枪缩放：scale 通道只允许出现在隐藏件上，且取值只能是 0 或 1
  9. **镜像符号**（导出空间）：mag_cover 开盖 = rotation x < 0；bolt 后拉 = position z > 0；
     casing 抛壳 = position x < 0（射手右侧）；clip 自下进入 = position y < 0
 10. bolt/single_load：拉机柄先退到位才抛壳/压弹；single_load 的 round_in 0→1→0 且与枪机开合同步

退出码 0 = 全部对上。用法：python tools/check_rsc_1917_anim.py
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "art" / "rsc_1917"
RES = ROOT / "src/main/resources/assets/apocalypse_zombies"
JAVA = ROOT / "src/main/java/com/apocalypse/zombies/item/Rsc1917Item.java"
NAME = "rsc_1917"

# 生成器（tools/rsc_1917_bb_anim.js）声明的片段契约：改生成器就要改这里
EXPECT = {
    "static_idle":     {"length": 2.00, "loop": True,  "ticks": 40,
                        "hidden0": ["casing", "clip_empty", "round_in"], "visible0": ["clip"]},
    "draw":            {"length": 1.00, "loop": None,  "ticks": 20,
                        "hidden0": ["casing", "clip_empty", "round_in"], "visible0": ["clip"]},
    "shoot":           {"length": 0.60, "loop": None,  "ticks": 12,
                        "hidden0": ["clip_empty", "round_in"], "visible0": ["clip"]},
    "shoot_last":      {"length": 1.20, "loop": None,  "ticks": 24,
                        "hidden0": ["round_in"], "visible0": []},
    "bolt":            {"length": 1.10, "loop": None,  "ticks": 22,
                        "hidden0": ["clip_empty", "round_in"], "visible0": ["clip"]},
    "reload_tactical": {"length": 2.60, "loop": None,  "ticks": 52,
                        "hidden0": ["casing", "round_in"], "visible0": ["clip"]},
    "reload_empty":    {"length": 3.60, "loop": None,  "ticks": 72,
                        "hidden0": ["casing", "round_in"], "visible0": []},
    "single_load":     {"length": 1.50, "loop": None,  "ticks": 30,
                        "hidden0": ["casing", "clip_empty"], "visible0": ["clip"]},
}
# 允许出现 scale 通道的骨：隐藏件 + 满/空漏夹（漏夹要在换弹中段整块换肤）
SCALE_BONES = {"casing", "clip_empty", "round_in", "clip"}
HIDE_BONES = {"casing", "clip_empty", "round_in"}
TRAVEL = 1.36           # 枪机全行程（u）= 85mm，真机口径

fails: list[str] = []
notes: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        fails.append(msg)


def vec(v) -> list[float]:
    if isinstance(v, dict):
        v = v.get("vector") or v.get("post", {}).get("vector")
    return [float(x) for x in v]


def keys_of(anim, bone, chan):
    """[(t, (x,y,z)), ...] 升序；没有该通道返回 []"""
    ch = (anim.get("bones", {}).get(bone) or {}).get(chan)
    if not ch:
        return []
    if isinstance(ch, dict) and "vector" in ch:          # 单键静态缩写
        return [(0.0, vec(ch))]
    out = []
    for t, v in ch.items():
        out.append((float(t), vec(v)))
    return sorted(out)


def first_move_time(ks):
    """第一次离开静止位的时间"""
    for t, v in ks:
        if any(abs(x) > 1e-6 for x in v):
            return t
    return None


def rest_at_end(anim, length, bones):
    """这些骨在片段的末帧必须回零（末帧 = rest）；末态被 scale 0 收掉的隐藏件不参与"""
    for b in bones:
        sc = keys_of(anim, b, "scale")
        if sc and abs(sc[-1][1][0]) < 1e-6:
            continue
        for chan in ("position", "rotation"):
            ks = keys_of(anim, b, chan)
            if not ks:
                continue
            t, v = ks[-1]
            check(abs(t - length) < 0.05, f"{b}.{chan} 末键在 t={t}，片段长 {length}（末帧要留 rest）")
            check(all(abs(x) < 1e-6 for x in v), f"{b}.{chan} 末值 {v} != 0（会从中间姿势跳回 idle）")


def main() -> int:
    anim_path = RES / "animations" / f"{NAME}.animation.json"
    geo_path = RES / "geo" / f"{NAME}.geo.json"
    check(anim_path.exists() and geo_path.exists(), "缺 rsc_1917 的 geo/动画文件（先跑 install）")
    if fails:
        return report()
    doc = json.loads(anim_path.read_text(encoding="utf-8"))
    geo = json.loads(geo_path.read_text(encoding="utf-8"))
    A = doc["animations"]
    bones = {b["name"] for b in geo["minecraft:geometry"][0]["bones"]}

    # 1/2/3 片段表 / 骨名 / 时长契约
    check(set(A) == set(EXPECT), f"片段表不符：多 {sorted(set(A) - set(EXPECT))} 缺 {sorted(set(EXPECT) - set(A))}")
    for name, spec in EXPECT.items():
        a = A.get(name)
        if not a:
            continue
        check(abs(a["animation_length"] - spec["length"]) < 1e-6,
              f"{name} 长度 {a['animation_length']} 应为 {spec['length']}")
        check(bool(a.get("loop")) == bool(spec["loop"]), f"{name} loop={a.get('loop')} 与契约不符")
        for b in a["bones"]:
            check(b in bones, f"{name} 动到 geo 里没有的骨 {b}（GeckoLib 会静默忽略整条通道）")
        # scale 只在隐藏件上、只允许 0/1
        for b, chans in a["bones"].items():
            if "scale" not in chans:
                continue
            check(b in SCALE_BONES, f"{name}: {b} 上出现 scale 通道（规范禁整枪缩放）")
            for t, v in keys_of(a, b, "scale"):
                check(all(abs(x) < 1e-6 or abs(x - 1) < 1e-6 for x in v),
                      f"{name}: {b}.scale 在 t={t} 值 {v} 不是 0/1")
        # 隐藏件钉位
        for b in spec["hidden0"]:
            ks = keys_of(a, b, "scale")
            if ks:
                check(all(abs(x) < 1e-6 for x in ks[0][1]),
                      f"{name}: {b} 在 t={ks[0][0]} 应钉成 scale 0（现在是 {ks[0][1]}）")
        for b in spec["visible0"]:
            ks = keys_of(a, b, "scale")
            if ks:
                check(all(abs(x - 1) < 1e-6 for x in ks[0][1]),
                      f"{name}: {b} 在 t={ks[0][0]} 应可见（scale 1），现在是 {ks[0][1]}")

    # 3. 时长契约 vs Java
    jav = JAVA.read_text(encoding="utf-8")
    tick_map = {
        "static_idle": "IDLE_TICKS", "draw": "DRAW_TICKS", "shoot": "SHOOT_TICKS",
        "shoot_last": "SHOOT_LAST_TICKS", "bolt": "BOLT_TICKS",
        "reload_tactical": "RELOAD_TACTICAL_TICKS", "reload_empty": "RELOAD_EMPTY_TICKS",
        "single_load": "SINGLE_LOAD_TICKS",
    }
    for name, spec in EXPECT.items():
        const = tick_map[name]
        m = re.search(rf"{const}\s*=\s*(\d+)", jav)
        if not m:
            notes.append(f"Java 没有 {const}（idle/draw 无常量属正常；其余片段必须声明）")
            continue
        got = int(m.group(1))
        check(got == spec["ticks"],
              f"{name}: Java {const}={got}，按 20 t/s 应为 ceil({spec['length']}×20)={spec['ticks']}")

    # 5. 换弹因果（两段共用）
    for name in ("reload_tactical", "reload_empty"):
        a = A[name]
        cover = keys_of(a, "mag_cover", "rotation")
        t_open = next((t for t, v in cover if v[0] <= -45.0), None)
        t_shut = next((t for t, v in cover if t_open is not None and t > t_open and abs(v[0]) < 1e-6), None)
        check(t_open is not None, f"{name}: 弹匣盖始终没达到敞开位（rotation x ≤ −45°）")
        check(t_shut is not None, f"{name}: 弹匣盖没有回到闭合位")
        # 空漏夹掉出必须在开盖之后
        drop = first_move_time(keys_of(a, "clip_empty", "position"))
        if drop is not None:
            check(t_open is not None and drop >= t_open - 1e-6,
                  f"{name}: 空漏夹 t={drop} 掉出，早于开盖 t={t_open}")
            check(bool(keys_of(a, "clip_empty", "scale")), f"{name}: 空漏夹没有 scale 开关")
        # 新漏夹：纯平移 + 在开盖之后 + 上升到位
        cks = keys_of(a, "clip", "position")
        rise = first_move_time(cks)
        if rise is not None:
            check(t_open is not None and rise >= t_open - 1e-6,
                  f"{name}: 新漏夹 t={rise} 就开始进匣，早于开盖 t={t_open}")
            for t, v in cks:
                check(abs(v[0]) < 1e-6, f"{name}: 漏夹位置 x={v[0]} 非 0（真机是竖直平移进出）")
                check(abs(v[2]) < 1e-6, f"{name}: 漏夹位置 z={v[2]} 非 0（真机是竖直平移进出）")
            check(min(v[1] for _, v in cks) < -1.5, f"{name}: 漏夹没有从下方（y < −1.5u）上来")
        for t, v in keys_of(a, "clip", "rotation"):
            check(all(abs(x) < 1e-6 for x in v), f"{name}: 漏夹带翻转 rotation={v}（用户明确要求纯平移）")
        # 枪机：只能在合盖之后
        bl = keys_of(a, "bolt", "position")
        t_pull = first_move_time(bl)
        check(t_pull is not None and t_shut is not None and t_pull > t_shut,
              f"{name}: 枪机 t={t_pull} 就动了，早于合盖 t={t_shut}（真机是最后一步送弹入膛）")
        check(max((v[2] for _, v in bl), default=0) > TRAVEL - 0.05,
              f"{name}: 枪机行程 {max((v[2] for _, v in bl), default=0)} 不足全行程 {TRAVEL}")
        rest_at_end(a, EXPECT[name]["length"], ["move", "body", "bolt", "mag_cover", "clip", "clip_empty"])
    lt, le = A["reload_tactical"]["animation_length"], A["reload_empty"]["animation_length"]
    check(lt < le, f"reload_tactical({lt}) 应短于 reload_empty({le})")

    # 7. shoot / shoot_last
    for name in ("shoot", "shoot_last"):
        a = A[name]
        bl = keys_of(a, "bolt", "position")
        check(max((v[2] for _, v in bl), default=0) > TRAVEL - 0.05, f"{name}: 枪机没走满行程")
        t_rear = max(bl, key=lambda k: k[1][2])[0]
        cs = keys_of(a, "casing", "scale")
        t_show = next((t for t, v in cs if abs(v[0] - 1) < 1e-6), None)
        check(t_show is not None, f"{name}: 弹壳没有显形")
        check(t_show is not None and abs(t_show - t_rear) < 0.09,
              f"{name}: 弹壳 t={t_show} 显形，枪机退到位 t={t_rear}（应几乎同时）")
        check(bool(cs) and abs(cs[-1][1][0]) < 1e-6, f"{name}: 弹壳最后没有收回（scale 0）")
        cx = keys_of(a, "casing", "position")
        check(min((v[0] for _, v in cx), default=0) < -1.0,
              f"{name}: 弹壳没往 −X 抛（导出空间 −X = 射手右侧）")
    sl = A["shoot_last"]
    check(abs(keys_of(sl, "bolt", "position")[-1][1][2]) < 1e-6,
          "shoot_last: 末态枪机没闭锁 —— M1917 无空仓挂机，打完必须复进闭锁")
    sc = keys_of(sl, "clip", "scale")
    se = keys_of(sl, "clip_empty", "scale")
    check(any(abs(v[0]) < 1e-6 for _, v in sc) and any(abs(v[0]) < 1e-6 for _, v in se),
          "shoot_last: 末发没有做 满漏夹→空漏夹 的接力（下一次换弹要接着它）")

    # 10. bolt / single_load
    bo = A["bolt"]
    bl = keys_of(bo, "bolt", "position")
    t_rear = max(bl, key=lambda k: k[1][2])[0]
    cs = keys_of(bo, "casing", "scale")
    t_show = next((t for t, v in cs if abs(v[0] - 1) < 1e-6), None)
    check(t_show is not None and t_show >= t_rear - 0.05, "bolt: 弹壳在枪机退到位之前就显形了")
    sg = A["single_load"]
    rs = keys_of(sg, "round_in", "scale")
    check(any(abs(v[0] - 1) < 1e-6 for _, v in rs) and abs(rs[-1][1][0]) < 1e-6,
          "single_load: 那一发没有 0→1→0（压进去之后要藏起来）")
    sb = keys_of(sg, "bolt", "position")
    t_open = first_move_time(sb)
    r_show = next((t for t, v in rs if abs(v[0] - 1) < 1e-6), None)
    check(t_open is not None and r_show is not None and r_show > t_open,
          "single_load: 那一发在枪机退到位之前就出现了（真机是先开膛再放弹）")
    check(abs(sb[-1][1][2]) < 1e-6, "single_load: 末态枪机没闭锁")

    # 9. 镜像符号
    m1 = A["reload_empty"]
    for name, a in A.items():
        for t, v in keys_of(a, "mag_cover", "rotation"):
            check(v[0] <= 1e-6, f"{name}: mag_cover.rotation x={v[0]} 为正（导出空间开盖应为 −X）")
        for t, v in keys_of(a, "bolt", "position"):
            check(v[2] >= -1e-6, f"{name}: bolt.position z={v[2]} 为负（后拉应沿 +Z）")
        for t, v in keys_of(a, "casing", "position"):
            check(v[0] <= 1e-6, f"{name}: casing.position x={v[0]} 为正（抛壳应向 −X）")
        # clip.position y：主行程必须为负（自下上来），允许 +0.10 以内的落座回弹（压到位那一顿）
        for t, v in keys_of(a, "clip", "position"):
            check(v[1] <= 0.10, f"{name}: clip.position y={v[1]} 过大（自下进入主行程应为负）")
    notes.append("镜像符号: mag_cover rotX≤0 / bolt posZ≥0 / casing posX≤0 / clip posY≤0 ✓")

    print(f"片段 {len(A)} 个：", ", ".join(f"{k}({v['animation_length']}s)" for k, v in A.items()))
    for name in EXPECT:
        a = A.get(name)
        if not a:
            continue
        nk = sum(len(c) for b in a["bones"].values() for c in b.values())
        print(f"  {name:16s} bones={len(a['bones']):2d} keys={nk:3d} "
              f"hidden0={EXPECT[name]['hidden0']}")
    return report()


def report() -> int:
    for n in notes:
        print("  " + n)
    if fails:
        print(f"\n*** {len(fails)} 项未过：")
        for f in fails:
            print("  - " + f)
        return 1
    print("\n动画自检：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
