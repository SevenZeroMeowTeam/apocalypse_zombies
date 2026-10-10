"""猫耳娘：spec → 软件渲染预览（真贴图，不依赖 Blockbench）。

为什么：本机 Blockbench 离屏抓图返回空白（程序化建的 cube 没有 mesh），
迭代时需要一个确定、秒级的"看形状+贴图"通道。做法是最朴素的画家算法：
  spec(bones+cubes) → 8 角点(含 cube 自身 rot) → 6 面 → 深度排序 → 按面 UV 仿射贴真贴图。

用法:
  py tools/cat_girl_preview.py                              # 4 视图拼一张 art/cat_girl/preview.png
  py tools/cat_girl_preview.py --views front,side --out x.png
  py tools/cat_girl_preview.py --flat                        # 不贴图，只轮廓（快）
"""
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPEC = ROOT / "art/cat_girl/cat_girl_spec.json"
DEFAULT_TEX = ROOT / "src/main/resources/assets/apocalypse_zombies/textures/entity/cat_girl.png"
DEFAULT_OUT = ROOT / "art/cat_girl/preview.png"

CORNERS = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
# 面 → (角点顺序, 亮度)
FACES = [
    ("north", [0, 1, 2, 3], 1.00),
    ("south", [5, 4, 7, 6], 0.86),
    ("west", [4, 0, 3, 7], 0.93),
    ("east", [1, 5, 6, 2], 0.93),
    ("up", [3, 2, 6, 7], 1.05),
    ("down", [4, 5, 1, 0], 0.78),
]
# 贴图 UV 轴向（Minecraft 约定）：u 轴 / v 轴（v 往贴图下方增长）
UV_AXIS = {
    "north": ((1, 0, 0), (0, -1, 0)),
    "south": ((-1, 0, 0), (0, -1, 0)),
    "east": ((0, 0, -1), (0, -1, 0)),
    "west": ((0, 0, 1), (0, -1, 0)),
    "up": ((1, 0, 0), (0, 0, 1)),
    "down": ((1, 0, 0), (0, 0, -1)),
}


def box_uv(u, v, w, h, d):
    return {
        "up": (u + d, v, u + d + w, v + d),
        "down": (u + d + w, v, u + d + w + w, v + d),
        "east": (u, v + d, u + d, v + d + h),
        "north": (u + d, v + d, u + d + w, v + d + h),
        "west": (u + d + w, v + d, u + d + w + d, v + d + h),
        "south": (u + 2 * d + w, v + d, u + 2 * d + 2 * w, v + d + h),
    }


def rot_matrix(rx, ry, rz):
    rx, ry, rz = (math.radians(a) for a in (rx, ry, rz))
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    return [
        [cy * cz, cz * sx * sy - cx * sz, cx * cz * sy + sx * sz],
        [cy * sz, cx * cz + sx * sy * sz, -cz * sx + cx * sy * sz],
        [-sy, cy * sx, cx * cy],
    ]


def build_faces(spec):
    out = []
    for c in spec["cubes"]:
        f, s = list(c["from"]), list(c["size"])
        if min(s) <= 0:
            continue
        rot = c.get("rot") or [0, 0, 0]
        piv = c.get("pivot") or f
        m = rot_matrix(*rot) if any(rot) else None
        pts = []
        for cx, cy, cz in CORNERS:
            p = [f[0] + s[0] * cx, f[1] + s[1] * cy, f[2] + s[2] * cz]
            if m:
                q = [sum(m[i][j] * (p[j] - piv[j]) for j in range(3)) for i in range(3)]
                p = [q[i] + piv[i] for i in range(3)]
            pts.append(p)
        k = c.get("k", 1.0)
        px_size = [int(round(v * k)) for v in s]
        rects = box_uv(*(c.get("uv") or [0, 0]), *px_size)
        if c.get("uvn"):
            x, y, w, h = c["uvn"]
            rects = dict(rects)
            rects["north"] = (x, y, x + w, y + h)
        for name, idx, shade in FACES:
            quad = [pts[i] for i in idx]
            uvec, vvec = UV_AXIS[name]
            us = [sum(q[k] * uvec[k] for k in range(3)) for q in quad]
            vs = [sum(q[k] * vvec[k] for k in range(3)) for q in quad]
            out.append({
                "quad": quad, "face": name, "uv": rects[name], "shade": shade,
                "bone": c["bone"], "axis": (uvec, vvec),
                "ofs": (min(us), max(us), min(vs), max(vs)),
            })
    return out


def project(p, view):
    x, y, z = p
    if view == "front":
        return x, y, -z
    if view == "back":
        return -x, y, z
    if view == "side":
        return z, y, -x
    if view == "q34":
        a = math.radians(-35)
        return x * math.cos(a) + z * math.sin(a), y, -(-x * math.sin(a) + z * math.cos(a))
    raise ValueError(view)


