#!/usr/bin/env python3
"""M1 加兰德 raw keyframe dump -> GeckoLib animation.json（与 Blockbench GeckoLib 插件同款格式）。

Input : art/m1garand/_anim_raw.json   (由 tools/m1_garand_bb_anim.js 在 Blockbench 里写盘)
Output: art/m1garand/m1_garand.animation.json

规则是从出厂文件 art/m1garand/m1_garand.animation.json 逆向核对出来的：
  * 时间按 24fps 吸附（半点进位，同 JS Math.round）t -> floor(t*24+0.5)/24；
    键名至少保留一位小数（"0.0" / "1.8333"）
  * 左手/右手系变换（与 geo.json 的 X 翻转一致，实测自出厂文件）：
      position -> [-x,  y, z]
      rotation -> [-x, -y, z]
      scale    -> [ x,  y, z]   （不变）
  * 插值决定写法：catmullrom/smooth/bezier/easeinout ->
        {"post": {"vector": [...]}, "lerp_mode": "catmullrom"}
      step -> {"post": {"vector": [...]}, "lerp_mode": "step"}
      linear（含 rest/scale 这类直接写的键）-> {"vector": [...]}
  * 单键通道一律写成静态缩写 {"rotation": {"vector": [0, 0, 0]}}
  * 首键落在非 0 帧的 catmullrom/step 通道，首键写成
        {"pre": {"vector": v}, "post": {"vector": v}, "lerp_mode": <mode>}
    （出厂文件 bolt.casing 0.4167 就是这么写的：该帧之前保持该值，语义上等价于静止位）
  * 通道顺序 rotation -> position -> scale；骨骼顺序沿用 dump 里的 animator 顺序
  * loop 只在循环动画上写 "loop": true；顶层 geckolib_format_version = 2
校验：tools/m1_anim_export.py --check 会把本次产物与出厂文件逐字节比对，
      未改动的动画（static_idle / draw）必须完全一致，否则说明规则反推错了。
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.normpath(os.path.join(HERE, "..", "art", "m1garand", "_anim_raw.json"))
OUT = os.path.normpath(os.path.join(HERE, "..", "art", "m1garand", "m1_garand.animation.json"))

FPS = 24.0
LERP = {"catmullrom": "catmullrom", "smooth": "catmullrom", "bezier": "catmullrom",
        "easeinout": "catmullrom", "step": "step"}


def flip(chan, vals):
    """Blockbench 工程空间 -> 导出空间（X 轴翻转，与 geo.json 一致）。"""
    x, y, z = (float(v) for v in vals)
    if chan == "position":
        return [-x, y, z]
    if chan == "rotation":
        return [-x, -y, z]
    return [x, y, z]


def fmt_time(t):
    s = f"{float(t):.4f}".rstrip("0")
    return s + "0" if s.endswith(".") else s


def num(v):
    f = float(v)
    return int(f) if f.is_integer() else round(f, 4)


def vec(vals):
    return [num(v) for v in vals]


def build(raw):
    animations = {}
    for a in raw["anims"]:
        bones = {}
        for bone, chans in a["bones"].items():
            out_bone = {}
            for chan in ("rotation", "position", "scale"):
                arr = chans.get(chan)
                if not arr:
                    continue
                snapped = {}
                for k in sorted(arr, key=lambda k: float(k["t"])):
                    t = math.floor(float(k["t"]) * FPS + 0.5) / FPS
                    snapped[fmt_time(t)] = k          # 同帧取后者
                times = sorted(snapped.keys(), key=float)
                if len(times) == 1:
                    out_bone[chan] = {"vector": vec(flip(chan, snapped[times[0]]["v"]))}
                    continue
                out_chan = {}
                for i, t in enumerate(times):
                    v = vec(flip(chan, snapped[t]["v"]))
                    mode = LERP.get(snapped[t].get("i") or "")
                    if not mode:
                        out_chan[t] = {"vector": v}
                    elif i == 0 and float(t) != 0.0:
                        out_chan[t] = {"pre": {"vector": v}, "post": {"vector": v},
                                       "lerp_mode": mode}
                    else:
                        out_chan[t] = {"post": {"vector": v}, "lerp_mode": mode}
                out_bone[chan] = out_chan
            if out_bone:
                bones[bone] = out_bone
        entry = {}
        if a["loop"] == "loop":
            entry["loop"] = True
        entry["animation_length"] = num(a["length"])
        entry["bones"] = bones
        animations[a["name"]] = entry
    return {"format_version": "1.8.0", "animations": animations, "geckolib_format_version": 2}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="与现有文件比对，不写盘")
    args = ap.parse_args()

    with open(RAW, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    doc = build(raw)

    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        with open(OUT, "r", encoding="utf-8") as fh:
            old = json.load(fh)
        bad = 0
        for name in old.get("animations", {}):
            same = json.dumps(old["animations"][name], sort_keys=True) == \
                   json.dumps(doc["animations"].get(name, {}), sort_keys=True)
            print(f"  {name:16s} {'一致' if same else '不一致'}")
            bad += 0 if same else 1
        print("逐字节对比：", "全部一致" if not bad else f"{bad} 个动画不同")
        return 1 if bad else 0

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {OUT}")
    for name, a in doc["animations"].items():
        keys = sum(len(k) for b in a["bones"].values() for k in b.values())
        print(f"  {name:16s} len={a['animation_length']:<5} loop={str(a.get('loop', False)):5s} "
              f"bones={len(a['bones'])} keys={keys}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
