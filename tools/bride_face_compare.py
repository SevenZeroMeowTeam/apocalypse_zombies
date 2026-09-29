"""把两张已裁好的 PNG 并排成一张对照图（左=改前，右=改后），中间留一道深色分隔。

纯标准库（本机 python 无 PIL）—— 复用 bride_face_crop.py 的差量解码/编码。

用法：
    python tools/bride_face_compare.py art/bride/face_crop_before.png art/bride/face_crop.png art/bride/face_ab.png
"""
import sys

sys.path.insert(0, "tools")
from bride_face_crop import read_png, write_png   # noqa: E402

GAP = 8
DIV = (70, 70, 84, 255)


def main():
    a_p, b_p = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else "art/bride/face_ab.png"
    aw, ah, ap = read_png(a_p)
    bw, bh, bp = read_png(b_p)
    h = max(ah, bh)
    ow = aw + GAP + bw
    dst = bytearray(ow * h * 4)
    for y in range(h):
        for x in range(ow):
            j = (y * ow + x) * 4
            if x < aw:
                src, sw, sh, sp, sx, sy = ap, aw, ah, ap, x, y
            elif x < aw + GAP:
                dst[j:j + 4] = bytes(DIV)
                continue
            else:
                src, sw, sh, sp, sx, sy = bp, bw, bh, bp, x - aw - GAP, y
            if sy >= sh:
                dst[j:j + 4] = bytes((30, 30, 36, 255))          # 补齐区：深底
            else:
                i = (sy * sw + sx) * 4
                dst[j:j + 4] = sp[i:i + 4]
    write_png(out, ow, h, bytes(dst))
    print(f"{a_p}({aw}x{ah}) | {b_p}({bw}x{bh}) -> {out} ({ow}x{h})")


if __name__ == "__main__":
    main()
