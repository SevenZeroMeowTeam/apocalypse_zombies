"""把脸面板的行/列按「色距」分组成块，输出每行的游程（run-length），便于精确判断
嘴唇/眼睛到底占了哪几列几行 —— 比肉眼看放大图可靠。

用法: python tools/bride_face_runs.py [row0 row1]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bride_face_dump import load_png, get, TEX, FACE


def dist(c1, c2):
    return max(abs(c1[i] - c2[i]) for i in range(3))


def main():
    a = sys.argv[1:]
    r0 = int(a[0]) if a else 0
    r1 = int(a[1]) if len(a) > 1 else FACE[3]
    w, h, nch, px = load_png(TEX)
    fx, fy, fw, fh = FACE
    for y in range(max(0, r0), min(fh, r1)):
        cells = [get(px, nch, w, fx + x, fy + y) for x in range(fw)]
        base = cells[0]
        runs = []
        start = 0
        for x in range(1, fw + 1):
            if x == fw or dist(cells[x], cells[start]) > 14:
                runs.append((start, x - 1, cells[start]))
                start = x
        txt = '  '.join('%d-%d(%02x%02x%02x)' % (s, e, c[0], c[1], c[2]) for s, e, c in runs)
        print('行%2d  %s' % (y, txt))


if __name__ == '__main__':
    main()
