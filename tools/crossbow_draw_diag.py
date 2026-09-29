#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""十字弩「上弦轨迹」色标诊断图：弓部骨骼按功能染色，静弦 / 半拉 / 满弦三帧并排。

为什么需要它：`tools/model_preview.py` 走真实贴图，而这把弩的贴图整体偏暗，缩略图里
弓臂/弦/凸轮糊成一片黑 —— 想判断「弦到底向前还是向后」根本看不清。这里用渲染器的
`tint=` 通道把弓部各组换成高饱和纯色（位置/遮挡/镂空与正常渲染逐像素一致，只换颜色）。

色标：弓臂=绿  凸轮=蓝  弦=红  缆=橙  挂机勾爪=黄  弓座=紫

用法：`python tools/crossbow_draw_diag.py [输出.png] [yaw=90]`
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_preview as mp          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "art", "crossbow")
GEO = os.path.join(ART, "crossbow.geo.json")
ANI = os.path.join(ART, "crossbow.animation.json")
TEX = os.path.join(ART, "crossbow.png")

# 骨骼名关键词 → 颜色（顺序即匹配优先级）
COLORS = (
    ("latch", (255, 235, 60)),
    ("string", (255, 70, 70)),
    ("cable", (255, 170, 40)),
    ("cam", (90, 170, 255)),
    ("limb", (0, 255, 120)),
    ("riser", (200, 120, 255)),
)


def tint_map(geo):
    """骨骼名 → 色标（按 COLORS 的优先级匹配关键词）。"""
    out = {}
    for b in geo["bones"]:
        for key, col in COLORS:
            if key in b["name"]:
                out[b["name"]] = col
                break
    return out


def classify(r, g, b):
    """把染色后的像素归回色标（亮度被明暗乘过，只按色相判）。"""
    if max(r, g, b) < 40:
        return None
    if g >= r and g >= b:
        return "绿 弓臂" if r < g * 0.75 else "黄 勾爪"
    if b >= r and b >= g:
        return "蓝 凸轮"
    return "红/橙 弦/缆"


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ART, "_diag_draw.png")
    yaw = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0
    g = json.load(open(GEO, encoding="utf-8"))["minecraft:geometry"][0]
    clip = json.load(open(ANI, encoding="utf-8"))["animations"]["draw"]
    t_end = max(float(k) for ch in clip["bones"].values() for c in ch.values() for k in c)

    geo, cubes = mp.load_geo(GEO)
    tex = mp.read_png(TEX)
    tint = tint_map(geo)
    print("染色骨骼 %d/%d：%s" % (len(tint), len(geo["bones"]), ", ".join(sorted(tint))))

    tiles = []
    for label, t in (("静止", 0.0), ("半拉", round(t_end / 2, 4)), ("满弦", t_end)):
        tmp = os.path.join(ART, "_diag_%s.png" % label)
        poses = mp.make_poses(geo, ANI, "draw", t) if t else None
        mp.render(geo, cubes, tex, tmp, (yaw,), 820, posemap=poses, tint=tint)
        rw, rh, rpx = mp.read_png(tmp)
        tiles.append((label, rw, rh, rpx))
        os.remove(tmp)
        print("  渲染 %s（t=%.4fs）→ %dx%d" % (label, t, rw, rh))

    # 三帧横向拼接
    W = sum(t[1] for t in tiles)
    H = max(t[2] for t in tiles)
    flat = bytearray()
    for y in range(H):
        for _, w0, h0, px in tiles:
            if y < h0:
                i0 = y * w0 * 4
                flat.extend(px[i0:i0 + w0 * 4])
            else:
                flat += bytes((58, 60, 66, 255)) * w0
    mp.write_png(out, W, H, flat)
    print("%s  %dx%d" % (out, W, H))

    # 各帧染色区域 bbox（供裁图用；帧内坐标 = 全局 x % 560）
    boxes = {}
    for ti, (label, w0, h0, px) in enumerate(tiles):
        for y in range(h0):
            for x in range(w0):
                i = (y * w0 + x) * 4
                k = classify(px[i], px[i + 1], px[i + 2])
                if k:
                    b = boxes.setdefault(k, [10 ** 9, 10 ** 9, -1, -1])
                    b[0] = min(b[0], ti * 560 + x)
                    b[1] = min(b[1], y)
                    b[2] = max(b[2], ti * 560 + x)
                    b[3] = max(b[3], y)
    for k in sorted(boxes):
        b = boxes[k]
        print("  %-12s x %d..%d  y %d..%d（帧内 x %d..%d）"
              % (k, b[0], b[2], b[1], b[3], b[0] % 560, b[2] % 560))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
