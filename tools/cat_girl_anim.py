#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""猫耳娘（cat_girl）动画生成器 —— GeckoLib/Bedrock 1.8.0 动画 JSON。

产物（同一份文件：既灌回 Blockbench 预览，也是模组交付件）：
  art/cat_girl/cat_girl.animation.json
  src/.../assets/apocalypse_zombies/animations/cat_girl.animation.json

旋转方向约定（与 tools/bride_v2.py 一致）：+X = 伸手/抬腿向前，-X = 向后；
躯干/头等 pivot 以下的部件正 X 向前摆，躯干以上（body/head 自身）负 X 为前倾。
所有角度为 22.5° 的整数倍与否不影响动画（动画不受方块旋转步进限制）。

动画清单（与实体端常量一一对应）：
  idle / walk / idle_hold / walk_hold  循环
  equip / attack / hurt / death        单次（loop=false）
  chop / mine                          劳作循环
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = ROOT / "art" / "cat_girl"
RES = ROOT / "src/main/resources/assets/apocalypse_zombies/animations"
NAME = "cat_girl.animation.json"

S = "easeInOutSine"
EI = "easeInQuad"
EO = "easeOutQuad"
EOB = "easeOutBack"

ANIMS = {}


def A(name, length, loop):
    ANIMS[name] = {"length": length, "loop": loop, "bones": {}}
    return ANIMS[name]


def K(anim, bone, channel, t, vec, easing=None):
    b = anim["bones"].setdefault(bone, {}).setdefault(channel, {})
    key = f"{float(t):.1f}"
    b[key] = {"vector": [float(v) for v in vec]}
    if easing and easing != "linear":
        b[key]["easing"] = easing


def rot(anim, bone, frames):
    for f in frames:
        t, x, y, z = f[0], f[1], f[2], f[3]
        K(anim, bone, "rotation", t, (x, y, z), f[4] if len(f) > 4 else None)


def pos(anim, bone, frames):
    for f in frames:
        t, x, y, z = f[0], f[1], f[2], f[3]
        K(anim, bone, "position", t, (x, y, z), f[4] if len(f) > 4 else None)


# ---------------------------------------------------------------- idle
a = A("idle", 2, True)
pos(a, "body", [(0, 0, 0, 0), (1, 0, 0.3, 0, S), (2, 0, 0, 0, S)])
rot(a, "head", [(0, 0, 0, 0), (0.7, 2, 5, 0, S), (1.4, -1, -5, 0, S), (2, 0, 0, 0, S)])
rot(a, "tail1", [(0, -10, -12, 0), (1, -10, 12, 0, S), (2, -10, -12, 0, S)])
rot(a, "tail2", [(0, 0, 6, 0), (1, 0, -6, 0, S), (2, 0, 6, 0, S)])
rot(a, "tail3", [(0, 0, -5, 0), (1, 0, 5, 0, S), (2, 0, -5, 0, S)])
rot(a, "tail4", [(0, 0, 4, 0), (1, 0, -4, 0, S), (2, 0, 4, 0, S)])
rot(a, "right_ear", [(0, 0, 0, 0), (1.05, 0, 0, 0), (1.15, 0, 0, -9, EO), (1.3, 0, 0, 0, S), (2, 0, 0, 0)])
rot(a, "left_ear", [(0, 0, 0, 0), (1.55, 0, 0, 0), (1.65, 0, 0, 9, EO), (1.8, 0, 0, 0, S), (2, 0, 0, 0)])
rot(a, "ahoge", [(0, 0, 0, 0), (0.5, 6, 0, 0, S), (1.5, -4, 0, 0, S), (2, 0, 0, 0, S)])
rot(a, "hair_back", [(0, 0, 0, 0), (1, 2, 0, 0, S), (2, 0, 0, 0, S)])
rot(a, "left_arm", [(0, 0, 0, 1), (1, 2, 0, 1, S), (2, 0, 0, 1, S)])
rot(a, "right_arm", [(0, 0, 0, -1), (1, -2, 0, -1, S), (2, 0, 0, -1, S)])
rot(a, "left_forearm", [(0, 4, 0, 0), (1, 6, 0, 0, S), (2, 4, 0, 0, S)])
rot(a, "right_forearm", [(0, 4, 0, 0), (1, 6, 0, 0, S), (2, 4, 0, 0, S)])
rot(a, "side_lock_l", [(0, 0, 0, 0), (1, 3, 0, 0, S), (2, 0, 0, 0, S)])
rot(a, "side_lock_r", [(0, 0, 0, 0), (1, 3, 0, 0, S), (2, 0, 0, 0, S)])
rot(a, "plush", [(0, 0, 0, 0), (1, 5, 0, 0, S), (2, 0, 0, 0, S)])

