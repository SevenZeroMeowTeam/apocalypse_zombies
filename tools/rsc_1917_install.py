#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RSC M1917 落位：把 build/ 里的产物规范化后装进 assets/ 与 art/rsc_1917/。

分工（与短管喷/S686 同规矩）：*_build.js 只管下发+导出，*_install.py 只管落位与规范化。

用法：py tools/rsc_1917_install.py [--check]

规范化内容（幂等，可反复跑）：
  * identifier = geometry.rsc_1917；texture_width/height = 512
  * root→move 的父子关系补齐（Blockbench 导出会把顶层 move 的 parent 丢掉）
  * 动画文件里的骨骼必须都在 geo 里；`root` 不进动画（它是静态的根）
  * 动画文件键名不得带 `animation.` 前缀（GeckoLib 4 用裸名）
"""
import argparse
import json
import os
import shutil
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BUILD = os.path.join(ROOT, "build")
ARC = os.path.join(ROOT, "art", "rsc_1917")
RES = os.path.join(ROOT, "src", "main", "resources", "assets", "apocalypse_zombies")

NAME = "rsc_1917"
SRC_GEO = os.path.join(BUILD, f"{NAME}.geo.json")
SRC_TEX = os.path.join(BUILD, f"{NAME}_tex.png")
SRC_ANIM = os.path.join(ARC, f"{NAME}.animation.json")

DST_GEO = os.path.join(RES, "geo", f"{NAME}.geo.json")
DST_TEX = os.path.join(RES, "textures", "item", f"{NAME}.png")
DST_ANIM = os.path.join(RES, "animations", f"{NAME}.animation.json")
ARC_GEO = os.path.join(ARC, f"{NAME}.geo.json")
ARC_TEX = os.path.join(ARC, f"{NAME}_tex.png")


def norm_geo(doc):
    g = doc["minecraft:geometry"][0]
    d = g["description"]
    d["identifier"] = f"geometry.{NAME}"
    d["texture_width"] = 512
    d["texture_height"] = 512
    names = {b["name"]: b for b in g["bones"]}
    if "move" in names and "root" in names and not names["move"].get("parent"):
        names["move"]["parent"] = "root"
    for b in g["bones"]:
        if b.get("parent") == b["name"]:
            del b["parent"]
    return doc


def norm_anim(doc):
    anims = {}
    for k, v in doc["animations"].items():
        anims[k[len("animation."):] if k.startswith("animation.") else k] = v
    doc["animations"] = anims
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只核对，不写盘")
    args = ap.parse_args()

    for p in (SRC_GEO, SRC_TEX, SRC_ANIM):
        if not os.path.exists(p):
            sys.exit(f"缺输入 {p}（先跑 tools/rsc_1917_build.js 与 tools/rsc_1917_anim.py）")

    geo = norm_geo(json.load(open(SRC_GEO, encoding="utf-8")))
    anim = norm_anim(json.load(open(SRC_ANIM, encoding="utf-8")))

    bones = {b["name"] for b in geo["minecraft:geometry"][0]["bones"]}
    used = set()
    for a in anim["animations"].values():
        used |= set(a["bones"].keys())
    missing = sorted(used - bones)
    ghosts = sorted(b for b in ("root",) if b in used)
    cubes = sum(len(b.get("cubes", [])) for b in geo["minecraft:geometry"][0]["bones"])

    print(f"geo   : {len(bones)} bones / {cubes} cubes / {geo['minecraft:geometry'][0]['description']['texture_width']}²")
    print(f"anim  : {len(anim['animations'])} clips / 动到的骨 {len(used)}")
    print(f"贴图  : {os.path.getsize(SRC_TEX)} bytes (512²)")
    ok = True
    if missing:
        print(f"  ! 动画动到 geo 里没有的骨: {missing}")
        ok = False
    if ghosts:
        print(f"  ! 动画里出现静态根骨: {ghosts}")
        ok = False
    for need in ("move", "body", "bolt", "mag_cover", "clip", "clip_empty", "casing", "round_in"):
        if need not in bones:
            print(f"  ! geo 缺骨 {need}")
            ok = False
    for clip in ("static_idle", "draw", "shoot", "bolt", "reload_tactical", "reload_empty",
                 "single_load", "shoot_last"):
        if clip not in anim["animations"]:
            print(f"  ! 动画缺片段 {clip}")
            ok = False
    if not ok:
        sys.exit("规范化自检未过，未落位")

    if args.check:
        print("核对通过（未写盘）")
        return 0

    os.makedirs(os.path.dirname(DST_GEO), exist_ok=True)
    os.makedirs(os.path.dirname(DST_TEX), exist_ok=True)
    os.makedirs(os.path.dirname(DST_ANIM), exist_ok=True)
    with open(DST_GEO, "w", encoding="utf-8") as fh:
        json.dump(geo, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(ARC_GEO, "w", encoding="utf-8") as fh:
        json.dump(geo, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(DST_ANIM, "w", encoding="utf-8") as fh:
        json.dump(anim, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    shutil.copyfile(SRC_TEX, DST_TEX)
    shutil.copyfile(SRC_TEX, ARC_TEX)
    print("落位:")
    for p in (DST_GEO, DST_ANIM, DST_TEX, ARC_GEO, ARC_TEX):
        print(f"  {os.path.relpath(p, ROOT)}  {os.path.getsize(p)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
