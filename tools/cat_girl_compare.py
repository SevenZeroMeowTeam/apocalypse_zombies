"""参考图 vs 模型渲染 并排对照图（人眼核验用）。
用法: py tools/cat_girl_compare.py [--render art/cat_girl/preview.png] [--out art/cat_girl/compare.png]
裁剪两边到"角色外接框"后统一高度并排；参考图放左，模型 4 视图放右。
"""
import argparse
import collections
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
REF = Path(r"C:\Users\Administrator\Downloads\Meshy_AI_straight_standing_cat_girl_front.png")
H = 520


def bbox_of(im, bg=None, tol=26, min_run=3):
    im = im.convert("RGB")
    W, Hh = im.size
    px = im.load()
    if bg is None:
        bg = collections.Counter([px[2, 2], px[W - 3, 2], px[2, Hh - 3], px[W - 3, Hh - 3]]).most_common(1)[0][0]

    def fg(c):
        return abs(c[0] - bg[0]) + abs(c[1] - bg[1]) + abs(c[2] - bg[2]) > tol

    rows = {}
    for y in range(Hh):
        xs = [x for x in range(W) if fg(px[x, y])]
        if len(xs) >= min_run:
            rows[y] = (min(xs), max(xs))
    ys = sorted(rows)
    return (min(rows[y][0] for y in ys), ys[0], max(rows[y][1] for y in ys) + 1, ys[-1] + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", default=str(ROOT / "art/cat_girl/preview.png"))
    ap.add_argument("--out", default=str(ROOT / "art/cat_girl/compare.png"))
    ap.add_argument("--panel", type=int, default=0, help="渲染图里取第几块(0 起)；默认取 front")
    a = ap.parse_args()

    ref = Image.open(REF)
    rb = bbox_of(ref)
    ref_c = ref.crop(rb)

    ren = Image.open(a.render)
    # 渲染图是 N 块并排（块间有 6px 白缝），按缝切
    panes = 4
    gap = 6
    pw = (ren.width - gap * (panes - 1)) // panes
    x0 = a.panel * (pw + gap)
    pane = ren.crop((x0, 0, x0 + pw, ren.height))
    pb = bbox_of(pane, bg=(246, 244, 247))
    pane_c = pane.crop(pb)

    def scale(im):
        r = H / im.height
        return im.resize((max(1, int(im.width * r)), H), Image.LANCZOS)

    ref_s, pane_s = scale(ref_c), scale(pane_c)
    W = ref_s.width + pane_s.width + 24
    out = Image.new("RGB", (W, H), (255, 255, 255))
    out.paste(ref_s, (0, 0))
    out.paste(pane_s, (ref_s.width + 24, 0))
    out.save(a.out)
    print(f"{a.out} {out.size}  参考 {ref_c.size}→{ref_s.size}  模型 {pane_c.size}→{pane_s.size}")
    print(f"参考角色框 {rb}  模型角色框 {pb}（面板 {pane.size}）")


if __name__ == "__main__":
    main()
