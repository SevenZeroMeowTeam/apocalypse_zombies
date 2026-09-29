# -*- coding: utf-8 -*-
"""美女僵尸远程技能「抛花刺」用的花束投掷物贴图（16×16）。

画的是一束能当飞镖甩出去的花：花瓣朝上、短茎、金缎带、两条飘带收尾。

为什么手写像素图而不是拿画图工具糊一张：
  * 16×16 的物品贴图在游戏里只有 16 个像素可用，关键结构必须 **≥2px 高**才看得见；
  * 生成器能被校验、能被复现、改一版有 diff 可看（跟死亡标记图标同一个做法）。

用法：
    python tools/bouquet_dart_icon.py             # 写出 src 里的 16×16 PNG
    python tools/bouquet_dart_icon.py --preview   # 另存 8× 放大图，给眼睛看
"""

import io
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "src", "main", "resources", "assets", "apocalypse_zombies",
                   "textures", "item", "bouquet_dart.png")
PREVIEW = os.path.join(ROOT, "art", "bride", "_bouquet_dart_x8.png")

SIZE = 16

# 调色板：D 深红（花的外圈） R 玫瑰红 P 浅粉 W 高光 G 深绿 g 浅绿 Y 金 y 亮金
PALETTE = {
    "D": (0x6B, 0x10, 0x22, 255),
    "R": (0xB3, 0x1D, 0x3A, 255),
    "P": (0xE2, 0x5A, 0x7C, 255),
    "W": (0xF7, 0xD6, 0xDF, 255),
    "G": (0x2E, 0x5C, 0x2A, 255),
    "g": (0x4E, 0x8A, 0x3C, 255),
    "Y": (0xC9, 0xA2, 0x27, 255),
    "y": (0xEF, 0xD1, 0x6B, 255),
}
TRANSPARENT = (0, 0, 0, 0)

# ------------------------------------------------------------------ 像素稿
# 12 个字符一行的网格改起来太容易错位，所以整张图直接写成 16 行 × 16 列。
# '.' = 透明。花头 y1..y6（6 行高，>2px 的关键结构），茎 y7..y10，缎带 y11..y14。
SPRITE = """
................
......DDDD......
....DDRRRRDD....
...DRRWRRRRPD...
...DRRRRRRPPD...
....DDRRRRDD....
......DDDD......
.......GG.......
......gGG.......
.....ggGGg......
.......GG.......
......YYYY......
......yyyy......
.....y....y.....
....y......y....
................
"""


def parse_sprite():
    rows = [r for r in SPRITE.strip("\n").splitlines()]
    if len(rows) != SIZE:
        raise SystemExit("像素稿必须是 %d 行，实际 %d 行" % (SIZE, len(rows)))
    for i, row in enumerate(rows):
        if len(row) != SIZE:
            raise SystemExit("第 %d 行必须是 %d 列，实际 %d 列" % (i, SIZE, len(row)))
    pixels = []
    for row in rows:
        for ch in row:
            if ch == ".":
                pixels.append(TRANSPARENT)
            elif ch in PALETTE:
                pixels.append(PALETTE[ch])
            else:
                raise SystemExit("像素稿里出现了调色板没有的字符：%r" % ch)
    return rows, pixels


# ------------------------------------------------------------------ PNG 写入（标准库）
def write_png(path, width, height, pixels, scale=1):
    """pixels 是 width*height 个 RGBA 元组；scale>1 时按整数倍放大（最近邻）。"""
    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    raw = b""
    for y in range(height):
        for _rep in range(scale):
            line = b"\x00"
            for x in range(width):
                px = pixels[y * width + x]
                line += bytes(px) * scale
            raw += line
    ihdr = struct.pack(">IIBBBBB", width * scale, height * scale, 8, 6, 0, 0, 0)
    blob = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as handle:
        handle.write(blob)
    return len(blob)


def main():
    rows, pixels = parse_sprite()
    opaque = sum(1 for p in pixels if p[3] == 255)
    ratio = opaque / float(SIZE * SIZE)

    failures = []

    # 1) 不能只有一两种颜色：16px 的物品要能一眼认出是花，而不是一团色块
    used = sorted({p[:3] for p in pixels if p[3] == 255})
    if len(used) < 5:
        failures.append("用色只有 %d 种，太单薄" % len(used))

    # 2) 不透明像素占比：太少是碎屑、太多是一坨方块
    if not 0.20 <= ratio <= 0.55:
        failures.append("不透明像素占比 %.0f%%（目标 20%%~55%%）" % (ratio * 100))

    # 3) 花头是视觉主体：最上面 6 行必须有不透明像素，且茎部要细（不能糊成一块）
    bloom_rows = [r for r in range(1, 7) if any(rows[r][x] != "." for x in range(SIZE))]
    if len(bloom_rows) < 5:
        failures.append("花头只有 %d 行有内容，太扁" % len(bloom_rows))
    stem_cols = {x for r in range(7, 11) for x in range(SIZE) if rows[r][x] in "Gg"}
    if len(stem_cols) > 5:
        failures.append("茎宽 %d 列，像柱子不像花茎" % len(stem_cols))

    # 4) 对称性断 **alpha 形状**（用色刻意有一侧高光，断用色会误报 —— 死亡标记图标踩过）
    for r in range(1, 7):
        xs = [x for x in range(SIZE) if rows[r][x] != "."]
        if not xs:
            continue
        centre = (min(xs) + max(xs)) / 2.0
        for x in xs:
            mirror = int(round(2 * centre - x))
            if 0 <= mirror < SIZE and rows[r][mirror] == ".":
                failures.append("第 %d 行 alpha 不镜像（x=%d 有、x=%d 无）" % (r, x, mirror))
                break
        if failures:
            break

    if failures:
        for item in failures:
            print("FAIL " + item)
        return 1

    size = write_png(OUT, SIZE, SIZE, pixels)
    print("写出 %s（%d 字节，%dx%d，不透明 %d 像素 / %.0f%%）"
          % (os.path.relpath(OUT, ROOT), size, SIZE, SIZE, opaque, ratio * 100))
    if "--preview" in sys.argv:
        write_png(PREVIEW, SIZE, SIZE, pixels, scale=8)
        print("预览 %s（8×）" % os.path.relpath(PREVIEW, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
