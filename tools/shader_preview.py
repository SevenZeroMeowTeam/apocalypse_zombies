"""离线把模组的着色器渲染成 PNG —— 不开 Minecraft 也能看到效果。

为什么需要它
------------
本模组的演出层大半是 shader 写的，但 **shader 只在玩家的机器上编译**。
本机开不了图形客户端（本目录的沙箱不允许起窗口），于是以前只能「写完 → 打包 →
装到游戏里 → 让玩家自己看」，出错也是玩家先看到。

这个脚本用本机的 OpenGL 3.3 上下文（moderngl）把 shader 真正跑一遍：
- 走的是**和 Minecraft 一样的 GLSL 150 管线**（同一个 Mesa 驱动，同一个显卡）；
- 编译失败会在这里就报出来，不用等玩家；
- 编译通过就**真的渲染一帧存成 PNG**，效果直接能看。

用法
----
    python tools/shader_preview.py                     # 渲染全部
    python tools/shader_preview.py --only sky          # 只渲染天幕
    python tools/shader_preview.py --list              # 列出可渲染项
"""
from __future__ import annotations

import argparse
import math
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHADERS = ROOT / "src/main/resources/assets/apocalypse_zombies/shaders"
OUT_DIR = ROOT / "build/shader-preview"

# —— 全屏三角形/四边形的顶点（和 MC 的 PostPass 一样用 NDC）
QUAD = [(-1.0, -1.0), (3.0, -1.0), (-1.0, 3.0)]


def make_context():
    import moderngl
    return moderngl.create_standalone_context(require=330)


def load(path: pathlib.Path) -> str:
    """读取 shader 源码。Minecraft 会在 #version 之外注入 uniform，这里只做最小处理。"""
    return path.read_text(encoding="utf-8")


def build_program(ctx, vsrc: str, fsrc: str, uniforms: dict):
    """编译 program 并设置 uniform。uniform 名不存在时静默跳过（和 MC 的 safeGetUniform 一致）。"""
    prog = ctx.program(vertex_shader=vsrc, fragment_shader=fsrc)
    for name, value in uniforms.items():
        if name not in prog:
            continue
        try:
            if hasattr(value, "read"):          # 贴图 → 绑到 sampler
                # moderngl 5.x：sampler uniform 要用 u.texture = tex 并 tex.use(unit)
                prog[name].texture = value
                value.use(0)
            elif isinstance(value, bool):
                prog[name].value = float(value)
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


def render(ctx, prog, width: int, height: int, uniforms: dict, label: str):
    """渲染一帧到 PNG。"""
    import moderngl
    from PIL import Image

    fbo = ctx.simple_framebuffer((width, height))
    fbo.use()
    ctx.clear(0.0, 0.0, 0.0, 0.0)

    # 全屏三角形：NDC 坐标直接当顶点属性
    vertices = [(-1.0, -1.0), (3.0, -1.0), (-1.0, 3.0)]
    data = b"".join(struct.pack("<2f", x, y) for x, y in vertices)
    vbo = ctx.buffer(data)
    try:
        vao = ctx.vertex_array(prog, [(vbo, "2f", "in_position")])
        vao.render(moderngl.TRIANGLES, 3)
    except Exception as exc:
        print(f"    draw failed: {exc}")
        return None
    data = fbo.read(components=3, alignment=1)
    img = Image.frombytes("RGB", (width, height), data).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / (label + ".png")
    img.save(path)
    return path


def preview_orbit_sky(ctx, width, height):
    """轨道维度的程序化天幕：三层星场 + 银河 + 地球 + 月球。"""
    vsrc = load(SHADERS / "core/orbit_sky.vsh")
    fsrc = load(SHADERS / "core/orbit_sky.fsh")
    # 把 MC 注入的 Position 属性改成本脚本用的名字
    vsrc = vsrc.replace("in vec3 Position;", "in vec2 in_position;")
    vsrc = vsrc.replace("vUV = Position.xy;", "vUV = in_position;")
    vsrc = vsrc.replace("gl_Position = vec4(Position.xy, 0.9999, 1.0);",
                        "gl_Position = vec4(in_position, 0.9999, 1.0);")
    prog = build_program(ctx, vsrc, fsrc, {
        "CamForward": (0.0, 0.0, 1.0),
        "CamRight": (1.0, 0.0, 0.0),
        "CamUp": (0.0, 1.0, 0.0),
        "TanHalf": math.tan(math.radians(70.0) * 0.5),
        "Aspect": width / height,
        "Alpha": 1.0,
        "GameTime": 12.0,
    })
    return render(ctx, prog, width, height, {}, "orbit_sky")