# ---------------------------------------------------------------- walk
a = A("walk", 1, True)
rot(a, "left_leg", [(0, 28, 0, 0), (0.5, -28, 0, 0, S), (1, 28, 0, 0, S)])
rot(a, "right_leg", [(0, -28, 0, 0), (0.5, 28, 0, 0, S), (1, -28, 0, 0, S)])
rot(a, "left_shin", [(0, -4, 0, 0), (0.25, -20, 0, 0, S), (0.5, -4, 0, 0, S), (0.75, -28, 0, 0, S), (1, -4, 0, 0, S)])
rot(a, "right_shin", [(0, -4, 0, 0), (0.25, -28, 0, 0, S), (0.5, -4, 0, 0, S), (0.75, -20, 0, 0, S), (1, -4, 0, 0, S)])
rot(a, "left_foot", [(0, 4, 0, 0), (0.5, -6, 0, 0, S), (1, 4, 0, 0, S)])
rot(a, "right_foot", [(0, -6, 0, 0), (0.5, 4, 0, 0, S), (1, -6, 0, 0, S)])
rot(a, "left_arm", [(0, -24, 0, 0), (0.5, 24, 0, 0, S), (1, -24, 0, 0, S)])
rot(a, "right_arm", [(0, 24, 0, 0), (0.5, -24, 0, 0, S), (1, 24, 0, 0, S)])
rot(a, "left_forearm", [(0, 14, 0, 0), (0.5, 6, 0, 0, S), (1, 14, 0, 0, S)])
rot(a, "right_forearm", [(0, 6, 0, 0), (0.5, 14, 0, 0, S), (1, 6, 0, 0, S)])
pos(a, "body", [(0, 0, 0, 0), (0.25, 0, 0.35, 0, S), (0.5, 0, 0, 0, S), (0.75, 0, 0.35, 0, S), (1, 0, 0, 0, S)])
rot(a, "body", [(0, -3, 0, 0), (1, -3, 0, 0)])
rot(a, "head", [(0, 3, -3, 0), (0.5, 3, 3, 0, S), (1, 3, -3, 0, S)])
rot(a, "tail1", [(0, -16, -10, 0), (0.5, -16, 10, 0, S), (1, -16, -10, 0, S)])
rot(a, "tail2", [(0, 0, 8, 0), (0.5, 0, -8, 0, S), (1, 0, 8, 0, S)])
rot(a, "tail3", [(0, 0, -6, 0), (0.5, 0, 6, 0, S), (1, 0, -6, 0, S)])
rot(a, "hair_back", [(0, -5, 0, 0), (0.5, 2, 0, 0, S), (1, -5, 0, 0, S)])
rot(a, "ahoge", [(0, 8, 0, 0), (0.5, -6, 0, 0, S), (1, 8, 0, 0, S)])
rot(a, "plush", [(0, -8, 0, 0), (0.5, 8, 0, 0, S), (1, -8, 0, 0, S)])
rot(a, "left_ribbon", [(0, 4, 0, 0), (0.5, -4, 0, 0, S), (1, 4, 0, 0, S)])
rot(a, "right_ribbon", [(0, -4, 0, 0), (0.5, 4, 0, 0, S), (1, -4, 0, 0, S)])

