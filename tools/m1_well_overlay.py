# -*- coding: utf-8 -*-
"""把漏夹井的新旧标定叠加到真机侧视参考图上（逐幅标定）。

ref_m1_side.png 是上下两幅方向相反的照片合成图：
  · 以"亮度 > 45"取枪身剪影（背景是黑底，四角取样会取到白边，不可用）；
  · 白色边框带 = 整行/整列几乎全亮，用比例上下限剔掉；
  · 每幅单独取列范围 → px/mm（真机全长 1105mm = 43.5"）；
  · 每幅单独判定枪口端（两端各 5% 宽度，平均高度小的那端是枪口：枪管细、枪托厚）。
"""
import json
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
REF = ROOT / "art/m1garand/ref_m1_side.png"
GEO = ROOT / "art/m1garand/m1_garand.geo.json"
OUT = ROOT / "art/m1garand/well_fix_overlay.png"

MM = 62.5        # 1 Blockbench 单位 = 62.5mm
Z0 = -13.60      # 枪口在 geo 空间的 z
GUN_MM = 1105.0  # 真机全长 43.5"


def gun_mask(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    return a, a.mean(axis=2) > 45


def find_panels(mask):
    H, W = mask.shape
    per_row = mask.sum(axis=1)
    ok = (per_row > 120) & (per_row < 0.85 * W)
    panels, start = [], None
    for y in range(H):
        if ok[y] and start is None:
            start = y
        elif not ok[y] and start is not None:
            if y - start > 40:
                panels.append((start, y))
            start = None
    if start is not None and H - start > 40:
        panels.append((start, H))
    return panels


def panel_geom(mask, pa, pb):
    sub = mask[pa:pb]
    frac = sub.mean(axis=0)
    cand = [x for x in range(mask.shape[1]) if 0.005 < frac[x] < 0.9]
    x0, x1 = cand[0], cand[-1]
    span = x1 - x0 + 1
    q = max(1, span // 20)
    left_h = sub[:, x0:x0 + q].sum() / q
    right_h = sub[:, x1 - q:x1].sum() / q
    muzzle_left = left_h < right_h

    def mm_to_px(mm):
        f = mm / GUN_MM
        return x0 + f * span if muzzle_left else x1 - f * span

    return x0, x1, span, muzzle_left, mm_to_px


def main():
    a, mask = gun_mask(REF)
    H, W = mask.shape
    panels = find_panels(mask)
    print("检测到 %d 幅：" % len(panels), panels)

    geo = json.loads(GEO.read_text(encoding="utf-8"))
    bones = {b["name"]: b for b in geo["minecraft:geometry"][0]["bones"]}

    im = Image.open(REF).convert("RGBA")
    dd = ImageDraw.Draw(im, "RGBA")
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 21)
        fsm = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)
    except Exception:
        font = fsm = ImageFont.load_default()

    bands = [
        (519, 618, (235, 40, 40, 55), (235, 40, 40, 240), "旧井 519-618mm（错，靠前）"),
        (601, 700, (30, 210, 90, 65), (15, 150, 60, 250), "新井 601-700mm（本次修正）"),
    ]
    anchors = [
        (610, (255, 130, 0, 235), "闭锁面 610"),
        (700, (0, 170, 255, 235), "拉机柄/后照门座 700"),
    ]

    for (pa, pb) in panels:
        x0, x1, span, muzzle_left, mm_to_px = panel_geom(mask, pa, pb)
        top, bot = pa + 1, pb - 1
        for mm_a, mm_b, fill, line, label in bands:
            xa, xb = sorted((mm_to_px(mm_a), mm_to_px(mm_b)))
            dd.rectangle([xa, top, xb, bot], fill=fill)
            dd.line([xa, top, xa, bot], fill=line, width=3)
            dd.line([xb, top, xb, bot], fill=line, width=3)
        xa, _ = sorted((mm_to_px(519), mm_to_px(618)))
        dd.text((xa + 6, top + 6), bands[0][4], font=fsm, fill=bands[0][3],
                stroke_width=3, stroke_fill=(0, 0, 0, 220))
        xa, _ = sorted((mm_to_px(601), mm_to_px(700)))
        dd.text((xa + 6, top + 30), bands[1][4], font=fsm, fill=bands[1][3],
                stroke_width=3, stroke_fill=(0, 0, 0, 220))
        for mm, col, label in anchors:
            x = mm_to_px(mm)
            dd.line([x, top, x, bot], fill=col, width=2)
            dd.text((x + 6, top + 54), label, font=fsm, fill=col, stroke_width=3,
                    stroke_fill=(0, 0, 0, 220))

        y = top + 82
        for name, col, label in (("clip_in", (255, 240, 0, 255), "漏夹"),
                                 ("cover", (255, 90, 255, 255), "漏夹盖"),
                                 ("casing", (0, 255, 255, 255), "弹壳")):
            cs = bones[name].get("cubes", [])
            zlo = min(c["origin"][2] for c in cs)
            zhi = max(c["origin"][2] + c["size"][2] for c in cs)
            mlo, mhi = (zlo - Z0) * MM, (zhi - Z0) * MM
            xa, xb = sorted((mm_to_px(mlo), mm_to_px(mhi)))
            dd.line([xa, y, xb, y], fill=col, width=7)
            dd.text((xa, y + 8), "%.0f-%.0fmm %s" % (mlo, mhi, label), font=fsm, fill=col,
                    stroke_width=3, stroke_fill=(0, 0, 0, 220))
            y += 36
        print("  行 %d..%d 列 %d..%d span=%d px (%.3f px/mm) 枪口在%s"
              % (pa, pb, x0, x1, span, span / GUN_MM, "左" if muzzle_left else "右"))

    legend = [("旧井 519-618mm（错误位，整体靠前一个井长）", (235, 40, 40, 255)),
              ("新井 601-700mm（真机标定：前壁=闭锁面，后壁=拉机柄前沿）", (15, 150, 60, 255)),
              ("闭锁面 610mm（枪管 24\"）", (255, 130, 0, 255)),
              ("拉机柄/后照门座 700mm（模型内可自证锚点）", (0, 170, 255, 255)),
              ("照片比例按全长 1105mm（43.5\"）定标，标定误差 ±1%（±11mm）", (200, 200, 200, 255))]
    y = H - 28 * len(legend) - 6
    for text, col in legend:
        dd.rectangle([10, y + 6, 34, y + 20], fill=col)
        dd.text((42, y), text, font=font, fill=(255, 255, 255, 255), stroke_width=3,
                stroke_fill=(0, 0, 0, 235))
        y += 28

    im.convert("RGB").save(OUT, quality=93)
    print("→", OUT)


if __name__ == "__main__":
    main()
