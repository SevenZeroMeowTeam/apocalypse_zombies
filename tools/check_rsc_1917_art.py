#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RSC M1917 图集自检：geo.json 的每个面必须落在真涂绘过的像素上，且镜像约定成立。

为什么需要它：贴图尺寸对、文件在，都不代表内容完整 —— 生成器把图集写到 art/，资源目录那份靠拷贝，
一旦漏拷/过期，大量面会采到全透明区，游戏里渲染成纯黑（M1 加兰德与 AWM 都栽在这上面）。

检查项：
  1. geo 的 identifier / texture_width / texture_height = geometry.rsc_1917 / 512 / 512
  2. art/ 与 resources/ 两份 PNG 字节一致（sha256），都是 512x512
  3. 每个面的 UV 矩形都在画布内、矩形内至少 1 个不透明像素
  4. 矩形之间不许重叠（重叠 = 打包出错，面会串色）
  5. **镜像符号**：导出空间里 −X = 射手右侧。抛壳件(casing)与拉机柄(bolt 的柄部方块)必须落在 X<0，
     否则说明这一版几何/导出把左右搞反了，动画里的抛壳与拉栓方向也会一起反。
  6. 逐骨/逐面统计，输出用到的最高 V/最高 U（图集是否被截断）

退出码 0 = 全部对上。用法：python tools/check_rsc_1917_art.py
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOD_ID = "apocalypse_zombies"
ART = ROOT / "art" / "rsc_1917"
RES = ROOT / "src/main/resources/assets" / MOD_ID
NAME = "rsc_1917"

fails: list[str] = []
notes: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        fails.append(msg)


