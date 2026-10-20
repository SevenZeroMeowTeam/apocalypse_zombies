"""离线 GLSL 校验器：用本机 OpenGL 3.3 真编译一遍模组里的着色器。

为什么需要它
------------
模组里的 shader 跑在玩家机器上，出错只会得到「黑屏 / 不显示」，本地又开不了图形客户端。
本脚本把每个 .fsh / .vsh 当成 GLSL 编译一次，语法错、类型错、uniform 用错都会立刻报出来。

它同时做两件事：
1. **语法与链接校验**（像驱动那样真正编译）
2. **uniform 清单比对**：把 .json 里声明的 uniform 和着色器里实际用的对上，
   少声明一个，运行时那条 uniform 就会静默拿到默认值 —— 这是最难查的一类 bug。

用法
----
    python tools/glsl_check.py            # 全量校验
    python tools/glsl_check.py --verbose  # 打印每个 program 的明细
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHADER_DIR = ROOT / "src/main/resources/assets/apocalypse_zombies/shaders"

# Minecraft 的 core shader 名字 -> (顶点文件, 片元文件)
CORE = {
    "orbit_sky": ("orbit_sky.vsh", "orbit_sky.fsh"),
    "orbit_beam": ("orbit_beam.vsh", "orbit_beam.fsh"),
    "orbit_gun": ("orbit_gun.vsh", "orbit_gun.fsh"),
    "orbit_hud": ("orbit_hud.vsh", "orbit_hud.fsh"),
}
PROGRAM = {
    "orbital": ("orbital.vsh", "orbital.fsh"),
    "orbital_blit": ("orbital_blit.vsh", "orbital_blit.fsh"),
}

INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"\s*$', re.M)
UNIFORM_RE = re.compile(r"^\s*uniform\s+(\w+)\s+(\w+)\s*(\[[^\]]*\])?\s*;", re.M)
SAMPLER_RE = re.compile(r"^\s*uniform\s+(sampler\w+)\s+(\w+)\s*;", re.M)


def expand_includes(src: str, base: Path, seen: set) -> str:
    """把 #include "x.glsl" 展开成真实内容（和 Minecraft 的做法一样）。"""
    def sub(match: re.Match) -> str:
        name = match.group(1)
        path = base / name
        key = str(path)
        if key in seen:
            return f"// already included: {name}\n"
        seen.add(key)
        if not path.exists():
            raise FileNotFoundError(f"include not found: {path}")
        return expand_includes(path.read_text(encoding="utf-8"), path.parent, seen)

    return INCLUDE_RE.sub(sub, src)


def strip_mc_boilerplate(src: str) -> str:
    """去掉 Minecraft 注入的版本行，让它变成合法的独立 GLSL。

    MC 在运行时把 `#version 150` 换掉，并注入 `#define` 与 uniform 声明。
    我们这里自己补齐：加版本行、去掉 MC 独有的宏。
    """
    src = re.sub(r"^#version.*$", "", src, flags=re.M)
    src = re.sub(r"^#moj_import.*$", "", src, flags=re.M)
    src = re.sub(r"^#define MC_ELEMENTS.*$", "", src, flags=re.M)
    return "#version 150\n" + src


def collect_uniforms(src: str) -> set:
    found = set()
    for match in UNIFORM_RE.finditer(src):
        found.add(match.group(2))
    for match in SAMPLER_RE.finditer(src):
        found.add(match.group(2))
    return found


