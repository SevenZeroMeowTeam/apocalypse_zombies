"""把脸面板的像素网格打印成文本表（每格 1px，标 RGB）。

用法:
    python tools/bride_face_dump.py            # 整张脸 16x22
    python tools/bride_face_dump.py 12 22      # 只打脸内行 12..21
    python tools/bride_face_dump.py 12 22 0.5  # 附加：与上一列/上一行的差量 >= 0.5 才标

脸面板在贴图里的矩形 = (0, 16, 16, 22)（见 tools/bride_face_crop.py 的同名常量）。
输出用两位十六进制近似色，并给出「与肤色基底的色距」，便于一眼看出哪块没画出来。
"""
import sys
import os
import zlib
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = os.path.join(ROOT, 'src/main/resources/assets/apocalypse_zombies/textures/entity/bride/bride_zombie.png')
FACE = (0, 16, 16, 22)


def load_png(path):
    raw = open(path, 'rb').read()
    assert raw[:8] == b'\x89PNG\r\n\x1a\n', 'not png'
    pos = 8
    idat = b''
    w = h = depth = ctype = None
    while pos < len(raw):
        ln, typ = struct.unpack('>I4s', raw[pos:pos + 8])
        data = raw[pos + 8:pos + 8 + ln]
        if typ == b'IHDR':
            w, h, depth, ctype = struct.unpack('>IIBB', data[:10])
        elif typ == b'IDAT':
            idat += data
        elif typ == b'IEND':
            break
        pos += 12 + ln
    assert depth == 8, depth
    nch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    out = bytearray(w * h * nch)
    prev = bytearray(w * nch)
    d = zlib.decompress(idat)
    p = 0
    for y in range(h):
        f = d[p]
        p += 1
        line = bytearray(d[p:p + w * nch])
        p += w * nch
        for i in range(len(line)):
            a = line[i - nch] if i >= nch else 0
            b = prev[i]
            c = prev[i - nch] if i >= nch else 0
            x = line[i]
            if f == 1:
                x += a
            elif f == 2:
                x += b
            elif f == 3:
                x += (a + b) >> 1
            elif f == 4:
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                x += a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            line[i] = x & 0xFF
        out[y * w * nch:(y + 1) * w * nch] = line
        prev = line
    return w, h, nch, bytes(out)


def get(px, nch, w, x, y):
    o = (y * w + x) * nch
    if nch == 4:
        return px[o], px[o + 1], px[o + 2], px[o + 3]
    if nch == 3:
        return px[o], px[o + 1], px[o + 2], 255
    v = px[o]
    return v, v, v, 255


def main():
    a = sys.argv[1:]
    y0 = int(a[0]) if a else 0
    y1 = int(a[1]) if len(a) > 1 else FACE[3]
    w, h, nch, px = load_png(TEX)
    fx, fy = FACE[0], FACE[1]
    fw, fh = FACE[2], FACE[3]
    print('脸面板 %dx%d @ (%d,%d)   贴图 %dx%d/%dch' % (fw, fh, fx, fy, w, h, nch))
    print('（每格 2 位 hex：R 的高 4 位 + G 的高 4 位；. = 与"未被覆盖"的基底一致）')
    print('      ' + ''.join('%2d ' % x for x in range(fw)))
    for y in range(max(0, y0), min(fh, y1)):
        row = []
        for x in range(fw):
            r, g, b, al = get(px, nch, w, fx + x, fy + y)
            row.append('%02x' % ((r >> 4) << 4 | (g >> 4)))
        print('行%2d  ' % y + ' '.join(row))


if __name__ == '__main__':
    main()
