#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回填 AWM 图集里"没被画到"的像素 —— 只补空白，不改动任何已涂绘像素。

背景
----
`art/awm/awm.png` 与 `geo/awm.geo.json` **不是同一代产物**：图集只画到 V=388，模型 UV 用到 V=453。
1549 个面的矩形整块落在透明区、另有 1013 个面被这条水平线**切穿**，游戏里渲染成纯黑。
`tools/awm_bb_gen.js` 只把图集画进 Blockbench 的内部贴图（`TEX.internal`，L315-322），PNG 是手工导出的 ——
所以漏导一次就会与几何脱代；而重跑生成器会连几何/动画一起重生成（art/ 的 geo 生成后经过手工微调），
因此这里只针对图集做定向回填。

回填公式照抄生成器第 7 段（L296-314）：

    rgb = clamp(MAT[材质] * SHADE[面朝向] * grain(x,y) * (1px 边缘 ? 0.76 : 1)),  a = 255
    grain(x,y) = 0.93 + 0.14 * frac(sin((x + i*7)*12.9898 + (y - i*3)*78.233) * 43758.5453)

材质判定：材质是**逐方块**的（生成器 `c.__mat`），色板只有 8 项（L29-38）。对每个方块的每个面，
用"已涂绘内部像素均值"去套 `MAT[m] * SHADE[面]`，误差足够小即认定该方块属于色板项 m ——
实测已涂绘面几乎都能判定成功（判不出来会打印告警，不会静默瞎猜）。
`i`（面序号）只影响颗粒相位（±7%），无法与原图逐位相同，取本脚本的枚举序号，观感无差别。

安全性：只写 alpha < 8 的像素，并断言所有原本不透明的像素逐字节不变。
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
GEO = ROOT / "src/main/resources/assets/apocalypse_zombies/geo/awm.geo.json"
TEX = ROOT / "art/awm/awm.png"

# 生成器色板（tools/awm_bb_gen.js L29-38）
MAT = {
    "mw": (216, 221, 227),   # 白/银金属（Printstream 主体）
    "mwd": (163, 172, 182),  # 深一档的金属
    "grp": (124, 132, 141),  # 枪灰（导轨、环、五金）
    "drk": (74, 80, 88),     # 深钢内嵌
    "blk": (35, 38, 43),     # 聚合物黑（镜、握把、弹匣底、制退器）
    "brs": (206, 162, 82),   # 黄铜弹壳
    "cpr": (196, 126, 72),   # 铜被甲弹头
    "gls": (30, 90, 122),    # 镜片玻璃
}
SHADE = {"up": 1.14, "down": 0.60, "north": 1.00, "south": 0.86, "east": 0.94, "west": 0.80}
EDGE = 0.76
ALPHA_MIN = 8
MAX_ERR = 9.0  # 判定材质的容差（色阶 0-255）。实测旧图与色板：中位误差 3.1、90 分位 5.5、最大 10.5
# 整骨都没有已涂绘像素时的兜底
FALLBACK_BONE = {"scope_wind": "blk", "round_in": "brs", "casing": "brs"}
# 从生成器 box()/ring() 调用逐行读出的部件指派（键 = 方块尺寸；geo.json 不保留方块名，只能靠尺寸回指）。
# 环形件的尺寸被旋转过、不是整数，这里用的是实测到的旋转后尺寸（容差 0.005）。
SIZE_HINTS = {
    (0.07, 0.30, 0.40): "drk",        # body      forend_vent_l1/r1/l2/r2
    (0.18, 0.30, 0.30): "drk",        # body      mag_release
    (0.80, 0.25, 2.20): "grp",        # body      forend_rail
    (0.27, 0.23145, 0.05): "drk",     # barrel    bore（8 段环）
    (0.64, 0.24, 0.28): "mw",         # bolt      handle_arm
    (0.20, 0.20, 0.2912): "blk",      # bolt      knob（6 段环）
    (0.32, 0.30, 0.20): "drk",        # bipod     foot_l / foot_r
    (0.15, 0.12858, 0.10): "brs",     # casing    case_neck（8 段环）
    (0.24, 0.20573, 0.09): "brs",     # casing    case_rim（8 段环）
    (0.32, 0.08, 0.27431): "grp",     # scope_elev elev_cap（8 段环）
    (0.10, 0.16, 0.32574): "grp",     # scope_elev elev_knurl（8 段环）
    (0.26, 0.16, 0.34): "drk",        # trigger_group trigger_shoe
    (1.20, 2.15, 0.50): "mwd",        # stock     stock_rear
    (0.08, 0.25, 0.30): "grp",        # stock     sling_loop
    (0.84, 2.00, 1.85): "mwd",        # mag       mag_body
    (0.96, 0.23, 1.95): "blk",        # mag       mag_floor
    (0.04, 1.20, 1.60): "grp",        # mag       mag_rib_l / mag_rib_r
    (0.03, 0.27, 0.23): "blk",        # mag       mag_hole
    (0.60, 0.15, 1.75): "grp",        # mag       mag_spine
}


