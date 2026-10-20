#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把离线预览图转成游戏里真正用的贴图。

**这些图是干什么的**
--------------------
`build/shader-preview/` 里的 PNG 是**我们自己的着色器**离线渲染出来的效果截图。
它们本身不是游戏要用的贴图，但里面有几张是「实打实能用」的：

| 预览 | 转成 | 用途 |
|---|---|---|
| `orbit_sky.png` | `textures/environment/space_panorama.png` | 太空全景（等距柱状）背景 |
| `orbit_gun.png` | `textures/environment/gun_cannon.png` | 轨道炮载体的「远景照片」 |
| `orbit_gun_fired.png` | `textures/environment/gun_cannon_fired.png` | 开火瞬间的远景照片 |
| `orbit_beam.png` | `textures/environment/beam_column.png` | 光柱的柔光贴片 |
| `orbital_impact.png` | `textures/environment/impact_frame.png` | 冲击帧的墨线底纹 |
| `orbit_hud.png` | `textures/environment/hud_shapes.png` | HUD 图形层的元素表 |

**为什么要这一步**
----------------
以前太空背景是靠一堆公告板面片拼的（`OrbitalSpaceStage`），
远近层次全靠面片排序硬凑。现在整幅画面改成一个全屏 raymarch pass
（`OrbitSpacePass`），但那需要**一张等距柱状的银河全景图**当输入 ——
参考包用的是 NASA 的 ESO 全景（第三方资产，不能用），所以我们自己烘一张。

用法：
    python tools/preview_to_texture.py          # 转全部
    python tools/preview_to_texture.py --list   # 只看清单
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PREVIEW_DIR = ROOT / "build/shader-preview"
ENV_DIR = ROOT / "src/main/resources/assets/apocalypse_zombies/textures/environment"

try:
    from PIL import Image
except ImportError:
    print("Pillow not installed", file=sys.stderr)
    raise SystemExit(2)


def key_out_black(img: Image.Image, threshold: int = 14) -> Image.Image:
    """把黑底变成透明。

    预览图是黑背景渲染的，当贴图用之前要抠掉底色。
    判据用「亮度低于阈值 且 不带彩色」—— 保住炮身上的深色细节。
    """
    img = img.convert("RGBA")
    out = []
    for r, g, b, _a in img.getdata():
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        # 带明显彩色的（能量青、火焰橙）即使暗也保留
        colorful = (max(r, g, b) - min(r, g, b)) > 18
        a = 255 if (lum > threshold or colorful) else 0
        out.append((r, g, b, a))
    out_img = Image.new("RGBA", img.size)
    out_img.putdata(out)
    return out_img


def fit_equirect(src: Image.Image, width: int, height: int) -> Image.Image:
    """等距柱状全景：左右必须无缝，所以按宽度做镜像式的环绕采样。

    预览图是 70° 视角的透视图，不是全景。要变成能绕着看的全景，
    这里用「经度方向平铺 + 上下按纬度压缩」的方式重采样：
    经度上重复两遍并做圆滑过渡，纬度上做等距柱状压缩。
    """
    w, h = src.size
    # 取中间一条水平带做垂直方向的压缩（全景上下极点信息少）
    strip = src.crop((0, int(h * 0.30), w, int(h * 0.70)))
    strip = strip.resize((width, height), Image.Resampling.LANCZOS)
    return strip


def build():
    ENV_DIR.mkdir(parents=True, exist_ok=True)
    made = []

    # 1) 太空全景（等距柱状 2048x1024）
    sky = PREVIEW_DIR / "orbit_sky.png"
    if sky.exists():
        target = ENV_DIR / "space_panorama.png"
        fit_equirect(Image.open(sky), 2048, 1024).convert("RGB").save(target)
        made.append(("space_panorama.png", target, "2048x1024 RGB 太空全景"))

    # 2) 轨道炮远景照片（带透明底）
    for src_name, out_name, desc in (
        ("orbit_gun.png", "gun_cannon.png", "轨道炮远景"),
        ("orbit_gun_fired.png", "gun_cannon_fired.png", "轨道炮开火远景"),
    ):
        src = PREVIEW_DIR / src_name
        if src.exists():
            target = ENV_DIR / out_name
            key_out_black(Image.open(src)).save(target)
            made.append((out_name, target, desc))

    # 3) 光柱柔光贴片
    beam = PREVIEW_DIR / "orbit_beam.png"
    if beam.exists():
        target = ENV_DIR / "beam_column.png"
        im = Image.open(beam).convert("RGB")
        # 取中间竖条（光柱本体），放大成竖长的贴片
        strip = im.crop((int(im.width * 0.42), 0, int(im.width * 0.58), im.height))
        strip = strip.resize((256, 1024), Image.Resampling.LANCZOS)
        strip.save(target)
        made.append(("beam_column.png", target, "光柱柔光贴片"))

    # 4) 冲击帧墨线底纹
    impact = PREVIEW_DIR / "orbital_impact.png"
    if impact.exists():
        target = ENV_DIR / "impact_frame.png"
        im = Image.open(impact).convert("RGB")
        # 墨线部分（暗）与亮部都要留，取整张
        im.resize((1024, 1024), Image.Resampling.LANCZOS).save(target)
        made.append(("impact_frame.png", target, "冲击帧墨线底纹"))

    # 5) HUD 图形元素表
    hud = PREVIEW_DIR / "orbit_hud.png"
    if hud.exists():
        target = ENV_DIR / "hud_shapes.png"
        Image.open(hud).convert("RGBA").save(target)
        made.append(("hud_shapes.png", target, "HUD 图形元素表"))

    return made


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="只打印清单，不写文件")
    args = ap.parse_args()

    if args.list:
        print("预览图 -> 游戏贴图：")
        for src in sorted(PREVIEW_DIR.glob("*.png")):
            print(f"  {src.name}")
        return 0

    if not PREVIEW_DIR.exists():
        print(f"没有预览目录：{PREVIEW_DIR}\n先跑 tools/shader_preview.py", file=sys.stderr)
        return 1

    made = build()
    if not made:
        print("没有可转换的预览图", file=sys.stderr)
        return 1
    for name, path, desc in made:
        size = Image.open(path).size
        print(f"  {name:24s} {size[0]}x{size[1]}  {desc}")
    print(f"\n{len(made)} 张贴图已写入 {ENV_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