def preview_orbit_beam(ctx, width, height):
    """实体光柱：世界空间圆柱 quad 的四段体积渐变。"""
    vsrc = load(SHADERS / "core/orbit_beam.vsh")
    fsrc = load(SHADERS / "core/orbit_beam.fsh")
    # 本脚本用「包围盒 NDC + UV0 角向/高度」模拟 Java 那边的圆柱 quad
    vsrc = """
#version 150
in vec2 in_position;
out vec2 texCoord0;
out vec4 vertexColor;
void main() {
    // 角向：x 方向 0..1 绕柱一周；高度：y 方向 0..1
    float ang = (in_position.x * 0.5 + 0.5);
    float h = (in_position.y * 0.5 + 0.5);
    texCoord0 = vec2(ang, h);
    vertexColor = vec4(1.0);
    gl_Position = vec4(in_position, 0.0, 1.0);
}
"""
    prog = build_program(ctx, vsrc, fsrc, {
        "ModelViewMat": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
        "ProjMat": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
        "ColorModulator": (1.0, 1.0, 1.0, 1.0),
        "GameTime": 3.0,
        "Radius": 3.0,
        "Strength": 1.0,
        "Energy": 0.85,
        "Haze": 0.4,
        "Core": (1.0, 0.98, 0.95),
        "Body": (1.0, 0.2, 0.12),
        "Deep": (0.62, 0.0, 0.02),
        "Scanline": 0.35,
    })
    return render(ctx, prog, width, height, {}, "orbit_beam")


def preview_orbital(ctx, width, height):
    """打击合成器：拿一张合成图当输入，跑一遍冲击帧/分级/颗粒。"""
    from PIL import Image
    vsrc = """
#version 150
in vec2 in_position;
out vec2 texCoord;
void main() {
    texCoord = in_position * 0.5 + 0.5;
    gl_Position = vec4(in_position, 0.0, 1.0);
}
"""
    fsrc = load(SHADERS / "program/orbital.fsh")
    # 造一张输入图：暖色渐变 + 几个亮块 + 暗角，模拟「打击瞬间的画面」
    base = Image.new("RGB", (width, height))
    px = base.load()
    for y in range(height):
        for x in range(width):
            u = x / width
            v = y / height
            r = int(40 + 180 * (1.0 - v) * (0.4 + 0.6 * math.sin(u * 6.0) ** 2))
            g = int(30 + 90 * (1.0 - v) * 0.7)
            b = int(60 + 120 * (1.0 - u) * 0.5)
            if 0.42 < u < 0.58 and 0.38 < v < 0.62:
                r, g, b = 245, 235, 220
            px[x, y] = (min(r, 255), min(g, 255), min(b, 255))
    tex = ctx.texture((width, height), 3)
    tex.write(base.tobytes())
    prog = build_program(ctx, vsrc, fsrc, {
        "DiffuseSampler": tex,
        "InSize": (width, height),
        "OutSize": (width, height),
        "Time": 2.0,
        "Strength": 1.0,
        "Radial": 0.6,
        "Chroma": 0.5,
        "Impact": 1.0,
        "Flash": 0.0,
        "Vignette": 0.5,
        "Grade": (0.16, 0.04, 0.01),
        "ZoomBlur": 0.35,
        "Bloom": 0.65,
        "Desaturate": 0.35,
        "Contrast": 0.55,
        "Grain": 0.35,
        "ImpactMode": 0.0,
        "ImpactStrength": 0.9,
        "ImpactCenter": (0.5, 0.5),
        "Exposure": 1.0,
        "Accent": (1.0, 0.33, 0.06),
    })
    path = render(ctx, prog, width, height, {}, "orbital_impact")
    tex.release()
    return path


