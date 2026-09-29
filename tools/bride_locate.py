# -*- coding: utf-8 -*-
"""在连拍帧里自动锁定美女僵尸（暖白色婚纱）并放大裁切。

判据：婚纱是**暖白**（R 明显高于 B），洞穴石墙/天空是中性灰蓝（R≈B），
草地是高饱和绿。所以 `R > 150 and R > B + 12 and R >= G` 基本只命中婚纱、
头纱、袖子 —— 比单纯「亮」稳得多（早期用亮度阈值时，亮石墙把信号淹了）。

用法：
    python tools/bride_locate.py "art/bride/_burst2/f_*.png" --out art/bride/_strip --scale 3
"""
import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from game_shot import write_png, gain              # noqa: E402
from game_frames import read_png, montage             # noqa: E402


def warm_pale(r, g, b):
    return r > 150 and r > b + 12 and r >= g - 4


def bride_bbox(w, h, rgba, min_px=40, skip_top=26, aspect=(1.1, 5.0), step=2):
    """返回 (x0, y0, x1, y1, 命中像素数) 或 None。用行列直方图取主体，
    避免被远处零星的反光像素拉宽。

    skip_top：跳过窗口标题栏（它是暖黄白，同样满足 warm_pale，会把检测拐跑）。
    aspect：只要「竖长形」主体 —— 人形站立 h/w ≈ 2，标题栏是 0.05，一步滤掉。
    step：隔行隔列采样（1600x900 全扫是 144 万次 Python 判定/帧，隔 2 取 1
    只用 36 万次，bbox 精度差 ±2px，外面还有 pad 兜着）。
    """
    col = [0] * w
    row = [0] * h
    tot = 0
    r_ch = rgba[0::4]
    g_ch = rgba[1::4]
    b_ch = rgba[2::4]
    for y in range(skip_top, h, step):
        base = y * w
        rr = r_ch[base:base + w:step]
        gg = g_ch[base:base + w:step]
        bb = b_ch[base:base + w:step]
        x = 0
        hit = 0
        for a, c, d in zip(rr, gg, bb):
            if a > 150 and a > d + 12 and a >= c - 4:
                col[x] += 1
                hit += 1
            x += step
        if hit:
            row[y] += hit
            tot += hit
    if tot < min_px:
        return None
    cthr = max(2, max(col) // 4)
    rthr = max(2, max(row) // 5)
    xs = [i for i, v in enumerate(col) if v >= cthr]
    ys = [i for i, v in enumerate(row) if v >= rthr]
    if not xs or not ys:
        return None
    # 主体 = 命中最多的连续区间（简单起见按最长连续段取）
    def longest(idx):
        best = cur = [idx[0], idx[0]]
        for v in idx[1:]:
            if v - cur[1] <= 3:
                cur[1] = v
            else:
                if cur[1] - cur[0] > best[1] - best[0]:
                    best = list(cur)
                cur = [v, v]
        if cur[1] - cur[0] > best[1] - best[0]:
            best = list(cur)
        return best
    x0, x1 = longest(xs)
    y0, y1 = longest(ys)
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    if bw <= 0 or bh <= 0:
        return None
    if not (aspect[0] <= bh / float(bw) <= aspect[1]):
        return None
    return x0, y0, x1, y1, tot


def crop_scale(w, h, rgba, box, pad, k):
    x0, y0, x1, y1 = box[:4]
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(w - 1, x1 + pad)
    y1 = min(h - 1, y1 + pad)
    cw, ch = x1 - x0 + 1, y1 - y0 + 1
    nw, nh = cw * k, ch * k
    out = bytearray(nw * nh * 4)
    for y in range(ch):
        src = ((y0 + y) * w + x0) * 4
        row = bytearray()
        for x in range(cw):
            row += rgba[src + x * 4:src + x * 4 + 4] * k
        for j in range(k):
            dst = ((y * k + j) * nw) * 4
            out[dst:dst + nw * 4] = row
    return nw, nh, bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", nargs="+")
    ap.add_argument("--out", default="art/bride/_strip")
    ap.add_argument("--pad", type=int, default=10)
    ap.add_argument("--scale", type=int, default=3)
    ap.add_argument("--montage", default=None)
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--pick", type=int, default=12)
    ap.add_argument("--gain", type=float, default=1.0, help="裁切后提亮（暗场景用 1.6~2.2）")
    a = ap.parse_args()

    paths = []
    for pat in a.frames:
        paths += sorted(glob.glob(pat))
    os.makedirs(a.out, exist_ok=True)

    hits = []
    for p in paths:
        w, h, rgba = read_png(p)
        box = bride_bbox(w, h, rgba)
        if not box:
            continue
        x0, y0, x1, y1, tot = box
        bh = y1 - y0 + 1
        if bh < 12:
            continue
        nw, nh, buf = crop_scale(w, h, rgba, box, a.pad, a.scale)
        if a.gain != 1.0:
            buf = gain(buf, a.gain)
        name = os.path.basename(p)
        dst = os.path.join(a.out, name)
        write_png(dst, nw, nh, buf)
        hits.append({"path": dst, "frame": name, "w": nw, "h": nh,
                     "bh": bh, "px": tot, "wh": (nw, nh), "rgba": buf,
                     "x0": x0, "y0": y0, "x1": x1, "y1": y1})

    print("命中 %d/%d 帧（画面里有暖白婚纱）" % (len(hits), len(paths)))
    if not hits:
        return 1
    hits.sort(key=lambda t: -t["bh"])
    print("%-12s %-22s %6s %6s" % ("帧", "裁切框(原图)", "高", "白px"))
    for t in hits[:a.pick]:
        print("%-12s (%3d,%3d)-(%3d,%3d) %6d %6d"
              % (t["frame"], t["x0"], t["y0"], t["x1"], t["y1"], t["bh"], t["px"]))

    if a.montage:
        # 挑离得最近的（裁切高最大）+ 时间上均匀分布，读姿势最清楚
        big = hits[:max(4, a.pick // 2)]
        step = max(1, len(hits) // max(1, a.pick - len(big)))
        rest = hits[::step]
        sel, seen = [], set()
        for t in big + rest:
            if t["frame"] in seen:
                continue
            seen.add(t["frame"])
            sel.append(t)
            if len(sel) >= a.pick:
                break
        tiles = [(t["path"], t["rgba"], t["w"], t["h"]) for t in sel]
        th = max(t[3] for t in tiles)
        tw = max(t[2] for t in tiles)
        n = montage(tiles, a.montage, cols=a.cols, tile=(tw, th))
        print("接触表 → %s  %d 格  %dx%d  %.1f KB"
              % (a.montage, len(tiles), tw * a.cols, th * ((len(tiles) + a.cols - 1) // a.cols), n / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
