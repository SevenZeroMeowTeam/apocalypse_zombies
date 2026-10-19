#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-A1 资产门禁：校验太空舞台 5 张原创贴图的尺寸/格式，并用 dHash 证明它们不是参考图的
缩放 / 裁切 / 重编码。

为什么用 dHash：把图片压成 9x8 灰度差值的 64 bit 指纹，汉明距离对「轻微重编码」几乎不变、
对「换一张结构不同的图」很敏感。门禁要求 5 张生成贴图与 3 张参考图的 64 bit 指纹距离
全部 ≥ 18（64 bit 里差 18 bit 已经是很不同的构图），只要有任何一张离参考图太近就 FAIL。

用法：
    python tools/check_orbital_art.py
退出码 0 = PASS，1 = FAIL。
"""

from __future__ import annotations

import math
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_DIR = os.path.join(
    ROOT, "src", "main", "resources", "assets", "apocalypse_zombies", "textures", "environment")

# 生成贴图 -> (期望尺寸, 允许的像素模式)
TEXTURES = {
    "earth": ((512, 512), ("RGBA",)),
    "nebula": ((1024, 512), ("RGB", "RGBA")),
    "sat_body": ((256, 256), ("RGBA", "RGB")),
    "sat_panel": ((256, 256), ("RGBA", "RGB")),
    "sat_dish": ((256, 256), ("RGBA",)),
}
PATHS = {name: os.path.join(ENV_DIR, name + ".png") for name in TEXTURES}

# 仓库根的三张参考图；扩展名不可信（实际可能是 JPEG/WebP），用 PIL 嗅探真实格式
REFERENCE_FILES = {
    "ref_earth": "小地球.png",
    "ref_cosmos": "宇宙.png",
    "ref_satellite": "卫星.png",
}
# 每张生成贴图对应哪张参考图的「最近语义」，仅用于报告里的 required 标注；
# 门禁本身要求对 3 张参考图全部 ≥ 阈值，证明不是任何一张派生的。
NEAREST_REFERENCE = {
    "earth": "ref_earth",
    "nebula": "ref_cosmos",
    "sat_body": "ref_satellite",
    "sat_panel": "ref_satellite",
    "sat_dish": "ref_satellite",
}
MIN_DHASH_DISTANCE = 18
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def dhash(image: Image.Image, hash_size: int = 8) -> int:
    """difference hash：9x8 灰度相邻像素比较，得到 64 bit 指纹。"""
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


def check_format(name: str, fmt, size, modes) -> list[str]:
    problems = []
    path = PATHS[name]
    with open(path, "rb") as handle:
        magic = handle.read(8)
    if magic != PNG_MAGIC:
        problems.append("%s: 文件头不是 PNG（%r）" % (name, magic[:4]))
    if fmt != "PNG":
        problems.append("%s: PIL 识别格式是 %s，不是 PNG" % (name, fmt))
    return problems


def check_alpha_semantics(name: str, image: Image.Image) -> list[str]:
    """渲染期约束：地球/天线必须有圆形透明底；舱体/电池片/星云必须不透明。"""
    problems = []
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    lo, hi = alpha.getextrema()
    if name in ("earth", "sat_dish"):
        corner = alpha.getpixel((0, 0))
        if corner != 0:
            problems.append("%s: 左上角 alpha=%d，圆形贴图应为透明" % (name, corner))
        if hi != 255:
            problems.append("%s: 没有完全不透明的内部（max alpha=%d）" % (name, hi))
        if lo != 0:
            problems.append("%s: 没有透明区域（min alpha=%d），圆形遮罩丢失" % (name, lo))
    else:
        if lo != 255:
            problems.append("%s: 出现半透明/透明像素（min alpha=%d），该层应完全不透明"
                            % (name, lo))
    return problems


def main() -> int:
    problems: list[str] = []
    print("== orbital art gate: P4-A1 ==")
    print()

    # ---------- 1) 生成贴图：存在性 / 尺寸 / 格式 / alpha 语义 ----------
    images: dict[str, Image.Image] = {}
    print("[1] generated textures")
    for name, (size, modes) in TEXTURES.items():
        path = PATHS[name]
        if not os.path.isfile(path):
            problems.append("%s: 缺少文件 %s" % (name, os.path.relpath(path, ROOT)))
            continue
        with Image.open(path) as source:
            source.load()
            fmt = source.format
            images[name] = source.copy()
        image = images[name]
        found = check_format(name, fmt, size, modes)
        if image.size != size:
            found.append("%s: 尺寸 %s，期望 %s" % (name, image.size, size))
        if image.mode not in modes:
            found.append("%s: 像素模式 %s，期望 %s" % (name, image.mode, "/".join(modes)))
        found += check_alpha_semantics(name, image)
        problems.extend(found)
        colors = len(set(image.convert("RGB").getdata()))
        alpha = image.convert("RGBA").getchannel("A").getextrema()
        print("  %-9s %-11s %-5s %4dx%-4d colors=%-6d alpha=%s %s"
              % (name, os.path.relpath(path, ENV_DIR), image.mode, image.width,
                 image.height, colors, alpha, "OK" if not found else "FAIL"))
    print()

    # ---------- 2) 参考图 ----------
    refs: dict[str, Image.Image] = {}
    ref_formats: dict[str, str] = {}
    print("[2] reference images (only used for dHash comparison, never sampled by the generator)")
    for key, filename in REFERENCE_FILES.items():
        path = os.path.join(ROOT, filename)
        if not os.path.isfile(path):
            problems.append("参考图缺失：%s" % filename)
            continue
        with Image.open(path) as source:
            source.load()
            ref_formats[key] = source.format or "?"
            refs[key] = source.copy()
        print("  %-12s %-10s %-6s %dx%d"
              % (key, filename, ref_formats[key], refs[key].width, refs[key].height))
    print()

    # ---------- 3) dHash 汉明距离矩阵 ----------
    print("[3] dHash hamming distance matrix (5 generated x %d reference, threshold >= %d)"
          % (len(refs), MIN_DHASH_DISTANCE))
    if not images or not refs:
        print("  (无法计算：生成图或参考图缺失)")
        problems.append("无法计算 dHash 距离矩阵")
    else:
        hashes = {name: dhash(image) for name, image in images.items()}
        ref_hashes = {key: dhash(image) for key, image in refs.items()}
        header = "  %-9s" % "" + "".join("%-14s" % key for key in refs)
        print(header)
        minimum = None
        minimum_pair = None
        for name, image_hash in hashes.items():
            cells = []
            for key, ref_hash in ref_hashes.items():
                distance = hamming(image_hash, ref_hash)
                required = NEAREST_REFERENCE[name] == key
                cells.append("%3d%s" % (distance, "*" if required else " "))
                if minimum is None or distance < minimum:
                    minimum, minimum_pair = distance, (name, key)
            print("  %-9s" % name + "".join("%-14s" % cell for cell in cells))
        print()
        print("  (* = 语义最近的一张参考图；门禁要求全部 >= %d)" % MIN_DHASH_DISTANCE)
        print("  minimum distance: %d  (%s vs %s)" % (minimum, minimum_pair[0], minimum_pair[1]))
        if minimum < MIN_DHASH_DISTANCE:
            close = ["%s/%s=%d" % (name, key, hamming(hashes[name], ref_hashes[key]))
                     for name in images for key in refs
                     if hamming(hashes[name], ref_hashes[key]) < MIN_DHASH_DISTANCE]
            problems.append("dHash 距离过小（< %d）：%s —— 疑似参考图的缩放/裁切/重编码"
                            % (MIN_DHASH_DISTANCE, ", ".join(close)))
    print()

    if problems:
        print("FAIL: %d problem(s)" % len(problems))
        for line in problems:
            print("  -", line)
        return 1
    print("PASS: 5 张原创贴图尺寸/格式正确，与 3 张参考图的 dHash 距离全部 >= %d"
          % MIN_DHASH_DISTANCE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
