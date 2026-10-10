"""猫耳娘：参考图 vs 模型（spec）正视图轮廓对照。

把两边都归一化成"高度分数"，逐带比较宽度占比，直接给可改建模的硬数字。
用法:
  py tools/cat_girl_silhouette.py                      # 参考图 vs art/cat_girl/cat_girl_spec.json
  py tools/cat_girl_silhouette.py --spec other.json
"""
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
REF = Path(r"C:\Users\Administrator\Downloads\Meshy_AI_straight_standing_cat_girl_front.png")
SPEC = ROOT / "art/cat_girl/cat_girl_spec.json"

GW, GH = 46, 42  # 字符网格


def ref_mask(ref_path=REF):
    """返回 (mask[GH][GW] bool, 每行宽度占比列表, 关键色)"""
    im = Image.open(ref_path).convert("RGB")
    W, H = im.size
    px = im.load()
    import collections

    bg = collections.Counter([px[2, 2], px[W - 3, 2], px[2, H - 3], px[W - 3, H - 3]]).most_common(1)[0][0]

    def fg(c):
        return abs(c[0] - bg[0]) + abs(c[1] - bg[1]) + abs(c[2] - bg[2]) > 26

    # 逐行前景（要求 >=3 像素，去掉噪点）
    rows = {}
    for y in range(H):
        xs = [x for x in range(W) if fg(px[x, y])]
        if len(xs) >= 3:
            rows[y] = (min(xs), max(xs), xs)
    ys = sorted(rows)
    top, bot = ys[0], ys[-1]
    ch = bot - top + 1
    # 水平范围
    x0 = min(rows[y][0] for y in ys)
    x1 = max(rows[y][1] for y in ys)
    grid = [[False] * GW for _ in range(GH)]
    widths = []
    for iy in range(GH):
        rel = 1 - (iy + 0.5) / GH  # 1=头顶
        y = bot - int(rel * ch)
        r = rows.get(min(max(y, top), bot))
        if not r:
            widths.append(0.0)
            continue
        widths.append((r[1] - r[0]) / ch)
        a, b = r[0], r[1]
        for ix in range(GW):
            cx = x0 + (ix + 0.5) * (x1 - x0) / GW
            grid[iy][ix] = a <= cx <= b
    return grid, widths, (top, bot, x0, x1), ch, im


def spec_mask(spec_path=SPEC):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    ys0 = []
    ys1 = []
    polys = []
    for c in spec["cubes"]:
        f, s = c["from"], c["size"]
        ys0.append(f[1])
        ys1.append(f[1] + s[1])
        polys.append((f[0], f[0] + s[0], f[1], f[1] + s[1]))
    top, bot = min(ys0), max(ys1)
    ch = bot - top
    x0 = min(p[0] for p in polys)
    x1 = max(p[1] for p in polys)
    grid = [[False] * GW for _ in range(GH)]
    widths = []
    for iy in range(GH):
        rel = 1 - (iy + 0.5) / GH
        y = top + rel * ch
        # 该高度上所有跨过的方块 → x 区间并集
        seg = [(a, b) for a, b, c0, c1 in polys if c0 <= y <= c1]
        if not seg:
            widths.append(0.0)
            continue
        lo = min(s[0] for s in seg)
        hi = max(s[1] for s in seg)
        widths.append((hi - lo) / ch)
        for ix in range(GW):
            cx = x0 + (ix + 0.5) * (x1 - x0) / GW
            grid[iy][ix] = lo <= cx <= hi
    return grid, widths, (top, bot, x0, x1), ch


def show(g_left, g_right, lw=GW, rw=GW):
    print("  参考图" + " " * (lw - 6) + "   |   spec 模型")
    for iy in range(GH):
        l = "".join("#" if v else "." for v in g_left[iy])
        r = "".join("#" if v else "." for v in g_right[iy])
        print(f"{l} | {r}")


def main():
    spec_path = SPEC
    if "--spec" in sys.argv:
        spec_path = Path(sys.argv[sys.argv.index("--spec") + 1])
    gm, wm, bm, chm, im = ref_mask()
    gs, ws, bs, chs = spec_mask(spec_path)
    print(f"参考图: 高 {chm}px  x[{bm[2]},{bm[3]}] 宽/高={ (bm[3]-bm[2])/chm:.3f}")
    print(f"模型  : 高 {chs}u  x[{bs[2]:.1f},{bs[3]:.1f}] 宽/高={(bs[3]-bs[2])/chs:.3f}  ({spec_path})")
    print(f"模型高 {chs}u = {chs/16:.2f} 格；参考图 1u = {chm/chs:.1f}px")
    show(gm, ws if False else gs)
    print("\n[逐带宽度占比] 相对高度 | 参考 | 模型 | 差")
    for iy in range(GH):
        rel = 1 - (iy + 0.5) / GH
        d = ws[iy] - wm[iy]
        flag = "  <<<" if abs(d) > 0.035 else ""
        print(f"  {rel:5.3f} | {wm[iy]:5.3f} | {ws[iy]:5.3f} | {d:+6.3f}{flag}")


if __name__ == "__main__":
    main()
