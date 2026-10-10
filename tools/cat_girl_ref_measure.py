"""参考图轮廓测量：把 1024x1024 的猫耳娘立绘切成"按高度的宽度剖面"，
给出可对着改建模的硬数字（头身比、肩宽、裙摆/胯宽比、腿粗、配色）。
用法: py tools/cat_girl_ref_measure.py [图片路径]
"""
import sys
from PIL import Image
import collections

REF = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Administrator\Downloads\Meshy_AI_straight_standing_cat_girl_front.png"
im = Image.open(REF).convert("RGB")
W, H = im.size
px = im.load()

# 背景：四角取样，取众数
corners = [px[2, 2], px[W - 3, 2], px[2, H - 3], px[W - 3, H - 3]]
bg = collections.Counter(corners).most_common(1)[0][0]


def is_fg(c):
    return abs(c[0] - bg[0]) + abs(c[1] - bg[1]) + abs(c[2] - bg[2]) > 26


# 逐行前景区间
rows = []
for y in range(H):
    xs = [x for x in range(W) if is_fg(px[x, y])]
    rows.append((min(xs), max(xs), len(xs)) if xs else None)

top = next(y for y, r in enumerate(rows) if r)
bot = max(y for y, r in enumerate(rows) if r)
ch = bot - top + 1
print(f"图 {W}x{H}  背景={bg}  角色 y[{top},{bot}] 高={ch}px")
print(f"1 单位 = 1/16 格；若角色按 30u 建模 → 每 u = {ch/30:.1f}px")

print("\n[高度剖面] 相对高度(0=脚 1=头顶) | 宽度px | 左 | 右 | 宽/高")
step = max(1, ch // 30)
for y in range(top, bot + 1, step):
    r = rows[y]
    if not r:
        continue
    rel = (bot - y) / ch
    print(f"  {rel:5.3f} | w={r[1]-r[0]:4d} | x[{r[0]:4d},{r[1]:4d}] | {(r[1]-r[0])/ch:5.3f}")

# 关键色：按高度采样几处
print("\n[关键高度取色]")
for rel in (0.97, 0.90, 0.84, 0.76, 0.70, 0.62, 0.55, 0.48, 0.40, 0.30, 0.20, 0.08):
    y = bot - int(rel * ch)
    r = rows[y]
    if not r:
        continue
    x0, x1, _ = r
    mid = (x0 + x1) // 2
    print(f"  rel={rel:4.2f} y={y:4d} 中心色={px[mid, y]} 左1/4={px[(3*x0+x1)//4, y]} 右1/4={px[(x0+3*x1)//4, y]}")

# ASCII 剪影（我靠这个"看"图）
print("\n[ASCII 剪影]")
CW, CH_ = 56, 44
for iy in range(CH_):
    y = top + int((iy + 0.5) * ch / CH_)
    r = rows[min(y, bot)]
    line = ["."] * CW
    if r:
        x0, x1, _ = r
        a = int(x0 * CW / W)
        b = int(x1 * CW / W)
        for x in range(a, b + 1):
            line[x] = "#"
    print("".join(line))
