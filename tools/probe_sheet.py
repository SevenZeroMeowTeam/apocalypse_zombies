# -*- coding: utf-8 -*-
"""把多条技能的手臂链探针图竖排成一张证据图。

为什么竖排而不是并排：每个剪辑的探针已经是「按时间从左到右的多帧条带」，
并排会让两组时间轴打架，读图的人分不清哪一段属于哪招。竖排＝每行一招，
行内仍是时间推进，最直观。

用法：
    python tools/probe_sheet.py out.png skill_veil_chop skill_veil_swipe ...
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from game_frames import read_png                        # noqa: E402
from game_shot import write_png                         # noqa: E402

PAD = 8
BG = (18, 20, 26)


def main():
    out = sys.argv[1]
    strips = []
    for clip in sys.argv[2:]:
        p = os.path.join("art/bride", "probe_%s.png" % clip)
        if not os.path.exists(p):
            # 探针文件名里带骨骼前缀，用通配找
            import glob
            hits = glob.glob(os.path.join("art/bride", "probe_%s_*.png" % clip))
            if not hits:
                print("缺探针图：%s" % p)
                continue
            p = hits[0]
        w, h, d = read_png(p)
        strips.append((w, h, d))
        print("纳入 %-46s %dx%d" % (os.path.basename(p), w, h))
    if not strips:
        return 1
    W = max(s[0] for s in strips) + PAD * 2
    H = sum(s[1] for s in strips) + PAD * (len(strips) + 1)
    buf = bytearray()
    for y in range(H):
        for x in range(W):
            buf += bytes(BG) + b"\xff"
    yy = PAD
    for (w, h, d) in strips:
        for y in range(h):
            row = yy + y
            base = row * W * 4
            src = y * w * 4
            buf[base + PAD * 4: base + PAD * 4 + w * 4] = d[src:src + w * 4]
        yy += h + PAD
    write_png(out, W, H, bytes(buf))
    print("写出 %s  %dx%d（自上而下：%s）"
          % (out, W, H, " / ".join(sys.argv[2:])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