def uv_of(face, p):
    uvec, vvec = face["axis"]
    umin, umax, vmin, vmax = face["ofs"]
    u0, v0, u1, v1 = face["uv"]
    su = (sum(p[k] * uvec[k] for k in range(3)) - umin) / max(umax - umin, 1e-6)
    sv = (sum(p[k] * vvec[k] for k in range(3)) - vmin) / max(vmax - vmin, 1e-6)
    return u0 + su * (u1 - u0), v0 + sv * (v1 - v0)


def render(spec, tex, view, flat=False, W=420, H=620, margin=16, bg=(246, 244, 247)):
    faces = build_faces(spec)
    proj = [[project(p, view) for p in f["quad"]] for f in faces]
    xs = [q[0] for f in proj for q in f]
    ys = [q[1] for f in proj for q in f]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sc = min((W - 2 * margin) / max(x1 - x0, 1e-6), (H - 2 * margin) / max(y1 - y0, 1e-6))

    def to_screen(px, py):
        return ((W - (x1 - x0) * sc) / 2 + (px - x0) * sc,
                H - ((H - (y1 - y0) * sc) / 2 + (py - y0) * sc))

    def from_screen(sx, sy):
        return (x0 + (sx - (W - (x1 - x0) * sc) / 2) / sc,
                y0 + (H - sy - (H - (y1 - y0) * sc) / 2) / sc)

    img = Image.new("RGB", (W, H), bg)
    order = sorted(range(len(faces)), key=lambda i: -sum(q[2] for q in proj[i]) / 4)
    for i in reversed(order):  # 远的先画
        f = faces[i]
        scr = [to_screen(q[0], q[1]) for q in proj[i]]
        if flat:
            ImageDraw.Draw(img).polygon(scr, fill=(180, 175, 185), outline=(60, 55, 65))
            continue
        bx0, by0 = int(min(p[0] for p in scr)), int(min(p[1] for p in scr))
        bx1, by1 = int(max(p[0] for p in scr)) + 1, int(max(p[1] for p in scr)) + 1
        bw, bh = max(bx1 - bx0, 1), max(by1 - by0, 1)
        P0, P1, P3 = proj[i][0], proj[i][1], proj[i][3]
        e1 = (P1[0] - P0[0], P1[1] - P0[1])
        e2 = (P3[0] - P0[0], P3[1] - P0[1])
        det = e1[0] * e2[1] - e1[1] * e2[0]
        if abs(det) < 1e-9:
            continue
        C = f["quad"]

        def src_of(sx, sy):
            mx, my = from_screen(sx, sy)
            dx, dy = mx - P0[0], my - P0[1]
            a = (dx * e2[1] - e2[0] * dy) / det
            b = (e1[0] * dy - dx * e1[1]) / det
            pm = [C[0][k] + a * (C[1][k] - C[0][k]) + b * (C[3][k] - C[0][k]) for k in range(3)]
            return uv_of(f, pm)

        q_ul, q_ll = src_of(bx0, by0), src_of(bx0, by1)
        q_lr, q_ur = src_of(bx1, by1), src_of(bx1, by0)
        data = [q_ul[0], q_ul[1], q_ll[0], q_ll[1], q_lr[0], q_lr[1], q_ur[0], q_ur[1]]
        try:
            warped = tex.transform((bw, bh), Image.QUAD, data, Image.NEAREST)
        except Exception:
            continue
        warped = ImageEnhance.Brightness(warped).enhance(f["shade"])
        mask = Image.new("L", (bw, bh), 0)
        ImageDraw.Draw(mask).polygon([(p[0] - bx0, p[1] - by0) for p in scr], fill=255)
        img.paste(warped, (bx0, by0), mask)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=str(DEFAULT_SPEC))
    ap.add_argument("--tex", default=str(DEFAULT_TEX))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--views", default="front,side,back,q34")
    ap.add_argument("--flat", action="store_true")
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    tex = Image.open(a.tex).convert("RGB")
    views = [v for v in a.views.split(",") if v]
    imgs = [render(spec, tex, v, flat=a.flat) for v in views]
    out = Image.new("RGB", (sum(i.width for i in imgs) + 6 * (len(imgs) - 1), imgs[0].height), (255, 255, 255))
    x = 0
    for i in imgs:
        out.paste(i, (x, 0))
        x += i.width + 6
    out.save(a.out)
    print(f"渲染 {len(views)} 视图 → {a.out}  {out.size}  (贴图 {tex.size})")


if __name__ == "__main__":
    main()