def _gun_camera(width, height):
    """轨道炮的 3/4 侧视机位：相机完全在枪身空间里，炮口在画面左侧。"""
    pos = (-22.0, 8.7, -9.0)
    target = (0.0, 0.0, -4.5)
    fwd = [target[i] - pos[i] for i in range(3)]
    n = math.sqrt(sum(c * c for c in fwd))
    fwd = [c / n for c in fwd]
    # right = normalize(cross(fwd, worldUp))，up = cross(right, fwd)
    right = [-fwd[2], 0.0, fwd[0]]
    n = math.sqrt(sum(c * c for c in right))
    right = [c / n for c in right]
    up = [
        right[1] * fwd[2] - right[2] * fwd[1],
        right[2] * fwd[0] - right[0] * fwd[2],
        right[0] * fwd[1] - right[1] * fwd[0],
    ]
    tan_half = math.tan(math.radians(45.0) * 0.5)
    return {
        "CamPos": tuple(pos),
        "CamForward": tuple(fwd),
        "CamRight": tuple(right),
        "CamUp": tuple(up),
        "TanHalf": tan_half,
        "Aspect": width / height,
        # 每像素的张切空间尺寸 = 2*tanHalf/画面高度
        "PixelSize": 2.0 * tan_half / height,
        "Charge": 0.80,
        "Fired": -1.0,
        "GameTime": 7.5,
        "Alpha": 1.0,
    }


def _render_gun(ctx, width, height, label, over):
    """渲染轨道炮近景。over = 需要覆盖的 uniform。"""
    vsrc = load(SHADERS / "core/orbit_gun.vsh")
    fsrc = load(SHADERS / "core/orbit_gun.fsh")
    # 本脚本的顶点属性叫 in_position（MC 里叫 Position）
    vsrc = vsrc.replace("in vec3 Position;", "in vec2 in_position;")
    vsrc = vsrc.replace("vUV = Position.xy;", "vUV = in_position;")
    vsrc = vsrc.replace("gl_Position = vec4(Position.xy, 0.9999, 1.0);",
                        "gl_Position = vec4(in_position, 0.9999, 1.0);")
    uniforms = _gun_camera(width, height)
    uniforms.update(over)
    prog = build_program(ctx, vsrc, fsrc, uniforms)
    return render(ctx, prog, width, height, {}, label)


def preview_orbit_gun(ctx, width, height):
    """轨道炮「弧光长矛」：解析 SDF 炮体（充能中，充电波正沿炮身向炮口推进）。"""
    return _render_gun(ctx, width, height, "orbit_gun", {})


def preview_orbit_gun_fired(ctx, width, height):
    """轨道炮：开火瞬间（炮口闪光 + 后坐 + 出膛弹道）。"""
    return _render_gun(ctx, width, height, "orbit_gun_fired",
                       {"Charge": 1.0, "Fired": 0.06})


