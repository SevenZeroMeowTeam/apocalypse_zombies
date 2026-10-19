#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「菜单通用背景」：把干净的《废土城市》插画（pause_background.png）调成末日紫调。

为什么需要它：`apocalypse_title.png`（《末日菜单》原图）里烤死了标题字和四个石质按钮，
只适合标题界面自己用（真实按钮正好盖住图里的按钮）。其它菜单（断开连接、选项、多人、
模组列表……）铺同一张图时，烤死的标题字/按钮会从对话框后面透出来，看起来像重影 UI。

所以这里从 `pause_background.png`（同一套场景、本来就没有任何文字/按钮）派生一张
`menu_background.png`：保留原图结构，只做紫色暮光调色 + 顶部压暗，输出真正的 PNG。

用法：
    python tools/menu_background.py
    python tools/menu_background.py --preview C:/Temp/menu_preview.png
"""
import argparse
import os

import numpy as np
from PIL import Image

SRC = os.path.join(
    "src", "main", "resources", "assets", "apocalypse_zombies", "textures", "gui",
    "pause_background.png")
DST = os.path.join(
    "src", "main", "resources", "assets", "apocalypse_zombies", "textures", "gui",
    "menu_background.png")


def build() -> Image.Image:
    rgb = np.asarray(Image.open(SRC).convert("RGB"), dtype=np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    # 以亮度为主，往蓝紫方向重新配比：R 借一点 B，G 压低，B 提亮 —— 得到暮光紫而不是橙。
    nr = np.clip(lum * 0.78 + b * 0.18, 0, 255)
    ng = np.clip(lum * 0.52 + g * 0.18, 0, 255)
    nb = np.clip(lum * 0.92 + b * 0.34, 0, 255)
    out = np.stack([nr, ng, nb], axis=-1) * 0.88
    # 顶部再压暗一点，给标题字/对话框让出对比度。
    shade = np.linspace(1.05, 0.78, out.shape[0], dtype=np.float32)[:, None, None]
    return Image.fromarray(np.clip(out * shade, 0, 255).astype(np.uint8))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the clean purple menu background")
    parser.add_argument("--preview", default=None, help="also write a copy here")
    args = parser.parse_args()
    image = build()
    image.save(DST, format="PNG")
    print(f"wrote {DST} ({image.width}x{image.height} RGB)")
    if args.preview:
        image.save(args.preview, format="PNG")
        print(f"preview {args.preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