def hint_for(size, tol: float = 0.005) -> str | None:
    for key, mat in SIZE_HINTS.items():
        if len(key) == len(size) and all(abs(k - v) <= tol for k, v in zip(key, size)):
            return mat
    return None


def hashi(a: float, b: float) -> float:
    n = math.sin(a * 12.9898 + b * 78.233) * 43758.5453
    return n - math.floor(n)


def grain(x: int, y: int, i: int) -> float:
    return 0.93 + 0.14 * hashi(x + i * 7, y - i * 3)


def cubes(geo: dict):
    """产出 (骨名, 方块序号, 该方块的 [(面名, u0, v0, u1, v1)...])。只处理逐面 UV。"""
    for bone in geo["minecraft:geometry"][0]["bones"]:
        for ci, cube in enumerate(bone.get("cubes", [])):
            faces = []
            for face, spec in (cube.get("uv") or {}).items():
                if not isinstance(spec, dict):
                    continue  # 盒式 UV 不在本缺陷范围
                u, v = spec["uv"]
                w, h = spec["uv_size"]
                u0, u1 = sorted((int(u), int(u + w)))
                v0, v1 = sorted((int(v), int(v + h)))
                faces.append((face, u0, v0, u1, v1))
            if faces:
                yield bone["name"], ci, tuple(cube.get("size", (0, 0, 0))), faces


def painted_estimate(px, u0, v0, u1, v1):
    """由该面已涂绘的像素估计 材质base × 朝向系数（即去掉颗粒/边缘后的期望色）。

    被图集边界切穿的面，涂绘部分可能只剩 1px 边框；边框被生成器统一压暗到 0.76，
    所以边框像素先按 1/0.76 复原再计入，内部像素原样计入。
    返回 (r,g,b,count)。
    """
    acc = [0.0, 0.0, 0.0, 0]
    for y in range(v0, v1):
        for x in range(u0, u1):
            r, g, b, a = px[x, y]
            if a <= ALPHA_MIN:
                continue
            edge = x == u0 or x == u1 - 1 or y == v0 or y == v1 - 1
            k = 1.0 / EDGE if edge else 1.0
            acc[0] += r * k
            acc[1] += g * k
            acc[2] += b * k
            acc[3] += 1
    return acc


