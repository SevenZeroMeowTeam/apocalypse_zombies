#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""贴图/图集放大预览 —— 纯标准库解码 + 最近邻放大，供人眼（和 AI 视觉）复查像素画。

本机 python 无 PIL，所以自带 PNG 解码（支持 8bit 灰/RGB/调色板/灰度+alpha/RGBA，
全部 5 种行滤波）。用法：

    python tools/atlas_preview.py <输入.png> [放大倍数=4] [输出.png]

默认输出到 art/bride/<输入名>_x<倍数>.png。
"""
import pathlib
import struct
import sys
import zlib


def load_png(path):
    raw = pathlib.Path(path).read_bytes()
    i, idat, W = 8, b"", 0
    while i < len(raw):
        ln = struct.unpack(">I", raw[i:i + 4])[0]
        tag, dat = raw[i + 4:i + 8], raw[i + 8:i + 8 + ln]
        i += 12 + ln
        if tag == b"IHDR":
            W, H, _bd, ct, _, _, _ = struct.unpack(">IIBBBBB", dat)
        elif tag == b"IDAT":
            idat += dat
        elif tag == b"IEND":
            break
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    stride = W * ch
    data = zlib.decompress(idat)
    out, prev, pos = bytearray(), bytearray(stride), 0
    for _ in range(H):
        f = data[pos]
        pos += 1
        line = bytearray(data[pos:pos + stride])
        pos += stride
        if f == 1:
            for x in range(ch, stride):
                line[x] = (line[x] + line[x - ch]) & 255
        elif f == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride):
                line[x] = (line[x] + ((line[x - ch] if x >= ch else 0) + prev[x]) // 2) & 255
        elif f == 4:
            for x in range(stride):
                a = line[x - ch] if x >= ch else 0
                b = prev[x]
                c = prev[x - ch] if x >= ch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        out += line
        prev = line
    # 统一吐成 RGBA
    rgba = bytearray()
    for k in range(0, len(out), ch):
        p = out[k:k + ch]
        if ch == 4:
            rgba += p
        elif ch == 3:
            rgba += bytes(p) + b"\xff"
        elif ch == 1:
            rgba += bytes(p) * 3 + b"\xff"
        else:
            rgba += bytes((p[0], p[0], p[0], p[1]))
    return W, H, bytes(rgba)


def save_png(path, W, H, rgba, scale):
    nw, nh = W * scale, H * scale
    rows = []
    for y in range(nh):
        sy = y // scale
        row = bytearray()
        for x in range(nw):
            sx = x // scale
            o = (sy * W + sx) * 4
            row += rgba[o:o + 4]
        rows.append(b"\x00" + bytes(row))
    comp = zlib.compress(b"".join(rows), 9)

    def chunk(tag, dat):
        return (struct.pack(">I", len(dat)) + tag + dat
                + struct.pack(">I", zlib.crc32(tag + dat) & 0xFFFFFFFF))

    pathlib.Path(path).write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", nw, nh, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", comp) + chunk(b"IEND", b""))
    return nw, nh


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = pathlib.Path(sys.argv[1])
    scale = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    dst = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else \
        src.parent / f"{src.stem}_x{scale}.png"
    W, H, rgba = load_png(src)
    # 可选裁切：额外传 4 个参数 x y w h（原图像素坐标），只放大这一块
    if len(sys.argv) >= 8:
        cx, cy, cw, chh = (int(v) for v in sys.argv[4:8])
        cx, cy = max(0, cx), max(0, cy)
        cw, chh = min(cw, W - cx), min(chh, H - cy)
        crop = bytearray()
        for y in range(cy, cy + chh):
            o = (y * W + cx) * 4
            crop += rgba[o:o + cw * 4]
        rgba, W, H = bytes(crop), cw, chh
    nw, nh = save_png(dst, W, H, rgba, scale)
    print(f"{src} {W}x{H}{' (裁切)' if len(sys.argv) >= 8 else ''} → {dst} ({nw}x{nh})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