# ---------------------------------------------------------------- idle_hold
a = A("idle_hold", 2, True)
rot(a, "right_arm", [(0, 52, 0, -4), (1, 49, 0, -4, S), (2, 52, 0, -4, S)])
rot(a, "right_forearm", [(0, 38, 0, 0), (1, 41, 0, 0, S), (2, 38, 0, 0, S)])
pos(a, "body", [(0, 0, 0, 0), (1, 0, 0.3, 0, S), (2, 0, 0, 0, S)])
rot(a, "head", [(0, 0, 0, 0), (0.7, 0, 5, 0, S), (1.4, 0, -5, 0, S), (2, 0, 0, 0, S)])
rot(a, "tail1", [(0, -10, -12, 0), (1, -10, 12, 0, S), (2, -10, -12, 0, S)])
rot(a, "tail2", [(0, 0, 6, 0), (1, 0, -6, 0, S), (2, 0, 6, 0, S)])
rot(a, "left_arm", [(0, 0, 0, 1), (1, 2, 0, 1, S), (2, 0, 0, 1, S)])
rot(a, "left_forearm", [(0, 4, 0, 0), (1, 6, 0, 0, S), (2, 4, 0, 0, S)])
rot(a, "right_ear", [(0, 0, 0, 0), (1.2, 0, 0, -9, EO), (1.4, 0, 0, 0, S), (2, 0, 0, 0)])
rot(a, "ahoge", [(0, 0, 0, 0), (1, 5, 0, 0, S), (2, 0, 0, 0, S)])

# ---------------------------------------------------------------- walk_hold
a = A("walk_hold", 1, True)
rot(a, "right_arm", [(0, 52, 0, -4), (0.25, 49, 0, -4, S), (0.75, 53, 0, -4, S), (1, 52, 0, -4, S)])
rot(a, "right_forearm", [(0, 38, 0, 0), (0.5, 41, 0, 0, S), (1, 38, 0, 0, S)])
rot(a, "left_leg", [(0, 28, 0, 0), (0.5, -28, 0, 0, S), (1, 28, 0, 0, S)])
rot(a, "right_leg", [(0, -28, 0, 0), (0.5, 28, 0, 0, S), (1, -28, 0, 0, S)])
rot(a, "left_shin", [(0, -4, 0, 0), (0.25, -20, 0, 0, S), (0.5, -4, 0, 0, S), (0.75, -28, 0, 0, S), (1, -4, 0, 0, S)])
rot(a, "right_shin", [(0, -4, 0, 0), (0.25, -28, 0, 0, S), (0.5, -4, 0, 0, S), (0.75, -20, 0, 0, S), (1, -4, 0, 0, S)])
rot(a, "left_arm", [(0, -24, 0, 0), (0.5, 24, 0, 0, S), (1, -24, 0, 0, S)])
rot(a, "left_forearm", [(0, 14, 0, 0), (0.5, 6, 0, 0, S), (1, 14, 0, 0, S)])
pos(a, "body", [(0, 0, 0, 0), (0.25, 0, 0.35, 0, S), (0.5, 0, 0, 0, S), (0.75, 0, 0.35, 0, S), (1, 0, 0, 0, S)])
rot(a, "body", [(0, -3, 0, 0), (1, -3, 0, 0)])
rot(a, "tail1", [(0, -16, -10, 0), (0.5, -16, 10, 0, S), (1, -16, -10, 0, S)])
rot(a, "tail2", [(0, 0, 8, 0), (0.5, 0, -8, 0, S), (1, 0, 8, 0, S)])
rot(a, "hair_back", [(0, -5, 0, 0), (0.5, 2, 0, 0, S), (1, -5, 0, 0, S)])
rot(a, "ahoge", [(0, 8, 0, 0), (0.5, -6, 0, 0, S), (1, 8, 0, 0, S)])
rot(a, "plush", [(0, -8, 0, 0), (0.5, 8, 0, 0, S), (1, -8, 0, 0, S)])

# ---------------------------------------------------------------- equip（拿取武器/工具）
a = A("equip", 0.55, False)
rot(a, "right_arm", [(0, 0, 0, 0), (0.18, 72, 0, 0, EOB), (0.4, 48, 0, -4, S), (0.55, 52, 0, -4)])
rot(a, "right_forearm", [(0, 0, 0, 0), (0.18, 30, 0, 0, EO), (0.55, 38, 0, 0, S)])
rot(a, "head", [(0, 0, 0, 0), (0.22, -10, 0, 0, S), (0.5, 0, 0, 0, S)])
pos(a, "body", [(0, 0, 0, 0), (0.15, 0, 0.2, 0, EO), (0.55, 0, 0, 0, S)])
rot(a, "ahoge", [(0, 0, 0, 0), (0.18, -14, 0, 0, EO), (0.55, 0, 0, 0, S)])