def read_png(path: Path):
    """极简 PNG 解码：只认 8bit RGBA / RGB、无隔行（生成器与 Blockbench 导出都是这个规格）。"""
    data = path.read_bytes()
    check(data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} 不是 PNG")
    pos, idat, w, h, ctype = 8, b"", 0, 0, 0
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            check(depth == 8, f"{path.name} 位深 {depth} != 8")
            check(inter == 0, f"{path.name} 是隔行 PNG，本脚本不认")
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
        pos += 12 + ln
    nch = {2: 3, 6: 4}.get(ctype)
    check(nch is not None, f"{path.name} 颜色类型 {ctype} 不是 RGB/RGBA")
    if nch is None:
        return w, h, None
    raw = zlib.decompress(idat)
    stride = w * nch
    out = bytearray(w * h * 4)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if f == 1:
            for i in range(nch, stride):
                line[i] = (line[i] + line[i - nch]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                b = prev[i]
                c = prev[i - nch] if i >= nch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        row = y * w * 4
        for x in range(w):
            s = x * nch
            d = row + x * 4
            out[d] = line[s]
            out[d + 1] = line[s + 1]
            out[d + 2] = line[s + 2]
            out[d + 3] = line[s + 3] if nch == 4 else 255
        prev = line
    return w, h, out


def main() -> int:
    geo_path = RES / "geo" / f"{NAME}.geo.json"
    rc_geo = RES / "geo" / f"{NAME}.geo.json"
    check(geo_path.exists(), f"缺 {geo_path}")
    if not geo_path.exists():
        return report()
    geo = json.loads(geo_path.read_text(encoding="utf-8"))
    g = geo["minecraft:geometry"][0]
    d = g["description"]
    check(d.get("identifier") == f"geometry.{NAME}", f"identifier={d.get('identifier')} 应为 geometry.{NAME}")
    check(d.get("texture_width") == 512 and d.get("texture_height") == 512,
          f"texture {d.get('texture_width')}x{d.get('texture_height')} 应为 512x512")

    art_png = ART / f"{NAME}_tex.png"
    res_png = RES / "textures" / "item" / f"{NAME}.png"
    for p in (art_png, res_png):
        check(p.exists(), f"缺 {p}")
    if not (art_png.exists() and res_png.exists()):
        return report()
    ha = hashlib.sha256(art_png.read_bytes()).hexdigest()
    hr = hashlib.sha256(res_png.read_bytes()).hexdigest()
    check(ha == hr, "art/ 与 resources/ 的贴图字节不一致（漏拷或过期 —— 游戏里会渲染成纯黑）")
    notes.append(f"贴图 sha256 = {ha[:16]}…  ({art_png.stat().st_size} bytes)")
    w, h, px = read_png(res_png)
    check((w, h) == (512, 512), f"贴图 {w}x{h} 应为 512x512")
    if px is None:
        return report()

    rects: list[tuple] = []
    maxu = maxv = 0
    per_bone: dict[str, int] = {}
    for b in g["bones"]:
        for c in b.get("cubes", []):
            per_bone[b["name"]] = per_bone.get(b["name"], 0) + 1
            uv = c.get("uv")
            if not uv:
                continue
            if isinstance(uv, dict):                     # 逐面 UV
                faces = {k: v for k, v in uv.items() if k != "rotation"}
                check(len(faces) == 6, f"{b['name']} 的方块只给了 {len(faces)} 个面 UV（要求 6 面）")
                check("rotation" not in uv, f"{b['name']} 的方块带 uv.rotation（镜像会错，规范禁）")
            else:
                continue
            for fname, fr in uv.items():
                if not isinstance(fr, dict) or "uv" not in fr:
                    continue
                u0, v0 = fr["uv"]
                sw, sh = fr.get("uv_size", [0, 0])
                x0, x1 = sorted((u0, u0 + sw))
                y0, y1 = sorted((v0, v0 + sh))
                check(x1 > x0 and y1 > y0, f"{b['name']}.{fname} UV 尺寸为 0 {fr}")
                r = (x0, y0, x1, y1)
                check(0 <= x0 and x1 <= w and 0 <= y0 and y1 <= h,
                      f"{b['name']}.{fname} UV 越界 {r}")
                rects.append((x0, y0, x1, y1, f"{b['name']}.{fname}"))
                maxu, maxv = max(maxu, x1), max(maxv, y1)
                filled = 0
                for yy in range(y0, min(y1, h)):
                    for xx in range(x0, min(x1, w)):
                        if px[(yy * w + xx) * 4 + 3] > 0:
                            filled += 1
                check(filled > 0, f"{b['name']}.{fname} 的 UV 区 {r} 全是透明像素（游戏里是纯黑面）")

    rects.sort(key=lambda t: (t[0], t[1]))
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            a, b2 = rects[i], rects[j]
            if a[0] < b2[2] and b2[0] < a[2] and a[1] < b2[3] and b2[1] < a[3]:
                check(False, f"UV 重叠：{a[4]} {a[:4]} 与 {b2[4]} {b2[:4]}")
    notes.append(f"面数 {len(rects)}，最高 U={maxu} V={maxv}（图集用到 {maxv}/512 行）")

    # ---- 镜像符号：导出空间 −X = 射手右侧 ----
    by_name = {b["name"]: b for b in g["bones"]}

    def cube_x_range(bone: str):
        lo, hi = 1e9, -1e9
        for c in by_name.get(bone, {}).get("cubes", []):
            o, s = c["origin"], c["size"]
            lo, hi = min(lo, o[0]), max(hi, o[0] + s[0])
        return (lo, hi) if lo <= hi else None

    cr = cube_x_range("casing")
    check(cr is not None and cr[0] < -0.02, f"casing 的 X 范围 {cr} 应在 −X 侧（射手右侧抛壳口）")
    br = cube_x_range("bolt")
    check(br is not None and br[0] < -0.20,
          f"bolt 的 X 范围 {br} 应向 −X 伸出（拉机柄在机匣右侧；镜像反了的话动画会往左抛壳）")
    notes.append(f"镜像符号: casing X{cr} / bolt X{br}（−X 侧 = 射手右侧 ✓）")

    print(f"geo  : {len(g['bones'])} bones / {sum(per_bone.values())} cubes")
    print("逐骨:", " ".join(f"{k}={v}" for k, v in sorted(per_bone.items())))
    return report()


def report() -> int:
    for n in notes:
        print("  " + n)
    if fails:
        print(f"\n*** {len(fails)} 项未过：")
        for f in fails:
            print("  - " + f)
        return 1
    print("\n图集自检：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
