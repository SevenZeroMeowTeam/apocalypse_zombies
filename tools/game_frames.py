# -*- coding: utf-8 -*-
"""连拍帧分析：PNG 解码（纯标准库）+ 抬臂信号 + 接触表拼图。

不用 PIL：本机没有 PIL/numpy。信号定义很简单——美女僵尸是画面里唯一
「大片高亮白」的实体，**手臂过顶时白色像素的最高点会明显上移**，所以
用「top-1% 亮像素的最高 y」当抬臂判据，再按它排序挑候选帧。

用法：
    python tools/game_frames.py art/bride/_burst/f_*.png
    python tools/game_frames.py art/bride/_burst/f_*.png --montage art/bride/_sheet.png --cols 6
"""
import argparse
import glob
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from game_shot import write_png            # noqa: E402  同一个写出路径

BPP = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def read_png(path):
    """返回 (w, h, RGBA bytes)。支持 8bit / 非隔行 / 常见 color type。"""
    with open(path, "rb") as f:
        sig = f.read(8)
        if sig != b"\x89PNG\r\n\x1a\n":
            raise ValueError("不是 PNG: %s" % path)
        idat = bytearray()
        w = h = ct = bd = None
        plte = None
        trns = None
        while True:
            head = f.read(8)
            if len(head) < 8:
                raise ValueError("PNG 截断: %s" % path)
            ln, tag = struct.unpack(">I4s", head)
            body = f.read(ln)
            f.read(4)
            if tag == b"IHDR":
                w, h, bd, ct, comp, filt, inter = struct.unpack(">IIBBBBB", body)
                if bd != 8 or inter != 0:
                    raise ValueError("只支持 8bit 非隔行（bd=%d inter=%d）" % (bd, inter))
            elif tag == b"PLTE":
                plte = body
            elif tag == b"tRNS":
                trns = body
            elif tag == b"IDAT":
                idat += body
            elif tag == b"IEND":
                break
    raw = zlib.decompress(bytes(idat))
    ch = BPP[ct]
    stride = w * ch
    out = bytearray(w * h * 4)
    prev = bytearray(stride)
    pos = 0
    for y in range(h):
        ft = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ft == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ft != 0:
            raise ValueError("未知 filter %d" % ft)
        # 统一转 RGBA —— 用扩展切片赋值走 C 速度（逐像素循环在 1600x900
        # 的连拍上要跑十几分钟，这里每通道一次切片拷贝就够了）。
        base = y * w * 4
        if ct == 6:
            out[base:base + w * 4] = line
        elif ct == 2:
            out[base + 2:base + w * 4:4] = line[0::3]
            out[base + 1:base + w * 4:4] = line[1::3]
            out[base:base + w * 4:4] = line[2::3]
            out[base + 3:base + w * 4:4] = b"\xff" * w
        elif ct == 0:
            out[base:base + w * 4:4] = line
            out[base + 1:base + w * 4:4] = line
            out[base + 2:base + w * 4:4] = line
            out[base + 3:base + w * 4:4] = b"\xff" * w
        elif ct == 3:
            idx = bytes(plte[line[x] * 3 + 2] for x in range(w))
            out[base:base + w * 4:4] = idx
            out[base + 1:base + w * 4:4] = bytes(plte[line[x] * 3 + 1] for x in range(w))
            out[base + 2:base + w * 4:4] = bytes(plte[line[x] * 3] for x in range(w))
            out[base + 3:base + w * 4:4] = bytes(
                (trns[line[x]] if trns and line[x] < len(trns) else 255) for x in range(w))
        elif ct == 4:
            out[base:base + w * 4:4] = line[0::2]
            out[base + 1:base + w * 4:4] = line[0::2]
            out[base + 2:base + w * 4:4] = line[0::2]
            out[base + 3:base + w * 4:4] = line[1::2]
        prev = line
    return w, h, bytes(out)