# ---------------------------------------------------------------- attack（打怪）
a = A("attack", 0.45, False)
rot(a, "right_arm", [(0, 52, 0, -4), (0.1, -92, 0, -4, EO), (0.22, 58, 0, -4, EI), (0.34, 52, 0, -4, EO), (0.45, 52, 0, -4)])
rot(a, "right_forearm", [(0, 38, 0, 0), (0.1, -25, 0, 0, EO), (0.22, 46, 0, 0, EI), (0.45, 38, 0, 0, EO)])
rot(a, "left_arm", [(0, 0, 0, 0), (0.1, -15, 0, 0, EO), (0.45, 0, 0, 0, EO)])
rot(a, "body", [(0, 0, 0, 0), (0.1, 4, 10, 0, EO), (0.22, -10, -14, 0, EI), (0.34, 0, 0, 0, EO)])
rot(a, "head", [(0, 0, 0, 0), (0.1, 0, 6, 0, EO), (0.22, 0, -7, 0, EI), (0.34, 0, 0, 0, EO)])
rot(a, "ahoge", [(0, 0, 0, 0), (0.1, 14, 0, 0, EO), (0.22, -12, 0, 0, EI), (0.45, 0, 0, 0, S)])
rot(a, "left_leg", [(0, 0, 0, 0), (0.22, 10, 0, 0, EI), (0.45, 0, 0, 0, EO)])
rot(a, "right_leg", [(0, 0, 0, 0), (0.22, -10, 0, 0, EI), (0.45, 0, 0, 0, EO)])

# ---------------------------------------------------------------- chop（伐木）
a = A("chop", 0.55, True)
rot(a, "right_arm", [(0, -118, 0, -6), (0.22, 42, 0, -6, EI), (0.32, 30, 0, -6, EO), (0.55, -118, 0, -6, EO)])
rot(a, "right_forearm", [(0, -30, 0, 0), (0.22, 35, 0, 0, EI), (0.55, -30, 0, 0, EO)])
rot(a, "left_arm", [(0, -108, 0, 6), (0.22, 40, 0, 6, EI), (0.32, 28, 0, 6, EO), (0.55, -108, 0, 6, EO)])
rot(a, "left_forearm", [(0, -26, 0, 0), (0.22, 32, 0, 0, EI), (0.55, -26, 0, 0, EO)])
rot(a, "body", [(0, -5, 0, 0), (0.22, -26, 0, 0, EI), (0.55, -5, 0, 0, EO)])
rot(a, "head", [(0, 0, 0, 0), (0.22, -10, 0, 0, EI), (0.55, 0, 0, 0, EO)])
rot(a, "left_leg", [(0, 9, 0, 0), (0.55, 9, 0, 0)])
rot(a, "right_leg", [(0, -9, 0, 0), (0.55, -9, 0, 0)])
rot(a, "ahoge", [(0, 0, 0, 0), (0.22, -16, 0, 0, EI), (0.55, 0, 0, 0, EO)])
rot(a, "hair_back", [(0, 0, 0, 0), (0.22, -8, 0, 0, EI), (0.55, 0, 0, 0, EO)])

# ---------------------------------------------------------------- mine（挖矿）
a = A("mine", 0.6, True)
rot(a, "right_arm", [(0, -105, 0, -6), (0.3, 38, 0, -6, EI), (0.6, -105, 0, -6, EO)])
rot(a, "right_forearm", [(0, -24, 0, 0), (0.3, 30, 0, 0, EI), (0.6, -24, 0, 0, EO)])
rot(a, "left_arm", [(0, 26, 0, 4), (0.6, 26, 0, 4)])
rot(a, "left_forearm", [(0, 22, 0, 0), (0.6, 22, 0, 0)])
rot(a, "body", [(0, -5, 0, 0), (0.3, -22, 0, 0, EI), (0.6, -5, 0, 0, EO)])
rot(a, "head", [(0, 0, 0, 0), (0.3, -8, 0, 0, EI), (0.6, 0, 0, 0, EO)])
rot(a, "ahoge", [(0, 0, 0, 0), (0.3, -14, 0, 0, EI), (0.6, 0, 0, 0, EO)])

