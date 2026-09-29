"""图集面板「平不平」量化审计：找出**该有明暗却是一片死色**的面板。

判据与 `bride_face_runs.py` 同一套：两块颜色的距离 = max 通道差；距离 < 14 在贴图上读不出来。
面板内所有像素两两距离的最大值（`span`）就是这块面板「有没有画出体积」的上限。

- `span < 14`  ⇒ 整块面板是一个色，任何"影/高光/褶皱"都没生效（除非它本就该是平的，如鞋底/宝石）。
- `色数 = 1`   ⇒ 连渐变都没动。

用法：
    python tools/bride_panel_audit.py [--all|--skin]
"""
import json
import sys
from collections import OrderedDict

sys.path.insert(0, "tools")
from bride_face_crop import read_png   # noqa: E402

TEX = "src/main/resources/assets/apocalypse_zombies/textures/entity/bride/bride_zombie.png"
ATLAS = "art/bride/bride_atlas.json"
THRESH = 14


def dist(a, b):
    """含 alpha —— 蕾丝/面纱这类"白网 + a=0 镂空"的面板 RGB 是一色，信息全在 alpha 通道，
    只看 RGB 会把它们误判成死色。"""
    return max(abs(a[i] - b[i]) for i in range(4))


def main():
    only_skin = "--skin" in sys.argv
    tw, th, tp = read_png(TEX)
    man = json.load(open(ATLAS, encoding="utf-8"))
    # 关键：图集里多条模型面**共享同一矩形**，main() 按清单顺序作画 ⇒ 同一个矩形**最后画的
    # 那条才算数**。若按清单条目直接归类，会把"归属"记成先画的那个画家（于是看到一堆莫名其妙的
    # 死色面板）。所以先按矩形收敛到最后一条。
    last = OrderedDict()
    for m in man["faces"]:
        last[tuple(m["rect"])] = m
    groups = OrderedDict()
    for rect, m in last.items():
        p = m.get("painter", "")
        if p.startswith("@"):
            continue                       # @ 开头 = 程序化/纯色，不用画家
        x, y, w, h = rect
        groups.setdefault((p, w, h), []).append((x, y))

    rows = []
    for (p, w, h), insts in groups.items():
        span = 0
        colors = set()
        rep = None
        for (x0, y0) in insts:
            for yy in range(y0, y0 + h):
                for xx in range(x0, x0 + w):
                    i = (yy * tw + xx) * 4
                    px = (tp[i], tp[i + 1], tp[i + 2], tp[i + 3])
                    if rep is None:
                        rep = px
                    colors.add(px)
                    for c in colors:
                        d = dist(px, c)
                        if d > span:
                            span = d
        rows.append((span, len(colors), p, w, h, len(insts), rep))

    rows.sort()
    print(f"# 面板平度审计（span<{THRESH} 即整块读成死色；--skin 只看皮肤族）")
    print(f"{'span':>4} {'色数':>4}  {'painter':16s} {'尺寸':>6} x块  代表色")
    for span, ncol, p, w, h, n, rep in rows:
        if only_skin and p not in ("skin", "leg_skin", "neck_skin", "hand", "decollete"):
            continue
        flag = "  <-- 死色" if span < THRESH else ""
        hexc = "#%02X%02X%02X a=%d" % rep
        print(f"{span:>4} {ncol:>4}  {p:16s} {w:>2}x{h:<3} x{n}  {hexc}{flag}")


if __name__ == "__main__":
    main()
