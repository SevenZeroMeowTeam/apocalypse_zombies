#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线渲染「太空全景」pass —— 用真正要进游戏的贴图，出真实效果图。

这个脚本同时是**验证工具**：
它把 `orbit_space.fsh` 用真实的 `space_panorama.png` / `planet_albedo.png` 跑一遍，
出图后用数值检查「地球是不是真的在画面里」「大气边缘有没有泛蓝」
—— 这两件事在游戏里是看不见的，只能靠这里确认。

用法：
    python tools/space_preview.py
"""
from __future__ import annotations

import math
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SH = ROOT / "src/main/resources/assets/apocalypse_zombies/shaders"
ENV = ROOT / "src/main/resources/assets/apocalypse_zombies/textures/environment"
OUT = ROOT / "build/shader-preview"

try:
    import moderngl
    from PIL import Image
except ImportError:
    print("moderngl / Pillow not installed", file=sys.stderr)
    raise SystemExit(2)


def camera_orbit(t: float) -> tuple:
    """模拟卫星绕飞：位置绕 Y 转，抬头看地球。"""
    orbit = t * 0.035
    r = 1.35
    cam = (math.sin(orbit) * r, 0.28 + math.sin(t * 0.11) * 0.05, math.cos(orbit) * r)
    # 看向地球中心
    fwd = (-cam[0], -cam[1], -cam[2])
    n = math.sqrt(sum(c * c for c in fwd)) or 1.0
    fwd = tuple(c / n for c in fwd)
    # right = normalize(cross(fwd, worldUp))
    up_w = (0.0, 1.0, 0.0)
    right = (fwd[1] * up_w[2] - fwd[2] * up_w[1],
             fwd[2] * up_w[0] - fwd[0] * up_w[2],
             fwd[0] * up_w[1] - fwd[1] * up_w[0])
    n = math.sqrt(sum(c * c for c in right)) or 1.0
    right = tuple(c / n for c in right)
    up = (right[1] * fwd[2] - right[2] * fwd[1],
          right[2] * fwd[0] - right[0] * fwd[2],
          right[0] * fwd[1] - right[1] * fwd[0])
    return cam, fwd, right, up


def render(ctx, width: int, height: int, t: float, reveal: float = 1.0, alpha: float = 1.0):
    # 预览里把顶点属性改名（MC 用 Position，moderngl 用 in_position）
    vs = (SH / "core/orbit_space.vsh").read_text(encoding="utf-8")
    vs = vs.replace("in vec3 Position;", "in vec2 in_position;").replace("Position.xy", "in_position")
    fs = (SH / "core/orbit_space.fsh").read_text(encoding="utf-8")
    prog = ctx.program(vertex_shader=vs, fragment_shader=fs)

    pano = Image.open(ENV / "space_panorama.png").convert("RGB")
    planet = Image.open(ENV / "planet_albedo.png").convert("RGBA")
    tex_pano = ctx.texture(pano.size, 3)
    tex_pano.write(pano.tobytes())
    tex_planet = ctx.texture(planet.size, 4)
    tex_planet.write(planet.tobytes())

    cam, fwd, right, up = camera_orbit(t)
    fov = 70.0
    tan_half = math.tan(math.radians(fov) * 0.5)
    aspect = width / height

    prog["CamPos"].value = tuple(cam)
    prog["CamForward"].value = tuple(fwd)
    prog["CamRight"].value = tuple(right)
    prog["CamUp"].value = tuple(up)
    prog["TanHalf"].value = tan_half
    prog["Aspect"].value = aspect
    prog["Alpha"].value = alpha
    prog["Reveal"].value = reveal
    # moderngl 5.x：sampler 用 u.texture = tex + tex.use(unit)
    prog["Panorama"].texture = tex_pano
    prog["PlanetMap"].texture = tex_planet
    tex_pano.use(0)
    tex_planet.use(1)

    fbo = ctx.simple_framebuffer((width, height))
    fbo.use()
    ctx.clear(0.0, 0.0, 0.0, 1.0)
    data = b"".join(struct.pack("<2f", x, y) for x, y in
                    [(-1, -1), (3, -1), (-1, 3)])
    vbo = ctx.buffer(data)
    vao = ctx.vertex_array(prog, [(vbo, "2f", "in_position")])
    vao.render(moderngl.TRIANGLES, 3)
    raw = fbo.read(components=3, alignment=1)
    img = Image.frombytes("RGB", (width, height), raw).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    tex_pano.release()
    tex_planet.release()
    return img


def analyse(img, label):
    px = img.load()
    w, h = img.size
    d = list(img.getdata())
    n = len(d)
    lum = [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in d]
    # 地球：画面中央那一块应该有明显的亮度与蓝色
    cx, cy = w // 2, h // 2
    r0 = min(w, h) // 5
    earth = [px[x, y] for y in range(cy - r0, cy + r0, 3) for x in range(cx - r0, cx + r0, 3)]
    blue = sum(1 for r, g, b in earth if b > r + 12)
    bright = sum(1 for r, g, b in earth if (0.2126 * r + 0.7152 * g + 0.0722 * b) > 45)
    print(f"[{label}] {w}x{h}")
    print(f"   整体亮度 p50={sorted(lum)[n//2]:.1f} p95={sorted(lum)[int(n*.95)]:.1f} max={max(lum):.1f}")
    print(f"   中心区(地球): 偏蓝像素 {100*blue/max(1,len(earth)):.1f}%  亮像素 {100*bright/max(1,len(earth)):.1f}%")
    # 大气：地球边缘外一圈应该偏蓝
    ring = [px[x, y] for y in range(cy - r0 - 8, cy - r0 + 2, 2) for x in range(cx - r0, cx + r0, 4)]
    ringblue = sum(1 for r, g, b in ring if b > r + 8)
    print(f"   地球上方(大气): 偏蓝像素 {100*ringblue/max(1,len(ring)):.1f}%")
    return blue / max(1, len(earth)), bright / max(1, len(earth))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ctx = moderngl.create_standalone_context(require=330)
    print(f"GL {ctx.info.get('GL_VERSION')} | {ctx.info.get('GL_RENDERER')}")

    ok = True
    # 1) 正常相位
    img = render(ctx, 960, 540, 12.0)
    path = OUT / "orbit_space.png"
    img.save(path)
    print(f"  -> {path}")
    blue, bright = analyse(img, "orbit_space")
    if blue < 0.15:
        print("   !! 中心区看不到地球（偏蓝像素太少）")
        ok = False
    if bright < 0.2:
        print("   !! 中心区太暗")
        ok = False

    # 2) 揭示中（开场淡入）
    img2 = render(ctx, 960, 540, 12.0, reveal=0.35)
    p2 = OUT / "orbit_space_reveal.png"
    img2.save(p2)
    a = list(img2.getdata())
    b = list(img.getdata())
    mean_a = sum(0.2126 * r + 0.7152 * g + 0.0722 * bb for r, g, bb in a) / len(a)
    mean_b = sum(0.2126 * r + 0.7152 * g + 0.0722 * bb for r, g, bb in b) / len(b)
    print(f"  -> {p2}")
    print(f"   揭示 0.35 的平均亮度 {mean_a:.1f} vs 全亮 {mean_b:.1f} → 淡出生效={'OK' if mean_a < mean_b * 0.7 else 'FAIL'}")
    if not (mean_a < mean_b * 0.7):
        ok = False

    print("\n" + ("SPACE PASS OK" if ok else "SPACE PASS 有问题"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
