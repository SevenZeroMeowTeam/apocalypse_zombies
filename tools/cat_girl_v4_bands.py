"""v4 真实渲染轮廓 vs 立绘（按渲染图算，不用 AABB）"""
from pathlib import Path
from PIL import Image

ROOT = Path(r"F:/mcmod")
prev = Image.open(ROOT / "art/cat_girl/preview.png").convert("RGB")
front = prev.crop((0, 0, 420, 620))
px = front.load()
bg = px[2, 2]
rows = {}
for y in range(620):
    xs = [x for x in range(420) if sum(abs(px[x, y][i] - bg[i]) for i in range(3)) > 24]
    if len(xs) > 3:
        rows[y] = (min(xs), max(xs))
ys = sorted(rows)
y1 = ys[-1]
h = ys[-1] - ys[0]
print(f"模型渲染 bbox 高 {h}px（面板 620）")
REF = {0.03: 0.123, 0.08: 0.116, 0.12: 0.112, 0.16: 0.097, 0.20: 0.214, 0.25: 0.264, 0.28: 0.251,
       0.30: 0.244, 0.33: 0.223, 0.36: 0.190, 0.40: 0.171, 0.44: 0.164, 0.48: 0.297, 0.52: 0.316,
       0.56: 0.343, 0.60: 0.292, 0.64: 0.265, 0.68: 0.236, 0.72: 0.253, 0.76: 0.254, 0.80: 0.213,
       0.84: 0.168, 0.88: 0.181, 0.92: 0.178, 0.96: 0.167}
print(f"{'rel':>5s} {'立绘':>6s} {'v4渲染':>7s} {'比':>6s}")
bad = []
for rel in sorted(REF):
    y = int(round(y1 - rel * h))
    if y in rows:
        a, b = rows[y]
        m = (b - a) / h
        r = m / REF[rel]
        flag = "" if 0.82 <= r <= 1.2 else "  ←"
        if flag:
            bad.append((rel, REF[rel], m, r))
        print(f"{rel:5.2f} {REF[rel]:6.3f} {m:7.3f} {r:5.2f}{flag}")
print("超差带:", bad if bad else "无（全部落在 0.82~1.20）")

# 脸贴图放大图（左：v4 的 28x20 逐像素；右：v3 的 7x8 对比）
tex = Image.open(ROOT / "src/main/resources/assets/apocalypse_zombies/textures/entity/cat_girl.png").convert("RGB")
K = 14
f4 = tex.crop((0, 0, 28, 20)).resize((28 * K, 20 * K), Image.NEAREST)
v3 = Image.open(ROOT / "art/cat_girl/_bak_v3_texture.png").convert("RGB").crop((7, 7, 14, 15))
f3 = v3.resize((v3.width * K * 4, v3.height * K * 4), Image.NEAREST)   # 同物理尺寸对比
out = Image.new("RGB", (f4.width + f3.width + 30, max(f4.height, f3.height)), (255, 255, 255))
out.paste(f4, (0, 0))
out.paste(f3, (f4.width + 30, 0))
out.save(ROOT / "art/cat_girl/face_now.png")
print(f"脸对比图 → art/cat_girl/face_now.png  左=v4({f4.size}) 右=v3 同尺寸放大=({f3.size})")
