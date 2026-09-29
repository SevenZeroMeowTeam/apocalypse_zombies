"""把 bride 图集（128²）的一块矩形裁出来放大，用来逐像素看脸/眼睛画得怎么样。

纯标准库解码 PNG（本机 python 无 PIL），最近邻放大，落下 PNG 供人眼审阅。

用法：
    python tools/bride_face_crop.py                       # 默认裁正面脸 0,16,16,22 ×10
    python tools/bride_face_crop.py x y w h scale out.png
"""
import sys
import zlib
import struct


def read_png(path):
    """返回 (w, h, rgba_bytes)。只支持 8-bit RGBA/Truecolor，非隔行。"""
    data = open(path, "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "不是 PNG"
    pos = 8
    idat = b""
    w = h = bitdepth = colortype = None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if ctype == b"IHDR":
            w, h, bitdepth, colortype, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
            assert bitdepth == 8 and interlace == 0, (bitdepth, interlace)
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
        pos += 12 + length

    channels = {0: 1, 2: 3, 4: 2, 6: 4}[colortype]
    raw = zlib.decompress(idat)
    stride = w * channels
    out = bytearray(stride * h)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if f == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        out[y * stride:(y + 1) * stride] = line
        prev = line

    if channels == 4:
        rgba = bytes(out)
    else:  # 补成 RGBA
        rgba = bytearray()
        for i in range(0, len(out), channels):
            px = out[i:i + channels]
            if channels == 1:
                rgba += bytes((px[0], px[0], px[0], 255))
            elif channels == 2:
                rgba += bytes((px[0], px[0], px[0], px[1]))
            else:
                rgba += bytes((px[0], px[1], px[2], 255))
        rgba = bytes(rgba)
    return w, h, rgba


def write_png(path, w, h, rgba):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgba[y * w * 4:(y + 1) * w * 4]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                           + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


def crop_scale(src, rect, scale, checker=True):
    """裁 rect=(x,y,w,h) 并最近邻放大 scale 倍，可选棋盘底（看清 alpha 镂空）。"""
    x0, y0, w, h = rect
    sw, sh, sp = read_png(src)
    ow, oh = w * scale, h * scale
    out = bytearray(ow * oh * 4)
    for oy in range(oh):
        for ox in range(ow):
            sx, sy = x0 + ox // scale, y0 + oy // scale
            i = (sy * sw + sx) * 4
            r, g, b, a = sp[i], sp[i + 1], sp[i + 2], sp[i + 3]
            if a < 255 and checker:                      # 透明处垫棋盘，肉眼好判镂空
                c = 200 if (((ox // 4) + (oy // 4)) % 2) else 150
                r = (r * a + c * (255 - a)) // 255
                g = (g * a + c * (255 - a)) // 255
                b = (b * a + c * (255 - a)) // 255
                a = 255
            j = (oy * ow + ox) * 4
            out[j:j + 4] = bytes((r, g, b, a))
    return ow, oh, bytes(out)


if __name__ == "__main__":
    argv = sys.argv[1:]
    src = "src/main/resources/assets/apocalypse_zombies/textures/entity/bride/bride_zombie.png"
    if len(argv) >= 5:
        rect = tuple(int(v) for v in argv[:4])
        scale = int(argv[4])
        out = argv[5] if len(argv) > 5 else "art/bride/face_crop.png"
    else:
        rect, scale, out = (0, 16, 16, 22), 10, "art/bride/face_crop.png"
    w, h, px = crop_scale(src, rect, scale)
    write_png(out, w, h, px)
    print(f"{src} rect={rect} x{scale} -> {out} ({w}x{h})")
