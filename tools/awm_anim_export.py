#!/usr/bin/env python3
"""Blockbench keyframe dump -> GeckoLib animation.json (bedrock 1.8.0 flavour).

Input : art/awm/_anim_raw.json   (written by tools/awm_bb_anim.js via MCP risky_eval)
Output: art/awm/awm.animation.json

GeckoLib accepts the 1.8.0 bedrock animation schema verbatim:
  - a channel value is either [x, y, z]           -> linear interpolation
  - or {"post": [x, y, z], "lerp_mode": "<mode>"} -> keep the Blockbench curve
Position values stay in Blockbench model units (16u = 1 block); GeckoLib divides by 16.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "art", "awm", "_anim_raw.json")
OUT = os.path.join(HERE, "..", "art", "awm", "awm.animation.json")

# Blockbench interpolation -> GeckoLib lerp_mode. '' / 'linear' -> plain array.
LERP = {
    "catmullrom": "catmullrom",
    "smooth": "catmullrom",
    "bezier": "catmullrom",
    "easeinout": "catmullrom",
    "step": "step",
}


def fmt_time(t):
    return f"{float(t):.3f}".rstrip("0").rstrip(".") or "0"


def main():
    with open(RAW, "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    animations = {}
    for a in raw["anims"]:
        bones = {}
        for bone, channels in a["bones"].items():
            out_bone = {}
            for chan in ("rotation", "position", "scale"):
                keys = channels.get(chan)
                if not keys:
                    continue
                out_chan = {}
                for time in sorted(keys, key=lambda k: float(k)):
                    entry = keys[time]
                    vals = [round(float(v), 4) for v in entry["v"]]
                    lerp = LERP.get(entry.get("i", ""))
                    out_chan[fmt_time(time)] = (
                        {"post": vals, "lerp_mode": lerp} if lerp else vals
                    )
                out_bone[chan] = out_chan
            if out_bone:
                bones[bone] = out_bone
        animations[a["name"]] = {
            "loop": a["loop"] != "once",
            "animation_length": round(float(a["length"]), 3),
            "bones": bones,
        }

    doc = {"format_version": "1.8.0", "animations": animations}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"wrote {os.path.normpath(OUT)}")
    for name, a in animations.items():
        chans = sum(len(c) for c in a["bones"].values())
        keys = sum(len(k) for b in a["bones"].values() for k in b.values())
        print(
            f"  {name:12s} len={a['animation_length']:<5} loop={str(a['loop']):5s} "
            f"bones={len(a['bones'])} channels={chans} keys={keys}"
        )


if __name__ == "__main__":
    main()
