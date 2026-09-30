#!/usr/bin/env python3
"""M1 加兰德：**去掉漏夹井盖（cover）** —— 真机机匣顶部没有这个件。

真机依据（美陆军 TACOM/ARDEC 手册 + 真机拆件表）：
  · M1 加兰德装填时漏夹是**直接压下去**的：「With the right hand, place a full clip on top of the
    follower assembly … press the clip straight down into the receiver until it catches.」——
    全程没有"打开盖"这一步；导向靠机匣两侧壁，扣住靠机匣**左侧**的漏夹卡榫（clip_latch）。
  · 真机拆件表里查不到这件东西：机匣顶面以上就是敞开的，装上夹以后**看得见顶上那一发弹**。

模型现状（本脚本删除的对象，几何全部量过）：
  · `cover` 骨 3 个方块，pivot 在机匣后端上缘 (0, 2.556, −0.816)：
      cover_l / cover_r   x ±0.10…±0.30   y 2.556…2.636   z −3.984…−2.400（601…700mm）
      cover_h（提手）      x ±0.30         y 2.636…2.684   z −3.088…−2.752（657…678mm）
  · 两条轨把井口从 |x| < 0.190 收窄到 |x| < 0.100，而漏夹宽 ±0.167 ⇒ **压不过去**，
    所以旧动画必须让"盖"抬起 0.55u（34mm）才装得进夹 —— 这一步真机上不存在，是这件几何造成的；
    而且"盖合"时两条轨的内面正好扎进漏夹里（0.100 < 0.167），合上就等于穿模。
  · 提手横在井口正中 657…678mm：装上夹以后一根横杆压在顶上，真机上不该有。

判据（本脚本的不变量，删前删后都跑）：
  · **敞口**：机匣顶面（y = 2.556）以上、井的内档（z −3.884…−2.500）、漏夹宽度（±0.167 + 0.01）
    这一段竖直通道里不许有任何方块 —— 漏夹要直着压下去，真机上也看得见顶上那一发。
  · **净宽**：同一段里机匣壁的最内侧 x 必须 ≥ 漏夹半宽 + 0.01，夹才过得去。
  · 删掉 cover 之后，其余骨的方块与 uv 必须一字未动。

删除后：井口开口恢复成机匣两侧壁之间 |x| < 0.190（= 0.38u ≈ 24mm），漏夹（±0.167）直进直出，
不再需要"抬盖"。动作侧由 tools/m1_reload_real.py 的第 ⑧ 步同步删掉所有剪辑里的 cover 通道。

用法：
  python tools/m1_cover_removal_geo.py --check   # 预演 + 不变量校验，不写盘
  python tools/m1_cover_removal_geo.py           # 写入 art/ 并同步 src/（删前留档 *.pre-cover.bak.json）
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "art/m1garand"
SRC = ROOT / "src/main/resources/assets/apocalypse_zombies"
GEO_ART, GEO_SRC = ART / "m1_garand.geo.json", SRC / "geo/m1_garand.geo.json"

BONE = "cover"
TOP_Y = 2.556                    # 机匣顶面（两侧壁基面）；它以上就是敞开的
Z_LO, Z_HI = -3.884, -2.500      # 井的内档（前后横梁之间）
CLIP_CLEARANCE = 0.01            # 漏夹两侧各留的余量（0.01u = 0.6mm）
EPS = 1e-3

fails: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        fails.append(msg)


def cube_bbox(c: dict) -> list[float]:
    o, s = c.get("origin", [0, 0, 0]), c.get("size", [0, 0, 0])
    return [o[0], o[1], o[2], o[0] + s[0], o[1] + s[1], o[2] + s[2]]


def corridor(bones: list[dict], span: float) -> tuple[float | None, list[tuple[str, list[float]]]]:
    """机匣顶面以上的井口通道：返回 (净宽半值, 挡在通道里的件)。"""
    half: float | None = None
    blockers: list[tuple[str, list[float]]] = []
    for b in bones:
        for c in b.get("cubes", []):
            x0, y0, z0, x1, y1, z1 = cube_bbox(c)
            if y1 <= TOP_Y + EPS:                       # 不高过机匣顶面：井内衬/机匣本体，不算
                continue
            if z1 <= Z_LO + EPS or z0 >= Z_HI - EPS:    # 不在井的内档里
                continue
            if x1 > -span and x0 < span:                # 落在漏夹宽度内 ⇒ 挡住压夹通道
                blockers.append((b["name"], [round(v, 3) for v in (x0, y0, z0, x1, y1, z1)]))
                continue
            edge = x0 if x0 >= 0.0 else -x1             # 通道外、某一侧壁的最内侧 x
            half = edge if half is None else min(half, edge)
    return half, blockers


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def dump(p: Path, d: dict) -> None:
    """与 tools/m1_well_shift.py、m1_garand_latch_geo.py 同款：紧凑 JSON。"""
    p.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只预演与校验，不写盘")
    args = ap.parse_args()

    geo = load(GEO_ART)
    bones = geo["minecraft:geometry"][0]["bones"]
    by_name = {b["name"]: b for b in bones}
    clip = by_name.get("clip_in")
    check(clip is not None, "几何里找不到 clip_in 骨（量不出漏夹宽度）")
    clip_half = 0.0
    if clip is not None:
        clip_half = max(abs(min(cube_bbox(c)[0] for c in clip["cubes"])),
                        abs(max(cube_bbox(c)[3] for c in clip["cubes"])))

    span = clip_half + CLIP_CLEARANCE

    # ---- 不变量 1：删之前井口是不是被挡住 ---------------------------------------
    half_before, blocked_before = corridor(bones, span)
    hb = half_before if half_before is not None else 0.0
    print(f"漏夹半宽 {clip_half:.3f}u（{clip_half * 62.5:.1f}mm），压夹通道判定宽度 {span:.3f}u")
    print(f"删除前：机匣两侧壁之间净宽 {hb:.3f}u，压夹通道内遮挡 {len(blocked_before)} 件"
          f" ⇒ {'漏夹压不进去' if blocked_before else '通道是通的'}")
    for name, bb in blocked_before:
        print(f"        · {name} {bb}")
    if BONE not in by_name:
        print(f"（几何里已经没有 {BONE} 骨 —— 脚本已应用过）")
    else:
        check(bool(blocked_before),
              f"{BONE} 存在，但它没有挡在压夹通道上（几何可能被改过，先看清楚再删）")
        check(any(name == BONE for name, _ in blocked_before),
              f"通道里的遮挡件不是 {BONE}（{blocked_before}）")

    # ---- 预演删除后的状态 -----------------------------------------------------
    after = [b for b in bones if b["name"] != BONE]
    half_after, blocked_after = corridor(after, span)
    ha = half_after if half_after is not None else 0.0
    check(not blocked_after, f"删掉 {BONE} 之后通道里仍有遮挡：{blocked_after}")
    check(ha >= span, f"删掉 {BONE} 之后井口净宽 {ha:.3f} 仍不够漏夹 ±{clip_half:.3f} 通过（需 {span:.3f}）")
    # 其余骨（含方块与 uv）必须一字未动
    kept = {b["name"]: b for b in after}
    for name, b in by_name.items():
        if name == BONE:
            continue
        check(kept.get(name) == b, f"删除操作动到了 {name} 骨（应只删 {BONE}）")

    print(f"删除后：两侧壁净宽 {ha:.3f}u（漏夹余量 {(ha - clip_half) * 62.5:.1f}mm）、通道畅通，骨 "
          f"{len(bones)} → {len(after)}，方块 "
          f"{sum(len(b.get('cubes', [])) for b in bones)} → "
          f"{sum(len(b.get('cubes', [])) for b in after)}，通道内遮挡 {len(blocked_after)} 件")
    print(f"（对照：旧动画为此要抬盖 0.55u = {0.55 * 62.5:.1f}mm —— 这一步随件一起取消）")

    if fails:
        print("\n不通过：")
        for f in fails:
            print("  ✗", f)
        return 1

    bak = ART / "m1_garand.geo.pre-cover.bak.json"      # 与 art/awm 的 *.pre-9217.bak.json 同款命名
    if BONE in by_name and not args.check:
        geo["minecraft:geometry"][0]["bones"] = after
        if not bak.exists():
            shutil.copy2(GEO_ART, bak)
        dump(GEO_ART, geo)
        shutil.copy2(GEO_ART, GEO_SRC)
        print(f"\n已删除 {BONE} 骨（3 个方块）并写入 {GEO_ART.name} + 同步 src/"
              f"（删前留档 {bak.name}）")
    elif args.check:
        print("\n（--check：未写盘）")
    else:
        print("\n已存在，无改动")
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
