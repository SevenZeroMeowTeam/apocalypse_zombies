"""用模组自己的轨道天幕 shader 烘焙两张太空贴图。

为什么需要它
------------
参考模组「The Shooting Star」的太空场景是**贴图驱动**的：一张银河全景、一张地球昼面图 +
辅助图、一本行星图集。那边的素材是 NASA / 第三方来源，不能抄。
本模组本来就有自己写的程序化太空着色器
（``assets/apocalypse_zombies/shaders/core/orbit_sky.fsh``：三层星场 + 银河尘带 + 星云 +
解析地球 + 月球 + 太阳），所以走另一条路：**用自己的 shader 离线渲染，把结果当游戏内贴图**。

为此给 orbit_sky 加了一个烘焙入口（``uniform float BakeMode``）：
- ``BakeMode = 0`` —— 游戏内相机视线（默认；Java 侧不设置这个 uniform，走原路径，画面不变）
- ``BakeMode = 1`` —— 等距柱状（equirectangular，2:1）全景天空：每个纹素按
  ``lon = (u-0.5)*2π`` / ``lat = (0.5-v)*π`` 反算视线方向再求值天空
- ``BakeMode = 2`` —— 等距柱状行星反照率：同一个地表函数在球面 (u,v) 上的取值

产出
----
- ``textures/environment/space_panorama.png``  2048x1024 RGB  全景天空（星场 + 银河 + 星云）
- ``textures/environment/planet_albedo.png``  1024x1024 RGBA 行星反照率（RGB = 地表，A = 云量）

约定
----
- 像素值直接存 shader 的线性输出（不做 gamma 编码）：Minecraft 的 shader 把贴图字节当线性值用，
  这样贴图进游戏后的观感 = 烘焙时的观感。
- 烘焙固定 ``GameTime = 0``（星云流动 / 星星闪烁全部定住），保证**同样的输入永远得到同样的字节**。

用法
----
    python tools/space_bake.py             # 烘焙两张图（覆盖写入资源目录）并做数值体检
    python tools/space_bake.py --analyze   # 只体检已有文件，不重新渲染
"""
from __future__ import annotations

import argparse
import hashlib
import math
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHADERS = ROOT / "src/main/resources/assets/apocalypse_zombies/shaders"
TEX_DIR = ROOT / "src/main/resources/assets/apocalypse_zombies/textures/environment"

PANORAMA_SIZE = (2048, 1024)   # 2:1 等距柱状全景
PLANET_SIZE = (1024, 1024)     # 2:1 等距柱状行星图
PANORAMA_PATH = TEX_DIR / "space_panorama.png"
PLANET_PATH = TEX_DIR / "planet_albedo.png"

TAU = math.pi * 2.0

# 全屏三角形：NDC 坐标直接当顶点属性（和 shader_preview.py 一致）
QUAD = [(-1.0, -1.0), (3.0, -1.0), (-1.0, 3.0)]


# ————————————————————————————————————————————————————————————
#  渲染（沿用 shader_preview.py 的写法：同一个 Mesa 驱动、同一条 GLSL 150 管线）
# ————————————————————————————————————————————————————————————
def make_context():
    import moderngl
    return moderngl.create_standalone_context(require=330)


def load(path: pathlib.Path) -> str:
    """读取 shader 源码。"""
    return path.read_text(encoding="utf-8")


def build_program(ctx, vsrc: str, fsrc: str, uniforms: dict):
    """编译 program 并设置 uniform；uniform 不存在时静默跳过（和 MC 的 safeGetUniform 一致）。"""
    prog = ctx.program(vertex_shader=vsrc, fragment_shader=fsrc)
    for name, value in uniforms.items():
        if name not in prog:
            continue
        try:
            if hasattr(value, "read"):          # 贴图 → 绑到 sampler
                prog[name].texture = value
                value.use(0)
            elif isinstance(value, (int, float)):
                prog[name].value = float(value)
            elif len(value) == 2:
                prog[name].value = tuple(float(v) for v in value)
            elif len(value) == 3:
                prog[name].value = tuple(float(v) for v in value)
            elif len(value) == 4:
                prog[name].value = tuple(float(v) for v in value)
        except Exception:
            pass
    return prog