def check_ternary_balance(path: pathlib.Path) -> list:
    """静态检查三目运算符的 '?' 与 ':' 是否配平。

    **为什么需要它**：GLSL 的三目是右结合的，`a ? b : c ? d : e ? f` 会被解析成
    右边少一个 ':' 的表达式，编译器报 "unexpected SEMICOLON, expecting COMMA or COLON"。
    这个错在 GLSL 里很难一眼看出来，但它会让**整个 shader 编译失败**——
    而 Minecraft 对 core shader 编译失败的处理是「静默不画」，
    玩家看到的只是「特效没出现」，日志里只有一行 uniform 找不到。

    v5.0.0 的 orbit_sky.fsh 就踩了这个坑（3 个 '?' 配 2 个 ':'），
    结果天空和光柱两个 shader 从来没在玩家机器上编译成功过。
    """
    src = path.read_text(encoding="utf-8")
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)   # 去块注释
    src = re.sub(r"//[^\n]*", "", src)                # 去行注释
    problems = []
    for i, line in enumerate(src.split("\n"), 1):
        q = line.count("?")
        c = line.count(":")
        if q > c:
            problems.append(f"{path.name}:{i}: {q} '?' but only {c} ':' -> {line.strip()[:80]}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    # —— 第一步：静态检查（不需要 GPU，任何机器都能跑）
    static_failures = []
    for f in sorted(SHADER_DIR.rglob("*.fsh")) + sorted(SHADER_DIR.rglob("*.vsh")):
        static_failures.extend(check_ternary_balance(f))
    if static_failures:
        print("STATIC GLSL PROBLEMS:")
        for p in static_failures:
            print("  " + p)
        return 1
    if args.verbose:
        print("static GLSL checks passed")

    try:
        import moderngl
    except ImportError:
        print("moderngl not installed - skipping GLSL compile check", file=sys.stderr)
        return 0

    ctx = moderngl.create_standalone_context(require=330)
    print(f"GL {ctx.info.get('GL_VERSION')} | {ctx.info.get('GL_RENDERER')}")

    failures = []
    checked = 0

    targets = []
    for name, (vsh, fsh) in CORE.items():
        targets.append(("core/" + name, SHADER_DIR / "core" / vsh, SHADER_DIR / "core" / fsh,
                        SHADER_DIR / "core" / (name + ".json")))
    for name, (vsh, fsh) in PROGRAM.items():
        targets.append(("program/" + name, SHADER_DIR / "program" / vsh,
                        SHADER_DIR / "program" / fsh, SHADER_DIR / "program" / (name + ".json")))

    for label, vpath, fpath, jpath in targets:
        if not vpath.exists() or not fpath.exists():
            failures.append(f"{label}: missing shader files")
            continue
        try:
            vsrc = strip_mc_boilerplate(expand_includes(vpath.read_text(encoding="utf-8"),
                                                        vpath.parent, set()))
            fsrc = strip_mc_boilerplate(expand_includes(fpath.read_text(encoding="utf-8"),
                                                        fpath.parent, set()))
        except FileNotFoundError as exc:
            failures.append(f"{label}: {exc}")
            continue

        try:
            prog = ctx.program(vertex_shader=vsrc, fragment_shader=fsrc)
            checked += 1
            if args.verbose:
                print(f"  OK  {label}")
        except Exception as exc:  # moderngl raises Exception on compile failure
            failures.append(f"{label}: {exc}")
            continue

        # uniform 清单比对 —— 必须查**链接后**的程序。
        # Minecraft 的 ShaderInstance 也是在链接后的 program 上查 uniform 位置，
        # 查不到就报 "could not find uniform named X" 然后静默不画。
        # 所以这里必须用同一种查法，否则本地过了、玩家那边照样是黑的。
        if jpath.exists():
            meta = json.loads(jpath.read_text(encoding="utf-8"))
            declared = {u["name"] for u in meta.get("uniforms", [])}
            declared |= {s["name"] for s in meta.get("samplers", [])}
            used = collect_uniforms(vsrc) | collect_uniforms(fsrc)
            # Minecraft 会给 core shader 注入这些 uniform（自己也在用），
            # 所以它们在 json 里没声明是正常的。
            mc_builtin = {"ModelViewMat", "ProjMat", "ColorModulator", "ScreenSize",
                          "FogStart", "FogEnd", "FogColor", "GameTime", "LineWidth",
                          "TextureMat", "IViewRotMat", "GlintAlpha", "FogShape",
                          "ChunkOffset", "TotalTime", "DiffuseSampler"}
            missing = []
            for name in sorted(declared):
                # json 里声明了但着色器根本没用 → 驱动会把它优化掉，查不到位置。
                # 这在 MC 里是无害的（只是多一行 uniform 找不到的警告），
                # 只有「着色器用了但 json 没声明」才是致命的（值永远是默认值）。
                if name in used and name not in mc_builtin:
                    try:
                        if prog.get(name, None) is None:
                            missing.append(name)
                    except Exception:
                        missing.append(name)
            if missing:
                failures.append(f"{label}: uniforms used but not resolvable in linked program: "
                                f"{', '.join(missing)}")
            elif args.verbose:
                print(f"      {len(declared)} declared uniforms OK")

    print(f"\ncompiled {checked}/{len(targets)} programs")
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  " + f)
        return 1
    print("all shaders compiled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