# ---------------------------------------------------------------- hurt
a = A("hurt", 0.3, False)
rot(a, "body", [(0, 0, 0, 0), (0.08, 14, 0, 6, EO), (0.18, -4, 0, -2, S), (0.3, 0, 0, 0, S)])
rot(a, "head", [(0, 0, 0, 0), (0.1, 12, 0, 0, EO), (0.2, -3, 0, 0, S), (0.3, 0, 0, 0, S)])
rot(a, "right_arm", [(0, 0, 0, 0), (0.08, -32, 0, -10, EO), (0.3, 0, 0, 0, S)])
rot(a, "left_arm", [(0, 0, 0, 0), (0.08, -32, 0, 10, EO), (0.3, 0, 0, 0, S)])
rot(a, "ahoge", [(0, 0, 0, 0), (0.1, 16, 0, 0, EO), (0.3, 0, 0, 0, S)])
rot(a, "tail1", [(0, -10, 0, 0), (0.1, 14, 0, 0, EO), (0.3, -10, 0, 0, S)])

# ---------------------------------------------------------------- death
a = A("death", 1.4, False)
rot(a, "body", [(0, 0, 0, 0), (0.15, -15, 0, 0, EI), (0.6, -85, 0, 0, EI), (1.4, -85, 0, 0)])
pos(a, "body", [(0, 0, 0, 0), (0.6, 0, -4, 0, EI), (1.4, 0, -4, 0)])
rot(a, "head", [(0, 0, 0, 0), (0.6, -15, 0, 0, EI), (1.4, -10, 0, 0)])
rot(a, "right_arm", [(0, 0, 0, -1), (0.6, 34, 0, -14, EI), (1.4, 38, 0, -16)])
rot(a, "left_arm", [(0, 0, 0, 1), (0.6, 28, 0, 14, EI), (1.4, 32, 0, 16)])
rot(a, "left_leg", [(0, 0, 0, 0), (0.4, -6, 0, -10, S), (1.4, -8, 0, -12)])
rot(a, "right_leg", [(0, 0, 0, 0), (0.4, -6, 0, 10, S), (1.4, -8, 0, 12)])
rot(a, "left_shin", [(0, 0, 0, 0), (0.6, -18, 0, 0, EI), (1.4, -20, 0, 0)])
rot(a, "right_shin", [(0, 0, 0, 0), (0.6, -18, 0, 0, EI), (1.4, -20, 0, 0)])
rot(a, "tail1", [(0, -12, 0, 0), (0.6, 24, -10, 0, EI), (1.4, 28, -12, 0)])
rot(a, "tail2", [(0, 0, 0, 0), (0.8, 0, -14, 0, EI), (1.4, 0, -16, 0)])
rot(a, "ahoge", [(0, 0, 0, 0), (0.5, -20, 0, 0, EI), (1.4, -14, 0, 0)])


def build():
    out = {"format_version": "1.8.0", "animations": {}}
    for name, data in ANIMS.items():
        entry = {"animation_length": data["length"]}
        if data["loop"]:
            entry["loop"] = True
        bones = {}
        for bone, channels in data["bones"].items():
            if not channels:
                continue
            bones[bone] = {}
            for chan, keys in channels.items():
                bones[bone][chan] = {t: v for t, v in sorted(keys.items(), key=lambda kv: float(kv[0]))}
        entry["bones"] = bones
        out["animations"][name] = entry
    text = json.dumps(out, ensure_ascii=False, indent="\t")
    ART.mkdir(parents=True, exist_ok=True)
    (ART / NAME).write_text(text, encoding="utf-8")
    RES.mkdir(parents=True, exist_ok=True)
    (RES / NAME).write_text(text, encoding="utf-8")
    total = sum(len(c) for a in ANIMS.values() for c in a["bones"].values())
    print(f"animations -> {ART / NAME} & {RES / NAME} ({len(ANIMS)} clips, {total} channels)")
    for n, d in ANIMS.items():
        print(f"  {n}: {d['length']}s {'loop' if d['loop'] else 'once'} bones={len(d['bones'])}")


if __name__ == "__main__":
    build()