def signature(w, h, rgba, band=None, thresh=150):
    """白亮像素（美女僵尸的婚纱/袖子）的分布信号。"""
    x0, x1 = (0, w) if not band else band
    vals = []
    for y in range(h):
        base = y * w * 4
        n = 0
        for x in range(x0, x1):
            o = base + x * 4
            if (rgba[o] + rgba[o + 1] + rgba[o + 2]) // 3 >= thresh:
                n += 1
        vals.append(n)
    tot = sum(vals) or 1
    # top-2% 亮像素的最低处（y 越小越高）
    need = max(1, tot // 50)
    acc = 0
    top_y = h
    for y, n in enumerate(vals):
        acc += n
        if acc >= need:
            top_y = y
            break
    ys = [y for y, n in enumerate(vals) if n]
    cy = sum(y * vals[y] for y in ys) / tot if tot else 0
    # 上半区（上 35%）的亮像素占比 = 抬臂时变大
    cut = int(h * 0.35)
    upper = sum(vals[:cut]) / tot
    return {"px": tot, "top_y": top_y, "cy": round(cy, 1),
            "upper": round(upper, 4)}


def montage(frames, out, cols=6, tile=None, label=True):
    """frames: [(path, rgba, w, h)] ⇒ 网格大图。"""
    if not frames:
        return 0
    tw, th = frames[0][2], frames[0][3]
    if tile:
        tw, th = tile
    rows = (len(frames) + cols - 1) // cols
    gw, gh = tw * cols, th * rows
    grid = bytearray(b"\x20" * (gw * gh * 4))
    for i in range(3, len(grid), 4):
        grid[i] = 255
    for i, (path, rgba, w, h) in enumerate(frames):
        cx, cy = (i % cols) * tw, (i // cols) * th
        sx = max(1, w // tw)
        sy = max(1, h // th)
        for y in range(min(th, h)):
            syy = min(h - 1, y * sy)
            dst = ((cy + y) * gw + cx) * 4
            src = (syy * w) * 4
            for x in range(min(tw, w)):
                s = src + min(w - 1, x * sx) * 4
                d = dst + x * 4
                grid[d:d + 4] = rgba[s:s + 4]
    return write_png(out, gw, gh, bytes(grid))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", nargs="+")
    ap.add_argument("--montage", default=None)
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--tile", default=None, help="WxH")
    ap.add_argument("--tile-w", type=int, default=120)
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args()

    paths = []
    for pat in a.frames:
        paths += sorted(glob.glob(pat))
    if not paths:
        print("没有匹配的帧", file=sys.stderr)
        return 2

    sigs = []
    for p in paths:
        w, h, rgba = read_png(p)
        s = signature(w, h, rgba)
        s["path"] = p
        s["wh"] = (w, h)
        sigs.append(s)

    base_cy = sorted(s["cy"] for s in sigs)[len(sigs) // 2]
    base_up = sorted(s["upper"] for s in sigs)[len(sigs) // 2]
    print("帧数 %d  中位亮像素 %d  中位重心 y %.1f  中位上半占比 %.3f"
          % (len(sigs), sorted(s["px"] for s in sigs)[len(sigs) // 2],
             base_cy, base_up))
    print("%-28s %6s %6s %8s %8s" % ("帧", "亮px", "top_y", "重心y", "上半占比"))
    for s in sigs:
        s["score"] = (base_cy - s["cy"]) + (s["upper"] - base_up) * 400
    for s in sorted(sigs, key=lambda t: -t["score"])[:a.top]:
        print("%-28s %6d %6d %8.1f %8.4f   Δ%.2f"
              % (os.path.basename(s["path"]), s["px"], s["top_y"], s["cy"],
                 s["upper"], s["score"]))
    print("--- 最低分（最不抬臂）:")
    for s in sorted(sigs, key=lambda t: t["score"])[:3]:
        print("%-28s %6d %6d %8.1f %8.4f   Δ%.2f"
              % (os.path.basename(s["path"]), s["px"], s["top_y"], s["cy"],
                 s["upper"], s["score"]))

    if a.montage:
        tw, th = (int(v) for v in a.tile.split("x")) if a.tile else (a.tile_w, int(a.tile_w * 1.31))
        picks = sorted(sigs, key=lambda t: -t["score"])[:a.top]
        # 候选帧 + 均匀抽样的对照帧
        step = max(1, len(sigs) // 6)
        picks_back = [sigs[i] for i in range(0, len(sigs), step)][:6]
        seen = set()
        frames = []
        for s in picks + picks_back:
            if s["path"] in seen:
                continue
            seen.add(s["path"])
            w, h, rgba = read_png(s["path"])
            frames.append((s["path"], rgba, w, h))
        n = montage(frames, a.montage, cols=a.cols, tile=(tw, th))
        print("接触表 → %s  %d 帧  %.1f KB" % (a.montage, len(frames), n / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