def analyze_gun_png(path, label="orbit_gun"):
    """用 Pillow 量一下渲染结果：覆盖率、亮度、剪影形状。"""
    from PIL import Image

    img = Image.open(path).convert("RGB")
    w, h = img.size
    px = img.load()
    bright = []
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            bright.append((r, g, b))

    def lum(c):
        return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255.0

    # 背景 = 全黑（shader 在没打到炮的地方写 vec4(0,0,0,0)）
    mask = [[max(bright[y * w + x]) > 8 for x in range(w)] for y in range(h)]
    total = w * h
    cover = sum(sum(row) for row in mask) / total
    mean_lum = sum(lum(c) for c in bright) / total
    gun_lum = [lum(bright[y * w + x]) for y in range(h) for x in range(w)
               if mask[y][x]]
    peak = max((max(c) for c in bright), default=0)
    hot = sum(1 for c in bright if max(c) > 200) / total
    cyan = sum(1 for c in bright if c[2] > 40 and c[2] > c[0] * 1.35) / total

    # 剪影：包围盒、逐列高度
    cols = [x for x in range(w) if any(mask[y][x] for y in range(h))]
    rows = [y for y in range(h) if any(mask[y][x] for x in range(w))]
    info = {
        "label": label,
        "size": f"{w}x{h}",
        "coverage": cover,
        "mean_lum": mean_lum,
        "gun_mean_lum": (sum(gun_lum) / len(gun_lum)) if gun_lum else 0.0,
        "peak": peak,
        "hot_frac": hot,
        "cyan_frac": cyan,
    }
    if cols:
        x0, x1 = cols[0], cols[-1]
        info["bbox"] = (x0, min(rows), x1, max(rows))
        info["aspect"] = (x1 - x0) / max(1, max(rows) - min(rows))
        col_h = []
        for x in range(x0, x1 + 1):
            ys = [y for y in range(h) if mask[y][x]]
            col_h.append((max(ys) - min(ys) + 1) if ys else 0)
        span = len(col_h)
        muzzle = sum(col_h[:max(1, span // 5)]) / max(1, span // 5)
        mid = sum(col_h[span // 2 - span // 10: span // 2 + span // 10]) / max(1, span // 5)
        info["muzzle_h"] = muzzle
        info["mid_h"] = mid
        info["muzzle_wider"] = muzzle > mid * 1.15
    print(f"  [{label}] {info['size']}  非背景像素 {cover*100:.1f}%  "
          f"平均亮度 {mean_lum:.4f}  枪体平均亮度 {info['gun_mean_lum']:.4f}  "
          f"峰值 {peak}  过曝像素 {hot*100:.2f}%  青色(能量辉光) {cyan*100:.2f}%")
    if "bbox" in info:
        print(f"      剪影包围盒 {info['bbox']}  长宽比 {info['aspect']:.2f}  "
              f"炮口端高度 {info['muzzle_h']:.1f}px vs 中段 {info['mid_h']:.1f}px  "
              f"炮口更宽: {info['muzzle_wider']}")
    return info


# ————————————————————————————————————————————————————————————
#  HUD 图形层（core/orbit_hud）：一个形状 = 一个四边形
# ————————————————————————————————————————————————————————————
#
#  布局：名字, 模式, 参数, x, y, 宽, 高, 颜色, 透明度, 取样点x, 取样点y
#  顺序即绘制顺序（投影在面板下面）。
#
#  HUD 形状是**绝对像素坐标**（和 Java 侧一致），所以画布尺寸是固定的：
#  下面的取样点坐标都按这个画布写死。
HUD_CANVAS = (960, 420)
HUD_SHAPES = [
    ("shadowA", 1, 6, 46, 36, 268, 148, 0x05070C, 0.60, 180, 177),
    ("plateA", 0, 6, 60, 50, 240, 120, 0x1B2430, 0.96, 180, 110),
    ("shadowB", 1, 3, 54, 214, 172, 68, 0x05070C, 0.60, 140, 280),
    ("plateB", 0, 3, 60, 220, 160, 56, 0x2E4A5C, 0.96, 140, 248),
    ("plateC", 0, 6, 480, 340, 180, 60, 0x4A3B6B, 0.96, 570, 370),
    ("discFill", 2, 0, 364, 74, 72, 72, 0xE08A3C, 1.0, 400, 110),
    ("discGlow", 2, 2, 464, 74, 72, 72, 0x40E0D0, 1.0, 500, 110),
    ("discRing", 2, 3, 564, 74, 72, 72, 0xE05A8A, 1.0, 600, 76),
    ("arc", 3, 4, 668, 68, 84, 84, 0x49D8FF, 1.0, 710, 70),
    ("reticle", 6, 4, 808, 78, 64, 64, 0xFFD166, 1.0, 840, 110),
    ("rule", 7, 4, 60, 330, 360, 6, 0x9AE66E, 1.0, 100, 333),
]


def _hud_vertex_data(shapes):
    """把形状列表变成顶点数据，编码方式与 Java 侧 OrbitHudShapes 完全一致。"""
    verts = []
    for shape in shapes:
        (_name, mode, param, x, y, w, h, rgb, alpha) = shape[:9]
        packed = (((rgb >> 19) & 0x1F) << 11) | (((rgb >> 10) & 0x3F) << 5) | ((rgb >> 3) & 0x1F)
        hi = (packed >> 8) & 0xFF
        lo = packed & 0xFF
        a8 = max(0, min(255, int(round(alpha * 255.0))))
        state = 0x80 | ((param & 7) << 4) | (mode & 0xF)
        u = w + 0.25
        v = h + 0.25
        corners = [
            ((x, y), (u, v)),
            ((x, y + h), (u, v + 0.5)),
            ((x + w, y + h), (u + 0.5, v + 0.5)),
            ((x + w, y), (u + 0.5, v)),
        ]
        for i in (0, 1, 2, 0, 2, 3):
            (px, py), (uu, vv) = corners[i]
            verts.append((px, py, uu, vv, hi / 255.0, lo / 255.0, a8 / 255.0, state / 255.0))
    return verts


def preview_orbit_hud(ctx, width, height):
    """HUD 图形层：面板 / 投影 / 圆盘 / 进度弧 / 准星 / 标尺。

    HUD 形状用的是**绝对像素坐标**（和 Java 侧一样，布局是固定像素的），
    所以预览必须用 HUD_SHAPES 布局所依据的画布尺寸，否则形状会画到画布外。
    """
    import moderngl
    from PIL import Image

    canvas_w, canvas_h = HUD_CANVAS

    vsrc = """
#version 150
in vec2 in_pos;
in vec2 in_uv;
in vec4 in_color;
uniform vec2 ScreenSize;
out vec2 texCoord0;
out vec4 vertexColor;
void main() {
    vec2 ndc = vec2(in_pos.x / ScreenSize.x * 2.0 - 1.0, 1.0 - in_pos.y / ScreenSize.y * 2.0);
    gl_Position = vec4(ndc, 0.0, 1.0);
    texCoord0 = in_uv;
    vertexColor = in_color;
}
"""
    fsrc = load(SHADERS / "core/orbit_hud.fsh")
    prog = build_program(ctx, vsrc, fsrc, {
        "ColorModulator": (1.0, 1.0, 1.0, 1.0),
        "ScreenSize": (float(canvas_w), float(canvas_h)),
    })

    verts = _hud_vertex_data(HUD_SHAPES)
    data = b"".join(struct.pack("<8f", *v) for v in verts)
    vbo = ctx.buffer(data)

    fbo = ctx.simple_framebuffer((canvas_w, canvas_h))
    fbo.use()
    ctx.clear(0.0, 0.0, 0.0, 0.0)
    ctx.enable(ctx.BLEND)
    # moderngl 5.x 的 blend_func 只有 setter 可用
    ctx.blend_func = (ctx.SRC_ALPHA, ctx.ONE_MINUS_SRC_ALPHA)
    vao = ctx.vertex_array(prog, [(vbo, "2f 2f 4f", "in_pos", "in_uv", "in_color")])
    vao.render(moderngl.TRIANGLES, len(verts))
    data = fbo.read(components=4, alignment=1)
    img = Image.frombytes("RGBA", (canvas_w, canvas_h), data).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "orbit_hud.png"
    img.save(path)
    return path


def analyze_hud_png(path):
    """量一下 HUD 预览图：颜色种类、圆角轮廓、进度弧填充、抗锯齿中间值。"""
    from PIL import Image

    img = Image.open(path).convert("RGBA")
    w, h = img.size
    data = img.load()

    exact = set()
    quant = set()
    aa = 0
    opaque = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = data[x, y]
            if 0 < a < 255:
                aa += 1
            if a >= 200:
                opaque += 1
                exact.add((r, g, b))
                quant.add((r >> 4, g >> 4, b >> 4))

    # 面板 C（没有投影垫着）用来量圆角：方角的话，左上角应该和内部一样满
    corner = data[480, 340][3]       # 左上角：圆角切掉的地方
    edge = data[570, 340][3]         # 上边中点
    inner = data[570, 370][3]        # 面板内部
    # 方角面板的话，左上角应该和内部一样亮
    rounded = corner < 40 and edge > 200 and inner > 200 and (inner - corner) > 150

    # 进度弧：中心 (710,110)，环半径 40，八个方向各采一个点
    arc_pts = []
    for k in range(8):
        a = k * math.pi / 4.0
        sx = int(round(710.0 + 40.0 * math.sin(a)))
        sy = int(round(110.0 - 40.0 * math.cos(a)))
        r, g, b, al = data[sx, sy]
        arc_pts.append((k * 45, al, r + g + b))
    lit = [p for p in arc_pts if p[1] >= 200 and p[2] > 200]
    dark = [p for p in arc_pts if p[1] >= 200 and p[2] <= 200]
    partial = len(lit) >= 2 and len(dark) >= 2

    # 形状颜色：每个形状取一个代表点，按颜色距离分组
    groups = []
    for shape in HUD_SHAPES:
        name = shape[0]
        r, g, b, a = data[shape[9], shape[10]]
        if a < 8:
            continue
        for grp in groups:
            if (abs(r - grp[0][0]) + abs(g - grp[0][1]) + abs(b - grp[0][2])) < 60:
                grp[1].append(name)
                break
        else:
            groups.append([(r, g, b), [name]])

    print(f"  [orbit_hud] {w}x{h}  不透明像素 {opaque}  "
          f"不同颜色(精确) {len(exact)} / (量化) {len(quant)}  "
          f"形状颜色 {len(groups)} 种")
    for c, members in groups:
        print(f"      {members} -> RGB{c}")
    print(f"      圆角：角 alpha={corner} 边 alpha={edge} 内部 alpha={inner} "
          f"-> {'圆角(不是方角)' if rounded else '方角?!'}")
    print(f"      进度弧：亮段 {len(lit)}/8 暗段 {len(dark)}/8 "
          f"-> {'部分填充' if partial else '没有部分填充?!'}")
    print(f"      抗锯齿：0<alpha<255 的像素 {aa} 个 "
          f"-> {'有中间值(边缘被抗锯齿)' if aa > 100 else '没有中间值?!'}")
    return {
        "distinct_exact": len(exact),
        "distinct_quant": len(quant),
        "shape_colours": len(groups),
        "aa_pixels": aa,
        "corner_alpha": corner,
        "edge_alpha": edge,
        "inner_alpha": inner,
        "rounded": rounded,
        "arc_lit": len(lit),
        "arc_dark": len(dark),
        "arc_partial": partial,
    }


PREVIEWS = {
    "sky": ("轨道维度程序化天幕", preview_orbit_sky),
    "beam": ("实体光柱（体积渐变）", preview_orbit_beam),
    "hud": ("HUD 图形层（面板/圆盘/进度弧/准星/标尺）", preview_orbit_hud),
    "gun": ("轨道炮「弧光长矛」（解析 SDF 炮体 · 充能中）", preview_orbit_gun),
    "gun_fired": ("轨道炮：开火瞬间（闪光 + 后坐 + 弹道）", preview_orbit_gun_fired),
    "orbital": ("打击合成器（冲击帧 + 分级）", preview_orbital),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=sorted(PREVIEWS), action="append")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=540)
    args = ap.parse_args()

    if args.list:
        for key, (desc, _) in sorted(PREVIEWS.items()):
            print(f"  {key:10s} {desc}")
        return 0

    try:
        ctx = make_context()
    except ImportError:
        print("moderngl not installed - cannot render previews", file=sys.stderr)
        return 1

    print(f"GL {ctx.info.get('GL_VERSION')} | {ctx.info.get('GL_RENDERER')}")
    keys = args.only or sorted(PREVIEWS)
    failures = 0
    for key in keys:
        desc, fn = PREVIEWS[key]
        print(f"[{key}] {desc}")
        try:
            path = fn(ctx, args.width, args.height)
            if path:
                print(f"    -> {path}")
                if key.startswith("gun"):
                    analyze_gun_png(path, key)
                if key == "hud":
                    analyze_hud_png(path)
            else:
                failures += 1
        except Exception as exc:
            print(f"    FAILED: {exc}")
            failures += 1
    print(f"\n{len(keys) - failures}/{len(keys)} previews rendered")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