def shader_sources() -> tuple[str, str]:
    """顶点着色器：把 MC 注入的 Position 属性改成本脚本用的名字（与 shader_preview.py 相同）。"""
    # v6.1：改用专门的烘焙 shader（orbit_bake.fsh）——
    # 它的调色/构图直接对标参考图（彩色星云 + 银河尘带 + 旋涡星系 + 高饱和地表），
    # 而 orbit_sky.fsh 那份是「游戏内实时解析体」的调法。
    vsrc = load(SHADERS / "core/orbit_bake.vsh")
    fsrc = load(SHADERS / "core/orbit_bake.fsh")
    vsrc = vsrc.replace("in vec3 Position;", "in vec2 in_position;")
    vsrc = vsrc.replace("vUV = Position.xy;", "vUV = in_position;")
    vsrc = vsrc.replace("gl_Position = vec4(Position.xy, 0.9999, 1.0);",
                        "gl_Position = vec4(in_position, 0.9999, 1.0);")
    return vsrc, fsrc


def render(ctx, prog, width: int, height: int, components: int):
    """渲染一帧，返回 PIL 图像（顶行 = 图顶）。"""
    import moderngl
    from PIL import Image

    fbo = ctx.simple_framebuffer((width, height), components=components)
    fbo.use()
    ctx.clear(0.0, 0.0, 0.0, 1.0)

    data = b"".join(struct.pack("<2f", x, y) for x, y in QUAD)
    vbo = ctx.buffer(data)
    vao = ctx.vertex_array(prog, [(vbo, "2f", "in_position")])
    vao.render(moderngl.TRIANGLES, 3)

    raw = fbo.read(components=components, alignment=1)
    mode = "RGB" if components == 3 else "RGBA"
    img = Image.frombytes(mode, (width, height), raw).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    vao.release()
    vbo.release()
    fbo.release()
    return img


def _u_mapping(width: int) -> tuple[float, float]:
    """全景图的 u 映射：让第 0 列与第 W-1 列落在**同一条视线**上（lon = ∓π）。

    常规的「纹素中心」取样 u = (x+0.5)/W 会让首末列相隔一个纹素，接缝处还会
    因为 sin(±π) 的 ±1e-16 落到不同的星点网格里。这里改成 u = x/(W-1)：
    首末列严格相同 → 全景图左右无缝可验证。
    """
    span = float(width - 1)
    return (width / span, -0.5 / span)


def bake_panorama(ctx):
    """烘焙 2048x1024 全景天空（RGB）。"""
    width, height = PANORAMA_SIZE
    vsrc, fsrc = shader_sources()
    prog = build_program(ctx, vsrc, fsrc, {
        "CamForward": (0.0, 0.0, 1.0),
        "CamRight": (1.0, 0.0, 0.0),
        "CamUp": (0.0, 1.0, 0.0),
        "TanHalf": math.tan(math.radians(70.0) * 0.5),
        "Aspect": width / height,
        "Alpha": 1.0,
        "GameTime": 0.0,             # 定住闪烁与星云流动 → 结果可复现
        "BakeMode": 1.0,             # 1 = 等距柱状全景天空
        "BakePixel": TAU / float(width - 1),   # 一个纹素对应的角尺寸
        "BakeSize": (float(width), float(height)),
    })
    return render(ctx, prog, width, height, 3)


def bake_planet(ctx):
    """烘焙 1024x1024 行星反照率（RGBA，A = 云量）。"""
    width, height = PLANET_SIZE
    vsrc, fsrc = shader_sources()
    prog = build_program(ctx, vsrc, fsrc, {
        "CamForward": (0.0, 0.0, 1.0),
        "CamRight": (1.0, 0.0, 0.0),
        "CamUp": (0.0, 1.0, 0.0),
        "TanHalf": math.tan(math.radians(70.0) * 0.5),
        "Aspect": width / height,
        "Alpha": 1.0,
        "GameTime": 0.0,
        "BakeMode": 2.0,             # 2 = 等距柱状行星反照率
        "BakePixel": TAU / float(width - 1),
        "BakeSize": (float(width), float(height)),
    })
    return render(ctx, prog, width, height, 4)


# ————————————————————————————————————————————————————————————
#  数值体检（只用 Pillow）
# ————————————————————————————————————————————————————————————
def _count(mask) -> int:
    """统计二值掩膜（0/255）里白色像素的个数。"""
    return sum(mask.histogram()[128:])


