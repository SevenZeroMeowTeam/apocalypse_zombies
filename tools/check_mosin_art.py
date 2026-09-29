#!/usr/bin/env python3
"""莫辛-纳甘（及同类逐面 UV 枪）图集自检：geo.json 的每个面必须落在真涂绘过的像素上。

为什么需要它：贴图尺寸对、文件在，都不代表内容完整 —— 生成器把图集写到 art/，资源目录那份靠拷贝，
一旦漏拷/过期，大量面会采到全透明区，游戏里渲染成纯黑（M1 加兰德与 AWM 都栽在这上面：
旧图只画到 V=237，而模型 UV 用到 V=322）。

本脚本对 `tools/m1_garand_bb_audit.js` 的补充是**跨文件**的：它在 BB 之外把 geo.json 与 PNG 对起来查：
  1. geo 的 identifier / texture_width / texture_height 必须是 geometry.<id> / 512 / 512
  2. art/ 与 resources/ 两份 PNG 必须字节一致（sha256），都是 512x512
  3. 每个面的 UV 矩形必须在画布内、且矩形内至少有 1 个不透明像素
  4. 矩形之间不许重叠（重叠 = 打包出错，面会串色）
  5. 逐骨/逐面统计，输出用到的最高 V（图集是否被截断）

退出码 0 = 全部对上。用法：python tools/check_mosin_art.py [枪名，默认 mosin_nagant]
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
ART = ROOT / "art"
RES = ROOT / "src/main/resources/assets" / MOD_ID

fails: list[str] = []
notes: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        fails.append(msg)


def png_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as h:
        head = h.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def png_pixels(path: Path) -> tuple[int, int, bytes] | None:
    """无交错 8 位 RGB/RGBA → (w, h, rgba)。其它情况返回 None（调用方跳过，不误报）。"""
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, width, height, depth, color = 8, 0, 0, 0, 0
    idat = bytearray()
    while pos + 8 <= len(raw):
        (length,) = struct.unpack(">I", raw[pos : pos + 4])
        kind = raw[pos + 4 : pos + 8]
        data = raw[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color = struct.unpack(">IIBB", data[:10])
        elif kind == b"IDAT":
            idat += data
        elif kind == b"IEND":
            break
        pos += 12 + length
    if not width or depth != 8 or color not in (2, 6):
        return None
    channels = 4 if color == 6 else 3
    stride = width * channels
    buf = zlib.decompress(bytes(idat))
    out = bytearray(width * height * 4)
    prev = bytearray(stride)
    p = 0
    for y in range(height):
        filt = buf[p]
        p += 1
        line = bytearray(buf[p : p + stride])
        p += stride
        if filt == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filt == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filt == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filt == 4:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                up = prev[i]
                ul = prev[i - channels] if i >= channels else 0
                pa, pb, pc = abs(up - ul), abs(left - ul), abs(left + up - 2 * ul)
                pred = left if (pa <= pb and pa <= pc) else (up if pb <= pc else ul)
                line[i] = (line[i] + pred) & 0xFF
        elif filt != 0:
            return None
        row = y * width * 4
        for x in range(width):
            s = x * channels
            out[row + x * 4 : row + x * 4 + 3] = line[s : s + 3]
            out[row + x * 4 + 3] = line[s + 3] if channels == 4 else 255
        prev = line
    return width, height, bytes(out)


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "mosin_nagant"
    geo_path = ART / name / f"{name}.geo.json"
    tex_art = ART / name / f"{name}.png"
    tex_res = RES / "textures/item" / f"{name}.png"

    check(geo_path.exists(), f"找不到 {geo_path}")
    check(tex_art.exists(), f"找不到 {tex_art}")
    check(tex_res.exists(), f"找不到 {tex_res}（资源目录那份，Java 用的是它）")
    if fails:
        for f in fails:
            print("  ✗", f)
        return 1

    geo = json.loads(geo_path.read_text(encoding="utf-8"))
    geometry = geo.get("minecraft:geometry", [{}])[0]
    desc = geometry.get("description", {})
    check(desc.get("identifier") == f"geometry.{name}",
          f"identifier 是 {desc.get('identifier')!r}，应为 'geometry.{name}'")
    check(desc.get("texture_width") == 512 and desc.get("texture_height") == 512,
          f"texture_width/height 是 {desc.get('texture_width')}x{desc.get('texture_height')}，应为 512x512")
    notes.append(f"identifier {desc.get('identifier')} · 画布 {desc.get('texture_width')}x{desc.get('texture_height')}")

    size_a, size_b = png_size(tex_art), png_size(tex_res)
    check(size_a == (512, 512), f"art 图是 {size_a}，应 512x512")
    check(size_b == (512, 512), f"资源图是 {size_b}，应 512x512")
    hash_a = hashlib.sha256(tex_art.read_bytes()).hexdigest()
    hash_b = hashlib.sha256(tex_res.read_bytes()).hexdigest()
    check(hash_a == hash_b, "art/ 与 resources/ 两份 PNG 字节不一致 —— 资源那份是旧的/漏拷")
    notes.append(f"两份 PNG 一致 sha256 {hash_a[:16]}…（{tex_res.stat().st_size} B）")

    px = png_pixels(tex_res)
    if px is None:
        notes.append("PNG 非 8 位 RGB/RGBA，跳过逐面涂绘检查")
        for n in notes:
            print(" ", n)
        return 0 if not fails else 1
    width, height, rgba = px

    bones = geometry.get("bones", [])
    cube_n = sum(len(b.get("cubes", [])) for b in bones)
    faces_total = 0
    blank: list[str] = []
    max_v = 0
    grid: dict[tuple[int, int], str] = {}
    overlaps: list[str] = []
    per_bone: dict[str, int] = {}

    for bone in bones:
        for cube in bone.get("cubes", []):
            uvmap = cube.get("uv") or {}
            per_bone[bone["name"]] = per_bone.get(bone["name"], 0) + 1
            if not isinstance(uvmap, dict):
                fails.append(f"{bone['name']} 的方块 UV 不是逐面格式（box_uv 没关掉？）")
                continue
            for face, rect in uvmap.items():
                if not isinstance(rect, dict):
                    continue
                u, v = rect["uv"]
                rw, rh = rect["uv_size"]
                u0, u1 = sorted((int(u), int(u + rw)))
                v0, v1 = sorted((int(v), int(v + rh)))
                faces_total += 1
                max_v = max(max_v, v1)
                if u0 < 0 or v0 < 0 or u1 > width or v1 > height:
                    fails.append(f"{bone['name']}.{face} UV 出界：{u0},{v0}..{u1},{v1}")
                    continue
                if u0 >= u1 or v0 >= v1:
                    continue
                if not any(rgba[((y * width) + x) * 4 + 3] > 8
                           for y in range(v0, v1) for x in range(u0, u1)):
                    blank.append(f"{bone['name']}.{face}")
                key = (u0, v0)
                if key in grid and grid[key] != f"{bone['name']}.{face}":
                    if len(overlaps) < 6:
                        overlaps.append(f"{grid[key]} 与 {bone['name']}.{face} 同起于 {key[0]},{key[1]}")
                grid[key] = f"{bone['name']}.{face}"

    check(not blank, f"{len(blank)}/{faces_total} 个面的 UV 落在全透明区（旧图/漏拷），例：{blank[:6]}")
    check(not overlaps, f"面矩形起笔位置撞车（打包重叠），例：{overlaps}")
    notes.append(f"{len(bones)} 骨 / {cube_n} 方块 / {faces_total} 面，最高用到 V={max_v}px"
                 f"（画布 512，余量 {512 - max_v}px）")
    notes.append("逐骨方块数：" + ", ".join(f"{k}×{v}" for k, v in per_bone.items()))

    print(f"=== {name} 图集自检 ===")
    for n in notes:
        print(" ", n)
    if fails:
        print(f"\n{len(fails)} 条不通过：")
        for f in fails[:20]:
            print("  ✗", f)
        return 1
    print("\n全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())