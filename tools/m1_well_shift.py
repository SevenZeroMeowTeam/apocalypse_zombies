#!/usr/bin/env python3
"""M1 加兰德：漏夹井标定修正（井后移 82mm）+ 装填动作"纯平移化"。

真机标定（自 art/m1garand/ref_m1_side.png 逐像素量取，全长 1105mm 定标）：
  · 机匣前缘（木护木→金属）  577mm      · 机匣后缘（金属→木托颈）  798mm
  · 扳机护圈环 718–790mm（真机 LOP 13" → 扳机 ~770mm，互证）
  · 右侧抛壳窗 700–795mm，后照门座 700–782mm，拉机柄（op-rod 折柄）700–740mm
  · 闭锁面 = 枪管 24" = 610mm（自枪口）

⇒ 漏夹井：前壁 = 闭锁面 610mm，井长 100mm → 610…710mm。
  在模型自身锚点上落地：井后壁贴"后照门座/拉机柄前沿 = 700mm" ⇒ 井 = 601…700mm。
  旧井 519…618mm —— 恰好比正确位置靠前一个井长；成因是 v3 把参考图里"木护木/木托颈"
  之间的边界当成了机匣前缘（519mm），机匣实长因此被放大到 280mm（真机 221mm）。
  井落在机匣前三分之一、闭锁面之后，与真机一致。

同时把弹壳静止位（= 抛出点）从 795mm（抛壳窗后沿之外）前移到 748mm（窗内中心）：
弹壳出现在抛壳窗正上方，即用户标注"弹壳从黄色方框上方抛出"。

用法：
  python tools/m1_well_shift.py --check    # 预演并校验结果，不写盘
  python tools/m1_well_shift.py            # 应用并同步 art/ 与 src/
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
ANIM_ART, ANIM_SRC = ART / "m1_garand.animation.json", SRC / "animations/m1_garand.animation.json"

MM = 62.5          # 16u = 1 block = 1000mm  ->  1u = 62.5mm
Z0 = -13.60        # 枪口


def Z(mm: float) -> float:
    """毫米（自枪口）-> 模型 z。与生成器 tools/m1_garand_bb_gen.js 的 Z() 同一定义。"""
    return Z0 + mm / MM


# --- 本次修正的目标（真机标定值）-------------------------------------------------
WELL_OLD_F, WELL_OLD_B = Z(519), Z(618)      # -5.296, -3.712
WELL_NEW_F, WELL_NEW_B = Z(601), Z(700)      # -3.984, -2.400
WELL_DZ = WELL_NEW_F - WELL_OLD_F            # +1.312u (82mm)
CASING_DZ = Z(748) - Z(795)                  # -0.752u (-47mm)

TOL = 1e-3
fails: list[str] = []
notes: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        fails.append(msg)


def cube_bbox(cube: dict) -> list[float]:
    o, s = cube.get("origin", [0, 0, 0]), cube.get("size", [0, 0, 0])
    return [o[0], o[1], o[2], o[0] + s[0], o[1] + s[1], o[2] + s[2]]


def near(a: float, b: float, tol: float = TOL) -> bool:
    return abs(a - b) <= tol


def find_cube(cubes: list[dict], want: list[float]) -> dict | None:
    """按外框（含容差）唯一匹配一个方块。"""
    hits = [c for c in cubes if all(near(a, b, 0.02) for a, b in zip(cube_bbox(c), want))]
    return hits[0] if len(hits) == 1 else None


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def bone_bbox(bones: dict, name: str) -> list[float] | None:
    cubes = bones[name].get("cubes", [])
    if not cubes:
        return None
    boxes = [cube_bbox(c) for c in cubes]
    return [min(b[i] for b in boxes) for i in range(3)] + [max(b[i + 3] for b in boxes) for i in range(3)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只预演与校验，不写盘")
    args = ap.parse_args()

    geo = load(GEO_ART)
    bones = {b["name"]: b for b in geo["minecraft:geometry"][0]["bones"]}
    body = bones["body"]["cubes"]

    # --- 1. 定位井组方块：接受"旧标定"或"新标定"两种外框 -------------------------
    want_old = {
        "well_f":    [-0.30, 2.556, WELL_OLD_F - 0.04, 0.30, 2.716, WELL_OLD_F + 0.10],
        "well_l":    [-0.30, 2.556, WELL_OLD_F, -0.19, 2.716, WELL_OLD_B],
        "well_r":    [0.19, 2.556, WELL_OLD_F, 0.30, 2.716, WELL_OLD_B],
        "well_b":    [-0.30, 2.556, WELL_OLD_B - 0.10, 0.30, 2.716, WELL_OLD_B + 0.04],
        "well_cav":  [-0.19, 2.204, WELL_OLD_F + 0.10, 0.19, 2.556, WELL_OLD_B - 0.10],
        "brg_top":   [-0.30, 2.556, Z(652), 0.30, 2.684, Z(799)],
    }
    # 不属于井组、但外框与井内腔相邻的方块：枪机通道属于枪机，必须留在原位
    stay_old = {"bolt_chan": [-0.21, 2.012, Z(519) + 0.10, 0.21, 2.524, Z(652) - 0.10]}
    def bb_shift(bb: list[float], dz: float) -> list[float]:
        return [bb[0], bb[1], bb[2] + dz, bb[3], bb[4], bb[5] + dz]

    want_new = {n: bb_shift(bb, WELL_DZ) for n, bb in want_old.items()}
    want_new["brg_top"] = [-0.30, 2.556, WELL_NEW_B, 0.30, 2.684, Z(799)]   # 切短，非平移

    found: dict[str, dict] = {}
    at_new: dict[str, bool] = {}
    for name, bb in want_old.items():
        cube_new = find_cube(body, want_new[name])
        cube_old = None if cube_new else find_cube(body, bb)
        cube = cube_new or cube_old
        if cube is None:
            fails.append(f"在 body 里找不到唯一的 {name}（旧外框 {[round(v, 3) for v in bb]}"
                         f" / 新外框 {[round(v, 3) for v in want_new[name]]}）")
        else:
            found[name] = cube
            at_new[name] = cube_new is not None
    already = not fails and all(at_new.values())
    if not fails and not already and any(at_new.values()):
        fails.append("几何处于半新半旧状态（部分方块已移动）—— 请先从 "
                     "art/m1garand/m1_garand.geo.json.bak 恢复再重跑")

    # 枪机通道若被误移，记录待归位
    revert: dict[str, dict] = {}
    if not fails:
        for name, bb in stay_old.items():
            moved = find_cube(body, bb_shift(bb, WELL_DZ))
            if moved and not find_cube(body, bb):
                revert[name] = moved
            elif not find_cube(body, bb):
                fails.append(f"找不到 {name} —— 既不在原位也不在误移位置")
    if fails:
        print("定位失败，未改动任何文件：")
        for f in fails:
            print("  ✗", f)
        return 1

    # --- 2. body：井组后移，机匣桥面从井后壁起（内存中应用）----------------------
    if not already:
        for name in ("well_f", "well_l", "well_r", "well_b", "well_cav"):
            found[name]["origin"][2] += WELL_DZ
        bridge = found["brg_top"]
        bridge["origin"][2] = WELL_NEW_B
        bridge["size"][2] = Z(799) - WELL_NEW_B        # 桥面前沿让到井后壁
        notes.append(f"brg_top 起端 {Z(652):.3f} -> {WELL_NEW_B:.3f}（井口让开 {WELL_NEW_B - Z(652):+.3f}u）")

    # --- 3. cover / clip_in 随井后移；casing 前移到抛壳窗内 ----------------------
    # 注意 pivot 语义：clip_in / casing 的 pivot 是"自身中心"，必须随几何一起走
    # （旋转/翻转都以它为中心）；cover 的 pivot 是"机匣后端上缘"这个固定基准，
    # 盖板动作是纯平移，pivot 留在 Z(799) 才能在重新生成时与生成器一致。
    # 2026-09-30：cover（漏夹井盖）已由 tools/m1_cover_removal_geo.py 从几何里删掉（真机机匣顶部没有
    # 这件东西，漏夹是直着压下去、靠左侧卡榫扣住的）。本脚本对"没有盖"的几何照样能跑：盖相关的
    # 平移/不变量/报告全部跳过。
    has_cover = "cover" in bones
    if not already:
        moved3 = ([("cover", WELL_DZ, "漏夹盖", False)] if has_cover else []) + [
            ("clip_in", WELL_DZ, "漏夹", True),
            ("casing", CASING_DZ, "弹壳", True)]
        for bone, dz, label, move_pivot in moved3:
            b = bones[bone]
            for cube in b.get("cubes", []):
                cube["origin"][2] += dz
            if move_pivot:
                b["pivot"][2] += dz
            notes.append(f"{label}({bone}): 几何 Δz {dz:+.3f}u，pivot {b['pivot'][2]:.3f}"
                         f"{'（随几何）' if move_pivot else '（固定基准，不变）'}")
    # 自愈：盖板 pivot 必须锁在"机匣后端上缘" Z(799)（固定基准，动画是纯平移）
    if has_cover:
        cover_pivot_z0 = bones["cover"]["pivot"][2]
        bones["cover"]["pivot"][2] = Z(799)
        pivot_fixed = not near(cover_pivot_z0, Z(799))
    else:
        pivot_fixed = False

    # 自愈：枪机通道不被井组带走
    for name, cube in revert.items():
        cube["origin"][2] -= WELL_DZ
        notes.append(f"{name}（枪机通道）属于枪机，不随井移动：z 归位 {cube['origin'][2]:.3f}")

    # --- 4. 装填动作纯平移化：clip_in 旋转清零、位移 x 归零（保留 y/z 垂直按压）---
    anim = load(ANIM_ART)
    rot_changed: list[str] = []
    pos_changed: list[str] = []
    for clip, data in anim["animations"].items():
        ch = data.get("bones", {}).get("clip_in")
        if not ch:
            continue
        rot = ch.get("rotation")
        channels = [] if "vector" in (rot or {}) else list((rot or {}).items())
        if "vector" in (rot or {}) and any(abs(v) > 1e-6 for v in rot["vector"]):
            rot["vector"] = [0, 0, 0]
            rot_changed.append(f"{clip}(常量)")
        for t, key in channels:
            slot = key.setdefault("post", {}) if isinstance(key, dict) else {}
            v = slot.get("vector")
            if v and any(abs(x) > 1e-6 for x in v):
                slot["vector"] = [0, 0, 0]
                rot_changed.append(f"{clip}@{t}")
        pos = ch.get("position")
        if isinstance(pos, dict) and "vector" not in pos:
            for t, key in pos.items():
                slot = key.setdefault("post", {}) if isinstance(key, dict) else {}
                v = slot.get("vector")
                if v and abs(v[0]) > 1e-6:
                    slot["vector"][0] = 0.0
                    pos_changed.append(f"{clip}@{t} x={v[0]}")

    # --- 5. 不变量校验（针对应用后的内存状态）------------------------------------
    clip = bone_bbox(bones, "clip_in")
    cover = bone_bbox(bones, "cover") if has_cover else None
    casing = bone_bbox(bones, "casing")
    port = (Z(700), Z(795))
    check(clip[2] >= WELL_NEW_F - 0.08 and clip[5] <= WELL_NEW_B + 0.08,
          f"漏夹越出漏夹井：clip z {clip[2]:.3f}…{clip[5]:.3f} 不在井 {WELL_NEW_F:.3f}…{WELL_NEW_B:.3f} 内")
    if cover is not None:
        check(near(cover[2], WELL_NEW_F, 0.05) and near(cover[5], WELL_NEW_B, 0.05),
              f"漏夹盖没压在井口：cover z {cover[2]:.3f}…{cover[5]:.3f} ≠ 井 {WELL_NEW_F:.3f}…{WELL_NEW_B:.3f}")
    check(casing[2] >= port[0] - 0.05 and casing[5] <= port[1] + 0.05,
          f"弹壳不在抛壳窗内：casing z {casing[2]:.3f}…{casing[5]:.3f} 不在窗 {port[0]:.3f}…{port[1]:.3f}")
    check(any(near(bb[5], WELL_NEW_B, 0.02) for bb in
              [cube_bbox(c) for c in bones["body"]["cubes"] if near(cube_bbox(c)[1], 2.556, 0.02)]),
          f"井后壁没有贴到后照门座/拉机柄前沿 {WELL_NEW_B:.3f}")
    check(find_cube(bones["body"]["cubes"], bb_shift(stay_old["bolt_chan"], WELL_DZ)) is None,
          "枪机通道仍停在误移位置（它属于枪机，应留在 Z(519)…Z(652)）")
    check(find_cube(bones["body"]["cubes"], stay_old["bolt_chan"]) is not None,
          "枪机通道不在原位 Z(519)…Z(652)")
    check(WELL_NEW_F > Z(519), f"井前壁 {WELL_NEW_F:.3f} 顶到机匣前缘 {Z(519):.3f}")
    pv = bones["clip_in"]["pivot"][2]
    check(WELL_NEW_F - 0.5 < pv < WELL_NEW_B + 0.5,
          f"漏夹 pivot {pv:.3f} 不在井内（动画偏移全部相对它，必须随几何一起移动）")
    if has_cover:
        check(near(bones["cover"]["pivot"][2], Z(799), 1e-6),
              f"漏夹盖 pivot {bones['cover']['pivot'][2]:.3f} 不在机匣后端上缘 {Z(799):.3f}"
              f"（盖板动作是纯平移，pivot 是固定基准，须与生成器一致）")
    for clip_name in ("reload_empty", "reload_tactical"):
        ch = anim["animations"][clip_name]["bones"].get("clip_in", {})
        for t, key in (ch.get("rotation") or {}).items():
            v = (key.get("post") or key).get("vector") or [0, 0, 0]
            check(all(abs(x) < 1e-6 for x in v), f"{clip_name}@{t} clip_in 仍有旋转 {v}")
        for t, key in (ch.get("position") or {}).items():
            v = (key.get("post") or key).get("vector") or [0, 0, 0]
            check(abs(v[0]) < 1e-6, f"{clip_name}@{t} clip_in 仍有横向位移 x={v[0]}")

    # --- 6. 报告 ------------------------------------------------------------------
    print(f"漏夹井标定：{WELL_OLD_F:.3f}…{WELL_OLD_B:.3f}  ->  {WELL_NEW_F:.3f}…{WELL_NEW_B:.3f}"
          f"   Δz = {WELL_DZ:+.3f}u ({WELL_DZ * MM:+.0f}mm)"
          f"   真机 610…710mm，落位 601…700mm{'   [已应用]' if already else ''}")
    print(f"装填动作：clip_in 旋转清零 {len(rot_changed)} 处，横向位移归零 {len(pos_changed)} 处"
          f"（保留 y/z —— '压下弹夹'仍是平移）")
    for line in rot_changed + pos_changed:
        print("   ·", line)
    print("\n=== 应用后不变量 ===")
    print(f"  漏夹井 z {WELL_NEW_F:.3f}…{WELL_NEW_B:.3f}")
    print(f"  漏夹   z {clip[2]:.3f}…{clip[5]:.3f}"
          + (f"   漏夹盖 z {cover[2]:.3f}…{cover[5]:.3f}" if cover is not None
             else "   漏夹盖：已删除（真机机匣顶部无盖，见 tools/m1_cover_removal_geo.py）")
          + "   （85mm 漏夹 / 100mm 井）")
    print(f"  弹壳   z {casing[2]:.3f}…{casing[5]:.3f}   抛壳窗 {port[0]:.3f}…{port[1]:.3f}")
    for line in notes:
        print("  ·", line)

    if fails:
        print(f"\n{len(fails)} 条不通过（未写盘）：")
        for f in fails:
            print("  ✗", f)
        return 1
    print("\n全部通过")

    if args.check:
        print("（--check：未写盘）")
        return 0
    if not already or pivot_fixed or revert:
        for art, src in ((GEO_ART, GEO_SRC), (ANIM_ART, ANIM_SRC)):
            if not art.with_suffix(art.suffix + ".bak").exists():
                shutil.copy2(art, art.with_suffix(art.suffix + ".bak"))
        dump(GEO_ART, geo)
        shutil.copy2(GEO_ART, GEO_SRC)
        dump(ANIM_ART, anim)
        shutil.copy2(ANIM_ART, ANIM_SRC)
        print("已写入 art/ 并同步 src/（原件备份 *.bak）"
              + ("（含盖板 pivot 归位）" if already and pivot_fixed else ""))
    else:
        print("已是目标标定，无改动")
    return 0


if __name__ == "__main__":
    sys.exit(main())
