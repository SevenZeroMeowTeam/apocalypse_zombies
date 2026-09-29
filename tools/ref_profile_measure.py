"""莫辛-纳甘 参考图 ↔ 模型 轮廓量化比对工具

用法（在仓库根跑）：
    python tools/ref_profile_measure.py ref art/mosin_nagant/ref/ref_mosin_9130_sniper_nobg.png --length-mm 1232
    python tools/ref_profile_measure.py geo src/main/resources/assets/apocalypse_zombies/geo/mosin_nagant.geo.json
    python tools/ref_profile_measure.py compare <ref.png> <geo.json> [--length-mm 1232]

做的事：
 1) 从图里抠出枪的前景掩膜（有 alpha 用 alpha；否则按四角背景色做色差阈值）；
 2) 用「枪管裸露段各列质心」拟合轴线 → 去倾斜（照片是随手拍的，通常歪 1~3°）；
 3) 按全长归一化到模型单位（默认 1232mm / 22.9u，53.8 mm/u），坐标口径与美术规范一致：
        Z = -17.35 + mm/53.8        （mm 自枪口量）
        Y = 相对膛线轴的竖向偏移（单位 u）
 4) 沿全长采样上/下轮廓，打印 ASCII 侧影（同尺度）与关键极值；
 5) `compare` 模式把「参考图轮廓」和「geo 投影轮廓」并排打出来，并给逐站差值。
"""
import argparse, json, math, os, sys

from PIL import Image

try:
    import numpy as np
    HAVE_NP = True
except Exception:
    HAVE_NP = False

MM_PER_U = 53.8              # 美术规范比例尺
MUZZLE_Z = -17.35            # 枪口 Z（硬锚点）
RIFLE_MM = 1232.0            # M91/30 全长
COLORS = "#@%*+=-:. "        # 侧影灰度阶梯（密 → 疏）


