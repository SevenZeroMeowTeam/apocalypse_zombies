#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 tools/uzi_bb_gen.js 喂给 Blockbench 跑（生成器本体是函数体，末尾 return out）。

用法:  python tools/uzi_bb_run.py [生成器路径]
产出:  build/uzi_gen_out.json  —— 生成器自检的完整回报（含 spillover 全文）
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bbmcp_call as bb  # noqa: E402

src_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "uzi_bb_gen.js")
src = open(src_path, encoding="utf-8").read()
# risky_eval 的载荷不允许出现 console. 与 // 、/* */ 注释 —— 先剥掉注释再送。
# （生成器里没有含 // 或 /* 的字符串字面量，所以正则剥离是安全的）
import re  # noqa: E402
src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
src = re.sub(r"//[^\n]*", "", src)
code = src

sid = bb.handshake()
raw = bb.text_of(bb.call(sid, "risky_eval", {"code": code}))
out_path = os.path.join(ROOT, "build", "uzi_gen_out.json")
open(out_path, "w", encoding="utf-8").write(raw)

try:
    doc = json.loads(raw)
except Exception as e:
    print("回报不是 JSON（%s），原文 %d 字节 -> %s" % (e, len(raw), out_path))
    print(raw[:2000])
    sys.exit(1)

res = doc.get("result", doc)
if isinstance(res, str):
    try:
        res = json.loads(res)
    except Exception:
        pass

if isinstance(res, dict):
    import base64  # noqa: E402
    png = res.pop("png", None)
    if isinstance(png, str) and png.startswith("data:image/png;base64,"):
        blob = base64.b64decode(png.split(",", 1)[1])
        tp = os.path.join(ROOT, "build", "uzi_bb_tex.png")
        open(tp, "wb").write(blob)
        print("%-22s -> %s (%d bytes)" % ("png", tp, len(blob)))
    for k in sorted(res):
        v = res[k]
        if isinstance(v, (list, dict)):
            print("%-22s %s (%d)" % (k, type(v).__name__, len(v)))
        elif isinstance(v, str) and len(v) > 200:
            print("%-22s %s..." % (k, v[:200]))
        else:
            print("%-22s %s" % (k, v))
else:
    print(json.dumps(res)[:1500])
print("\n完整回报 -> %s" % out_path)

if "--no-export" not in sys.argv:
    gp = os.path.join(ROOT, "build", "uzi.geo.json").replace("\\", "/")
    r = bb.text_of(bb.call(sid, "geckolib_export_model",
                           {"path": gp, "mode": "compile", "max_content_length": 0}))
    print("geo export ->", r[:400])
