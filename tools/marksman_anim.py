#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""骸骨射手动画驱动 + 导出：

  1. 把 tools/marksman_bb_anim.js 送进 Blockbench 跑（risky_eval，注释先剥），
     它会建 idle / walk / shoot / skill_bone_lock 四段并把关键帧 dump 到 art/marksman/_anim_raw.json；
  2. 转成 GeckoLib 吃的 bedrock 1.8.0 animation.json，落 art 与 src 两处；
  3. 跑闸门：clip 名与 Java ANIM_* 一致、禁 scale 通道、技能命中帧（1.7s）存在、时长正确。

用法：python tools/marksman_anim.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import bbmcp_call as bb  # noqa: E402

ART = ROOT / "art" / "marksman"
SRC = ROOT / "src" / "main" / "resources" / "assets" / "apocalypse_zombies"
RAW = ART / "_anim_raw.json"
OUT_ART = ART / "marksman_skeleton.animation.json"
OUT_SRC = SRC / "animations" / "marksman_skeleton.animation.json"

MODEL = "marksman_skeleton"
# clip 名 → (时长, 是否循环)。必须与 Java 的 ANIM_IDLE/ANIM_WALK/ANIM_SHOOT/ANIM_LOCK 常量逐字一致。
EXPECT = {
    "idle": (3.0, True),
    "walk": (1.0, True),
    "shoot": (0.9, False),
    "skill_bone_lock": (2.1, False),
}
IMPACT_TIME = 1.7           # EliteAbility.BONE_LOCK 的 impactTick=34 → 34/20 s
IMPACT_BONES = ("arm_l", "forearm_r", "chest")

LERP = {
    "catmullrom": "catmullrom",
    "smooth": "catmullrom",
    "bezier": "catmullrom",
    "easeinout": "catmullrom",
    "step": "step",
}


def fmt_time(t):
    return f"{float(t):.3f}".rstrip("0").rstrip(".") or "0"


def run_bb() -> dict:
    src = (HERE / "marksman_bb_anim.js").read_text(encoding="utf-8")
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    sid = bb.handshake()
    raw = bb.text_of(bb.call(sid, "risky_eval", {"code": src}))
    (ROOT / "build" / "marksman_anim_out.json").write_text(raw, encoding="utf-8")
    doc = json.loads(raw)
    res = doc.get("result", doc)
    if isinstance(res, str):
        res = json.loads(res)
    return res


def convert(raw: dict) -> dict:
    anims = {}
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
                    out_chan[fmt_time(time)] = {"post": vals, "lerp_mode": lerp} if lerp else vals
                out_bone[chan] = out_chan
            if out_bone:
                bones[bone] = out_bone
        anims[a["name"]] = {
            "loop": a["loop"] != "once",
            "animation_length": round(float(a["length"]), 3),
            "bones": bones,
        }
    return {"format_version": "1.8.0", "animations": anims}


def main() -> int:
    res = run_bb()
    if not isinstance(res, dict):
        print("FAIL：Blockbench 回报不是对象：", str(res)[:300])
        return 1
    for w in res.get("warnings", []):
        print("warn:", w)
    for s in res.get("steps", []):
        print("step:", s)
    if res.get("scale_channels"):
        print(f"FAIL：Blockbench 里有 {res['scale_channels']} 个 scale 关键帧（本项目禁 scale）")
        return 1
    if not RAW.exists():
        print(f"FAIL：没拿到关键帧 dump（{RAW}），看上面的 warnings")
        return 1

    raw = json.loads(RAW.read_text(encoding="utf-8"))
    doc = convert(raw)
    anims = doc["animations"]

    bad = []
    if set(anims) != set(EXPECT):
        bad.append(f"clip 集合不对：{sorted(anims)} != {sorted(EXPECT)}")
    for name, (length, loop) in EXPECT.items():
        a = anims.get(name)
        if not a:
            continue
        if abs(a["animation_length"] - length) > 1e-6:
            bad.append(f"{name} 时长 {a['animation_length']} != {length}")
        if a["loop"] != loop:
            bad.append(f"{name} loop={a['loop']} != {loop}")
        for bone, chans in a["bones"].items():
            if "scale" in chans:
                bad.append(f"{name}.{bone} 有 scale 通道")
    sk = anims.get("skill_bone_lock", {}).get("bones", {})
    for bone in IMPACT_BONES:
        keys = sk.get(bone, {}).get("rotation", {})
        if fmt_time(IMPACT_TIME) not in keys:
            bad.append(f"技能在 {IMPACT_TIME}s 没有 {bone} 的关键帧（命中帧必须与 impactTick=34 对齐）")
    if bad:
        print("FAIL：")
        for b in bad:
            print("  -", b)
        return 1

    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    OUT_ART.write_text(text, encoding="utf-8")
    OUT_SRC.parent.mkdir(parents=True, exist_ok=True)
    OUT_SRC.write_text(text, encoding="utf-8")

    print()
    print(f"已落盘  {OUT_ART}")
    print(f"        {OUT_SRC}")
    for name, a in anims.items():
        chans = sum(len(c) for c in a["bones"].values())
        keys = sum(len(k) for b in a["bones"].values() for k in b.values())
        print(f"  {name:16s} len={a['animation_length']:<4} loop={str(a['loop']):5s} 骨={len(a['bones']):2d} 通道={chans:2d} 关键帧={keys}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