# ---------------------------------------------------------------- 前景掩膜
def mask_from_image(path):
    """返回 (mask: list[list[bool]] 行优先, w, h)。"""
    im = Image.open(path)
    im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
    if im.width > 1800:                      # 降采样到 ~1800px 宽，够用且快
        r = 1800.0 / im.width
        im = im.resize((1800, max(1, int(im.height * r))), Image.LANCZOS)
    w, h = im.size
    px = im.load()
    alpha_mode = "A" in im.getbands() and im.getchannel("A").getextrema()[0] < 250
    mask = [[False] * w for _ in range(h)]
    if alpha_mode:
        for y in range(h):
            row = mask[y]
            for x in range(w):
                if px[x, y][3] > 40:
                    row[x] = True
        return mask, w, h
    # 无 alpha：取四角中位数当背景色
    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    bg = tuple(sorted(c[i] for c in corners)[len(corners) // 2] for i in range(3))
    for y in range(h):
        row = mask[y]
        for x in range(w):
            p = px[x, y]
            if abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > 90:
                row[x] = True
    return mask, w, h


def bbox(mask, w, h):
    xs = [x for y in range(h) for x in range(w) if mask[y][x]]
    ys = [y for y in range(h) for x in range(w) if mask[y][x]]
    if not xs:
        raise SystemExit("掩膜为空：背景阈值可能不对")
    return min(xs), max(xs), min(ys), max(ys)


def tilt_deg(mask, w, h, x0, x1):
    """用前 45% 长度（枪管裸露段）各列质心拟合轴线倾角（度）。"""
    n = 0
    sx = sy = sxx = sxy = 0.0
    for x in range(x0, x0 + max(4, int((x1 - x0) * 0.45))):
        col = [y for y in range(h) if mask[y][x]]
        if not col:
            continue
        cy = sum(col) / len(col)
        n += 1
        sx += x; sy += cy; sxx += x * x; sxy += x * cy
    if n < 8:
        return 0.0
    den = n * sxx - sx * sx
    if abs(den) < 1e-9:
        return 0.0
    slope = (n * sxy - sx * sy) / den
    return math.degrees(math.atan(slope))


def rotate_mask(mask, w, h, deg):
    if abs(deg) < 0.15:
        return mask, w, h
    im = Image.new("L", (w, h), 0)
    p = im.load()
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                p[x, y] = 255
    im = im.rotate(deg, resample=Image.BILINEAR, expand=True, fillcolor=0)
    w2, h2 = im.size
    p = im.load()
    m2 = [[p[x, y] > 100 for x in range(w2)] for y in range(h2)]
    return m2, w2, h2


def profile_from_mask(mask, w, h, mm_per_px, x0, x1, y_bore):
    """逐列上/下轮廓 → {mm: (y_top_u, y_bot_u)}（u 为相对膛线轴的偏移，向上为正）。"""
    prof = {}
    for x in range(x0, x1 + 1):
        col = [y for y in range(h) if mask[y][x]]
        if not col:
            continue
        mm = (x - x0) * mm_per_px
        top = (y_bore - min(col)) * mm_per_px / MM_PER_U
        bot = (y_bore - max(col)) * mm_per_px / MM_PER_U
        prof[round(mm, 1)] = (top, bot)
    return prof


def bore_row(mask, w, h, x0, x1):
    """枪管裸露段（前 30%）各列中点 → 膛线轴像素行。"""
    mids = []
    for x in range(x0, x0 + max(4, int((x1 - x0) * 0.30))):
        col = [y for y in range(h) if mask[y][x]]
        if col:
            mids.append((min(col) + max(col)) / 2.0)
    return sum(mids) / len(mids) if mids else (h / 2.0)


# ---------------------------------------------------------------- geo 投影
def geo_profile(geo_path, want_u_per_col=0.2):
    """把 geo 的方块投影到 ZY 平面 → {z: (y_top, y_bot)}（几何空间，u）。"""
    g = json.load(open(geo_path, encoding="utf-8"))
    geo = g["minecraft:geometry"][0]
    boxes = []
    for bone in geo["bones"]:
        for c in bone.get("cubes", []) or []:
            o, s = c["origin"], c["size"]
            lo = [o[i] if s[i] >= 0 else o[i] + s[i] for i in range(3)]
            hi = [lo[i] + abs(s[i]) for i in range(3)]
            if c.get("rotation"):
                piv = c.get("pivot", [lo[0] + s[0] / 2.0, lo[1] + s[1] / 2.0, lo[2] + s[2] / 2.0])
                pts = []
                for cx in (lo[0], hi[0]):
                    for cy in (lo[1], hi[1]):
                        for cz in (lo[2], hi[2]):
                            pts.append(rot3([cx - piv[0], cy - piv[1], cz - piv[2]], c["rotation"]))
                lo = [piv[i] + min(p[i] for p in pts) for i in range(3)]
                hi = [piv[i] + max(p[i] for p in pts) for i in range(3)]
            boxes.append((lo, hi))
    if not boxes:
        raise SystemExit("geo 里没有方块")
    zmin = min(b[0][2] for b in boxes); zmax = max(b[1][2] for b in boxes)
    prof = {}
    n = int((zmax - zmin) / want_u_per_col) + 1
    for i in range(n + 1):
        z = zmin + i * want_u_per_col
        tops = [b[1][1] for b in boxes if b[0][2] - 1e-9 <= z <= b[1][2] + 1e-9]
        bots = [b[0][1] for b in boxes if b[0][2] - 1e-9 <= z <= b[1][2] + 1e-9]
        if tops:
            prof[round(z, 2)] = (max(tops), min(bots))
    return prof, boxes


def rot3(v, deg):
    """bedrock 顺序：Z → Y → X（与 Blockbench/GeckoLib 一致）。"""
    x, y, z = v
    rx, ry, rz = [math.radians(a) for a in deg]
    # Z
    x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
    # Y
    x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
    # X
    y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
    return [x, y, z]


# ---------------------------------------------------------------- 打印
def ascii_side(prof, mm_key=True, cols=118, rows=26, label=""):
    """把轮廓画成 ASCII 侧影（左=枪口）。"""
    if mm_key:
        items = sorted(prof.items(), key=lambda kv: -kv[0])   # mm 小 = 枪口 → 排前面
    else:
        items = sorted(prof.items())                          # z 小 = 枪口
    if not items:
        return ""
    xs = [k for k, _ in items]
    x0, x1 = min(xs), max(xs)
    tops = [v[0] for _, v in items]; bots = [v[1] for _, v in items]
    ytop = max(tops); ybot = min(bots)
    grid = [[" "] * cols for _ in range(rows)]
    for k, (t, b) in items:
        c = int((k - x0) / (x1 - x0 + 1e-9) * (cols - 1))
        r1 = int((ytop - t) / (ytop - ybot + 1e-9) * (rows - 1))
        r2 = int((ytop - b) / (ytop - ybot + 1e-9) * (rows - 1))
        for r in range(min(r1, r2), max(r1, r2) + 1):
            grid[r][c] = "#"
    out = []
    if label:
        out.append(label)
    v = MM_PER_U
    out.append("  y/u  %s" % " ".join("%+5.2f" % (ytop - i * (ytop - ybot) / (rows - 1)) for i in (0, rows // 4, rows // 2, 3 * rows // 4, rows - 1)))
    for r in range(rows):
        yv = ytop - r * (ytop - ybot) / (rows - 1)
        out.append("%+5.2f |%s|" % (yv, "".join(grid[r])))
    # x 轴刻度（mm / Z）
    lab = [" "] * cols
    for i, (k, _) in enumerate([(x0, 0), ((x0 + x1) / 2, 0), (x1, 0)]):
        mm = k
        txt = "%dmm(z%.1f)" % (mm, MUZZLE_Z + mm / v)
        s = int((k - x0) / (x1 - x0 + 1e-9) * (cols - 1)) - len(txt) // 2
        for j, ch in enumerate(txt):
            if 0 <= s + j < cols:
                lab[s + j] = ch
    out.append("      " + "".join(lab))
    return "\n".join(out)


def landmarks(prof, key="mm"):
    """自动挑关键极值：全枪最高/最低、前部最高（准星）、中部最高（照门）、后部最低（托底）等。"""
    items = sorted(prof.items(), key=lambda kv: kv[0])
    if not items:
        return {}
    n = len(items)
    def seg(a, b):
        return [kv for kv in items if a <= kv[0] <= b]
    res = {}
    res["最前站"] = items[0]
    res["最后站"] = items[-1]
    for name, a, b in [("前 12%（准星区）", 0, 0.12), ("12–45%（裸管）", 0.12, 0.45),
                       ("45–62%（机匣/照门）", 0.45, 0.62), ("62–100%（枪托）", 0.62, 1.0)]:
        s = seg(items[0][0] + (items[-1][0] - items[0][0]) * a, items[0][0] + (items[-1][0] - items[0][0]) * b)
        if s:
            res[name + " 最高"] = max(s, key=lambda kv: kv[1][0])
            res[name + " 最低"] = min(s, key=lambda kv: kv[1][1])
    return res


def print_ref(path, length_mm, cols, rows):
    mask, w, h = mask_from_image(path)
    x0, x1, y0, y1 = bbox(mask, w, h)
    d = tilt_deg(mask, w, h, x0, x1)
    mask, w, h = rotate_mask(mask, w, h, d)
    x0, x1, y0, y1 = bbox(mask, w, h)
    mm_per_px = length_mm / float(x1 - x0)
    yb = bore_row(mask, w, h, x0, x1)
    prof = profile_from_mask(mask, w, h, mm_per_px, x0, x1, yb)
    print("=== 参考图 %s ===" % os.path.basename(path))
    print("  像素 %dx%d · 掩膜包围盒 x[%d,%d] y[%d,%d] · 去倾斜 %.2f°" % (w, h, x0, x1, y0, y1, d))
    print("  全长 %dmm → %.3f mm/px · 膛线轴在像素行 %.1f" % (length_mm, mm_per_px, yb))
    print("  自检：掩膜高 %d px = %.1f u（模型实测 3.85 u / 包络 ±1.04~2.81）" % (y1 - y0, (y1 - y0) * mm_per_px / MM_PER_U))
    lm = landmarks(prof)
    for k, (mk, v) in lm.items():
        print("  %-22s mm %8.0f  Z %+6.2f  top %+5.2f u / bot %+5.2f u" % (k, mk, MUZZLE_Z + mk / MM_PER_U, v[0], v[1]))
    print(ascii_side(prof, True, cols, rows, "  ── 参考侧影（左=枪口，横轴 mm，纵轴 u 相对膛线轴）"))
    return prof


def print_geo(path, cols, rows):
    prof, boxes = geo_profile(path)
    # 几何空间 → mm（Z=-17.35 为枪口；geo 与工程 Z 同向，X 才翻转）
    mm = {round((z - MUZZLE_Z) * MM_PER_U, 1): v for z, v in prof.items()}
    print("=== 模型 geo %s ===" % os.path.basename(path))
    print("  方块 %d · Z 包络 [%.2f, %.2f] · Y 包络 [%.2f, %.2f]" % (
        len(boxes), min(b[0][2] for b in boxes), max(b[1][2] for b in boxes),
        min(b[0][1] for b in boxes), max(b[1][1] for b in boxes)))
    lm = landmarks(mm)
    for k, (mk, v) in lm.items():
        print("  %-22s mm %8.0f  Z %+6.2f  top %+5.2f u / bot %+5.2f u" % (k, mk, MUZZLE_Z + mk / MM_PER_U, v[0], v[1]))
    print(ascii_side(mm, True, cols, rows, "  ── 模型侧影（同尺度）"))
    return mm


def compare(ref_path, geo_path, length_mm, cols, rows):
    a = print_ref(ref_path, length_mm, cols, rows)
    b = print_geo(geo_path, cols, rows)
    print("\n=== 逐站差值（模型 - 参考，单位 u；>0.15u 才列） ===")
    ka = sorted(a); kb = sorted(b)
    ia = 0
    rows_out = []
    for mm in range(0, int(length_mm) + 1, 10):
        ra = nearest(a, mm); rb = nearest(b, mm)
        if ra is None or rb is None:
            continue
        dt, db = rb[0] - ra[0], rb[1] - ra[1]
        if max(abs(dt), abs(db)) > 0.15:
            rows_out.append((mm, ra, rb, dt, db))
    if not rows_out:
        print("  全部站点差值 ≤0.15u —— 轮廓已对齐")
    for mm, ra, rb, dt, db in rows_out:
        print("  mm %4d  Z %+6.2f | 参考 %+5.2f/%+5.2f  模型 %+5.2f/%+5.2f  Δ上 %+5.2f Δ下 %+5.2f" %
              (mm, MUZZLE_Z + mm / MM_PER_U, ra[0], ra[1], rb[0], rb[1], dt, db))
    print("  差异站数 %d / %d" % (len(rows_out), len(list(range(0, int(length_mm) + 1, 10)))))


def nearest(prof, mm):
    ks = list(prof)
    if not ks:
        return None
    k = min(ks, key=lambda k: abs(k - mm))
    return prof[k] if abs(k - mm) <= 12 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["ref", "geo", "compare"])
    ap.add_argument("img", nargs="?")
    ap.add_argument("geo", nargs="?")
    ap.add_argument("--length-mm", type=float, default=RIFLE_MM)
    ap.add_argument("--cols", type=int, default=118)
    ap.add_argument("--rows", type=int, default=26)
    a = ap.parse_args()
    if a.mode == "ref":
        print_ref(a.img, a.length_mm, a.cols, a.rows)
    elif a.mode == "geo":
        print_geo(a.img, a.cols, a.rows)
    else:
        compare(a.img, a.geo, a.length_mm, a.cols, a.rows)


if __name__ == "__main__":
    main()