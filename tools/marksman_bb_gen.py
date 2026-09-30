#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""骸骨射手几何/贴图驱动：把 tools/marksman_bb_gen.js 送进 Blockbench 跑，再把结果落成仓库文件。

用法:
    python tools/marksman_bb_gen.py            # 建模 + 画图 + 落盘 + 抓一张截图
    python tools/marksman_bb_gen.py --no-shot  # 不抓图

产出:
    art/marksman/marksman_skeleton.geo.json         几何台账（art 侧，唯一真相源）
    art/marksman/marksman_skeleton.png              128×128 贴图
    art/marksman/uv_ledger.json                     逐面 UV + 密度 + 材质台账
    src/main/resources/assets/apocalypse_zombies/geo/marksman_skeleton.geo.json
    src/main/resources/assets/apocalypse_zombies/textures/entity/marksman_skeleton.png
    build/marksman_gen_out.json                     生成器的完整回报（含 png base64 之外的字段）
    build/marksman_shot.png                         当前 Blockbench 视图截图（目检用）

为什么要有这一层：Blockbench 里的生成器只负责「建与画」，schema 组装、闸门与落盘留在 Python，
这样 geo.json 的字节完全由上面那份 JS 的数字决定，可复算、可 review。
"""
import base64
import json
import os
import re
import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import bbmcp_call as bb  # noqa: E402

ART = ROOT / "art" / "marksman"
BUILD = ROOT / "build"
SRC = ROOT / "src" / "main" / "resources" / "assets" / "apocalypse_zombies"
MODEL = "marksman_skeleton"

for d in (ART, BUILD):
    d.mkdir(parents=True, exist_ok=True)

_SID = None


def mcp(tool, args=None):
    global _SID
    if _SID is None:
        _SID = bb.handshake()
    return bb.call(_SID, tool, args or {})


def text_of(res):
    return bb.text_of(res)


def blank_png(path: Path, w=128, h=128, rgba=(44, 44, 44, 255)) -> None:
    """写一张纯色 PNG 当 Blockbench 的贴图底板（生成器会整张重画）。纯标准库，可重复。"""
    raw = b"".join(b"\x00" + bytes(rgba) * w for _ in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    blob = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    path.write_bytes(blob)


def ensure_project() -> dict:
    """工程必须是 geckolib_model 格式。**不要**连续调 MCP 的 create_project —— 那会让 Project
    变成半初始化对象（getMultiFileRuleset is not a function）；原生入口 newProject 才稳。"""
    js = ("(function(){"
          "var before=(typeof Project!=='undefined'&&Project&&typeof Format!=='undefined')?Format.id:null;"
          "var err=null;"
          "if(before!=='geckolib_model'){try{newProject('geckolib_model');}catch(e){err=String(e);}}"
          "return {before:before,after:(typeof Format!=='undefined')?Format.id:null,err:err,"
          "name:(typeof Project!=='undefined'&&Project)?Project.name:null};"
          "})()")
    res = mcp("risky_eval", {"code": js})
    return parse_result(text_of(res))


def parse_result(raw: str):
    doc = json.loads(raw)
    res = doc.get("result", doc)
    if isinstance(res, str):
        try:
            res = json.loads(res)
        except Exception:
            pass
    return res


def run_generator() -> dict:
    src = (HERE / "marksman_bb_gen.js").read_text(encoding="utf-8")
    # risky_eval 的载荷不允许出现 console. 与注释 —— 先剥注释（生成器里没有含 // 或 /* 的字符串字面量）
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    raw = text_of(mcp("risky_eval", {"code": src}))
    (BUILD / "marksman_gen_out.json").write_text(raw, encoding="utf-8")
    return parse_result(raw)


def shot(path: Path, view: str = "main", cam=None, target=None) -> str:
    """抓视图。复用 tools/bb_shot.py —— capture_app_screenshot 在 1.8.1 上回空块，
    要看模型得用 capture_screenshot(view) 拿 image content 块（长 base64 会折行，
    所以按 content 块取原始 base64，别走 JSON 字符串）。
    机位用显式 position/target，比 locked_angle 稳（locked_angle 在本机没换过机位）。"""
    import bb_shot  # 同目录，延迟导入避免循环

    if cam or target:
        mcp("set_camera_angle", {"view": view, "projection": "perspective",
                                 "position": cam or [0, 16, -60], "target": target or [0, 16, 0]})
    p = bb_shot.shot(view=view, out=str(path))
    if not p:
        return "抓图失败（见上文回报）"
    return f"{p} ({p.stat().st_size} bytes)"


def build_geo(model: dict) -> dict:
    """把生成器的 dump 组装成 bedrock 1.12.0 几何（GeckoLib 直接吃）。"""
    names = {b["name"] for b in model["bones"]}
    bones = []
    for b in model["bones"]:
        node = {"name": b["name"]}
        if b.get("parent"):
            assert b["parent"] in names, f"父骨不存在: {b['parent']} → {b['name']}"
            node["parent"] = b["parent"]
        node["pivot"] = [round(float(v), 4) for v in b["pivot"]]
        cubes = []
        for c in model["cubes"]:
            if c["bone"] != b["name"]:
                continue
            f, t = c["from"], c["to"]
            uv = {}
            for fn in ("north", "south", "east", "west", "up", "down"):
                r = c["uv"].get(fn)
                assert r, f"{c['name']} 缺 {fn} 面 UV"
                uv[fn] = {"uv": [int(r[0]), int(r[1])], "uv_size": [int(r[2]), int(r[3])]}
            cubes.append({
                "origin": [round(float(v), 4) for v in f],
                "size": [round(float(t[i] - f[i]), 4) for i in range(3)],
                "uv": uv,
            })
        if cubes:
            node["cubes"] = cubes
        bones.append(node)

    vb = model["visible_bounds"]
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {
                "identifier": f"geometry.{MODEL}",
                "texture_width": model["texture"]["w"],
                "texture_height": model["texture"]["h"],
                "visible_bounds_width": vb["width"],
                "visible_bounds_height": vb["height"],
                "visible_bounds_offset": vb["offset"],
            },
            "bones": bones,
        }],
    }


def main() -> int:
    want_shot = "--no-shot" not in sys.argv

    blank_png(BUILD / "marksman_blank.png")
    proj = ensure_project()
    print("工程：", json.dumps(proj, ensure_ascii=False))
    if proj.get("after") != "geckolib_model":
        print("FAIL：工程格式不是 geckolib_model，中止（别在半初始化的工程上建模型）")
        return 1

    res = run_generator()
    if not isinstance(res, dict):
        print("FAIL：生成器回报不是对象：", str(res)[:400])
        return 1
    if res.get("error"):
        print("FAIL：生成器报错 ->", res["error"])
        return 1

    for k in sorted(res):
        if k in ("png", "model"):
            continue
        v = res[k]
        if isinstance(v, (list, dict)):
            print("%-20s %s(%d)" % (k, type(v).__name__, len(v)))
        else:
            print("%-20s %s" % (k, v))

    chk = res["check"]
    model = res["model"]
    bad = []
    if not chk.get("elements_registered"):
        bad.append("体块没注册进 Project.elements（忘了 c.init() → 视口不渲染，就是白屏）")
    if not chk.get("canvas_128"):
        bad.append(f"贴图画布不是 128×128（实际 {res['tex'].get('canvas')}）")
    if chk["uv_overlaps"]:
        bad.append(f"UV 重叠 {chk['uv_overlaps']} 处")
    if chk["uv_out_of_bounds"]:
        bad.append(f"UV 越界 {chk['uv_out_of_bounds']} 处")
    if not chk["bone_rest_rot_all_zero"]:
        bad.append("有骨头 rest 旋转非零")
    if not chk["foot_at_zero"]:
        bad.append(f"脚底不在 Y=0（min={res['bbox']['min']}）")
    if not chk["top_at_32"]:
        bad.append(f"颅顶不是 Y=32（max={res['bbox']['max']}）")
    if chk["cube_rotations"]:
        bad.append(f"有 {chk['cube_rotations']} 个体块带旋转（本项目 mob 体块必须轴对齐）")
    if bad:
        print("FAIL：")
        for b in bad:
            print("  -", b)
        return 1

    geo = build_geo(model)
    geo_txt = json.dumps(geo, ensure_ascii=False, indent=2) + "\n"

    (ART / f"{MODEL}.geo.json").write_text(geo_txt, encoding="utf-8")
    if isinstance(res.get("png"), str) and res["png"].startswith("data:image/png;base64,"):
        (ART / f"{MODEL}.png").write_bytes(base64.b64decode(res["png"].split(",", 1)[1]))
    else:
        print("FAIL：生成器没回贴图 png")
        return 1

    (ART / "uv_ledger.json").write_text(json.dumps({
        "model": MODEL,
        "texture": model["texture"],
        "density_px_per_u": res["density"],
        "atlas_used_px": res["atlas_used_px"],
        "bbox": res["bbox"],
        "bones": model["bones"],
        "cubes": model["cubes"],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (SRC / "geo" / f"{MODEL}.geo.json").write_text(geo_txt, encoding="utf-8")
    tex_dir = SRC / "textures" / "entity"
    tex_dir.mkdir(parents=True, exist_ok=True)
    (tex_dir / f"{MODEL}.png").write_bytes((ART / f"{MODEL}.png").read_bytes())

    print()
    print("密度            %.2f px/u   图集占用 %d/128 px" % (res["density"], res["atlas_used_px"]))
    print("包围盒          min=%s max=%s  (%.1f 格高)" % (res["bbox"]["min"], res["bbox"]["max"], res["bbox"]["max"][1] / 16.0))
    print("面数/骨头/体块  %d / %d / %d" % (chk["faces_packed"], res["bones"], res["cubes"]))
    print("已落盘          %s" % (ART / f"{MODEL}.geo.json"))
    print("                %s" % (ART / f"{MODEL}.png"))
    print("                %s" % (SRC / "geo" / f"{MODEL}.geo.json"))
    print("                %s" % (tex_dir / f"{MODEL}.png"))
    if want_shot:
        print("截图(正面)     %s" % shot(BUILD / "marksman_shot_front.png", "main", [0, 16, -62], [0, 16, 0]))
        print("截图(左侧)     %s" % shot(BUILD / "marksman_shot_side.png", "main", [-62, 16, 0], [0, 16, 0]))
        print("截图(背后)     %s" % shot(BUILD / "marksman_shot_back.png", "main", [0, 18, 62], [0, 16, 0]))
        print("截图(3/4)      %s" % shot(BUILD / "marksman_shot.png", "main", [-44, 30, -44], [0, 14, 0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
