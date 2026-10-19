#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-A2/A3 资产门禁：天基载体原创电影板的尺寸/格式 + dHash 参考图距离。

校验：
1) carrier_cannon / carrier_lance / carrier_singularity / carrier_plasma /
   carrier_asteroid 五张：PNG、RGB、1408x768；
2) carrier_asteroid_cutout：PNG、RGBA、600x600，轮廓外 alpha=0、本体不透明；
3) 与仓库根参考图（天基炮 / 天基矛发射器 / 引力奇点 / 等离子发射器 / 小行星）
   做 9x8 dHash（64bit）汉明距离矩阵；每张电影板对「本模式的参考图」必须 >= 18，
   否则 FAIL（证明不是参考图的缩放/裁切/重编码）。

用法：
    python tools/check_carrier_art.py
退出码 0 = PASS，1 = FAIL。
"""

from __future__ import annotations

import math
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_DIR = os.path.join(
    ROOT, "src", "main", "resources", "assets", "apocalypse_zombies", "textures", "environment")

PLATES = {
    "carrier_cannon": (1408, 768, "RGB"),
    "carrier_lance": (1408, 768, "RGB"),
    "carrier_singularity": (1408, 768, "RGB"),
    "carrier_plasma": (1408, 768, "RGB"),
    "carrier_asteroid": (1408, 768, "RGB"),
}
CUTOUT = ("carrier_asteroid_cutout", 600, 600, "RGBA")

# 参考图：扩展名不可信（实际是 JPEG 字节），用 PIL 嗅探真实格式
REFERENCE_FILES = {
    "ref_cannon": "天基炮.png",
    "ref_lance": "天基矛发射器.png",
    "ref_singularity": "引力奇点.png",
    "ref_plasma": "等离子发射器.png",
    "ref_asteroid": "小行星.png",
}
# 每张生成图对应的本模式参考图（门禁只断言这一对）
REQUIRED = {
    "carrier_cannon": "ref_cannon",
    "carrier_lance": "ref_lance",
    "carrier_singularity": "ref_singularity",
    "carrier_plasma": "ref_plasma",
    "carrier_asteroid": "ref_asteroid",
    "carrier_asteroid_cutout": "ref_asteroid",
}
MIN_DHASH_DISTANCE = 18
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def dhash(image: Image.Image, hash_size: int = 8) -> int:
    gray = image.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    bits = 0
    for row in range(hash_size):
        base = row * (hash_size + 1)
        for col in range(hash_size):
            bits = (bits << 1) | (1 if pixels[base + col] > pixels[base + col + 1] else 0)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _png_format(path: str):
    with open(path, "rb") as handle:
        magic = handle.read(8)
    return magic == PNG_MAGIC


def main() -> int:
    problems: list[str] = []
    images: dict[str, Image.Image] = {}
    formats: dict[str, str] = {}
    print("== carrier art gate: P4-A2/A3 ==")
    print()

    print("[1] generated plates (1408x768 RGB) + asteroid cutout (600x600 RGBA)")
    entries = [(name, width, height, mode) for name, (width, height, mode) in PLATES.items()]
    entries.append(CUTOUT)
    for name, width, height, mode in entries:
        path = os.path.join(ENV_DIR, name + ".png")
        if not os.path.isfile(path):
            problems.append("%s: 缺少文件 %s" % (name, os.path.relpath(path, ROOT)))
            continue
        if not _png_format(path):
            problems.append("%s: 文件头不是 PNG" % name)
        with Image.open(path) as source:
            source.load()
            formats[name] = source.format or "?"
            images[name] = source.copy()
        image = images[name]
        local = []
        if formats[name] != "PNG":
            local.append("PIL 识别格式为 %s（应为 PNG）" % formats[name])
        if image.size != (width, height):
            local.append("尺寸 %s（应为 %dx%d）" % (image.size, width, height))
        if image.mode != mode:
            local.append("像素模式 %s（应为 %s）" % (image.mode, mode))
        if name == CUTOUT[0]:
            alpha = image.convert("RGBA").getchannel("A")
            lo, hi = alpha.getextrema()
            if lo != 0:
                local.append("没有透明像素（min alpha=%d）" % lo)
            if hi != 255:
                local.append("没有不透明本体（max alpha=%d）" % hi)
            if alpha.getpixel((0, 0)) != 0:
                local.append("左上角 alpha=%d，应为透明" % alpha.getpixel((0, 0)))
            # 轮廓必须是「不规则多边形」而不是正圆：沿 32 个方向量最外不透明半径，
            # 最大/最小比值必须够大（带缺口/凸起）。
            centre_x, centre_y = image.width / 2.0, image.height / 2.0
            max_scan = int(min(centre_x, centre_y)) - 1
            radii = []
            for step in range(32):
                angle = 2.0 * math.pi * step / 32.0
                cos_a, sin_a = math.cos(angle), math.sin(angle)
                found = 0
                for scan in range(max_scan, 0, -1):
                    px = int(centre_x + cos_a * scan)
                    py = int(centre_y + sin_a * scan)
                    if 0 <= px < image.width and 0 <= py < image.height:
                        if alpha.getpixel((px, py)) > 32:
                            found = scan
                            break
                if found > 0:
                    radii.append(found)
            if len(radii) >= 8 and min(radii) > 0:
                irregularity = max(radii) / float(min(radii))
                if irregularity < 1.10:
                    local.append("轮廓太接近正圆（max/min=%.2f，应 >= 1.10 的不规则多边形）"
                                 % irregularity)
        problems.extend("%s: %s" % (name, item) for item in local)
        print("  %-24s %-11s %-5s %4dx%-4d %s"
              % (name, os.path.basename(path), image.mode, image.width, image.height,
                 "OK" if not local else "FAIL"))
    print()

    refs: dict[str, Image.Image] = {}
    ref_formats: dict[str, str] = {}
    print("[2] reference images (only used for dHash comparison; generator never reads them)")
    for key, filename in REFERENCE_FILES.items():
        path = os.path.join(ROOT, filename)
        if not os.path.isfile(path):
            problems.append("参考图缺失：%s" % filename)
            continue
        with Image.open(path) as source:
            source.load()
            ref_formats[key] = source.format or "?"
            refs[key] = source.copy()
        print("  %-14s %-14s %-6s %dx%d"
              % (key, filename, ref_formats[key], refs[key].width, refs[key].height))
    print()

    print("[3] dHash hamming distance matrix (*(required) must be >= %d)"
          % MIN_DHASH_DISTANCE)
    if not images or not refs:
        problems.append("无法计算 dHash 距离矩阵")
    else:
        hashes = {name: dhash(image) for name, image in images.items()}
        ref_hashes = {key: dhash(image) for key, image in refs.items()}
        header = "  %-24s" % "" + "".join("%-13s" % key for key in refs)
        print(header)
        minimum = None
        for name in images:
            cells = []
            for key in refs:
                distance = hamming(hashes[name], ref_hashes[key])
                required = REQUIRED.get(name) == key
                cells.append("%3d%s" % (distance, "*" if required else " "))
                if required and (minimum is None or distance < minimum):
                    minimum = distance
            print("  %-24s" % name + "".join("%-13s" % cell for cell in cells))
        print()
        for name, key in REQUIRED.items():
            if name not in hashes or key not in ref_hashes:
                continue
            distance = hamming(hashes[name], ref_hashes[key])
            if distance < MIN_DHASH_DISTANCE:
                problems.append("%s 与本模式参考图 %s 的 dHash 距离 %d < %d（疑似派生）"
                                % (name, key, distance, MIN_DHASH_DISTANCE))
        print("  required-pair minimum distance: %s" % minimum)
    print()

    if problems:
        print("FAIL: %d problem(s)" % len(problems))
        for line in problems:
            print("  -", line)
        return 1
    print("PASS: 6 张原创电影板尺寸/格式正确，且每张与本模式参考图的 dHash 距离 >= %d"
          % MIN_DHASH_DISTANCE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
