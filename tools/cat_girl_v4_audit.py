"""v4 核验：脸贴图逐像素 ASCII + 逐带宽度剖面 vs 立绘目标表"""
import json
from pathlib import Path
from PIL import Image

ROOT = Path(r"F:/mcmod")
spec = json.loads((ROOT / "art/cat_girl/cat_girl_spec.json").read_text(encoding="utf-8"))
tex = Image.open(ROOT / "src/main/resources/assets/apocalypse_zombies/textures/entity/cat_girl.png").convert("RGB")
px = tex.load()

PAL = [((250, 214, 205), 's'), ((255, 234, 227), '.'), ((226, 188, 180), ','), ((250, 180, 180), 'r'),
       ((206, 171, 166), 'h'), ((228, 206, 202), '+'), ((176, 140, 136), 'x'), ((244, 236, 232), '~'),
       ((252, 250, 250), 'W'), ((154, 102, 120), 'i'), ((206, 168, 186), 'I'), ((104, 70, 78), '#'),
       ((255, 255, 255), 'o'), ((188, 154, 148), 'b'), ((138, 100, 98), 'l'), ((208, 132, 136), 'm')]


def sym(c):
    best, bd = '?', 1e9
    for col, ch in PAL:
        d = sum((c[i] - col[i]) ** 2 for i in range(3))
        if d < bd:
            bd, best = d, ch
    return best


face = [c for c in spec["cubes"] if c["name"] == "face"][0]
x, y, w, h = face["uvn"]
print(f"脸层正面 UV ({x},{y}) {w}x{h} px —— 逐像素实际画出内容：")
print("     " + "".join(str(i % 10) for i in range(w)))
for j in range(h):
    print(f" {j:3d} " + "".join(sym(px[x + i, y + j]) for i in range(w)))
print(" 图例 s=肤 . =亮肤 , =暗肤 r=腮红 h=发 + =亮发 x=暗发 b=眉 l=睫毛 W=眼白 i=虹膜 #=瞳 o=高光 m=嘴")

# ---------------- 宽度剖面
H = max(c["from"][1] + c["size"][1] for c in spec["cubes"])
print(f"\n模型总高 {H:.1f}u；逐带宽度（全宽/身高，含全部块）")
REF = [(0.975, "耳尖", 0.17), (0.89, "头+发", 0.175), (0.74, "肩/外套", 0.23), (0.65, "胸/袖", 0.27),
       (0.58, "肘(最宽)", 0.34), (0.41, "手/大腿", 0.175), (0.30, "裙摆", 0.23), (0.115, "小腿", 0.11),
       (0.03, "鞋", 0.13)]


def width_at(yy):
    xs = []
    for c in spec["cubes"]:
        x0, y0, z0 = c["from"]
        w, hh, d = c["size"]
        if y0 - 0.01 <= yy <= y0 + hh + 0.01:
            xs += [x0, x0 + w]
    return (max(xs) - min(xs)) if xs else 0.0


print(f"{'带':10s} {'高度位置':>7s} {'立绘':>7s} {'模型':>7s} {'比例':>7s}")
for rel, name, ref in REF:
    yy = rel * H
    m = width_at(yy) / H
    print(f"{name:10s} {rel:7.2f} {ref:7.2f} {m:7.2f} {m/ref:6.2f}x")