def identify(mean_rgb, face, count):
    """用已涂绘像素的估计值反查色板项。mean_rgb 是累加和，这里先归一化。"""
    if not count:
        return None, 0.0
    avg = [mean_rgb[k] / count for k in range(3)]
    best, best_err = None, 1e9
    s = SHADE.get(face, 1.0)
    for name, base in MAT.items():
        pred = [c * s for c in base]
        err = sum(abs(avg[k] - pred[k]) for k in range(3)) / 3.0
        if err < best_err:
            best, best_err = name, err
    return (best if best_err <= MAX_ERR else None), best_err


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只统计，不写文件")
    args = ap.parse_args()

    geo = json.loads(GEO.read_text(encoding="utf-8"))
    before = Image.open(TEX).convert("RGBA")
    w, h = before.size
    src = before.load()
    out = before.copy()
    dst = out.load()

    # --- 1. 遍历：每个方块先由它已涂绘的面判定材质 ---
    parsed = list(cubes(geo))
    cube_entries = []                      # (骨, 面列表, 材质, 该材质来源)
    by_size: dict[tuple, list[str]] = defaultdict(list)
    unresolved = []
    face_total = 0
    for bone, ci, size, faces in parsed:
        votes = defaultdict(float)
        counts = defaultdict(int)
        for face, u0, v0, u1, v1 in faces:
            face_total += 1
            mean = painted_estimate(src, u0, v0, u1, v1)
            m, err = identify(mean[:3], face, mean[3])
            if m:
                votes[m] += 1.0 / (1.0 + err)
                counts[m] += 1
        if votes:
            mat = max(votes, key=lambda k: votes[k])
            cube_entries.append((bone, faces, mat, f"{counts[mat]} 面判定"))
        else:
            cube_entries.append((bone, faces, None, "待定"))
            unresolved.append((bone, ci, size))

    # --- 2. 未定方块：同骨同尺寸兄弟 → 任意骨同尺寸兄弟 → 兜底表 ---
    known_by_bone_size = defaultdict(list)
    known_by_size = defaultdict(list)
    for (bone, ci, size, _f), entry in zip(parsed, cube_entries):
        if entry[2]:
            known_by_bone_size[(bone, size)].append(entry[2])
            known_by_size[size].append(entry[2])

    # 每根骨的多数材质：环形件这类"尺寸无法唯一定位、整骨又在涂绘范围外"的兜底依据
    bone_votes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for (bone, ci, size, _f), entry in zip(parsed, cube_entries):
        if entry[2]:
            bone_votes[bone][entry[2]] += 1
    bone_majority = {b: max(v, key=lambda k: v[k]) for b, v in bone_votes.items()}

    resolved = []
    rule_tally: dict[str, int] = defaultdict(int)
    for (bone, ci, size, faces), entry in zip(parsed, cube_entries):
        mat = entry[2]
        rule = "自身已涂绘面判定"
        if not mat:
            mat = hint_for(size)
            if mat:
                rule = "生成器部件尺寸表"
            else:
                for pool, label in ((known_by_bone_size.get((bone, size)), "同骨同尺寸兄弟"),
                                    (known_by_size.get(size), "他骨同尺寸兄弟")):
                    if pool:
                        mat = max(set(pool), key=pool.count)
                        rule = f"{label}({mat})"
                        break
        if not mat and bone in bone_majority:
            mat, rule = bone_majority[bone], "同骨多数材质"
        if not mat and bone in FALLBACK_BONE:
            mat, rule = FALLBACK_BONE[bone], "兜底表（按生成器指派）"
        if not mat:
            mat, rule = "grp", "未知→枪灰"
        rule_tally[rule] += 1
        resolved.append((bone, faces, mat, rule))

    # --- 3. 回填（只写透明像素） ---
    filled_faces = 0
    filled_px = 0
    per_mat = defaultdict(lambda: [0, 0])
    for i, (bone, faces, mat, _note) in enumerate(resolved):
        base = MAT[mat]
        for face, u0, v0, u1, v1 in faces:
            blank = sum(1 for y in range(v0, v1) for x in range(u0, u1) if src[x, y][3] <= ALPHA_MIN)
            if not blank:
                continue
            s = SHADE.get(face, 1.0)
            for y in range(v0, v1):
                for x in range(u0, u1):
                    if src[x, y][3] > ALPHA_MIN:
                        continue
                    edge = x == u0 or x == u1 - 1 or y == v0 or y == v1 - 1
                    f = s * grain(x, y, i) * (EDGE if edge else 1.0)
                    dst[x, y] = tuple(min(255, round(base[k] * f)) for k in range(3)) + (255,)
                    filled_px += 1
            filled_faces += 1
            per_mat[mat][0] += 1
            per_mat[mat][1] += blank

    # --- 4. 安全断言：原有不透明像素逐字节不变 ---
    changed = sum(
        1 for y in range(h) for x in range(w)
        if src[x, y][3] > ALPHA_MIN and src[x, y] != dst[x, y]
    )
    if changed:
        print(f"✗ 改动到了 {changed} 个已涂绘像素 —— 拒绝写出")
        return 1

    print(f"  面总数 {face_total}｜回填 {filled_faces} 个面 / {filled_px} 个像素｜已涂绘像素改动 {changed} 个 ✓")
    print("  材质来源（面块数）：")
    for rule, n in sorted(rule_tally.items(), key=lambda kv: -kv[1]):
        print(f"    {n:>5}  {rule}")
    print("  按色板统计（材质：面数 / 像素）：")
    for mat, (nf, npx) in sorted(per_mat.items(), key=lambda kv: -kv[1][1]):
        print(f"    {mat:<4} {MAT[mat]}  {nf:>5} 面 / {npx:>6} 像素")
    warn = [e for e in resolved if "未知" in e[3]]
    if warn:
        print(f"  ⚠ 材质未知、按枪灰兜底的面块 {len(warn)} 个")
        seen = defaultdict(list)
        for (bone, ci, size, _f), e in zip(parsed, resolved):
            if "未知" in e[3]:
                seen[(bone, size)].append(ci)
        for (bone, size), cis in sorted(seen.items(), key=lambda kv: -len(kv[1])):
            print(f"      {bone:<18} size={size}  ×{len(cis)}")
    if args.dry_run:
        print("  (--dry-run，未写文件)")
        return 0

    out.save(TEX)
    print(f"  已写出 {TEX.relative_to(ROOT)} ({TEX.stat().st_size} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