def _mask(channel, keep_high: bool, threshold: int):
    """把单通道变成 0/255 掩膜：keep_high=True 表示取「大于阈值」的像素。"""
    if keep_high:
        return channel.point(lambda v: 255 if v > threshold else 0)
    return channel.point(lambda v: 255 if v <= threshold else 0)


def _channel_diff(a, b):
    """两个通道的逐像素绝对差图。"""
    from PIL import ImageChops
    return ImageChops.difference(a, b)


def analyze_panorama(path: pathlib.Path) -> dict:
    """量一下全景图：均值、左右接缝、银河亮带、星点分布。"""
    from PIL import Image, ImageChops, ImageStat

    img = Image.open(path)
    img.load()
    width, height = img.size
    rgb = img.convert("RGB")
    stat = ImageStat.Stat(rgb)
    mean_rgb = tuple(round(v, 3) for v in stat.mean)

    # —— 左右接缝：全景图 u=0 与 u=1 必须是同一片天空
    left = rgb.crop((0, 0, 1, height))
    right = rgb.crop((width - 1, 0, width, height))
    neighbour = rgb.crop((1, 0, 2, height))
    seam = ImageStat.Stat(ImageChops.difference(left, right))
    seam_mean = seam.mean[0]
    seam_max = max(ImageChops.difference(left, right).getextrema()[i][1] for i in range(3))
    adj = ImageStat.Stat(ImageChops.difference(left, neighbour)).mean[0]

    # —— 逐行亮度剖面 → 银河亮带
    lum = rgb.convert("L")
    rows = [ImageStat.Stat(lum.crop((0, y, width, y + 1))).mean[0] for y in range(height)]
    ordered = sorted(rows)
    median = ordered[height // 2]
    peak_row = max(range(height), key=lambda y: rows[y])
    band_rows = [y for y in range(height) if rows[y] >= median * 1.6 + 1.0]

    # —— 星点：亮度直方图
    hist = lum.histogram()
    total = width * height
    stars_soft = sum(hist[24:])
    stars_mid = sum(hist[64:])
    stars_bright = sum(hist[128:])
    stars_hot = sum(hist[220:])
    levels = sum(1 for c in hist if c)
    # 通道直方图的非零个数 = 颜色层次
    color_levels = sum(len([c for c in ch.histogram() if c]) for ch in rgb.split())

    return {
        "path": path,
        "size": (width, height),
        "mode": img.mode,
        "mean_rgb": mean_rgb,
        "mean_lum": round(stat.mean[0], 3) if False else round(sum(stat.mean) / 3.0, 3),
        "seam_mean_abs_diff": round(seam_mean, 4),
        "seam_max_abs_diff": seam_max,
        "adjacent_col_mean_abs_diff": round(adj, 4),
        "row_median_lum": round(median, 3),
        "row_peak_lum": round(rows[peak_row], 3),
        "peak_row": peak_row,
        "band_rows": (min(band_rows), max(band_rows)) if band_rows else None,
        "band_rows_count": len(band_rows),
        "stars_soft": stars_soft,
        "stars_mid": stars_mid,
        "stars_bright": stars_bright,
        "stars_hot": stars_hot,
        "lum_levels": levels,
        "color_levels": color_levels,
        "total": total,
    }


def analyze_planet(path: pathlib.Path) -> dict:
    """量一下行星图：海陆分布、冰盖、云量、左右接缝。"""
    from PIL import Image, ImageChops, ImageStat

    img = Image.open(path)
    img.load()
    width, height = img.size
    rgb = img.convert("RGB")
    r, g, b = rgb.split()
    total = width * height
    stat = ImageStat.Stat(rgb)

    # —— 冰盖：三个通道都很亮
    ice = ImageChops.darker(ImageChops.darker(_mask(r, True, 140), _mask(g, True, 140)),
                            _mask(b, True, 140))
    rest = ImageChops.invert(ice)          # 非冰面
    # —— 海陆：冰面之外，蓝占优 = 海，绿/褐占优 = 陆
    blue_over_green = ImageChops.subtract(b, g).point(lambda v: 255 if v > 0 else 0)
    green_over_blue = ImageChops.subtract(g, b).point(lambda v: 255 if v > 0 else 0)
    ocean = ImageChops.darker(blue_over_green, rest)
    land = ImageChops.darker(green_over_blue, rest)

    alpha = img.getchannel("A")
    ahist = alpha.histogram()
    clouds = sum(ahist[128:])
    cloud_soft = sum(ahist[16:])

    # —— 左右接缝
    left = rgb.crop((0, 0, 1, height))
    right = rgb.crop((width - 1, 0, width, height))
    seam = ImageStat.Stat(ImageChops.difference(left, right)).mean[0]

    return {
        "path": path,
        "size": (width, height),
        "mode": img.mode,
        "mean_rgb": tuple(round(v, 3) for v in stat.mean),
        "mean_alpha": round(sum(ahist[i] * i for i in range(256)) / 255.0 / total, 3),
        "ocean_frac": round(_count(ocean) / total, 4),
        "land_frac": round(_count(land) / total, 4),
        "ice_frac": round(_count(ice) / total, 4),
        "cloud_frac": round(clouds / total, 4),
        "cloud_any_frac": round(cloud_soft / total, 4),
        "alpha_levels": len([c for c in ahist if c]),
        "seam_mean_abs_diff": round(seam, 4),
    }


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def report_panorama(info: dict) -> None:
    print("  [全景] %s %dx%d %s" % (info["path"].name, info["size"][0], info["size"][1], info["mode"]))
    print("      平均 RGB = %s   平均亮度 = %.3f / 255" % (info["mean_rgb"], info["mean_lum"]))
    print("      左右接缝：首列 vs 末列 平均差 %.4f、最大差 %d"
          % (info["seam_mean_abs_diff"], info["seam_max_abs_diff"]))
    print("      （参照）相邻两列 平均差 %.4f → 接缝与普通相邻列同量级即为无缝"
          % info["adjacent_col_mean_abs_diff"])
    print("      逐行亮度：中位 %.2f，峰值 %.2f（第 %d 行），亮带行 %s（%d 行）"
          % (info["row_median_lum"], info["row_peak_lum"], info["peak_row"],
             info["band_rows"], info["band_rows_count"]))
    print("      星点像素：>=24 亮度 %d、>=64 %d、>=128 %d、>=220 %d（共 %d 纹素）"
          % (info["stars_soft"], info["stars_mid"], info["stars_bright"],
             info["stars_hot"], info["total"]))
    print("      亮度层级 %d 级，颜色层级 %d 级" % (info["lum_levels"], info["color_levels"]))


def report_planet(info: dict) -> None:
    print("  [行星] %s %dx%d %s" % (info["path"].name, info["size"][0], info["size"][1], info["mode"]))
    print("      平均 RGB = %s   平均 alpha = %.3f" % (info["mean_rgb"], info["mean_alpha"]))
    print("      海 %.1f%%  陆 %.1f%%  冰盖 %.1f%%（三者互斥，覆盖 %.1f%% 画面）"
          % (info["ocean_frac"] * 100, info["land_frac"] * 100, info["ice_frac"] * 100,
             (info["ocean_frac"] + info["land_frac"] + info["ice_frac"]) * 100))
    print("      云（alpha>=50%%）%.1f%%，有云像素 %.1f%%，alpha 层级 %d 级"
          % (info["cloud_frac"] * 100, info["cloud_any_frac"] * 100, info["alpha_levels"]))
    print("      左右接缝：首列 vs 末列 平均差 %.4f" % info["seam_mean_abs_diff"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--analyze", action="store_true", help="只体检已有贴图，不重新渲染")
    args = ap.parse_args()

    TEX_DIR.mkdir(parents=True, exist_ok=True)
    if not args.analyze:
        try:
            ctx = make_context()
        except ImportError:
            print("moderngl not installed - cannot bake textures", file=sys.stderr)
            return 1
        print("GL %s | %s" % (ctx.info.get("GL_VERSION"), ctx.info.get("GL_RENDERER")))
        pano = bake_panorama(ctx)
        pano.save(PANORAMA_PATH, optimize=False)
        print("  -> %s (%dx%d %s)" % (PANORAMA_PATH, pano.width, pano.height, pano.mode))
        planet = bake_planet(ctx)
        planet.save(PLANET_PATH, optimize=False)
        print("  -> %s (%dx%d %s)" % (PLANET_PATH, planet.width, planet.height, planet.mode))

    print("== 数值体检 ==")
    report_panorama(analyze_panorama(PANORAMA_PATH))
    report_planet(analyze_planet(PLANET_PATH))
    print("== sha256 ==")
    print("  %s  %s" % (sha256(PANORAMA_PATH), PANORAMA_PATH.name))
    print("  %s  %s" % (sha256(PLANET_PATH), PLANET_PATH.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
